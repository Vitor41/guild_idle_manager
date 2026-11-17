"""Pure presentation helpers for class-change requirement summaries."""

from collections import defaultdict


TIER_LABELS = {
    1: "1ª troca",
    2: "2ª troca",
    3: "3ª troca",
}


def _count_label(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def build_transition_stage_cards(
    transitions: list[dict[str, int | str]],
    mercenaries: list[dict[str, int | str]],
    *,
    gold: int,
    guild_level: int,
    training_ground_level: int,
) -> list[dict[str, object]]:
    """Group equivalent transitions and report authoritative current requirements."""
    grouped: dict[tuple[int, int, int, int, int], list[dict[str, object]]] = defaultdict(list)
    for transition in transitions:
        key = (
            int(transition["tier"]),
            int(transition["required_mercenary_level"]),
            int(transition["required_guild_level"]),
            int(transition["required_training_ground_level"]),
            int(transition["gold_cost"]),
        )
        grouped[key].append({
            "from_class_id": int(transition["from_class_id"]),
            "target_label": str(transition.get("target_label", "")).strip(),
        })

    cards: list[dict[str, object]] = []
    for (tier, required_mercenary_level, required_guild_level,
         required_training_ground_level, gold_cost), paths in sorted(grouped.items()):
        from_class_ids = {int(path["from_class_id"]) for path in paths}
        target_labels = sorted({str(path["target_label"]) for path in paths if path["target_label"]})
        matching_workers = [
            worker for worker in mercenaries
            if int(worker["class_id"]) in from_class_ids
        ]
        available_workers = [worker for worker in matching_workers if worker["status"] == "available"]
        busy_workers = [worker for worker in matching_workers if worker["status"] != "available"]
        current_mercenary_level = max((int(worker["level"]) for worker in matching_workers), default=None)
        eligible_ids = {
            int(worker["id"])
            for worker in available_workers
            if int(worker["level"]) >= required_mercenary_level
            and int(gold) >= gold_cost
            and int(guild_level) >= required_guild_level
            and int(training_ground_level) >= required_training_ground_level
        }
        checks = [
            {
                "label": "Ouro",
                "required": gold_cost,
                "current": int(gold),
                "met": int(gold) >= gold_cost,
                "shortfall": max(0, gold_cost - int(gold)),
            },
            {
                "label": "Guilda",
                "required": required_guild_level,
                "current": int(guild_level),
                "met": int(guild_level) >= required_guild_level,
                "shortfall": max(0, required_guild_level - int(guild_level)),
            },
            {
                "label": "Campo de Treino",
                "required": required_training_ground_level,
                "current": int(training_ground_level),
                "met": int(training_ground_level) >= required_training_ground_level,
                "shortfall": max(0, required_training_ground_level - int(training_ground_level)),
            },
            {
                "label": "Mercenário",
                "required": required_mercenary_level,
                "current": current_mercenary_level if current_mercenary_level is not None else "—",
                "met": current_mercenary_level is not None and current_mercenary_level >= required_mercenary_level,
                "shortfall": (
                    max(0, required_mercenary_level - current_mercenary_level)
                    if current_mercenary_level is not None else None
                ),
                "missing": "Sem mercenário da classe de origem" if current_mercenary_level is None else "",
            },
        ]
        global_checks_met = all(check["met"] for check in checks[:3])
        eligible_count = len(eligible_ids)
        level_ready_available = [
            worker for worker in available_workers
            if int(worker["level"]) >= required_mercenary_level
        ]
        level_ready_busy = [
            worker for worker in busy_workers
            if int(worker["level"]) >= required_mercenary_level
        ]
        if not matching_workers:
            worker_summary = "Nenhum mercenário com a classe de origem desta etapa."
        elif level_ready_available and global_checks_met:
            worker_summary = f"{_count_label(len(eligible_ids), 'mercenário elegível', 'mercenários elegíveis')}."
        elif level_ready_available:
            worker_summary = (
                f"{_count_label(len(level_ready_available), 'mercenário disponível', 'mercenários disponíveis')} "
                "com nível suficiente."
            )
        elif available_workers and level_ready_busy:
            available_count = len(available_workers)
            busy_count = len(level_ready_busy)
            worker_summary = (
                f"{_count_label(available_count, 'mercenário disponível', 'mercenários disponíveis')} "
                f"{'está' if available_count == 1 else 'estão'} abaixo do nível; "
                f"{_count_label(busy_count, 'mercenário ocupado', 'mercenários ocupados')} "
                f"{'atende' if busy_count == 1 else 'atendem'} ao nível."
            )
        elif available_workers:
            available_max_level = max(int(worker["level"]) for worker in available_workers)
            worker_summary = (
                f"{_count_label(len(available_workers), 'mercenário disponível', 'mercenários disponíveis')}; "
                f"maior nível Nv. {available_max_level} "
                f"(necessário Nv. {required_mercenary_level})."
            )
        elif level_ready_busy:
            busy_count = len(level_ready_busy)
            worker_summary = (
                f"{_count_label(busy_count, 'mercenário', 'mercenários')} "
                f"{'está ocupado' if busy_count == 1 else 'estão ocupados'} e "
                f"{'atende' if busy_count == 1 else 'atendem'} ao nível."
            )
        else:
            busy_max_level = max(int(worker["level"]) for worker in busy_workers)
            worker_summary = (
                f"Sem mercenário disponível; maior nível ocupado Nv. {busy_max_level} "
                f"(necessário Nv. {required_mercenary_level})."
            )
        if eligible_count:
            state = "Liberada"
        elif global_checks_met:
            if not matching_workers:
                state = "Sem mercenário na classe"
            elif available_workers:
                state = "Nível insuficiente"
            elif level_ready_busy:
                state = "Mercenário ocupado"
            else:
                state = "Nível insuficiente"
        else:
            state = "Faltam requisitos"
        state_class = {
            "Liberada": "ready",
            "Faltam requisitos": "pending",
            "Nível insuficiente": "pending",
            "Mercenário ocupado": "occupied",
            "Sem mercenário na classe": "empty",
        }[state]
        cards.append({
            "label": TIER_LABELS.get(tier, f"Evolução tier {tier}"),
            "tier": tier,
            "gold_cost": gold_cost,
            "required_mercenary_level": required_mercenary_level,
            "required_guild_level": required_guild_level,
            "required_training_ground_level": required_training_ground_level,
            "eligible_count": eligible_count,
            "path_count": len(paths),
            "targets": target_labels,
            "state": state,
            "state_class": state_class,
            "worker_summary": worker_summary,
            "checks": checks,
        })
    return cards
