import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from models.enums import UserRole

if TYPE_CHECKING:
    from models.device_model import Device
    from models.refresh_token_model import RefreshToken
    from models.ticket_model import Ticket


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    """Usuario de la plataforma: dueño de sus tickets, dispositivos y presupuesto."""

    __tablename__ = "users"

    # UUID en vez de entero: no se pueden enumerar usuarios adivinando /users/1, /users/2...
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=3, max_length=50)
    email: str = Field(index=True, unique=True, max_length=320)
    full_name: str | None = Field(default=None, max_length=120)
    # Solo se guarda el hash Argon2id (incluye algoritmo, parámetros y sal).
    hashed_password: str = Field(max_length=255)
    role: UserRole = Field(default=UserRole.user)
    is_active: bool = Field(default=True)

    # Preferencias financieras
    currency: str = Field(default="MXN", min_length=3, max_length=3)
    monthly_budget: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)

    # Llave del objeto en MinIO (no la URL: las URLs prefirmadas caducan)
    avatar_key: str | None = Field(default=None, max_length=255)

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column_kwargs={"onupdate": utc_now},
    )
    last_login_at: datetime | None = None

    refresh_tokens: list["RefreshToken"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    devices: list["Device"] = Relationship(back_populates="user", cascade_delete=True)
    tickets: list["Ticket"] = Relationship(back_populates="user", cascade_delete=True)
