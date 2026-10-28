from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.guild import GuildResources
from app.models.mercenary import Mercenary
from app.models.mission import MissionRun, MissionRunMember, MissionTemplate
from app.models.item import MissionTemplateItemDrop


def list_active_mission_templates(db: Session) -> list[MissionTemplate]:
    return list(
        db.scalars(
            select(MissionTemplate)
            .where(MissionTemplate.is_active.is_(True))
            .order_by(MissionTemplate.display_order, MissionTemplate.id)
        )
    )


def list_active_mission_templates_for_band(
    db: Session,
    level_band: str,
    levels: tuple[int, ...] = (),
    gathering_family: str | None = None,
) -> list[MissionTemplate]:
    statement = (
        select(MissionTemplate)
        .options(selectinload(MissionTemplate.item_drops).joinedload(MissionTemplateItemDrop.item_template))
        .where(MissionTemplate.is_active.is_(True), MissionTemplate.level_band == level_band)
        .order_by(MissionTemplate.display_order, MissionTemplate.id)
    )
    if levels:
        statement = statement.where(MissionTemplate.required_min_mercenary_level.in_(levels))
    if gathering_family:
        statement = statement.where(MissionTemplate.gathering_family == gathering_family)
    return list(db.scalars(statement))


def list_active_gathering_families(db: Session) -> list[str]:
    return list(db.scalars(
        select(MissionTemplate.gathering_family)
        .where(
            MissionTemplate.is_active.is_(True),
            MissionTemplate.mission_type == "gathering",
            MissionTemplate.gathering_family.is_not(None),
        )
        .distinct()
        .order_by(MissionTemplate.gathering_family)
    ))


def list_all_mission_templates(db: Session) -> list[MissionTemplate]:
    return list(db.scalars(select(MissionTemplate).order_by(MissionTemplate.display_order, MissionTemplate.id)))


def get_mission_template_by_id(db: Session, mission_template_id: int) -> MissionTemplate | None:
    return db.get(MissionTemplate, mission_template_id)


def get_active_mission_template(db: Session, mission_template_id: int) -> MissionTemplate | None:
    return db.scalar(
        select(MissionTemplate).where(
            MissionTemplate.id == mission_template_id,
            MissionTemplate.is_active.is_(True),
        )
    )


def get_mission_template_by_name(db: Session, name: str) -> MissionTemplate | None:
    return db.scalar(select(MissionTemplate).where(MissionTemplate.name == name))


def create_mission_template(db: Session, data: dict[str, object]) -> MissionTemplate:
    payload = dict(data)
    if "display_order" not in payload:
        maximum_order = db.scalar(select(func.max(MissionTemplate.display_order))) or 0
        payload["display_order"] = maximum_order + 1
    mission_template = MissionTemplate(**payload)
    db.add(mission_template)
    return mission_template


def save_mission_template_order(db: Session, mission_templates: list[MissionTemplate]) -> None:
    for position, mission_template in enumerate(mission_templates, start=1):
        mission_template.display_order = position
        db.add(mission_template)
    db.commit()


def update_mission_template_duration(
    db: Session,
    mission_template: MissionTemplate,
    duration_seconds: int,
) -> MissionTemplate:
    mission_template.duration_seconds = duration_seconds
    db.add(mission_template)
    db.commit()
    db.refresh(mission_template)
    return mission_template


def update_mission_template(db: Session, mission_template: MissionTemplate, data: dict[str, object]) -> MissionTemplate:
    for key, value in data.items():
        setattr(mission_template, key, value)
    db.add(mission_template)
    db.commit()
    db.refresh(mission_template)
    return mission_template


def list_available_mercenaries_by_guild(db: Session, guild_id: int) -> list[Mercenary]:
    return list(
        db.scalars(
            select(Mercenary)
            .where(Mercenary.guild_id == guild_id, Mercenary.status == "available")
            .order_by(Mercenary.id)
        )
    )


def get_available_mercenary_by_guild(
    db: Session,
    guild_id: int,
    mercenary_id: int,
) -> Mercenary | None:
    return db.scalar(
        select(Mercenary).where(
            Mercenary.id == mercenary_id,
            Mercenary.guild_id == guild_id,
            Mercenary.status == "available",
        )
    )


def create_mission_run(
    db: Session,
    guild_id: int,
    mission_template_id: int,
    mercenaries: list[Mercenary],
    started_at: datetime,
    ends_at: datetime,
    run_multiplier: int = 1,
    *,
    commit: bool = True,
) -> MissionRun:
    mission_run = MissionRun(
        guild_id=guild_id,
        mission_template_id=mission_template_id,
        status="in_progress",
        run_multiplier=run_multiplier,
        started_at=started_at,
        ends_at=ends_at,
    )
    db.add(mission_run)
    db.flush()
    for mercenary in mercenaries:
        db.add(MissionRunMember(mission_run_id=mission_run.id, mercenary_id=mercenary.id))
        mercenary.status = "busy"
        db.add(mercenary)
    if commit:
        db.commit()
        db.refresh(mission_run)
    else:
        db.flush()
    return mission_run


def list_mission_runs_by_guild(db: Session, guild_id: int) -> list[MissionRun]:
    return list(
        db.scalars(
            select(MissionRun)
            .options(
                joinedload(MissionRun.mission_template),
                joinedload(MissionRun.members).joinedload(MissionRunMember.mercenary),
            )
            .where(MissionRun.guild_id == guild_id)
            .order_by(MissionRun.id.desc())
        )
        .unique()
    )


def get_mission_run_by_guild(db: Session, guild_id: int, mission_run_id: int) -> MissionRun | None:
    return (
        db.scalars(
            select(MissionRun)
            .options(
                joinedload(MissionRun.mission_template),
                joinedload(MissionRun.members).joinedload(MissionRunMember.mercenary),
            )
            .where(MissionRun.id == mission_run_id, MissionRun.guild_id == guild_id)
        )
        .unique()
        .one_or_none()
    )


def count_mission_runs_by_status(db: Session, guild_id: int, status: str) -> int:
    return (
        db.scalar(
            select(func.count(MissionRun.id)).where(
                MissionRun.guild_id == guild_id,
                MissionRun.status == status,
            )
        )
        or 0
    )


def count_awaiting_loot(db: Session, guild_id: int, now: datetime) -> int:
    return (
        db.scalar(
            select(func.count(MissionRun.id)).where(
                MissionRun.guild_id == guild_id,
                MissionRun.status == "in_progress",
                MissionRun.ends_at <= now,
            )
        )
        or 0
    )


def count_active_long_idle_runs(db: Session, guild_id: int) -> int:
    return db.scalar(
        select(func.count(MissionRun.id))
        .join(MissionTemplate)
        .where(
            MissionRun.guild_id == guild_id,
            MissionRun.status == "in_progress",
            MissionTemplate.mission_type == "long_idle",
        )
    ) or 0


def add_gold(resources: GuildResources, amount: int) -> None:
    resources.gold += amount


def count_mission_templates(db: Session) -> int:
    return db.scalar(select(func.count(MissionTemplate.id))) or 0
