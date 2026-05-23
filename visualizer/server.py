import asyncio
import json
import serial
import serial.tools.list_ports
import threading
import time
import csv
import datetime
import math
import os
import websockets

# WebSocket server configuration
WS_HOST = "localhost"
WS_PORT = 8765

# CSV log configuration
CSV_FILE = "sensor_data.csv"

# Global state
connected_clients = set()
serial_lock = threading.Lock()
active_port = None          # Name of the active port (e.g. "COM3", "SIMULATOR")
reader_thread = None
reader_stop_event = None
data_queue = asyncio.Queue()

# Recording state
is_recording = False
recording_lock = threading.Lock()

def get_available_ports():
    """Returns a list of available serial port names, ensuring COM3 is first if present."""
    ports = [p.device for p in serial.tools.list_ports.comports()]
    # Put COM3 at the beginning of the list if it exists
    if "COM3" in ports:
        ports.remove("COM3")
        ports.insert(0, "COM3")
    else:
        # If COM3 is not physically present, we can append it as a placeholder/option
        ports.insert(0, "COM3")
        
    if "SIMULATOR" not in ports:
        ports.append("SIMULATOR")
    return ports

def convert_ldr(raw_val):
    """Converts 10-bit raw ADC to light percentage (0-100%)."""
    return round((raw_val / 1023.0) * 100.0, 1)

def convert_temp(raw_val):
    """Converts 10-bit raw ADC to Temp in °C (LM35 at 5V reference: Vout = Temp * 10mV)."""
    # Vout = raw_val * 5000mV / 1023
    # Temp_C = Vout / 10 = raw_val * 500 / 1023 = raw_val * 0.48876
    return round(raw_val * 0.48876, 1)

def convert_hum(raw_val):
    """Converts 10-bit raw ADC to humidity percentage (0-100%), inverting the raw value
    since Dry = high ADC (~1023) and Wet = low ADC (~0)."""
    inverted_val = 1023 - raw_val
    return round((inverted_val / 1023.0) * 100.0, 1)

def log_to_csv(timestamp, ldr_pct, temp_c, hum_pct):
    """Appends converted sensor values to the CSV file if recording is active."""
    global is_recording
    with recording_lock:
        if not is_recording:
            return
            
    file_exists = os.path.exists(CSV_FILE)
    try:
        with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Fecha_Hora", "Luz_Porcentaje", "Temperatura_C", "Humedad_Porcentaje"])
            writer.writerow([timestamp, ldr_pct, temp_c, hum_pct])
    except Exception as e:
        print(f"Error writing to CSV: {e}")

