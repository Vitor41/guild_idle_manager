from __future__ import annotations

from collections import Counter, defaultdict
from math import ceil
from random import Random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import ContentSeedRun
from app.models.building import BuildingTemplate
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop, ItemTemplate, MissionTemplateItemDrop
from app.models.mission import MissionTemplate
from app.services.mission_service import MISSION_LEVEL_BANDS
from app.services.prd2_balance_service import PRD2_PACK_KEY, PRD2_VERSION
from app.services.building_balance_service import building_cost_factor


MILESTONES = (20, 50, 100, 200, 350)
RARITIES = ("common", "uncommon", "rare", "epic", "legendary", "mythic")
RARITY_LABELS = {
    "common": "Comum", "uncommon": "Incomum", "rare": "Raro",
    "epic": "Épico", "legendary": "Lendário", "mythic": "Mítico",
}


def _expected_rates(mission: MissionTemplate) -> tuple[float, float]:
    chance = mission.base_success_chance / 100
    failed_xp_factor = 0 if mission.mission_type == "long_idle" else 0.25
    expected_xp = mission.base_xp_reward * (chance + (1 - chance) * failed_xp_factor)
    expected_gold = mission.base_gold_reward * chance
    hours = max(1, mission.duration_seconds) / 3600
    return expected_xp / hours, expected_gold / hours


def _expected_materials_per_hour(mission: MissionTemplate) -> float:
    if mission.mission_type != "gathering":
        return 0
    expected = 0.0
    for drop in mission.item_drops:
        if drop.is_active and drop.item_template.item_type != "equipment":
            expected += drop.drop_chance / 100 * (drop.min_quantity + drop.max_quantity) / 2
    return expected * mission.base_success_chance / 100 * 3600 / max(1, mission.duration_seconds)


def _band_for_level(level: int) -> str:
    for band in MISSION_LEVEL_BANDS:
        low, high = (int(value) for value in band.split("-"))
        if low <= level <= high:
            return band
    return MISSION_LEVEL_BANDS[-1]


