from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.class_change import ClassChangeRun, ClassTransitionOption


def get_transition_by_classes(
    db: Session,
    from_class_id: int,
    to_class_id: int,
) -> ClassTransitionOption | None:
    return db.scalar(
        select(ClassTransitionOption).where(
            ClassTransitionOption.from_class_id == from_class_id,
            ClassTransitionOption.to_class_id == to_class_id,
        )
    )


def list_active_transitions_for_class(
    db: Session,
    from_class_id: int,
) -> list[ClassTransitionOption]:
    return list(
        db.scalars(
            select(ClassTransitionOption)
            .options(
                joinedload(ClassTransitionOption.to_class),
                joinedload(ClassTransitionOption.from_class),
            )
            .where(
                ClassTransitionOption.from_class_id == from_class_id,
                ClassTransitionOption.is_active.is_(True),
            )
            .order_by(ClassTransitionOption.id)
        )
    )


def create_transition(db: Session, data: dict[str, object]) -> ClassTransitionOption:
    transition = ClassTransitionOption(**data)
    db.add(transition)
    return transition


def list_class_change_runs_by_guild(db: Session, guild_id: int) -> list[ClassChangeRun]:
    return list(
        db.scalars(
            select(ClassChangeRun)
            .options(
                joinedload(ClassChangeRun.mercenary),
                joinedload(ClassChangeRun.to_class),
            )
            .where(ClassChangeRun.guild_id == guild_id)
            .order_by(ClassChangeRun.id.desc())
        )
    )


def get_in_progress_run_for_mercenary(
    db: Session,
    guild_id: int,
    mercenary_id: int,
) -> ClassChangeRun | None:
    return db.scalar(
        select(ClassChangeRun).where(
            ClassChangeRun.guild_id == guild_id,
            ClassChangeRun.mercenary_id == mercenary_id,
            ClassChangeRun.status == "in_progress",
        )
    )


def get_class_change_run_by_guild(
    db: Session,
    guild_id: int,
    run_id: int,
) -> ClassChangeRun | None:
    return db.scalar(
        select(ClassChangeRun)
        .options(
            joinedload(ClassChangeRun.mercenary),
            joinedload(ClassChangeRun.to_class),
        )
        .where(
            ClassChangeRun.id == run_id,
            ClassChangeRun.guild_id == guild_id,
        )
    )


def create_class_change_run(
    db: Session,
    guild_id: int,
    mercenary_id: int,
    from_class_id: int,
    to_class_id: int,
    gold_cost: int,
    started_at: datetime,
    ends_at: datetime,
) -> ClassChangeRun:
    run = ClassChangeRun(
        guild_id=guild_id,
        mercenary_id=mercenary_id,
        from_class_id=from_class_id,
        to_class_id=to_class_id,
        gold_cost=gold_cost,
        started_at=started_at,
        ends_at=ends_at,
    )
    db.add(run)
    return run
