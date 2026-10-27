# Importar todos los modelos aquí registra las tablas en SQLModel.metadata
# (lo necesitan create_all y el autogenerate de Alembic).
from models.category_model import Category
from models.device_model import Device
from models.refresh_token_model import RefreshToken
from models.ticket_item_model import TicketItem
from models.ticket_model import Ticket
from models.user_model import User

__all__ = ["User", "RefreshToken", "Device", "Ticket", "TicketItem", "Category"]
