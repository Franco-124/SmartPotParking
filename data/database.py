"""
Capa de acceso a datos SQLite — funciones puras sin estado compartido.
Cada función abre y cierra su propia conexión: seguro en un proceso Streamlit
de hilo único donde no existe riesgo de condición de carrera.
"""

import sqlite3
from typing import List, Tuple

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from settings import DB_PATH, UMBRAL_OCUPACION


def init_db() -> None:
    """Crea la tabla lecturas si no existe. Idempotente: seguro llamarlo al inicio."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lecturas (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                puesto    TEXT    NOT NULL,
                distancia REAL    NOT NULL,
                timestamp TEXT    NOT NULL
            )
            """
        )
        conn.commit()


def insert_reading(puesto: str, distancia: float, timestamp: str) -> None:
    """Inserta una lectura de sensor. puesto debe coincidir con NOMBRES_CELDAS."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO lecturas (puesto, distancia, timestamp) VALUES (?, ?, ?)",
            (puesto, distancia, timestamp),
        )
        conn.commit()


def get_last_n_readings(n: int = 100) -> List[Tuple[str, float, str]]:
    """
    Últimas n lecturas en orden cronológico (más antiguo primero).
    La subconsulta toma los n más recientes por id DESC y luego los reordena
    ASC para que el eje X del gráfico vaya de izquierda (pasado) a derecha (presente).
    """
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT puesto, distancia, timestamp
            FROM (
                SELECT puesto, distancia, timestamp, id
                FROM lecturas
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (n,),
        ).fetchall()
    return rows


def get_occupation_stats(since: str | None = None) -> dict:
    """
    Cuenta lecturas OCUPADO / LIBRE por celda (1 lectura ≈ 1 segundo de observación).

    since: timestamp ISO-8601 para limitar el análisis a la sesión actual.
           Si es None, acumula todo el historial de la DB.

    Retorna dict con clave = nombre de puesto:
        {"Puesto A": {"ocupado": int, "libre": int}, "Puesto B": {...}}
    Las celdas sin datos retornan {"ocupado": 0, "libre": 0}.
    """
    where = "WHERE timestamp >= :since" if since else ""
    params: dict = {"umbral": UMBRAL_OCUPACION}
    if since:
        params["since"] = since

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            f"""
            SELECT puesto,
                   SUM(CASE WHEN distancia <= :umbral THEN 1 ELSE 0 END) AS ocupado,
                   SUM(CASE WHEN distancia >  :umbral THEN 1 ELSE 0 END) AS libre
            FROM lecturas
            {where}
            GROUP BY puesto
            """,
            params,
        ).fetchall()

    # Retornar siempre la estructura completa aunque la DB esté vacía o no tenga
    # aún lecturas de alguna celda (evita KeyError en app.py al inicio de sesión).
    result: dict = {}
    for puesto, ocupado, libre in rows:
        result[puesto] = {"ocupado": ocupado or 0, "libre": libre or 0}
    return result
