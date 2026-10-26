from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.guild import Guild, GuildResources


def get_guild_by_user_id(db: Session, user_id: int) -> Guild | None:
    return db.scalar(select(Guild).where(Guild.user_id == user_id))


def create_guild_for_user(db: Session, user_id: int, name: str) -> Guild:
    guild = Guild(user_id=user_id, name=name, level=1, reputation=0)
    db.add(guild)
    db.flush()

    resources = GuildResources(
        guild_id=guild.id,
        gold=100,
        wood=0,
        ore=0,
        crystals=0,
    )
    db.add(resources)
    db.commit()
    db.refresh(guild)
    return guild


def get_resources_by_guild_id(db: Session, guild_id: int) -> GuildResources | None:
    return db.scalar(select(GuildResources).where(GuildResources.guild_id == guild_id))

