from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, or_, select

from api.v1.auth_api import revoke_all_refresh_tokens
from api.v1.dependencies import get_admin_user, get_current_user, get_human_user
from core.config import settings
from core.security import get_password_hash, verify_password
from db.database import get_session
from models.user_model import User
from schemas.user_schema import (
    AvatarResponse,
    PasswordChange,
    UserFilters,
    UserResponse,
    UserUpdate,
)
from services.storage_service import (
    IMAGE_TYPES,
    StorageService,
    avatar_key,
    get_storage,
    user_prefix,
    validate_file,
)

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def read_me(user: User = Depends(get_current_user)) -> User:
    """Perfil del usuario autenticado (también funciona con token de dispositivo)."""
    return user


@router.patch("/me", response_model=UserResponse)
def update_me(
    user_update: UserUpdate,
    user: User = Depends(get_human_user),
    session: Session = Depends(get_session),
) -> User:
    update_data = user_update.model_dump(exclude_unset=True)
    if "email" in update_data and update_data["email"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El correo no puede ser null.",
        )
    for field, value in update_data.items():
        setattr(user, field, value)
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese correo ya está registrado.",
        ) from None
    session.refresh(user)
    return user


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: PasswordChange,
    user: User = Depends(get_human_user),
    session: Session = Depends(get_session),
) -> None:
    """Cambia la contraseña y cierra todas las sesiones abiertas (revoca refresh tokens)."""
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta.",
        )
    user.hashed_password = get_password_hash(body.new_password)
    session.add(user)
    revoke_all_refresh_tokens(session, user.id)
    session.commit()


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    user: User = Depends(get_human_user),
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> None:
    """Elimina la cuenta, sus tickets, dispositivos y todos sus archivos en MinIO."""
    prefix = user_prefix(user.id)
    session.delete(user)
    session.commit()
    storage.delete_prefix(prefix)


# === Avatar (MinIO) ===

@router.put("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_human_user),
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> User:
    """Sube o reemplaza la foto de perfil (JPEG, PNG o WebP)."""
    data = await file.read(settings.max_upload_bytes + 1)
    content_type = validate_file(data, IMAGE_TYPES)

    new_key = avatar_key(user.id, content_type)
    storage.upload(new_key, data, content_type)
    old_key = user.avatar_key
    user.avatar_key = new_key
    session.add(user)
    session.commit()
    session.refresh(user)
    if old_key and old_key != new_key:
        storage.delete(old_key)
    return user


@router.get("/me/avatar", response_model=AvatarResponse)
def get_avatar(
    user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage),
) -> AvatarResponse:
    """Devuelve una URL prefirmada temporal para ver el avatar."""
    if not user.avatar_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sin foto de perfil.")
    return AvatarResponse(
        url=storage.presigned_url(user.avatar_key),
        expires_in=settings.PRESIGNED_URL_EXPIRE_MINUTES * 60,
    )


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
def delete_avatar(
    user: User = Depends(get_human_user),
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> None:
    if user.avatar_key:
        storage.delete(user.avatar_key)
        user.avatar_key = None
        session.add(user)
        session.commit()


# === Administración ===

@router.get("/", response_model=list[UserResponse])
def list_users(
    response: Response,
    filters: Annotated[UserFilters, Query()],
    session: Session = Depends(get_session),
    _admin: User = Depends(get_admin_user),
) -> list[User]:
    """Lista paginada de usuarios (solo administradores). Total en el header X-Total-Count."""
    statement = select(User)
    if filters.is_active is not None:
        statement = statement.where(User.is_active == filters.is_active)
    if filters.search:
        statement = statement.where(
            or_(
                col(User.username).icontains(filters.search, autoescape=True),
                col(User.email).icontains(filters.search, autoescape=True),
            )
        )
    total = session.exec(select(func.count()).select_from(statement.subquery())).one()
    response.headers["X-Total-Count"] = str(total)
    statement = statement.order_by(User.created_at).offset(filters.skip).limit(filters.limit)
    return list(session.exec(statement).all())
