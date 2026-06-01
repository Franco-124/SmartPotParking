"""
Fuente de datos.

DEMO_MODE = True  → datos simulados (sin hardware)
DEMO_MODE = False → lee del puerto serie del ESP32

FORMATO DEL ESP32:
    DATA,<dist_a>,<dist_b>,<dist_c>,<dist_d>,<co_raw>
"""

import random
import time
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from settings import DEMO_MODE, SERIAL_PORT, SERIAL_BAUD, SERIAL_TIMEOUT

# ── Conexión serie (solo si no es modo demo) ───────────────────────────────

_ser = None

if not DEMO_MODE:
    import serial as _pyserial
    _ser = _pyserial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
    print(f"[SmartSpot] Puerto serie conectado: {SERIAL_PORT} @ {SERIAL_BAUD} baud")
else:
    print("[SmartSpot] DEMO MODE activo — usando datos simulados.")


# ── Mock ───────────────────────────────────────────────────────────────────

_OCUPADO_S     = 8.0
_LIBRE_S       = 5.0
_CICLO         = _OCUPADO_S + _LIBRE_S
_OFFSETS       = (0.0, 6.0, 3.0, 10.0)


def _mock_reading() -> dict:
    t = time.time()
    def dist(offset: float) -> float:
        fase = (t + offset) % _CICLO
        lo, hi = (5.0, 9.0) if fase < _OCUPADO_S else (12.0, 30.0)
        return round(random.uniform(lo, hi), 1)

    return {
        "puesto_a":  dist(_OFFSETS[0]),
        "puesto_b":  dist(_OFFSETS[1]),
        "puesto_c":  dist(_OFFSETS[2]),
        "puesto_d":  dist(_OFFSETS[3]),
        "co_raw":    int(random.uniform(300, 750)),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


# ── Parser ─────────────────────────────────────────────────────────────────

def _parse_line(line: str) -> dict | None:
    parts = line.strip().split(",")
    if len(parts) != 6 or parts[0] != "DATA":
        return None
    try:
        return {
            "puesto_a": float(parts[1]),
            "puesto_b": float(parts[2]),
            "puesto_c": float(parts[3]),
            "puesto_d": float(parts[4]),
            "co_raw":   int(float(parts[5])),
        }
    except ValueError:
        return None


# ── API pública ────────────────────────────────────────────────────────────

def get_source() -> str:
    return "demo" if DEMO_MODE else "serial"


def get_reading() -> dict | None:
    if DEMO_MODE:
        time.sleep(0.8)          # simula cadencia del ESP32
        return _mock_reading()

    for _ in range(10):
        line = _ser.readline().decode("utf-8", errors="ignore")
        parsed = _parse_line(line)
        if parsed:
            parsed["timestamp"] = datetime.now().isoformat(timespec="seconds")
            return parsed
    return None
