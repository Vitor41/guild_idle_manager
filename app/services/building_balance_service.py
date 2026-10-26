from __future__ import annotations

from math import ceil


BUILDING_MAX_LEVEL = 50
STANDARD_MILESTONES = (1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50)
HOUSING_MILESTONES = (1, 2, 3, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50)


def clamp_level(level: int) -> int:
    return max(0, min(BUILDING_MAX_LEVEL, int(level)))


def housing_capacity(level: int) -> int:
    level = clamp_level(level)
    capacities = {
        0: 0, 1: 1, 2: 2, 3: 3, 5: 5, 10: 7, 15: 9,
        20: 11, 25: 13, 30: 15, 35: 17, 40: 18, 45: 19, 50: 20,
    }
    return capacities[max(key for key in capacities if key <= level)]


def training_xp_bonus(level: int) -> int:
    return clamp_level(level)


def blacksmith_drop_bonus(level: int) -> int:
    return min(25, ceil(clamp_level(level) / 2))


def warehouse_material_bonus(level: int) -> int:
    level = clamp_level(level)
    if level < 1:
        return 0
    return min(20, max(1, (level // 5) * 2))


def mission_office_values(level: int) -> dict[str, int]:
    level = clamp_level(level)
    if level < 1:
        party_size = 1
    elif level < 10:
        party_size = 2
    elif level < 25:
        party_size = 3
    elif level < 50:
        party_size = 4
    else:
        party_size = 5
    return {
        "party_size": party_size,
        "reward_bonus_percent": min(10, level // 5),
        "duration_reduction_percent": min(10, (level // 10) * 2),
    }


def scouts_values(level: int) -> dict[str, int]:
    level = clamp_level(level)
    multiplier = 3 if level >= 10 else 2 if level >= 5 else 1
    return {
        "max_multiplier": multiplier,
        "duration_reduction_percent": min(15, (level // 10) * 3),
        "drop_bonus_percentage_points": min(10, level // 5),
        "success_bonus_percentage_points": 3 if level >= 50 else 2 if level >= 45 else 0,
    }


def tavern_values(level: int, common_base: int = 90, uncommon_base: int = 10) -> dict[str, int | None]:
    level = clamp_level(level)
    steps = min(10, level // 5)
    bonus = steps * 2
    next_level = next((value for value in STANDARD_MILESTONES if value > level), None)
    next_steps = min(10, (next_level or level) // 5)
    next_bonus = next_steps * 2
    return {
        "common_base": common_base,
        "uncommon_base": uncommon_base,
        "common_final": max(0, common_base - bonus),
        "uncommon_final": min(100, uncommon_base + bonus),
        "uncommon_bonus_percentage_points": bonus,
        "hire_discount_percent": bonus,
        "next_milestone_level": next_level,
        "next_common_final": max(0, common_base - next_bonus),
        "next_uncommon_final": min(100, uncommon_base + next_bonus),
        "next_hire_discount_percent": next_bonus,
    }


def market_values(level: int) -> dict[str, int]:
    level = clamp_level(level)
    return {
        "slots": 0 if level < 1 else min(10, 1 + (level - 1) // 5),
        "time_reduction_percent": min(30, (level // 5) * 3),
        "value_bonus_percent": min(20, (level // 5) * 2),
    }


def docks_values(level: int) -> dict[str, int]:
    level = clamp_level(level)
    merchants = 0 if level < 1 else 4 if level >= 50 else 3 if level >= 35 else 2 if level >= 20 else 1
    return {
        "merchants": merchants,
        "offers": 0 if level < 1 else min(14, 4 + level // 5),
        "rotation_seconds": max(7200, 21600 - (level // 5) * 1440),
        "catalog_level": min(10, max(1, ceil(level / 5))) if level else 0,
    }


def building_cost_factor(next_level: int) -> float:
    next_level = max(1, min(BUILDING_MAX_LEVEL, next_level))
    if next_level <= 10:
        return float(next_level)
    if next_level <= 25:
        return 10 + (next_level - 10) * 1.5
    if next_level <= 40:
        return 32.5 + (next_level - 25) * 2
    return 62.5 + (next_level - 40) * 3


def required_guild_level_for_upgrade(next_level: int, base_required_level: int = 1) -> int:
    return max(base_required_level, ceil(max(1, next_level) / 2))


def next_milestone(effect_type: str, level: int) -> int | None:
    milestones = HOUSING_MILESTONES if effect_type == "housing" else STANDARD_MILESTONES
    return next((milestone for milestone in milestones if milestone > clamp_level(level)), None)


def _benefit_lines(effect_type: str, level: int) -> tuple[list[str], list[str]]:
    level = clamp_level(level)
    if effect_type == "housing":
        return [f"Capacidade: {housing_capacity(level)} mercenários"], ["Elenco", "Taverna"]
    if effect_type == "training_ground":
        class_change_status = "Troca de classe: liberada" if level >= 10 else "Troca de classe: bloqueada até nível 10"
        return [f"XP de mercenários: +{training_xp_bonus(level)}%", class_change_status], ["Missões", "Masmorras", "Classes"]
    if effect_type == "blacksmith":
        return [f"Chance de equipamento: +{blacksmith_drop_bonus(level)} p.p.", "Receitas e refino melhoram por nível"], ["Loot", "Criação", "Refino"]
    if effect_type == "warehouse":
        return [f"Materiais principais: +{warehouse_material_bonus(level)} adicionais", f"Produção offline: +{level // 5} ouro/h"], ["Coleta", "Loot", "Progresso offline"]
    if effect_type == "contract_office":
        values = mission_office_values(level)
        return [f"Grupo de missão: até {values['party_size']}", f"Recompensas de missão: +{values['reward_bonus_percent']}%", f"Redução de duração: {values['duration_reduction_percent']}%"], ["Missões"]
    if effect_type == "scouts":
        values = scouts_values(level)
        return [f"Multiplicador máximo: {values['max_multiplier']}x", f"Loot de masmorra: +{values['drop_bonus_percentage_points']} p.p.", f"Redução de exploração: {values['duration_reduction_percent']}%"], ["Masmorras", "Chefes"]
    if effect_type == "tavern":
        values = tavern_values(level)
        return [f"Aprendiz Incomum: {values['uncommon_final']}%", f"Desconto em contratação: {values['hire_discount_percent']}%"], ["Taverna", "Contratação"]
    if effect_type == "market":
        values = market_values(level)
        return [f"Espaços de venda: {values['slots']}", f"Redução de tempo: {values['time_reduction_percent']}%", f"Bônus de valor: +{values['value_bonus_percent']}%"], ["Mercado", "Economia"]
    if effect_type == "docks":
        values = docks_values(level)
        return [f"Mercantes ativos: {values['merchants']}", f"Ofertas: {values['offers']}", f"Rotação: {values['rotation_seconds'] // 3600}h"], ["Docas", "Materiais", "Equipamentos"]
    return ["Benefício configurável"], ["Guilda"]


def get_building_benefit(effect_type: str, level: int) -> dict[str, object]:
    current_lines, systems = _benefit_lines(effect_type, level)
    milestone = next_milestone(effect_type, level)
    next_lines = _benefit_lines(effect_type, milestone)[0] if milestone is not None else []
    return {
        "current": current_lines,
        "next_milestone_level": milestone,
        "next": next_lines,
        "systems": systems,
        "is_max_level": clamp_level(level) >= BUILDING_MAX_LEVEL,
    }
