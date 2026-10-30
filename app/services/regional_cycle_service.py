"""Deterministic, campaign-local regional Vigília cycles and offer snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import random

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.game_balance import GUILD_MAX_LEVEL, GUILD_XP_BASE, GUILD_XP_GROWTH
from app.models.campaign import CampaignMetadata
from app.models.dungeon import DungeonTemplate
from app.models.guild import Guild
from app.models.mercenary import Mercenary, MercenaryClass
from app.models.mission import MissionTemplate
from app.models.regional import (
    RegionalCpuCyclePlan,
    RegionalCpuMercenary,
    RegionalCpuResource,
    RegionalCycle,
    RegionalCycleRegion,
    RegionalEvent,
    RegionalEventActivity,
    RegionalGuildState,
    RegionalOffer,
    RegionalRegionState,
    RegionalRunOutcome,
    RegionalWorldState,
)
from app.services.balance_service import CLASS_SUCCESS_BONUS, calculate_power_score, power_success_adjustment
from app.services.equipment_service import get_mercenary_attribute_summary
from app.models.content import ProfessionTemplate


LEGACY_VIGILIA_RULES_VERSION = "vigilia-v2"
VIGILIA_RULES_VERSION = "vigilia-v4"
RIVAL_CALM_RULES_VERSIONS = frozenset({"vigilia-v3", "vigilia-v4"})
CYCLE_SECONDS = 6 * 60 * 60
RANKS = ("E", "D", "C", "B", "A", "S")
# Confirmed GDD reference for a Vigília with no regional actions.
REGION_BASELINE_PRESSURE = 1
RIVAL_CALM_WINDOW_CYCLES = 4
RIVAL_CALM_IMPACT_PER_CYCLE = 0.25
REGIONAL_IMPACT_BASE = 0.02
REGIONAL_IMPACT_PER_RANK = 0.02
# CPU rivals make a deterministic per-action decision each Vigília. Their
# profile sets the cadence; archetype and campaign seed add small variation.
CPU_ACTION_PROBABILITY_BY_PROFILE = {"strong": 0.28, "medium": 0.25, "new": 0.22}
CPU_ARCHETYPE_ACTION_ADJUSTMENT = {
    "expansion": 0.005,
    "security": -0.005,
    "contracts": 0.0,
    "exploration": -0.005,
}
BASE_RANK_WEIGHTS = (31, 27, 22, 12, 7, 1)
LATE_RANK_WEIGHTS = (8, 14, 23, 32, 18, 5)
REGIONS = (
    ("vale-fronteira", "Vale da Fronteira"),
    ("bosque-ambar", "Bosque de Âmbar"),
    ("costa-brumas", "Costa das Brumas"),
    ("terras-cinza", "Terras de Cinza"),
    ("picos-norte", "Picos do Norte"),
)
RIVAL_ARCHETYPES = ("expansion", "security", "contracts", "exploration")
CPU_RESOURCE_CODES = ("gold", "xp", "wood", "ore", "leather", "herb", "cloth", "gem", "relic", "essence")
CPU_GUILD_NAMES = (
    "Companhia do Farol", "Lanças de Âmbar", "Pacto das Cinzas", "Sentinelas do Vale",
    "Ordem das Brumas", "Vigias do Norte", "Círculo da Forja", "Batedores da Aurora",
    "Escudo Errante", "Companhia do Cedro", "Guardiões da Trilha", "Lâminas do Poente",
    "Pacto da Montanha", "Cavaleiros da Névoa", "Mãos de Prata", "Companhia Rubra",
    "Ordem do Carvalho", "Vigias da Costa", "Lobos da Fronteira", "Estrelas do Caminho",
    "Escudo da Serra", "Círculo do Horizonte", "Lanças do Crepúsculo", "Guardiões do Pinhal",
)
CPU_PROFILE_BASE = {
    "strong": {
        "guild_level": 3, "mercenary_level": 4, "attributes": (12, 12, 10, 10, 8, 2),
        "gold": 600, "material": 15, "capacity": 2500,
    },
    "medium": {
        "guild_level": 2, "mercenary_level": 2, "attributes": (8, 8, 7, 7, 5, 0),
        "gold": 300, "material": 7, "capacity": 1200,
    },
    "new": {
        "guild_level": 1, "mercenary_level": 1, "attributes": (5, 5, 5, 5, 5, 0),
        "gold": 100, "material": 1, "capacity": 500,
    },
}
CPU_STAGE_RESOURCE_SCALARS = (1.00, 1.05, 1.10, 1.15, 1.20)
CPU_STAGE_LEVEL_BONUSES = (0, 0, 1, 1, 2)
PROFESSION_RESOURCE_CODES = {
    "woodcutter": "wood", "miner": "ore", "leatherworker": "leather", "herbalist": "herb",
    "weaver": "cloth", "prospector": "gem", "reliquary": "relic", "alchemist": "essence",
}


class RegionalCycleError(ValueError):
    pass


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _now(value: datetime | None = None) -> datetime:
    return _utc(value or datetime.now(timezone.utc))


def _seed_text(*parts: object) -> str:
    return sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _rng(*parts: object) -> random.Random:
    return random.Random(int(_seed_text(*parts), 16))


def regional_stage_for_region(region_code: str) -> int:
    """Fixed world-order stage; deliberately independent of the human guild."""
    return next((index + 1 for index, (code, _name) in enumerate(REGIONS) if code == region_code), 1)


def cpu_initial_profile_values(profile: str, region_stage: int) -> dict[str, object]:
    """Moderately scale a CPU rival's initial stats and inventory by region band."""
    base = CPU_PROFILE_BASE.get(profile, CPU_PROFILE_BASE["new"])
    stage_index = max(1, min(len(CPU_STAGE_RESOURCE_SCALARS), int(region_stage))) - 1
    scalar = CPU_STAGE_RESOURCE_SCALARS[stage_index]
    level_bonus = CPU_STAGE_LEVEL_BONUSES[stage_index]
    return {
        "guild_level": int(base["guild_level"]) + level_bonus,
        "mercenary_level": int(base["mercenary_level"]) + level_bonus,
        "attributes": tuple(max(1, round(value * scalar)) for value in base["attributes"]),
        "gold": round(int(base["gold"]) * scalar),
        "material": round(int(base["material"]) * scalar),
        "capacity": round(int(base["capacity"]) * scalar),
        "stage": stage_index + 1,
        "scalar": scalar,
    }


def rival_calm_for_cycle(
    cycle_number: int,
    rules_version: str,
    has_strong_rival: bool,
    baseline_applied: bool,
) -> dict[str, object]:
    """Return the temporary calm ledger contribution for a resolved Vigília."""
    versioned = rules_version in RIVAL_CALM_RULES_VERSIONS
    active = versioned and has_strong_rival and 0 <= cycle_number < RIVAL_CALM_WINDOW_CYCLES
    applied = active
    amount = RIVAL_CALM_IMPACT_PER_CYCLE if applied else 0.0
    return {
        "active": active,
        "applied": applied,
        "security": amount,
        "threat": -amount,
        "window_cycles": RIVAL_CALM_WINDOW_CYCLES,
        "expires_after_cycle": RIVAL_CALM_WINDOW_CYCLES - 1,
        "expired_before_this_cycle": versioned and cycle_number == RIVAL_CALM_WINDOW_CYCLES,
        "baseline_was_applied": baseline_applied,
    }


