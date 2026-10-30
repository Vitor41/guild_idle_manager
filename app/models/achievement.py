from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from app.models.guild import Guild
    from app.models.item import ItemTemplate


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AchievementTemplate(Base):
    __tablename__ = "achievement_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    criterion_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reward_gold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reward_item_template_id: Mapped[int | None] = mapped_column(ForeignKey("item_templates.id"), nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    guild_achievements: Mapped[list["GuildAchievement"]] = relationship(back_populates="achievement_template")
    reward_item_template: Mapped["ItemTemplate | None"] = relationship()


class GuildAchievement(Base):
    __tablename__ = "guild_achievements"
    __table_args__ = (UniqueConstraint("guild_id", "achievement_template_id", name="uq_guild_achievement"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    achievement_template_id: Mapped[int] = mapped_column(ForeignKey("achievement_templates.id"), nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    guild: Mapped["Guild"] = relationship(back_populates="achievements")
    achievement_template: Mapped[AchievementTemplate] = relationship(back_populates="guild_achievements")


class CodexEntry(Base):
    __tablename__ = "codex_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reference_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rarity: Mapped[str] = mapped_column(String(30), nullable=False, default="common")

    guild_unlocks: Mapped[list["GuildCodexUnlock"]] = relationship(back_populates="codex_entry")


class GuildCodexUnlock(Base):
    __tablename__ = "guild_codex_unlocks"
    __table_args__ = (UniqueConstraint("guild_id", "codex_entry_id", name="uq_guild_codex_unlock"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    codex_entry_id: Mapped[int] = mapped_column(ForeignKey("codex_entries.id"), nullable=False, index=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="codex_unlocks")
    codex_entry: Mapped[CodexEntry] = relationship(back_populates="guild_unlocks")


class GuildStat(Base):
    __tablename__ = "guild_stats"
    __table_args__ = (UniqueConstraint("guild_id", "key", name="uq_guild_stat"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    guild: Mapped["Guild"] = relationship(back_populates="stats")
