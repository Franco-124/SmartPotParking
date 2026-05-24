"""
Abstracción de fuente de datos.

PRINCIPIO DE DISEÑO:
get_reading() es el ÚNICO punto de integración con el hardware.
Todo el sistema (app.py, database.py) consume exclusivamente esta función.
Al conectar el ESP32, reemplaza SOLO el cuerpo de get_reading() — nada más.

── INTEGRACIÓN ESP32 ──────────────────────────────────────────────────────────
LÍNEA A MODIFICAR: cuerpo de get_reading() a partir del comentario "# ← SERIAL".

Ejemplo con pyserial (agregar 'pyserial' a requirements.txt):

    import serial
    _ser = serial.Serial("COM3", 115200, timeout=2)  # ajusta puerto y baudrate

    def get_reading() -> dict:  # ← SERIAL: reemplaza desde aquí
        raw = _ser.readline().decode().strip()   # ESP32 envía "12.3,8.7\\n"
        a, b = map(float, raw.split(","))
        return {
            "puesto_a": a,
            "puesto_b": b,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
──────────────────────────────────────────────────────────────────────────────
"""

import random
import time
from datetime import datetime

# Parámetros del ciclo simulado.
# Son constantes de implementación del mock, no del dominio,
# por eso viven aquí y no en config.py: cuando se active el serial son irrelevantes.
_OCUPADO_S: float = 8.0    # segundos con vehículo presente → distancia corta
_LIBRE_S:   float = 5.0    # segundos con celda vacía       → distancia larga
_CICLO:     float = _OCUPADO_S + _LIBRE_S   # 13 s por ciclo completo

# Puesto B arranca desplazado 6 s respecto a Puesto A.
# Con este offset, durante la mayor parte del ciclo ambos puestos están en
# estados contrarios, haciendo visibles OCUPADO y LIBRE simultáneamente.
_B_OFFSET: float = 6.0

_RANGO_OCUPADO = (5.0, 9.0)     # distancias con vehículo (≤ umbral 10 cm)
_RANGO_LIBRE   = (12.0, 30.0)   # distancias sin vehículo (> umbral 10 cm)


def _dist_por_fase(fase: float) -> float:
    """Retorna una distancia aleatoria según la fase actual del ciclo."""
    lo, hi = _RANGO_OCUPADO if fase < _OCUPADO_S else _RANGO_LIBRE
    return round(random.uniform(lo, hi), 1)


def get_reading() -> dict:
    """
    Retorna la lectura actual de ambos sensores.

    Contrato de retorno — invariante para app.py independientemente de la fuente:
        {
            "puesto_a": float,   # distancia en cm del sensor A
            "puesto_b": float,   # distancia en cm del sensor B
            "timestamp": str     # ISO-8601, precisión de segundos
        }

    # ← SERIAL: reemplaza el cuerpo de esta función al conectar el ESP32.
    """
    t = time.time()
    return {
        "puesto_a": _dist_por_fase(t % _CICLO),
        "puesto_b": _dist_por_fase((t + _B_OFFSET) % _CICLO),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
