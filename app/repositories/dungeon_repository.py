from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.dungeon import DungeonRun, DungeonRunMember, DungeonTemplate
from app.models.item import DungeonTemplateItemDrop
from app.models.mercenary import Mercenary


def list_dungeon_templates(db: Session) -> list[DungeonTemplate]:
    return list(db.scalars(select(DungeonTemplate).order_by(DungeonTemplate.id)))


def list_active_dungeon_templates(db: Session) -> list[DungeonTemplate]:
    return list(
        db.scalars(
            select(DungeonTemplate)
            .where(DungeonTemplate.is_active.is_(True))
            .order_by(DungeonTemplate.id)
        )
    )


def list_active_dungeon_templates_for_band(db: Session, level_band: str) -> list[DungeonTemplate]:
    return list(db.scalars(
        select(DungeonTemplate)
        .options(selectinload(DungeonTemplate.item_drops).joinedload(DungeonTemplateItemDrop.item_template))
        .where(DungeonTemplate.is_active.is_(True), DungeonTemplate.level_band == level_band)
        .order_by(DungeonTemplate.id)
    ))


def get_dungeon_template(db: Session, template_id: int) -> DungeonTemplate | None:
    return db.get(DungeonTemplate, template_id)


def get_active_dungeon_template(db: Session, template_id: int) -> DungeonTemplate | None:
    return db.scalar(
        select(DungeonTemplate).where(
            DungeonTemplate.id == template_id,
            DungeonTemplate.is_active.is_(True),
        )
    )


def get_dungeon_template_by_name(db: Session, name: str) -> DungeonTemplate | None:
    return db.scalar(select(DungeonTemplate).where(DungeonTemplate.name == name))


def get_active_dungeon_run_for_template(
    db: Session,
    guild_id: int,
    dungeon_template_id: int,
) -> DungeonRun | None:
    return db.scalar(select(DungeonRun).where(
        DungeonRun.guild_id == guild_id,
        DungeonRun.dungeon_template_id == dungeon_template_id,
        DungeonRun.status == "in_progress",
    ).order_by(DungeonRun.id))


def create_dungeon_template(db: Session, data: dict[str, object]) -> DungeonTemplate:
    template = DungeonTemplate(**data)
    db.add(template)
    return template


def list_dungeon_runs_by_guild(db: Session, guild_id: int) -> list[DungeonRun]:
    return list(
        db.scalars(
            select(DungeonRun)
            .options(
                joinedload(DungeonRun.dungeon_template),
                joinedload(DungeonRun.members).joinedload(DungeonRunMember.mercenary),
            )
            .where(DungeonRun.guild_id == guild_id)
            .order_by(DungeonRun.id.desc())
        )
        .unique()
    )


def get_dungeon_run_by_guild(db: Session, guild_id: int, run_id: int) -> DungeonRun | None:
    return (
        db.scalars(
            select(DungeonRun)
            .options(
                joinedload(DungeonRun.dungeon_template),
                joinedload(DungeonRun.members).joinedload(DungeonRunMember.mercenary),
            )
            .where(DungeonRun.id == run_id, DungeonRun.guild_id == guild_id)
        )
        .unique()
        .one_or_none()
    )


def create_dungeon_run(
    db: Session,
    guild_id: int,
    dungeon_template_id: int,
    mercenaries: list[Mercenary],
    started_at: datetime,
    ends_at: datetime,
    run_multiplier: int = 1,
    *,
    commit: bool = True,
) -> DungeonRun:
    run = DungeonRun(
        guild_id=guild_id,
        dungeon_template_id=dungeon_template_id,
        status="in_progress",
        run_multiplier=run_multiplier,
        started_at=started_at,
        ends_at=ends_at,
    )
    db.add(run)
    db.flush()
    for mercenary in mercenaries:
        db.add(DungeonRunMember(dungeon_run_id=run.id, mercenary_id=mercenary.id))
        mercenary.status = "busy"
        db.add(mercenary)
    if commit:
        db.commit()
        db.refresh(run)
    else:
        db.flush()
    return run


def count_dungeon_runs_by_status(db: Session, guild_id: int, status: str) -> int:
    return db.scalar(
        select(func.count(DungeonRun.id)).where(
            DungeonRun.guild_id == guild_id,
            DungeonRun.status == status,
        )
    ) or 0


def count_awaiting_dungeon_loot(db: Session, guild_id: int, now: datetime) -> int:
    return db.scalar(
        select(func.count(DungeonRun.id)).where(
            DungeonRun.guild_id == guild_id,
            DungeonRun.status == "in_progress",
            DungeonRun.ends_at <= now,
        )
    ) or 0


def list_dungeon_drops(db: Session) -> list[DungeonTemplateItemDrop]:
    return list(
        db.scalars(
            select(DungeonTemplateItemDrop)
            .options(
                joinedload(DungeonTemplateItemDrop.dungeon_template),
                joinedload(DungeonTemplateItemDrop.item_template),
            )
            .order_by(DungeonTemplateItemDrop.id)
        )
    )


def list_active_drops_for_dungeon(db: Session, dungeon_template_id: int) -> list[DungeonTemplateItemDrop]:
    return list(
        db.scalars(
            select(DungeonTemplateItemDrop)
            .options(joinedload(DungeonTemplateItemDrop.item_template))
            .where(
                DungeonTemplateItemDrop.dungeon_template_id == dungeon_template_id,
                DungeonTemplateItemDrop.is_active.is_(True),
            )
            .order_by(DungeonTemplateItemDrop.id)
        )
    )


def get_dungeon_drop(db: Session, drop_id: int) -> DungeonTemplateItemDrop | None:
    return db.get(DungeonTemplateItemDrop, drop_id)


def get_dungeon_drop_by_pair(db: Session, dungeon_template_id: int, item_template_id: int) -> DungeonTemplateItemDrop | None:
    return db.scalar(
        select(DungeonTemplateItemDrop).where(
            DungeonTemplateItemDrop.dungeon_template_id == dungeon_template_id,
            DungeonTemplateItemDrop.item_template_id == item_template_id,
        )
    )


def create_dungeon_drop(db: Session, data: dict[str, object]) -> DungeonTemplateItemDrop:
    drop = DungeonTemplateItemDrop(**data)
    db.add(drop)
    return drop
