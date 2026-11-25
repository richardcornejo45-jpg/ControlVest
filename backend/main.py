import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from database import (
    COOLDOWN_SECONDS,
    init_db,
    listar_infracciones,
    registrar_infraccion_con_cooldown,
)

app = FastAPI(
    title="ControlVest API",
    description="Backend local para registro y consulta de infracciones de código de vestimenta",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InfraccionCreate(BaseModel):
    nombre_alumno: str = Field(..., min_length=1, max_length=120)
    estado_detectado: str = Field(default="Incumplimiento_Vestimenta", min_length=1, max_length=80)
    confianza: float = Field(..., ge=0.0, le=100.0)
    fecha_hora: Optional[str] = None


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/")
def healthcheck() -> dict:
    return {"status": "ok", "servicio": "ControlVest Backend", "cooldown_segundos": COOLDOWN_SECONDS}


@app.post("/api/infracciones", status_code=201)
def crear_infraccion(payload: InfraccionCreate) -> dict:
    fecha_iso = payload.fecha_hora or datetime.now(timezone.utc).astimezone().isoformat()

    # Normaliza confianza si llega como 0.91 en vez de 91.0
    confianza_pct = round(payload.confianza * 100, 2) if 0 < payload.confianza <= 1 else round(payload.confianza, 2)

    registrada, segundos_restantes, registro = registrar_infraccion_con_cooldown(
        nombre_alumno=payload.nombre_alumno,
        estado_detectado=payload.estado_detectado,
        confianza=confianza_pct,
        fecha_hora=fecha_iso,
        cooldown_seconds=COOLDOWN_SECONDS,
    )

    if not registrada:
        return {
            "registrada": False,
            "motivo": f"Cooldown activo para {payload.nombre_alumno}. Espera {segundos_restantes}s para evitar duplicados.",
            "segundos_restantes": segundos_restantes,
            "data": registro,
        }

    return {
        "registrada": True,
        "motivo": "Infracción registrada correctamente en SQLite.",
        "segundos_restantes": 0,
        "data": registro,
    }


@app.get("/api/infracciones")
def obtener_infracciones(limit: int = Query(default=200, ge=1, le=1000)) -> dict:
    registros = listar_infracciones(limit=limit)
    return {
        "total": len(registros),
        "infracciones": registros,
    }


@app.get("/api/infracciones/csv")
def exportar_infracciones_csv() -> StreamingResponse:
    registros = listar_infracciones(limit=5000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "nombre_alumno", "estado_detectado", "confianza", "fecha_hora"])

    for r in registros:
        writer.writerow([
            r.get("id"),
            r.get("nombre_alumno"),
            r.get("estado_detectado"),
            r.get("confianza"),
            r.get("fecha_hora"),
        ])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=infracciones_controlvest.csv"},
    )