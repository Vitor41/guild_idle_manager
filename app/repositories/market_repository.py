from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.market import GuildActivity, MarketSale


def get_guild_activity(db: Session, guild_id: int) -> GuildActivity | None:
    return db.scalar(select(GuildActivity).where(GuildActivity.guild_id == guild_id))


def create_guild_activity(db: Session, guild_id: int) -> GuildActivity:
    activity = GuildActivity(guild_id=guild_id)
    db.add(activity)
    return activity


def create_market_sale(db: Session, data: dict[str, object]) -> MarketSale:
    sale = MarketSale(**data)
    db.add(sale)
    return sale


def get_market_sale_by_guild(db: Session, guild_id: int, sale_id: int) -> MarketSale | None:
    return db.scalar(
        select(MarketSale)
        .options(joinedload(MarketSale.item_template), joinedload(MarketSale.item_instance))
        .where(MarketSale.id == sale_id, MarketSale.guild_id == guild_id)
    )


def list_market_sales_by_guild(db: Session, guild_id: int) -> list[MarketSale]:
    return list(
        db.scalars(
            select(MarketSale)
            .options(joinedload(MarketSale.item_template), joinedload(MarketSale.item_instance))
            .where(MarketSale.guild_id == guild_id)
            .order_by(MarketSale.id.desc())
        )
    )


def count_active_market_sales(db: Session, guild_id: int) -> int:
    return db.scalar(
        select(func.count(MarketSale.id)).where(
            MarketSale.guild_id == guild_id,
            MarketSale.status == "in_progress",
        )
    ) or 0
