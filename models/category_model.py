import uuid
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from models.ticket_item_model import TicketItem


class Category(SQLModel, table=True):
    """
    Categoría de gasto (Despensa, Transporte, Salud...).
    user_id NULL = categoría global del sistema; con valor = categoría propia del usuario.
    """

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_category_user_name"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", index=True, ondelete="CASCADE"
    )
    name: str = Field(max_length=60)
    color: str = Field(default="#64748b", max_length=7)

    items: list["TicketItem"] = Relationship(back_populates="category")
