---
{
  "name": "finanzas_tickets",
  "description": "Plataforma FinanzasESP: sube tickets de compra (foto pequeña guardada en el dispositivo) a la API de finanzas, que los guarda en MinIO, y consulta los tickets registrados y su estado. Úsala cuando el usuario pida subir/registrar/enviar un ticket o recibo, o pregunte por sus tickets, compras o gastos.",
  "metadata": {
    "cap_groups": ["cap_http_request", "cap_files"],
    "manage_mode": "readonly"
  }
}
---

# FinanzasESP: tickets de compra

Este dispositivo es un cliente de la plataforma de finanzas personales
**FinanzasESP**. El backend (FastAPI + PostgreSQL + MinIO) corre en la PC de la
red local. Tú solo llamas a la API con `http_request`.

## Configuración fija (no se la pidas al usuario)

- BASE_URL: `http://172.18.4.111:8000`  <!-- EDITA con la IPv4 actual de la PC (ipconfig) -->
- DEVICE_KEY: `fesp_PEGA_AQUI_LA_LLAVE`  <!-- EDITA: se obtiene en el panel web -> Dispositivos ESP32 -->
- Todas las peticiones con cuerpo usan `"Content-Type": "application/json"`.
- Las respuestas son JSON en texto. Contesta al usuario en español, breve,
  sin pegar el JSON crudo.

## Paso 1 - Obtener un token de dispositivo (siempre primero)

El dispositivo NO usa usuario y contraseña: cambia su llave por un JWT que dura
60 minutos. Si una petición posterior responde `HTTP 401`, repite este paso
una sola vez y reintenta.

```json
{
  "url": "http://172.18.4.111:8000/api/v1/auth/device-token",
  "method": "POST",
  "headers": { "Content-Type": "application/json" },
  "body": "{\"device_key\":\"fesp_PEGA_AQUI_LA_LLAVE\"}"
}
```

- `HTTP 200` -> toma `access_token` del cuerpo; úsalo como `<TOKEN>` abajo.
- `HTTP 401` -> la llave es incorrecta o el dispositivo fue revocado desde el
  panel web. Díselo al usuario y detente.

## Paso 2A - Subir un ticket (imagen pequeña en el dispositivo)

1. Lee el archivo de la foto (por ejemplo `/fatfs/tickets/ticket.jpg`) con las
   herramientas de archivos y obtén su contenido en **base64**.
2. Envíalo:

```json
{
  "url": "http://172.18.4.111:8000/api/v1/tickets/base64",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer <TOKEN>"
  },
  "body": "{\"image_base64\":\"<BASE64>\",\"content_type\":\"image/jpeg\",\"notes\":\"Subido desde ESP32\"}"
}
```

- `HTTP 201` -> ticket guardado en MinIO con estado `pendiente`. Responde con
  el `id` corto (primeros 8 caracteres) y la fecha.
- `HTTP 409` -> ese mismo ticket ya se había subido. Avísalo, no reintentes.
- `HTTP 413` / `HTTP 415` -> imagen muy grande o formato no permitido
  (solo JPEG, PNG, WebP o PDF).
- `HTTP 400` -> el base64 no es válido.

**Límite importante:** el base64 tiene que ir completo dentro de `body`. Solo es
práctico con imágenes pequeñas (unos pocos KB, ej. 180x280 px en JPEG calidad
50). Si la imagen es grande, no intentes pegarla: dile al usuario que la suba
desde el panel web (`http://172.18.4.111:8000/`).

## Paso 2B - Consultar tickets

```json
{
  "url": "http://172.18.4.111:8000/api/v1/tickets/?limit=5",
  "method": "GET",
  "headers": { "Authorization": "Bearer <TOKEN>" }
}
```

Devuelve una lista (del más reciente al más antiguo). Para cada ticket resume:
fecha (`created_at`), estado (`status`), origen (`source`: web o esp32) y,
si ya fue procesado, tienda (`store_name`) y `total`.

Filtros útiles en la URL: `status=pendiente`, `created_from=2026-10-01`,
`created_to=2026-10-31`.

## Lo que este dispositivo NO puede hacer

Con un token de dispositivo la API responde `HTTP 403` a: borrar tickets,
cambiar la contraseña, borrar la cuenta o crear otros dispositivos. Si el
usuario lo pide, indícale que lo haga desde el panel web.
