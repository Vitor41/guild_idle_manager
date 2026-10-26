from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from app.database.connection import SessionLocal
from app.models.building import BuildingTemplate, GuildBuilding
from app.models.mission import MissionRun, MissionTemplate
from app.models.guild import GuildResources
from app.models.dock import DockOffer
from app.models.item import ItemTemplate
from app.models.salvage import GuildSalvageJob
from app.repositories.item_repository import get_inventory_resource_totals
from app.services.building_balance_service import BUILDING_MAX_LEVEL, building_cost_factor, get_building_benefit, tavern_values
from app.services.mission_service import LONG_IDLE_CONFIGS, LONG_IDLE_LIMIT, MISSION_LEVEL_BANDS
from app.services.salvage_service import SALVAGE_SLOT_RULES, _select_salvage_material


def main() -> int:
    issues: list[str] = []
    db = SessionLocal()
    try:
        templates = list(db.scalars(select(BuildingTemplate).order_by(BuildingTemplate.id)))
        guild_building_max = db.scalar(select(func.max(GuildBuilding.level))) or 0
        if guild_building_max > BUILDING_MAX_LEVEL:
            issues.append(f"Construção de guilda acima do nível {BUILDING_MAX_LEVEL}: {guild_building_max}")
        for template in templates:
            if template.max_level > BUILDING_MAX_LEVEL:
                issues.append(f"Template {template.name} possui máximo {template.max_level}")
            benefit = get_building_benefit(template.effect_type, BUILDING_MAX_LEVEL)
            if not benefit["current"] or not benefit["is_max_level"]:
                issues.append(f"Benefício final ausente: {template.name}")

        tavern = tavern_values(50)
        if tavern["uncommon_final"] != 30 or tavern["hire_discount_percent"] != 20:
            issues.append("Taverna nível 50 diverge de 30% Incomum / 20% desconto")

        long_missions = list(db.scalars(select(MissionTemplate).where(
            MissionTemplate.mission_type == "long_idle", MissionTemplate.is_active.is_(True)
        )))
        bands = {mission.level_band for mission in long_missions}
        expected_long_rules = {hours * 3600: chance for hours, chance, _ in LONG_IDLE_CONFIGS}
        active_durations_by_band = {
            band: [
                mission.duration_seconds for mission in long_missions
                if mission.level_band == band
            ]
            for band in MISSION_LEVEL_BANDS
        }
        for band, durations in active_durations_by_band.items():
            if not durations:
                issues.append(f"Faixa {band} sem missão longa ativa")
            if len(durations) != len(set(durations)):
                issues.append(f"Faixa {band} possui durações longas duplicadas")
            if any(duration not in expected_long_rules for duration in durations):
                issues.append(f"Faixa {band} possui duração longa inválida")
        for mission in long_missions:
            if expected_long_rules.get(mission.duration_seconds) != mission.base_success_chance:
                issues.append(f"Regra inválida na missão longa {mission.name}")
            if (mission.min_party_size, mission.max_party_size) != (1, 5):
                issues.append(f"Grupo inválido na missão longa {mission.name}: {mission.min_party_size}-{mission.max_party_size}")
        over_limit = db.execute(
            select(MissionRun.guild_id, func.count(MissionRun.id))
            .join(MissionTemplate)
            .where(MissionRun.status == "in_progress", MissionTemplate.mission_type == "long_idle")
            .group_by(MissionRun.guild_id)
            .having(func.count(MissionRun.id) > LONG_IDLE_LIMIT)
        ).all()
        if over_limit:
            issues.append(f"Guildas acima do limite de missões longas: {over_limit}")

        user_templates = [
            path for path in (ROOT / "app" / "templates").rglob("*.html")
            if "admin" not in path.parts
        ]
        rng_files = [str(path.relative_to(ROOT)) for path in user_templates if "RNG" in path.read_text(encoding="utf-8")]
        if rng_files:
            issues.append(f"Texto RNG visível em: {', '.join(rng_files)}")
        if "treasury(resources)" not in (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8"):
            issues.append("Tesouro global não encontrado no layout base")

        main_js = (ROOT / "app" / "static" / "js" / "main.js").read_text(encoding="utf-8")
        for required_function in (
            "captureGameFormState", "restoreGameFormState", "preservePageContext",
        ):
            if f"function {required_function}" not in main_js:
                issues.append(f"Navegacao assincrona sem {required_function}")

        for resources in db.scalars(select(GuildResources).order_by(GuildResources.guild_id)):
            inventory_totals = get_inventory_resource_totals(db, resources.guild_id)
            treasury_totals = {
                key: getattr(resources, key) for key in ("wood", "ore", "crystals")
            }
            if treasury_totals != inventory_totals:
                issues.append(
                    f"Tesouro divergente na guilda {resources.guild_id}: "
                    f"{treasury_totals} != {inventory_totals}"
                )

        active_salvage_duplicates = db.execute(
            select(GuildSalvageJob.guild_id, GuildSalvageJob.slot_number, func.count(GuildSalvageJob.id))
            .where(GuildSalvageJob.status == "in_progress")
            .group_by(GuildSalvageJob.guild_id, GuildSalvageJob.slot_number)
            .having(func.count(GuildSalvageJob.id) > 1)
        ).all()
        if active_salvage_duplicates:
            issues.append(f"Bancadas de desmontagem duplicadas: {active_salvage_duplicates}")
        if [rule["unit_cost"] for rule in SALVAGE_SLOT_RULES.values()] != [50, 150, 300]:
            issues.append("Custos das bancadas de desmontagem divergentes")

        salvage_ratios = []
        dock_equipment = db.execute(
            select(DockOffer, ItemTemplate)
            .join(ItemTemplate, ItemTemplate.id == DockOffer.item_template_id)
            .where(ItemTemplate.item_type == "equipment")
        ).all()
        for offer, item_template in dock_equipment:
            material = _select_salvage_material(db, item_template)
            maximum_recovery = 3 * material.base_sell_value
            salvage_ratios.append(maximum_recovery / max(1, offer.unit_price + 50))
        maximum_salvage_ratio = max(salvage_ratios, default=0)
        if maximum_salvage_ratio >= 0.75:
            issues.append(
                f"Risco de arbitragem Docas/desmontagem: retorno máximo {maximum_salvage_ratio:.1%}"
            )

        print("QA PRD Guild Idle Manager")
        print(f"Construções: {len(templates)} | maior nível: {guild_building_max}")
        print(f"Missões longas: {len(long_missions)} | faixas: {len(bands)}")
        print(f"Desmontagem: {len(dock_equipment)} ofertas auditadas | retorno máximo: {maximum_salvage_ratio:.1%}")
        for target in (10, 25, 50):
            total_factor = sum(building_cost_factor(level) for level in range(1, target + 1))
            print(f"Fator acumulado de custo até {target}: {total_factor:.1f}")
        if issues:
            print("FALHAS:")
            for issue in issues:
                print(f"- {issue}")
            return 1
        print("Resultado: aprovado")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
