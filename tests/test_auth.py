from jose import jwt
from sqlmodel import Session, select

from core.config import settings
from core.security import get_password_hash, verify_and_update_password, verify_password
from tests.conftest import login, register


# === Hasheo ===

def test_hash_argon2id_con_sal_aleatoria():
    h1 = get_password_hash("Secreta123")
    h2 = get_password_hash("Secreta123")
    assert h1.startswith("$argon2id$")
    assert h1 != h2  # sal distinta en cada hash
    assert verify_password("Secreta123", h1)
    assert not verify_password("otra-clave1", h1)


def test_rehash_cuando_cambian_parametros():
    from passlib.context import CryptContext

    viejo = CryptContext(schemes=["argon2"], argon2__time_cost=1, argon2__memory_cost=8192)
    valid, new_hash = verify_and_update_password("Secreta123", viejo.hash("Secreta123"))
    assert valid and new_hash and new_hash.startswith("$argon2id$")


def test_registro_no_expone_hash(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert "hashed_password" not in body and "password" not in body
    assert body["username"] == "ana" and body["role"] == "user"


def test_registro_duplicado_y_politica_password(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409
    assert register(client, username="beto", password="solo-letras").status_code == 422
    assert register(client, username="x").status_code == 422


# === Tokens ===

def test_login_con_usuario_o_correo(client):
    register(client)
    assert login(client, "ana").status_code == 200
    assert login(client, "ANA@correo.com").status_code == 200
    assert login(client, "ana", "Incorrecta1").status_code == 401
    assert login(client, "nadie", "Secreta123").status_code == 401


def test_claims_del_access_token(tokens):
    payload = jwt.decode(
        tokens["access_token"], settings.SECRET_KEY,
        algorithms=[settings.TOKEN_ALGORITHM], issuer=settings.JWT_ISSUER,
    )
    assert payload["type"] == "access" and payload["role"] == "user"
    assert {"sub", "jti", "iat", "exp"} <= payload.keys()
    assert tokens["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_ruta_protegida_requiere_token(client, auth):
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get("/api/v1/users/me", headers={"Authorization": "Bearer basura"}).status_code == 401
    assert client.get("/api/v1/users/me", headers=auth).json()["username"] == "ana"


def test_refresh_no_sirve_como_access(client, tokens):
    headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401


def test_rotacion_y_deteccion_de_reuso(client, tokens):
    old = tokens["refresh_token"]
    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": old})
    assert r1.status_code == 200
    new = r1.json()["refresh_token"]
    assert new != old

    # Reusar el refresh viejo = posible robo -> se revocan TODAS las sesiones
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old})
    assert r2.status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new}).status_code == 401


def test_logout_revoca_refresh(client, tokens):
    body = {"refresh_token": tokens["refresh_token"]}
    assert client.post("/api/v1/auth/logout", json=body).status_code == 204
    assert client.post("/api/v1/auth/refresh", json=body).status_code == 401


def test_cambio_password_cierra_sesiones(client, tokens, auth):
    r = client.put(
        "/api/v1/users/me/password", headers=auth,
        json={"current_password": "Secreta123", "new_password": "NuevaClave456"},
    )
    assert r.status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    assert login(client, "ana", "Secreta123").status_code == 401
    assert login(client, "ana", "NuevaClave456").status_code == 200


def test_listado_solo_admin(client, auth):
    assert client.get("/api/v1/users/", headers=auth).status_code == 403

    from db.database import get_session
    from main import app
    from models.enums import UserRole
    from models.user_model import User

    session: Session = next(app.dependency_overrides[get_session]())
    user = session.exec(select(User).where(User.username == "ana")).one()
    user.role = UserRole.admin
    session.add(user)
    session.commit()

    admin_token = login(client).json()["access_token"]
    r = client.get("/api/v1/users/", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200 and r.headers["X-Total-Count"] == "1"
