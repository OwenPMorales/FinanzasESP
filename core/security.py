import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import settings

TokenType = Literal["access", "refresh", "device"]

# ============================================================
# HASHEO DE CONTRASEÑAS (Argon2id)
# ============================================================

# Argon2id: ganador de la Password Hashing Competition y recomendado por OWASP.
# Es "memory-hard": cada intento cuesta RAM, lo que encarece ataques con GPU/ASIC.
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__type="ID",
    argon2__time_cost=settings.ARGON2_TIME_COST,
    argon2__memory_cost=settings.ARGON2_MEMORY_COST,
    argon2__parallelism=settings.ARGON2_PARALLELISM,
)

# Hash señuelo: se verifica cuando el usuario no existe para que el login
# tarde lo mismo y no revele qué usuarios están registrados (timing attack).
_DUMMY_HASH = pwd_context.hash("usuario-inexistente")


def get_password_hash(password: str) -> str:
    """Hashea la contraseña con Argon2id (incluye sal aleatoria en el hash)."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña coincide con el hash."""
    return pwd_context.verify(plain_password, hashed_password)


def verify_and_update_password(
    plain_password: str,
    hashed_password: str | None,
) -> tuple[bool, str | None]:
    """
    Verifica la contraseña y, si el hash usa parámetros viejos, devuelve uno nuevo.
    Así se pueden subir los costos de Argon2 sin obligar a nadie a cambiar su contraseña.
    """
    if hashed_password is None:
        pwd_context.verify(plain_password, _DUMMY_HASH)
        return False, None
    return pwd_context.verify_and_update(plain_password, hashed_password)


# ============================================================
# LLAVES DE DISPOSITIVO (ESP32)
# ============================================================

DEVICE_KEY_PREFIX = "fesp_"


def generate_device_key() -> str:
    """Genera una llave aleatoria de 256 bits para un dispositivo."""
    return DEVICE_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_device_key(device_key: str) -> str:
    """
    SHA-256 (no Argon2) porque la llave ya tiene 256 bits de entropía:
    no se puede adivinar por fuerza bruta y así se puede buscar por índice.
    """
    return hashlib.sha256(device_key.encode()).hexdigest()


# ============================================================
# TOKENS JWT
# ============================================================

def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + expires_delta
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iss": settings.JWT_ISSUER,
        "iat": now,
        "exp": expires_at,
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.TOKEN_ALGORITHM)
    return token, jti, expires_at


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    token, _, _ = _create_token(
        str(user_id),
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        {"role": role},
    )
    return token


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str, datetime]:
    """Devuelve (token, jti, expira). El jti se guarda en BD para poder revocarlo."""
    return _create_token(
        str(user_id),
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_device_token(user_id: uuid.UUID, device_id: uuid.UUID) -> str:
    token, _, _ = _create_token(
        str(user_id),
        "device",
        timedelta(minutes=settings.DEVICE_TOKEN_EXPIRE_MINUTES),
        {"dev": str(device_id)},
    )
    return token


def decode_token(token: str, expected_types: set[TokenType]) -> dict[str, Any]:
    """Valida firma, expiración, emisor y tipo. Lanza JWTError si algo falla."""
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.TOKEN_ALGORITHM],
        issuer=settings.JWT_ISSUER,
    )
    if payload.get("type") not in expected_types:
        raise JWTError("Tipo de token inválido.")
    if not isinstance(payload.get("sub"), str):
        raise JWTError("Token sin sujeto.")
    return payload
