from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.models.tavern import GuildTavernState, TavernConfig, TavernSpecialOffer


def get_tavern_config(db: Session) -> TavernConfig | None:
    return db.scalar(select(TavernConfig).order_by(TavernConfig.id).limit(1))


def create_tavern_config(db: Session) -> TavernConfig:
    config = TavernConfig()
    db.add(config)
    return config


def get_guild_tavern_state(db: Session, guild_id: int) -> GuildTavernState | None:
    return db.scalar(select(GuildTavernState).where(GuildTavernState.guild_id == guild_id))


def create_guild_tavern_state(
    db: Session,
    guild_id: int,
    apprentice_cost: int,
    next_special_check_at: datetime,
) -> GuildTavernState:
    state = GuildTavernState(
        guild_id=guild_id,
        current_apprentice_hire_cost=apprentice_cost,
        next_special_check_at=next_special_check_at,
    )
    db.add(state)
    return state


def get_active_special_offer(
    db: Session,
    guild_id: int,
    now: datetime,
) -> TavernSpecialOffer | None:
    return db.scalar(
        select(TavernSpecialOffer)
        .options(joinedload(TavernSpecialOffer.mercenary_class))
        .where(
            TavernSpecialOffer.guild_id == guild_id,
            TavernSpecialOffer.status == "active",
            TavernSpecialOffer.available_until > now,
        )
        .order_by(TavernSpecialOffer.available_until.desc())
        .limit(1)
    )


def list_special_offers_by_guild(db: Session, guild_id: int) -> list[TavernSpecialOffer]:
    return list(
        db.scalars(
            select(TavernSpecialOffer)
            .options(joinedload(TavernSpecialOffer.mercenary_class))
            .where(TavernSpecialOffer.guild_id == guild_id)
            .order_by(TavernSpecialOffer.id.desc())
        )
    )


def create_special_offer(db: Session, data: dict[str, object]) -> TavernSpecialOffer:
    offer = TavernSpecialOffer(**data)
    db.add(offer)
    return offer


def reset_all_special_checks(db: Session, next_check_at: datetime) -> None:
    db.execute(update(GuildTavernState).values(next_special_check_at=next_check_at))
