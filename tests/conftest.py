import os
import sys
from pathlib import Path

# Variables de entorno de prueba ANTES de importar la app (Settings las lee al importar).
os.environ["SECRET_KEY"] = "clave-de-pruebas-no-usar-en-produccion-0123456789"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["USE_ALEMBIC"] = "true"
os.environ["MAX_UPLOAD_MB"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from db.database import get_session  # noqa: E402
from main import app  # noqa: E402
from services.storage_service import get_storage  # noqa: E402

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x01" * 64
PDF_BYTES = b"%PDF-1.7\n" + b"\x02" * 64


class FakeStorage:
    """MinIO en memoria: permite probar la API sin contenedores."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def ensure_bucket(self) -> None: ...

    def is_available(self) -> bool:
        return True

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def presigned_url(self, key: str) -> str:
        return f"http://minio.test/finanzas-esp/{key}?X-Amz-Signature=fake"

    def stream(self, key: str):
        yield self.objects[key][0]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self.objects if k.startswith(prefix)]:
            del self.objects[key]


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def client(storage: FakeStorage):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_storage] = lambda: storage
    # Sin "with": no corre el lifespan, así no se toca el MinIO real.
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(client: TestClient, username="ana", password="Secreta123", **extra):
    body = {"username": username, "email": f"{username}@correo.com", "password": password, **extra}
    return client.post("/api/v1/auth/register", json=body)


def login(client: TestClient, username="ana", password="Secreta123"):
    return client.post(
        "/api/v1/auth/token", data={"username": username, "password": password}
    )


@pytest.fixture
def tokens(client: TestClient) -> dict:
    assert register(client).status_code == 201
    response = login(client)
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}
