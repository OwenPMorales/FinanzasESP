"""
Genera docs/Entregable_v01_FinanzasESP.pdf (introducción, desarrollo y conclusión).

Uso:  python docs/generar_pdf.py
"""
from datetime import date
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = DOCS / "Entregable_v01_FinanzasESP.pdf"

FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Arial", FONTS / "arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", FONTS / "arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", FONTS / "ariali.ttf"))
pdfmetrics.registerFont(TTFont("Consolas", FONTS / "consola.ttf"))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic")

TEAL = colors.HexColor("#0f766e")
TEAL_SOFT = colors.HexColor("#ccfbf1")
SLATE = colors.HexColor("#334155")
GRAY = colors.HexColor("#64748b")
LINE = colors.HexColor("#cbd5e1")
CODE_BG = colors.HexColor("#f1f5f9")

base = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("t", fontName="Arial-Bold", fontSize=28, leading=34, textColor=TEAL, alignment=TA_CENTER),
    "subtitle": ParagraphStyle("st", fontName="Arial", fontSize=14, leading=20, textColor=SLATE, alignment=TA_CENTER),
    "cover": ParagraphStyle("c", fontName="Arial", fontSize=11, leading=16, textColor=GRAY, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", fontName="Arial-Bold", fontSize=18, leading=24, textColor=TEAL, spaceBefore=6, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Arial-Bold", fontSize=13.5, leading=18, textColor=SLATE, spaceBefore=12, spaceAfter=6),
    "h3": ParagraphStyle("h3", fontName="Arial-Bold", fontSize=11, leading=15, textColor=SLATE, spaceBefore=8, spaceAfter=4),
    "body": ParagraphStyle("b", fontName="Arial", fontSize=10.5, leading=15.5, alignment=TA_JUSTIFY, spaceAfter=6),
    "bullet": ParagraphStyle("bl", fontName="Arial", fontSize=10.5, leading=15, leftIndent=14, bulletIndent=4, spaceAfter=2),
    "cell": ParagraphStyle("cell", fontName="Arial", fontSize=9, leading=12),
    "cellb": ParagraphStyle("cellb", fontName="Arial-Bold", fontSize=9, leading=12, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Consolas", fontSize=8, leading=10.5, backColor=CODE_BG,
                           borderPadding=6, leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=10),
    "caption": ParagraphStyle("cap", fontName="Arial-Italic", fontSize=9, leading=12, textColor=GRAY, alignment=TA_CENTER, spaceAfter=10),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items, numbered=False):
    return [
        Paragraph(i, S["bullet"], bulletText=f"{n}." if numbered else "•")
        for n, i in enumerate(items, 1)
    ]


def code(text, width=92):
    # Preformatted no hace salto de línea: se parten a mano las líneas largas.
    lines = []
    for line in text.strip("\n").splitlines():
        while len(line) > width:
            lines.append(line[:width])
            line = "      " + line[width:]
        lines.append(line)
    return Preformatted("\n".join(lines), S["code"])


def table(rows, widths, header=True):
    data = [
        [Paragraph(str(c), S["cellb" if header and r == 0 else "cell"]) for c in row]
        for r, row in enumerate(rows)
    ]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), TEAL))
    t.setStyle(TableStyle(style))
    return t


def caption(text):
    return P(text, "caption")


# ----------------------------------------------------------------------------
# Diagramas
# ----------------------------------------------------------------------------

def box(d, x, y, w, h, title, lines=(), fill=TEAL_SOFT):
    d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=TEAL, strokeWidth=1, rx=4, ry=4))
    d.add(String(x + w / 2, y + h - 14, title, fontName="Arial-Bold", fontSize=9.5,
                 fillColor=SLATE, textAnchor="middle"))
    for i, line in enumerate(lines):
        d.add(String(x + w / 2, y + h - 28 - i * 11, line, fontName="Arial", fontSize=7.5,
                     fillColor=GRAY, textAnchor="middle"))


def arrow(d, x1, y1, x2, y2, label="", dashed=False, color=SLATE):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.2,
               strokeDashArray=[4, 3] if dashed else None))
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    s = 6
    p1 = (x2 - s * math.cos(ang - 0.4), y2 - s * math.sin(ang - 0.4))
    p2 = (x2 - s * math.cos(ang + 0.4), y2 - s * math.sin(ang + 0.4))
    d.add(Polygon([x2, y2, *p1, *p2], fillColor=color, strokeColor=color))
    if label:
        d.add(String((x1 + x2) / 2, (y1 + y2) / 2 + 4, label, fontName="Arial", fontSize=7.5,
                     fillColor=GRAY, textAnchor="middle"))


