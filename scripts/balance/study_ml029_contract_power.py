"""Reproduce the ML-029 Common Apprentice curve and regional contract comparisons."""

from __future__ import annotations

import csv
from math import ceil, floor
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("APP_MODE", "desktop")

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database.connection import create_database_engine
from app.models.mission import MissionTemplate
from app.models.item import ItemTemplate
from app.services.balance_service import power_success_adjustment
from app.services.campaign_service import CampaignService
from app.services.balance_service import calculate_power_score
from app.services.equipment_service import normalize_equipment_slot
from app.services.mission_power_service import (
    COMMON_APRENTICE_REFERENCE_MAX_LEVEL,
    REGIONAL_CONTRACT_RANK_POWER_MULTIPLIERS,
    common_apprentice_reference_curve,
    recommended_regional_contract_power,
)


MULTIPLIER_SCENARIOS = {
    "initial_po": {"E": 1.00, "D": 1.15, "C": 1.30, "B": 1.50, "A": 1.75, "S": 2.00},
    "conservative": REGIONAL_CONTRACT_RANK_POWER_MULTIPLIERS,
}
LEVEL_GROUPS = ((1, 2), (5, 2), (18, 2), (50, 2), (75, 3), (200, 4), (350, 5))
RANKS = ("E", "D", "C", "B", "A", "S")
EQUIPMENT_SLOTS = {"main_hand": 1, "off_hand": 1, "helmet": 1, "chest": 1, "gloves": 1,
                   "boots": 1, "necklace": 1, "earring": 2, "belt": 1, "ring": 2}
EQUIPMENT_RNG_ATTRIBUTES = ("power", "vitality", "agility", "intelligence", "luck", "armor")


def _baseline_templates() -> tuple[
    dict[tuple[int, int], dict[str, int | str]], dict[int, int]
]:
    """Read current seed/admin values from a disposable fresh campaign database."""
    scratch_root = REPO_ROOT / ".lot-e2-test-tmp"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ml029-study-", dir=scratch_root) as temp_dir:
        campaign = CampaignService(Path(temp_dir) / "saves").create_campaign(
            "ML-029 disposable baseline", "Guilda de referência",
        )
        engine = create_database_engine(f"sqlite:///{Path(campaign.database_path).as_posix()}")
        try:
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            with factory() as db:
                templates = list(db.scalars(select(MissionTemplate).where(
                    MissionTemplate.is_active.is_(True),
                    ~MissionTemplate.mission_type.in_(("gathering", "long_idle")),
                )))
                item_templates = list(db.scalars(select(ItemTemplate).where(
                    ItemTemplate.item_type == "equipment",
                    ItemTemplate.is_active.is_(True),
                )))
                result = {}
                equipment_power: dict[int, int] = {}
                for level, group_size in LEVEL_GROUPS:
                    eligible = [template for template in templates if (
                        int(template.recommended_level or 1) <= max(20, level)
                        and int(template.min_party_size or 1) <= 1
                        and int(template.max_party_size or 1) == group_size
                    )]
                    if not eligible:
                        raise RuntimeError(
                            f"Sem template normal de grupo 1–{group_size} até o nível {level}."
                        )
                    template = min(eligible, key=lambda row: (
                        abs(int(row.recommended_level or 1) - level),
                        int(row.recommended_level or 1),
                        int(row.id),
                    ))
                    result[(level, group_size)] = {
                        "name": str(template.name),
                        "recommended_level": int(template.recommended_level or 1),
                        "recommended_power": int(template.recommended_power or 1),
                        "base_success_chance": int(template.base_success_chance),
                        "min_party_size": int(template.min_party_size or 1),
                        "max_party_size": int(template.max_party_size or 1),
                    }
                    best_by_slot = {slot: [] for slot in EQUIPMENT_SLOTS}
                    for item in item_templates:
                        required_level = int(item.required_level or item.item_level or 1)
                        slot = normalize_equipment_slot(item.equipment_slot)
                        if required_level > level or slot not in best_by_slot:
                            continue
                        attributes = {
                            name: int(getattr(item, f"bonus_{name}") or 0)
                            for name in EQUIPMENT_RNG_ATTRIBUTES
                        }
                        rng_max = max(0, int(item.rng_bonus_max or 0))
                        score = max(
                            calculate_power_score({
                                **attributes,
                                rng_attribute: attributes[rng_attribute] + rng_max,
                            })
                            for rng_attribute in EQUIPMENT_RNG_ATTRIBUTES
                        ) if rng_max else calculate_power_score(attributes)
                        best_by_slot[slot].append(score)
                    equipment_power[level] = sum(
                        sum(sorted(scores, reverse=True)[:capacity])
                        for slot, capacity in EQUIPMENT_SLOTS.items()
                        if (scores := best_by_slot[slot])
                    )
                return result, equipment_power
        finally:
            engine.dispose()