def build_band_metrics(db: Session) -> list[dict[str, object]]:
    rows = []
    for band in MISSION_LEVEL_BANDS:
        missions = list(db.scalars(select(MissionTemplate).where(
            MissionTemplate.level_band == band,
            MissionTemplate.is_active.is_(True),
        )))
        normal = [m for m in missions if m.mission_type not in {"gathering", "long_idle"}]
        gathering = [m for m in missions if m.mission_type == "gathering"]
        long_idle = [m for m in missions if m.mission_type == "long_idle"]
        best_normal_xp = max(normal, key=lambda m: _expected_rates(m)[0], default=None)
        best_normal_gold = max(normal, key=lambda m: _expected_rates(m)[1], default=None)
        best_gathering = max(gathering, key=_expected_materials_per_hour, default=None)
        low, high = (int(value) for value in band.split("-"))
        xp_required = sum(level * 100 for level in range(low, high))
        expected_xp_per_run = 0.0
        expected_gold_per_run = 0.0
        if best_normal_xp:
            chance = best_normal_xp.base_success_chance / 100
            expected_xp_per_run = best_normal_xp.base_xp_reward * (chance + (1 - chance) * 0.25)
            expected_gold_per_run = best_normal_xp.base_gold_reward * chance
        estimated_attempts = ceil(xp_required / max(1, expected_xp_per_run))
        rows.append({
            "band": band,
            "normal_count": len(normal),
            "gathering_count": len(gathering),
            "long_count": len(long_idle),
            "best_normal_xp_name": best_normal_xp.name if best_normal_xp else "-",
            "normal_xp_per_hour": round(_expected_rates(best_normal_xp)[0], 1) if best_normal_xp else 0,
            "best_normal_gold_name": best_normal_gold.name if best_normal_gold else "-",
            "normal_gold_per_hour": round(_expected_rates(best_normal_gold)[1], 1) if best_normal_gold else 0,
            "best_gathering_name": best_gathering.name if best_gathering else "-",
            "gathering_materials_per_hour": round(_expected_materials_per_hour(best_gathering), 2) if best_gathering else 0,
            "gathering_xp_per_hour": round(max((_expected_rates(m)[0] for m in gathering), default=0), 1),
            "gathering_gold_per_hour": round(max((_expected_rates(m)[1] for m in gathering), default=0), 1),
            "long_durations": sorted(m.duration_seconds // 3600 for m in long_idle),
            "xp_required": xp_required,
            "estimated_active_missions": estimated_attempts,
            "estimated_active_gold": round(estimated_attempts * expected_gold_per_run),
        })
    return rows


def build_progression_profiles(band_metrics: list[dict[str, object]], db: Session) -> dict[str, dict[int, float]]:
    metrics = {row["band"]: row for row in band_metrics}
    long_by_band: dict[str, dict[int, MissionTemplate]] = defaultdict(dict)
    for mission in db.scalars(select(MissionTemplate).where(
        MissionTemplate.mission_type == "long_idle",
        MissionTemplate.is_active.is_(True),
    )):
        long_by_band[mission.level_band][mission.duration_seconds // 3600] = mission

    profiles = {
        "Ativo": {"active_hours": 5.0, "gather_hours": 0.0, "long_hours": 0},
        "Híbrido": {"active_hours": 2.25, "gather_hours": 0.5, "long_hours": 3},
        "Casual/idle": {"active_hours": 0.25, "gather_hours": 0.0, "long_hours": 8},
    }
    results: dict[str, dict[int, float]] = {name: {} for name in profiles}
    for profile_name, profile in profiles.items():
        elapsed_days = 0.0
        for level in range(1, max(MILESTONES)):
            band = _band_for_level(level)
            row = metrics[band]
            daily_xp = float(row["normal_xp_per_hour"]) * float(profile["active_hours"])
            daily_xp += float(row["gathering_xp_per_hour"]) * float(profile["gather_hours"])
            long_hours = int(profile["long_hours"])
            long_mission = long_by_band[band].get(long_hours)
            if long_mission:
                daily_xp += long_mission.base_xp_reward * long_mission.base_success_chance / 100
            elapsed_days += level * 100 / max(1, daily_xp)
            if level + 1 in MILESTONES:
                results[profile_name][level + 1] = round(elapsed_days, 2)
    return results


def simulate_equipment_drops(db: Session, executions: int = 1000) -> dict[str, dict[str, int]]:
    pools: dict[str, list[tuple[str, int]]] = {key: [] for key in ("Missão", "Coleta", "Masmorra", "Chefe")}
    for drop in db.scalars(
        select(MissionTemplateItemDrop)
        .join(ItemTemplate, ItemTemplate.id == MissionTemplateItemDrop.item_template_id)
        .where(MissionTemplateItemDrop.is_active.is_(True), ItemTemplate.item_type == "equipment")
    ):
        key = "Coleta" if drop.mission_template.mission_type == "gathering" else "Missão"
        pools[key].append((drop.item_template.rarity, drop.drop_chance))
    for drop in db.scalars(
        select(DungeonTemplateItemDrop)
        .join(ItemTemplate, ItemTemplate.id == DungeonTemplateItemDrop.item_template_id)
        .where(DungeonTemplateItemDrop.is_active.is_(True), ItemTemplate.item_type == "equipment")
    ):
        key = "Chefe" if drop.dungeon_template.content_type == "boss" else "Masmorra"
        pools[key].append((drop.item_template.rarity, drop.drop_chance))

    rng = Random(51058)
    result = {}
    for content_type, pool in pools.items():
        counts = Counter({rarity: 0 for rarity in RARITIES})
        if pool:
            for _ in range(executions):
                rarity, chance = pool[rng.randrange(len(pool))]
                if rng.random() * 100 < chance:
                    counts[rarity] += 1
        result[content_type] = dict(counts)
    return result


def build_content_findings(db: Session, bands: list[dict[str, object]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    early = next(row for row in bands if row["band"] == "1-20")
    xp_ratio = float(early["normal_xp_per_hour"]) / max(1, float(early["gathering_xp_per_hour"]))
    gold_ratio = float(early["normal_gold_per_hour"]) / max(1, float(early["gathering_gold_per_hour"]))
    findings.append({
        "severity": "Observação" if xp_ratio >= 1.2 and gold_ratio >= 1.2 else "Alto",
        "finding": f"Missões normais entregam {xp_ratio:.2f}x XP/h e {gold_ratio:.2f}x ouro/h contra coleta no early game.",
    })
    invalid_long_bands = [
        row["band"] for row in bands
        if not row["long_durations"] or any(duration not in {1, 3, 8} for duration in row["long_durations"])
    ]
    if invalid_long_bands:
        findings.append({"severity": "Crítico", "finding": f"Faixas com configuração longa inválida: {', '.join(invalid_long_bands)}."})
    else:
        findings.append({
            "severity": "Observação",
            "finding": "Todas as faixas possuem Missões Longas válidas; opções podem ser desativadas intencionalmente pelo admin.",
        })

    marker = db.scalar(select(ContentSeedRun).where(
        ContentSeedRun.pack_key == PRD2_PACK_KEY,
        ContentSeedRun.version == PRD2_VERSION,
    ))
    removed = 0
    if marker:
        import json
        removed = len(json.loads(marker.report_json).get("duplicates_deactivated", []))
    findings.append({
        "severity": "Baixo",
        "finding": f"{removed} coletas duplicadas foram desativadas mantendo os gaps por material.",
    })

    dungeon_counts = list(db.execute(
        select(DungeonTemplate.level_band, DungeonTemplate.content_type)
        .where(DungeonTemplate.is_active.is_(True))
    ))
    total_dungeons = sum(1 for _, content_type in dungeon_counts if content_type == "dungeon")
    if total_dungeons > 300:
        findings.append({
            "severity": "Médio",
            "finding": f"Existem {total_dungeons} masmorras ativas; a massa é ampla e parte tende a ser ignorada por eficiência semelhante.",
        })
    return findings


def build_building_costs(db: Session) -> list[dict[str, object]]:
    rows = []
    for building in db.scalars(select(BuildingTemplate).where(BuildingTemplate.is_active.is_(True)).order_by(BuildingTemplate.id)):
        row: dict[str, object] = {"name": building.name}
        for target in (10, 25, 50):
            factors = sum(building_cost_factor(level) for level in range(1, target + 1))
            row[f"gold_{target}"] = round(building.base_upgrade_gold_cost * factors)
            row[f"wood_{target}"] = round(building.base_upgrade_wood_cost * factors)
            row[f"ore_{target}"] = round(building.base_upgrade_ore_cost * factors)
            row[f"crystals_{target}"] = round(building.base_upgrade_crystals_cost * factors)
        rows.append(row)
    return rows


def build_early_leveling_comparison(db: Session) -> dict[str, dict[str, float | int]]:
    missions = list(db.scalars(select(MissionTemplate).where(
        MissionTemplate.level_band == "1-20",
        MissionTemplate.is_active.is_(True),
        MissionTemplate.mission_type != "long_idle",
    )))
    result = {}
    for route, predicate in (
        ("Missões normais", lambda mission: mission.mission_type != "gathering"),
        ("Coletas", lambda mission: mission.mission_type == "gathering"),
    ):
        attempts = 0
        elapsed_seconds = 0
        expected_gold = 0.0
        for level in range(1, 10):
            eligible = [
                mission for mission in missions
                if predicate(mission) and mission.required_min_mercenary_level <= level
            ]
            if not eligible:
                continue
            choice = max(eligible, key=lambda mission: _expected_rates(mission)[0])
            chance = choice.base_success_chance / 100
            expected_xp = choice.base_xp_reward * (chance + (1 - chance) * 0.25)
            level_attempts = ceil(level * 100 / max(1, expected_xp))
            attempts += level_attempts
            elapsed_seconds += level_attempts * choice.duration_seconds
            expected_gold += level_attempts * choice.base_gold_reward * chance
        result[route] = {
            "attempts": attempts,
            "hours": round(elapsed_seconds / 3600, 2),
            "gold": round(expected_gold),
        }
    return result


def build_prd2_qa_report(db: Session) -> dict[str, object]:
    bands = build_band_metrics(db)
    marker = db.scalar(select(ContentSeedRun).where(
        ContentSeedRun.pack_key == PRD2_PACK_KEY,
        ContentSeedRun.version == PRD2_VERSION,
    ))
    import json
    balance_changes = json.loads(marker.report_json) if marker else {}
    return {
        "bands": bands,
        "profiles": build_progression_profiles(bands, db),
        "drop_simulation_runs": 1000,
        "drop_distribution": simulate_equipment_drops(db, 1000),
        "findings": build_content_findings(db, bands),
        "building_costs": build_building_costs(db),
        "balance_changes": balance_changes,
        "early_leveling": build_early_leveling_comparison(db),
    }


def render_prd2_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Relatório QA de Progressão End-to-End",
        "",
        "## Sumário executivo",
        "",
        "A simulação compara rotas de missão, coleta, missões longas, masmorras, chefes e loot após o pacote PRD 2.",
        "O farm ativo permanece a principal fonte de XP e ouro; coleta mantém domínio de materiais; idle e missões longas são complementares.",
        "",
        "## Progressão por faixa",
        "",
        "| Faixa | Missões | Coletas | Longas | XP/h missão | XP/h coleta | Ouro/h missão | Ouro/h coleta | Materiais/h |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["bands"]:
        lines.append(
            f"| {row['band']} | {row['normal_count']} | {row['gathering_count']} | {row['long_count']} | "
            f"{row['normal_xp_per_hour']} | {row['gathering_xp_per_hour']} | "
            f"{row['normal_gold_per_hour']} | {row['gathering_gold_per_hour']} | {row['gathering_materials_per_hour']} |"
        )
    lines.extend([
        "", "## Volume estimado por faixa", "",
        "| Faixa | XP necessário | Missões ativas estimadas | Ouro esperado durante progressão |",
        "|---|---:|---:|---:|",
    ])
    for row in report["bands"]:
        lines.append(
            f"| {row['band']} | {row['xp_required']} | {row['estimated_active_missions']} | {row['estimated_active_gold']} |"
        )
    lines.extend([
        "", "## Tempo estimado por perfil", "",
        "Valores em dias corridos considerando o padrão diário descrito no PRD.", "",
        "| Perfil | Nível 20 | Nível 50 | Nível 100 | Nível 200 | Nível 350 |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for profile, values in report["profiles"].items():
        lines.append(f"| {profile} | " + " | ".join(str(values[level]) for level in MILESTONES) + " |")
    lines.extend([
        "", "## Nível 1 ao 10", "",
        "| Rota | Execuções estimadas | Horas ativas | Ouro esperado |",
        "|---|---:|---:|---:|",
    ])
    for route, values in report["early_leveling"].items():
        lines.append(f"| {route} | {values['attempts']} | {values['hours']} | {values['gold']} |")
    lines.extend([
        "", "## Distribuição de equipamentos", "",
        f"Simulação determinística de {report['drop_simulation_runs']} execuções por tipo de conteúdo.", "",
        "| Conteúdo | Comum | Incomum | Raro | Épico | Lendário | Mítico |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for content_type, counts in report["drop_distribution"].items():
        lines.append(f"| {content_type} | " + " | ".join(str(counts[rarity]) for rarity in RARITIES) + " |")
    lines.extend(["", "## Rotas mais eficientes", ""])
    for row in report["bands"]:
        lines.append(
            f"- **{row['band']}**: XP em `{row['best_normal_xp_name']}`; ouro em `{row['best_normal_gold_name']}`; "
            f"materiais em `{row['best_gathering_name']}`."
        )
    lines.extend(["", "## Achados e gargalos", ""])
    for finding in report["findings"]:
        lines.append(f"- **{finding['severity']}**: {finding['finding']}")
    lines.extend([
        "", "## Auditoria das coletas", "",
        f"Foram desativadas {len(report['balance_changes'].get('duplicates_deactivated', []))} duplicidades. "
        f"{report['balance_changes'].get('gathering_adjusted', 0)} coletas early tiveram XP/ouro graduados e "
        f"{report['balance_changes'].get('normal_reviewed', 0)} missões normais foram revisadas contra o piso competitivo.", "",
    ])
    for removed in report["balance_changes"].get("duplicates_deactivated", []):
        lines.append(
            f"- Removida `{removed['name']}` (nível {removed['level']}, {removed['family']}); mantida a missão #{removed['kept_id']}."
        )
    lines.extend([
        "", "## Custos acumulados das construções", "",
        "Valores calculados a partir dos custos globais e da curva atual; ajudam a localizar gargalos de ouro, madeira e minério.", "",
        "| Construção | Ouro nv.10 | Madeira nv.10 | Minério nv.10 | Ouro nv.50 | Madeira nv.50 | Minério nv.50 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for row in report["building_costs"]:
        lines.append(
            f"| {row['name']} | {row['gold_10']} | {row['wood_10']} | {row['ore_10']} | "
            f"{row['gold_50']} | {row['wood_50']} | {row['ore_50']} |"
        )
    lines.extend([
        "", "## Economia e recomendações", "",
        "- Missões normais devem permanecer a escolha de XP, ouro e equipamento comum.",
        "- Coletas devem permanecer a fonte previsível de materiais; o bônus do Armazém reduz repetição sem substituir atividade.",
        "- Idle offline entrega madeira e minério básicos em ritmo controlado e somente 1 cristal no teto efetivo.",
        "- Missões longas não entregam itens e operam a 50% do melhor farm ativo bruto por hora.",
        "- Masmorras e Chefes mantêm chances superiores para raridades altas, mas a massa atual merece curadoria futura por uso real.",
        "", "## Evidências", "",
        "Os cálculos usam templates ativos, duração, chance base, recompensa e drops persistidos no PostgreSQL. Falhas de missões comuns concedem 25% do XP; missões longas falhas não concedem XP.",
    ])
    return "\n".join(lines)
