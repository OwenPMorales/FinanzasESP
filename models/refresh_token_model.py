import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from models.user_model import utc_now

if TYPE_CHECKING:
    from models.user_model import User


class RefreshToken(SQLModel, table=True):
    """
    Registro de cada refresh token emitido (solo su jti, nunca el token).
    Permite cerrar sesión, rotar tokens y detectar reutilización de un token robado.
    """

    __tablename__ = "refresh_tokens"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    jti: str = Field(index=True, unique=True, max_length=64)
    expires_at: datetime
    revoked_at: datetime | None = None
    user_agent: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=utc_now)

    user: "User" = Relationship(back_populates="refresh_tokens")
