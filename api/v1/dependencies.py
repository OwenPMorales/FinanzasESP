import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlmodel import Session

from core.security import decode_token
from db.database import get_session
from models.device_model import Device
from models.enums import UserRole
from models.user_model import User

# ⚠️ tokenUrl debe coincidir con la ruta completa del endpoint de login (lo usa Swagger).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No se pudieron validar las credenciales.",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass
class Principal:
    """Quién hace la petición: un usuario directamente o un ESP32 en su nombre."""

    user: User
    device: Device | None = None

    @property
    def is_device(self) -> bool:
        return self.device is not None


def get_principal(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> Principal:
    """Valida el JWT (de usuario o de dispositivo) y carga a su dueño."""
    try:
        payload = decode_token(token, {"access", "device"})
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, ValueError):
        raise credentials_exception from None

    user = session.get(User, user_id)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo.")

    device = None
    if payload["type"] == "device":
        try:
            device = session.get(Device, uuid.UUID(payload.get("dev", "")))
        except ValueError:
            raise credentials_exception from None
        # Si el usuario revoca el dispositivo, sus tokens dejan de servir al instante.
        if device is None or device.user_id != user.id or not device.is_active:
            raise credentials_exception
        device.last_seen_at = datetime.now(timezone.utc)
        session.add(device)
        session.commit()
    return Principal(user=user, device=device)


def get_current_user(principal: Principal = Depends(get_principal)) -> User:
    """Usuario dueño de la petición (aceptando tokens de usuario y de dispositivo)."""
    return principal.user


def get_human_user(principal: Principal = Depends(get_principal)) -> User:
    """
    Solo tokens de usuario. Un ESP32 no puede cambiar contraseñas, borrar la
    cuenta ni crear otros dispositivos aunque su token sea válido.
    """
    if principal.is_device:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta operación no está permitida con un token de dispositivo.",
        )
    return principal.user


def get_admin_user(user: User = Depends(get_human_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador.",
        )
    return user
