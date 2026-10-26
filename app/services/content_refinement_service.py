import json
from datetime import datetime, timezone
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import ContentSeedRun
from app.models.building import BuildingTemplate
from app.models.achievement import AchievementTemplate, CodexEntry
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop, ItemTemplate, MissionTemplateItemDrop
from app.models.mission import MissionTemplate
from app.seeds.massive_content import BANDS, PACK_KEY


REFINEMENT_PACK_KEY = "refino_progressao_linear_pos_mvp034"
REFINEMENT_VERSION = 2

MISSION_TYPE_LABELS = {
    "combat": "combate", "patrol": "patrulha", "escort": "escolta", "hunt": "caçada",
    "exploration": "exploração", "investigation": "investigação", "defense": "defesa",
    "rescue": "resgate", "contract": "serviço da guilda", "story": "história",
    "elite": "ameaça de elite", "gathering": "coleta",
}
DIFFICULTY_LABELS = {
    "very_easy": "muito baixo", "easy": "baixo", "normal": "moderado", "hard": "alto",
    "dangerous": "perigoso", "heroic": "heroico", "legendary": "lendário", "elite": "de elite",
}
FAMILY_LABELS = {
    "wood": "madeira", "ore": "minérios", "herb": "ervas", "leather": "couros",
    "cloth": "fibras", "gem": "gemas", "relic": "relíquias", "essence": "essências",
}

BAND_REGIONS = {
    "1-20": ("Arredores da Guilda", "Bosque dos Sinos", "Estrada do Carvalho", "Colinas Brandas", "Vale dos Moinhos", "Ponte Velha"),
    "21-50": ("Fronteira Cinzenta", "Mata das Corujas", "Passagem do Norte", "Campos de Âmbar", "Lago das Brumas", "Ruínas do Vigia"),
    "51-100": ("Serra de Ferro", "Floresta Rubra", "Costa dos Ventos", "Pântano Luminoso", "Fortaleza Partida", "Deserto de Vidro"),
    "101-130": ("Terras Arcanas", "Cordilheira Rúnica", "Jardins Esquecidos", "Baía da Lua", "Planície dos Ecos", "Círculo Antigo"),
    "131-200": ("Marchas Sombrias", "Vale Carmesim", "Ermos Imperiais", "Bosque Petrificado", "Costa Afogada", "Muralha Sem Coroa"),
    "201-250": ("Domínios Dracônicos", "Fenda Celeste", "Mar de Cinzas", "Trono Partido", "Ilhas do Eclipse", "Bastião Eterno"),
    "251-300": ("Abismo Primordial", "Céu Estilhaçado", "Reino da Névoa", "Coroa do Vazio", "Santuário Solar", "Cidade Imortal"),
    "301-350": ("Limiar do Fim", "Aurora Extinta", "Império Esquecido", "Vazio Soberano", "Última Fortaleza", "Coração do Mundo"),
}

MISSION_VERBS = {
    "combat": ("Conter", "Derrotar", "Enfrentar", "Expulsar"),
    "patrol": ("Patrulhar", "Vigiar", "Inspecionar", "Guardar"),
    "escort": ("Escoltar", "Conduzir", "Proteger", "Acompanhar"),
    "hunt": ("Caçar", "Rastrear", "Cercar", "Abater"),
    "exploration": ("Explorar", "Mapear", "Desbravar", "Reconhecer"),
    "investigation": ("Investigar", "Decifrar", "Examinar", "Revelar"),
    "defense": ("Defender", "Fortificar", "Proteger", "Sustentar"),
    "rescue": ("Resgatar", "Localizar", "Salvar", "Recuperar"),
    "contract": ("Cumprir o Acordo em", "Atender o Chamado de", "Honrar o Pacto de", "Executar a Ordem em"),
    "story": ("Desvendar", "Restaurar", "Encontrar", "Recuperar"),
    "elite": ("Romper o Cerco de", "Vencer os Campeões de", "Eliminar a Ameaça em", "Dominar a Batalha de"),
}

MISSION_TARGETS = (
    "Batedores Hostis", "Salteadores da Estrada", "Feras Desgarradas", "Suprimentos Perdidos",
    "Caravana dos Artesãos", "Sentinelas Corrompidas", "Mensageiros da Guilda", "Relíquia Desaparecida",
    "Acampamento Inimigo", "Túneis Instáveis", "Peregrinos Cercados", "Sinais Misteriosos",
    "Mercadores Isolados", "Criaturas da Névoa", "Posto Avançado", "Mapa Fragmentado",
)