def regional_cpu_action_probability(
    campaign_id: str,
    state: RegionalGuildState,
    rules_version: str = VIGILIA_RULES_VERSION,
) -> float:
    """Stable per-rival activity cadence, with a small deterministic seed variation."""
    base = CPU_ACTION_PROBABILITY_BY_PROFILE.get(state.profile, CPU_ACTION_PROBABILITY_BY_PROFILE["new"])
    archetype_adjustment = CPU_ARCHETYPE_ACTION_ADJUSTMENT.get(state.archetype, 0.0)
    seed_fraction = int(_seed_text(
        campaign_id, state.region_code, state.slot, state.archetype, rules_version, "activity-rate",
    )[:8], 16) / 0xFFFFFFFF
    seed_variation = (seed_fraction - 0.5) * 0.02
    return round(max(0.05, min(0.35, base + archetype_adjustment + seed_variation)), 4)


def rank_progression_stage(guild_level: int, total_power: int) -> float:
    level_stage = max(0.0, min(1.0, (max(1, guild_level) - 1) / 49))
    power_stage = max(0.0, min(1.0, total_power / 30000))
    return round(level_stage * 0.65 + power_stage * 0.35, 6)


def rank_weights_for_stage(stage: float) -> dict[str, int]:
    factor = max(0.0, min(1.0, float(stage)))
    values = [round(base + (late - base) * factor) for base, late in zip(BASE_RANK_WEIGHTS, LATE_RANK_WEIGHTS)]
    difference = 100 - sum(values)
    values[2] += difference
    return dict(zip(RANKS, values))


def regional_outcome_impact(rank: str) -> float:
    """Positive, rank-scaled regional impact with hundredth-point precision."""
    rank_index = RANKS.index(rank) if rank in RANKS else 0
    return round(REGIONAL_IMPACT_BASE + REGIONAL_IMPACT_PER_RANK * (rank_index + 1), 4)


def roll_contract_ranks(stage: float, seed: int | str, count: int = 10) -> list[str]:
    """Weighted rank sampling with distinct rank slots and a hard three-per-rank cap."""
    rng = random.Random(int(seed) if isinstance(seed, str) and seed.isdigit() else str(seed))
    weights = rank_weights_for_stage(stage)
    counts = {rank: 0 for rank in RANKS}
    output: list[str] = []
    for _ in range(max(0, count)):
        available = [weights[rank] if counts[rank] < 3 else 0 for rank in RANKS]
        picked = rng.choices(RANKS, weights=available, k=1)[0]
        counts[picked] += 1
        output.append(picked)
    return output


def simulate_rank_distribution(stage: float, seed: int, cycles: int = 1000) -> dict[str, object]:
    counts = {rank: 0 for rank in RANKS}
    baseline_counts = {rank: 0 for rank in RANKS}
    dungeon_counts = {rank: 0 for rank in RANKS}
    boss_counts = {rank: 0 for rank in RANKS}
    b_to_s = 0
    max_contract_rank_slots = 0
    for cycle_number in range(max(0, cycles)):
        cycle_seed = _seed_text(seed, cycle_number, "rank-simulation")
        ranks = roll_contract_ranks(stage, cycle_seed, 10)
        max_contract_rank_slots = max(
            max_contract_rank_slots,
            max((ranks.count(rank) for rank in RANKS), default=0),
        )
        for rank in ranks:
            counts[rank] += 1
            b_to_s += rank in {"B", "A", "S"}
        weight_payload = _rank_weight_payload(stage)
        baseline_rng = _rng(cycle_seed, "uncapped-regional")
        baseline_weights = rank_weights_for_stage(stage)
        for _ in range(10):
            baseline_counts[_roll_rank(baseline_rng, baseline_weights)] += 1
        dungeon_rng = _rng(cycle_seed, "dungeon")
        for _ in range(3):
            dungeon_counts[_roll_rank(dungeon_rng, weight_payload["dungeon"])] += 1
        boss_rng = _rng(cycle_seed, "boss")
        boss_counts[_roll_rank(boss_rng, weight_payload["boss"])] += 1
    total = max(1, cycles * 10)
    dungeon_total = max(1, cycles * 3)
    boss_total = max(1, cycles)
    return {
        "cycles": max(0, cycles),
        "offers": max(0, cycles) * 10,
        "rank_counts": counts,
        "max_contract_rank_slots_in_cycle": max_contract_rank_slots,
        "rank_percentages": {rank: round(value * 100 / total, 2) for rank, value in counts.items()},
        "b_to_s_per_cycle": round(b_to_s / max(1, cycles), 2),
        "b_to_s_percentage": round(b_to_s * 100 / total, 2),
        "uncapped_regional_rank_counts": baseline_counts,
        "uncapped_regional_rank_percentages": {
            rank: round(value * 100 / total, 2) for rank, value in baseline_counts.items()
        },
        "dungeon_rank_counts": dungeon_counts,
        "dungeon_rank_percentages": {
            rank: round(value * 100 / dungeon_total, 2) for rank, value in dungeon_counts.items()
        },
        "boss_rank_counts": boss_counts,
        "boss_rank_percentages": {
            rank: round(value * 100 / boss_total, 2) for rank, value in boss_counts.items()
        },
    }


def total_player_power(db: Session, guild: Guild) -> int:
    mercenaries = list(db.scalars(select(Mercenary).where(
        Mercenary.guild_id == guild.id,
        Mercenary.status != "dismissed",
    ).order_by(Mercenary.id)))
    return sum(int(get_mercenary_attribute_summary(db, guild.id, mercenary)["total_power_score"]) for mercenary in mercenaries)


def _guild_player_level(guild: Guild) -> int:
    return max(1, int(guild.level or 1))


