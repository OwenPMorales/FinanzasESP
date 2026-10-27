import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from api.v1.dependencies import get_human_user
from core.security import generate_device_key, hash_device_key
from db.database import get_session
from models.device_model import Device
from models.user_model import User
from schemas.device_schema import DeviceCreate, DeviceCreated, DeviceResponse

router = APIRouter()

MAX_DEVICES_PER_USER = 10


@router.post("/", response_model=DeviceCreated, status_code=status.HTTP_201_CREATED)
def create_device(
    body: DeviceCreate,
    user: User = Depends(get_human_user),
    session: Session = Depends(get_session),
) -> DeviceCreated:
    """
    Registra un ESP32 y genera su llave. La llave en claro solo aparece en esta
    respuesta; en la base de datos queda únicamente su SHA-256.
    """
    active = session.exec(
        select(Device).where(Device.user_id == user.id, Device.is_active)
    ).all()
    if len(active) >= MAX_DEVICES_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Máximo {MAX_DEVICES_PER_USER} dispositivos activos por usuario.",
        )

    device_key = generate_device_key()
    device = Device(
        user_id=user.id,
        name=body.name,
        key_prefix=device_key[:12],
        key_hash=hash_device_key(device_key),
    )
    session.add(device)
    session.commit()
    session.refresh(device)
    return DeviceCreated(**DeviceResponse.model_validate(device).model_dump(), device_key=device_key)


@router.get("/", response_model=list[DeviceResponse])
def list_devices(
    user: User = Depends(get_human_user),
    session: Session = Depends(get_session),
) -> list[Device]:
    return list(
        session.exec(
            select(Device).where(Device.user_id == user.id).order_by(Device.created_at)
        ).all()
    )


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_device(
    device_id: uuid.UUID,
    user: User = Depends(get_human_user),
    session: Session = Depends(get_session),
) -> None:
    """
    Revoca el dispositivo (no se borra para conservar el origen de sus tickets).
    Sus tokens vigentes dejan de funcionar de inmediato.
    """
    device = session.get(Device, device_id)
    if device is None or device.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo no encontrado.")
    device.is_active = False
    session.add(device)
    session.commit()
