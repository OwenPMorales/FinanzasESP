import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80, examples=["ESP32-S3 cocina"])


class DeviceResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeviceCreated(DeviceResponse):
    device_key: str = Field(
        description="Llave del dispositivo. Se muestra UNA sola vez: cópiala al ESP32."
    )
