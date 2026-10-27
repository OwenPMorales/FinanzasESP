import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from models.enums import TicketSource, TicketStatus
from models.user_model import utc_now

if TYPE_CHECKING:
    from models.device_model import Device
    from models.ticket_item_model import TicketItem
    from models.user_model import User


class Ticket(SQLModel, table=True):
    """
    Ticket de compra. La imagen vive en MinIO; aquí solo su llave y metadatos.
    Los campos de compra (tienda, fecha, total) los llena el modelo de IA o el usuario.
    """

    __tablename__ = "tickets"
    # El mismo archivo no se puede subir dos veces por el mismo usuario.
    __table_args__ = (
        UniqueConstraint("user_id", "image_sha256", name="uq_ticket_user_image"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    device_id: uuid.UUID | None = Field(
        default=None, foreign_key="devices.id", index=True, ondelete="SET NULL"
    )
    source: TicketSource = Field(default=TicketSource.web)
    status: TicketStatus = Field(default=TicketStatus.pendiente, index=True)

    # --- Archivo en MinIO ---
    image_key: str = Field(max_length=255)
    image_content_type: str = Field(max_length=50)
    image_size: int
    image_sha256: str = Field(max_length=64)

    # --- Datos de la compra (los extrae la IA en la v02) ---
    store_name: str | None = Field(default=None, max_length=150)
    purchase_date: date | None = Field(default=None, index=True)
    total: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    currency: str = Field(default="MXN", max_length=3)
    notes: str | None = Field(default=None, max_length=500)

    # --- Trazabilidad de la IA ---
    ocr_raw_text: str | None = None
    ai_model: str | None = Field(default=None, max_length=80)
    ai_confidence: float | None = None

    created_at: datetime = Field(default_factory=utc_now, index=True)
    processed_at: datetime | None = None

    user: "User" = Relationship(back_populates="tickets")
    device: "Device" = Relationship(back_populates="tickets")
    items: list["TicketItem"] = Relationship(back_populates="ticket", cascade_delete=True)
