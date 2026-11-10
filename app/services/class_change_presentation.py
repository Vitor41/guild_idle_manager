"""Pure presentation helpers for class-change requirement summaries."""

from collections import defaultdict


TIER_LABELS = {
    1: "1ª troca",
    2: "2ª troca",
    3: "3ª troca",
}


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
        current_mercenary_level = max((int(worker["level"]) for worker in matching_workers), default=0)
        available_workers = [worker for worker in matching_workers if worker["status"] == "available"]
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
                "current": current_mercenary_level,
                "met": current_mercenary_level >= required_mercenary_level,
                "shortfall": max(0, required_mercenary_level - current_mercenary_level),
            },
        ]
        global_checks_met = all(check["met"] for check in checks[:3])
        eligible_count = len(eligible_ids)
        if eligible_count:
            state = "Liberada"
        elif global_checks_met:
            state = "Sem mercenário elegível"
        else:
            state = "Faltam requisitos"
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
            "checks": checks,
        })
    return cards
