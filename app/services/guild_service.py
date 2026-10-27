from sqlalchemy.orm import Session

from sqlalchemy import select

from app.models.campaign import CampaignMetadata
from app.models.guild import Guild, GuildResources
from app.repositories.guild_repository import (
    create_guild_for_user,
    get_guild_by_user_id,
    get_resources_by_guild_id,
)
from app.repositories.item_repository import sync_inventory_resource_totals


class GuildCreationError(ValueError):
    pass


def create_initial_guild(db: Session, user_id: int | str, guild_name: str) -> Guild:
    guild_name = guild_name.strip()
    if not guild_name:
        raise GuildCreationError("Nome da guilda e obrigatorio.")
    existing_guild = (
        db.scalar(select(Guild).where(Guild.campaign_id == user_id))
        if isinstance(user_id, str)
        else get_guild_by_user_id(db, user_id)
    )
    if existing_guild:
        raise GuildCreationError("Este usuario ja possui uma guilda.")
    if isinstance(user_id, str):
        guild = Guild(campaign_id=user_id, name=guild_name, level=1, reputation=0)
        db.add(guild)
        db.flush()
        resources = GuildResources(guild_id=guild.id, gold=100, wood=0, ore=0, crystals=0)
        db.add(resources)
        db.commit()
        db.refresh(guild)
        return guild
    return create_guild_for_user(db, user_id=user_id, name=guild_name)


def get_current_guild_context(db: Session, user_id: int | str) -> tuple[Guild | None, GuildResources | None]:
    guild = (
        db.scalar(select(Guild).where(Guild.campaign_id == user_id))
        if isinstance(user_id, str)
        else get_guild_by_user_id(db, user_id)
    )
    if guild is None:
        return None, None
    resources = get_resources_by_guild_id(db, guild.id)
    if resources is not None and sync_inventory_resource_totals(db, resources):
        db.commit()
        db.refresh(resources)
    return guild, resources
