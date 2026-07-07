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

# Model weights (loaded from weights.json)
WEIGHTS_FILE = "weights.json"
model_weights = None

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

def load_weights():
    """Loads perceptron weights from weights.json in the current folder."""
    global model_weights
    try:
        with open(WEIGHTS_FILE, "r", encoding="utf-8") as f:
            model_weights = json.load(f)
    except Exception as e:
        print(f"Error loading weights.json: {e}")
        model_weights = None

def compute_class(raw_ldr, raw_temp, raw_hum):
    """Computes perceptron class from raw 10-bit ADC values."""
    if not model_weights:
        return 0

    # Downscale to ADC8 (0-255) to match training
    ldr8 = (raw_ldr >> 2) & 0xFF
    temp8 = (raw_temp >> 2) & 0xFF
    hum8 = (raw_hum >> 2) & 0xFF

    norm = model_weights["normalization"]
    mean = norm["mean"]
    scale = norm["scale_mul"]

    x_h = (hum8 - mean["hum"]) * scale["hum"]
    x_t = (temp8 - mean["temp"]) * scale["temp"]
    x_l = (ldr8 - mean["ldr"]) * scale["ldr"]

    p1 = model_weights["perceptron_riego"]
    p2 = model_weights["perceptron_sol"]

    z1 = (x_h * p1["w_hum"]) + (x_t * p1["w_temp"]) + (x_l * p1["w_luz"]) + p1["bias"]
    if z1 >= 0:
        return 1

    z2 = (x_h * p2["w_hum"]) + (x_t * p2["w_temp"]) + (x_l * p2["w_luz"]) + p2["bias"]
    if z2 >= 0:
        return 2

    return 0

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

def log_to_csv(timestamp, ldr_pct, temp_c, hum_pct, clase):
    """Appends converted sensor values and model class to the CSV file if recording is active."""
    global is_recording
    with recording_lock:
        if not is_recording:
            return
            
    file_exists = os.path.exists(CSV_FILE)
    try:
        with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Fecha_Hora", "Luz_Porcentaje", "Temperatura_C", "Humedad_Porcentaje", "Clase_Inferencia"])
            writer.writerow([timestamp, ldr_pct, temp_c, hum_pct, clase])
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
            # Packet starts with 0xFF and is 7 bytes long: [0xFF][LUZ_H][LUZ_L][TEMP_H][TEMP_L][HUM_H][HUM_L]
            if buf[0] == 0xFF:
                if len(buf) >= 7:
                    # Reconstruct 10-bit raw ADC values
                    raw_ldr = (buf[1] << 8) | buf[2]
                    raw_temp = (buf[3] << 8) | buf[4]
                    raw_hum = (buf[5] << 8) | buf[6]

                    clase = compute_class(raw_ldr, raw_temp, raw_hum)

                    # Send class back to PIC (single byte)
                    try:
                        ser.write(bytes([clase & 0xFF]))
                    except Exception as e:
                        print(f"Error writing class to serial: {e}")
                    
                    # Apply conversions
                    ldr_pct = convert_ldr(raw_ldr)
                    temp_c = convert_temp(raw_temp)
                    hum_pct = convert_hum(raw_hum)
                    
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    log_to_csv(timestamp, ldr_pct, temp_c, hum_pct, clase)

                    asyncio.run_coroutine_threadsafe(
                        data_queue.put({
                            "type": "data",
                            "ldr": ldr_pct,
                            "temp": temp_c,
                            "hum": hum_pct,
                            "clase": clase,
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
                    if len(parts) >= 3:
                        raw_ldr = int(parts[0])
                        raw_temp = int(parts[1])
                        raw_hum = int(parts[2])
                        clase = compute_class(raw_ldr, raw_temp, raw_hum)

                        try:
                            ser.write(bytes([clase & 0xFF]))
                        except Exception:
                            pass
                        
                        ldr_pct = convert_ldr(raw_ldr)
                        temp_c = convert_temp(raw_temp)
                        hum_pct = convert_hum(raw_hum)
                        
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        log_to_csv(timestamp, ldr_pct, temp_c, hum_pct, clase)

                        asyncio.run_coroutine_threadsafe(
                            data_queue.put({
                                "type": "data",
                                "ldr": ldr_pct,
                                "temp": temp_c,
                                "hum": hum_pct,
                                "clase": clase,
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
    """Target function for generating simulated converted sensor data (5Hz) with Perceptron decision."""
    print("Starting simulator reader thread...")
    asyncio.run_coroutine_threadsafe(
        data_queue.put({"status": "connected", "port": "SIMULATOR"}), loop
    )

    t = 0
    while not stop_event.is_set():
        # Generate clean waves
        ldr_pct = round(50.0 + 35.0 * math.sin(t * 0.02) + math.sin(t * 0.1) * 2.0, 1)
        ldr_pct = max(0.0, min(100.0, ldr_pct))
        
        temp_c = round(24.0 + 4.0 * math.sin(t * 0.05) + math.sin(t * 0.3) * 0.3, 1)
        
        hum_pct = round(55.0 + 20.0 * math.cos(t * 0.04) + math.sin(t * 0.2) * 0.8, 1)
        hum_pct = max(0.0, min(100.0, hum_pct))

        # Convert to raw 10-bit to reuse compute_class
        raw_ldr = int(round((ldr_pct / 100.0) * 1023.0))
        raw_temp = int(round((temp_c / 0.48876)))
        raw_hum = int(round((1.0 - (hum_pct / 100.0)) * 1023.0))
        raw_ldr = max(0, min(1023, raw_ldr))
        raw_temp = max(0, min(1023, raw_temp))
        raw_hum = max(0, min(1023, raw_hum))

        clase = compute_class(raw_ldr, raw_temp, raw_hum)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        log_to_csv(timestamp, ldr_pct, temp_c, hum_pct, clase)

        asyncio.run_coroutine_threadsafe(
            data_queue.put({
                "type": "data",
                "ldr": ldr_pct,
                "temp": temp_c,
                "hum": hum_pct,
                "clase": clase,
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
    load_weights()
    # Start the data queue broadcaster task
    asyncio.create_task(queue_listener())

    # Start the WebSocket server
    print(f"Starting WebSocket server on ws://{WS_HOST}:{WS_PORT}...")
    
    # Automatically open index.html in default browser
    try:
        import webbrowser
        html_path = os.path.abspath("index.html")
        if os.path.exists(html_path):
            file_url = "file:///" + html_path.replace("\\", "/")
            print(f"Opening dashboard: {file_url}")
            # Give the server a tiny fraction of a second to bind the port
            await asyncio.sleep(0.5)
            webbrowser.open(file_url)
    except Exception as e:
        print(f"Could not open browser: {e}")

    async with websockets.serve(handler, WS_HOST, WS_PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down server...")
        stop_connection_sync()