def architecture_diagram():
    d = Drawing(470, 215)
    box(d, 0, 140, 120, 60, "ESP32-S3", ["ESP-Claw + SKILL.md", "http_request"])
    box(d, 0, 30, 120, 60, "Navegador", ["Panel web / Swagger", "multipart, JSON"])
    box(d, 175, 70, 120, 90, "FastAPI", ["auth / users", "devices / tickets", "Argon2id + JWT", "uvicorn :8000"],
        fill=colors.HexColor("#99f6e4"))
    box(d, 350, 150, 120, 55, "PostgreSQL 15", ["usuarios, tokens,", "tickets  (:5440)"])
    box(d, 350, 80, 120, 55, "MinIO", ["imágenes y PDF", "bucket finanzas-esp"])
    box(d, 350, 5, 120, 60, "IA (v02)", ["Gemini 2.5 Flash", "OCR de respaldo"], fill=colors.HexColor("#f1f5f9"))
    arrow(d, 120, 170, 175, 135)
    arrow(d, 120, 60, 175, 95)
    d.add(String(150, 162, "JWT device", fontName="Arial", fontSize=7.5, fillColor=GRAY))
    d.add(String(150, 64, "JWT access", fontName="Arial", fontSize=7.5, fillColor=GRAY))
    arrow(d, 295, 140, 350, 175, "SQLModel")
    arrow(d, 295, 115, 350, 107, "S3 API")
    arrow(d, 295, 85, 350, 40, "v02", dashed=True, color=GRAY)
    arrow(d, 360, 80, 120, 45, "", dashed=True, color=GRAY)
    d.add(String(250, 52, "URL prefirmada", fontName="Arial", fontSize=7.5, fillColor=GRAY))
    return d


