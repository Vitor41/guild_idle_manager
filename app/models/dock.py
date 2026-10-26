from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MerchantTemplate(Base):
    __tablename__ = "merchant_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    merchant_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    min_dock_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rotation_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    content_pack: Mapped[str] = mapped_column(String(80), nullable=False, default="massivo_v1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    offer_templates: Mapped[list["MerchantOfferTemplate"]] = relationship(back_populates="merchant")


class MerchantOfferTemplate(Base):
    __tablename__ = "merchant_offer_templates"
    __table_args__ = (UniqueConstraint("merchant_template_id", "item_template_id", name="uq_merchant_item_offer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_template_id: Mapped[int] = mapped_column(ForeignKey("merchant_templates.id"), nullable=False, index=True)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False, index=True)
    base_price: Mapped[int] = mapped_column(Integer, nullable=False)
    min_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    min_dock_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    merchant: Mapped[MerchantTemplate] = relationship(back_populates="offer_templates")
    item_template = relationship("ItemTemplate")


class DockRotation(Base):
    __tablename__ = "dock_rotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    merchants: Mapped[list["DockRotationMerchant"]] = relationship(back_populates="rotation", cascade="all, delete-orphan")


class DockRotationMerchant(Base):
    __tablename__ = "dock_rotation_merchants"
    __table_args__ = (UniqueConstraint("dock_rotation_id", "slot", name="uq_dock_rotation_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dock_rotation_id: Mapped[int] = mapped_column(ForeignKey("dock_rotations.id"), nullable=False, index=True)
    merchant_template_id: Mapped[int] = mapped_column(ForeignKey("merchant_templates.id"), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    rotation: Mapped[DockRotation] = relationship(back_populates="merchants")
    merchant: Mapped[MerchantTemplate] = relationship()
    offers: Mapped[list["DockOffer"]] = relationship(back_populates="rotation_merchant", cascade="all, delete-orphan")


class DockOffer(Base):
    __tablename__ = "dock_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    dock_rotation_merchant_id: Mapped[int] = mapped_column(ForeignKey("dock_rotation_merchants.id"), nullable=False, index=True)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    initial_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    rotation_merchant: Mapped[DockRotationMerchant] = relationship(back_populates="offers")
    item_template = relationship("ItemTemplate")
