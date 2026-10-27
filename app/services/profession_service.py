from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.time import as_utc
from app.models.content import ProfessionTemplate, ProfessionTraining
from app.models.guild import Guild, GuildResources
from app.models.mercenary import Mercenary


class ProfessionError(ValueError):
    pass


PROFESSION_FAMILY_LABELS = {
    "wood": "madeiras", "ore": "minérios", "herb": "ervas", "leather": "couros",
    "cloth": "fibras e tecidos", "gem": "gemas", "relic": "relíquias", "essence": "essências",
}

PROFESSION_COLORS = {
    "woodcutter": "#6f9b58", "miner": "#9aa1a8", "herbalist": "#83b96b",
    "leatherworker": "#a97852", "weaver": "#b792c5", "prospector": "#c59445",
    "reliquary": "#c5a85a", "alchemist": "#8f72c9",
}


def profession_color(code: str | None) -> str:
    return PROFESSION_COLORS.get(code or "", "#a98a52")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_professions_context(db: Session, guild: Guild) -> dict[str, object]:
    professions = list(db.scalars(select(ProfessionTemplate).where(ProfessionTemplate.is_active.is_(True)).order_by(ProfessionTemplate.name)))
    for profession in professions:
        profession.family_label = PROFESSION_FAMILY_LABELS.get(profession.material_family, profession.material_family)
        profession.view_color = profession_color(profession.code)
    mercenaries = list(db.scalars(select(Mercenary).options(joinedload(Mercenary.profession)).where(
        Mercenary.guild_id == guild.id, Mercenary.status != "dismissed"
    ).order_by(Mercenary.name)))
    trainings = list(db.scalars(select(ProfessionTraining).options(joinedload(ProfessionTraining.mercenary), joinedload(ProfessionTraining.profession)).where(
        ProfessionTraining.guild_id == guild.id, ProfessionTraining.status == "in_progress").order_by(ProfessionTraining.ends_at)))
    return {"professions": professions, "mercenaries": mercenaries, "trainings": trainings, "now": utc_now()}


def start_profession_training(db: Session, guild: Guild, resources: GuildResources, mercenary_id: int, profession_id: int) -> ProfessionTraining:
    mercenary = db.scalar(select(Mercenary).where(Mercenary.id == mercenary_id, Mercenary.guild_id == guild.id))
    profession = db.scalar(select(ProfessionTemplate).where(ProfessionTemplate.id == profession_id, ProfessionTemplate.is_active.is_(True)))
    if mercenary is None or profession is None:
        raise ProfessionError("Mercenário ou profissão indisponível.")
    if mercenary.status != "available":
        raise ProfessionError("O mercenário precisa estar disponível para treinar.")
    if resources.gold < profession.training_gold_cost:
        raise ProfessionError("Ouro insuficiente para este treinamento.")
    active = db.scalar(select(ProfessionTraining).where(ProfessionTraining.mercenary_id == mercenary.id, ProfessionTraining.status == "in_progress"))
    if active is not None:
        raise ProfessionError("Este mercenário já está em treinamento.")
    now = utc_now()
    training = ProfessionTraining(guild_id=guild.id, mercenary_id=mercenary.id, profession_id=profession.id,
        status="in_progress", started_at=now, ends_at=now + timedelta(seconds=profession.training_duration_seconds))
    resources.gold -= profession.training_gold_cost
    mercenary.status = "busy"
    db.add_all([training, resources, mercenary])
    db.commit()
    db.refresh(training)
    return training


def complete_profession_training(db: Session, guild: Guild, training_id: int) -> ProfessionTraining:
    training = db.scalar(select(ProfessionTraining).options(joinedload(ProfessionTraining.mercenary)).where(
        ProfessionTraining.id == training_id, ProfessionTraining.guild_id == guild.id))
    if training is None or training.status != "in_progress":
        raise ProfessionError("Treinamento indisponível.")
    now = utc_now()
    if now < as_utc(training.ends_at):
        raise ProfessionError("O treinamento ainda não terminou.")
    training.status = "completed"
    training.completed_at = now
    training.mercenary.profession_id = training.profession_id
    training.mercenary.status = "available"
    db.add_all([training, training.mercenary])
    db.commit()
    return training


def get_profession_drop_bonus_percentage_points(
    mercenaries: list[Mercenary], profession_code: str | None,
) -> int:
    if not profession_code:
        return 0
    bonuses = []
    for mercenary in mercenaries:
        if mercenary.profession and mercenary.profession.code == profession_code:
            bonuses.append(mercenary.profession.bonus_percent)
    return max(bonuses, default=0)


def get_gathering_bonus_percent(mercenaries: list[Mercenary], profession_code: str | None) -> int:
    return get_profession_drop_bonus_percentage_points(mercenaries, profession_code)
