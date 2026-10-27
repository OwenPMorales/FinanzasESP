# FinanzasESP

Plataforma de finanzas personales conectada a un **ESP32**. Subes tus tickets de
compra (desde la web o desde el dispositivo), se guardan en **MinIO** y la
plataforma registra precios, productos y fechas para que lleves el control de
tus gastos.

> **Rama `v01` — Primer entregable:** modelo User · Hasheo · Token · MinIO.
> El documento completo (introducción, desarrollo y conclusión) está en
> [docs/Entregable_v01_FinanzasESP.pdf](docs/Entregable_v01_FinanzasESP.pdf)
> (también en Word: [docs/Entregable_v01_FinanzasESP.docx](docs/Entregable_v01_FinanzasESP.docx)).

## Arquitectura

```
 ESP32 (ESP-Claw) ──HTTP/JSON──┐
                               ▼
 Navegador (panel web) ──► FastAPI ──► PostgreSQL   (usuarios, tokens, tickets)
                               │
                               └─────► MinIO        (imágenes / PDF de tickets, avatares)
                               └ ─ ─ ► IA (v02)     (Gemini: lee el ticket → productos y precios)
```

## Tecnologías y por qué

| Tecnología | Uso | Justificación |
|---|---|---|
| **FastAPI** | API REST | Asíncrono, valida con Pydantic y genera Swagger (`/docs`) automáticamente. |
| **SQLModel** | ORM | Un solo modelo sirve como tabla (SQLAlchemy) y como validación (Pydantic). |
| **PostgreSQL 15** | Base de datos | Transacciones ACID, `NUMERIC` exacto para dinero, tipos `UUID` y `ENUM`. |
| **Alembic** | Migraciones | Versiona el esquema; `upgrade`/`downgrade` reproducibles. |
| **Argon2id** (passlib) | Hasheo | Ganador de la Password Hashing Competition y recomendado por OWASP. Es *memory-hard*. |
| **JWT** (python-jose) | Tokens | Sin estado para el access token; refresh token con rotación y revocación en BD. |
| **MinIO** (SDK oficial) | Archivos | Almacenamiento de objetos compatible con S3, local en Docker, migrable a AWS sin cambiar código. |
| **Docker Compose** | Infraestructura | PostgreSQL y MinIO idénticos en cualquier PC con un solo comando. |
| **ESP-Claw** (ESP32-S3) | Dispositivo | Agente en el ESP32 que llama a la API con `http_request` siguiendo un `SKILL.md`. |
| **pytest** | Pruebas | 22 pruebas con SQLite en memoria y MinIO simulado. |

## Lo que incluye la v01

**Modelo User** — UUID como llave primaria (no enumerable), `username` y `email`
únicos e indexados, rol (`user`/`admin`), moneda y presupuesto mensual, llave
del avatar en MinIO, `created_at` / `updated_at` / `last_login_at`.

**Hasheo** — Argon2id con `m=19 MiB, t=2, p=1` (mínimo de OWASP), sal aleatoria
por hash, *rehash* automático al iniciar sesión si se suben los parámetros,
verificación señuelo contra *timing attacks* cuando el usuario no existe, y
política de contraseña (8–128 caracteres, letra y número). Las llaves de los
ESP32 se guardan como SHA-256 (tienen 256 bits de entropía).

**Token** — Tres tipos de JWT firmados con HS256 (`type`, `jti`, `iss`, `iat`, `exp`):

| Tipo | Duración | Para qué |
|---|---|---|
| `access` | 30 min | Peticiones del usuario (`Authorization: Bearer`). |
| `refresh` | 7 días | Obtener un par nuevo. Se **rota** en cada uso; si se reutiliza uno viejo se cierran todas las sesiones. |
| `device` | 60 min | El ESP32 cambia su llave por este token. Solo puede subir/consultar tickets. |

**MinIO** — Bucket `finanzas-esp` con llaves `users/<id>/avatar/...` y
`users/<id>/tickets/AAAA/MM/<ticket>.jpg`. Validación por *magic bytes* (no se
confía en el `Content-Type`), límite de 5 MB, detección de duplicados por
SHA-256, URLs prefirmadas de 15 min, descarga por streaming y borrado en cascada
al eliminar la cuenta.

## Modelos de base de datos

```
users 1──N refresh_tokens        users 1──N devices 1──N tickets (device_id, opcional)
users 1──N tickets 1──N ticket_items N──1 categories (globales o del usuario)
```

`ticket_items` y `categories` ya existen en el esquema (con 8 categorías
sembradas por la migración) y se llenarán en la v02 con la IA.

## Modelos de IA (planeados para v02)

