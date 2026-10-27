"""
Recorre el flujo completo del entregable v01 contra el servidor REAL
(PostgreSQL + MinIO en Docker) e imprime cada paso. Sirve como evidencia.

Uso:  python scripts/demo_flujo.py [http://localhost:8000]
"""
import base64
import sys
import uuid
from pathlib import Path

import httpx
from jose import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.storage_service import get_storage  # noqa: E402

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
API = f"{BASE}/api/v1"
SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def paso(n: int, titulo: str, r: httpx.Response, extra: str = "") -> None:
    print(f"[{n:02d}] {titulo:<52} -> HTTP {r.status_code} {extra}")


def main() -> None:
    c = httpx.Client(timeout=30)
    user = f"demo_{uuid.uuid4().hex[:6]}"
    password = "Finanzas2026"

    paso(1, "GET /health", r := c.get(f"{BASE}/health"), str(r.json()))

    r = c.post(f"{API}/auth/register", json={
        "username": user, "email": f"{user}@finanzas-esp.com",
        "password": password, "full_name": "Usuario Demo",
    })
    paso(2, "Registro (Argon2id)", r, f"id={r.json()['id']}")
    weak = c.post(f"{API}/auth/register", json={"username": user + "x", "email": f"{user}x@a.com", "password": "corta"})
    paso(3, "Registro con contraseña débil (rechazo)", weak)

    r = c.post(f"{API}/auth/token", data={"username": user, "password": password})
    tokens = r.json()
    claims = jwt.get_unverified_claims(tokens["access_token"])
    paso(4, "Login OAuth2 -> access + refresh", r, f"type={claims['type']} exp_in={tokens['expires_in']}s")
    paso(5, "Login con contraseña incorrecta", c.post(f"{API}/auth/token", data={"username": user, "password": "Mala12345"}))
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}

    paso(6, "GET /users/me sin token", c.get(f"{API}/users/me"))
    r = c.get(f"{API}/users/me", headers=auth)
    paso(7, "GET /users/me con Bearer", r, f"username={r.json()['username']}")

    with open(SAMPLES / "ticket_ejemplo.jpg", "rb") as fh:
        avatar = fh.read()
    r = c.put(f"{API}/users/me/avatar", headers=auth, files={"file": ("avatar.jpg", avatar, "image/jpeg")})
    paso(8, "PUT /users/me/avatar (MinIO)", r, f"has_avatar={r.json()['has_avatar']}")
    url = c.get(f"{API}/users/me/avatar", headers=auth).json()["url"]
    paso(9, "URL prefirmada del avatar (descarga directa)", c.get(url), url.split("?")[0])

    r = c.post(f"{API}/tickets/", headers=auth, files={"file": ("ticket.jpg", avatar, "image/jpeg")},
               data={"notes": "Súper semanal"})
    ticket = r.json()
    paso(10, "POST /tickets/ (multipart -> MinIO)", r, f"status={ticket['status']} source={ticket['source']}")
    paso(11, "Mismo ticket otra vez (SHA-256 duplicado)", c.post(
        f"{API}/tickets/", headers=auth, files={"file": ("ticket.jpg", avatar, "image/jpeg")}))
    paso(12, "Archivo falso .jpg (magic bytes)", c.post(
        f"{API}/tickets/", headers=auth, files={"file": ("x.jpg", b"no soy imagen", "image/jpeg")}))

    r = c.post(f"{API}/devices/", headers=auth, json={"name": "ESP32-S3 demo"})
    device = r.json()
    paso(13, "POST /devices/ (llave del ESP32)", r, f"key={device['device_key'][:12]}...")
    r = c.post(f"{API}/auth/device-token", json={"device_key": device["device_key"]})
    esp = {"Authorization": f"Bearer {r.json()['access_token']}"}
    paso(14, "POST /auth/device-token", r, f"type={jwt.get_unverified_claims(r.json()['access_token'])['type']}")

    mini = base64.b64encode((SAMPLES / "ticket_esp32_mini.jpg").read_bytes()).decode()
    r = c.post(f"{API}/tickets/base64", headers=esp, json={"image_base64": mini, "content_type": "image/jpeg"})
    paso(15, "ESP32: POST /tickets/base64", r, f"source={r.json()['source']}")
    paso(16, "ESP32 intenta borrar la cuenta (prohibido)", c.delete(f"{API}/users/me", headers=esp))

    r = c.get(f"{API}/tickets/", headers=auth)
    paso(17, "GET /tickets/", r, f"X-Total-Count={r.headers['X-Total-Count']}")
    r = c.get(f"{API}/tickets/{ticket['id']}", headers=auth)
    paso(18, "GET /tickets/{id} (URL prefirmada)", r, f"items={r.json()['items']}")
    r = c.get(f"{API}/tickets/{ticket['id']}/image", headers=auth)
    paso(19, "GET /tickets/{id}/image (stream)", r, f"{len(r.content)} bytes")

    r = c.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    nuevos = r.json()
    paso(20, "POST /auth/refresh (rotación)", r)
    paso(21, "Reusar refresh viejo (detección de robo)", c.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}))
    paso(22, "Refresh nuevo tras la alarma (revocado)", c.post(
        f"{API}/auth/refresh", json={"refresh_token": nuevos["refresh_token"]}))

    storage = get_storage()
    objetos = [o.object_name for o in storage.client.list_objects(
        storage.bucket, prefix=f"users/{claims['sub']}/", recursive=True)]
    print(f"\nObjetos en MinIO del usuario ({len(objetos)}):")
    for name in objetos:
        print("   ", name)

    if "--limpiar" in sys.argv:
        paso(23, "DELETE /users/me (BD + MinIO)", c.delete(f"{API}/users/me", headers=auth))


if __name__ == "__main__":
    main()