def _ensure_cpu_roster(
    db: Session,
    campaign_id: str,
    state: RegionalGuildState,
    *,
    roster_size: int,
    region_code: str,
    slot: int,
) -> None:
    existing = list(db.scalars(select(RegionalCpuMercenary).where(
        RegionalCpuMercenary.guild_state_id == state.id,
    ).order_by(RegionalCpuMercenary.slot)))
    class_codes = [code for code in db.scalars(select(MercenaryClass.code).where(
        MercenaryClass.is_active.is_(True), MercenaryClass.code.is_not(None),
    ).order_by(MercenaryClass.id)) if code]
    class_codes = class_codes or ["warrior", "rogue", "mage", "cleric", "archer"]
    professions = list(db.scalars(select(ProfessionTemplate.code).where(
        ProfessionTemplate.is_active.is_(True),
    ).order_by(ProfessionTemplate.id)))
    rng = _rng(campaign_id, region_code, slot, "cpu-roster", VIGILIA_RULES_VERSION)
    profile_values = cpu_initial_profile_values(state.profile, regional_stage_for_region(region_code))
    base_level = int(profile_values["mercenary_level"])
    power, vitality, agility, intelligence, luck, armor = profile_values["attributes"]
    rarity = "uncommon" if state.profile == "strong" else "common"
    present_slots = {member.slot for member in existing}
    for mercenary_slot in range(1, roster_size + 1):
        if mercenary_slot in present_slots:
            continue
        variation = [rng.randint(-1, 2) for _ in range(5)]
        member_power, member_vitality, member_agility, member_intelligence, member_luck = (
            max(1, value + delta) for value, delta in zip((power, vitality, agility, intelligence, luck), variation)
        )
        profession = professions[(mercenary_slot + slot) % len(professions)] if professions else None
        member = RegionalCpuMercenary(
            campaign_id=campaign_id,
            guild_state_id=state.id,
            slot=mercenary_slot,
            name=f"{state.name} · {mercenary_slot}",
            class_code=class_codes[rng.randrange(len(class_codes))],
            level=base_level,
            rarity=rarity,
            profession_code=profession,
            power=member_power,
            vitality=member_vitality,
            agility=member_agility,
            intelligence=member_intelligence,
            luck=member_luck,
            armor=armor,
            equipment_bonus_json="{}",
            active=True,
        )
        db.add(member)
    db.flush()

    resource_rows = list(db.scalars(select(RegionalCpuResource).where(
        RegionalCpuResource.guild_state_id == state.id,
    )))
    resource_codes = {item.resource_code for item in resource_rows}
    for resource_code in CPU_RESOURCE_CODES:
        if resource_code in resource_codes:
            continue
        amount = (
            int(profile_values["gold"]) if resource_code == "gold"
            else 0 if resource_code == "xp"
            else int(profile_values["material"])
        )
        db.add(RegionalCpuResource(
            campaign_id=campaign_id,
            guild_state_id=state.id,
            resource_code=resource_code,
            amount=amount,
            capacity=1_000_000 if resource_code == "xp" else int(profile_values["capacity"]),
        ))
    db.flush()
    roster = list(db.scalars(select(RegionalCpuMercenary).where(
        RegionalCpuMercenary.guild_state_id == state.id,
        RegionalCpuMercenary.active.is_(True),
    )))
    state.roster_size = len(roster)
    state.power = sum(_cpu_member_power(member) for member in roster)


def _cpu_member_power(member: RegionalCpuMercenary) -> int:
    bonus = json.loads(member.equipment_bonus_json or "{}")
    attributes = {
        "power": member.power + int(bonus.get("power", 0)),
        "vitality": member.vitality + int(bonus.get("vitality", 0)),
        "agility": member.agility + int(bonus.get("agility", 0)),
        "intelligence": member.intelligence + int(bonus.get("intelligence", 0)),
        "luck": member.luck + int(bonus.get("luck", 0)),
        "armor": member.armor + int(bonus.get("armor", 0)),
    }
    return calculate_power_score(attributes)


def ensure_campaign_world(db: Session, campaign: CampaignMetadata, guild: Guild) -> RegionalWorldState:
    campaign_id = campaign.campaign_id
    world = db.get(RegionalWorldState, campaign_id)
    if world is None:
        world = RegionalWorldState(campaign_id=campaign_id, rules_version=VIGILIA_RULES_VERSION)
        db.add(world)
        db.flush()

    regions_by_name = {name: code for code, name in REGIONS}
    home_code = regions_by_name.get(campaign.home_region)
    if home_code is None:
        home_code, _home_name = REGIONS[0]
    region_rows = {row.region_code: row for row in db.scalars(select(RegionalRegionState).where(
        RegionalRegionState.campaign_id == campaign_id,
    ))}
    for code, name in REGIONS:
        if code not in region_rows:
            row = RegionalRegionState(
                campaign_id=campaign_id,
                region_code=code,
                region_name=name,
                security=50,
                threat=25,
                influence=0,
            )
            db.add(row)
            region_rows[code] = row
    db.flush()

    guild_rows = list(db.scalars(select(RegionalGuildState).where(
        RegionalGuildState.campaign_id == campaign_id,
    ).order_by(RegionalGuildState.region_code, RegionalGuildState.slot)))
    by_region_slot = {(row.region_code, row.slot): row for row in guild_rows}
    player_state = next((row for row in guild_rows if row.guild_id == guild.id), None)
    if player_state is None:
        player_state = next((row for row in guild_rows if row.profile == "player"), None)
    if player_state is None:
        player_state = RegionalGuildState(
            campaign_id=campaign_id,
            region_code=home_code,
            slot=0,
            guild_id=guild.id,
            name=guild.name,
            profile="player",
            archetype="player",
            roster_size=0,
            level=_guild_player_level(guild),
            power=0,
            reputation=max(0, min(100, int(guild.reputation or 0))),
            influence=0,
            event_wins=0,
            active=True,
        )
        db.add(player_state)
        db.flush()
        by_region_slot[(home_code, 0)] = player_state
    else:
        player_state.guild_id = guild.id
        player_state.region_code = home_code
        player_state.slot = 0
        player_state.name = guild.name
        player_state.level = _guild_player_level(guild)
        player_state.reputation = max(0, min(100, int(guild.reputation or 0)))
    current_power = total_player_power(db, guild)
    player_state.power = current_power
    player_state.roster_size = sum(1 for _ in db.scalars(select(Mercenary.id).where(
        Mercenary.guild_id == guild.id,
        Mercenary.status != "dismissed",
    )))

    rival_index = 0
    for region_code, _region_name in REGIONS:
        profiles = ("strong", "medium", "new", "new") if region_code == home_code else (
            "strong", "medium", "new", "new", "new"
        )
        first_slot = 1 if region_code == home_code else 0
        for offset, profile in enumerate(profiles):
            slot = first_slot + offset
            state = by_region_slot.get((region_code, slot))
            if state is None:
                archetype = RIVAL_ARCHETYPES[int(_seed_text(campaign_id, region_code, slot, "archetype")[:8], 16) % len(RIVAL_ARCHETYPES)]
                name = CPU_GUILD_NAMES[rival_index % len(CPU_GUILD_NAMES)]
                state = RegionalGuildState(
                    campaign_id=campaign_id,
                    region_code=region_code,
                    slot=slot,
                    name=name,
                    profile=profile,
                    archetype=archetype,
                    roster_size={"strong": 5, "medium": 3, "new": 1}[profile],
                    level=int(cpu_initial_profile_values(
                        profile, regional_stage_for_region(region_code),
                    )["guild_level"]),
                    xp=0,
                    power=0,
                    reputation=0,
                    influence=0,
                    event_wins=0,
                    active=True,
                )
                db.add(state)
                db.flush()
                by_region_slot[(region_code, slot)] = state
            _ensure_cpu_roster(
                db,
                campaign_id,
                state,
                roster_size={"strong": 5, "medium": 3, "new": 1}[profile],
                region_code=region_code,
                slot=slot,
            )
            rival_index += 1
    db.flush()
    return world


def _rank_weight_payload(stage: float) -> dict[str, object]:
    contract = rank_weights_for_stage(stage)
    dungeon_values = [max(1, round(contract[rank] * (1 + index * 0.08))) for index, rank in enumerate(RANKS)]
    total = sum(dungeon_values)
    dungeon = {rank: round(weight * 100 / total) for rank, weight in zip(RANKS, dungeon_values)}
    dungeon[RANKS[-1]] += 100 - sum(dungeon.values())
    boss_values = [max(1, round(contract[rank] * ((index + 1) ** 1.25))) for index, rank in enumerate(RANKS)]
    boss_total = sum(boss_values)
    boss = {rank: round(weight * 100 / boss_total) for rank, weight in zip(RANKS, boss_values)}
    boss[RANKS[-1]] += 100 - sum(boss.values())
    return {"stage": stage, "contract": contract, "dungeon": dungeon, "boss": boss}


