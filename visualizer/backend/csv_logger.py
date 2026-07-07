import csv
import os
import threading

CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'sensor_data.csv')

_is_recording = False
_lock = threading.Lock()


def start():
    global _is_recording
    with _lock:
        _is_recording = True


def stop():
    global _is_recording
    with _lock:
        _is_recording = False


def is_recording():
    with _lock:
        return _is_recording


def log(timestamp, ldr_pct, temp_c, hum_pct):
    with _lock:
        if not _is_recording:
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
