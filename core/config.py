from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "FinanzasESP"
    # SQLite solo como respaldo local; el .env apunta a PostgreSQL.
    DATABASE_URL: str = "sqlite:///./finanzas.db"
    USE_ALEMBIC: bool = True

    # === Tokens (JWT) ===
    SECRET_KEY: str
    TOKEN_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "finanzas-esp"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEVICE_TOKEN_EXPIRE_MINUTES: int = 60

    # === Hasheo (Argon2id) ===
    ARGON2_TIME_COST: int = 2
    ARGON2_MEMORY_COST: int = 19456  # KiB (19 MiB)
    ARGON2_PARALLELISM: int = 1

    # === CORS ===
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ]

    # === MinIO ===
    MINIO_ENDPOINT: str = "localhost:9030"
    MINIO_PUBLIC_ENDPOINT: str | None = None
    MINIO_ACCESS_KEY: str = "finanzas_admin"
    MINIO_SECRET_KEY: str = "finanzas_minio_2026"
    MINIO_BUCKET: str = "finanzas-esp"
    MINIO_SECURE: bool = False
    MINIO_REGION: str = "us-east-1"
    PRESIGNED_URL_EXPIRE_MINUTES: int = 15
    MAX_UPLOAD_MB: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


settings = Settings()