def _roll_rank(rng: random.Random, weights: dict[str, int]) -> str:
    return rng.choices(RANKS, weights=[max(1, weights.get(rank, 0)) for rank in RANKS], k=1)[0]


def _roll_contract_rank_set(rng: random.Random, weights: dict[str, int]) -> list[str]:
    counts = {rank: 0 for rank in RANKS}
    ranks: list[str] = []
    for _ in range(10):
        allowed = [weights[rank] if counts[rank] < 3 else 0 for rank in RANKS]
        rank = rng.choices(RANKS, weights=allowed, k=1)[0]
        counts[rank] += 1
        ranks.append(rank)
    return ranks


def _select_templates(pool: list[object], count: int, rng: random.Random) -> list[object]:
    if not pool:
        raise RegionalCycleError("O catálogo local não tem conteúdo ativo suficiente para a Vigília regional.")
    if len(pool) >= count:
        return rng.sample(pool, count)
    selected = list(pool)
    while len(selected) < count:
        selected.append(pool[rng.randrange(len(pool))])
    return selected[:count]


def _select_contract_templates(
    pool: list[MissionTemplate],
    count: int,
    rng: random.Random,
    guild_level: int,
    roster_level: int,
) -> list[MissionTemplate]:
    """Keep two no-building starter contracts on the level-one board when possible."""
    if guild_level <= 1 and roster_level <= 1 and count >= 2:
        starter_pool = [template for template in pool if (
            template.required_guild_level <= 1
            and template.required_min_mercenary_level <= 1
            and (template.required_building_type is None or template.required_building_level <= 0)
            and template.min_party_size <= 1 <= template.max_party_size
        )]
        guaranteed_count = min(2, len(starter_pool))
        if guaranteed_count:
            selected = rng.sample(starter_pool, guaranteed_count)
            selected_ids = {template.id for template in selected}
            remaining_pool = [template for template in pool if template.id not in selected_ids]
            remaining = _select_templates(remaining_pool, count - guaranteed_count, rng)
            return selected + remaining
    return _select_templates(pool, count, rng)


def _contract_candidates(
    db: Session,
    guild_level: int,
    roster_level: int = 1,
) -> list[MissionTemplate]:
    """Use an aspirational level-20 floor, then follow the player's real roster."""
    challenge_ceiling = max(20, max(1, int(guild_level)), max(1, int(roster_level)))
    return list(db.scalars(select(MissionTemplate).where(
        MissionTemplate.is_active.is_(True),
        ~MissionTemplate.mission_type.in_(("gathering", "long_idle")),
        MissionTemplate.required_min_mercenary_level <= challenge_ceiling,
        MissionTemplate.recommended_level <= challenge_ceiling,
    ).order_by(MissionTemplate.id)))


def _template_rank_order(template: MissionTemplate | DungeonTemplate) -> tuple[int, int, int, int, int, int]:
    """Order untouched templates from lower to higher challenge for rank labeling."""
    recommended_power = (
        int(template.recommended_power or 0)
        if isinstance(template, MissionTemplate)
        else int(template.required_total_power or template.recommended_level * 10)
    )
    required_level = (
        int(template.required_min_mercenary_level or 1)
        if isinstance(template, MissionTemplate)
        else int(template.recommended_level or 1)
    )
    return (
        int(template.recommended_level or 1),
        recommended_power,
        required_level,
        -int(template.base_success_chance),
        int(template.duration_seconds),
        int(template.base_gold_reward) + int(template.base_xp_reward),
    )


def _pair_contract_templates_with_ranks(
    templates: list[MissionTemplate],
    ranks: list[str],
) -> list[tuple[MissionTemplate, str]]:
    """Pair E→S with ascending challenge among the ten templates chosen for this board."""
    if len(templates) != len(ranks):
        raise RegionalCycleError("A quantidade de ranks deve corresponder às ofertas de contrato.")
    ordered_templates = sorted(templates, key=_template_rank_order)
    ordered_ranks = sorted(ranks, key=RANKS.index)
    return list(zip(ordered_templates, ordered_ranks))


def _add_offer(
    db: Session,
    campaign_id: str,
    cycle: RegionalCycle,
    region_code: str,
    offer_type: str,
    slot: int,
    template: MissionTemplate | DungeonTemplate,
    rank: str,
) -> RegionalOffer:
    if isinstance(template, MissionTemplate):
        mission_id, dungeon_id = template.id, None
        recommended_power = max(1, int(template.recommended_power or 0))
        level_band = template.level_band
    else:
        mission_id, dungeon_id = None, template.id
        recommended_power = max(1, int(template.required_total_power or template.recommended_level * 10))
        level_band = template.level_band
    offer = RegionalOffer(
        campaign_id=campaign_id,
        cycle_id=cycle.id,
        cycle_number=cycle.cycle_number,
        region_code=region_code,
        offer_type=offer_type,
        slot=slot,
        mission_template_id=mission_id,
        dungeon_template_id=dungeon_id,
        rank=rank,
        name_snapshot=template.name,
        description_snapshot=template.description or "",
        level_band_snapshot=level_band,
        recommended_level_snapshot=max(1, int(template.recommended_level or 1)),
        recommended_power_snapshot=recommended_power,
        min_party_size_snapshot=max(1, int(template.min_party_size or 1)),
        max_party_size_snapshot=max(1, int(template.max_party_size or 1)),
        duration_seconds_snapshot=max(1, int(template.duration_seconds)),
        gold_reward_snapshot=max(0, int(template.base_gold_reward)),
        xp_reward_snapshot=max(0, int(template.base_xp_reward)),
        success_chance_snapshot=max(5, min(95, int(template.base_success_chance))),
        status="available",
    )
    db.add(offer)
    return offer


