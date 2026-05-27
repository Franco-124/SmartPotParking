"""
Módulo de autenticación — registro y verificación de usuarios.

Roles:
    admin : acceso completo al dashboard y analítica.
    user  : solo vista de ocupación y sensor CO.

Usa PBKDF2-HMAC-SHA256 con salt aleatorio de 32 bytes y 260 000 iteraciones
(recomendación OWASP 2023) sin dependencias externas: solo stdlib.
"""

import hashlib
import os
import sqlite3
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from settings import DB_PATH

ROLES = ("admin", "user")


def init_users_table() -> None:
    """Crea la tabla users si no existe. Idempotente."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL UNIQUE,
                email      TEXT    NOT NULL UNIQUE,
                pwd_hash   TEXT    NOT NULL,
                salt       TEXT    NOT NULL,
                role       TEXT    NOT NULL DEFAULT 'user',
                created_at TEXT    NOT NULL
            )
            """
        )
        # Migración no destructiva: agrega columna role si ya existe la tabla sin ella.
        try:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000).hex()


def register_user(
    username: str, email: str, password: str, role: str = "user"
) -> tuple[bool, str]:
    """
    Registra un nuevo usuario.
    Retorna (True, msg_ok) o (False, msg_error).
    """
    username = username.strip()
    email    = email.strip().lower()
    role     = role if role in ROLES else "user"

    if not username:
        return False, "El nombre de usuario no puede estar vacío."
    if len(username) < 3:
        return False, "El usuario debe tener al menos 3 caracteres."
    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "Correo electrónico inválido."
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."

    salt     = os.urandom(32)
    pwd_hash = _hash(password, salt)

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """INSERT INTO users (username, email, pwd_hash, salt, role, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username, email, pwd_hash, salt.hex(), role,
                 datetime.now().isoformat(timespec="seconds")),
            )
            conn.commit()
        return True, "¡Cuenta creada correctamente!"
    except sqlite3.IntegrityError as exc:
        detail = str(exc).lower()
        if "username" in detail:
            return False, "El nombre de usuario ya está en uso."
        if "email" in detail:
            return False, "El correo electrónico ya está registrado."
        return False, "No se pudo crear la cuenta. Intenta de nuevo."


def login_user(username: str, password: str) -> tuple[bool, str, str]:
    """
    Verifica credenciales.
    Retorna (True, msg_ok, role) o (False, msg_error, "").
    Tiempo constante para ambas ramas: evita timing attacks básicos.
    """
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT pwd_hash, salt, role FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()

    dummy_salt  = b"\x00" * 32
    stored_hash = row[0] if row else ""
    salt        = bytes.fromhex(row[1]) if row else dummy_salt
    computed    = _hash(password, salt)

    if row and computed == stored_hash:
        return True, "Inicio de sesión exitoso.", row[2]
    return False, "Usuario o contraseña incorrectos.", ""
