"""Reproducible Work 1 gathering/offline matrix using isolated in-memory SQLite."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.connection import Base, SessionLocal, configure_database, get_engine
from app.desktop.clock_guard import ClockGuard, MemoryAnchorStore
from app.models import (
    BuildingTemplate,
    CampaignMetadata,
    Guild,
    GuildBuilding,
    GuildInventoryItem,
    GuildResources,
    GatheringAssignment,
    ItemTemplate,
    Mercenary,
    MercenaryClass,
    ProfessionTemplate,
)
from app.services.gathering_service import assign_worker
from app.services.inventory_capacity_service import get_inventory_capacity


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
DURATIONS = (("5 min", 300), ("6 h", 6 * 3600), ("8 h", 8 * 3600), ("24 h", 24 * 3600))
FAMILIES = ("wood", "ore", "leather")
ROSTER_PROFILES = (1, 3, 5, 20)
WAREHOUSE_LEVELS = (0, 5)


def _render_report(rows: list[dict[str, object]]) -> str:
    lines = [
        "# Work 1 — simulação reproduzível de coleta e ausência",
        "",
        "## Reprodução",
        "",
        "A execução usa SQLite em memória, conteúdo mínimo versionado no harness e relógio/âncoras determinísticos. Nenhum save real é lido ou alterado.",
        "",
        "```powershell",
        "$env:APP_MODE='desktop'",
        ".\\.venv-desktop\\Scripts\\python.exe scripts\\balance\\simulate_work1_gathering.py",
        "```",
        "",
        "## Regra de bônus adotada neste gate",
        "",
        "- Profissão compatível: **15 p.p.** por ciclo, o valor existente em `ProfessionTemplate.bonus_percent` e nas linhas seedadas de profissões (`app/seeds/massive_content.py`). Sem profissão compatível: **0 p.p.**. A unidade-base continua 1 por minuto.",
        "- Ferramentas: **0 p.p. em Work 1**. O GDD as descreve como proposta/saída futura do Ferreiro; o modelo de item atual não identifica ferramentas de coleta por família nem fornece bônus balanceado. Adiar até haver modelo, custos/sinks e comparação reproduzível, sem atribuir valor especulativo.",
        "- Construções: **0 p.p. em Work 1**. Armazém altera capacidade e seu bônus de materiais é aplicado a drops de missões/masmorras; Vigias altera chance de sucesso/drop de combate. Nenhum é bônus de chance de unidade extra de coleta designada. Adiar até decisão de balanceamento específica, sem reutilizar esses efeitos como coleta.",
        "- A composição futura permanece soma em pontos percentuais, limitada a 45 p.p.; os testes existentes cobrem o teto. A base de 1 unidade e o ciclo de 60 segundos não mudam.",
        "- Compatibilidade de construções: novos templates iniciais e Docas usam teto 100. Uma migration one-shot amplia apenas os nove `effect_type` base quando ainda estão exatamente no teto legado 50; caps diferentes de 50 e tipos customizados permanecem. Os seeds criam templates ausentes e não alteram o `max_level` de linhas existentes. Como não existe histórico de edição por linha, `50` em um template base é tratado como o valor padrão legado. O Alojamento continua em 20 vagas nos níveis 50–100.",
        "",
        "## Resultados",
        "",
        "`Ativos` aplica a regra atual de até três atividades por guilda (uma por família). Perfis com elenco de 5 ou 20 mercenários são medidos com três coletores ativos e os demais sem designação; não representam capacidade de coleta acima do limite atual.",
        "",
        "| Elenco | Ativos | Profissão | Armazém | Ausência pedida | Tempo reconhecido | Ciclos | Produzido | Guardado | Excedente | Uso/capacidade | Pausou | Bônus por família | Madeira/minério/cristais | Cristais offline concedidos |",
        "|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---:|:---:|---|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['roster']} | {row['assigned']} | {row['profession']} | {row['warehouse_level']} | {row['requested']} | "
            f"{row['credited']} s | {row['cycles']} | {row['produced']} | {row['stored']} | {row['discarded']} | "
            f"{row['usage']}/{row['capacity']} | {'sim' if row['paused'] else 'não'} | {row['family_bonus']} | {row['resource_totals']} | {row['crystals']} |"
        )
    lines.extend([
        "",
        "## Interpretação e limites",
        "",
        "- As quatro durações passam pelo `ClockGuard` real. Com estamina inicial de 8 h: 5 min reconhece 300 s; 6 h reconhece 21.600 s; 8 h reconhece 28.800 s; 24 h reconhece somente 28.800 s. Os casos de 8 h e 24 h usam a mesma seed de ciclo e devem produzir o mesmo resultado.",
        "- Os perfis 5/20 verificam o limite estrutural, não extrapolam cinco/vinte postos: só madeira, minério e couro têm atividades compatíveis no GDD e cada uma admite um trabalhador.",
        "- O ensaio é uma trajetória determinística por combinação, não Monte Carlo. Serve para reproduzir o gate atual, validar teto/pausa e comparar entradas pareadas; não fecha a distribuição p50/p90 nem o balanceamento final. O GDD mantém os números como hipótese sujeita a simulação mais ampla.",
        "- Madeira e minério passivos ficam em zero. O prêmio offline de Cristais é zero abaixo de 8 h e exatamente um em 8 h e 24 h (24 h é limitado a 8 h). Cada cenário reabre a campanha uma segunda vez antes do reconhecimento do relatório e valida que o grant e o relatório não duplicam. Os contadores `GuildResources` acompanham o inventário e incluem somente as atividades de coleta e o prêmio de Cristais nesta fixture; Cristais continuam fora da capacidade do inventário.",
        "",
    ])
    return "\n".join(lines)


def run_matrix() -> list[dict[str, object]]:
    configure_database("sqlite:///:memory:")
    Base.metadata.create_all(get_engine())
    start = START
    anchor_store = MemoryAnchorStore()
    rows: list[dict[str, object]] = []
    case_index = 0
    warehouse_template_id: int
    class_template_id: int
    profession_ids: dict[str, int]

    with SessionLocal() as db:
        class_template = MercenaryClass(
            name="Batedor de simulação", code="simulation-scout", description="Fixture isolada.",
            base_power=5, base_vitality=5, base_agility=5, base_intelligence=5, base_luck=5,
        )
        warehouse_template = BuildingTemplate(
            name="Armazém de simulação", description="Fixture isolada.", effect_type="warehouse",
            base_upgrade_gold_cost=1, base_upgrade_wood_cost=0, base_upgrade_ore_cost=0,
            base_upgrade_crystals_cost=0, max_level=100, required_guild_level=1, is_active=True,
        )
        professions = {
            family: ProfessionTemplate(
                code=f"sim-{family}", name=f"Profissão {family}", description="Fixture isolada.",
                material_family=family, bonus_percent=15,
            )
            for family in FAMILIES
        }
        templates = {
            family: ItemTemplate(
                name=f"Material de simulação {family}", description="Fixture isolada.",
                item_type="material", rarity="common", material_family=family,
                item_level=1, level_band="1-20", tier=1,
            )
            for family in FAMILIES
        }
        db.add_all([class_template, warehouse_template, *professions.values(), *templates.values()])
        db.flush()
        warehouse_template_id = warehouse_template.id
        class_template_id = class_template.id
        profession_ids = {family: profession.id for family, profession in professions.items()}
        db.commit()

    guard = ClockGuard(anchor_store=anchor_store, wall_clock=lambda: START)
    for roster_size in ROSTER_PROFILES:
        active_count = min(roster_size, len(FAMILIES))
        active_families = FAMILIES[:active_count]
        for matching_profession in (False, True):
            for warehouse_level in WAREHOUSE_LEVELS:
                for requested_label, requested_seconds in DURATIONS:
                    case_index += 1
                    campaign_id = str(uuid4())
                    now = START + timedelta(seconds=requested_seconds)
                    anchor_store.save(campaign_id, START)
                    with SessionLocal() as db:
                        metadata = CampaignMetadata(
                            campaign_id=campaign_id,
                            campaign_name="Fixture de balanceamento",
                            schema_version=4,
                            last_session_state="offline",
                            last_clean_shutdown_utc=START,
                            stamina_seconds=8 * 3600,
                        )
                        guild = Guild(campaign_id=campaign_id, name=f"Guilda fixture {case_index}", level=1)
                        guild.resources = GuildResources(gold=100, wood=0, ore=0, crystals=0)
                        db.add_all([metadata, guild])
                        db.flush()
                        if warehouse_level:
                            db.add(GuildBuilding(
                                guild_id=guild.id, building_template_id=warehouse_template_id,
                                level=warehouse_level,
                            ))
                        worker_rows = []
                        for index in range(roster_size):
                            family = active_families[index] if index < active_count else None
                            worker = Mercenary(
                                guild_id=guild.id,
                                class_id=class_template_id,
                                profession_id=(profession_ids[family] if family and matching_profession else None),
                                name=f"Trabalhador {case_index}-{index + 1}",
                                level=1,
                                power=5,
                                vitality=5,
                                agility=5,
                                intelligence=5,
                                luck=5,
                            )
                            db.add(worker)
                            worker_rows.append((worker, family))
                        db.flush()
                        bonuses = []
                        for worker_index, (worker, family) in enumerate(worker_rows[:active_count]):
                            assignment = assign_worker(db, guild, worker.id, family, now=START)
                            assignment.rng_seed = 10_000 + roster_size * 100 + int(matching_profession) * 10 + worker_index
                            bonuses.append(f"{family}:{assignment.extra_chance}pp")
                        db.commit()

                    guard.wall_clock = lambda now=now: now
                    guard.activate_campaign(campaign_id)
                    with SessionLocal() as db:
                        metadata = db.get(CampaignMetadata, campaign_id)
                        guild = db.query(Guild).filter_by(campaign_id=campaign_id).one()
                        resources = db.query(GuildResources).filter_by(guild_id=guild.id).one()
                        assignments = list(db.query(GatheringAssignment).filter_by(guild_id=guild.id).all())
                        summary = json.loads(metadata.pending_offline_report)
                        capacity = get_inventory_capacity(db, guild)
                        inventory = list(db.query(GuildInventoryItem).filter_by(guild_id=guild.id).all())
                        family_totals = {family: 0 for family in FAMILIES}
                        for item in inventory:
                            family = db.get(ItemTemplate, item.item_template_id).material_family
                            family_totals[family] += item.quantity
                        gathering = summary["gathering"]
                        rows.append({
                            "roster": roster_size,
                            "assigned": len(assignments),
                            "profession": "compatível" if matching_profession else "sem profissão",
                            "warehouse_level": warehouse_level,
                            "requested": requested_label,
                            "credited": summary["credited_seconds"],
                            "cycles": sum(result["cycles"] for result in gathering.values()),
                            "produced": sum(result["produced"] for result in gathering.values()),
                            "stored": sum(family_totals.values()),
                            "discarded": sum(result["discarded"] for result in gathering.values()),
                            "usage": sum(family_totals.values()),
                            "capacity": capacity,
                            "paused": any(result.get("paused", False) for result in gathering.values()),
                            "family_bonus": ", ".join(bonuses) or "—",
                            "resource_totals": f"{resources.wood}/{resources.ore}/{resources.crystals}",
                            "crystals": resources.crystals,
                            "stamina_remaining": metadata.stamina_seconds,
                        })
                        assert summary["materials"]["wood_total"] == summary["materials"]["ore_total"] == 0
                        expected_crystals = 1 if summary["credited_seconds"] >= 8 * 3600 else 0
                        assert summary["materials"]["crystals"] == expected_crystals
                        assert summary["crystals"] == expected_crystals
                        assert resources.crystals == expected_crystals
                        assert summary["credited_seconds"] == min(requested_seconds, 8 * 3600)
                        assert metadata.stamina_seconds == 8 * 3600 - summary["stamina_spent_seconds"]
                        assert sum(family_totals.values()) <= capacity

                    reopened_summary = guard.activate_campaign(campaign_id)
                    with SessionLocal() as db:
                        reopened_guild = db.query(Guild).filter_by(campaign_id=campaign_id).one()
                        reopened_resources = db.query(GuildResources).filter_by(guild_id=reopened_guild.id).one()
                        assert reopened_summary["report_id"] == summary["report_id"]
                        assert reopened_resources.crystals == expected_crystals

    configure_database("sqlite:///:memory:")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "work1_gathering_simulation.md",
        help="Markdown report destination; use '-' to print only.",
    )
    args = parser.parse_args()
    rows = run_matrix()
    report = _render_report(rows)
    if str(args.output) == "-":
        print(report)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Relatório salvo em {args.output}")
    print(f"Combinações: {len(rows)}; perfis={ROSTER_PROFILES}; profissões=0/15pp; armazéns={WAREHOUSE_LEVELS}; ausências={tuple(label for label, _ in DURATIONS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
