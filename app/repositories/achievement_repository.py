from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.achievement import AchievementTemplate, CodexEntry, GuildAchievement, GuildCodexUnlock, GuildStat


def get_achievement_by_key(db: Session, key: str) -> AchievementTemplate | None:
    return db.scalar(select(AchievementTemplate).where(AchievementTemplate.key == key))


def list_active_achievements(db: Session) -> list[AchievementTemplate]:
    return list(db.scalars(select(AchievementTemplate).where(AchievementTemplate.is_active.is_(True)).order_by(AchievementTemplate.id)))


def get_guild_achievement(db: Session, guild_id: int, template_id: int) -> GuildAchievement | None:
    return db.scalar(select(GuildAchievement).where(
        GuildAchievement.guild_id == guild_id, GuildAchievement.achievement_template_id == template_id
    ))


def list_guild_achievements(db: Session, guild_id: int) -> list[GuildAchievement]:
    return list(db.scalars(select(GuildAchievement).options(joinedload(GuildAchievement.achievement_template)).where(
        GuildAchievement.guild_id == guild_id
    ).order_by(GuildAchievement.id)))


def get_codex_entry_by_key(db: Session, key: str) -> CodexEntry | None:
    return db.scalar(select(CodexEntry).where(CodexEntry.key == key))


def list_codex_entries(db: Session) -> list[CodexEntry]:
    return list(db.scalars(select(CodexEntry).order_by(CodexEntry.category, CodexEntry.title)))


def get_codex_unlock(db: Session, guild_id: int, entry_id: int) -> GuildCodexUnlock | None:
    return db.scalar(select(GuildCodexUnlock).where(
        GuildCodexUnlock.guild_id == guild_id, GuildCodexUnlock.codex_entry_id == entry_id
    ))


def list_codex_unlocks(db: Session, guild_id: int) -> list[GuildCodexUnlock]:
    return list(db.scalars(select(GuildCodexUnlock).options(joinedload(GuildCodexUnlock.codex_entry)).where(
        GuildCodexUnlock.guild_id == guild_id
    )))


def get_guild_stat(db: Session, guild_id: int, key: str) -> GuildStat | None:
    return db.scalar(select(GuildStat).where(GuildStat.guild_id == guild_id, GuildStat.key == key))
