import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator

from models.enums import UserRole

USERNAME_PATTERN = r"^[a-zA-Z0-9_.-]+$"


def validate_password_strength(password: str) -> str:
    """Política mínima: 8+ caracteres, al menos una letra y un número."""
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("La contraseña debe tener al menos una letra y un número.")
    return password


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    email: EmailStr
    # Argon2 no trunca a 72 bytes como bcrypt, así que se permiten frases largas.
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)
    currency: str = Field(default="MXN", min_length=3, max_length=3)

    _check_password = field_validator("password")(validate_password_strength)

    @field_validator("username", "email")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, value: str) -> str:
        return value.upper()


class UserUpdate(BaseModel):
    """Campos que el propio usuario puede cambiar en PATCH /users/me."""

    full_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    monthly_budget: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    _check_password = field_validator("new_password")(validate_password_strength)


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    currency: str
    monthly_budget: Decimal | None
    avatar_key: str | None = Field(default=None, exclude=True)
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def has_avatar(self) -> bool:
        return self.avatar_key is not None


class UserFilters(BaseModel):
    """Query params para GET /api/v1/users/ (solo administradores)."""

    model_config = {"extra": "forbid"}

    is_active: bool | None = None
    search: str | None = Field(
        default=None, min_length=1, max_length=50,
        description="Coincidencia parcial en username o email",
    )
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


class AvatarResponse(BaseModel):
    url: str
    expires_in: int
