import base64
import binascii
import hashlib
import uuid
from datetime import datetime, time, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from api.v1.dependencies import Principal, get_principal
from core.config import settings
from db.database import get_session
from models.enums import TicketSource
from models.ticket_model import Ticket
from schemas.ticket_schema import (
    TicketBase64Upload,
    TicketDetail,
    TicketFilters,
    TicketResponse,
)
from services.storage_service import (
    TICKET_TYPES,
    StorageService,
    get_storage,
    ticket_key,
    validate_file,
)

router = APIRouter()


def _get_own_ticket(session: Session, ticket_id: uuid.UUID, principal: Principal) -> Ticket:
    ticket = session.get(Ticket, ticket_id)
    # 404 también si es de otro usuario: no se revela que el ticket existe.
    if ticket is None or ticket.user_id != principal.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado.")
    return ticket


def _store_ticket(
    data: bytes,
    notes: str | None,
    principal: Principal,
    session: Session,
    storage: StorageService,
) -> Ticket:
    """Valida el archivo, lo sube a MinIO y crea el registro. Común a ambas formas de subida."""
    content_type = validate_file(data, TICKET_TYPES)
    digest = hashlib.sha256(data).hexdigest()

    duplicate = session.exec(
        select(Ticket).where(Ticket.user_id == principal.user.id, Ticket.image_sha256 == digest)
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Este ticket ya fue subido (id {duplicate.id}).",
        )

    ticket_id = uuid.uuid4()
    created_at = datetime.now(timezone.utc)
    key = ticket_key(principal.user.id, ticket_id, created_at, content_type)

    ticket = Ticket(
        id=ticket_id,
        user_id=principal.user.id,
        device_id=principal.device.id if principal.device else None,
        source=TicketSource.esp32 if principal.is_device else TicketSource.web,
        image_key=key,
        image_content_type=content_type,
        image_size=len(data),
        image_sha256=digest,
        currency=principal.user.currency,
        notes=notes,
        created_at=created_at,
    )

    # Primero MinIO y luego la BD; si la BD falla se borra el objeto (compensación)
    # para no dejar archivos huérfanos.
    storage.upload(key, data, content_type)
    session.add(ticket)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        storage.delete(key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Este ticket ya fue subido."
        ) from None
    except Exception:
        session.rollback()
        storage.delete(key)
        raise
    session.refresh(ticket)
    return ticket


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def upload_ticket(
    file: UploadFile = File(..., description="Foto (JPEG/PNG/WebP) o PDF del ticket"),
    notes: Annotated[str | None, Form(max_length=500)] = None,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> Ticket:
    """Sube un ticket de compra (multipart/form-data). Queda en estado `pendiente`."""
    data = await file.read(settings.max_upload_bytes + 1)
    return _store_ticket(data, notes, principal, session, storage)


@router.post("/base64", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def upload_ticket_base64(
    payload: TicketBase64Upload,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> Ticket:
    """Igual que `POST /tickets/`, pero con la imagen en base64 dentro de JSON (ESP32)."""
    encoded = payload.image_base64
    if encoded.startswith("data:"):  # acepta también "data:image/jpeg;base64,...."
        encoded = encoded.split(",", 1)[-1]
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="image_base64 no es un base64 válido."
        ) from None
    return _store_ticket(data, payload.notes, principal, session, storage)


@router.get("/", response_model=list[TicketResponse])
def list_tickets(
    response: Response,
    filters: Annotated[TicketFilters, Query()],
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[Ticket]:
    """Tickets del usuario, del más reciente al más antiguo. Total en X-Total-Count."""
    statement = select(Ticket).where(Ticket.user_id == principal.user.id)
    if filters.status:
        statement = statement.where(Ticket.status == filters.status)
    if filters.created_from:
        statement = statement.where(
            Ticket.created_at >= datetime.combine(filters.created_from, time.min, timezone.utc)
        )
    if filters.created_to:
        statement = statement.where(
            Ticket.created_at <= datetime.combine(filters.created_to, time.max, timezone.utc)
        )
    total = session.exec(select(func.count()).select_from(statement.subquery())).one()
    response.headers["X-Total-Count"] = str(total)
    statement = statement.order_by(Ticket.created_at.desc()).offset(filters.skip).limit(filters.limit)
    return list(session.exec(statement).all())


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(
    ticket_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> TicketDetail:
    """Detalle del ticket con sus productos y una URL prefirmada de la imagen."""
    ticket = _get_own_ticket(session, ticket_id, principal)
    detail = TicketDetail.model_validate(ticket)
    detail.image_url = storage.presigned_url(ticket.image_key)
    return detail


@router.get("/{ticket_id}/image")
def download_ticket_image(
    ticket_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> StreamingResponse:
    """Descarga la imagen a través de la API (útil cuando el cliente no alcanza a MinIO)."""
    ticket = _get_own_ticket(session, ticket_id, principal)
    return StreamingResponse(storage.stream(ticket.image_key), media_type=ticket.image_content_type)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> None:
    """Elimina el ticket, sus productos y la imagen en MinIO (solo el usuario, no el ESP32)."""
    if principal.is_device:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un dispositivo no puede borrar tickets.",
        )
    ticket = _get_own_ticket(session, ticket_id, principal)
    key = ticket.image_key
    session.delete(ticket)
    session.commit()
    storage.delete(key)
