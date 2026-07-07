import asyncio
import datetime
import json
import math
import os
import time
import threading

import serial

from . import csv_logger
from .converters import convert_ldr, convert_temp, convert_hum


def _load_weights():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'weights.json')
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {
            "normalization": {"mean": {"hum": 165, "temp": 19, "ldr": 166},
                              "scale_mul": {"hum": 4, "temp": 36, "ldr": 4}},
            "perceptron_riego": {"w_hum": 15, "w_temp": 1, "w_luz": -2, "bias": -2621},
            "perceptron_sol":   {"w_hum": 2,  "w_temp": 12, "w_luz": 9, "bias": -1966},
        }


def _pic_classify(hum_pct, temp_c, ldr_pct, weights):
    norm = weights["normalization"]
    adc8_hum  = max(0, min(255, round(255 - hum_pct * 2.55)))
    adc8_temp = max(0, min(255, round(temp_c / 1.953)))
    adc8_luz  = max(0, min(255, round(ldr_pct * 2.55)))

    x_h = (adc8_hum  - norm["mean"]["hum"])  * norm["scale_mul"]["hum"]
    x_t = (adc8_temp - norm["mean"]["temp"]) * norm["scale_mul"]["temp"]
    x_l = (adc8_luz  - norm["mean"]["ldr"])  * norm["scale_mul"]["ldr"]

    r = weights["perceptron_riego"]
    z1 = x_h * r["w_hum"] + x_t * r["w_temp"] + x_l * r["w_luz"] + r["bias"]
    if z1 >= 0:
        return 1

    # P2 no usa temperatura (igual que el ASM: EVAL_P2 solo opera HUM y LUZ)
    s = weights["perceptron_sol"]
    z2 = x_h * s["w_hum"] + x_l * s["w_luz"] + s["bias"]
    return 2 if z2 >= 0 else 0


def serial_reader_loop(port_name, baud, loop, stop_event, data_queue):
    print(f"Starting serial reader thread for {port_name}...")
    try:
        ser = serial.Serial(port_name, baud, timeout=0.5)
        asyncio.run_coroutine_threadsafe(
            data_queue.put({"status": "connected", "port": port_name}), loop
        )
    except Exception as e:
        asyncio.run_coroutine_threadsafe(
            data_queue.put({"status": "error", "message": f"Could not open {port_name}: {str(e)}"}), loop
        )
        return

    buf = bytearray()
    while not stop_event.is_set():
        try:
            b = ser.read(1)
            if not b:
                continue
            val = b[0]
            buf.append(val)

            # --- Formato binario (0xFF header + 6 bytes datos + 1 byte CLASE = 8 bytes) ---
            if buf[0] == 0xFF:
                if len(buf) >= 8:
                    raw_ldr  = (buf[1] << 8) | buf[2]
                    raw_temp = (buf[3] << 8) | buf[4]
                    raw_hum  = (buf[5] << 8) | buf[6]
                    classification = buf[7]

                    ldr_pct = convert_ldr(raw_ldr)
                    temp_c  = convert_temp(raw_temp)
                    hum_pct = convert_hum(raw_hum)

                    timestamp = _now()
                    csv_logger.log(timestamp, ldr_pct, temp_c, hum_pct)
                    asyncio.run_coroutine_threadsafe(
                        data_queue.put({
                            "type": "data",
                            "ldr": ldr_pct, "temp": temp_c, "hum": hum_pct,
                            "alert": classification, "timestamp": timestamp,
                        }), loop
                    )
                    buf = bytearray()
                continue

            # --- Formato ASCII ---
            if val == 0x0A:  # '\n'
                try:
                    line  = buf.decode("ascii", errors="ignore").strip()
                    parts = line.split(",")
                    raw_ldr = raw_temp = raw_hum = 0
                    classification = -1

                    if ":" in line:
                        kv = {}
                        for part in parts:
                            part = part.strip()
                            if ":" in part:
                                k, v = part.split(":", 1)
                                try:
                                    kv[k.upper()] = int(v.strip())
                                except ValueError:
                                    pass
                        if all(k in kv for k in ("H", "T", "L")):
                            raw_hum  = kv["H"]
                            raw_temp = kv["T"]
                            raw_ldr  = kv["L"]
                            classification = kv.get("C", -1)
                        else:
                            buf = bytearray()
                            continue
                    elif len(parts) >= 3:
                        raw_ldr  = int(parts[0])
                        raw_temp = int(parts[1])
                        raw_hum  = int(parts[2])
                        if len(parts) >= 4:
                            classification = int(parts[3])
                    else:
                        buf = bytearray()
                        continue

                    ldr_pct = convert_ldr(raw_ldr)
                    temp_c  = convert_temp(raw_temp)
                    hum_pct = convert_hum(raw_hum)

                    timestamp = _now()
                    csv_logger.log(timestamp, ldr_pct, temp_c, hum_pct)
                    asyncio.run_coroutine_threadsafe(
                        data_queue.put({
                            "type": "data",
                            "ldr": ldr_pct, "temp": temp_c, "hum": hum_pct,
                            "alert": classification, "timestamp": timestamp,
                        }), loop
                    )
                except Exception:
                    pass
                buf = bytearray()
                continue

            if len(buf) > 30:
                if 0xFF in buf:
                    buf = buf[buf.index(0xFF):]
                else:
                    buf = bytearray()

        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                data_queue.put({"status": "error", "message": f"Serial read error: {str(e)}"}), loop
            )
            break

    ser.close()
    print(f"Closed serial port {port_name}")
    asyncio.run_coroutine_threadsafe(data_queue.put({"status": "disconnected"}), loop)


def simulator_reader_loop(loop, stop_event, data_queue):
    print("Starting simulator reader thread...")
    asyncio.run_coroutine_threadsafe(
        data_queue.put({"status": "connected", "port": "SIMULATOR"}), loop
    )

    weights = _load_weights()
    t = 0
    while not stop_event.is_set():
        # Humedad: barre 0-71% para cruzar la zona Riego (< 20%)
        hum_pct = round(35.0 + 36.0 * math.sin(t * 0.015), 1)
        hum_pct = max(0.0, min(100.0, hum_pct))

        # Temperatura: barre 12-52°C para cruzar la zona Sol (> 43°C)
        temp_c  = round(32.0 + 20.0 * math.sin(t * 0.022), 1)

        # Luz: barre 10-100% para cruzar la zona Sol (> 71% junto con temp alta)
        ldr_pct = round(55.0 + 45.0 * math.sin(t * 0.018 + 1.0), 1)
        ldr_pct = max(0.0, min(100.0, ldr_pct))

        sim_alert = _pic_classify(hum_pct, temp_c, ldr_pct, weights)

        timestamp = _now()
        csv_logger.log(timestamp, ldr_pct, temp_c, hum_pct)
        asyncio.run_coroutine_threadsafe(
            data_queue.put({
                "type": "data",
                "ldr": ldr_pct, "temp": temp_c, "hum": hum_pct,
                "alert": sim_alert, "timestamp": timestamp,
            }), loop
        )
        t += 1
        time.sleep(0.2)

    print("Stopped simulator reader thread")
    asyncio.run_coroutine_threadsafe(data_queue.put({"status": "disconnected"}), loop)


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
