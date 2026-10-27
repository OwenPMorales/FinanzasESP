import base64

from tests.conftest import JPEG_BYTES, PDF_BYTES, PNG_BYTES


def _upload(client, auth, data=JPEG_BYTES, name="ticket.jpg"):
    return client.post(
        "/api/v1/tickets/", headers=auth,
        files={"file": (name, data, "image/jpeg")}, data={"notes": "Súper"},
    )


# === Avatar ===

def test_avatar_sube_a_minio_y_da_url_prefirmada(client, auth, storage):
    r = client.put("/api/v1/users/me/avatar", headers=auth, files={"file": ("a.png", PNG_BYTES, "image/png")})
    assert r.status_code == 200 and r.json()["has_avatar"] is True
    (key,) = storage.objects
    assert key.startswith("users/") and key.endswith("/avatar/avatar.png")

    url = client.get("/api/v1/users/me/avatar", headers=auth).json()["url"]
    assert "X-Amz-Signature" in url


def test_avatar_valida_contenido_real(client, auth):
    # Dice ser PNG pero el contenido es texto: se rechaza por magic bytes
    r = client.put("/api/v1/users/me/avatar", headers=auth, files={"file": ("a.png", b"hola mundo", "image/png")})
    assert r.status_code == 415
    # PDF no es válido como avatar
    r = client.put("/api/v1/users/me/avatar", headers=auth, files={"file": ("a.pdf", PDF_BYTES, "application/pdf")})
    assert r.status_code == 415


# === Tickets ===

def test_subir_ticket_multipart(client, auth, storage):
    r = _upload(client, auth)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pendiente" and body["source"] == "web"
    assert body["image_content_type"] == "image/jpeg"
    (key,) = storage.objects
    assert f"/tickets/" in key and key.endswith(f"{body['id']}.jpg")


def test_ticket_pdf_y_limite_de_tamano(client, auth):
    assert _upload(client, auth, PDF_BYTES, "factura.pdf").status_code == 201
    grande = b"\xff\xd8\xff" + b"0" * (1024 * 1024 + 10)  # MAX_UPLOAD_MB=1 en pruebas
    assert _upload(client, auth, grande).status_code == 413


def test_ticket_duplicado(client, auth):
    assert _upload(client, auth).status_code == 201
    assert _upload(client, auth).status_code == 409


def test_detalle_listado_descarga_y_borrado(client, auth, storage):
    ticket_id = _upload(client, auth).json()["id"]
    _upload(client, auth, PNG_BYTES, "otro.png")

    r = client.get("/api/v1/tickets/", headers=auth)
    assert r.status_code == 200 and r.headers["X-Total-Count"] == "2"

    detail = client.get(f"/api/v1/tickets/{ticket_id}", headers=auth).json()
    assert detail["image_url"].startswith("http://minio.test/") and detail["items"] == []

    img = client.get(f"/api/v1/tickets/{ticket_id}/image", headers=auth)
    assert img.status_code == 200 and img.content == JPEG_BYTES

    assert client.delete(f"/api/v1/tickets/{ticket_id}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/tickets/{ticket_id}", headers=auth).status_code == 404
    assert len(storage.objects) == 1


def test_aislamiento_entre_usuarios(client, auth):
    from tests.conftest import login, register

    ticket_id = _upload(client, auth).json()["id"]
    register(client, "beto")
    otro = {"Authorization": f"Bearer {login(client, 'beto').json()['access_token']}"}
    assert client.get(f"/api/v1/tickets/{ticket_id}", headers=otro).status_code == 404
    assert client.get("/api/v1/tickets/", headers=otro).json() == []


# === ESP32 ===

def test_flujo_esp32_llave_token_y_base64(client, auth, storage):
    r = client.post("/api/v1/devices/", headers=auth, json={"name": "ESP32-S3 cocina"})
    assert r.status_code == 201
    device = r.json()
    assert device["device_key"].startswith("fesp_")

    # La llave en claro no vuelve a aparecer
    listed = client.get("/api/v1/devices/", headers=auth).json()
    assert "device_key" not in listed[0]

    tok = client.post("/api/v1/auth/device-token", json={"device_key": device["device_key"]})
    assert tok.status_code == 200
    esp = {"Authorization": f"Bearer {tok.json()['access_token']}"}

    payload = {"image_base64": "data:image/jpeg;base64," + base64.b64encode(JPEG_BYTES).decode()}
    r = client.post("/api/v1/tickets/base64", headers=esp, json=payload)
    assert r.status_code == 201
    assert r.json()["source"] == "esp32" and r.json()["device_id"] == device["id"]

    # Permisos limitados del dispositivo
    assert client.get("/api/v1/tickets/", headers=esp).status_code == 200
    assert client.delete(f"/api/v1/tickets/{r.json()['id']}", headers=esp).status_code == 403
    assert client.delete("/api/v1/users/me", headers=esp).status_code == 403
    assert client.post("/api/v1/devices/", headers=esp, json={"name": "x2"}).status_code == 403

    # Revocar el dispositivo invalida su token al instante
    assert client.delete(f"/api/v1/devices/{device['id']}", headers=auth).status_code == 204
    assert client.get("/api/v1/tickets/", headers=esp).status_code == 401
    assert client.post("/api/v1/auth/device-token", json={"device_key": device["device_key"]}).status_code == 401


def test_base64_invalido(client, auth):
    r = client.post("/api/v1/tickets/base64", headers=auth, json={"image_base64": "esto no es base64!!"})
    assert r.status_code == 400


def test_borrar_cuenta_limpia_minio(client, auth, storage):
    _upload(client, auth)
    client.put("/api/v1/users/me/avatar", headers=auth, files={"file": ("a.png", PNG_BYTES, "image/png")})
    assert len(storage.objects) == 2
    assert client.delete("/api/v1/users/me", headers=auth).status_code == 204
    assert storage.objects == {}
    assert client.get("/api/v1/users/me", headers=auth).status_code == 401