| Modelo | Tarea | Por qué |
|---|---|---|
| **Gemini 2.5 Flash** (multimodal) | Leer la foto del ticket y devolver JSON con tienda, fecha, productos, cantidades y precios. | Lee imagen directamente (sin OCR aparte), soporta salida estructurada con esquema JSON, barato y rápido. |
| **Tesseract OCR + LLM de texto** (respaldo) | Si no hay API o falla, OCR local + extracción con LLM. | Funciona sin enviar la imagen a la nube. |
| **LLM clasificador** | Asignar cada producto a una categoría. | Las descripciones de tickets son abreviadas ("LCHE ENT 1L"); un LLM las entiende mejor que reglas. |
| **Agente del ESP-Claw** | Interpretar órdenes en lenguaje natural en el ESP32 y llamar a la API. | El usuario habla con el dispositivo; el `SKILL.md` le dice qué endpoints usar. |

La tabla `tickets` ya guarda `ocr_raw_text`, `ai_model` y `ai_confidence` para
auditar qué modelo leyó cada ticket.

## Puesta en marcha

Requisitos: Python 3.12+, Docker Desktop.

```powershell
# Todo en uno (venv, .env, Docker, migraciones y servidor):
PowerShell -ExecutionPolicy Bypass -File .\iniciar.ps1
```

O paso a paso:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env          # y cambia SECRET_KEY
docker compose up -d
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

| Servicio | URL |
|---|---|
| Panel web | http://localhost:8000/ |
| Swagger | http://localhost:8000/docs |
| Consola MinIO | http://localhost:9031 (`finanzas_admin` / `finanzas_minio_2026`) |
| PostgreSQL | `localhost:5440` (`finanzas` / `finanzas_secret_2026`) |

```powershell
pytest                                   # 22 pruebas
python scripts\demo_flujo.py             # flujo completo contra el servidor real
python scripts\crear_admin.py <usuario>  # promover a administrador
```

## Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST | `/api/v1/auth/register` | — | Registro |
| POST | `/api/v1/auth/token` | — | Login OAuth2 (form) → access + refresh |
| POST | `/api/v1/auth/refresh` | — | Rotación del refresh token |
| POST | `/api/v1/auth/logout` | — | Revoca el refresh token |
| POST | `/api/v1/auth/device-token` | llave ESP32 | Llave → JWT de dispositivo |
| GET / PATCH / DELETE | `/api/v1/users/me` | usuario | Perfil (DELETE borra BD + MinIO) |
| PUT | `/api/v1/users/me/password` | usuario | Cambia contraseña y cierra sesiones |
| PUT / GET / DELETE | `/api/v1/users/me/avatar` | usuario | Avatar en MinIO / URL prefirmada |
| GET | `/api/v1/users/` | admin | Lista paginada con filtros |
| POST / GET | `/api/v1/devices/` | usuario | Vincular / listar ESP32 |
| DELETE | `/api/v1/devices/{id}` | usuario | Revocar ESP32 |
| POST | `/api/v1/tickets/` | usuario o ESP32 | Subir ticket (multipart) |
| POST | `/api/v1/tickets/base64` | usuario o ESP32 | Subir ticket en JSON (ESP32) |
| GET | `/api/v1/tickets/` | usuario o ESP32 | Listar con filtros y paginación |
| GET | `/api/v1/tickets/{id}` | usuario o ESP32 | Detalle + URL prefirmada |
| GET | `/api/v1/tickets/{id}/image` | usuario o ESP32 | Descarga por streaming |
| DELETE | `/api/v1/tickets/{id}` | usuario | Borra ticket + imagen |

## ESP32 (ESP-Claw)

1. En el panel web → **Dispositivos ESP32** → vincula uno y copia la llave `fesp_...`.
2. Edita `BASE_URL` y `DEVICE_KEY` en [esp32/espclaw_skill/finanzas_tickets/SKILL.md](esp32/espclaw_skill/finanzas_tickets/SKILL.md).
3. En la Web Config del ESP-Claw: agrega la IP de la PC al **HTTP allowlist**,
   confirma `cap_http_request` y sube el archivo a `skills/finanzas_tickets/SKILL.md`.
4. Desde el Web Chat: *"sube el ticket /fatfs/tickets/ticket.jpg"* o *"¿cuáles son mis últimos tickets?"*.

## Estructura

```
FinanzasESP/
├── main.py                 # App, CORS, routers, /health, panel web
├── core/                   # config (.env) y security (Argon2id, JWT, llaves)
├── db/                     # engine y sesión
├── models/                 # tablas SQLModel
├── schemas/                # entrada/salida Pydantic
├── services/               # storage_service (MinIO)
├── api/v1/                 # auth, users, devices, tickets + dependencias
├── alembic/                # migraciones
├── static/index.html       # panel web
├── esp32/                  # SKILL.md para ESP-Claw
├── scripts/                # demo, crear_admin
├── samples/                # tickets de ejemplo
├── tests/                  # pytest
└── docs/                   # PDF del entregable y evidencias
```

## Hoja de ruta

- **v01** (esta rama): User, hasheo, tokens, MinIO, dispositivos, subida de tickets.
- **v02**: lectura de tickets con IA → `ticket_items`, categorías automáticas.
- **v03**: resumen de gastos por mes/categoría, presupuesto y alertas en el ESP32.
