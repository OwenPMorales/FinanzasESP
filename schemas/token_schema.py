from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Segundos de vida del access token")


class DeviceToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class DeviceTokenRequest(BaseModel):
    device_key: str = Field(min_length=10, max_length=100)
