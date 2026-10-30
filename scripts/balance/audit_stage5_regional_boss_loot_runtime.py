"""Aggregate regional boss loot via start/claim services on disposable SQLite."""
from __future__ import annotations

import json
import math
import random
import sys
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import Base, create_database_engine
from app.models.campaign import CampaignMetadata
from app.models.dungeon import DungeonTemplate
from app.models.guild import Guild, GuildResources
from app.models.item import GuildItemInstance, ItemTemplate
from app.models.mercenary import Mercenary, MercenaryClass
from app.models.regional import RegionalCycle, RegionalOffer
from app.seeds.campaign_content import apply_initial_campaign_content
from app.services import dungeon_service
from app.services.building_service import ensure_guild_buildings
from app.services.dungeon_service import claim_dungeon_loot, start_dungeon
from app.services.equipment_service import create_equipment_instance_from_template, get_party_power_score
from app.services.mercenary_service import equip_mercenary_item
from app.services.regional_cycle_service import REGIONS, _add_offer, _template_rank_order, ensure_campaign_world
from app.services.result_detail_service import parse_result_details

RANKS = ("E", "D", "C", "B", "A", "S")
PROFILES = (("near_requirement", 1.02), ("overpowered", 1.50))
REPORT_STEM = "stage5_regional_boss_loot_runtime_2026-10-30"
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _mean_ci(values: list[int]) -> dict[str, float | int]:
    n = len(values)
    mean = sum(values) / n if n else 0.0
    if n < 2:
        half = 0.0
    else:
        variance = sum((value - mean) ** 2 for value in values) / (n - 1)
        half = 1.96 * math.sqrt(variance / n)
    return {"mean": round(mean, 3), "ci95_low": round(max(0.0, mean - half), 3),
            "ci95_high": round(mean + half, 3), "n": n}


def _wilson(successes: int, n: int) -> dict[str, float | int]:
    if not n:
        return {"rate": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "n": 0}
    z = 1.96
    p = successes / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {"rate": round(p, 4), "ci95_low": round(center - half, 4),
            "ci95_high": round(center + half, 4), "n": n}


