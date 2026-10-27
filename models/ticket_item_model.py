import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.category_model import Category
    from models.ticket_model import Ticket


class TicketItem(SQLModel, table=True):
    """Renglón del ticket: producto, cantidad y precios. Base de las gráficas de gasto."""

    __tablename__ = "ticket_items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="tickets.id", index=True, ondelete="CASCADE")
    category_id: uuid.UUID | None = Field(
        default=None, foreign_key="categories.id", index=True, ondelete="SET NULL"
    )
    description: str = Field(max_length=200)
    quantity: Decimal = Field(default=Decimal("1"), max_digits=10, decimal_places=3)
    unit_price: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    total_price: Decimal = Field(max_digits=12, decimal_places=2)

    ticket: "Ticket" = Relationship(back_populates="items")
    category: "Category" = Relationship(back_populates="items")
