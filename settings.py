"""
Único punto de verdad para todas las constantes del sistema.
Cambiar el umbral, colores o nombres de celda es una sola línea aquí;
ningún otro archivo necesita modificarse.
"""
from __future__ import annotations

# Umbral de ocupación en cm. Distancia <= umbral → OCUPADO, > umbral → LIBRE.
UMBRAL_OCUPACION: float = 10.0

# Path del archivo SQLite relativo al directorio de ejecución (smartspot/).
DB_PATH: str = "parking.db"

# Nombres canónicos de las celdas usados como clave en la DB y en la UI.
NOMBRES_CELDAS: list[str] = ["Puesto A", "Puesto B", "Puesto C", "Puesto D"]
CELDA_A: str = NOMBRES_CELDAS[0]
CELDA_B: str = NOMBRES_CELDAS[1]
CELDA_C: str = NOMBRES_CELDAS[2]
CELDA_D: str = NOMBRES_CELDAS[3]

# Cantidad de lecturas a mostrar en la serie de tiempo.
HISTORICO_N: int = 100

# Intervalo de refresco del dashboard en segundos.
REFRESH_INTERVAL: float = 0.0

# ── Modo demo (sin hardware) ───────────────────────────────────────────────
# True  → datos simulados para capturas / presentaciones
# False → lee del puerto serie real (producción)
DEMO_MODE: bool = True

# ── Puerto serie del ESP32 ─────────────────────────────────────────────────
# Windows: "COM3", "COM4", etc.  Linux/Mac: "/dev/ttyUSB0", "/dev/ttyACM0"
# Si se deja vacío ("") source.py intentará auto-detectar el puerto.
SERIAL_PORT:    str   = "COM11"
SERIAL_BAUD:    int   = 115200
SERIAL_TIMEOUT: float = 1.0

# ── Sensor MQ7 — CO (Monóxido de Carbono) ─────────────────────────────────
# Umbrales sobre el valor ADC crudo que envía el ESP32.
# Ajustar según la calibración del sensor y las condiciones del ambiente.
CO_UMBRAL_NORMAL:   int = 400   # < 400  → 🟢 NORMAL
CO_UMBRAL_MODERADO: int = 700   # < 700  → 🟡 MODERADO   (≥ 700 → 🔴 ALERTA)
CO_MAX_RAW:         int = 1023  # Escala máxima para la barra de nivel (10-bit ADC)

# Paleta de colores usada en los estilos HTML/CSS y en Plotly.
# Centralizar aquí garantiza coherencia visual entre la tarjeta de celda
# y los gráficos analíticos sin duplicar valores hex en múltiples archivos.
COLORES: dict[str, str] = {
    "ocupado":    "#c0392b",
    "libre":      "#27ae60",
    "ocupado_bg": "rgba(192, 57, 43, 0.22)",
    "libre_bg":   "rgba(39, 174, 96, 0.13)",
}
