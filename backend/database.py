import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = Path(__file__).resolve().parent / "control_vestimenta.db"
COOLDOWN_SECONDS = 30


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS infracciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_alumno TEXT NOT NULL,
                estado_detectado TEXT NOT NULL,
                confianza REAL NOT NULL,
                fecha_hora TEXT NOT NULL,
                created_at_epoch REAL NOT NULL
            )
            """
        )
        conn.commit()


def parse_iso_to_epoch(fecha_hora: Optional[str]) -> float:
    if not fecha_hora:
        return datetime.now(timezone.utc).timestamp()
    try:
        normalizada = fecha_hora.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalizada)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return datetime.now(timezone.utc).timestamp()


def registrar_infraccion_con_cooldown(
    nombre_alumno: str,
    estado_detectado: str,
    confianza: float,
    fecha_hora: str,
    cooldown_seconds: int = COOLDOWN_SECONDS,
) -> Tuple[bool, int, Dict[str, Any]]:
    """
    Retorna (registrada, segundos_restantes, registro_o_ultimo).
    Si el mismo alumno ya tiene una infracción dentro de cooldown_seconds, no duplica.
    """
    ahora_epoch = parse_iso_to_epoch(fecha_hora)

    with get_connection() as conn:
        fila_previa = conn.execute(
            """
            SELECT *
            FROM infracciones
            WHERE LOWER(TRIM(nombre_alumno)) = LOWER(TRIM(?))
            ORDER BY created_at_epoch DESC, id DESC
            LIMIT 1
            """,
            (nombre_alumno,),
        ).fetchone()

        if fila_previa is not None:
            transcurridos = ahora_epoch - float(fila_previa["created_at_epoch"])
            if 0 <= transcurridos < cooldown_seconds:
                restantes = max(1, int(round(cooldown_seconds - transcurridos)))
                return False, restantes, dict(fila_previa)

        cursor = conn.execute(
            """
            INSERT INTO infracciones (
                nombre_alumno,
                estado_detectado,
                confianza,
                fecha_hora,
                created_at_epoch
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                nombre_alumno.strip(),
                estado_detectado.strip(),
                float(confianza),
                fecha_hora,
                ahora_epoch,
            ),
        )
        conn.commit()
        nuevo_id = cursor.lastrowid

        nueva_fila = conn.execute(
            "SELECT * FROM infracciones WHERE id = ?",
            (nuevo_id,),
        ).fetchone()

        return True, 0, dict(nueva_fila)


def listar_infracciones(limit: int = 200) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        filas = conn.execute(
            """
            SELECT
                id,
                nombre_alumno,
                estado_detectado,
                confianza,
                fecha_hora
            FROM infracciones
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(fila) for fila in filas]