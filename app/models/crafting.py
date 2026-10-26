from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.item import ItemTemplate


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CraftingRecipe(Base):
    __tablename__ = "crafting_recipes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output_item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False, index=True)
    output_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    gold_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required_blacksmith_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    output_item_template: Mapped["ItemTemplate"] = relationship(back_populates="crafting_outputs")
    materials: Mapped[list["CraftingRecipeMaterial"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )


class CraftingRecipeMaterial(Base):
    __tablename__ = "crafting_recipe_materials"
    __table_args__ = (UniqueConstraint("recipe_id", "item_template_id", name="uq_recipe_material"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("crafting_recipes.id"), nullable=False, index=True)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    recipe: Mapped[CraftingRecipe] = relationship(back_populates="materials")
    item_template: Mapped["ItemTemplate"] = relationship(back_populates="crafting_materials")
