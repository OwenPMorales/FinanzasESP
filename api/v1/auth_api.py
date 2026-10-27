import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from core.config import settings
from core.security import (
    create_access_token,
    create_device_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_device_key,
    verify_and_update_password,
)
from db.database import get_session
from models.device_model import Device
from models.refresh_token_model import RefreshToken
from models.user_model import User
from schemas.token_schema import DeviceToken, DeviceTokenRequest, RefreshRequest, TokenPair
from schemas.user_schema import UserCreate, UserResponse

router = APIRouter()

invalid_refresh = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Refresh token inválido o expirado.",
    headers={"WWW-Authenticate": "Bearer"},
)


def _as_utc(value: datetime) -> datetime:
    # SQLite devuelve datetimes sin zona; PostgreSQL con zona. Se normalizan a UTC.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def issue_token_pair(session: Session, user: User, user_agent: str | None) -> TokenPair:
    """Crea access + refresh y registra el jti del refresh en la base de datos."""
    refresh_token, jti, expires_at = create_refresh_token(user.id)
    session.add(
        RefreshToken(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    session.commit()
    return TokenPair(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def revoke_all_refresh_tokens(session: Session, user_id: uuid.UUID) -> None:
    now = datetime.now(timezone.utc)
    active = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ).all()
    for token in active:
        token.revoked_at = now
        session.add(token)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, session: Session = Depends(get_session)) -> User:
    """Registra un usuario nuevo. La contraseña se guarda hasheada con Argon2id."""
    existing = session.exec(
        select(User).where(
            (User.username == user_data.username) | (User.email == user_data.email)
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario o correo ya está registrado.",
        )

    user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        currency=user_data.currency,
        hashed_password=get_password_hash(user_data.password),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        # Dos registros simultáneos con el mismo dato: lo frena el UNIQUE de la BD.
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario o correo ya está registrado.",
        ) from None
    session.refresh(user)
    return user


@router.post("/token", response_model=TokenPair)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session),
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenPair:
    """
    Login OAuth2 (form-urlencoded). El campo `username` acepta usuario o correo.
    Devuelve un access token (30 min) y un refresh token (7 días).
    """
    identifier = form_data.username.strip().lower()
    user = session.exec(
        select(User).where((User.username == identifier) | (User.email == identifier))
    ).first()

    valid, new_hash = verify_and_update_password(
        form_data.password, user.hashed_password if user else None
    )
    if user is None or not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo.")

    if new_hash:
        user.hashed_password = new_hash  # rehash transparente con parámetros nuevos
    user.last_login_at = datetime.now(timezone.utc)
    session.add(user)
    return issue_token_pair(session, user, user_agent)


@router.post("/refresh", response_model=TokenPair)
def refresh(
    body: RefreshRequest,
    session: Session = Depends(get_session),
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenPair:
    """
    Cambia un refresh token por un par nuevo (rotación). El refresh usado queda revocado;
    si alguien vuelve a presentarlo, se asume robo y se cierran todas las sesiones.
    """
    try:
        payload = decode_token(body.refresh_token, {"refresh"})
    except JWTError:
        raise invalid_refresh from None

    stored = session.exec(
        select(RefreshToken).where(RefreshToken.jti == payload.get("jti"))
    ).first()
    if stored is None:
        raise invalid_refresh

    if stored.revoked_at is not None:
        revoke_all_refresh_tokens(session, stored.user_id)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reutilizado: se cerraron todas las sesiones por seguridad.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if _as_utc(stored.expires_at) <= datetime.now(timezone.utc):
        raise invalid_refresh

    user = session.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise invalid_refresh

    stored.revoked_at = datetime.now(timezone.utc)
    session.add(stored)
    return issue_token_pair(session, user, user_agent)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, session: Session = Depends(get_session)) -> None:
    """Revoca el refresh token (cierra la sesión). Es idempotente."""
    try:
        payload = decode_token(body.refresh_token, {"refresh"})
    except JWTError:
        return
    stored = session.exec(
        select(RefreshToken).where(RefreshToken.jti == payload.get("jti"))
    ).first()
    if stored and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
        session.add(stored)
        session.commit()


@router.post("/device-token", response_model=DeviceToken)
def device_token(body: DeviceTokenRequest, session: Session = Depends(get_session)) -> DeviceToken:
    """
    El ESP32 cambia su llave de dispositivo por un JWT de corta duración.
    El JWT de dispositivo solo sirve para subir y consultar tickets.
    """
    device = session.exec(
        select(Device).where(Device.key_hash == hash_device_key(body.device_key))
    ).first()
    if device is None or not device.is_active or not device.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Llave de dispositivo inválida o revocada.",
        )
    device.last_seen_at = datetime.now(timezone.utc)
    session.add(device)
    session.commit()
    return DeviceToken(
        access_token=create_device_token(device.user_id, device.id),
        expires_in=settings.DEVICE_TOKEN_EXPIRE_MINUTES * 60,
    )
