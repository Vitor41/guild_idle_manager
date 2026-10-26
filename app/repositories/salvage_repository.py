from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.salvage import GuildSalvageJob


def list_salvage_jobs_by_guild(db: Session, guild_id: int) -> list[GuildSalvageJob]:
    return list(db.scalars(
        select(GuildSalvageJob)
        .options(
            joinedload(GuildSalvageJob.item_template),
            joinedload(GuildSalvageJob.material_template),
        )
        .where(GuildSalvageJob.guild_id == guild_id)
        .order_by(GuildSalvageJob.id.desc())
    ))


def get_salvage_job_by_guild(
    db: Session, guild_id: int, job_id: int, *, lock: bool = False
) -> GuildSalvageJob | None:
    statement = select(GuildSalvageJob).where(
        GuildSalvageJob.id == job_id,
        GuildSalvageJob.guild_id == guild_id,
    )
    if lock:
        statement = statement.with_for_update()
    return db.scalar(statement)


def get_active_salvage_job_for_slot(
    db: Session, guild_id: int, slot_number: int, *, lock: bool = False
) -> GuildSalvageJob | None:
    statement = select(GuildSalvageJob).where(
        GuildSalvageJob.guild_id == guild_id,
        GuildSalvageJob.slot_number == slot_number,
        GuildSalvageJob.status == "in_progress",
    )
    if lock:
        statement = statement.with_for_update()
    return db.scalar(statement)


def create_salvage_job(db: Session, data: dict[str, object]) -> GuildSalvageJob:
    job = GuildSalvageJob(**data)
    db.add(job)
    return job
