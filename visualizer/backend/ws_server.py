import asyncio
import json
import threading

import serial.tools.list_ports
import websockets

from . import csv_logger
from .serial_reader import serial_reader_loop, simulator_reader_loop

connected_clients = set()
_serial_lock      = threading.Lock()
_active_port      = None
_reader_thread    = None
_reader_stop_event = None


# ─── Puertos ──────────────────────────────────────────────────────────────────

def get_available_ports():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    if "COM3" in ports:
        ports.remove("COM3")
        ports.insert(0, "COM3")
    else:
        ports.insert(0, "COM3")
    if "SIMULATOR" not in ports:
        ports.append("SIMULATOR")
    return ports


# ─── Broadcast ────────────────────────────────────────────────────────────────

async def broadcast(message):
    if connected_clients:
        payload = json.dumps(message)
        await asyncio.gather(
            *[client.send(payload) for client in connected_clients],
            return_exceptions=True,
        )


async def queue_listener(data_queue):
    while True:
        item = await data_queue.get()
        if "status" in item:
            await broadcast({
                "type":    "status",
                "status":  item["status"],
                "port":    item.get("port"),
                "message": item.get("message"),
            })
        elif item.get("type") == "data":
            await broadcast(item)
        data_queue.task_done()


# ─── Gestión de conexión serial ───────────────────────────────────────────────

def start_connection(port_name, data_queue):
    global _active_port, _reader_thread, _reader_stop_event
    with _serial_lock:
        if _active_port is not None:
            stop_connection_sync()

        _active_port       = port_name
        _reader_stop_event = threading.Event()
        loop               = asyncio.get_event_loop()

        if port_name == "SIMULATOR":
            target = simulator_reader_loop
            args   = (loop, _reader_stop_event, data_queue)
        else:
            target = serial_reader_loop
            args   = (port_name, 9600, loop, _reader_stop_event, data_queue)

        _reader_thread = threading.Thread(target=target, args=args, daemon=True)
        _reader_thread.start()


def stop_connection_sync():
    global _active_port, _reader_thread, _reader_stop_event
    if _reader_stop_event:
        _reader_stop_event.set()
    if _reader_thread:
        _reader_thread.join(timeout=2.0)
    _active_port       = None
    _reader_thread     = None
    _reader_stop_event = None


async def stop_connection():
    if _active_port is not None:
        await asyncio.to_thread(stop_connection_sync)


# ─── Handler WebSocket ────────────────────────────────────────────────────────

def make_handler(data_queue):
    """Devuelve el handler de WebSocket con acceso al data_queue."""

    async def handler(websocket):
        global _active_port
        connected_clients.add(websocket)
        print(f"Client connected. Active clients: {len(connected_clients)}")

        await websocket.send(json.dumps({
            "type":        "init",
            "ports":       get_available_ports(),
            "active_port": _active_port,
            "status":      "connected" if _active_port else "disconnected",
            "recording":   csv_logger.is_recording(),
        }))

        try:
            async for message in websocket:
                data    = json.loads(message)
                command = data.get("command")

                if command == "get_ports":
                    await websocket.send(json.dumps({
                        "type":  "ports",
                        "ports": get_available_ports(),
                    }))

                elif command == "connect":
                    port = data.get("port")
                    if port:
                        start_connection(port, data_queue)
                    else:
                        await websocket.send(json.dumps({
                            "type": "status", "status": "error",
                            "message": "No port name specified.",
                        }))

                elif command == "disconnect":
                    await stop_connection()

                elif command == "start_recording":
                    csv_logger.start()
                    await broadcast({"type": "recording_status", "recording": True})

                elif command == "stop_recording":
                    csv_logger.stop()
                    await broadcast({"type": "recording_status", "recording": False})

        except websockets.exceptions.ConnectionClosedOK:
            pass
        except Exception as e:
            print(f"Error handling message: {e}")
        finally:
            connected_clients.remove(websocket)
            print(f"Client disconnected. Active clients: {len(connected_clients)}")

    return handler