def _materialize_cycle(
    db: Session,
    campaign: CampaignMetadata,
    guild: Guild,
    world: RegionalWorldState,
    cycle_number: int,
    region_scope: tuple[tuple[str, str], ...] | None = None,
) -> RegionalCycle:
    existing = db.scalar(select(RegionalCycle).where(
        RegionalCycle.campaign_id == campaign.campaign_id,
        RegionalCycle.cycle_number == cycle_number,
    ))
    if existing is not None:
        return existing
    epoch = _utc(campaign.created_at_utc)
    starts_at = epoch + timedelta(seconds=cycle_number * CYCLE_SECONDS)
    ends_at = starts_at + timedelta(seconds=CYCLE_SECONDS)
    power = total_player_power(db, guild)
    level = _guild_player_level(guild)
    stage = rank_progression_stage(level, power)
    weight_payload = _rank_weight_payload(stage)
    cycle = RegionalCycle(
        campaign_id=campaign.campaign_id,
        cycle_number=cycle_number,
        starts_at_utc=starts_at,
        ends_at_utc=ends_at,
        seed=_seed_text(campaign.campaign_id, cycle_number, VIGILIA_RULES_VERSION),
        rules_version=VIGILIA_RULES_VERSION,
        content_version=campaign.content_version,
        player_level_snapshot=level,
        player_power_snapshot=power,
        rank_weights_json=json.dumps(weight_payload, ensure_ascii=False, sort_keys=True),
        status="open",
    )
    db.add(cycle)
    db.flush()

    db.execute(
        text("UPDATE regional_offers SET status = 'expired' WHERE campaign_id = :campaign_id AND cycle_number < :cycle_number AND status IN ('available', 'supply_preparing')"),
        {"campaign_id": campaign.campaign_id, "cycle_number": cycle_number},
    )
    roster_level = max(db.scalars(select(Mercenary.level).where(
        Mercenary.guild_id == guild.id,
        Mercenary.status != "dismissed",
    )).all(), default=1)
    mission_candidates = _contract_candidates(db, level, roster_level)
    dungeon_candidates = list(db.scalars(select(DungeonTemplate).where(
        DungeonTemplate.is_active.is_(True),
        DungeonTemplate.content_type == "dungeon",
        DungeonTemplate.level_band.is_not(None),
    ).order_by(DungeonTemplate.id)))
    boss_candidates = list(db.scalars(select(DungeonTemplate).where(
        DungeonTemplate.is_active.is_(True),
        DungeonTemplate.content_type == "boss",
    ).order_by(DungeonTemplate.id)))

    for region_code, _region_name in (region_scope or REGIONS):
        region_rng = _rng(campaign.campaign_id, cycle_number, region_code, VIGILIA_RULES_VERSION, "offers")
        contracts = _select_contract_templates(mission_candidates, 10, region_rng, level, roster_level)
        contract_ranks = _roll_contract_rank_set(region_rng, weight_payload["contract"])
        for slot, (template, rank) in enumerate(
            _pair_contract_templates_with_ranks(contracts, contract_ranks), start=1,
        ):
            _add_offer(db, campaign.campaign_id, cycle, region_code, "contract", slot, template, rank)
        dungeons = _select_templates(dungeon_candidates, 3, region_rng)
        dungeon_ranks = sorted(
            (_roll_rank(region_rng, weight_payload["dungeon"]) for _ in dungeons),
            key=RANKS.index,
        )
        dungeons = sorted(dungeons, key=_template_rank_order)
        for slot, (template, rank) in enumerate(zip(dungeons, dungeon_ranks), start=1):
            _add_offer(
                db, campaign.campaign_id, cycle, region_code, "dungeon", slot, template,
                rank,
            )
        boss_rank = _roll_rank(region_rng, weight_payload["boss"])
        ranked_bosses = sorted(boss_candidates, key=_template_rank_order)
        if not ranked_bosses:
            raise RegionalCycleError("O catálogo local não tem chefes ativos para a Vigília regional.")
        boss_index = round(RANKS.index(boss_rank) * (len(ranked_bosses) - 1) / (len(RANKS) - 1))
        boss = ranked_bosses[boss_index]
        _add_offer(db, campaign.campaign_id, cycle, region_code, "boss", 1, boss, boss_rank)
    db.flush()
    return cycle


def _offer_sort_value(offer: RegionalOffer) -> tuple[int, int, int]:
    rank_value = RANKS.index(offer.rank) if offer.rank in RANKS else 0
    expected_value = offer.success_chance_snapshot * (offer.gold_reward_snapshot + offer.xp_reward_snapshot)
    return (rank_value, expected_value, -offer.recommended_power_snapshot)


