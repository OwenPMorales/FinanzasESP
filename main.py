import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlmodel import Session, SQLModel

import models  # noqa: F401 - registra todas las tablas en SQLModel.metadata
from api.v1.auth_api import router as auth_router
from api.v1.device_api import router as device_router
from api.v1.ticket_api import router as ticket_router
from api.v1.user_api import router as user_router
from core.config import settings
from db.database import engine, get_session
from services.storage_service import StorageService, get_storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finanzas_esp")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.USE_ALEMBIC:
        SQLModel.metadata.create_all(engine)
    # Si MinIO aún no arranca, la API inicia igual y los endpoints de archivos responden 503.
    try:
        get_storage().ensure_bucket()
    except Exception as exc:  # noqa: BLE001
        logger.warning("MinIO no disponible al iniciar: %s", exc)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Plataforma de finanzas personales con ESP32: sube tickets de compra "
        "(web o dispositivo), guárdalos en MinIO y lleva el control de precios, "
        "productos y fechas.\n\n**Entregable v01:** modelo User, hasheo Argon2id, "
        "tokens JWT (access/refresh/dispositivo) y almacenamiento MinIO."
    ),
    version="0.1.0",
    lifespan=lifespan,
)
# Con allow_credentials=True los orígenes deben ser explícitos, nunca "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["X-Total-Count"],
    max_age=3600,
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(user_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(device_router, prefix="/api/v1/devices", tags=["Devices (ESP32)"])
app.include_router(ticket_router, prefix="/api/v1/tickets", tags=["Tickets"])


@app.get("/", include_in_schema=False)
def web_app() -> FileResponse:
    """Panel web mínimo para probar la plataforma desde el navegador."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["Health"])
def health_check(
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> dict[str, str]:
    try:
        session.exec(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001
        database = "error"
    storage_status = "ok" if storage.is_available() else "error"
    return {
        "status": "healthy" if database == storage_status == "ok" else "degraded",
        "database": database,
        "storage": storage_status,
    }
