from enum import Enum


class UserRole(str, Enum):
    user = "user"
    admin = "admin"


class TicketStatus(str, Enum):
    pendiente = "pendiente"      # imagen en MinIO, falta extraer datos
    procesando = "procesando"    # el modelo de IA lo está leyendo
    procesado = "procesado"      # tienda, fecha, total y productos guardados
    error = "error"              # la IA no pudo leerlo; requiere captura manual


class TicketSource(str, Enum):
    web = "web"
    esp32 = "esp32"
    api = "api"