def _chance(base: int, party_power: int, recommended_power: int, modifier_pp: int = 0) -> tuple[int, int]:
    raw = base + power_success_adjustment(party_power, recommended_power) + modifier_pp
    uncapped = max(5, raw)
    return min(95, uncapped), uncapped


def build_scenario_rows() -> tuple[
    list[dict[str, object]], dict[tuple[int, int], dict[str, int | str]]
]:
    curve = common_apprentice_reference_curve(COMMON_APRENTICE_REFERENCE_MAX_LEVEL)
    baseline, equipment_power = _baseline_templates()
    rows = []
    for level, group_size in LEVEL_GROUPS:
        attributes = curve[level - 1]
        member_power = int(attributes["power_score"])
        catalog = baseline[(level, group_size)]
        for rank in RANKS:
            for party_kind, party_count in (("solo", 1), ("grupo_maximo", group_size)):
                party_power = member_power * party_count
                baseline_chance, _ = _chance(
                    int(catalog["base_success_chance"]),
                    party_power,
                    int(catalog["recommended_power"]),
                )
                for scenario, multipliers in MULTIPLIER_SCENARIOS.items():
                    recommended = recommended_regional_contract_power(
                        level,
                        rank,
                        group_size,
                        fallback_power=int(catalog["recommended_power"]),
                    ) if scenario == "conservative" else max(
                        1,
                        ceil(
                            member_power * float(multipliers[rank]) * group_size
                        ),
                    )
                    chance, uncapped = _chance(
                        int(catalog["base_success_chance"]), party_power, recommended,
                    )
                    chance_with_supply, uncapped_with_supply = _chance(
                        int(catalog["base_success_chance"]), party_power, recommended, 5,
                    )
                    max_modifier_chance, _ = _chance(
                        int(catalog["base_success_chance"]), party_power, recommended,
                        (3 if party_kind == "solo" else 8) + 15,
                    )
                    stage = min(4, 1 + max(0, level - 51) // 75) if level >= 51 else 0
                    maximum_rarity_bonus = min(20, floor(5 * stage))
                    equipment_party_power = party_power + equipment_power[level] * party_count
                    equipment_chance, _ = _chance(
                        int(catalog["base_success_chance"]), equipment_party_power, recommended,
                    )
                    max_supported_chance, _ = _chance(
                        int(catalog["base_success_chance"]), equipment_party_power, recommended,
                        (3 if party_kind == "solo" else 8) + 15 + maximum_rarity_bonus,
                    )
                    max_supported_with_supply, _ = _chance(
                        int(catalog["base_success_chance"]), equipment_party_power, recommended,
                        (3 if party_kind == "solo" else 8) + 15 + maximum_rarity_bonus + 5,
                    )
                    rows.append({
                        "level": level,
                        "rank": rank,
                        "group_max": group_size,
                        "party_kind": party_kind,
                        "party_size": party_count,
                        "common_power_each": member_power,
                        "party_power": party_power,
                        "baseline_template_power": int(catalog["recommended_power"]),
                        "baseline_chance": baseline_chance,
                        "scenario": scenario,
                        "multiplier": float(multipliers[rank]),
                        "recommended_power": recommended,
                        "chance_no_modifiers": chance,
                        "chance_uncapped_no_modifiers": uncapped,
                        "chance_with_supply": chance_with_supply,
                        "chance_with_supply_uncapped": uncapped_with_supply,
                        "chance_with_max_class_and_skill": max_modifier_chance,
                        "max_seeded_equipment_power_each": equipment_power[level],
                        "chance_with_max_seeded_equipment": equipment_chance,
                        "max_rarity_bonus_pp": maximum_rarity_bonus,
                        "chance_with_max_equipment_class_skill_rarity": max_supported_chance,
                        "chance_with_max_modifiers_and_supply": max_supported_with_supply,
                        "base_chance": int(catalog["base_success_chance"]),
                        "template_recommended_level": int(catalog["recommended_level"]),
                        "baseline_template": str(catalog["name"]),
                    })
    return rows, baseline


def write_evidence(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    curve = common_apprentice_reference_curve(COMMON_APRENTICE_REFERENCE_MAX_LEVEL)
    curve_path = output_dir / "lot_e2_ml029_common_apprentice_1_350.csv"
    with curve_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(curve[0]))
        writer.writeheader()
        writer.writerows(curve)

    rows, baseline = build_scenario_rows()
    scenarios_path = output_dir / "lot_e2_ml029_scenarios_2026-11-08.csv"
    with scenarios_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    target_report = output_dir / "lot_e2_ml029_balance_study_2026-11-08.md"
    c18 = baseline[(18, 2)]
    contents = [
        "# ML-029 — estudo de poder recomendado para contratos regionais",
        "",
        "Este arquivo é gerado pelo script `scripts/balance/study_ml029_contract_power.py` a partir da curva real de progressão e de templates seedados em uma campanha descartável. Nenhum save do usuário é consultado.",
        "",
        "## Referência Comum",
        "",
        "O maior vetor válido recém-contratado é FOR/VIT/AGI/INT/SOR `7/7/7/7/7`: cada atributo respeita o cap Comum 7 e a fórmula de poder produz 18, dentro do intervalo Comum 1–18. O gerador de Taverna não aplica o bônus de função ao Aprendiz. A tabela por nível chama `apply_levelup_attributes()` real para raridade Comum e `calculate_power_score()` real, sem equipamento, profissão, skills ou evolução.",
        "",
        "Com classe Aprendiz, cada level-up acrescenta FOR +2, VIT +2, AGI +1, INT +1 e SOR +1. Para Comum, o bônus por raridade é 0%. Essa curva de referência mantém a classe inicial; não representa uma trilha universal de evolução. `apply_class_evolution_attributes()` soma apenas deltas positivos dos atributos-base da classe de origem para a classe-alvo, e `class_success_bonus()`/skills/equipamento entram separadamente no cálculo de chance.",
        "",
        "| Nível | Atributos FOR/VIT/AGI/INT/SOR | Poder |",
        "|---:|---|---:|",
    ]
    for level in (1, 5, 10, 12, 18, 20, 50, 75, 100, 200, 350):
        row = curve[level - 1]
        attrs = "/".join(str(row[key]) for key in ("power", "vitality", "agility", "intelligence", "luck"))
        contents.append(f"| {level} | {attrs} | {row['power_score']} |")
    contents.extend([
        "",
        f"A tabela completa de {len(curve)} níveis está em [CSV]({curve_path.name}).",
        "",
        "## Exemplos do catálogo atual e comparação",
        "",
        "O baseline é o `recommended_power` do template normal mais próximo do nível, com party iniciável de tamanho mínimo 1 e máximo correspondente à faixa. Hoje esse valor é copiado ao snapshot sem usar Rank; o Rank atual ordena ofertas, mas não multiplica o poder recomendado. Os candidatos usam `ceil(poder_Comum(nível) × multiplicador_Rank × grupo_máximo)`. Chance base, ajuste de poder, limites e suprimento usam os serviços atuais. A tabela base isola mercenários Comuns sem bônus de classe/raridade/skill e sem equipamento. As colunas de sensibilidade somam a melhor combinação por slot de equipamentos seedados até o nível do cenário, usando o maior valor RNG legal de cada peça, e/ou os limites atuais de classe, skill e raridade; isso representa um teto de catálogo, não uma expectativa de posse.",
        "",
        f"Caso do usuário: Rank C nível 18, grupo 1–2: template `{c18['name']}` mantém recomendação atual {c18['recommended_power']}, base {c18['base_success_chance']}%; a referência Comum nível 18 tem poder {curve[17]['power_score']}. O baseline dá chance {next(row['baseline_chance'] for row in rows if row['level']==18 and row['rank']=='C' and row['party_kind']=='solo')}% para solo e {next(row['baseline_chance'] for row in rows if row['level']==18 and row['rank']=='C' and row['party_kind']=='grupo_maximo')}% para grupo máximo antes de classe/skill/suprimento.",
        "",
        "| Nível | Rank | Grupo máx. | Tipo | Template base atual | Poder atual | Poder candidato | Chance atual | Chance candidata | Com suprimento | Classe+skill máx. | Equip.+classe+skill+raridade máx. | Mesmo teto + suprimento |",
        "|---:|:---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        if row["scenario"] != "conservative" or row["rank"] not in {"E", "C", "S"}:
            continue
        contents.append(
        f"| {row['level']} | {row['rank']} | {row['group_max']} | {row['party_kind']} | "
        f"{row['baseline_template']} | {row['baseline_template_power']} | {row['recommended_power']} | "
            f"{row['baseline_chance']}% | {row['chance_no_modifiers']}% | {row['chance_with_supply']}% | "
        f"{row['chance_with_max_class_and_skill']}% | {row['chance_with_max_equipment_class_skill_rarity']}% | "
        f"{row['chance_with_max_modifiers_and_supply']}% |"
        )
    contents.extend([
        "",
        "A comparação integral Rank E–S, nos dois conjuntos de multiplicadores, está em [CSV de cenários](lot_e2_ml029_scenarios_2026-11-08.csv). `grupo_max` é o tamanho máximo real do template amostrado; `solo` usa um mercenário e `grupo_maximo` usa esse número de Comuns. O baseline de cada nível é igual entre Ranks porque o template atual não escala poder pelo Rank.",
        "",
        "## Multiplicadores avaliados",
        "",
        "| Rank | PO inicial | Conservador escolhido para teste |",
        "|:---:|---:|---:|",
    ])
    for rank in RANKS:
        contents.append(
            f"| {rank} | {MULTIPLIER_SCENARIOS['initial_po'][rank]:.2f} | "
            f"{MULTIPLIER_SCENARIOS['conservative'][rank]:.2f} |"
        )
    contents.extend([
        "",
        "## Decisão e riscos",
        "",
        "A variante conservadora foi escolhida para aplicação a novas ofertas de contratos regionais de combate. Em Rank C nível 18, ela recomenda `ceil(93 × 1,10 × 2) = 205`: chance Comum sem bônus fica 55% solo e 75% com dois; suprimento eleva para 60%/80%. O baseline de 49 levava os dois cenários a 95%, então +5 p.p. não tinha efeito. O conjunto PO inicial elevaria C18 a 242 e reduziria a chance do grupo a 69% (74% com suprimento), risco maior no começo. Em nível 1, Rank E mantém 36 de poder recomendado, dá 59% solo e 85% com dois Comuns, com suprimento 64%/90%; isso preserva uma entrada solo com risco e recompensa a formação completa. O Rank S completo no nível 1 dá 65% sem bônus, contra 59% com o conjunto PO inicial; no nível 350, grupo completo Rank S dá 21% contra 14% no conjunto inicial, antes de bônus/equipamento.",
        "",
        "A chance continua usando cap 95%, classe/skills e os bônus reais; Comuns não recebem bônus de raridade. `get_party_chance_details()` acrescenta até +3 p.p. de classe para solo, até +8 p.p. no grupo e skills até +15 p.p.; raridade pode acrescentar até +20 p.p. em conteúdo de nível alto para elencos não Comuns. Equipamento acrescenta atributos ao poder efetivo, não p.p. direto. O CSV mede o teto de equipamento combinando a melhor peça permitida de cada slot, seu RNG máximo seedado, e os limites de classe, skill e raridade. Esse extremo pode chegar a 95% até no início; no jogo ele depende de obter várias peças fortes, então representa uma fronteira e não uma expectativa. O suprimento demonstra +5 p.p. nos cenários Common sem bônus enquanto há espaço; em qualquer combinação já limitada a 95%, não aumenta a chance. Esse é risco residual explícito para validação de builds equipadas.",
        "",
        "A aplicação calcula apenas o snapshot de novas ofertas do tipo `contract` para templates que não sejam `gathering` ou `long_idle`; o valor do template/admin, requisitos, seed, ofertas já materializadas, snapshots, runs, coleta, missão longa, masmorra e chefe não são recalculados. Níveis fora de 1–350 e Ranks desconhecidos mantêm o poder configurado do template.",
        "",
        "## Reproduzir",
        "",
        "Com o ambiente desktop do projeto ativo, execute `python scripts/balance/study_ml029_contract_power.py`. O comando cria uma campanha descartável em pasta temporária para ler os templates atuais e gera os CSVs e este Markdown em `reports/`.",
        "",
    ])
    target_report.write_text("\n".join(contents), encoding="utf-8")


if __name__ == "__main__":
    write_evidence(REPO_ROOT / "reports")
    print("ML-029 study evidence generated")