def serial_reader_loop(port_name, baud, loop, stop_event):
    """Target function for reading from the actual physical/virtual serial port."""
    print(f"Starting serial reader thread for {port_name}...")
    try:
        ser = serial.Serial(port_name, baud, timeout=0.5)
        # Notify success
        asyncio.run_coroutine_threadsafe(
            data_queue.put({"status": "connected", "port": port_name}), loop
        )
    except Exception as e:
        print(f"Failed to open serial port {port_name}: {e}")
        asyncio.run_coroutine_threadsafe(
            data_queue.put({"status": "error", "message": f"Could not open {port_name}: {str(e)}"}), loop
        )
        return

    buf = bytearray()
    while not stop_event.is_set():
        try:
            # Read 1 byte (blocking read with 0.5s timeout)
            b = ser.read(1)
            if not b:
                continue
            val = b[0]
            buf.append(val)

            # Dual mode parsing:
            
            # --- Format A: Binary ---
            # Packet starts with 0xFF and is 7 bytes long
            if buf[0] == 0xFF:
                if len(buf) >= 7:
                    # Reconstruct 10-bit raw ADC values
                    raw_ldr = (buf[1] << 8) | buf[2]
                    raw_temp = (buf[3] << 8) | buf[4]
                    raw_hum = (buf[5] << 8) | buf[6]
                    
                    # Apply conversions
                    ldr_pct = convert_ldr(raw_ldr)
                    temp_c = convert_temp(raw_temp)
                    hum_pct = convert_hum(raw_hum)
                    
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    log_to_csv(timestamp, ldr_pct, temp_c, hum_pct)

                    asyncio.run_coroutine_threadsafe(
                        data_queue.put({
                            "type": "data",
                            "ldr": ldr_pct,
                            "temp": temp_c,
                            "hum": hum_pct,
                            "timestamp": timestamp
                        }), loop
                    )
                    buf = bytearray()
                continue

            # --- Format B: ASCII ---
            # If the first byte is not 0xFF, it could be ASCII.
            # If we hit a newline (0x0A = '\n'), we parse the accumulated buffer.
            if val == 0x0A:  # '\n'
                try:
                    line = buf.decode('ascii', errors='ignore').strip()
                    parts = line.split(',')
                    if len(parts) == 3:
                        raw_ldr = int(parts[0])
                        raw_temp = int(parts[1])
                        raw_hum = int(parts[2])
                        
                        ldr_pct = convert_ldr(raw_ldr)
                        temp_c = convert_temp(raw_temp)
                        hum_pct = convert_hum(raw_hum)
                        
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        log_to_csv(timestamp, ldr_pct, temp_c, hum_pct)

                        asyncio.run_coroutine_threadsafe(
                            data_queue.put({
                                "type": "data",
                                "ldr": ldr_pct,
                                "temp": temp_c,
                                "hum": hum_pct,
                                "timestamp": timestamp
                            }), loop
                        )
                except Exception as e:
                    # Silent ignore if decoding/parsing fails
                    pass
                buf = bytearray()
                continue

            # --- Buffer Overflow Prevention ---
            # If buffer doesn't start with 0xFF and is growing without a newline,
            # or if it's too long (> 30 bytes), clear it or search for a 0xFF.
            if len(buf) > 30:
                if 0xFF in buf:
                    idx = buf.index(0xFF)
                    buf = buf[idx:]
                else:
                    buf = bytearray()

        except Exception as e:
            print(f"Error in serial reader thread: {e}")
            asyncio.run_coroutine_threadsafe(
                data_queue.put({"status": "error", "message": f"Serial read error: {str(e)}"}), loop
            )
            break

    ser.close()
    print(f"Closed serial port {port_name}")
    asyncio.run_coroutine_threadsafe(
        data_queue.put({"status": "disconnected"}), loop
    )

def simulator_reader_loop(loop, stop_event):
    """Target function for generating simulated converted sensor data (5Hz)."""
    print("Starting simulator reader thread...")
    asyncio.run_coroutine_threadsafe(
        data_queue.put({"status": "connected", "port": "SIMULATOR"}), loop
    )

    t = 0
    while not stop_event.is_set():
        # Generate clean minimalist-like mock waveforms directly as converted values
        # LDR: light level varying slowly (0-100%)
        ldr_pct = round(50.0 + 35.0 * math.sin(t * 0.02) + math.sin(t * 0.1) * 2.0, 1)
        ldr_pct = max(0.0, min(100.0, ldr_pct))
        
        # Temperature: varying around 24 degrees C.
        temp_c = round(24.0 + 4.0 * math.sin(t * 0.05) + math.sin(t * 0.3) * 0.3, 1)
        
        # Humidity: varying around 55%
        hum_pct = round(55.0 + 12.0 * math.cos(t * 0.04) + math.sin(t * 0.2) * 0.8, 1)
        hum_pct = max(0.0, min(100.0, hum_pct))

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Log to CSV (only if is_recording is True inside log_to_csv)
        log_to_csv(timestamp, ldr_pct, temp_c, hum_pct)

        # Queue for broadcast
        asyncio.run_coroutine_threadsafe(
            data_queue.put({
                "type": "data",
                "ldr": ldr_pct,
                "temp": temp_c,
                "hum": hum_pct,
                "timestamp": timestamp
            }), loop
        )
        t += 1
        time.sleep(0.2)  # 200 ms (5Hz)

    print("Stopped simulator reader thread")
    asyncio.run_coroutine_threadsafe(
        data_queue.put({"status": "disconnected"}), loop
    )

