from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.building import BuildingTemplate, GuildBuilding


def count_building_templates(db: Session) -> int:
    return db.scalar(select(func.count(BuildingTemplate.id))) or 0


def list_building_templates(db: Session) -> list[BuildingTemplate]:
    return list(db.scalars(select(BuildingTemplate).order_by(BuildingTemplate.id)))


def list_active_building_templates(db: Session) -> list[BuildingTemplate]:
    return list(
        db.scalars(
            select(BuildingTemplate)
            .where(BuildingTemplate.is_active.is_(True))
            .order_by(BuildingTemplate.id)
        )
    )


def get_building_template(db: Session, template_id: int) -> BuildingTemplate | None:
    return db.get(BuildingTemplate, template_id)


def get_building_template_by_name(db: Session, name: str) -> BuildingTemplate | None:
    return db.scalar(select(BuildingTemplate).where(BuildingTemplate.name == name))


def create_building_template(db: Session, data: dict[str, object]) -> BuildingTemplate:
    template = BuildingTemplate(**data)
    db.add(template)
    return template


def list_guild_buildings(db: Session, guild_id: int) -> list[GuildBuilding]:
    return list(
        db.scalars(
            select(GuildBuilding)
            .options(joinedload(GuildBuilding.building_template))
            .where(GuildBuilding.guild_id == guild_id)
            .order_by(GuildBuilding.id)
        )
    )


def get_guild_building(db: Session, guild_id: int, building_id: int) -> GuildBuilding | None:
    return db.scalar(
        select(GuildBuilding)
        .options(joinedload(GuildBuilding.building_template))
        .where(GuildBuilding.id == building_id, GuildBuilding.guild_id == guild_id)
    )


def get_guild_building_by_effect(db: Session, guild_id: int, effect_type: str) -> GuildBuilding | None:
    return db.scalar(
        select(GuildBuilding)
        .join(GuildBuilding.building_template)
        .options(joinedload(GuildBuilding.building_template))
        .where(
            GuildBuilding.guild_id == guild_id,
            BuildingTemplate.effect_type == effect_type,
        )
    )


def get_guild_building_by_template(db: Session, guild_id: int, template_id: int) -> GuildBuilding | None:
    return db.scalar(
        select(GuildBuilding).where(
            GuildBuilding.guild_id == guild_id,
            GuildBuilding.building_template_id == template_id,
        )
    )


def create_guild_building(db: Session, guild_id: int, template_id: int) -> GuildBuilding:
    building = GuildBuilding(guild_id=guild_id, building_template_id=template_id, level=0)
    db.add(building)
    return building
