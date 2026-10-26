from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.guild import GuildResources
from app.models.mercenary import Mercenary, MercenaryClass


def list_active_mercenary_classes(db: Session) -> list[MercenaryClass]:
    return list(
        db.scalars(
            select(MercenaryClass)
            .where(MercenaryClass.is_active.is_(True))
            .order_by(MercenaryClass.name)
        )
    )


def get_active_mercenary_class(db: Session, class_id: int) -> MercenaryClass | None:
    return db.scalar(
        select(MercenaryClass).where(
            MercenaryClass.id == class_id,
            MercenaryClass.is_active.is_(True),
        )
    )


def get_mercenary_class_by_name(db: Session, name: str) -> MercenaryClass | None:
    return db.scalar(select(MercenaryClass).where(MercenaryClass.name == name))


def get_mercenary_class_by_code(db: Session, code: str) -> MercenaryClass | None:
    return db.scalar(select(MercenaryClass).where(MercenaryClass.code == code))


def create_mercenary_class(db: Session, data: dict[str, object]) -> MercenaryClass:
    mercenary_class = MercenaryClass(**data)
    db.add(mercenary_class)
    return mercenary_class


def list_mercenaries_by_guild(db: Session, guild_id: int) -> list[Mercenary]:
    return list(
        db.scalars(
            select(Mercenary)
            .options(joinedload(Mercenary.mercenary_class))
            .where(Mercenary.guild_id == guild_id, Mercenary.status != "dismissed")
            .order_by(Mercenary.id)
        )
    )


def get_mercenary_by_guild(db: Session, guild_id: int, mercenary_id: int) -> Mercenary | None:
    return db.scalar(
        select(Mercenary)
        .options(joinedload(Mercenary.mercenary_class))
        .where(
            Mercenary.id == mercenary_id,
            Mercenary.guild_id == guild_id,
            Mercenary.status != "dismissed",
        )
    )


def list_available_mercenaries_by_ids(
    db: Session,
    guild_id: int,
    mercenary_ids: list[int],
) -> list[Mercenary]:
    if not mercenary_ids:
        return []
    return list(
        db.scalars(
            select(Mercenary)
            .options(joinedload(Mercenary.mercenary_class))
            .where(
                Mercenary.guild_id == guild_id,
                Mercenary.id.in_(mercenary_ids),
                Mercenary.status == "available",
            )
            .order_by(Mercenary.id)
        )
    )


def create_mercenary(
    db: Session,
    guild_id: int,
    mercenary_class: MercenaryClass,
    name: str,
    level: int = 1,
    xp: int = 0,
    status: str = "available",
    rarity: str = "common",
    power: int | None = None,
    vitality: int | None = None,
    agility: int | None = None,
    intelligence: int | None = None,
    luck: int | None = None,
    hire_cost: int = 0,
) -> Mercenary:
    mercenary = Mercenary(
        guild_id=guild_id,
        class_id=mercenary_class.id,
        name=name,
        level=level,
        xp=xp,
        status=status,
        rarity=rarity,
        hire_cost=hire_cost,
        power=mercenary_class.base_power if power is None else power,
        vitality=mercenary_class.base_vitality if vitality is None else vitality,
        agility=mercenary_class.base_agility if agility is None else agility,
        intelligence=mercenary_class.base_intelligence if intelligence is None else intelligence,
        luck=mercenary_class.base_luck if luck is None else luck,
    )
    db.add(mercenary)
    return mercenary


def count_mercenaries_by_guild(db: Session, guild_id: int) -> int:
    return (
        db.scalar(
            select(func.count(Mercenary.id)).where(
                Mercenary.guild_id == guild_id,
                Mercenary.status != "dismissed",
            )
        )
        or 0
    )


def list_active_mercenary_names_by_guild(db: Session, guild_id: int) -> list[str]:
    return list(
        db.scalars(
            select(Mercenary.name).where(
                Mercenary.guild_id == guild_id,
                Mercenary.status != "dismissed",
            )
        )
    )


def count_mercenaries_by_status(db: Session, guild_id: int, status: str) -> int:
    return (
        db.scalar(
            select(func.count(Mercenary.id)).where(
                Mercenary.guild_id == guild_id,
                Mercenary.status == status,
            )
        )
        or 0
    )


def spend_gold(resources: GuildResources, amount: int) -> None:
    resources.gold -= amount
