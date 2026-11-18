"""Compare the live contract candidate rule with the pre-ML-050 CPU rule."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database.connection import configure_database, create_database_engine
from app.models.regional import (
    RegionalCpuCyclePlan,
    RegionalCpuMercenary,
    RegionalCycle,
    RegionalEventActivity,
    RegionalGuildState,
    RegionalOffer,
)
from app.services import regional_cycle_service
from app.services.campaign_service import CampaignService


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED_START = 2026110301
DEFAULT_CAMPAIGN_COUNT = 5
DEFAULT_HORIZON = 100
PROFILE_NAMES = ("strong", "medium", "new")
ACTION_TYPES = ("contract", "dungeon", "boss", "portal", "other")


def _previous_contract_candidates(db, guild_level: int, roster_level: int = 1):
    """Reproduce the candidate filter immediately before ML-050."""
    from app.models.mission import MissionTemplate

    challenge_ceiling = max(20, max(1, int(guild_level)), max(1, int(roster_level)))
    return list(db.scalars(select(MissionTemplate).where(
        MissionTemplate.is_active.is_(True),
        ~MissionTemplate.mission_type.in_(("gathering", "long_idle")),
        MissionTemplate.required_min_mercenary_level <= challenge_ceiling,
        MissionTemplate.recommended_level <= challenge_ceiling,
    ).order_by(MissionTemplate.id)))


def _blank_profile_metrics() -> dict[str, object]:
    return {
        "cpu_guild_states": 0,
        "action_starts_by_type": {kind: 0 for kind in ACTION_TYPES},
        "xp_earned": 0,
        "guild_level_final_sum": 0,
        "guild_level_gain_sum": 0,
        "mercenary_level_final_sum": 0,
        "active_mercenary_count": 0,
        "max_inactive_streak_sum": 0,
        "max_inactive_streak": 0,
        "active_cycles": 0,
        "possible_guild_cycles": 0,
    }


def _derive_metrics(raw: dict[str, object]) -> dict[str, object]:
    starts = raw["action_starts_by_type"]
    assert isinstance(starts, dict)
    combat_starts = sum(int(starts[kind]) for kind in ("contract", "dungeon", "boss"))
    dungeon_boss_starts = int(starts["dungeon"]) + int(starts["boss"])
    guild_count = int(raw["cpu_guild_states"])
    active_mercenary_count = int(raw["active_mercenary_count"])
    possible_cycles = int(raw["possible_guild_cycles"])
    return {
        "cpu_guild_states": guild_count,
        "action_starts_by_type": dict(starts),
        "activity_starts_total": sum(int(value) for value in starts.values()),
        "dungeon_boss_share_of_contract_dungeon_boss_starts": round(
            dungeon_boss_starts / max(1, combat_starts), 4,
        ),
        "xp_earned": int(raw["xp_earned"]),
        "mean_final_guild_level": round(int(raw["guild_level_final_sum"]) / max(1, guild_count), 2),
        "mean_guild_level_gain": round(int(raw["guild_level_gain_sum"]) / max(1, guild_count), 2),
        "mean_final_active_mercenary_level": round(
            int(raw["mercenary_level_final_sum"]) / max(1, active_mercenary_count), 2,
        ),
        "active_mercenaries": active_mercenary_count,
        "mean_max_inactive_streak": round(
            int(raw["max_inactive_streak_sum"]) / max(1, guild_count), 2,
        ),
        "longest_inactive_streak": int(raw["max_inactive_streak"]),
        "guild_cycles_with_activity_percent": round(
            100 * int(raw["active_cycles"]) / max(1, possible_cycles), 2,
        ),
    }


def _sum_raw_metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    total = _blank_profile_metrics()
    total_starts = total["action_starts_by_type"]
    assert isinstance(total_starts, dict)
    for row in rows:
        for key in (
            "cpu_guild_states", "xp_earned", "guild_level_final_sum", "guild_level_gain_sum",
            "mercenary_level_final_sum", "active_mercenary_count", "max_inactive_streak_sum",
            "active_cycles", "possible_guild_cycles",
        ):
            total[key] = int(total[key]) + int(row[key])
        total["max_inactive_streak"] = max(
            int(total["max_inactive_streak"]), int(row["max_inactive_streak"]),
        )
        row_starts = row["action_starts_by_type"]
        assert isinstance(row_starts, dict)
        for kind in ACTION_TYPES:
            total_starts[kind] += int(row_starts[kind])
    return total


def _validate_raw_profile(profile: str, row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise ValueError(f"profile {profile}: metrics must be a JSON object")
    required = _blank_profile_metrics()
    missing = sorted(set(required) - set(row))
    if missing:
        raise ValueError(f"profile {profile}: missing required metrics: {', '.join(missing)}")
    starts = row["action_starts_by_type"]
    if not isinstance(starts, dict):
        raise ValueError(f"profile {profile}: action_starts_by_type must be an object")
    missing_actions = sorted(set(ACTION_TYPES) - set(starts))
    if missing_actions:
        raise ValueError(
            f"profile {profile}: missing action counts: {', '.join(missing_actions)}",
        )
    numeric_fields = set(required) - {"action_starts_by_type"}
    for field in numeric_fields:
        value = row[field]
        if type(value) is not int or value < 0:
            raise ValueError(f"profile {profile}: {field} must be a nonnegative integer")
    for action in ACTION_TYPES:
        value = starts[action]
        if type(value) is not int or value < 0:
            raise ValueError(f"profile {profile}: action count {action} must be a nonnegative integer")
    return row


def _source_hashes() -> dict[str, str]:
    sources = set((ROOT / "app").rglob("*.py"))
    sources.update({
        ROOT / "scripts/balance/compare_ml050_cpu_campaigns.py",
        ROOT / "scripts/balance/simulate_regional_cpu_campaigns.py",
        ROOT / "requirements.txt",
        ROOT / "requirements-desktop-dev.txt",
    })
    result = {}
    for path in sorted(path for path in sources if path.is_file()):
        relative = path.relative_to(ROOT).as_posix()
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _configuration(args: argparse.Namespace) -> dict[str, object]:
    return {
        "seed_start": args.seed_start,
        "campaign_count": args.campaign_count,
        "horizon_cycles": args.horizon_cycles,
        "seeds": list(range(args.seed_start, args.seed_start + args.campaign_count)),
        "profiles": list(PROFILE_NAMES),
        "variants": ["previous", "ml050"],
        "action_types": list(ACTION_TYPES),
        "app_mode": os.environ.get("APP_MODE", ""),
        "python_version": platform.python_version(),
        "source_sha256": _source_hashes(),
    }


def _configuration_sha256(configuration: dict[str, object]) -> str:
    encoded = json.dumps(configuration, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _write_json_atomic(path: Path, value: dict[str, object]) -> None:
    temporary_path = path.with_name(f"{path.name}.tmp")
    temporary_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    temporary_path.replace(path)


def _load_or_create_checkpoint(
    checkpoint_path: Path,
    configuration: dict[str, object],
    configuration_sha256: str,
) -> dict[str, object]:
    if checkpoint_path.exists():
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"checkpoint is unreadable; preserving it: {checkpoint_path}") from exc
        if checkpoint.get("configuration") != configuration:
            raise ValueError(
                "checkpoint configuration/source hashes differ from the current run; "
                "refusing to mix or overwrite results",
            )
        if checkpoint.get("configuration_sha256") != configuration_sha256:
            raise ValueError("checkpoint configuration digest does not match its recorded inputs")
        if checkpoint.get("schema_version") != 1 or not isinstance(checkpoint.get("results"), dict):
            raise ValueError("checkpoint schema is invalid; preserving it")
        return checkpoint
    return {
        "schema_version": 1,
        "configuration": configuration,
        "configuration_sha256": configuration_sha256,
        "template_campaign_id": str(UUID(int=0)),
        "template_ready": False,
        "template_sha256": None,
        "results": {},
        "status": "running",
    }


def _validate_checkpoint_results(
    checkpoint: dict[str, object], configuration: dict[str, object], *, require_complete: bool,
) -> None:
    result_map = checkpoint["results"]
    assert isinstance(result_map, dict)
    expected_seeds = [str(seed) for seed in configuration["seeds"]]
    variants = configuration["variants"]
    assert isinstance(variants, list)
    unexpected_seeds = sorted(set(result_map) - set(expected_seeds))
    if unexpected_seeds:
        raise ValueError(f"checkpoint contains unexpected seeds: {', '.join(unexpected_seeds)}")
    for seed in expected_seeds:
        seed_result = result_map.get(seed, {})
        if not isinstance(seed_result, dict):
            raise ValueError(f"checkpoint seed {seed} must contain an object")
        for variant in variants:
            arm = seed_result.get(variant)
            if arm is None:
                if require_complete:
                    raise ValueError(f"checkpoint is incomplete: seed {seed}, variant {variant}")
                continue
            if not isinstance(arm, dict) or not isinstance(arm.get("profiles"), dict):
                raise ValueError(f"checkpoint arm is malformed: seed {seed}, variant {variant}")
            if type(arm.get("cpu_actions_total")) is not int or type(arm.get("cpu_xp_net")) is not int:
                raise ValueError(f"checkpoint runner totals are missing: seed {seed}, variant {variant}")
            profiles = arm["profiles"]
            for profile in configuration["profiles"]:
                if profile not in profiles:
                    raise ValueError(
                        f"checkpoint is missing profile {profile}: seed {seed}, variant {variant}",
                    )
                _validate_raw_profile(profile, profiles[profile])


def _aggregate_checkpoint(
    checkpoint: dict[str, object], checkpoint_path: Path, output_prefix: Path,
) -> dict[str, object]:
    configuration = checkpoint["configuration"]
    assert isinstance(configuration, dict)
    _validate_checkpoint_results(checkpoint, configuration, require_complete=True)
    raw_results = checkpoint["results"]
    assert isinstance(raw_results, dict)
    paired_results = []
    campaign_summaries = []
    runner_totals = []
    for seed_value in configuration["seeds"]:
        seed = int(seed_value)
        arms = raw_results[str(seed)]
        paired_row = {"seed": seed}
        summary_row = {"seed": seed}
        runner_row = {"seed": seed}
        for variant in configuration["variants"]:
            arm = arms[variant]
            profiles = arm["profiles"]
            paired_row[variant] = profiles
            summary_row[variant] = {
                profile: _derive_metrics(_validate_raw_profile(profile, profiles[profile]))
                for profile in configuration["profiles"]
            }
            runner_row[variant] = {
                "cpu_actions_total": arm["cpu_actions_total"],
                "cpu_xp_net": arm["cpu_xp_net"],
            }
        paired_results.append(paired_row)
        campaign_summaries.append(summary_row)
        runner_totals.append(runner_row)

    profile_summary = {}
    for profile in configuration["profiles"]:
        profile_summary[profile] = {}
        for variant in configuration["variants"]:
            total = _sum_raw_metrics([row[variant][profile] for row in paired_results])
            profile_summary[profile][variant] = _derive_metrics(total)
    report = {
        "card": "ML-050",
        "seed_start": configuration["seed_start"],
        "seeds": configuration["seeds"],
        "horizon_cycles": configuration["horizon_cycles"],
        "runner": "simulator live services with identical seeded SQLite content, deterministic campaign UUIDs, and separate disposable databases",
        "previous_rule": "recommended_level and required_min_mercenary_level <= max(20, guild_level, roster_level)",
        "ml050_rule": "guild-level recommendation bands for 1-99; previous ceiling unchanged at 100+",
        "data_source": {
            "checkpoint": checkpoint_path.name,
            "configuration_sha256": checkpoint["configuration_sha256"],
            "source_sha256": configuration["source_sha256"],
            "profile_metrics": "raw per-profile counters saved after each seed/variant completed",
            "runner_totals": "cpu_actions_total and cpu_xp_net returned by the live campaign simulator",
        },
        "campaigns": campaign_summaries,
        "runner_totals_by_campaign": runner_totals,
        "profile_summary": profile_summary,
    }
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path, markdown_path = output_prefix.with_suffix(".json"), output_prefix.with_suffix(".md")
    json_temporary = json_path.with_name(f"{json_path.name}.tmp")
    markdown_temporary = markdown_path.with_name(f"{markdown_path.name}.tmp")
    json_temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_temporary.write_text(_build_markdown(report), encoding="utf-8")
    json_temporary.replace(json_path)
    markdown_temporary.replace(markdown_path)
    return report


def _campaign_profile_metrics(seed: int, saves_root: Path, horizon: int) -> dict[str, dict[str, object]]:
    campaign_id = str(UUID(int=seed))
    database_path = saves_root / f"{campaign_id}.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        with factory() as db:
            states = list(db.scalars(select(RegionalGuildState).where(
                RegionalGuildState.campaign_id == campaign_id,
                RegionalGuildState.guild_id.is_(None),
            ).order_by(RegionalGuildState.id)))
            states_by_id = {state.id: state for state in states}
            cycles = {
                cycle.id: cycle.cycle_number
                for cycle in db.scalars(select(RegionalCycle).where(
                    RegionalCycle.campaign_id == campaign_id,
                    RegionalCycle.cycle_number < horizon,
                ))
            }
            offers = {
                offer.id: offer
                for offer in db.scalars(select(RegionalOffer).where(
                    RegionalOffer.campaign_id == campaign_id,
                    RegionalOffer.cycle_number < horizon,
                ))
            }
            plans = list(db.scalars(select(RegionalCpuCyclePlan).where(
                RegionalCpuCyclePlan.campaign_id == campaign_id,
            )))
            plans_by_id = {plan.id: plan for plan in plans}
            starts_by_state = defaultdict(Counter)
            starts_by_state_cycle = defaultdict(Counter)
            xp_by_state = Counter()
            for plan in plans:
                cycle_number = cycles.get(plan.cycle_id)
                state = states_by_id.get(plan.guild_state_id)
                if cycle_number is None or state is None:
                    continue
                xp_by_state[state.id] += int(plan.xp_earned or 0)
                decisions = json.loads(plan.decisions_json or "[]")
                categorized = 0
                for decision in decisions:
                    offer = offers.get(int(decision.get("offer_id") or 0))
                    action_type = offer.offer_type if offer is not None else "other"
                    if action_type not in ACTION_TYPES:
                        action_type = "other"
                    starts_by_state[state.id][action_type] += 1
                    starts_by_state_cycle[(state.id, cycle_number)][action_type] += 1
                    categorized += 1
                unclassified_starts = max(0, int(plan.started_actions or 0) - categorized)
                if unclassified_starts:
                    starts_by_state[state.id]["other"] += unclassified_starts
                    starts_by_state_cycle[(state.id, cycle_number)]["other"] += unclassified_starts

            for activity in db.scalars(select(RegionalEventActivity).join(
                RegionalCpuCyclePlan,
                RegionalCpuCyclePlan.id == RegionalEventActivity.source_run_id,
            ).where(
                RegionalEventActivity.source_type == "cpu_portal",
                RegionalCpuCyclePlan.campaign_id == campaign_id,
            )):
                plan = plans_by_id.get(activity.source_run_id)
                cycle_number = cycles.get(plan.cycle_id) if plan is not None else None
                if cycle_number is not None:
                    starts_by_state[activity.guild_state_id]["portal"] += 1
                    starts_by_state_cycle[(activity.guild_state_id, cycle_number)]["portal"] += 1

            mercenaries_by_state = defaultdict(list)
            for mercenary in db.scalars(select(RegionalCpuMercenary).where(
                RegionalCpuMercenary.campaign_id == campaign_id,
                RegionalCpuMercenary.active.is_(True),
            )):
                mercenaries_by_state[mercenary.guild_state_id].append(int(mercenary.level or 1))

            profile_rows: dict[str, list[dict[str, object]]] = {name: [] for name in PROFILE_NAMES}
            for state in states:
                initial_values = regional_cycle_service.cpu_initial_profile_values(
                    state.profile,
                    regional_cycle_service.regional_stage_for_region(state.region_code),
                )
                idle_streak = longest_idle_streak = 0
                active_cycles = 0
                for cycle_number in range(horizon):
                    cycle_starts = starts_by_state_cycle[(state.id, cycle_number)]
                    had_activity = sum(cycle_starts.values()) > 0
                    if had_activity:
                        active_cycles += 1
                        idle_streak = 0
                    else:
                        idle_streak += 1
                        longest_idle_streak = max(longest_idle_streak, idle_streak)
                mercenary_levels = mercenaries_by_state[state.id]
                profile_rows[state.profile].append({
                    "state_id": state.id,
                    "level_final": int(state.level),
                    "level_gain": int(state.level) - int(initial_values["guild_level"]),
                    "xp_earned": int(xp_by_state[state.id]),
                    "starts_by_type": dict(starts_by_state[state.id]),
                    "active_mercenary_levels": mercenary_levels,
                    "max_inactive_streak": longest_idle_streak,
                    "active_cycles": active_cycles,
                })

            result = {name: _blank_profile_metrics() for name in PROFILE_NAMES}
            for profile, rows in profile_rows.items():
                metric = result[profile]
                metric["cpu_guild_states"] = len(rows)
                metric["possible_guild_cycles"] = len(rows) * horizon
                starts = metric["action_starts_by_type"]
                assert isinstance(starts, dict)
                for row in rows:
                    metric["guild_level_final_sum"] += int(row["level_final"])
                    metric["guild_level_gain_sum"] += int(row["level_gain"])
                    metric["xp_earned"] += int(row["xp_earned"])
                    metric["max_inactive_streak_sum"] += int(row["max_inactive_streak"])
                    metric["max_inactive_streak"] = max(
                        int(metric["max_inactive_streak"]), int(row["max_inactive_streak"]),
                    )
                    metric["active_cycles"] += int(row["active_cycles"])
                    for kind, value in row["starts_by_type"].items():
                        if kind in starts:
                            starts[kind] += int(value)
                    for level in row["active_mercenary_levels"]:
                        metric["mercenary_level_final_sum"] += int(level)
                        metric["active_mercenary_count"] += 1
                result[profile] = metric
            return result
    finally:
        engine.dispose()


def _fmt_pair(before: float | int, after: float | int, suffix: str = "") -> str:
    return f"{before}{suffix} → {after}{suffix} ({after - before:+g}{suffix})"


def _build_markdown(report: dict[str, object]) -> str:
    summaries = report["profile_summary"]
    assert isinstance(summaries, dict)
    lines = [
        "# ML-050 — comparação pareada de atividade CPU",
        "",
        f"Seeds: {', '.join(str(seed) for seed in report['seeds'])} · "
        f"{report['horizon_cycles']} Vigílias por campanha.",
        "",
        "A linha anterior usa o filtro de candidatos anterior ao ML-050. A nova linha usa a faixa de contratos "
        "por nível da guilda. Cada par reutiliza o mesmo banco de conteúdo, UUID de campanha e seed; cada braço "
        "escreve em uma pasta descartável separada.",
        "",
        "Ações contam inícios de contratos, masmorras, chefes e entradas CPU em portais. A fração de masmorras/chefes "
        "usa apenas contratos, masmorras e chefes no denominador. XP é a soma registrada nos planos CPU. O ganho "
        "de nível compara o nível final da guilda CPU com o nível inicial determinístico de seu perfil/região.",
        "",
        f"Métricas brutas por seed/variante: `{report['data_source']['checkpoint']}`. "
        f"Configuração SHA-256: `{report['data_source']['configuration_sha256']}`.",
        "",
        "| Perfil | Ações totais antes → depois | Contratos | Masmorras | Chefes | Quota masmorras/chefes | XP antes → depois | Nível final da guilda | Nível médio do elenco | Maior sequência sem atividade |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for profile in PROFILE_NAMES:
        row = summaries[profile]
        before = row["previous"]
        after = row["ml050"]
        before_starts = before["action_starts_by_type"]
        after_starts = after["action_starts_by_type"]
        lines.append(
            f"| {profile} | {_fmt_pair(before['activity_starts_total'], after['activity_starts_total'])} | "
            f"{_fmt_pair(before_starts['contract'], after_starts['contract'])} | "
            f"{_fmt_pair(before_starts['dungeon'], after_starts['dungeon'])} | "
            f"{_fmt_pair(before_starts['boss'], after_starts['boss'])} | "
            f"{_fmt_pair(100 * before['dungeon_boss_share_of_contract_dungeon_boss_starts'], 100 * after['dungeon_boss_share_of_contract_dungeon_boss_starts'], '%')} | "
            f"{_fmt_pair(before['xp_earned'], after['xp_earned'])} | "
            f"{_fmt_pair(before['mean_final_guild_level'], after['mean_final_guild_level'])} "
            f"(ganho {_fmt_pair(before['mean_guild_level_gain'], after['mean_guild_level_gain'])}) | "
            f"{_fmt_pair(before['mean_final_active_mercenary_level'], after['mean_final_active_mercenary_level'])} | "
            f"{before['longest_inactive_streak']} → {after['longest_inactive_streak']} ciclos |"
        )
    lines.extend([
        "",
        "O relatório mantém o efeito observado por perfil para revisão; nenhuma compensação de CPU foi aplicada.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT))
    from scripts.balance import simulate_regional_cpu_campaigns as simulator

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEED_START)
    parser.add_argument("--campaign-count", type=int, default=DEFAULT_CAMPAIGN_COUNT)
    parser.add_argument("--horizon-cycles", type=int, default=DEFAULT_HORIZON)
    parser.add_argument("--output-prefix", default="reports/ml050_cpu_paired_2026-11-17")
    parser.add_argument(
        "--aggregate-only", action="store_true",
        help="build the report from a complete checkpoint without running campaigns",
    )
    args = parser.parse_args()
    if args.campaign_count < 1 or args.horizon_cycles < 1:
        parser.error("--campaign-count and --horizon-cycles must be positive")

    output_prefix = Path(args.output_prefix)
    if not output_prefix.is_absolute():
        output_prefix = ROOT / output_prefix
    outputs = (output_prefix.with_suffix(".json"), output_prefix.with_suffix(".md"))
    checkpoint_path = output_prefix.with_name(f"{output_prefix.name}.checkpoint.json")
    checkpoint_dir = output_prefix.with_name(f".{output_prefix.name}_state")
    configuration = _configuration(args)
    configuration_sha256 = _configuration_sha256(configuration)
    try:
        checkpoint = _load_or_create_checkpoint(
            checkpoint_path, configuration, configuration_sha256,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if any(path.exists() for path in outputs):
        matching_existing_report = False
        if args.aggregate_only and outputs[0].is_file():
            try:
                previous_report = json.loads(outputs[0].read_text(encoding="utf-8"))
                matching_existing_report = (
                    previous_report.get("data_source", {}).get("configuration_sha256")
                    == configuration_sha256
                )
            except (OSError, json.JSONDecodeError, AttributeError):
                matching_existing_report = False
        if not matching_existing_report:
            parser.error(f"refusing to overwrite an existing report: {output_prefix}")

    if args.aggregate_only:
        try:
            _validate_checkpoint_results(checkpoint, configuration, require_complete=True)
            _aggregate_checkpoint(checkpoint, checkpoint_path, output_prefix)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.error(f"cannot aggregate checkpoint: {exc}")
        print(f"JSON: {outputs[0]}")
        print(f"Markdown: {outputs[1]}")
        return

    simulator.HORIZON = args.horizon_cycles
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    template_saves = checkpoint_dir / "template_saves"
    campaigns = CampaignService(template_saves)
    template_campaign_id = str(checkpoint["template_campaign_id"])
    try:
        template = campaigns.inspect_campaign(template_campaign_id)
    except FileNotFoundError:
        if checkpoint["template_ready"]:
            parser.error("checkpoint template save is missing; preserving checkpoint and refusing a new template")
        with patch("app.services.campaign_service.uuid4", return_value=UUID(template_campaign_id)):
            template = campaigns.create_campaign(
                "ML-050 CPU baseline template", "Guilda de Teste ML-050",
            )
    if not checkpoint["template_ready"]:
        campaigns.activate_campaign(template_campaign_id)
        template = campaigns.inspect_campaign(template_campaign_id)
        checkpoint["template_ready"] = True
        checkpoint["template_sha256"] = hashlib.sha256(
            template.database_path.read_bytes(),
        ).hexdigest()
        _write_json_atomic(checkpoint_path, checkpoint)
    else:
        template_hash = hashlib.sha256(template.database_path.read_bytes()).hexdigest()
        if template_hash != checkpoint["template_sha256"]:
            parser.error("checkpoint template database hash changed; refusing to mix campaign results")

    result_map = checkpoint["results"]
    assert isinstance(result_map, dict)
    try:
        _validate_checkpoint_results(checkpoint, configuration, require_complete=False)
        with tempfile.TemporaryDirectory(prefix="ml050-cpu-paired-run-", dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            for index, seed in enumerate(configuration["seeds"], start=1):
                seed_result = result_map.setdefault(str(seed), {})
                assert isinstance(seed_result, dict)
                for variant in configuration["variants"]:
                    if variant in seed_result:
                        print(
                            f"[{index}/{args.campaign_count}] {variant} seed={seed} recovered from checkpoint",
                            flush=True,
                        )
                        continue
                    saves_root = temp_root / "campaigns" / variant / str(seed)
                    saves_root.mkdir(parents=True, exist_ok=True)
                    if variant == "previous":
                        with patch.object(
                            regional_cycle_service, "_contract_candidates", new=_previous_contract_candidates,
                        ):
                            campaign_result = simulator.run_campaign(
                                seed, saves_root, template.database_path,
                            )
                    else:
                        campaign_result = simulator.run_campaign(
                            seed, saves_root, template.database_path,
                        )
                    profiles = _campaign_profile_metrics(seed, saves_root, args.horizon_cycles)
                    for profile in configuration["profiles"]:
                        _validate_raw_profile(profile, profiles[profile])
                    seed_result[variant] = {
                        "profiles": profiles,
                        "cpu_actions_total": int(campaign_result["cpu_actions_total"]),
                        "cpu_xp_net": int(campaign_result["cpu_xp_net"]),
                    }
                    _write_json_atomic(checkpoint_path, checkpoint)
                    print(
                        f"[{index}/{args.campaign_count}] {variant} seed={seed} "
                        f"actions={campaign_result['cpu_actions_total']} xp={campaign_result['cpu_xp_net']} (checkpointed)",
                        flush=True,
                    )
        _validate_checkpoint_results(checkpoint, configuration, require_complete=True)
        checkpoint["status"] = "complete"
        _write_json_atomic(checkpoint_path, checkpoint)
        _aggregate_checkpoint(checkpoint, checkpoint_path, output_prefix)
    finally:
        configure_database("sqlite:///:memory:")
    print(f"JSON: {outputs[0]}")
    print(f"Markdown: {outputs[1]}")


if __name__ == "__main__":
    main()
