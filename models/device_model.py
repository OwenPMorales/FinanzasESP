import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from models.user_model import utc_now

if TYPE_CHECKING:
    from models.ticket_model import Ticket
    from models.user_model import User


class Device(SQLModel, table=True):
    """ESP32 (u otro cliente IoT) vinculado a un usuario mediante una llave propia."""

    __tablename__ = "devices"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    name: str = Field(max_length=80)
    # Primeros caracteres de la llave, para que el usuario la reconozca en la lista.
    key_prefix: str = Field(max_length=16)
    # SHA-256 de la llave completa; la llave en claro solo se muestra al crearla.
    key_hash: str = Field(index=True, unique=True, max_length=64)
    is_active: bool = Field(default=True)
    last_seen_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)

    user: "User" = Relationship(back_populates="devices")
    tickets: list["Ticket"] = Relationship(back_populates="device")
