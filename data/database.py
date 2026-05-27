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
    """Crea las tablas si no existen. Idempotente."""
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
        # Tabla separada para CO: es una lectura ambiental global,
        # no pertenece a ningún puesto específico.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS co_lecturas (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                co_raw    INTEGER NOT NULL,
                timestamp TEXT    NOT NULL
            )
            """
        )
        conn.commit()


def insert_reading(puesto: str, distancia: float, timestamp: str) -> None:
    """Inserta una lectura de distancia. puesto debe coincidir con NOMBRES_CELDAS."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO lecturas (puesto, distancia, timestamp) VALUES (?, ?, ?)",
            (puesto, distancia, timestamp),
        )
        conn.commit()


def insert_co_reading(co_raw: int, timestamp: str) -> None:
    """Inserta una lectura del sensor MQ7."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO co_lecturas (co_raw, timestamp) VALUES (?, ?)",
            (co_raw, timestamp),
        )
        conn.commit()


def get_last_n_readings(n: int = 100) -> List[Tuple[str, float, str]]:
    """
    Últimas n lecturas de distancia en orden cronológico (más antiguo primero).
    Subconsulta: toma los n más recientes por id DESC y reordena ASC para
    que el eje X del gráfico vaya de izquierda (pasado) a derecha (presente).
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


def get_last_co_readings(n: int = 100) -> List[Tuple[int, str]]:
    """Últimas n lecturas de CO en orden cronológico (más antiguo primero)."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT co_raw, timestamp
            FROM (
                SELECT co_raw, timestamp, id
                FROM co_lecturas
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
    Cuenta lecturas OCUPADO / LIBRE por celda (1 lectura ≈ 1 segundo).
    since: timestamp ISO-8601 para limitar al período de la sesión actual.
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

    result: dict = {}
    for puesto, ocupado, libre in rows:
        result[puesto] = {"ocupado": ocupado or 0, "libre": libre or 0}
    return result
