import json
import re
from collections import defaultdict
from math import ceil
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.content import ContentSeedRun
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop, ItemTemplate
from app.models.mission import MissionTemplate
from app.seeds.massive_content import PACK_KEY


PRD3_PACK_KEY = "melhorias_prd_3_masmorras_chefes"
PRD3_VERSION = 2

LEVEL_BANDS = ("1-20", "21-50", "51-100", "101-130", "131-200", "201-250", "251-300", "301-350")
BAND_LIMITS = {
    "1-20": (1, 20), "21-50": (21, 50), "51-100": (51, 100), "101-130": (101, 130),
    "131-200": (131, 200), "201-250": (201, 250), "251-300": (251, 300), "301-350": (301, 350),
}
DUNGEON_TARGETS = (10, 15, 22, 15, 30, 22, 22, 26)
BOSS_TARGETS = (2, 3, 5, 3, 8, 6, 6, 10)
RARITY_ORDER = ("common", "uncommon", "rare", "epic", "legendary", "mythic")
RARITY_LABELS = {
    "common": "Comum", "uncommon": "Incomum", "rare": "Raro",
    "epic": "Épico", "legendary": "Lendário", "mythic": "Mítico",
}
LEGACY_CURATED_NAMES = {"Covil dos Lobos", "Fortaleza do Ogro", "Dragão das Cinzas"}
LEGACY_DUPLICATE_NAMES = {"Dragao das Cinzas"}

DUNGEON_ARCHETYPES = (
    ("xp", "Melhor para XP", "Formação ofensiva para acelerar a progressão.", "heroic", 1.36, 0.72, 1.00),
    ("gold", "Melhor para ouro", "Grupo resistente para proteger o tesouro recuperado.", "hard", 0.78, 1.38, 1.00),
    ("equipment", "Bom para equipamentos", "Equipe equilibrada com espaço para um caçador de relíquias.", "hard", 0.88, 0.82, 1.18),
    ("rare", "Chance de item raro", "Mercenários bem equipados para enfrentar um risco maior.", "legendary", 0.82, 0.78, 1.35),
    ("material", "Farm de material raro", "Composição estável e profissões de coleta compatíveis.", "hard", 0.84, 0.86, 1.22),
    ("short", "Incursão rápida", "Grupo ágil para uma exploração curta e segura.", "normal", 0.92, 0.90, 0.78),
    ("balanced", "Recompensa equilibrada", "Tanque, suporte e dano oferecem o melhor equilíbrio.", "normal", 1.02, 1.02, 1.00),
    ("risky", "Risco alto, recompensa alta", "Formação completa e equipamento acima da média.", "legendary", 1.20, 1.18, 1.28),
    ("transition", "Conteúdo de transição", "Grupo próximo da próxima faixa de nível.", "heroic", 1.12, 1.04, 1.10),
    ("composition", "Desafio de composição", "Atenda aos papéis indicados para aproveitar a sinergia.", "heroic", 1.05, 0.94, 1.12),
)
BOSS_ARCHETYPES = (
    ("physical", "Chefe de força física", "Tanque e dano físico sustentado são recomendados."),
    ("arcane", "Chefe de poder arcano", "Suporte e combatentes de alcance ajudam a controlar o confronto."),
    ("resistant", "Chefe resistente", "Uma formação equilibrada reduz o risco de um combate prolongado."),
    ("swift", "Chefe veloz", "Dano rápido e boa preparação são essenciais."),
    ("rare", "Caçada por raridade alta", "Grupo forte e bem equipado para buscar recompensas superiores."),
    ("endgame", "Desafio de progressão", "Teste de força para mercenários no topo da faixa."),
)

