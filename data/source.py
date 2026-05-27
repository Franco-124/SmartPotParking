"""
Fuente de datos — solo puerto serie.

FORMATO DEL ESP32:
    DATA,<dist_a>,<dist_b>,<dist_c>,<dist_d>,<co_raw>
    Ejemplo: DATA,12.35,6.86,0.03,999.00,478

    - dist_*  : distancia en cm (999.00 = fuera de rango del HC-SR04)
    - co_raw  : valor ADC crudo del sensor MQ7 (CO)
"""

from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from settings import SERIAL_PORT, SERIAL_BAUD, SERIAL_TIMEOUT

# ── Conexión serie (singleton de módulo) ───────────────────────────────────

_ser = None


def _init_serial() -> None:
    global _ser
    import serial as _pyserial
    port = SERIAL_PORT
    _ser = _pyserial.Serial(port, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
    print(f"[SmartSpot] Puerto serie conectado: {port} @ {SERIAL_BAUD} baud")


_init_serial()


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
    return "serial"


def get_reading() -> dict | None:
    """
    Lee hasta 10 líneas del ESP32 buscando una válida DATA,...
    Retorna el dict con los valores o None si no llegó dato válido.
    """
    for _ in range(10):
        line = _ser.readline().decode("utf-8", errors="ignore")
        parsed = _parse_line(line)
        if parsed:
            parsed["timestamp"] = datetime.now().isoformat(timespec="seconds")
            return parsed
    return None