def _cpu_plan_for_guild(
    db: Session,
    campaign_id: str,
    cycle: RegionalCycle,
    region: RegionalRegionState,
    state: RegionalGuildState,
) -> tuple[RegionalCpuCyclePlan, float, float, int, int, int]:
    existing = db.scalar(select(RegionalCpuCyclePlan).where(
        RegionalCpuCyclePlan.cycle_id == cycle.id,
        RegionalCpuCyclePlan.guild_state_id == state.id,
    ))
    if existing is not None:
        raise RegionalCycleError("Foi encontrado um plano CPU parcialmente persistido; o ciclo não foi reaplicado.")
    roster = list(db.scalars(select(RegionalCpuMercenary).where(
        RegionalCpuMercenary.guild_state_id == state.id,
        RegionalCpuMercenary.active.is_(True),
    ).order_by(RegionalCpuMercenary.slot)))
    resources = list(db.scalars(select(RegionalCpuResource).where(
        RegionalCpuResource.guild_state_id == state.id,
    ).order_by(RegionalCpuResource.resource_code)))
    resource_by_code = {item.resource_code: item for item in resources}
    before_resources = {item.resource_code: item.amount for item in resources}
    roster_snapshot = [
        {
            "slot": member.slot,
            "name": member.name,
            "class": member.class_code,
            "level": member.level,
            "rarity": member.rarity,
            "profession": member.profession_code,
            "attributes": {
                "power": member.power, "vitality": member.vitality, "agility": member.agility,
                "intelligence": member.intelligence, "luck": member.luck, "armor": member.armor,
            },
            "equipment_bonus": json.loads(member.equipment_bonus_json or "{}"),
            "total_power": _cpu_member_power(member),
        }
        for member in roster
    ]
    plan_seed = _seed_text(campaign_id, cycle.cycle_number, state.id, cycle.rules_version, "cpu-plan")
    rng = _rng(plan_seed)
    activity_rng = _rng(plan_seed, "activity")
    action_probability = regional_cpu_action_probability(campaign_id, state, cycle.rules_version)
    all_offers = list(db.scalars(select(RegionalOffer).where(
        RegionalOffer.cycle_id == cycle.id,
        RegionalOffer.region_code == region.region_code,
    ).order_by(RegionalOffer.offer_type, RegionalOffer.slot)))
    contract_offers = [offer for offer in all_offers if offer.offer_type == "contract"]
    dungeon_offers = [offer for offer in all_offers if offer.offer_type == "dungeon"]
    actions_requested = 2 if state.profile == "strong" else 1
    available_roster = list(roster)
    profession_family = {
        row.code: row.material_family
        for row in db.scalars(select(ProfessionTemplate).where(ProfessionTemplate.is_active.is_(True)))
    }
    decisions: list[dict[str, object]] = []
    outcomes: list[dict[str, object]] = []
    successes = failures = gold_earned = xp_earned = 0
    threat_delta = security_delta = 0.0
    rank_sum = 0
    action_index = 0
    for _ in range(actions_requested):
        if activity_rng.random() >= action_probability:
            continue
        use_exploration = state.archetype == "exploration" and dungeon_offers
        candidates = dungeon_offers if use_exploration else contract_offers
        if not candidates:
            candidates = all_offers
        if state.archetype == "security":
            defensive = [
                offer for offer in candidates
                if any(token in (offer.name_snapshot + " " + offer.description_snapshot).casefold()
                       for token in ("patrulha", "vigia", "guarda", "defesa", "ameaça"))
            ]
            candidates = defensive or candidates
        candidates = [
            offer for offer in candidates
            if offer.status == "available"
            and offer.min_party_size_snapshot <= len(available_roster)
            and offer.min_party_size_snapshot <= offer.max_party_size_snapshot
        ]
        if not candidates:
            continue
        action_index += 1
        if state.archetype == "exploration" and candidates:
            offer = max(candidates, key=lambda row: (_offer_sort_value(row), -row.id))
        elif state.archetype == "security" and candidates:
            offer = min(candidates, key=lambda row: (row.recommended_power_snapshot, row.id))
        else:
            offer = max(candidates, key=lambda row: (_offer_sort_value(row), -row.id))
        offer.status = "cpu_completed"
        offer.reserved_by_guild_state_id = state.id
        party_size = offer.min_party_size_snapshot
        party = rng.sample(available_roster, party_size)
        available_ids = {member.id for member in party}
        available_roster = [member for member in available_roster if member.id not in available_ids]
        member_power = sum(_cpu_member_power(member) for member in party)
        class_bonus = min(8, sum(CLASS_SUCCESS_BONUS.get(member.class_code, 0) for member in party))
        chance = max(
            5,
            min(
                95,
                offer.success_chance_snapshot
                + power_success_adjustment(member_power, offer.recommended_power_snapshot)
                + class_bonus,
            ),
        )
        success = rng.randint(1, 100) <= chance
        rank_value = RANKS.index(offer.rank) + 1
        rank_sum += rank_value
        action_type = "exploration" if offer.offer_type in {"dungeon", "boss"} else state.archetype
        decisions.append({
            "action": action_index,
            "type": action_type,
            "offer_id": offer.id,
            "offer_type": offer.offer_type,
            "rank": offer.rank,
            "mercenary_slots": [member.slot for member in party],
            "chance": chance,
        })
        reward_gold = offer.gold_reward_snapshot if success else 0
        reward_xp = offer.xp_reward_snapshot if success else max(0, offer.xp_reward_snapshot // 4)
        if success:
            successes += 1
            gold_earned += reward_gold
            xp_earned += reward_xp * len(party)
            gold_resource = resource_by_code.get("gold")
            if gold_resource is not None:
                gold_resource.amount = min(gold_resource.capacity, gold_resource.amount + reward_gold)
            xp_resource = resource_by_code.get("xp")
            if xp_resource is not None:
                xp_resource.amount = min(xp_resource.capacity, xp_resource.amount + reward_xp * len(party))
            member = party[0]
            family = profession_family.get(member.profession_code or "")
            resource_code = PROFESSION_RESOURCE_CODES.get(member.profession_code or "", family or "")
            material_resource = resource_by_code.get(resource_code)
            if material_resource is not None:
                material_resource.amount = min(material_resource.capacity, material_resource.amount + 1)
            positive = regional_outcome_impact(offer.rank)
            security_delta += positive
            threat_delta -= positive
            state.influence = min(100, state.influence + rank_value)
            state.reputation = min(100, state.reputation + rank_value)
            _apply_cpu_xp(state, party, reward_xp * len(party))
        else:
            failures += 1
            negative = regional_outcome_impact(offer.rank)
            threat_delta += negative
            security_delta -= negative
            state.influence = min(100, state.influence + 1)
            state.reputation = max(0, state.reputation - max(1, rank_value // 2))
            xp_resource = resource_by_code.get("xp")
            if xp_resource is not None:
                xp_resource.amount = min(xp_resource.capacity, xp_resource.amount + reward_xp * len(party))
            _apply_cpu_xp(state, party, reward_xp * len(party))
        outcomes.append({
            "action": action_index,
            "offer_id": offer.id,
            "rank": offer.rank,
            "success": success,
            "gold": reward_gold,
            "xp": reward_xp,
            "contribution": rank_value,
        })
    state.power = sum(_cpu_member_power(member) for member in roster)
    state.roster_size = len(roster)
    after_resources = {item.resource_code: item.amount for item in resources}
    plan = RegionalCpuCyclePlan(
        campaign_id=campaign_id,
        cycle_id=cycle.id,
        guild_state_id=state.id,
        seed=plan_seed,
        roster_snapshot_json=json.dumps(roster_snapshot, ensure_ascii=False, sort_keys=True),
        resources_before_json=json.dumps(before_resources, sort_keys=True),
        resources_after_json=json.dumps(after_resources, sort_keys=True),
        decisions_json=json.dumps(decisions, ensure_ascii=False, sort_keys=True),
        outcomes_json=json.dumps(outcomes, ensure_ascii=False, sort_keys=True),
        actions=len(decisions),
        successes=successes,
        failures=failures,
        gold_earned=gold_earned,
        xp_earned=xp_earned,
    )
    db.add(plan)
    # Portal/rebellion activity ledgers use the plan ID as their source run.
    # Assign it before _process_cycle links CPU results to an active event.
    db.flush()
    return plan, threat_delta, security_delta, successes, failures, rank_sum


def _apply_cpu_xp(state: RegionalGuildState, roster: list[RegionalCpuMercenary], xp_gain: int) -> None:
    if xp_gain <= 0 or state.level >= GUILD_MAX_LEVEL:
        return
    state.xp += xp_gain // 10
    while state.level < GUILD_MAX_LEVEL:
        required = GUILD_XP_BASE + (state.level - 1) * GUILD_XP_GROWTH
        if state.xp < required:
            break
        state.xp -= required
        state.level += 1
        for member in roster:
            member.level += 1
            if member.class_code in {"knight", "warrior", "blade", "reaper", "paladin", "sentinel"}:
                member.power += 1
            elif member.class_code in {"cleric", "priest", "high_priest", "templar"}:
                member.vitality += 1
            elif member.class_code in {"mage", "wizard", "arcane", "mentalist", "warlock"}:
                member.intelligence += 1
            else:
                member.agility += 1
    if state.level >= GUILD_MAX_LEVEL:
        state.level = GUILD_MAX_LEVEL
        state.xp = 0


def _process_cycle(db: Session, campaign_id: str, cycle: RegionalCycle, world: RegionalWorldState) -> None:
    if cycle.status == "completed":
        return
    if cycle.status != "open":
        raise RegionalCycleError("O ciclo regional tem um estado inválido e foi preservado.")
    # Materialize priority-expired rebellions before CPU plans are generated so
    # the first cycle whose start follows the priority deadline can participate.
    from app.services.regional_event_service import expire_due_events

    expire_due_events(db, campaign_id, cycle.starts_at_utc)
    regions = list(db.scalars(select(RegionalRegionState).where(
        RegionalRegionState.campaign_id == campaign_id,
    ).order_by(RegionalRegionState.region_code)))
    for region in regions:
        existing_snapshot = db.scalar(select(RegionalCycleRegion).where(
            RegionalCycleRegion.cycle_id == cycle.id,
            RegionalCycleRegion.region_code == region.region_code,
        ))
        if existing_snapshot is not None:
            raise RegionalCycleError("O histórico regional parcial não será aplicado novamente.")
        previous_region_snapshot = None
        if cycle.cycle_number > 0:
            previous_cycle = db.scalar(select(RegionalCycle).where(
                RegionalCycle.campaign_id == campaign_id,
                RegionalCycle.cycle_number == cycle.cycle_number - 1,
            ))
            if previous_cycle is not None:
                previous_region_snapshot = db.scalar(select(RegionalCycleRegion).where(
                    RegionalCycleRegion.cycle_id == previous_cycle.id,
                    RegionalCycleRegion.region_code == region.region_code,
                ))
        before = (
            (previous_region_snapshot.security_after,
             previous_region_snapshot.threat_after,
             previous_region_snapshot.influence_after)
            if previous_region_snapshot is not None
            else (50.0, 25.0, 0)
        )
        security = float(region.security)
        threat = float(region.threat)
        cpu_actions = successes = failures = gold_earned = xp_earned = 0
        cpu_guilds = list(db.scalars(select(RegionalGuildState).where(
            RegionalGuildState.campaign_id == campaign_id,
            RegionalGuildState.region_code == region.region_code,
            RegionalGuildState.guild_id.is_(None),
            RegionalGuildState.active.is_(True),
        ).order_by(RegionalGuildState.slot)))
        archetype_totals: dict[str, int] = {}
        for cpu in cpu_guilds:
            plan, threat_delta, security_delta, action_successes, action_failures, _rank_sum = _cpu_plan_for_guild(
                db, campaign_id, cycle, region, cpu
            )
            from app.services.regional_event_service import record_cpu_event_activity

            portal_security_delta, portal_threat_delta = record_cpu_event_activity(
                db, campaign_id, cycle, region.region_code, plan
            )
            cpu_actions += plan.actions
            successes += action_successes
            failures += action_failures
            gold_earned += plan.gold_earned
            xp_earned += plan.xp_earned
            security = round(max(0.0, min(100.0,
                security + security_delta + portal_security_delta)), 4)
            threat = round(max(0.0, min(100.0,
                threat + threat_delta + portal_threat_delta)), 4)
            archetype_totals[cpu.archetype] = archetype_totals.get(cpu.archetype, 0) + plan.actions
        player_outcomes = list(db.scalars(
            select(RegionalRunOutcome)
            .join(RegionalGuildState, RegionalGuildState.id == RegionalRunOutcome.guild_state_id)
            .where(
                RegionalRunOutcome.campaign_id == campaign_id,
                RegionalRunOutcome.applied_cycle_number == cycle.cycle_number,
                RegionalGuildState.region_code == region.region_code,
                RegionalGuildState.profile == "player",
            )
        ))
        player_started_offer_ids = set(db.scalars(
            select(RegionalOffer.id)
            .join(RegionalGuildState, RegionalGuildState.id == RegionalOffer.reserved_by_guild_state_id)
            .where(
                RegionalOffer.campaign_id == campaign_id,
                RegionalOffer.cycle_number == cycle.cycle_number,
                RegionalOffer.region_code == region.region_code,
                RegionalGuildState.profile == "player",
                RegionalOffer.status.in_(("player_reserved", "in_progress", "completed", "failed")),
            )
        ))
        player_action_ids = player_started_offer_ids | {outcome.offer_id for outcome in player_outcomes}
        player_successes = sum(outcome.success for outcome in player_outcomes)
        player_failures = len(player_outcomes) - player_successes
        baseline_applied = cpu_actions + len(player_action_ids) == 0
        if baseline_applied:
            security = max(0.0, min(100.0, security - REGION_BASELINE_PRESSURE))
            threat = max(0.0, min(100.0, threat + REGION_BASELINE_PRESSURE))
        strong_rival = next((row for row in cpu_guilds if row.profile == "strong"), None)
        calm = rival_calm_for_cycle(
            cycle.cycle_number,
            cycle.rules_version,
            strong_rival is not None,
            baseline_applied,
        )
        calm["source_guild_state_id"] = strong_rival.id if calm["active"] and strong_rival else None
        security = max(0.0, min(100.0, security + float(calm["security"])))
        threat = max(0.0, min(100.0, threat + float(calm["threat"])))
        guilds = list(db.scalars(select(RegionalGuildState.influence).where(
            RegionalGuildState.campaign_id == campaign_id,
            RegionalGuildState.region_code == region.region_code,
        )))
        influence = max(0, min(100, round(sum(guilds) / max(1, len(guilds)))))
        region.security, region.threat, region.influence = security, threat, influence
        region.last_updated_cycle = cycle.cycle_number
        db.add(RegionalCycleRegion(
            campaign_id=campaign_id,
            cycle_id=cycle.id,
            region_code=region.region_code,
            security_before=before[0],
            threat_before=before[1],
            influence_before=before[2],
            security_after=security,
            threat_after=threat,
            influence_after=influence,
            cpu_actions=cpu_actions,
            cpu_successes=successes,
            cpu_failures=failures,
            cpu_gold_earned=gold_earned,
            cpu_xp_earned=xp_earned,
            summary_json=json.dumps({
                "baseline": {
                    "applied": baseline_applied,
                    "security": -REGION_BASELINE_PRESSURE if baseline_applied else 0,
                    "threat": REGION_BASELINE_PRESSURE if baseline_applied else 0,
                },
                "rival_calm": calm,
                "player_actions": len(player_action_ids),
                "player_successes": player_successes,
                "player_failures": player_failures,
                "actions_by_archetype": archetype_totals,
                "successes": successes,
                "failures": failures,
            }, ensure_ascii=False, sort_keys=True),
        ))
    cycle.status = "completed"
    cycle.processed_at_utc = datetime.now(timezone.utc)
    world.last_completed_cycle = max(world.last_completed_cycle, cycle.cycle_number)
    from app.services.regional_event_service import create_cycle_portals

    create_cycle_portals(db, campaign_id, cycle, regions)
    db.flush()


def advance_regional_world(
    db: Session,
    campaign: CampaignMetadata,
    guild: Guild,
    now: datetime | None = None,
) -> RegionalCycle:
    world = ensure_campaign_world(db, campaign, guild)
    current_time = _now(now)
    elapsed = max(0.0, (current_time - _utc(campaign.created_at_utc)).total_seconds())
    target_cycle = int(elapsed // CYCLE_SECONDS)
    target_cycle = max(target_cycle, world.last_materialized_cycle)
    for cycle_number in range(world.last_materialized_cycle + 1, target_cycle + 1):
        try:
            if cycle_number > 0:
                previous = db.scalar(select(RegionalCycle).where(
                    RegionalCycle.campaign_id == campaign.campaign_id,
                    RegionalCycle.cycle_number == cycle_number - 1,
                ))
                if previous is None:
                    raise RegionalCycleError("Falta um snapshot anterior; o calendário regional não avançou.")
                _process_cycle(db, campaign.campaign_id, previous, world)
            current = _materialize_cycle(db, campaign, guild, world, cycle_number)
            world.last_materialized_cycle = cycle_number
            world.rules_version = VIGILIA_RULES_VERSION
            db.add(world)
            db.commit()
            db.refresh(current)
        except Exception:
            db.rollback()
            raise
    active_cycle = db.scalar(select(RegionalCycle).where(
        RegionalCycle.campaign_id == campaign.campaign_id,
        RegionalCycle.cycle_number == world.last_materialized_cycle,
    ))
    if active_cycle is None:
        active_cycle = _materialize_cycle(db, campaign, guild, world, max(0, world.last_materialized_cycle))
        world.last_materialized_cycle = active_cycle.cycle_number
        db.add(world)
        db.commit()
        db.refresh(active_cycle)
    return active_cycle


def get_regional_board(
    db: Session,
    campaign: CampaignMetadata,
    guild: Guild,
    now: datetime | None = None,
) -> dict[str, object]:
    active_cycle = advance_regional_world(db, campaign, guild, now)
    from app.services.regional_event_service import (
        active_rebellion,
        active_portals_for_region,
        evaluate_open_rebellion,
        event_history_for_campaign,
        expire_due_events,
    )

    current_time = _now(now)
    expire_due_events(db, campaign.campaign_id, current_time)
    evaluate_open_rebellion(db, campaign, active_cycle, guild.id, current_time)
    home_code = next((code for code, name in REGIONS if name == campaign.home_region), REGIONS[0][0])
    home_region = db.scalar(select(RegionalRegionState).where(
        RegionalRegionState.campaign_id == campaign.campaign_id,
        RegionalRegionState.region_code == home_code,
    ))
    regions = list(db.scalars(select(RegionalRegionState).where(
        RegionalRegionState.campaign_id == campaign.campaign_id,
    ).order_by(RegionalRegionState.region_name)))
    guild_states = list(db.scalars(select(RegionalGuildState).where(
        RegionalGuildState.campaign_id == campaign.campaign_id,
    )))
    rankings = []
    for state in guild_states:
        score = round(
            state.influence * 0.5
            + state.reputation * 0.25
            + min(100, state.event_wins * 10) * 0.25,
            2,
        )
        rankings.append((score, state))
    rankings.sort(key=lambda entry: (-entry[0], entry[1].name.casefold()))
    offer_rows = list(db.scalars(select(RegionalOffer).where(
        RegionalOffer.cycle_id == active_cycle.id,
        RegionalOffer.region_code == home_code,
    ).order_by(RegionalOffer.offer_type, RegionalOffer.slot)))
    offers = {"contract": [], "dungeon": [], "boss": []}
    for offer in offer_rows:
        offers.setdefault(offer.offer_type, []).append(offer)
    latest_history = list(db.scalars(
        select(RegionalCycleRegion)
        .join(RegionalCycle, RegionalCycle.id == RegionalCycleRegion.cycle_id)
        .where(
            RegionalCycleRegion.campaign_id == campaign.campaign_id,
            RegionalCycleRegion.region_code == home_code,
            RegionalCycle.status == "completed",
        )
        .order_by(RegionalCycle.cycle_number.desc())
        .limit(8)
    ))
    portal_events = active_portals_for_region(db, campaign.campaign_id, home_code)
    rebellion_event = active_rebellion(db, campaign.campaign_id)
    event_history = event_history_for_campaign(db, campaign.campaign_id)
    open_offers = [offer for offer in offers["contract"] + offers["dungeon"] + offers["boss"] if offer.status in {"available", "supply_preparing"}]
    return {
        "world": db.get(RegionalWorldState, campaign.campaign_id),
        "cycle": active_cycle,
        "home_region": home_region,
        "regions": regions,
        "rankings": [{"score": score, "guild": state} for score, state in rankings],
        "offers": offers,
        "latest_history": latest_history,
        "portal_events": portal_events,
        "rebellion_event": rebellion_event,
        "event_history": event_history,
        "available_mercenaries": list(db.scalars(select(Mercenary).where(
            Mercenary.guild_id == guild.id,
            Mercenary.status == "available",
        ).order_by(Mercenary.level.desc(), Mercenary.id))),
        "active_offer_count": len(open_offers),
        "rank_progression_stage": json.loads(active_cycle.rank_weights_json).get("stage", 0.0),
        "contract_rank_weights": json.loads(active_cycle.rank_weights_json).get("contract", {}),
        "region_names": dict(REGIONS),
    }


def get_current_player_regional_guild(db: Session, campaign_id: str, guild_id: int) -> RegionalGuildState | None:
    return db.scalar(select(RegionalGuildState).where(
        RegionalGuildState.campaign_id == campaign_id,
        RegionalGuildState.guild_id == guild_id,
    ))


def record_player_offer_result(
    db: Session,
    guild: Guild,
    *,
    source_type: str,
    source_run_id: int,
    offer_id: int | None,
    success: bool,
    gold_earned: int,
    xp_earned: int,
) -> None:
    if not guild.campaign_id or offer_id is None:
        return
    existing = db.scalar(select(RegionalRunOutcome).where(
        RegionalRunOutcome.campaign_id == guild.campaign_id,
        RegionalRunOutcome.source_type == source_type,
        RegionalRunOutcome.source_run_id == source_run_id,
    ))
    if existing is not None:
        return
    offer = db.get(RegionalOffer, offer_id)
    player_state = get_current_player_regional_guild(db, guild.campaign_id, guild.id)
    region = db.scalar(select(RegionalRegionState).where(
        RegionalRegionState.campaign_id == guild.campaign_id,
        RegionalRegionState.region_code == (offer.region_code if offer else ""),
    ))
    world = db.get(RegionalWorldState, guild.campaign_id)
    if offer is None or player_state is None or region is None or world is None:
        return
    applied_cycle = max(0, world.last_materialized_cycle)
    rank_value = RANKS.index(offer.rank) + 1 if offer.rank in RANKS else 1
    contribution = rank_value if success else 1
    if success:
        impact = regional_outcome_impact(offer.rank)
        region.security = round(min(100.0, region.security + impact), 4)
        region.threat = round(max(0.0, region.threat - impact), 4)
        player_state.influence = min(100, player_state.influence + rank_value)
        guild.reputation = max(0, int(guild.reputation or 0) + rank_value)
    else:
        delta = regional_outcome_impact(offer.rank)
        region.security = round(max(0.0, region.security - delta), 4)
        region.threat = round(min(100.0, region.threat + delta), 4)
        player_state.influence = min(100, player_state.influence + 1)
        guild.reputation = max(0, int(guild.reputation or 0) - max(1, rank_value // 2))
    player_state.reputation = max(0, min(100, guild.reputation))
    player_state.power = total_player_power(db, guild)
    db.flush()
    event_activity = db.scalar(select(RegionalEventActivity).where(
        RegionalEventActivity.source_type == source_type,
        RegionalEventActivity.source_run_id == source_run_id,
        RegionalEventActivity.status == "in_progress",
    ))
    if event_activity is not None:
        event_activity.contribution = contribution
        event = db.get(RegionalEvent, event_activity.event_id)
        if event is not None and event.event_type == "rebellion" and player_state.region_code != region.region_code:
            home_region = db.scalar(select(RegionalRegionState).where(
                RegionalRegionState.campaign_id == guild.campaign_id,
                RegionalRegionState.region_code == player_state.region_code,
            ))
            if home_region is not None:
                home_influences = list(db.scalars(select(RegionalGuildState.influence).where(
                    RegionalGuildState.campaign_id == guild.campaign_id,
                    RegionalGuildState.region_code == home_region.region_code,
                )))
                home_region.influence = max(0, min(100, round(
                    sum(home_influences) / max(1, len(home_influences))
                )))
                home_region.last_updated_cycle = applied_cycle
                db.add(home_region)
        db.add(event_activity)
    regional_guild_influences = list(db.scalars(select(RegionalGuildState.influence).where(
        RegionalGuildState.campaign_id == guild.campaign_id,
        RegionalGuildState.region_code == region.region_code,
    )))
    region.influence = max(0, min(100, round(
        sum(regional_guild_influences) / max(1, len(regional_guild_influences))
    )))
    region.last_updated_cycle = applied_cycle
    if offer.status == "in_progress":
        offer.status = "completed" if success else "failed"
        offer.resolved_at_utc = datetime.now(timezone.utc)
    db.add_all([region, player_state, guild, offer])
    db.add(RegionalRunOutcome(
        campaign_id=guild.campaign_id,
        guild_state_id=player_state.id,
        offer_id=offer.id,
        source_type=source_type,
        source_run_id=source_run_id,
        offer_cycle_number=offer.cycle_number,
        applied_cycle_number=applied_cycle,
        rank=offer.rank,
        success=success,
        contribution=contribution,
        gold_earned=max(0, gold_earned),
        xp_earned=max(0, xp_earned),
    ))
    db.flush()