def er_diagram():
    d = Drawing(470, 320)

    def entity(x, y, name, fields, w=135):
        h = 24 + 11 * len(fields)
        d.add(Rect(x, y, w, h, fillColor=colors.white, strokeColor=TEAL, strokeWidth=1))
        d.add(Rect(x, y + h - 16, w, 16, fillColor=TEAL, strokeColor=TEAL))
        d.add(String(x + 6, y + h - 12, name, fontName="Arial-Bold", fontSize=9, fillColor=colors.white))
        for i, f in enumerate(fields):
            d.add(String(x + 6, y + h - 28 - i * 11, f, fontName="Consolas", fontSize=7, fillColor=SLATE))
        return h

    # users: x 168-303, y 180-303 | tickets: x 168-303, y 8-131
    entity(168, 180, "users", ["PK id UUID", "username UQ", "email UQ", "hashed_password",
                                "role ENUM", "is_active", "currency, monthly_budget",
                                "avatar_key (MinIO)", "created/updated/last_login"])
    entity(0, 226, "refresh_tokens", ["PK id UUID", "FK user_id", "jti UQ", "expires_at",
                                       "revoked_at", "user_agent"], w=120)
    entity(345, 237, "devices", ["PK id UUID", "FK user_id", "name, key_prefix",
                                  "key_hash UQ (SHA-256)", "is_active, last_seen_at"], w=125)
    entity(168, 8, "tickets", ["PK id UUID", "FK user_id, FK device_id", "source, status ENUM",
                                "image_key, content_type", "image_size, image_sha256",
                                "store_name, purchase_date", "total NUMERIC, currency",
                                "ocr_raw_text, ai_model", "ai_confidence"])
    entity(0, 30, "ticket_items", ["PK id UUID", "FK ticket_id", "FK category_id",
                                    "description", "quantity, unit_price", "total_price"], w=120)
    entity(345, 52, "categories", ["PK id UUID", "FK user_id (NULL=global)", "name, color"], w=125)

    def rel(x1, y1, x2, y2, label, dx=0, dy=4):
        d.add(Line(x1, y1, x2, y2, strokeColor=GRAY, strokeWidth=1))
        d.add(String((x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, label, fontName="Arial", fontSize=7,
                     fillColor=GRAY, textAnchor="middle"))

    rel(168, 262, 120, 262, "1 : N")
    rel(303, 262, 345, 262, "1 : N")
    rel(235, 180, 235, 131, "1 : N", dx=14, dy=0)
    rel(168, 70, 120, 70, "1 : N")
    rel(345, 70, 303, 70, "N : 1")
    rel(400, 237, 303, 115, "1 : N (opcional)", dx=34, dy=0)
    return d


def token_flow_diagram():
    d = Drawing(470, 130)
    box(d, 0, 40, 95, 50, "Login", ["usuario + contraseña"])
    box(d, 125, 40, 95, 50, "access + refresh", ["30 min / 7 días"])
    box(d, 250, 40, 95, 50, "/auth/refresh", ["revoca el usado,", "emite par nuevo"])
    box(d, 375, 75, 95, 50, "Uso normal", ["sesión continúa"])
    box(d, 375, 0, 95, 55, "Reuso detectado", ["refresh revocado ->", "se cierran TODAS", "las sesiones"],
        fill=colors.HexColor("#fee2e2"))
    arrow(d, 95, 65, 125, 65)
    arrow(d, 220, 65, 250, 65)
    arrow(d, 345, 72, 375, 98)
    arrow(d, 345, 55, 375, 30, color=colors.HexColor("#b91c1c"))
    return d


# ----------------------------------------------------------------------------
# Contenido
# ----------------------------------------------------------------------------

def read(name):
    return (DOCS / name).read_text(encoding="utf-8").strip()


def on_page(canvas, doc):
    if doc.page == 1:
        return
    canvas.saveState()
    canvas.setFont("Arial", 8.5)
    canvas.setFillColor(GRAY)
    canvas.drawString(2 * cm, 1.3 * cm, "FinanzasESP — Entregable v01: User, Hasheo, Token y MinIO")
    canvas.drawRightString(letter[0] - 2 * cm, 1.3 * cm, f"Página {doc.page}")
    canvas.setStrokeColor(LINE)
    canvas.line(2 * cm, 1.7 * cm, letter[0] - 2 * cm, 1.7 * cm)
    canvas.restoreState()


def build():
    story = []
    W = letter[0] - 4 * cm

    # --- Portada ---
    story += [
        Spacer(1, 4.5 * cm),
        P("FinanzasESP", "title"),
        Spacer(1, 10),
        P("Plataforma de finanzas personales con ESP32 y tickets de compra", "subtitle"),
        Spacer(1, 30),
        P("Entregable v01 — Modelo User · Hasheo · Token · MinIO", "subtitle"),
        Spacer(1, 2.5 * cm),
        P("Documentación, explicación y justificación de tecnologías,<br/>"
          "modelos de base de datos y modelos de inteligencia artificial", "cover"),
        Spacer(1, 2.5 * cm),
        P("Owen Morales", "cover"),
        P("Desarrollo Backend con FastAPI", "cover"),
        P("Repositorio GitHub · rama <b>v01</b>", "cover"),
        P(date.today().strftime("%d/%m/%Y"), "cover"),
        PageBreak(),
    ]

    # --- Índice ---
    story += [
        P("Contenido", "h1"),
        *bullets([
            "1. Introducción",
            "2. Desarrollo",
            "&nbsp;&nbsp;&nbsp;2.1 Arquitectura general",
            "&nbsp;&nbsp;&nbsp;2.2 Tecnologías y justificación",
            "&nbsp;&nbsp;&nbsp;2.3 Modelos de base de datos",
            "&nbsp;&nbsp;&nbsp;2.4 Modelo User",
            "&nbsp;&nbsp;&nbsp;2.5 Hasheo de contraseñas",
            "&nbsp;&nbsp;&nbsp;2.6 Tokens (JWT)",
            "&nbsp;&nbsp;&nbsp;2.7 Almacenamiento con MinIO",
            "&nbsp;&nbsp;&nbsp;2.8 Integración con el ESP32",
            "&nbsp;&nbsp;&nbsp;2.9 Modelos de inteligencia artificial",
            "&nbsp;&nbsp;&nbsp;2.10 Entorno, pruebas y evidencias",
            "&nbsp;&nbsp;&nbsp;2.11 Repositorio y rama v01",
            "3. Conclusión",
            "Referencias",
        ]),
        PageBreak(),
    ]

    # --- 1. Introducción ---
    story += [
        P("1. Introducción", "h1"),
        P("La mayoría de las personas no sabe con precisión en qué gasta su dinero. Los tickets de compra "
          "contienen exactamente esa información —tienda, fecha, productos, cantidades y precios— pero "
          "terminan en una bolsa o en la basura. Capturarlos a mano en una hoja de cálculo es tedioso y, "
          "por eso, casi nadie lo hace de forma constante."),
        P("<b>FinanzasESP</b> es una plataforma que resuelve ese problema: el usuario sube la foto o el PDF "
          "de su ticket desde un panel web o desde un dispositivo <b>ESP32</b> (con el firmware de agente "
          "ESP-Claw), la imagen se guarda de forma segura en <b>MinIO</b> y, en la siguiente versión, un "
          "modelo de inteligencia artificial extrae los productos y precios para construir el historial de "
          "gastos, compararlo contra un presupuesto mensual y detectar cambios de precio entre compras."),
        P("Este documento corresponde al <b>primer entregable (rama v01)</b>, cuyo alcance es la base de "
          "seguridad e infraestructura sobre la que se construye todo lo demás:"),
        *bullets([
            "<b>Modelo User</b>: la entidad dueña de los tickets, dispositivos y preferencias financieras.",
            "<b>Hasheo</b>: almacenamiento seguro de contraseñas con Argon2id.",
            "<b>Token</b>: autenticación con JWT (access, refresh con rotación y token de dispositivo).",
            "<b>MinIO</b>: almacenamiento de objetos para avatares y tickets de compra.",
        ]),
        P("Además del mínimo pedido, se desarrollaron: vinculación de dispositivos ESP32 con llaves propias, "
          "subida de tickets (multipart y base64), un panel web, migraciones con Alembic, 22 pruebas "
          "automatizadas y la skill para el agente ESP-Claw. También se documenta el esquema completo de base "
          "de datos y los modelos de IA que se integrarán en la v02."),
        PageBreak(),
    ]

    # --- 2. Desarrollo ---
    story += [
        P("2. Desarrollo", "h1"),
        P("2.1 Arquitectura general", "h2"),
        P("El sistema sigue una arquitectura cliente-servidor en capas. Los clientes (navegador y ESP32) solo "
          "hablan con la API; la API es la única que accede a PostgreSQL y a MinIO. Los archivos nunca pasan "
          "por la base de datos: en PostgreSQL solo se guarda la <i>llave</i> del objeto en MinIO."),
        architecture_diagram(),
        caption("Figura 1. Arquitectura de FinanzasESP (líneas punteadas: componentes de la v02)."),
        P("El código respeta la estructura en capas usada a lo largo del curso:"),
        table([
            ["Carpeta", "Responsabilidad"],
            ["core/", "Configuración desde <font face='Consolas'>.env</font> (pydantic-settings) y seguridad: Argon2id, JWT, llaves de dispositivo."],
            ["db/", "Motor de SQLModel y la dependencia <font face='Consolas'>get_session</font>."],
            ["models/", "Tablas (SQLModel, table=True) y enumeraciones."],
            ["schemas/", "Contratos de entrada y salida (Pydantic). Nunca exponen el hash."],
            ["services/", "<font face='Consolas'>storage_service</font>: encapsula MinIO; el resto de la API no conoce S3."],
            ["api/v1/", "Routers auth, users, devices, tickets y dependencias de autenticación."],
            ["alembic/", "Migraciones versionadas del esquema."],
            ["tests/", "Pruebas con SQLite en memoria y MinIO simulado."],
        ], [3 * cm, W - 3 * cm]),
        PageBreak(),
    ]

    story += [
        P("2.2 Tecnologías y justificación", "h2"),
        table([
            ["Tecnología", "Rol", "Justificación", "Alternativa descartada"],
            ["FastAPI", "Framework web", "Validación automática con Pydantic, documentación OpenAPI/Swagger "
             "generada sola, inyección de dependencias (ideal para auth y sesiones) y alto rendimiento.",
             "Flask (sin validación ni docs integradas), Django (demasiado pesado para una API)."],
            ["SQLModel", "ORM", "Una clase sirve como tabla y como modelo Pydantic; menos código duplicado. "
             "Basado en SQLAlchemy 2, así que soporta relaciones, cascadas y Alembic.",
             "SQLAlchemy puro (más verboso)."],
            ["PostgreSQL 15", "Base de datos", "ACID, tipo NUMERIC exacto para dinero (no float), UUID y ENUM "
             "nativos, índices y restricciones UNIQUE compuestas. Corre en Docker.",
             "SQLite (sin concurrencia real), MongoDB (los datos financieros son relacionales)."],
            ["Alembic", "Migraciones", "Cambios del esquema versionados y reversibles; la migración inicial "
             "también siembra las categorías.", "create_all (no versiona ni migra)."],
            ["Argon2id (passlib + argon2-cffi)", "Hasheo", "Ganador de la Password Hashing Competition (2015); "
             "OWASP lo recomienda en primer lugar. Resistente a GPU por consumo de memoria.",
             "bcrypt (trunca a 72 bytes, no es memory-hard), SHA-256 (demasiado rápido)."],
            ["JWT (python-jose)", "Tokens", "Estándar RFC 7519; el access token se valida sin consultar sesiones, "
             "y funciona igual para navegador y ESP32 con el header Authorization.",
             "Sesiones con cookie (incómodas para IoT)."],
            ["MinIO + SDK minio", "Archivos", "Almacenamiento de objetos compatible con S3, gratuito y local. "
             "Con el mismo código se podría migrar a AWS S3. URLs prefirmadas.",
             "Guardar archivos en la BD (la infla) o en disco (no escala)."],
            ["Docker Compose", "Infraestructura", "PostgreSQL y MinIO idénticos en cualquier PC con "
             "<font face='Consolas'>docker compose up -d</font>; puertos propios (5440, 9030, 9031).",
             "Instalación manual de servicios."],
            ["ESP-Claw (ESP32-S3)", "Dispositivo", "Firmware de agente de Espressif: se programa con un "
             "SKILL.md en lenguaje natural y la herramienta http_request, sin recompilar firmware.",
             "Sketch Arduino (cada cambio requiere flashear)."],
            ["pytest", "Pruebas", "Pruebas rápidas con TestClient; las dependencias de BD y MinIO se "
             "sustituyen con dependency_overrides.", "Pruebas manuales en Swagger."],
        ], [2.8 * cm, 2.2 * cm, 7.2 * cm, W - 12.2 * cm]),
        PageBreak(),
    ]

    story += [
        P("2.3 Modelos de base de datos", "h2"),
        P("El esquema completo se creó desde la v01 para que la base de datos ya refleje el dominio del "
          "proyecto, aunque <font face='Consolas'>ticket_items</font> y <font face='Consolas'>categories</font> "
          "se llenarán con la IA en la v02. Todas las llaves primarias son <b>UUID</b>: no se pueden "
          "enumerar recursos probando /users/1, /users/2, y el ESP32 puede generar referencias sin chocar."),
        er_diagram(),
        caption("Figura 2. Diagrama entidad-relación (6 tablas)."),
        table([
            ["Tabla", "Propósito", "Decisiones de diseño"],
            ["users", "Cuenta del usuario.", "username y email UNIQUE + índice; dinero en NUMERIC(12,2)."],
            ["refresh_tokens", "Sesiones abiertas.", "Solo se guarda el jti (id del token), nunca el token. "
             "revoked_at permite cerrar sesión y detectar reutilización."],
            ["devices", "ESP32 vinculados.", "Se guarda el SHA-256 de la llave (UNIQUE, indexado). Revocar = "
             "is_active=false, para conservar el origen de sus tickets."],
            ["tickets", "Ticket subido.", "UNIQUE(user_id, image_sha256) evita duplicados. device_id ON DELETE "
             "SET NULL. Campos de IA para trazabilidad."],
            ["ticket_items", "Productos del ticket.", "ON DELETE CASCADE con el ticket; quantity con 3 decimales "
             "(kilos)."],
            ["categories", "Clasificación del gasto.", "user_id NULL = categoría global; la migración siembra 8 "
             "(Despensa, Restaurantes, Transporte, Salud, Hogar, Entretenimiento, Servicios, Otros)."],
        ], [2.8 * cm, 3.4 * cm, W - 6.2 * cm]),
        P("Las relaciones usan <font face='Consolas'>ondelete=\"CASCADE\"</font> en la llave foránea y "
          "<font face='Consolas'>cascade_delete=True</font> en SQLModel: al borrar un usuario se eliminan sus "
          "tokens, dispositivos, tickets y productos en una sola transacción; después la API borra todo su "
          "prefijo en MinIO."),
        PageBreak(),
    ]

    story += [
        P("2.4 Modelo User", "h2"),
        P("El usuario es la raíz del dominio: todo lo demás le pertenece. El modelo combina datos de identidad, "
          "seguridad y preferencias financieras."),
        code('''class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=3, max_length=50)
    email: str = Field(index=True, unique=True, max_length=320)
    full_name: str | None = Field(default=None, max_length=120)
    hashed_password: str = Field(max_length=255)      # solo el hash Argon2id
    role: UserRole = Field(default=UserRole.user)      # user | admin
    is_active: bool = Field(default=True)
    currency: str = Field(default="MXN", min_length=3, max_length=3)
    monthly_budget: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    avatar_key: str | None = Field(default=None, max_length=255)   # llave en MinIO
    created_at / updated_at / last_login_at: datetime

    refresh_tokens / devices / tickets: Relationship(cascade_delete=True)'''),
        table([
            ["Campo", "Justificación"],
            ["id UUID", "No enumerable; seguro de exponer en URLs y en el ESP32."],
            ["username / email", "Únicos e indexados; se normalizan a minúsculas para que ANA y ana sean la misma cuenta. "
             "El login acepta cualquiera de los dos."],
            ["hashed_password", "Nunca se guarda ni se devuelve la contraseña; el esquema de respuesta no incluye el hash."],
            ["role", "Autorización: solo admin puede listar usuarios (GET /api/v1/users/)."],
            ["is_active", "Permite suspender una cuenta sin borrar su historial; sus tokens dejan de servir (403)."],
            ["currency, monthly_budget", "Base de la v03: comparar gastos del mes contra el presupuesto."],
            ["avatar_key", "Se guarda la llave del objeto, no la URL, porque las URLs prefirmadas caducan."],
            ["last_login_at", "Auditoría básica de actividad."],
        ], [3.6 * cm, W - 3.6 * cm]),
        Spacer(1, 6),
        P("Los esquemas separan lo que entra de lo que sale: <font face='Consolas'>UserCreate</font> valida "
          "formato de usuario (letras, números, punto, guion), correo con <font face='Consolas'>EmailStr</font> "
          "y la política de contraseña; <font face='Consolas'>UserUpdate</font> solo permite cambiar nombre, "
          "correo, moneda y presupuesto (no el rol ni is_active); <font face='Consolas'>UserResponse</font> "
          "expone un campo calculado <font face='Consolas'>has_avatar</font> en lugar de la llave interna."),
        PageBreak(),
    ]

    story += [
        P("2.5 Hasheo de contraseñas", "h2"),
        P("Una contraseña nunca debe guardarse en texto plano ni cifrada (lo cifrado se puede descifrar). Se "
          "guarda un <b>hash</b>: una función de un solo sentido. Para contraseñas no sirve cualquier hash: "
          "SHA-256 calcula miles de millones de hashes por segundo en una GPU, así que una contraseña filtrada se "
          "rompe rápido. Se necesita un algoritmo <b>lento a propósito y con sal</b>."),
        P("Se eligió <b>Argon2id</b> con los parámetros mínimos que recomienda OWASP:"),
        table([
            ["Parámetro", "Valor", "Significado"],
            ["Variante", "Argon2id", "Híbrido: resiste ataques de canal lateral (Argon2i) y de GPU (Argon2d)."],
            ["memory_cost (m)", "19 456 KiB (19 MiB)", "Cada intento obliga a reservar 19 MiB: una GPU con miles de núcleos "
             "no tiene memoria para probar tantas contraseñas en paralelo."],
            ["time_cost (t)", "2", "Número de pasadas sobre la memoria."],
            ["parallelism (p)", "1", "Hilos por hash."],
            ["Sal", "16 bytes aleatorios", "Distinta en cada hash: dos usuarios con la misma contraseña tienen hashes diferentes "
             "y las tablas arcoíris no sirven."],
        ], [3.2 * cm, 3.6 * cm, W - 6.8 * cm]),
        Spacer(1, 6),
        P("El hash resultante es autodescriptivo: incluye algoritmo, versión, parámetros y sal. Así se ve en la "
          "base de datos real:"),
        code("$argon2id$v=19$m=19456,t=2,p=1$Z2wNoTTGmHOOce59z/mfsw$i2z2fU...\n"
             " algoritmo  ver  parámetros      sal (base64)         hash"),
        P("Mejoras implementadas sobre el hasheo básico:", "h3"),
        *bullets([
            "<b>Rehash transparente</b>: el login usa <font face='Consolas'>verify_and_update</font>; si en el futuro se "
            "suben los parámetros en el .env, el hash de cada usuario se actualiza la próxima vez que inicia sesión.",
            "<b>Protección contra timing attacks</b>: si el usuario no existe se verifica contra un hash señuelo, para que "
            "la respuesta tarde lo mismo y no revele qué cuentas existen. El mensaje de error también es el mismo.",
            "<b>Política de contraseña</b>: 8 a 128 caracteres con al menos una letra y un número. A diferencia de bcrypt, "
            "Argon2 no trunca a 72 bytes, por lo que se permiten frases largas.",
            "<b>Llaves de dispositivo con SHA-256</b>: las llaves del ESP32 son aleatorias de 256 bits "
            "(<font face='Consolas'>secrets.token_urlsafe(32)</font>); no se pueden adivinar, así que basta un hash rápido, "
            "que además permite buscarlas por índice. Argon2 se reserva para secretos elegidos por humanos.",
        ]),
        code('''pwd_context = CryptContext(
    schemes=["argon2"], deprecated="auto", argon2__type="ID",
    argon2__time_cost=settings.ARGON2_TIME_COST,       # 2
    argon2__memory_cost=settings.ARGON2_MEMORY_COST,   # 19456 KiB
    argon2__parallelism=settings.ARGON2_PARALLELISM,   # 1
)
_DUMMY_HASH = pwd_context.hash("usuario-inexistente")   # contra timing attacks'''),
        PageBreak(),
    ]

    story += [
        P("2.6 Tokens (JWT)", "h2"),
        P("Después del login, el cliente no vuelve a enviar su contraseña: envía un <b>JSON Web Token</b> en el header "
          "<font face='Consolas'>Authorization: Bearer &lt;token&gt;</font>. El token está firmado con HMAC-SHA256 y una "
          "<font face='Consolas'>SECRET_KEY</font> de 512 bits generada con <font face='Consolas'>secrets</font>; si alguien "
          "modifica un solo carácter, la firma deja de coincidir y la API responde 401."),
        table([
            ["Tipo", "Duración", "Obtención", "Uso"],
            ["access", "30 min", "POST /auth/token (OAuth2 form)", "Todas las rutas del usuario."],
            ["refresh", "7 días", "Junto con el access", "Solo POST /auth/refresh y /auth/logout. Se rota en cada uso."],
            ["device", "60 min", "POST /auth/device-token con la llave del ESP32", "Subir y consultar tickets. Prohibido: borrar, "
             "cambiar contraseña, crear dispositivos (403)."],
        ], [1.8 * cm, 1.8 * cm, 5.2 * cm, W - 8.8 * cm]),
        Spacer(1, 6),
        P("Claims de cada token:", "h3"),
        code('''{
  "sub":  "9342f8b7-3eda-4b8c-938b-1e22b4c91022",   # id del usuario
  "type": "access",                                 # access | refresh | device
  "jti":  "99264497b6bc4e2c...",                    # id único del token
  "iss":  "finanzas-esp",                           # emisor (se valida)
  "iat":  1793068631, "exp": 1793070431,            # emitido / expira
  "role": "user"                                    # solo access; device lleva "dev"
}'''),
        P("El claim <font face='Consolas'>type</font> evita la confusión de tokens: un refresh token presentado como "
          "Bearer es rechazado, y uno de dispositivo no sirve en rutas exclusivas del usuario."),
        P("Rotación de refresh tokens y detección de robo", "h3"),
        P("El access token es corto para limitar el daño si se filtra. El refresh token dura más, por lo que se protege "
          "con <b>rotación</b>: cada vez que se usa se revoca y se emite uno nuevo. Si alguien presenta un refresh ya "
          "revocado significa que hay dos copias del token (la del usuario y la de un atacante), así que la API revoca "
          "<b>todas</b> las sesiones del usuario."),
        token_flow_diagram(),
        caption("Figura 3. Rotación de refresh tokens con detección de reutilización."),
        *bullets([
            "<b>Logout</b> revoca el refresh token (idempotente).",
            "<b>Cambiar la contraseña</b> revoca todos los refresh tokens: se cierran las sesiones en otros equipos.",
            "<b>Revocar un ESP32</b> invalida su token de inmediato: la dependencia comprueba "
            "<font face='Consolas'>device.is_active</font> en cada petición.",
            "Usuario inactivo: 403 aunque el token tenga firma válida.",
        ]),
        PageBreak(),
    ]

    sample = ROOT / "samples" / "ticket_ejemplo.jpg"
    story += [
        P("2.7 Almacenamiento con MinIO", "h2"),
        P("Los archivos binarios (fotos y PDF de tickets, avatares) no se guardan en PostgreSQL: inflarían la base de "
          "datos, harían lentos los respaldos y no se pueden servir con URLs directas. Se usa <b>MinIO</b>, un "
          "almacenamiento de objetos compatible con la API de Amazon S3, en el contenedor "
          "<font face='Consolas'>chainguard/minio</font> (usuario nonroot y bind mount, como en las prácticas anteriores)."),
        P("Organización de llaves", "h3"),
        code('''finanzas-esp/                              (bucket, se crea al iniciar la API)
└── users/<user_id>/
    ├── avatar/avatar.jpg
    └── tickets/2026/10/<ticket_id>.jpg       (o .png / .webp / .pdf)'''),
        P("Todo lo de un usuario cuelga de su prefijo, así borrar la cuenta es un solo "
          "<font face='Consolas'>delete_prefix</font>. Agrupar por año/mes facilita respaldos y reportes."),
        P("Medidas implementadas", "h3"),
        *bullets([
            "<b>Validación por magic bytes</b>: se lee la firma binaria del archivo (FF D8 FF = JPEG, 89 50 4E 47 = PNG, "
            "RIFF..WEBP, %PDF-). Un .exe renombrado a .jpg se rechaza con 415 aunque el cliente diga image/jpeg.",
            "<b>Límite de tamaño</b> configurable (5 MB): se leen como máximo 5 MB + 1 byte y se responde 413.",
            "<b>Duplicados</b>: SHA-256 del contenido + UNIQUE(user_id, image_sha256) -> 409 si se sube el mismo ticket.",
            "<b>Consistencia</b>: primero se sube a MinIO y luego se guarda en BD; si la BD falla, se borra el objeto "
            "(compensación) para no dejar huérfanos.",
            "<b>URLs prefirmadas</b> de 15 minutos: el navegador descarga directo de MinIO sin pasar por la API y sin "
            "hacer público el bucket. Se firman con <font face='Consolas'>MINIO_PUBLIC_ENDPOINT</font> para que funcionen "
            "también desde el ESP32 en la red local.",
            "<b>Streaming</b>: GET /tickets/{id}/image entrega el archivo en bloques de 32 KB para clientes que no "
            "alcanzan MinIO.",
            "<b>Aislamiento</b>: un usuario que pide el ticket de otro recibe 404 (no se revela que existe).",
            "<b>Tolerancia a fallos</b>: si MinIO no responde la API sigue arriba; /health informa "
            "<font face='Consolas'>storage: error</font> y los endpoints de archivos responden 503.",
        ]),
        KeepTogether([
            Image(str(sample), width=4.2 * cm, height=4.2 * cm * 560 / 360),
            caption("Figura 4. Ticket de ejemplo (samples/ticket_ejemplo.jpg) usado en las pruebas."),
        ]),
        PageBreak(),
    ]

    story += [
        P("2.8 Integración con el ESP32", "h2"),
        P("El dispositivo es un ESP32-S3 con <b>ESP-Claw</b>, el firmware de agente de Espressif. En lugar de programar "
          "en C, se le entrega un archivo <font face='Consolas'>SKILL.md</font> que describe en lenguaje natural qué "
          "endpoints llamar con su herramienta <font face='Consolas'>http_request</font>."),
        P("Por seguridad, el ESP32 <b>no usa la contraseña del usuario</b>. El flujo es:"),
        *bullets([
            "En el panel web el usuario vincula un dispositivo y recibe una llave <font face='Consolas'>fesp_...</font> "
            "(se muestra una sola vez; en la BD queda su SHA-256).",
            "La llave se pega en el SKILL.md. El ESP32 la cambia por un JWT de tipo <i>device</i> de 60 minutos.",
            "Con ese token sube tickets en JSON/base64 (POST /tickets/base64), porque http_request no puede armar "
            "multipart con bytes binarios. Los tickets quedan con source=esp32 y el device_id.",
            "Si el ESP32 se pierde, el usuario lo revoca desde el panel y deja de funcionar al instante.",
        ], numbered=True),
        P("Limitación conocida: el base64 debe ir completo dentro del cuerpo, por lo que desde el ESP32 solo es práctico "
          "subir imágenes pequeñas (la muestra de 180×280 px pesa 6 KB). Para fotos grandes la v02 añadirá la ruta por "
          "Telegram ya probada en el proyecto MiniBot (el ESP envía la referencia y el servidor descarga la foto)."),
        P("2.9 Modelos de inteligencia artificial", "h2"),
        P("La IA no forma parte del alcance de la v01, pero el esquema ya está preparado para ella "
          "(<font face='Consolas'>status</font>, <font face='Consolas'>ocr_raw_text</font>, "
          "<font face='Consolas'>ai_model</font>, <font face='Consolas'>ai_confidence</font>, "
          "<font face='Consolas'>ticket_items</font>, <font face='Consolas'>categories</font>). Modelos seleccionados:"),
        table([
            ["Modelo", "Tarea", "Justificación"],
            ["Gemini 2.5 Flash (multimodal)", "Leer la imagen del ticket y devolver JSON: tienda, fecha, total, productos, "
             "cantidades y precios.", "Lee la imagen directamente (sin OCR separado), maneja tickets arrugados o "
             "inclinados, admite salida estructurada con esquema JSON y su costo por imagen es muy bajo. Ya se usó en "
             "proyectos previos del curso."],
            ["Tesseract OCR + LLM de texto (Granite / Gemini)", "Respaldo cuando no hay API multimodal.",
             "Tesseract es gratuito y local; el LLM convierte el texto ruidoso del OCR en JSON. El texto queda en "
             "ocr_raw_text para auditoría."],
            ["LLM clasificador", "Asignar cada producto a una categoría.", "Los tickets usan abreviaturas "
             "(\"LCHE ENT 1L\"); un LLM las entiende mejor que reglas por palabra clave. Se le pasa la lista de "
             "categorías de la BD para que solo elija entre ellas."],
            ["Agente LLM de ESP-Claw", "Interpretar lo que el usuario pide en el chat del ESP32.", "Permite "
             "\"sube este ticket\" o \"¿cuánto gasté?\" sin interfaz gráfica; el SKILL.md acota qué puede hacer."],
        ], [3.6 * cm, 4.4 * cm, W - 8 * cm]),
        Spacer(1, 6),
        P("Flujo previsto (v02): ticket <i>pendiente</i> -> <i>procesando</i> -> el modelo devuelve JSON validado con "
          "Pydantic -> se crean los <font face='Consolas'>ticket_items</font> -> <i>procesado</i>. Si la confianza es baja "
          "o el JSON no valida, el ticket queda en <i>error</i> para captura manual. Así la IA nunca escribe datos sin "
          "validar en la base de datos."),
        PageBreak(),
    ]

    story += [
        P("2.10 Entorno, pruebas y evidencias", "h2"),
        P("El proyecto usa un <b>entorno virtual</b> (<font face='Consolas'>.venv</font>) con dependencias fijadas por "
          "rango en <font face='Consolas'>requirements.txt</font> (y <font face='Consolas'>requirements-dev.txt</font> para "
          "pruebas y este PDF). Los secretos viven en <font face='Consolas'>.env</font>, excluido de git; el repositorio "
          "incluye <font face='Consolas'>.env.example</font>. El script <font face='Consolas'>iniciar.ps1</font> crea el "
          "venv, el .env con una SECRET_KEY nueva, levanta Docker, aplica migraciones y arranca uvicorn con "
          "<font face='Consolas'>--host 0.0.0.0</font> para que el ESP32 alcance el servidor."),
        P("Pruebas automatizadas (pytest)", "h3"),
        code(read("evidencia_pytest.txt")),
        P("Flujo completo contra PostgreSQL y MinIO reales (scripts/demo_flujo.py)", "h3"),
        code(read("evidencia_demo.txt")),
        P("Estado en la base de datos", "h3"),
        P("Se observa que solo se guarda el hash Argon2id, que los refresh tokens usados quedaron revocados por la "
          "rotación y la detección de reutilización, que de los dispositivos solo se conserva el SHA-256 de la llave, "
          "y que los tickets apuntan a llaves de MinIO."),
        code(read("evidencia_bd.txt")),
        PageBreak(),
    ]

    story += [
        P("2.11 Repositorio y rama v01", "h2"),
        P("El código está en GitHub. El trabajo de este entregable vive en la rama <b>v01</b>; cada entregable "
          "posterior tendrá su propia rama (v02, v03) para poder revisar la evolución del proyecto."),
        code('''git init
git checkout -b v01
git add .
git commit -m "v01: modelo User, hasheo Argon2id, tokens JWT y MinIO"
git remote add origin https://github.com/<usuario>/FinanzasESP.git
git push -u origin v01'''),
        P("Quedan fuera del repositorio (.gitignore): <font face='Consolas'>.venv/</font>, <font face='Consolas'>.env</font>, "
          "<font face='Consolas'>minio_data/</font>, bases SQLite y cachés de Python."),
        Spacer(1, 10),
        P("3. Conclusión", "h1"),
        P("La v01 de FinanzasESP deja lista la base sobre la que se construirá el control de finanzas: una identidad de "
          "usuario sólida, contraseñas protegidas con el algoritmo recomendado actualmente, un sistema de tokens que "
          "distingue entre personas y dispositivos, y un almacenamiento de archivos escalable e independiente de la base "
          "de datos."),
        P("Las decisiones se tomaron pensando en riesgos reales y no solo en que \"funcione\": Argon2id en lugar de "
          "bcrypt o SHA-256 por su resistencia a GPU; refresh tokens con rotación y detección de reutilización para "
          "limitar el daño de un token robado; llaves propias y permisos reducidos para el ESP32 en lugar de compartir "
          "la contraseña; validación del contenido real de los archivos y URLs prefirmadas en lugar de un bucket "
          "público. Todo está respaldado por 22 pruebas automatizadas y por una demostración completa contra "
          "PostgreSQL y MinIO en Docker."),
        P("El modelo de datos ya contempla productos, categorías y la trazabilidad de la IA, por lo que la v02 "
          "puede concentrarse en integrar Gemini para leer los tickets sin modificar lo construido. Con eso, la v03 "
          "podrá ofrecer el objetivo final: ver en qué se gasta, cómo cambian los precios y si se respeta el "
          "presupuesto, consultable incluso desde el ESP32."),
        Spacer(1, 10),
        P("Referencias", "h2"),
        *bullets([
            "OWASP. <i>Password Storage Cheat Sheet</i>. cheatsheetseries.owasp.org",
            "Biryukov, A., Dinu, D., Khovratovich, D. (2016). <i>Argon2: the memory-hard function for password hashing</i>. RFC 9106.",
            "Jones, M., Bradley, J., Sakimura, N. (2015). <i>JSON Web Token (JWT)</i>. RFC 7519.",
            "OWASP. <i>JSON Web Token Cheat Sheet</i> y <i>OAuth 2.0 Security Best Current Practice</i> (rotación de refresh tokens).",
            "FastAPI. <i>Security — OAuth2 with Password (and hashing), Bearer with JWT tokens</i>. fastapi.tiangolo.com",
            "SQLModel. <i>Documentation</i>. sqlmodel.tiangolo.com",
            "MinIO. <i>Python Client API Reference</i> y <i>Presigned URLs</i>. min.io/docs",
            "Espressif. <i>ESP-Claw</i>: capacidades cap_http_request y skills. github.com/espressif/esp-claw",
            "Google. <i>Gemini API — Image understanding and structured output</i>. ai.google.dev",
        ]),
    ]

    doc = SimpleDocTemplate(
        str(OUT), pagesize=letter,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2.2 * cm,
        title="FinanzasESP — Entregable v01", author="Owen Morales",
        subject="Modelo User, Hasheo, Token y MinIO",
    )
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF generado: {OUT}")


if __name__ == "__main__":
    build()