DUNGEON_PREFIXES = (
    "Cripta", "Covil", "Ruínas", "Fenda", "Torre", "Ninho", "Câmara", "Abismo",
    "Santuário", "Fortaleza", "Catacumbas", "Bastião", "Templo", "Labirinto", "Cidadela",
)
DUNGEON_EPITHETS = (
    "dos Sinos Partidos", "do Vigia Rubro", "da Ordem Cinzenta", "do Carvalho Sombrio",
    "do Juramento Quebrado", "da Serpente Antiga", "do Rei Afogado", "da Aurora Extinta",
    "das Cinzas Silenciosas", "do Sol Sepultado", "da Névoa Eterna", "dos Ecos Perdidos",
    "da Lua de Ferro", "do Trono Vazio", "das Runas Profundas", "do Véu Partido",
    "do Guardião Adormecido", "da Coroa Esquecida", "dos Ossos Dourados", "do Horizonte Negro",
)
BOSS_NAMES = (
    "Varkun, o Guardião Cinzento", "Morgath, o Devorador de Relíquias", "A Serpente de Vidro",
    "Brakka, Capitã dos Ossos", "Elyra, a Voz da Névoa", "Tharok, o Martelo Antigo",
    "Zareth, o Rei Afogado", "Maelis, a Chama Pálida", "Gorun, o Vigia Rubro",
    "Ilyss, a Tecelã do Vazio", "Rhazak, o Senhor das Cinzas", "Nerath, o Coração de Ferro",
    "Velka, a Coroa Sombria", "Ormak, o Colosso Partido", "Selene, a Lua Faminta",
    "Dravon, o Juramento Vivo", "Kharis, a Lâmina Silenciosa", "Aldren, o Rei sem Trono",
    "Morva, a Mãe das Runas", "Tyrak, o Último Sentinela", "Azra, a Aurora Extinta",
    "Brom, o Escudo Profundo", "Nymera, a Dama dos Ecos", "Korvan, o Caçador Eterno",
    "Edris, o Arauto do Abismo", "Valgor, o Punho da Tempestade", "Lysara, a Bruxa Dourada",
    "Dargan, o Senhor do Labirinto", "O Vigia do Sol Sepultado", "A Fera da Coroa Esquecida",
    "Kaelor, o Dragão de Pedra", "Mirza, a Guardiã do Véu", "Rothar, o Rei das Correntes",
    "Ylena, a Voz das Profundezas", "Grom, o Titã das Ruínas", "A Serpente da Lua de Ferro",
    "Varis, o Príncipe do Vazio", "Malrik, o Portador da Noite", "Seraph, o Anjo Partido",
    "Korath, o Devorador de Estrelas", "Arven, o Mestre das Cinzas", "Thyra, a Rainha Escarlate",
    "Norgal, o Guardião do Fim",
)


def _content_snapshot(templates: list[DungeonTemplate]) -> dict[str, object]:
    counts = {kind: {band: 0 for band in LEVEL_BANDS} for kind in ("dungeon", "boss")}
    for template in templates:
        if template.is_active and template.content_type in counts and template.level_band in counts[template.content_type]:
            counts[template.content_type][template.level_band] += 1
    return {"counts": counts, "active_total": sum(sum(values.values()) for values in counts.values())}


def _catalog_snapshot(templates: list[DungeonTemplate]) -> list[dict[str, object]]:
    return [{
        "id": template.id, "name": template.name, "active": template.is_active,
        "type": template.content_type, "band": template.level_band,
        "level": template.recommended_level, "duration": template.duration_seconds,
        "chance": template.base_success_chance, "xp": template.base_xp_reward,
        "gold": template.base_gold_reward, "power": template.required_total_power,
        "party": [template.min_party_size, template.max_party_size],
        "roles": [template.required_tank_count, template.required_support_count, template.required_damage_count],
        "drops": [{
            "type": drop.item_template.item_type, "rarity": drop.item_template.rarity,
            "chance": drop.drop_chance, "min": drop.min_quantity, "max": drop.max_quantity,
            "value": drop.item_template.base_sell_value,
        } for drop in template.item_drops if drop.is_active and drop.item_template],
    } for template in templates if template.is_active and template.content_type in {"dungeon", "boss"}]