def start_connection(port_name):
    """Starts the reader thread for the specified port (either simulator or serial COM port)."""
    global active_port, reader_thread, reader_stop_event
    with serial_lock:
        if active_port is not None:
            stop_connection_sync()

        active_port = port_name
        reader_stop_event = threading.Event()
        loop = asyncio.get_event_loop()

        if port_name == "SIMULATOR":
            reader_thread = threading.Thread(
                target=simulator_reader_loop,
                args=(loop, reader_stop_event),
                daemon=True
            )
        else:
            reader_thread = threading.Thread(
                target=serial_reader_loop,
                args=(port_name, 9600, loop, reader_stop_event),
                daemon=True
            )
        reader_thread.start()

def stop_connection_sync():
    """Synchronous stopping helper."""
    global active_port, reader_thread, reader_stop_event
    if reader_stop_event:
        reader_stop_event.set()
    if reader_thread:
        reader_thread.join(timeout=2.0)
    active_port = None
    reader_thread = None
    reader_stop_event = None

async def stop_connection():
    """Asynchronously stops the reader thread."""
    global active_port
    if active_port is not None:
        await asyncio.to_thread(stop_connection_sync)

async def broadcast(message):
    """Broadcasts a JSON message to all connected WebSocket clients."""
    if connected_clients:
        payload = json.dumps(message)
        await asyncio.gather(*[client.send(payload) for client in connected_clients], return_exceptions=True)

async def queue_listener():
    """Listens to the data queue and broadcasts incoming data to all clients."""
    while True:
        item = await data_queue.get()
        if "status" in item:
            await broadcast({
                "type": "status",
                "status": item["status"],
                "port": item.get("port"),
                "message": item.get("message")
            })
        elif item.get("type") == "data":
            await broadcast(item)
        data_queue.task_done()

async def handler(websocket):
    """WebSocket client message handler."""
    global active_port, is_recording
    connected_clients.add(websocket)
    print(f"Client connected: {websocket.remote_address}. Active clients: {len(connected_clients)}")

    # Send initial configuration to the client
    await websocket.send(json.dumps({
        "type": "init",
        "ports": get_available_ports(),
        "active_port": active_port,
        "status": "connected" if active_port else "disconnected",
        "recording": is_recording
    }))

    try:
        async for message in websocket:
            data = json.loads(message)
            command = data.get("command")

            if command == "get_ports":
                await websocket.send(json.dumps({
                    "type": "ports",
                    "ports": get_available_ports()
                }))

            elif command == "connect":
                port = data.get("port")
                if port:
                    print(f"Request to connect to port: {port}")
                    start_connection(port)
                else:
                    await websocket.send(json.dumps({
                        "type": "status",
                        "status": "error",
                        "message": "No port name specified."
                    }))

            elif command == "disconnect":
                print("Request to disconnect")
                await stop_connection()

            elif command == "start_recording":
                print("Start recording data to CSV")
                with recording_lock:
                    is_recording = True
                await broadcast({
                    "type": "recording_status",
                    "recording": True
                })

            elif command == "stop_recording":
                print("Stop recording data to CSV")
                with recording_lock:
                    is_recording = False
                await broadcast({
                    "type": "recording_status",
                    "recording": False
                })

    except websockets.exceptions.ConnectionClosedOK:
        pass
    except Exception as e:
        print(f"Error handling message: {e}")
    finally:
        connected_clients.remove(websocket)
        print(f"Client disconnected. Active clients: {len(connected_clients)}")

async def main():
    # Start the data queue broadcaster task
    asyncio.create_task(queue_listener())

    # Start the WebSocket server
    print(f"Starting WebSocket server on ws://{WS_HOST}:{WS_PORT}...")
    async with websockets.serve(handler, WS_HOST, WS_PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down server...")
        stop_connection_sync()
