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
NOMBRES_CELDAS: list[str] = ["Puesto A", "Puesto B"]
CELDA_A: str = NOMBRES_CELDAS[0]
CELDA_B: str = NOMBRES_CELDAS[1]

# Cantidad de lecturas a mostrar en la serie de tiempo.
HISTORICO_N: int = 100

# Intervalo de refresco del dashboard en segundos.
REFRESH_INTERVAL: float = 1.0

# Paleta de colores usada en los estilos HTML/CSS y en Plotly.
# Centralizar aquí garantiza coherencia visual entre la tarjeta de celda
# y los gráficos analíticos sin duplicar valores hex en múltiples archivos.
COLORES: dict[str, str] = {
    "ocupado":    "#c0392b",
    "libre":      "#27ae60",
    "ocupado_bg": "rgba(192, 57, 43, 0.22)",
    "libre_bg":   "rgba(39, 174, 96, 0.13)",
}