GATHERING_NAMES = {
    "wood": (("Coletar", "Cortar", "Separar"), ("Madeira de Carvalho", "Troncos Resistentes", "Resina Antiga")),
    "ore": (("Extrair", "Minerar", "Prospectar"), ("Minério de Ferro", "Veios Metálicos", "Pedra Mineral")),
    "herb": (("Colher", "Buscar", "Catalogar"), ("Ervas Medicinais", "Flores Raras", "Raízes Alquímicas")),
    "leather": (("Rastrear", "Recolher", "Preparar"), ("Couros de Fera", "Peles Resistentes", "Partes de Criatura")),
    "cloth": (("Separar", "Colher", "Preparar"), ("Fibras de Linho", "Fios Silvestres", "Tecidos Naturais")),
    "gem": (("Garimpar", "Lapidar", "Localizar"), ("Cristais Brutos", "Gemas Rúnicas", "Fragmentos Luminosos")),
    "relic": (("Recuperar", "Escavar", "Catalogar"), ("Relíquias Antigas", "Fragmentos Sagrados", "Insígnias Perdidas")),
    "essence": (("Extrair", "Concentrar", "Recolher"), ("Essências Arcanas", "Resíduos Mágicos", "Ecos Elementais")),
}

DUNGEON_PLACES = (
    "Cripta", "Fortaleza", "Santuário", "Caverna", "Torre", "Catacumbas",
    "Bastião", "Templo", "Labirinto", "Cidadela", "Abismo", "Biblioteca",
)
DUNGEON_SUBJECTS = (
    "Ossos Frios", "Lua Quebrada", "Chama Pálida", "Eco Profundo", "Vigia Caído", "Correntes Negras",
    "Rei Esquecido", "Dragão Cinzento", "Eclipse Vermelho", "Juramentos Partidos", "Cristais Rubros", "Sino Afogado",
)
DUNGEON_QUALIFIERS = (
    "Oculta", "Submersa", "Profanada", "Silenciosa", "Imperial", "Sem Retorno",
    "da Névoa", "do Último Pacto", "da Aurora", "do Véu Sombrio", "do Primeiro Reino", "da Coroa Perdida",
)

RARITY_LIMITS = {
    1: ((78, "common"), (98, "uncommon"), (100, "rare")),
    2: ((62, "common"), (90, "uncommon"), (99, "rare"), (100, "epic")),
    3: ((45, "common"), (78, "uncommon"), (95, "rare"), (100, "epic")),
    4: ((35, "common"), (67, "uncommon"), (90, "rare"), (99, "epic"), (100, "legendary")),
    5: ((28, "common"), (58, "uncommon"), (83, "rare"), (96, "epic"), (100, "legendary")),
    6: ((22, "common"), (48, "uncommon"), (74, "rare"), (92, "epic"), (99, "legendary"), (100, "mythic")),
    7: ((18, "common"), (41, "uncommon"), (68, "rare"), (89, "epic"), (98, "legendary"), (100, "mythic")),
    8: ((14, "common"), (34, "uncommon"), (61, "rare"), (85, "epic"), (97, "legendary"), (100, "mythic")),
}


def _tier_for_band(level_band: str) -> int:
    for band, _, _, tier, _ in BANDS:
        if band == level_band:
            return tier
    return 1