def _even_selection(candidates: list[DungeonTemplate], amount: int) -> list[DungeonTemplate]:
    if amount <= 0:
        return []
    if len(candidates) <= amount:
        return candidates
    if amount == 1:
        return [candidates[len(candidates) // 2]]
    indexes = {round(index * (len(candidates) - 1) / (amount - 1)) for index in range(amount)}
    return [candidates[index] for index in sorted(indexes)]


def _mission_reference_rates(db: Session, band: str) -> tuple[float, float]:
    missions = list(db.scalars(select(MissionTemplate).where(
        MissionTemplate.is_active.is_(True), MissionTemplate.level_band == band,
        ~MissionTemplate.mission_type.in_(("gathering", "long_idle")),
    )))
    xp_rates = [mission.base_xp_reward * 3600 / max(1, mission.duration_seconds) for mission in missions]
    gold_rates = [mission.base_gold_reward * 3600 / max(1, mission.duration_seconds) for mission in missions]
    return (median(xp_rates) if xp_rates else 100.0, median(gold_rates) if gold_rates else 50.0)


def _natural_dungeon_name(global_index: int) -> str:
    prefix = DUNGEON_PREFIXES[global_index % len(DUNGEON_PREFIXES)]
    epithet = DUNGEON_EPITHETS[(global_index // len(DUNGEON_PREFIXES) + global_index * 7) % len(DUNGEON_EPITHETS)]
    return f"{prefix} {epithet}"


def _unique_name(base: str, used: set[str], global_index: int) -> str:
    if base not in used:
        used.add(base)
        return base
    qualifiers = ("Oculta", "Profunda", "Antiga", "Esquecida", "Silenciosa", "Proibida", "Perdida")
    for offset in range(len(qualifiers)):
        candidate = f"{base} {qualifiers[(global_index + offset) % len(qualifiers)]}"
        if candidate not in used:
            used.add(candidate)
            return candidate
    candidate = f"{base} do Norte"
    used.add(candidate)
    return candidate


def _roles_for(kind: str, archetype: str, index: int) -> tuple[int, int, int]:
    if kind == "boss":
        patterns = {
            "physical": (2, 1, 2), "arcane": (1, 2, 2), "resistant": (2, 2, 1),
            "swift": (1, 1, 3), "rare": (1, 2, 2), "endgame": (2, 1, 2),
        }
        return patterns[archetype]
    patterns = ((1, 0, 1), (0, 1, 1), (1, 1, 1), (0, 1, 2), (1, 0, 2))
    return patterns[index % len(patterns)]


def _base_chance(kind: str, difficulty: str, band_index: int) -> int:
    if kind == "boss":
        table = {
            "hard": (72, 68, 64, 61, 58, 55, 52, 50),
            "heroic": (58, 54, 50, 47, 44, 41, 38, 36),
            "legendary": (55, 51, 47, 44, 41, 38, 35, 33),
        }
        return table[difficulty][band_index]
    table = {
        "normal": (86, 83, 80, 78, 75, 72, 69, 68),
        "hard": (77, 74, 71, 68, 65, 62, 59, 57),
        "heroic": (68, 65, 62, 59, 56, 53, 50, 48),
        "legendary": (64, 61, 58, 55, 52, 49, 46, 44),
    }
    return table[difficulty][band_index]


def _configure_template(
    template: DungeonTemplate, kind: str, position: int, total: int, band_index: int,
    xp_rate: float, gold_rate: float, used_names: set[str], global_index: int, rename: bool = True,
) -> dict[str, object]:
    band = LEVEL_BANDS[band_index]
    low, high = BAND_LIMITS[band]
    level = round(low + (high - low) * position / max(1, total - 1))
    tier = band_index + 1
    if kind == "dungeon":
        code, label, profile, difficulty, xp_factor, gold_factor, duration_factor = DUNGEON_ARCHETYPES[position % len(DUNGEON_ARCHETYPES)]
        duration_minutes = (12 + tier * 5 + (position % 4) * 4) * duration_factor
        if code == "short":
            duration_minutes *= 0.58
        if code == "risky":
            duration_minutes *= 1.35
        tank, support, damage = _roles_for(kind, code, position)
        if rename:
            template.name = _unique_name(_natural_dungeon_name(global_index), used_names, global_index)
        template.description = f"Especialidade: {label}. {profile}"
        template.min_party_size = max(2, min(3, tank + support + damage))
        template.max_party_size = min(5, max(template.min_party_size, tank + support + damage))
        template.required_total_power = max(24, round(level * (7.0 + tier * 0.35) * template.min_party_size))
        template.required_equipment_tier = max(0, tier - 2)
    else:
        code, label, profile = BOSS_ARCHETYPES[position % len(BOSS_ARCHETYPES)]
        difficulty = "hard" if position == 0 and band_index < 2 else "heroic" if position % 3 else "legendary"
        duration_minutes = 30 + tier * 9 + (position % 4) * 8
        xp_factor = 0.92 + (0.08 if code == "endgame" else 0)
        gold_factor = 0.86 + (0.08 if code == "resistant" else 0)
        tank, support, damage = _roles_for(kind, code, position)
        if rename:
            template.name = _unique_name(BOSS_NAMES[global_index % len(BOSS_NAMES)], used_names, global_index)
        template.description = f"Desafio de chefe: {label}. {profile}"
        template.min_party_size = tank + support + damage
        template.max_party_size = 5
        template.required_total_power = max(60, round(level * (9.5 + tier * 0.55) * template.min_party_size))
        template.required_equipment_tier = max(1, tier - 1)
    template.recommended_level = level
    template.required_min_mercenary_level = max(low, level - max(1, (high - low) // max(4, total)))
    template.required_guild_level = min(50, max(1, ceil(level / 8)))
    template.required_building_type = "scouts"
    template.required_building_level = 1
    template.difficulty = difficulty
    template.duration_seconds = max(300, round(duration_minutes * 60))
    template.base_success_chance = _base_chance(kind, difficulty, band_index)
    template.base_xp_reward = max(100, round(xp_rate * xp_factor * template.duration_seconds / 3600))
    template.base_gold_reward = max(45, round(gold_rate * gold_factor * template.duration_seconds / 3600))
    template.required_tank_count = tank
    template.required_support_count = support
    template.required_damage_count = damage
    template.required_class_code = None
    template.is_active = True
    return {"id": template.id, "name": template.name, "band": band, "role": label, "level": level}


def _desired_rarity(kind: str, band_index: int, position: int) -> str:
    dungeon_cycles = (
        ("common", "uncommon", "uncommon", "rare"),
        ("uncommon", "uncommon", "rare", "rare", "epic"),
        ("uncommon", "rare", "rare", "epic"),
        ("rare", "rare", "epic", "legendary"),
        ("rare", "epic", "epic", "legendary"),
        ("rare", "epic", "legendary"),
        ("epic", "epic", "legendary", "mythic"),
        ("epic", "legendary", "legendary", "mythic"),
    )
    boss_cycles = (
        ("uncommon", "rare"), ("rare", "rare", "epic"), ("rare", "epic", "epic"),
        ("epic", "epic", "legendary"), ("epic", "legendary", "legendary"),
        ("epic", "legendary", "mythic"), ("legendary", "legendary", "mythic"),
        ("legendary", "mythic", "mythic"),
    )
    cycle = (boss_cycles if kind == "boss" else dungeon_cycles)[band_index]
    return cycle[position % len(cycle)]


def _drop_chance(kind: str, rarity: str, band_index: int) -> int:
    dungeon = {"common": 48, "uncommon": 40, "rare": 25, "epic": 12, "legendary": 4, "mythic": 1}
    boss = {"common": 46, "uncommon": 45, "rare": 38, "epic": 24, "legendary": 10, "mythic": 3}
    base = (boss if kind == "boss" else dungeon)[rarity]
    if rarity in {"rare", "epic", "legendary"}:
        base += min(5, band_index // 2)
    return min(60, base)


def _rebalance_drops(db: Session, active: list[DungeonTemplate]) -> int:
    items = list(db.scalars(select(ItemTemplate).where(ItemTemplate.is_active.is_(True))))
    grouped: dict[tuple[str, str, str], list[ItemTemplate]] = defaultdict(list)
    for item in items:
        grouped[(item.level_band, item.item_type, item.rarity)].append(item)
    adjusted = 0
    positions: dict[tuple[str, str], int] = defaultdict(int)
    for template in active:
        kind = "boss" if template.content_type == "boss" else "dungeon"
        band_index = LEVEL_BANDS.index(template.level_band)
        key = (template.level_band, kind)
        position = positions[key]
        positions[key] += 1
        desired = _desired_rarity(kind, band_index, position)
        equipment_candidates = grouped.get((template.level_band, "equipment", desired), [])
        if not equipment_candidates:
            for fallback in reversed(RARITY_ORDER[:RARITY_ORDER.index(desired) + 1]):
                equipment_candidates = grouped.get((template.level_band, "equipment", fallback), [])
                if equipment_candidates:
                    desired = fallback
                    break
        material_candidates = [item for item in items if item.level_band == template.level_band and item.item_type != "equipment"]
        drops = sorted(template.item_drops, key=lambda drop: drop.id)
        material_drop = next((drop for drop in drops if drop.item_template.item_type != "equipment"), None)
        equipment_drop = next((drop for drop in drops if drop.item_template.item_type == "equipment"), None)
        if material_drop and material_candidates:
            candidate = material_candidates[(position * 5 + band_index) % len(material_candidates)]
            material_drop.item_template_id = candidate.id
            material_drop.drop_chance = min(92, 62 + band_index * 3 + (18 if kind == "boss" else 0))
            material_drop.min_quantity = max(1, band_index + 1) * (2 if kind == "boss" else 1)
            material_drop.max_quantity = material_drop.min_quantity + (7 if kind == "boss" else 3)
            material_drop.is_active = True
            adjusted += 1
        if equipment_drop and equipment_candidates:
            candidate = equipment_candidates[(position * 7 + band_index) % len(equipment_candidates)]
            equipment_drop.item_template_id = candidate.id
            equipment_drop.drop_chance = _drop_chance(kind, candidate.rarity, band_index)
            equipment_drop.min_quantity = equipment_drop.max_quantity = 1
            equipment_drop.is_active = True
            adjusted += 1
    return adjusted


def apply_prd3_dungeon_balance(db: Session, force: bool = False) -> dict[str, object]:
    marker = db.scalar(select(ContentSeedRun).where(
        ContentSeedRun.pack_key == PRD3_PACK_KEY, ContentSeedRun.version == PRD3_VERSION,
    ))
    if marker is not None and not force:
        return json.loads(marker.report_json)

    templates = list(db.scalars(
        select(DungeonTemplate)
        .options(selectinload(DungeonTemplate.item_drops).selectinload(DungeonTemplateItemDrop.item_template))
        .order_by(DungeonTemplate.id)
    ))
    previous_marker = db.scalar(select(ContentSeedRun).where(
        ContentSeedRun.pack_key == PRD3_PACK_KEY,
        ContentSeedRun.version < PRD3_VERSION,
    ).order_by(ContentSeedRun.version.desc()))
    previous_report = json.loads(previous_marker.report_json) if previous_marker else {}
    before = previous_report.get("before", _content_snapshot(templates))
    before_catalog = previous_report.get("before_catalog", _catalog_snapshot(templates))
    used_names = {template.name for template in templates if template.name not in LEGACY_CURATED_NAMES | LEGACY_DUPLICATE_NAMES}
    kept: list[dict[str, object]] = []
    deactivated: list[dict[str, object]] = []
    active_curated: list[DungeonTemplate] = []
    global_indexes = {"dungeon": 0, "boss": 0}

    for duplicate in templates:
        if duplicate.content_pack != PACK_KEY and duplicate.name in LEGACY_DUPLICATE_NAMES and duplicate.is_active:
            duplicate.is_active = False
            deactivated.append({
                "id": duplicate.id, "name": duplicate.name, "band": duplicate.level_band,
                "type": duplicate.content_type, "reason": "Duplicata de conteúdo legado",
            })

    for band_index, band in enumerate(LEVEL_BANDS):
        xp_rate, gold_rate = _mission_reference_rates(db, band)
        for kind, targets in (("dungeon", DUNGEON_TARGETS), ("boss", BOSS_TARGETS)):
            legacy = [template for template in templates if (
                template.content_pack != PACK_KEY and template.is_active and template.name in LEGACY_CURATED_NAMES and
                template.content_type == kind and template.level_band == band
            )]
            external_count = sum(1 for template in templates if (
                template.content_pack != PACK_KEY and template.is_active and template not in legacy and
                template.content_type == kind and template.level_band == band
            ))
            target_generated = max(0, targets[band_index] - external_count - len(legacy))
            generated = [template for template in templates if (
                template.content_pack == PACK_KEY and template.content_type == kind and template.level_band == band
            )]
            generated.sort(key=lambda template: (template.recommended_level, template.id))
            selected = _even_selection(generated, target_generated)
            selected_ids = {template.id for template in selected}
            for template in generated:
                if template.id not in selected_ids:
                    template.is_active = False
                    deactivated.append({"id": template.id, "name": template.name, "band": band, "type": kind})
            curated = legacy + selected
            for position, template in enumerate(curated):
                legacy_name = template.name if template in legacy else None
                entry = _configure_template(
                    template, kind, position, len(curated), band_index, xp_rate, gold_rate,
                    used_names, global_indexes[kind],
                    rename=not (template.content_pack == PACK_KEY and template.description.startswith(("Especialidade:", "Desafio de chefe:"))),
                )
                if legacy_name:
                    legacy_titles = {
                        "Covil dos Lobos": "Covil da Lua de Caça",
                        "Fortaleza do Ogro": "Fortaleza do Punho de Pedra",
                        "Dragão das Cinzas": "Azhur, o Dragão das Cinzas",
                    }
                    template.name = legacy_titles[legacy_name]
                    used_names.add(template.name)
                    entry["name"] = template.name
                global_indexes[kind] += 1
                kept.append(entry)
                active_curated.append(template)

    drop_adjustments = _rebalance_drops(db, active_curated)
    after = _content_snapshot(templates)
    report = {
        "pack": PRD3_PACK_KEY, "version": PRD3_VERSION,
        "before": before, "after": after,
        "before_catalog": before_catalog,
        "kept": kept, "deactivated": deactivated,
        "drop_adjustments": drop_adjustments,
    }
    if marker is None:
        db.add(ContentSeedRun(pack_key=PRD3_PACK_KEY, version=PRD3_VERSION, report_json=json.dumps(report, ensure_ascii=False)))
    else:
        marker.report_json = json.dumps(report, ensure_ascii=False)
        db.add(marker)
    db.commit()
    return report


def dungeon_identity(template: DungeonTemplate) -> dict[str, str]:
    description = template.description or ""
    match = re.match(r"(?:Especialidade|Desafio de chefe): ([^.]+)\.", description)
    role = match.group(1) if match else ("Desafio de chefe" if template.content_type == "boss" else "Recompensa equilibrada")
    difficulty = template.difficulty or "normal"
    risk = {
        "normal": "Risco moderado", "hard": "Risco elevado",
        "heroic": "Risco alto", "legendary": "Risco extremo", "elite": "Risco extremo",
    }.get(difficulty, "Risco moderado")
    profile = description.split(". ", 1)[1] if ". " in description else "Grupo equilibrado dentro da faixa recomendada."
    return {"role": role, "risk": risk, "profile": profile}


def maximum_drop_rarity(template: DungeonTemplate) -> str:
    active = [drop.item_template.rarity for drop in template.item_drops if drop.is_active and drop.item_template]
    rarity = max(active, key=lambda value: RARITY_ORDER.index(value) if value in RARITY_ORDER else -1, default="common")
    return RARITY_LABELS.get(rarity, rarity.title())


def apply_dungeon_explorer_unlock_fix(db: Session) -> dict[str, int]:
    pack_key = "prd3_explorer_unlock_fix"
    marker = db.scalar(select(ContentSeedRun).where(
        ContentSeedRun.pack_key == pack_key,
        ContentSeedRun.version == 1,
    ))
    if marker is not None:
        return json.loads(marker.report_json)
    adjusted = 0
    for template in db.scalars(select(DungeonTemplate).where(
        DungeonTemplate.is_active.is_(True),
        DungeonTemplate.content_type.in_(("dungeon", "boss")),
        DungeonTemplate.required_building_type == "scouts",
        DungeonTemplate.required_building_level != 1,
    )):
        template.required_building_level = 1
        adjusted += 1
    report = {"adjusted": adjusted}
    db.add(ContentSeedRun(
        pack_key=pack_key,
        version=1,
        report_json=json.dumps(report, ensure_ascii=False),
    ))
    db.commit()
    return report