def run_audit(n_per_cell: int = 10_000, seed: int = 20261030,
              selected_ranks: tuple[str, ...] = RANKS,
              selected_profiles: tuple[str, ...] = tuple(profile for profile, _ in PROFILES)) -> dict[str, object]:
    randomizer = random.Random(seed)
    with TemporaryDirectory(prefix="gim-stage5-boss-loot-") as temp:
        engine = create_database_engine(f"sqlite:///{(Path(temp) / 'loot.sqlite3').as_posix()}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            with factory() as db:
                apply_initial_campaign_content(db)
                campaign = CampaignMetadata(
                    campaign_id="stage5-boss-loot-runtime", campaign_name="Boss loot runtime audit",
                    created_at_utc=EPOCH, updated_at_utc=EPOCH, schema_version=5,
                    content_version=3, home_region=REGIONS[0][1],
                )
                guild = Guild(campaign_id=campaign.campaign_id, name="Regional boss audit", level=50)
                resources = GuildResources(guild=guild, gold=1_000_000_000)
                db.add_all((campaign, guild, resources))
                db.flush()
                ensure_campaign_world(db, campaign, guild)
                buildings = ensure_guild_buildings(db, guild.id)
                for row in buildings:
                    if row.building_template.effect_type in {"explorers", "scouts"}:
                        row.level = 100
                all_classes = list(db.scalars(select(MercenaryClass).where(MercenaryClass.is_active.is_(True))))
                by_code = {row.code: row for row in all_classes if row.code}
                by_role = {
                    "tank": [row for row in all_classes if (row.role_type or "").lower() == "tank"],
                    "support": [row for row in all_classes if (row.role_type or "").lower() == "support"],
                    "damage": [row for row in all_classes if (row.role_type or "").lower() not in {"tank", "support"}],
                }
                if any(not values for values in by_role.values()):
                    raise RuntimeError("Catálogo de classes não cobre tank, support e damage.")
                party = []
                for index in range(5):
                    member = Mercenary(
                        guild_id=guild.id, class_id=by_role["damage"][index % len(by_role["damage"])].id,
                        name=f"Boss audit {index + 1}",
                        level=500, xp=0, status="available", rarity="epic", hire_cost=0,
                        power=1, vitality=0, agility=0, intelligence=0, luck=0,
                    )
                    party.append(member)
                db.add_all(party)
                db.flush()
                bosses = list(db.scalars(select(DungeonTemplate).where(
                    DungeonTemplate.is_active.is_(True), DungeonTemplate.content_type == "boss",
                )))
                boss_pool = sorted(bosses, key=_template_rank_order)
                if len(boss_pool) < len(RANKS):
                    raise RuntimeError(f"Esperava ao menos {len(RANKS)} bosses seedados; achei {len(boss_pool)}.")
                templates = {}
                for rank in RANKS:
                    index = round(RANKS.index(rank) * (len(boss_pool) - 1) / (len(RANKS) - 1))
                    templates[rank] = boss_pool[index]

                # Give the funded team derived power close to each template's exact requirement.
                # All other attributes stay present so the production power formula is used.
                rows = []
                cell_results: dict[str, dict[str, list]] = {}
                for rank_index, rank in enumerate(RANKS):
                    if rank not in selected_ranks:
                        continue
                    template = templates[rank]
                    role_plan = ["tank"] * template.required_tank_count + ["support"] * template.required_support_count
                    role_plan += ["damage"] * template.required_damage_count
                    if len(role_plan) > 5:
                        raise RuntimeError(f"{rank}/{template.name} requer mais de cinco papéis.")
                    role_plan += ["damage"] * (5 - len(role_plan))
                    selected_classes = []
                    for role in role_plan:
                        if template.required_class_code and template.required_class_code in by_code:
                            required_class = by_code[template.required_class_code]
                            if (required_class.role_type or "").lower() == role and not any(c.id == required_class.id for c in selected_classes):
                                selected_classes.append(required_class)
                                continue
                        selected_classes.append(by_role[role][0])
                    if template.required_class_code and template.required_class_code in by_code and all(
                        c.id != by_code[template.required_class_code].id for c in selected_classes
                    ):
                        replace_at = next((index for index, role in enumerate(role_plan)
                                           if role == (by_code[template.required_class_code].role_type or "damage").lower()), None)
                        if replace_at is not None:
                            selected_classes[replace_at] = by_code[template.required_class_code]
                    for member, cls in zip(party, selected_classes):
                        member.class_id = cls.id
                    db.flush()
                    for member in party:
                        db.refresh(member, attribute_names=["mercenary_class"])
                    # Equip only the gate tier for this boss; weak ranks remain measurable near their own requirement.
                    tier = int(template.required_equipment_tier or 0)
                    if tier:
                        gear = db.scalar(select(ItemTemplate).where(
                            ItemTemplate.item_type == "equipment", ItemTemplate.tier >= tier,
                            ItemTemplate.equipment_slot == "necklace", ItemTemplate.required_level <= 500,
                        ).order_by(ItemTemplate.tier, ItemTemplate.required_level, ItemTemplate.id))
                        if gear is None:
                            raise RuntimeError(f"Seed sem colar para Tier {tier}.")
                        for member in party:
                            equipped = list(db.scalars(select(GuildItemInstance).where(
                                GuildItemInstance.guild_id == guild.id,
                                GuildItemInstance.equipped_to_mercenary_id == member.id,
                            )))
                            for instance in equipped:
                                instance.equipped_to_mercenary_id = None
                            db.flush()
                            instance = create_equipment_instance_from_template(db, guild.id, gear)
                            db.flush()
                            equip_mercenary_item(db, guild, member.id, str(instance.id))
                    for profile_index, (profile, ratio) in enumerate(PROFILES):
                        if profile not in selected_profiles:
                            continue
                        required = max(1, int(template.required_total_power or template.recommended_level * 10))
                        target = math.ceil(required * ratio)
                        for member in party:
                            member.power = max(1, math.ceil(target / 5))
                        db.flush()
                        actual_power = get_party_power_score(db, guild.id, party)
                        party[0].power = max(1, party[0].power + target - actual_power)
                        db.flush()
                        actual_power = get_party_power_score(db, guild.id, party)
                        key = f"{rank}:{profile}"
                        successes = 0
                        gold_values = []
                        xp_values = []
                        equipment_per_attempt = []
                        materials_per_attempt = []
                        material_overflow_per_attempt = []
                        item_drop_attempts = []
                        item_counts = Counter()
                        equipment_before = db.scalar(select(func.count(GuildItemInstance.id))) or 0
                        cycle_no = rank_index * 2 + profile_index
                        cycle = RegionalCycle(
                            campaign_id=campaign.campaign_id, cycle_number=cycle_no,
                            starts_at_utc=EPOCH + timedelta(days=cycle_no),
                            ends_at_utc=EPOCH + timedelta(days=cycle_no, hours=6),
                            seed=f"boss-loot-{seed}-{rank}-{profile}", rules_version="vigilia-v3",
                            content_version=3, player_level_snapshot=500, player_power_snapshot=actual_power,
                            rank_weights_json="{}", status="open",
                        )
                        db.add(cycle)
                        db.flush()
                        for attempt in range(n_per_cell):
                            offer = _add_offer(db, campaign.campaign_id, cycle, REGIONS[0][0], "boss", attempt, template, rank)
                            db.flush()
                            offer.status = "in_progress"
                            start_at = EPOCH + timedelta(days=cycle_no, hours=1)
                            with patch.object(dungeon_service, "utc_now", return_value=start_at):
                                try:
                                    run = start_dungeon(
                                        db, guild, str(template.id), [str(member.id) for member in party], commit=False,
                                        regional_duration_seconds=template.duration_seconds,
                                        regional_success_chance=offer.success_chance_snapshot,
                                        regional_recommended_power=offer.recommended_power_snapshot,
                                        regional_recommended_level=offer.recommended_level_snapshot,
                                    )
                                except Exception as error:
                                    raise RuntimeError(
                                        f"Start {rank}/{profile} {template.name}: party={[(m.mercenary_class.code, m.level) for m in party]}, "
                                        f"required roles={template.required_tank_count}/{template.required_support_count}/{template.required_damage_count}, "
                                        f"required class={template.required_class_code}, size={template.min_party_size}-{template.max_party_size}; {error}"
                                    ) from error
                            run.regional_offer_id = offer.id
                            run.rank_snapshot = rank
                            end_at = run.ends_at
                            item_totals = {"equipment": 0, "materials": 0, "materials_stored": 0,
                                           "materials_discarded": 0}
                            original_create_equipment = dungeon_service.create_equipment_instance_from_template
                            original_add_inventory = dungeon_service.add_inventory_quantity_capped

                            def capture_equipment(*args, **kwargs):
                                instance = original_create_equipment(*args, **kwargs)
                                item_totals["equipment"] += 1
                                return instance

                            def capture_material(*args, **kwargs):
                                result = original_add_inventory(*args, **kwargs)
                                item_totals["materials_stored"] += int(result[0])
                                item_totals["materials_discarded"] += int(result[1])
                                item_totals["materials"] += int(result[0]) + int(result[1])
                                return result

                            with patch.object(dungeon_service, "utc_now", return_value=end_at), \
                                    patch.object(dungeon_service, "randint", side_effect=lambda a, b: randomizer.randint(a, b)), \
                                    patch.object(dungeon_service, "create_equipment_instance_from_template", side_effect=capture_equipment), \
                                    patch.object(dungeon_service, "add_inventory_quantity_capped", side_effect=capture_material):
                                claimed = claim_dungeon_loot(db, guild, resources, run.id, commit=False)
                            successes += int(bool(claimed.success))
                            gold_values.append(int(claimed.gold_reward or 0))
                            xp_values.append(int(claimed.xp_reward or 0) * len(party))
                            equipment_per_attempt.append(item_totals["equipment"])
                            materials_per_attempt.append(item_totals["materials"])
                            material_overflow_per_attempt.append(item_totals["materials_discarded"])
                            item_drop_attempts.append(int(item_totals["equipment"] + item_totals["materials"] > 0))
                            details = parse_result_details(claimed.result_details)
                            for item in details.get("items", []):
                                item_counts[str(item).split(" x", 1)[0]] += 1
                            if attempt % 100 == 99:
                                db.flush()
                                db.expunge(run)
                                if attempt % 1000 == 999:
                                    print(f"{rank}/{profile}: {attempt + 1}/{n_per_cell} claims", flush=True)
                            else:
                                db.flush()
                        equipment_after = db.scalar(select(func.count(GuildItemInstance.id))) or 0
                        cell_results[key] = {
                            "rank": rank, "profile": profile, "template_id": template.id,
                            "template_name": template.name, "template_level_band": template.level_band,
                            "required_total_power": required, "party_power": actual_power,
                            "power_ratio": round(actual_power / required, 4), "n_attempts": n_per_cell,
                            "wins": successes, "failures": n_per_cell - successes,
                            "success_rate_wilson95": _wilson(successes, n_per_cell),
                            "attempts_with_any_item_drop": sum(item_drop_attempts),
                            "any_item_drop_probability_wilson95": _wilson(sum(item_drop_attempts), n_per_cell),
                            "gold_per_attempt": _mean_ci(gold_values), "team_xp_per_attempt": _mean_ci(xp_values),
                            "equipment_instances_per_attempt": _mean_ci(equipment_per_attempt),
                            "material_units_per_attempt": _mean_ci(materials_per_attempt),
                            "material_units_discarded_per_attempt": _mean_ci(material_overflow_per_attempt),
                            "items_per_attempt": {"count": sum(item_counts.values()), "by_item": dict(item_counts)},
                            "equipment_instances_created": equipment_after - equipment_before,
                        }
                        rows.append(cell_results[key])
                return {
                    "report_id": REPORT_STEM, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "seed": seed, "n_per_rank_power_cell": n_per_cell,
                    "method": "fixed rank/template per production rank mapping; all runs start and claim through services; RNG is seeded, not forced; funded L50 roster; success/failure included",
                    "rank_selection": "boss template index selected with production rank-to-boss-pool mapping; rank incidence itself is conditional and not estimated",
                    "power_profiles": "near_requirement targets 1.02x; overpowered targets 1.50x; reported power is computed by get_party_power_score",
                    "selected_ranks": list(selected_ranks), "selected_profiles": list(selected_profiles),
                    "cells": rows,
                }
        finally:
            engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=10_000, help="claims per rank × power cell")
    parser.add_argument("--seed", type=int, default=20261030)
    parser.add_argument("--ranks", nargs="+", choices=RANKS, default=RANKS)
    parser.add_argument("--profiles", nargs="+", choices=tuple(profile for profile, _ in PROFILES),
                        default=tuple(profile for profile, _ in PROFILES))
    args = parser.parse_args()
    report = run_audit(n_per_cell=args.n, seed=args.seed,
                       selected_ranks=tuple(args.ranks), selected_profiles=tuple(args.profiles))
    suffix = "" if len(args.ranks) == len(RANKS) and len(args.profiles) == len(PROFILES) else "_" + "".join(args.ranks) + "_" + "_".join(args.profiles)
    path = ROOT / "reports" / f"{REPORT_STEM}{suffix}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Loot de chefes regionais por rank e perfil de poder", "",
             f"N={report['n_per_rank_power_cell']} por célula rank × poder; SQLite temporário. Ranks condicionados, sem estimar incidência.", "",
             "| Rank | Perfil | Chefe | Poder/requisito | N | Vitórias (IC95% Wilson) | Tentativas com item (IC95% Wilson) | Ouro/tentativa IC95% | XP equipe/tentativa IC95% | Equip./tentativa IC95% | Materiais gerados/tentativa IC95% | Materiais descartados/tentativa IC95% |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in report["cells"]:
        wins = row["success_rate_wilson95"]
        gold = row["gold_per_attempt"]
        xp = row["team_xp_per_attempt"]
        drops = row["any_item_drop_probability_wilson95"]
        equipment = row["equipment_instances_per_attempt"]
        materials = row["material_units_per_attempt"]
        discarded = row["material_units_discarded_per_attempt"]
        lines.append(f"| {row['rank']} | {row['profile']} | {row['template_name']} | {row['power_ratio']:.2f}× | {row['n_attempts']} | {row['wins']}/{row['n_attempts']} ({wins['rate']:.1%}; {wins['ci95_low']:.1%}–{wins['ci95_high']:.1%}) | {row['attempts_with_any_item_drop']}/{row['n_attempts']} ({drops['rate']:.1%}; {drops['ci95_low']:.1%}–{drops['ci95_high']:.1%}) | {gold['mean']:.1f} ({gold['ci95_low']:.1f}–{gold['ci95_high']:.1f}) | {xp['mean']:.1f} ({xp['ci95_low']:.1f}–{xp['ci95_high']:.1f}) | {equipment['mean']:.3f} ({equipment['ci95_low']:.3f}–{equipment['ci95_high']:.3f}) | {materials['mean']:.3f} ({materials['ci95_low']:.3f}–{materials['ci95_high']:.3f}) | {discarded['mean']:.3f} ({discarded['ci95_low']:.3f}–{discarded['ci95_high']:.3f}) |")
    lines.extend(["", "As recompensas são totais realizados via claim: ouro de vitória (zero em falha), XP incluindo o grupo, drops de materiais e equipamentos contados no serviço. Claims usam RNG seeded sem forçar vitória/loot. Os IC95% de médias são aproximações normais; taxas usam Wilson. Resultados condicionados aos ranks e uma composição financiada, sem estimar frequência natural de rank. Nenhum save real foi aberto.", ""])
    (ROOT / "reports" / f"{REPORT_STEM}{suffix}.md").write_text("\n".join(lines), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
