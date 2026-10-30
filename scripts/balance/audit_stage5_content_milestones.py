"""Audit live-content gates relevant to first equipment and dungeon milestones."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import Base, create_database_engine
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop, MissionTemplateItemDrop
from app.seeds.campaign_content import apply_initial_campaign_content
from app.services.regional_event_service import (
    PORTAL_BASE_CHANCE, PORTAL_MAX_CHANCE, PORTAL_MIN_THREAT,
    PORTAL_TTL, REBELLION_CHANCE, REBELLION_MAX_SECURITY, REBELLION_MIN_THREAT,
)
from scripts.balance.funded_progression_simulation import STRATEGIES
from scripts.balance.simulate_guild_progression_profiles import Profile, _eligible_templates


def _profile_spec(strategy: dict[str, object]) -> Profile:
    return Profile(
        name=str(strategy["name"]), mode=str(strategy["mode"]),
        online_hours_per_day=float(strategy["online_hours"]),
        slots=int(strategy["teams"]), party_size=int(strategy["party_size"]),
        party_selection_policy="selectable",
    )


def _audit(db) -> dict[str, object]:
    by_profile = {}
    for strategy in STRATEGIES:
        profile = _profile_spec(strategy)
        first_gear = None
        first_normal_dungeon = None
        for guild_level in range(1, 51):
            missions = [mission for mission in _eligible_templates(db, profile, guild_level)
                        if mission.required_min_mercenary_level <= guild_level]
            drops = [drop for mission in missions for drop in mission.item_drops
                     if drop.is_active and drop.item_template
                     and drop.item_template.item_type == "equipment"]
            if first_gear is None and drops:
                first_gear = {
                    "guild_level": guild_level,
                    "mission_catalog_count": len({drop.mission_template_id for drop in drops}),
                    "unique_equipment_templates": len({drop.item_template_id for drop in drops}),
                    "base_drop_chance_percent_min": min(int(drop.drop_chance) for drop in drops),
                    "base_drop_chance_percent_median": median(int(drop.drop_chance) for drop in drops),
                    "base_drop_chance_percent_max": max(int(drop.drop_chance) for drop in drops),
                    "candidate_mission_names": sorted({drop.mission_template.name for drop in drops})[:5],
                }
            if first_normal_dungeon is None:
                candidates = list(db.scalars(
                    select(DungeonTemplate)
                    .options(selectinload(DungeonTemplate.item_drops).selectinload(DungeonTemplateItemDrop.item_template))
                    .where(DungeonTemplate.is_active.is_(True), DungeonTemplate.content_type == "dungeon")
                ))
                candidates = [template for template in candidates
                              if template.min_party_size <= profile.party_size <= template.max_party_size
                              and template.required_guild_level <= guild_level
                              and template.required_min_mercenary_level <= guild_level
                              and (not template.required_building_type
                                   or template.required_building_type == "scouts"
                                   and template.required_building_level <= 1)]
                if candidates:
                    template = min(candidates, key=lambda item: (
                        item.required_guild_level, item.required_min_mercenary_level,
                        item.recommended_level, item.id,
                    ))
                    equip_drops = [drop for drop in template.item_drops
                                   if drop.is_active and drop.item_template
                                   and drop.item_template.item_type == "equipment"]
                    first_normal_dungeon = {
                        "guild_and_mercenary_level_at_least": guild_level,
                        "party_size": profile.party_size,
                        "required_building": "Exploradores 1",
                        "catalog_name": template.name,
                        "recommended_level": int(template.recommended_level),
                        "base_success_chance_percent": int(template.base_success_chance),
                        "equipment_drop_chance_percent": int(equip_drops[0].drop_chance) if equip_drops else None,
                        "dungeon_duration_minutes": round(int(template.duration_seconds) / 60, 1),
                    }
        by_profile[str(strategy["name"])] = {
            "online_hours_per_day_assumption": strategy["online_hours"],
            "planned_party_size": strategy["party_size"],
            "first_catalog_mission_equipment_opportunity": first_gear,
            "first_normal_dungeon_after_building_gate": first_normal_dungeon,
            "days_to_first_equipment": None,
            "days_to_first_dungeon": None,
            "reason_days_unestimated": "The funded trajectory does not materialize per-action equipment loot, does not buy Scouts, and does not run dungeons.",
        }

    portal_curve = {}
    for threat, chance in ((70, PORTAL_BASE_CHANCE), (85, PORTAL_BASE_CHANCE + 15 * (0.20 / 30)),
                           (100, PORTAL_MAX_CHANCE)):
        portal_curve[str(threat)] = {
            "per_eligible_region_vigilia_percent": round(chance * 100, 2),
            "chance_after_1_10_20_eligible_opportunities_percent": {
                str(count): round((1 - (1 - chance) ** count) * 100, 2) for count in (1, 10, 20)
            },
        }
    rebellion_curve = {
        str(count): round((1 - (1 - REBELLION_CHANCE) ** count) * 100, 2)
        for count in (1, 10, 50, 100)
    }
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "content_seed": "apply_initial_campaign_content (current source, temporary SQLite)",
        "profiles": by_profile,
        "regional_event_gates": {
            "first_portal_possible_at_threat": PORTAL_MIN_THREAT,
            "portal_chance_at_threshold_percent": round(PORTAL_BASE_CHANCE * 100, 2),
            "portal_chance_cap_percent": round(PORTAL_MAX_CHANCE * 100, 2),
            "portal_entry_deadline_hours_including_offline": PORTAL_TTL.total_seconds() / 3600,
            "rebellion_requires_threat_at_least": REBELLION_MIN_THREAT,
            "rebellion_requires_security_at_most": REBELLION_MAX_SECURITY,
            "rebellion_chance_per_eligible_vigilia_percent": REBELLION_CHANCE * 100,
            "conditional_chance_curves": {
                "portal_by_threat_percent": portal_curve,
                "rebellion_after_eligible_vigilia_count_percent": rebellion_curve,
                "assumptions": "Independent opportunities at a fixed threat/chance, with an event slot available; excludes threshold progression, dynamic threat/security, cooldown/suppression, and regional event effects.",
            },
            "days_to_first_event_by_profile": None,
            "reason_days_unestimated": "No funded profile simulator currently advances region threat/security from the fresh-save state and rolls event creation per profile.",
        },
        "limitations": [
            "Catalog access is not a board appearance or a completed activity.",
            "Equipment chance is the seeded base chance before skill, profession, building, and equipment bonuses.",
            "Normal dungeon availability also requires Scouts 1; the funded purchase policy does not build it.",
            "This audit reports eligibility thresholds only and does not claim first milestone timing.",
        ],
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Gates de conteúdo dos primeiros marcos — Stage 5", "",
        f"Conteúdo atual seedado em SQLite temporário · {report['generated_at_utc']}.", "",
        "Este levantamento mede disponibilidade de catálogo pelos gates do serviço, não dias de campanha nem conclusão de atividade.", "",
        "| Perfil | Grupo | Nível da primeira missão elegível com equipamento | Missões/drop únicos | Drop-base min/mediana/máx. | Primeira masmorra normal após Exploradores 1 | Sucesso base |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for name, row in report["profiles"].items():
        gear = row["first_catalog_mission_equipment_opportunity"]
        dungeon = row["first_normal_dungeon_after_building_gate"]
        chance = (f"{gear['base_drop_chance_percent_min']}/{gear['base_drop_chance_percent_median']}/"
                  f"{gear['base_drop_chance_percent_max']}%" if gear else "—")
        dungeon_name = (f"{dungeon['catalog_name']} (guilda/mercenário ≥{dungeon['guild_and_mercenary_level_at_least']}, "
                        f"grupo {dungeon['party_size']})" if dungeon else "—")
        lines.append(
            f"| {name} | {row['planned_party_size']} | {gear['guild_level'] if gear else '—'} | "
            f"{gear['mission_catalog_count']}/{gear['unique_equipment_templates']} | {chance} | "
            f"{dungeon_name} | {dungeon['base_success_chance_percent'] if dungeon else '—'}% |"
        )
    event = report["regional_event_gates"]
    lines.extend([
        "", "## Gates regionais", "",
        f"Portal: ameaça ≥{event['first_portal_possible_at_threat']}, chance inicial {event['portal_chance_at_threshold_percent']}% até teto {event['portal_chance_cap_percent']}%; prazo de entrada {event['portal_entry_deadline_hours_including_offline']}h também durante catch-up offline. Rebelião: ameaça ≥{event['rebellion_requires_threat_at_least']} e segurança ≤{event['rebellion_requires_security_at_most']}, chance {event['rebellion_chance_per_eligible_vigilia_percent']}% por Vigília elegível.",
        "",
        "Chance condicional de pelo menos um portal após 1/10/20 oportunidades elegíveis: " + "; ".join(
            f"ameaça {threat}: {curve['chance_after_1_10_20_eligible_opportunities_percent']['1']}/"
            f"{curve['chance_after_1_10_20_eligible_opportunities_percent']['10']}/"
            f"{curve['chance_after_1_10_20_eligible_opportunities_percent']['20']}%"
            for threat, curve in event["conditional_chance_curves"]["portal_by_threat_percent"].items()
        ) + ". Rebelião, dado que cada Vigília é elegível: " + "; ".join(
            f"{count} Vigílias: {chance}%" for count, chance in event["conditional_chance_curves"]["rebellion_after_eligible_vigilia_count_percent"].items()
        ) + ". Não é prazo de campanha.",
        "",
        "Ainda sem estimativa por perfil: dias até primeiro equipamento, masmorra e evento. As curvas regionais são condicionais a oportunidades elegíveis, chance fixa e slot livre; não modelam progresso de ameaça/segurança nem supressão por evento ativo. A rota financiada atual não compra Exploradores 1 nem simula drops por ação. A matriz registra essas lacunas para o gate; este relatório não as transforma em prova de alcance ou softlock.",
        "",
        "## Reprodução", "", "```powershell",
        ".venv\\Scripts\\python.exe scripts\\balance\\audit_stage5_content_milestones.py",
        "```", "",
    ])
    return "\n".join(lines)


def main() -> None:
    with TemporaryDirectory(prefix="gim-stage5-milestones-") as temp_dir:
        engine = create_database_engine(f"sqlite:///{(Path(temp_dir) / 'stage5-content.sqlite3').as_posix()}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            with factory() as db:
                apply_initial_campaign_content(db)
                report = _audit(db)
        finally:
            engine.dispose()
    stem = ROOT / "reports" / "stage5_content_milestones_2026-10-29"
    stem.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    print(f"JSON: {stem.with_suffix('.json')}")
    print(f"Markdown: {stem.with_suffix('.md')}")


if __name__ == "__main__":
    main()
