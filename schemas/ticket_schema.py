import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from models.enums import TicketSource, TicketStatus


class TicketBase64Upload(BaseModel):
    """
    Subida en JSON para clientes IoT (ESP32 / ESP-Claw), que arman el cuerpo
    como texto y no pueden construir un multipart/form-data con bytes binarios.
    """

    image_base64: str = Field(min_length=8)
    content_type: str = Field(default="image/jpeg", examples=["image/jpeg"])
    notes: str | None = Field(default=None, max_length=500)


class TicketItemResponse(BaseModel):
    id: uuid.UUID
    description: str
    quantity: Decimal
    unit_price: Decimal | None
    total_price: Decimal
    category_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class TicketResponse(BaseModel):
    id: uuid.UUID
    status: TicketStatus
    source: TicketSource
    device_id: uuid.UUID | None
    image_content_type: str
    image_size: int
    store_name: str | None
    purchase_date: date | None
    total: Decimal | None
    currency: str
    notes: str | None
    created_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class TicketDetail(TicketResponse):
    image_url: str | None = Field(
        default=None, description="URL prefirmada de MinIO (caduca)"
    )
    ai_model: str | None
    ai_confidence: float | None
    items: list[TicketItemResponse] = []


class TicketFilters(BaseModel):
    model_config = {"extra": "forbid"}

    status: TicketStatus | None = None
    created_from: date | None = None
    created_to: date | None = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
