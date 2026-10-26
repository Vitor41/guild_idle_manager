from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.dungeon import DungeonTemplate
    from app.models.guild import Guild
    from app.models.mercenary import Mercenary
    from app.models.mission import MissionTemplate
    from app.models.market import MarketSale
    from app.models.crafting import CraftingRecipe, CraftingRecipeMaterial


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ItemTemplate(Base):
    __tablename__ = "item_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(180), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    item_type: Mapped[str] = mapped_column(String(40), nullable=False)
    rarity: Mapped[str] = mapped_column(String(40), nullable=False)
    item_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    level_band: Mapped[str] = mapped_column(String(20), nullable=False, default="1-20", index=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_pack: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    material_family: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    favored_class_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    favored_attribute: Mapped[str | None] = mapped_column(String(30), nullable=True)
    base_sell_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    equipment_slot: Mapped[str | None] = mapped_column(String(30), nullable=True)
    icon_group: Mapped[str | None] = mapped_column(String(60), nullable=True)
    required_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    bonus_power: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_vitality: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_agility: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_intelligence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_luck: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_armor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rng_bonus_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rng_bonus_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    inventory_items: Mapped[list["GuildInventoryItem"]] = relationship(back_populates="item_template")
    item_instances: Mapped[list["GuildItemInstance"]] = relationship(back_populates="item_template")
    mission_drops: Mapped[list["MissionTemplateItemDrop"]] = relationship(back_populates="item_template")
    dungeon_drops: Mapped[list["DungeonTemplateItemDrop"]] = relationship(back_populates="item_template")
    market_sales: Mapped[list["MarketSale"]] = relationship(back_populates="item_template")
    crafting_outputs: Mapped[list["CraftingRecipe"]] = relationship(back_populates="output_item_template")
    crafting_materials: Mapped[list["CraftingRecipeMaterial"]] = relationship(back_populates="item_template")


class GuildInventoryItem(Base):
    __tablename__ = "guild_inventory_items"
    __table_args__ = (
        UniqueConstraint("guild_id", "item_template_id", name="uq_guild_inventory_item"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    guild: Mapped["Guild"] = relationship(back_populates="inventory_items")
    item_template: Mapped[ItemTemplate] = relationship(back_populates="inventory_items")


class GuildItemInstance(Base):
    __tablename__ = "guild_item_instances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False, index=True)
    equipped_to_mercenary_id: Mapped[int | None] = mapped_column(ForeignKey("mercenaries.id"), nullable=True, index=True)
    equipment_slot: Mapped[str] = mapped_column(String(30), nullable=False)
    required_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    bonus_power: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_vitality: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_agility: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_intelligence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_luck: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_armor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rng_bonus_attribute: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rng_bonus_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    upgrade_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    guild: Mapped["Guild"] = relationship(back_populates="item_instances")
    item_template: Mapped[ItemTemplate] = relationship(back_populates="item_instances")
    equipped_to_mercenary: Mapped["Mercenary | None"] = relationship(back_populates="equipment_instances")
    market_sale: Mapped["MarketSale | None"] = relationship(back_populates="item_instance", uselist=False)


class MissionTemplateItemDrop(Base):
    __tablename__ = "mission_template_item_drops"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    mission_template_id: Mapped[int] = mapped_column(ForeignKey("mission_templates.id"), nullable=False, index=True)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False, index=True)
    drop_chance: Mapped[int] = mapped_column(Integer, nullable=False)
    min_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    max_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    mission_template: Mapped["MissionTemplate"] = relationship(back_populates="item_drops")
    item_template: Mapped[ItemTemplate] = relationship(back_populates="mission_drops")


class DungeonTemplateItemDrop(Base):
    __tablename__ = "dungeon_template_item_drops"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dungeon_template_id: Mapped[int] = mapped_column(ForeignKey("dungeon_templates.id"), nullable=False, index=True)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False, index=True)
    drop_chance: Mapped[int] = mapped_column(Integer, nullable=False)
    min_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    max_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    dungeon_template: Mapped["DungeonTemplate"] = relationship(back_populates="item_drops")
    item_template: Mapped[ItemTemplate] = relationship(back_populates="dungeon_drops")
