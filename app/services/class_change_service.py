from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.class_change import ClassChangeRun
from app.models.class_change import ClassTransitionOption
from app.models.guild import Guild, GuildResources
from app.repositories.class_change_repository import (
    create_class_change_run,
    get_class_change_run_by_guild,
    get_in_progress_run_for_mercenary,
    get_transition_by_classes,
    list_active_transitions_for_class,
    list_class_change_runs_by_guild,
)
from app.repositories.mercenary_repository import get_mercenary_by_guild
from app.repositories.mercenary_repository import list_mercenaries_by_guild
from app.services.building_service import get_building_level
from app.services.guild_progression_service import add_guild_xp
from app.services.achievement_service import record_guild_stat, unlock_codex_reference
from app.services.mission_service import format_duration_seconds
from app.services.display_service import annotate_mercenary_display, class_label
from app.services.progression_service import apply_class_evolution_attributes
from app.services.icon_service import get_class_icon_path


class ClassChangeError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _transition_requirement_steps(db: Session) -> list[dict[str, object]]:
    transitions = list(
        db.query(ClassTransitionOption)
        .join(ClassTransitionOption.to_class)
        .filter(ClassTransitionOption.is_active.is_(True))
        .order_by(ClassTransitionOption.required_mercenary_level, ClassTransitionOption.required_guild_level)
        .all()
    )
    steps: dict[tuple[int, int, int, int], dict[str, object]] = {}
    for transition in transitions:
        key = (
            transition.required_mercenary_level,
            transition.required_guild_level,
            transition.required_training_ground_level,
            transition.gold_cost,
        )
        if key in steps:
            steps[key]["target_count"] = int(steps[key]["target_count"]) + 1
            continue
        tier_label = {
            1: "Primeira classe",
            2: "Especialização",
            3: "Classe final",
        }.get(transition.to_class.tier, f"Evolução tier {transition.to_class.tier}")
        steps[key] = {
            "label": tier_label,
            "required_mercenary_level": transition.required_mercenary_level,
            "required_guild_level": transition.required_guild_level,
            "required_training_ground_level": transition.required_training_ground_level,
            "gold_cost": transition.gold_cost,
            "duration_seconds": transition.duration_seconds,
            "target_count": 1,
        }
    return list(steps.values())


def get_class_change_page_context(db: Session, guild: Guild) -> dict[str, object]:
    runs = list_class_change_runs_by_guild(db, guild.id)
    training_ground_level = get_building_level(db, guild.id, "training_ground")
    all_mercenaries = list_mercenaries_by_guild(db, guild.id)
    transitions_by_mercenary = {}
    mercenaries = []
    for mercenary in all_mercenaries:
        transitions = list_active_transitions_for_class(db, mercenary.class_id)
        eligible = [transition for transition in transitions if (
            mercenary.status == "available"
            and mercenary.level >= transition.required_mercenary_level
            and guild.level >= transition.required_guild_level
            and training_ground_level >= transition.required_training_ground_level
        )]
        if eligible:
            mercenaries.append(mercenary)
            transitions_by_mercenary[mercenary.id] = eligible
    for mercenary in mercenaries:
        annotate_mercenary_display(mercenary)
    for transitions in transitions_by_mercenary.values():
        for transition in transitions:
            transition.to_class.view_label = class_label(transition.to_class)
            transition.to_class.icon_path = get_class_icon_path(transition.to_class)
    for run in runs:
        run.to_class.icon_path = get_class_icon_path(run.to_class)
    return {
        "mercenaries": mercenaries,
        "transitions_by_mercenary": transitions_by_mercenary,
        "in_progress_runs": [run for run in runs if run.status == "in_progress"],
        "finished_runs": [run for run in runs if run.status == "completed"][:10],
        "training_ground_level": training_ground_level,
        "requirement_steps": _transition_requirement_steps(db),
        "now": utc_now(),
        "format_duration": format_duration_seconds,
    }


def start_class_change(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    mercenary_id: str,
    to_class_id: str,
) -> ClassChangeRun:
    if resources is None:
        raise ClassChangeError("Recursos da guilda indisponiveis.")
    try:
        parsed_mercenary_id = int(mercenary_id)
        parsed_to_class_id = int(to_class_id)
    except ValueError as exc:
        raise ClassChangeError("Dados de troca invalidos.") from exc

    mercenary = get_mercenary_by_guild(db, guild.id, parsed_mercenary_id)
    if mercenary is None:
        raise ClassChangeError("Mercenario nao encontrado.")
    if mercenary.status != "available":
        raise ClassChangeError("Mercenario precisa estar disponivel.")
    if get_in_progress_run_for_mercenary(db, guild.id, mercenary.id):
        raise ClassChangeError("Este mercenario ja esta em troca de classe.")

    transition = get_transition_by_classes(db, mercenary.class_id, parsed_to_class_id)
    if transition is None or not transition.is_active:
        raise ClassChangeError("Troca de classe indisponivel.")
    if mercenary.level < transition.required_mercenary_level:
        raise ClassChangeError("Nivel do mercenario insuficiente para esta troca.")
    if guild.level < transition.required_guild_level:
        raise ClassChangeError("Nivel da guilda insuficiente para esta troca.")
    if get_building_level(db, guild.id, "training_ground") < transition.required_training_ground_level:
        raise ClassChangeError("Campo de Treino insuficiente para esta troca.")
    if resources.gold < transition.gold_cost:
        raise ClassChangeError("Ouro insuficiente para iniciar a troca de classe.")

    started_at = utc_now()
    resources.gold -= transition.gold_cost
    mercenary.status = "busy"
    run = create_class_change_run(
        db=db,
        guild_id=guild.id,
        mercenary_id=mercenary.id,
        from_class_id=mercenary.class_id,
        to_class_id=transition.to_class_id,
        gold_cost=transition.gold_cost,
        started_at=started_at,
        ends_at=started_at + timedelta(seconds=transition.duration_seconds),
    )
    add_guild_xp(guild, 10)
    db.add(resources)
    db.add(mercenary)
    db.add(guild)
    db.commit()
    db.refresh(run)
    return run


def claim_class_change(db: Session, guild: Guild, run_id: int) -> ClassChangeRun:
    run = get_class_change_run_by_guild(db, guild.id, run_id)
    if run is None:
        raise ClassChangeError("Troca de classe nao encontrada.")
    if run.status != "in_progress":
        raise ClassChangeError("Esta troca ja foi concluida.")
    now = utc_now()
    if now < run.ends_at:
        raise ClassChangeError("A troca de classe ainda nao terminou.")

    run.status = "completed"
    run.completed_at = now
    apply_class_evolution_attributes(run.mercenary, run.mercenary.mercenary_class, run.to_class)
    run.mercenary.class_id = run.to_class_id
    run.mercenary.status = "available"
    add_guild_xp(guild, 10)
    if run.to_class.code:
        unlock_codex_reference(db, guild.id, "class", run.to_class.code)
    record_guild_stat(db, guild.id, "class_changes", 1)
    db.add(run)
    db.add(run.mercenary)
    db.add(guild)
    db.commit()
    db.refresh(run)
    return run
