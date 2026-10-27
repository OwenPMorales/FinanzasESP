from collections.abc import Generator

from sqlmodel import Session, create_engine

from core.config import settings

connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # descarta conexiones muertas (ej. si se reinicia el contenedor)
)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