def _semantic_mission_name(mission: MissionTemplate, index: int) -> str:
    regions = BAND_REGIONS[mission.level_band]
    if mission.mission_type == "gathering":
        verbs, resources = GATHERING_NAMES.get(mission.gathering_family or "wood", GATHERING_NAMES["wood"])
        family_index = index // max(1, len(GATHERING_NAMES))
        return f"{verbs[family_index % len(verbs)]} {resources[(family_index // len(verbs)) % len(resources)]} em {regions[(family_index // (len(verbs) * len(resources))) % len(regions)]}"
    verbs = MISSION_VERBS.get(mission.mission_type, MISSION_VERBS["combat"])
    verb = verbs[index % len(verbs)]
    target = MISSION_TARGETS[(index // len(verbs)) % len(MISSION_TARGETS)]
    region = regions[(index // (len(verbs) * len(MISSION_TARGETS))) % len(regions)]
    return f"{verb} {target} em {region}"


def _semantic_dungeon_name(dungeon: DungeonTemplate, index: int) -> str:
    regions = BAND_REGIONS[dungeon.level_band]
    if dungeon.content_type == "boss":
        return f"Trono de {DUNGEON_SUBJECTS[index % len(DUNGEON_SUBJECTS)]} em {regions[(index // len(DUNGEON_SUBJECTS)) % len(regions)]}"
    place = DUNGEON_PLACES[index % len(DUNGEON_PLACES)]
    subject = DUNGEON_SUBJECTS[(index // len(DUNGEON_PLACES)) % len(DUNGEON_SUBJECTS)]
    qualifier = DUNGEON_QUALIFIERS[(index // (len(DUNGEON_PLACES) * len(DUNGEON_SUBJECTS))) % len(DUNGEON_QUALIFIERS)]
    return f"{place} dos {subject} {qualifier}"


def _unique_name(candidate: str, used: set[str], regions: tuple[str, ...], index: int) -> str:
    if candidate not in used:
        used.add(candidate)
        return candidate
    qualifiers = ("ao Amanhecer", "sob a Lua", "durante a Vigília", "no Crepúsculo", "sob Chuva", "na Longa Noite")
    for offset in range(len(qualifiers) * len(regions)):
        alternate = f"{candidate} {qualifiers[(index + offset) % len(qualifiers)]} de {regions[(index + offset) % len(regions)]}"
        if alternate not in used:
            used.add(alternate)
            return alternate[:120]
    raise ValueError(f"Não foi possível gerar nome único para {candidate}.")


def _rarity_for(tier: int, stable_index: int) -> str:
    roll = (stable_index * 37 + tier * 11) % 100 + 1
    for limit, rarity in RARITY_LIMITS.get(tier, RARITY_LIMITS[8]):
        if roll <= limit:
            return rarity
    return "common"


def _mission_balance(mission: MissionTemplate, index: int) -> None:
    level = max(1, mission.recommended_level)
    tier = _tier_for_band(mission.level_band)
    elite = mission.mission_type == "elite" or mission.difficulty in {"heroic", "legendary"}
    gathering = mission.mission_type == "gathering"
    difficulty_factor = 1.22 if elite else 1.0
    mission.required_min_mercenary_level = level
    mission.required_guild_level = min(50, max(1, ceil(level / 8)))
    mission.recommended_power = max(8, int((level * 2.3 + tier * 8) * (1.25 if elite else 1)))
    mission.duration_seconds = int((120 + level * 16 + tier * 90 + (index % 5) * 45) * (1.25 if elite else 1))
    mission.base_xp_reward = max(80, int((70 + level ** 1.55 * 3.3) * difficulty_factor * (0.62 if gathering else 1)))
    mission.base_gold_reward = max(15, int((12 + level ** 1.35 * 2.2) * difficulty_factor * (0.48 if gathering else 1)))
    base_by_tier = {1: 82, 2: 76, 3: 68, 4: 62, 5: 55, 6: 49, 7: 45, 8: 41}
    mission.base_success_chance = max(25, base_by_tier[tier] - (7 if elite else index % 5))
    if gathering:
        mission.base_success_chance = min(92, mission.base_success_chance + 10)
        mission.min_party_size = 1
        mission.max_party_size = min(3, 1 + tier // 3)
    mission.description = (
        f"Missão de coleta para obter {FAMILY_LABELS.get(mission.gathering_family or '', 'materiais')} na faixa de nível {mission.level_band}."
        if gathering else
        f"Missão de {MISSION_TYPE_LABELS.get(mission.mission_type, 'aventura')} recomendada para mercenários de nível {level}, com risco {DIFFICULTY_LABELS.get(mission.difficulty, 'moderado')}."
    )


def _dungeon_balance(dungeon: DungeonTemplate, index: int) -> None:
    level = max(1, dungeon.recommended_level)
    tier = _tier_for_band(dungeon.level_band)
    boss = dungeon.content_type == "boss"
    factor = 1.45 if boss else 1.0
    dungeon.required_min_mercenary_level = level
    dungeon.required_guild_level = min(50, max(1, ceil(level / 8)))
    dungeon.required_total_power = max(24, int((level * 6.5 + tier * 30) * factor))
    dungeon.duration_seconds = int((600 + level * 28 + tier * 240 + (index % 5) * 120) * (1.5 if boss else 1))
    dungeon.base_xp_reward = max(220, int((180 + level ** 1.58 * 5.2) * factor))
    dungeon.base_gold_reward = max(100, int((75 + level ** 1.38 * 4.5) * factor))
    base_by_tier = {1: 72, 2: 66, 3: 59, 4: 54, 5: 48, 6: 43, 7: 39, 8: 35}
    dungeon.base_success_chance = max(20, base_by_tier[tier] - (8 if boss else index % 4))
    dungeon.required_equipment_tier = max(0, tier - 2)
    regular_patterns = ((1, 0, 1), (0, 1, 1), (0, 0, 2), (1, 1, 0), (0, 1, 2), (1, 0, 2))
    boss_patterns = ((1, 1, 1), (2, 1, 1), (1, 2, 1), (1, 1, 2), (2, 0, 2), (0, 2, 2))
    tank, support, damage = (boss_patterns if boss else regular_patterns)[index % 6]
    dungeon.required_tank_count = tank
    dungeon.required_support_count = support
    dungeon.required_damage_count = damage
    if boss:
        dungeon.min_party_size = max(3, tank + support + damage)
        dungeon.max_party_size = max(dungeon.min_party_size, 5)
    dungeon.description = (
        f"Chefe guardião em uma região de {dungeon.biome or 'origem desconhecida'}, recomendado para grupos de nível {level}."
        if boss else
        f"Masmorra de {dungeon.biome or 'exploração'} para grupos de nível {level}, com composição e equipamentos preparados."
    )


def _rebalance_items_and_drops(db: Session) -> dict[str, int]:
    items = list(db.scalars(select(ItemTemplate).where(ItemTemplate.content_pack == PACK_KEY).order_by(ItemTemplate.id)))
    items_by_band_family: dict[tuple[str, str], list[ItemTemplate]] = {}
    equipment_by_band: dict[str, list[ItemTemplate]] = {}
    for index, item in enumerate(items):
        tier = max(1, item.tier)
        item.rarity = _rarity_for(tier, index)
        item.base_sell_value = max(2, int((item.item_level + 4) * tier * (1.8 if item.item_type == "equipment" else 0.45)))
        if item.item_type == "equipment":
            equipment_by_band.setdefault(item.level_band, []).append(item)
            item.rng_bonus_min = max(1, tier)
            item.rng_bonus_max = max(item.rng_bonus_min, tier * 3 + item.item_level // 40)
        elif item.material_family:
            items_by_band_family.setdefault((item.level_band, item.material_family), []).append(item)

    mission_drops = list(db.scalars(select(MissionTemplateItemDrop).join(MissionTemplate).where(MissionTemplate.content_pack == PACK_KEY).order_by(MissionTemplateItemDrop.id)))
    for index, drop in enumerate(mission_drops):
        mission = drop.mission_template
        tier = _tier_for_band(mission.level_band)
        if drop.item_template.item_type == "material":
            family = mission.gathering_family or drop.item_template.material_family or "wood"
            candidates = items_by_band_family.get((mission.level_band, family))
            if candidates:
                drop.item_template_id = candidates[index % len(candidates)].id
            drop.drop_chance = 88 if mission.mission_type == "gathering" else max(28, 58 - tier * 3)
            quantity_ranges = {1: (1, 3), 2: (2, 4), 3: (3, 6), 4: (4, 7), 5: (5, 9), 6: (6, 10), 7: (7, 11), 8: (8, 12)}
            drop.min_quantity, drop.max_quantity = quantity_ranges[tier]
        else:
            candidates = equipment_by_band.get(mission.level_band)
            if candidates:
                drop.item_template_id = candidates[index % len(candidates)].id
            drop.drop_chance = max(2, 11 - tier // 2)
            drop.min_quantity = drop.max_quantity = 1

    dungeon_drops = list(db.scalars(select(DungeonTemplateItemDrop).join(DungeonTemplate).where(DungeonTemplate.content_pack == PACK_KEY).order_by(DungeonTemplateItemDrop.id)))
    for index, drop in enumerate(dungeon_drops):
        dungeon = drop.dungeon_template
        tier = _tier_for_band(dungeon.level_band)
        if drop.item_template.item_type == "material":
            family = drop.item_template.material_family or "relic"
            candidates = items_by_band_family.get((dungeon.level_band, family))
            if candidates:
                drop.item_template_id = candidates[index % len(candidates)].id
            drop.drop_chance = min(90, 62 + tier * 2)
            drop.min_quantity = max(1, tier)
            drop.max_quantity = tier + 3
        else:
            candidates = equipment_by_band.get(dungeon.level_band)
            if candidates:
                drop.item_template_id = candidates[(index * 7) % len(candidates)].id
            drop.drop_chance = min(32, 10 + tier * 2 + (8 if dungeon.content_type == "boss" else 0))
            drop.min_quantity = drop.max_quantity = 1
    return {"items": len(items), "mission_drops": len(mission_drops), "dungeon_drops": len(dungeon_drops)}


def run_progression_refinement(db: Session, force: bool = False) -> dict[str, object]:
    marker = db.scalar(select(ContentSeedRun).where(
        ContentSeedRun.pack_key == REFINEMENT_PACK_KEY,
        ContentSeedRun.version == REFINEMENT_VERSION,
    ))
    if marker is not None and not force:
        return json.loads(marker.report_json)

    used_mission_names = set(db.scalars(select(MissionTemplate.name).where(MissionTemplate.content_pack != PACK_KEY)))
    missions = list(db.scalars(select(MissionTemplate).where(MissionTemplate.content_pack == PACK_KEY).order_by(MissionTemplate.level_band, MissionTemplate.slug)))
    band_positions: dict[str, int] = {}
    for mission in missions:
        index = band_positions.get(mission.level_band, 0)
        regions = BAND_REGIONS[mission.level_band]
        mission.name = _unique_name(_semantic_mission_name(mission, index), used_mission_names, regions, index)
        _mission_balance(mission, index)
        band_positions[mission.level_band] = index + 1

    used_dungeon_names = set(db.scalars(select(DungeonTemplate.name).where(DungeonTemplate.content_pack != PACK_KEY)))
    dungeons = list(db.scalars(select(DungeonTemplate).where(DungeonTemplate.content_pack == PACK_KEY).order_by(DungeonTemplate.level_band, DungeonTemplate.slug)))
    band_positions = {}
    for dungeon in dungeons:
        index = band_positions.get(dungeon.level_band, 0)
        regions = BAND_REGIONS[dungeon.level_band]
        dungeon.name = _unique_name(_semantic_dungeon_name(dungeon, index), used_dungeon_names, regions, index)
        _dungeon_balance(dungeon, index)
        band_positions[dungeon.level_band] = index + 1

    drop_report = _rebalance_items_and_drops(db)
    from app.services.class_service import refine_class_catalog
    from app.services.skill_service import refine_class_skills
    classes_refined = refine_class_catalog(db)
    skills_refined = refine_class_skills(db)
    contract_office = db.scalar(select(BuildingTemplate).where(BuildingTemplate.effect_type == "contract_office"))
    if contract_office is not None:
        contract_office.name = "Escritório de Missões"
        contract_office.description = "Permite aceitar missões com grupos maiores."
    for achievement in db.scalars(select(AchievementTemplate)):
        achievement.title = achievement.title.replace("Contratos", "Missões").replace("Dungeons", "Masmorras")
        achievement.description = achievement.description.replace("dungeons", "masmorras").replace("contratos", "missões")
    dungeon_by_id = {str(dungeon.id): dungeon for dungeon in dungeons}
    for entry in db.scalars(select(CodexEntry).where(CodexEntry.category == "dungeon")):
        dungeon = dungeon_by_id.get(entry.reference_key)
        if dungeon is not None:
            entry.title = dungeon.name
            entry.description = dungeon.description
    report = {
        "pack": REFINEMENT_PACK_KEY,
        "version": REFINEMENT_VERSION,
        "missions_refined": len(missions),
        "dungeons_refined": len(dungeons),
        "classes_refined": classes_refined,
        "skills_refined": skills_refined,
        **drop_report,
    }
    if marker is None:
        db.add(ContentSeedRun(
            pack_key=REFINEMENT_PACK_KEY,
            version=REFINEMENT_VERSION,
            report_json=json.dumps(report, ensure_ascii=False),
            applied_at=datetime.now(timezone.utc),
        ))
    else:
        marker.report_json = json.dumps(report, ensure_ascii=False)
    db.commit()
    return report
