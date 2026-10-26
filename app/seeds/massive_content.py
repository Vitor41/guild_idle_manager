import json
import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.building import BuildingTemplate
from app.models.content import ContentSeedRun, ProfessionTemplate
from app.models.dock import MerchantOfferTemplate, MerchantTemplate
from app.models.dungeon import DungeonTemplate
from app.models.item import DungeonTemplateItemDrop, ItemTemplate, MissionTemplateItemDrop
from app.models.mission import MissionTemplate


PACK_KEY = "conteudo_massivo_pos_mvp026"
PACK_VERSION = 3
BANDS = (
    ("1-20", 1, 20, 1, (10, 25, 45)),
    ("21-50", 21, 50, 2, (45, 90, 150)),
    ("51-100", 51, 100, 3, (150, 280, 450)),
    ("101-130", 101, 130, 4, (450, 650, 850)),
    ("131-200", 131, 200, 5, (850, 1300, 1900)),
    ("201-250", 201, 250, 6, (1900, 2500, 3200)),
    ("251-300", 251, 300, 7, (3200, 4100, 5200)),
    ("301-350", 301, 350, 8, (5200, 6500, 8000)),
)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", normalized.lower())).strip("_")


def _rarity(index: int) -> str:
    roll = index % 100
    if roll < 60:
        return "common"
    if roll < 85:
        return "uncommon"
    if roll < 95:
        return "rare"
    if roll < 99:
        return "epic"
    return "legendary" if index % 500 else "mythic"


def _band_for_index(index: int):
    return BANDS[index % len(BANDS)]


def _material_rows() -> list[dict[str, object]]:
    families = {
        "wood": ("Madeira", 40, ["Bruta", "de Carvalho", "Sombria", "Arcana", "Ancestral"]),
        "ore": ("Minério", 50, ["de Cobre", "de Ferro", "de Prata", "de Mithril", "Estelar"]),
        "stone": ("Pedra", 30, ["Rústica", "Talhada", "Rúnica", "Lunar", "Primordial"]),
        "leather": ("Couro", 35, ["Cru", "Curtido", "de Fera", "Dracônico", "Ancestral"]),
        "cloth": ("Fibra", 35, ["Silvestre", "de Linho", "Prateada", "Arcana", "Celestial"]),
        "herb": ("Erva", 45, ["Verde", "Curativa", "Sombria", "Lunar", "do Eclipse"]),
        "essence": ("Essência", 40, ["Natural", "Ígnea", "Sombria", "Astral", "Primordial"]),
        "gem": ("Gema", 35, ["Bruta", "Azul", "Rúnica", "Estelar", "do Vazio"]),
        "beast": ("Parte de Criatura", 35, ["Presa", "Garra", "Osso", "Escama", "Chifre"]),
        "relic": ("Fragmento", 40, ["Antigo", "Rúnico", "Sagrado", "Imperial", "Esquecido"]),
        "catalyst": ("Catalisador", 30, ["Simples", "Alquímico", "Arcano", "Abissal", "Eterno"]),
        "insignia": ("Insígnia", 20, ["de Bronze", "de Prata", "Dourada", "Heroica", "Lendária"]),
    }
    rows: list[dict[str, object]] = []
    global_index = 0
    for family, (base, count, variants) in families.items():
        for local_index in range(count):
            band, low, high, tier, _ = _band_for_index(local_index)
            variant = variants[(local_index // len(BANDS)) % len(variants)]
            name = f"{base} {variant} {tier}-{local_index + 1:02d}"
            rows.append({
                "slug": f"material_{family}_{tier}_{local_index + 1:03d}",
                "name": name,
                "description": f"Recurso de {base.lower()} obtido em regiões de nível {low} a {high}.",
                "item_type": "material",
                "rarity": _rarity(global_index),
                "item_level": low + (local_index % max(1, high - low + 1)),
                "level_band": band,
                "tier": tier,
                "content_pack": PACK_KEY,
                "material_family": family,
                "icon_group": family,
                "required_level": low,
                "base_sell_value": max(2, tier * tier * 3),
                "is_active": True,
            })
            global_index += 1
    return rows


def _equipment_rows() -> list[dict[str, object]]:
    categories = (
        (700, [
            ("Espada", "main_hand", "sword", "warrior", "power"),
            ("Machado", "main_hand", "axe", "warrior", "power"),
            ("Martelo", "main_hand", "mace", "cleric", "vitality"),
            ("Lança", "main_hand", "spear", "warrior", "power"),
            ("Adaga", "main_hand", "dagger", "rogue", "agility"),
            ("Rapieira", "main_hand", "sword", "rogue", "agility"),
            ("Cajado", "main_hand", "staff", "mage", "intelligence"),
            ("Varinha", "main_hand", "wand", "mage", "intelligence"),
            ("Grimório", "off_hand", "book", "mage", "intelligence"),
            ("Cetro", "main_hand", "mace", "cleric", "intelligence"),
            ("Arco", "main_hand", "bow", "archer", "agility"),
            ("Besta", "main_hand", "bow", "archer", "luck"),
            ("Escudo", "shield", "shield", "warrior", "vitality"),
        ]),
        (500, [
            ("Elmo", "helmet", "helmet", "warrior", "vitality"),
            ("Peitoral de Placas", "chest", "heavy_armor", "warrior", "vitality"),
            ("Cota de Malha", "chest", "medium_armor", "cleric", "vitality"),
            ("Armadura de Couro", "chest", "light_armor", "rogue", "agility"),
            ("Túnica", "chest", "robe", "mage", "intelligence"),
            ("Luvas", "gloves", "gloves", "archer", "agility"),
            ("Botas", "boots", "boots", "rogue", "agility"),
        ]),
        (500, [
            ("Anel", "ring", "ring", "any", "luck"),
            ("Amuleto", "necklace", "necklace", "any", "intelligence"),
            ("Brinco", "earring", "earring", "any", "agility"),
            ("Cinto", "belt", "belt", "any", "vitality"),
            ("Medalhão", "necklace", "necklace", "cleric", "intelligence"),
            ("Talismã", "ring", "ring", "mage", "luck"),
        ]),
    )
    prefixes = {
        "common": ["Simples", "Rústico", "Antigo"], "uncommon": ["Reforçado", "Polido", "Afiado"],
        "rare": ["Sombrio", "Flamejante", "Rúnico"], "epic": ["Ancestral", "Celestial", "Dracônico"],
        "legendary": ["Primordial", "Eterno", "Estelar"], "mythic": ["Mítico", "Transcendente", "Soberano"],
    }
    suffixes = {"power": "da Força", "agility": "da Precisão", "intelligence": "do Arcano", "vitality": "da Fortaleza", "luck": "da Fortuna"}
    rarity_names = {"common": "comum", "uncommon": "incomum", "rare": "raro", "epic": "épico", "legendary": "lendário", "mythic": "mítico"}
    rows: list[dict[str, object]] = []
    global_index = 0
    for count, bases in categories:
        for local_index in range(count):
            band, low, high, tier, _ = _band_for_index(global_index)
            base, slot, icon, class_code, attribute = bases[local_index % len(bases)]
            rarity = _rarity(global_index)
            prefix = prefixes[rarity][(local_index // len(bases)) % 3]
            name = f"{base} {prefix} {suffixes[attribute]} {tier}-{local_index + 1:03d}"
            level = low + (local_index % max(1, high - low + 1))
            bonus = max(1, tier * 2 + level // 20)
            data: dict[str, object] = {
                "slug": f"equipamento_{global_index + 1:05d}", "name": name,
                "description": f"Equipamento {rarity_names[rarity]} indicado para progressão entre os níveis {low} e {high}.",
                "item_type": "equipment", "rarity": rarity, "item_level": level, "level_band": band,
                "tier": tier, "content_pack": PACK_KEY, "equipment_slot": slot, "icon_group": icon,
                "required_level": level, "favored_class_code": class_code, "favored_attribute": attribute,
                "base_sell_value": max(20, tier * tier * 35), "bonus_power": bonus if attribute == "power" else max(1, tier),
                "bonus_vitality": bonus if attribute == "vitality" else 0,
                "bonus_agility": bonus if attribute == "agility" else 0,
                "bonus_intelligence": bonus if attribute == "intelligence" else 0,
                "bonus_luck": bonus if attribute == "luck" else 0,
                "bonus_armor": bonus if slot in {"helmet", "chest", "gloves", "boots", "shield"} else 0,
                "rng_bonus_min": max(1, tier), "rng_bonus_max": max(2, tier * 3), "is_active": True,
            }
            rows.append(data)
            global_index += 1
    return rows


def _mission_rows() -> list[dict[str, object]]:
    counts = (140, 170, 220, 150, 280, 230, 230, 240)
    types = ["combat", "patrol", "escort", "hunt", "exploration", "investigation", "defense", "rescue", "contract", "story"]
    actions = ["Patrulha", "Caçada", "Escolta", "Exploração", "Defesa", "Resgate", "Investigação", "Contrato"]
    places = ["Bosque", "Estrada", "Vale", "Fortaleza", "Santuário", "Fronteira", "Desfiladeiro", "Ruínas"]
    type_names = {"combat": "combate", "patrol": "patrulha", "escort": "escolta", "hunt": "caçada", "exploration": "exploração", "investigation": "investigação", "defense": "defesa", "rescue": "resgate", "contract": "contrato", "story": "história", "elite": "elite"}
    rows: list[dict[str, object]] = []
    order = 1000
    for band_index, count in enumerate(counts):
        band, low, high, tier, power = BANDS[band_index]
        for index in range(count):
            elite = index >= count - max(20, count // 5)
            difficulty = "legendary" if elite and index % 7 == 0 else "heroic" if elite else ["very_easy", "easy", "normal", "hard", "dangerous"][index % 5]
            mission_type = "elite" if elite else types[index % len(types)]
            level = low + (index % (high - low + 1))
            name = f"{actions[index % len(actions)]} no {places[(index // len(actions)) % len(places)]} {tier}-{index + 1:03d}"
            rows.append({
                "slug": f"missao_{band_index + 1}_{index + 1:04d}", "name": name,
                "description": f"Contrato de {type_names[mission_type]} recomendado para grupos próximos do nível {level}.",
                "display_order": order, "difficulty": difficulty, "level_band": band, "mission_type": mission_type,
                "content_pack": PACK_KEY, "recommended_level": level, "recommended_power": power[min(2, index % 3)],
                "duration_seconds": max(180, 120 + level * 18 + (600 if elite else 0)),
                "base_gold_reward": max(10, level * (3 if elite else 2)), "base_xp_reward": max(8, level * (2 if elite else 1)),
                "base_success_chance": max(35, 88 - band_index * 4 - (12 if elite else index % 10)),
                "min_party_size": 2 if elite else 1, "max_party_size": min(5, 2 + band_index // 2 + (1 if elite else 0)),
                "required_guild_level": min(50, max(1, level // 7)), "required_min_mercenary_level": low,
                "required_building_type": "contract_office" if index % 4 == 0 else None,
                "required_building_level": min(100, tier * 2) if index % 4 == 0 else 0, "is_active": True,
            })
            order += 1
    return rows


def _gathering_rows() -> list[dict[str, object]]:
    counts = (60, 70, 80, 60, 90, 70, 70, 70)
    professions = [
        ("wood", "woodcutter", "Extração de Madeira"), ("ore", "miner", "Mineração"),
        ("herb", "herbalist", "Colheita de Ervas"), ("leather", "leatherworker", "Rastreamento de Feras"),
        ("cloth", "weaver", "Coleta de Fibras"), ("gem", "prospector", "Garimpo de Gemas"),
        ("relic", "reliquary", "Busca por Relíquias"), ("essence", "alchemist", "Extração de Essências"),
    ]
    rows: list[dict[str, object]] = []
    family_names = {"wood": "madeiras", "ore": "minérios", "herb": "ervas", "leather": "couros", "cloth": "fibras", "gem": "gemas", "relic": "relíquias", "essence": "essências"}
    order = 5000
    for band_index, count in enumerate(counts):
        band, low, high, tier, power = BANDS[band_index]
        for index in range(count):
            family, profession, action = professions[index % len(professions)]
            level = low + index % (high - low + 1)
            rows.append({
                "slug": f"coleta_{band_index + 1}_{index + 1:04d}", "name": f"{action} {tier}-{index + 1:03d}",
                "description": f"Expedição segura para obter {family_names[family]}.",
                "display_order": order, "difficulty": "easy" if index % 3 else "normal", "level_band": band,
                "mission_type": "gathering", "content_pack": PACK_KEY, "recommended_level": level,
                "recommended_power": power[0], "gathering_family": family, "profession_code": profession,
                "duration_seconds": max(180, 180 + level * 12), "base_gold_reward": max(5, level),
                "base_xp_reward": max(4, level // 2), "base_success_chance": max(65, 94 - band_index * 3),
                "min_party_size": 1, "max_party_size": min(3, 1 + band_index // 3),
                "required_guild_level": min(50, max(1, level // 8)), "required_min_mercenary_level": low,
                "required_building_type": None, "required_building_level": 0, "is_active": True,
            })
            order += 1
    return rows


def _dungeon_rows() -> list[dict[str, object]]:
    counts = (36, 48, 72, 48, 84, 72, 72, 84)
    boss_counts = (5, 8, 12, 8, 15, 12, 12, 28)
    biomes = ["mines", "woods", "catacombs", "ruins", "fortress", "tower", "caves", "swamp", "sanctuary", "portal", "abyss", "lost_city"]
    biome_names = ["Minas", "Bosque", "Catacumbas", "Ruínas", "Fortaleza", "Torre", "Cavernas", "Pântano", "Santuário", "Portal", "Abismo", "Cidade Perdida"]
    difficulties = ["normal", "hard", "heroic", "legendary"]
    rows: list[dict[str, object]] = []
    for band_index, count in enumerate(counts):
        band, low, high, tier, power = BANDS[band_index]
        for index in range(count + boss_counts[band_index]):
            is_boss = index >= count
            level = low + index % (high - low + 1)
            biome_index = index % len(biomes)
            name = ("Covil do Guardião" if is_boss else biome_names[biome_index]) + f" {tier}-{index + 1:03d}"
            rows.append({
                "slug": f"{'boss' if is_boss else 'dungeon'}_{band_index + 1}_{index + 1:04d}", "name": name,
                "description": f"Desafio de {biome_names[biome_index].lower()} para grupos próximos do nível {level}.",
                "content_type": "boss" if is_boss else "dungeon", "content_pack": PACK_KEY, "level_band": band,
                "recommended_level": level, "biome": biomes[biome_index],
                "difficulty": "legendary" if is_boss else difficulties[index % len(difficulties)],
                "duration_seconds": 900 + level * 30 + (1800 if is_boss else 0),
                "base_gold_reward": level * (8 if is_boss else 4), "base_xp_reward": level * (5 if is_boss else 3),
                "base_success_chance": max(25, 68 - band_index * 3 - (12 if is_boss else index % 8)),
                "min_party_size": 3 if is_boss else 2, "max_party_size": 5,
                "required_guild_level": min(50, max(1, level // 7)), "required_min_mercenary_level": low,
                "required_building_type": "scouts", "required_building_level": min(100, max(1, tier * 3)),
                "required_total_power": power[2] if is_boss else power[1], "required_class_code": None,
                "required_tank_count": 1 if is_boss else 0, "required_support_count": 1 if is_boss else 0,
                "required_damage_count": 1 if is_boss else 0, "required_equipment_tier": max(0, tier - 1), "is_active": True,
            })
    return rows


PROFESSIONS = (
    ("woodcutter", "Lenhador", "wood"), ("miner", "Minerador", "ore"),
    ("herbalist", "Herborista", "herb"), ("leatherworker", "Coureiro", "leather"),
    ("weaver", "Tecelão", "cloth"), ("prospector", "Garimpeiro", "gem"),
    ("reliquary", "Relicário", "relic"), ("alchemist", "Alquimista", "essence"),
)


def _insert_missing(db: Session, model, rows: list[dict[str, object]], key: str) -> list:
    existing = set(db.scalars(select(getattr(model, key))))
    objects = [model(**row) for row in rows if row[key] not in existing]
    db.add_all(objects)
    if objects:
        db.flush()
    return objects


def run_massive_content_seed(db: Session) -> dict[str, object]:
    marker = db.scalar(select(ContentSeedRun).where(ContentSeedRun.pack_key == PACK_KEY, ContentSeedRun.version == PACK_VERSION))
    if marker is not None:
        return json.loads(marker.report_json)

    legacy_names = {"Cacar lobos", "Patrulhar estrada", "Escoltar comerciante", "Limpar caverna pequena"}
    for legacy in db.scalars(select(MissionTemplate).where(MissionTemplate.name.in_(legacy_names))):
        legacy.is_active = False
        db.add(legacy)

    rarity_labels = {"common": "comum", "uncommon": "incomum", "rare": "raro", "epic": "épico", "legendary": "lendário", "mythic": "mítico"}
    mission_type_labels = {"combat": "combate", "patrol": "patrulha", "escort": "escolta", "hunt": "caçada", "exploration": "exploração", "investigation": "investigação", "defense": "defesa", "rescue": "resgate", "contract": "contrato", "story": "história", "elite": "elite"}
    family_labels = {"wood": "madeiras", "ore": "minérios", "herb": "ervas", "leather": "couros", "cloth": "fibras", "gem": "gemas", "relic": "relíquias", "essence": "essências"}
    for item in db.scalars(select(ItemTemplate).where(ItemTemplate.content_pack == PACK_KEY, ItemTemplate.item_type == "equipment")):
        if item.description.startswith("Equipamento "):
            item.description = f"Equipamento {rarity_labels.get(item.rarity, item.rarity)} indicado para progressão entre os níveis {item.level_band}."
            db.add(item)
    for mission in db.scalars(select(MissionTemplate).where(MissionTemplate.content_pack == PACK_KEY)):
        if mission.description.startswith("Contrato de "):
            mission.description = f"Contrato de {mission_type_labels.get(mission.mission_type, mission.mission_type)} recomendado para grupos próximos do nível {mission.recommended_level}."
        elif mission.description.startswith("Expedição segura para obter recursos da família "):
            mission.description = f"Expedição segura para obter {family_labels.get(mission.gathering_family or '', mission.gathering_family or 'materiais')}."
        db.add(mission)

    materials = _material_rows()
    equipment = _equipment_rows()
    _insert_missing(db, ItemTemplate, materials + equipment, "slug")
    item_map = {item.slug: item for item in db.scalars(select(ItemTemplate).where(ItemTemplate.content_pack == PACK_KEY))}

    _insert_missing(db, MissionTemplate, _mission_rows() + _gathering_rows(), "slug")
    mission_map = {item.slug: item for item in db.scalars(select(MissionTemplate).where(MissionTemplate.content_pack == PACK_KEY))}
    _insert_missing(db, DungeonTemplate, _dungeon_rows(), "slug")
    dungeon_map = {item.slug: item for item in db.scalars(select(DungeonTemplate).where(DungeonTemplate.content_pack == PACK_KEY))}

    _insert_missing(db, ProfessionTemplate, [
        {"code": code, "name": name, "description": f"Especialista em coleta de {family_labels.get(family, family)}.", "material_family": family,
         "bonus_percent": 15, "training_gold_cost": 250, "training_duration_seconds": 3600, "is_active": True}
        for code, name, family in PROFESSIONS
    ], "code")
    for profession in db.scalars(select(ProfessionTemplate)):
        if profession.description.startswith("Especialista em coletas da família "):
            profession.description = f"Especialista em coleta de {family_labels.get(profession.material_family, profession.material_family)}."
            db.add(profession)

    if db.scalar(select(BuildingTemplate).where(BuildingTemplate.effect_type == "docks")) is None:
        db.add(BuildingTemplate(name="Docas", description="Recebe mercantes rotativos com materiais e equipamentos.", effect_type="docks",
            base_upgrade_gold_cost=500, base_upgrade_wood_cost=100, base_upgrade_ore_cost=50, base_upgrade_crystals_cost=0,
            max_level=50, required_guild_level=1, is_active=True))
        db.flush()

    mission_ids = list(mission_map.values())
    dungeon_ids = list(dungeon_map.values())
    material_items = [item_map[row["slug"]] for row in materials]
    equipment_items = [item_map[row["slug"]] for row in equipment]
    existing_mission_pairs = set(db.execute(select(MissionTemplateItemDrop.mission_template_id, MissionTemplateItemDrop.item_template_id)).all())
    mission_drops = []
    for index, mission in enumerate(mission_ids):
        material = material_items[index % len(material_items)]
        pair = (mission.id, material.id)
        if pair not in existing_mission_pairs:
            mission_drops.append(MissionTemplateItemDrop(mission_template_id=mission.id, item_template_id=material.id,
                drop_chance=90 if mission.mission_type == "gathering" else 55, min_quantity=1, max_quantity=max(2, material.tier + 2), is_active=True))
            existing_mission_pairs.add(pair)
    for index, equipment_item in enumerate(equipment_items):
        mission = mission_ids[index % len(mission_ids)]
        pair = (mission.id, equipment_item.id)
        if pair not in existing_mission_pairs:
            mission_drops.append(MissionTemplateItemDrop(mission_template_id=mission.id, item_template_id=equipment_item.id,
                drop_chance=max(1, 18 - equipment_item.tier), min_quantity=1, max_quantity=1, is_active=True))
    db.add_all(mission_drops)

    existing_dungeon_pairs = set(db.execute(select(DungeonTemplateItemDrop.dungeon_template_id, DungeonTemplateItemDrop.item_template_id)).all())
    dungeon_drops = []
    for index, dungeon in enumerate(dungeon_ids):
        for item in (material_items[index % len(material_items)], equipment_items[index % len(equipment_items)]):
            pair = (dungeon.id, item.id)
            if pair not in existing_dungeon_pairs:
                dungeon_drops.append(DungeonTemplateItemDrop(dungeon_template_id=dungeon.id, item_template_id=item.id,
                    drop_chance=75 if item.item_type == "material" else (20 if dungeon.content_type == "boss" else 10),
                    min_quantity=1, max_quantity=max(1, item.tier), is_active=True))
                existing_dungeon_pairs.add(pair)
    db.add_all(dungeon_drops)
    db.flush()

    merchant_types = ["wood", "ore", "herb", "gem", "leather", "cloth", "relic", "essence", "forge", "armor", "rare", "smuggler", "guild"]
    merchant_rows = []
    for index in range(80):
        merchant_type = merchant_types[index % len(merchant_types)]
        merchant_label = {"wood": "de Madeiras", "ore": "de Minérios", "herb": "Herborista", "gem": "de Gemas", "leather": "de Couros", "cloth": "de Tecidos", "relic": "de Relíquias", "essence": "de Essências", "forge": "Ferreiro", "armor": "Armeiro", "rare": "Colecionador", "smuggler": "Contrabandista", "guild": "Emissário"}[merchant_type]
        merchant_rows.append({"slug": f"mercante_{index + 1:03d}", "name": f"Mercante {merchant_label} {index + 1:02d}",
            "description": "Viajante das Docas com um estoque próprio e temporário.", "merchant_type": merchant_type,
            "min_dock_level": 1 + index % 10, "rotation_weight": max(10, 100 - index // 2), "content_pack": PACK_KEY, "is_active": True})
    _insert_missing(db, MerchantTemplate, merchant_rows, "slug")
    merchant_name_labels = {row["slug"]: row["name"] for row in merchant_rows}
    for merchant in db.scalars(select(MerchantTemplate).where(MerchantTemplate.content_pack == PACK_KEY)):
        if re.match(r"^Mercante [A-Za-z]+ \d{2}$", merchant.name):
            merchant.name = str(merchant_name_labels.get(merchant.slug, merchant.name))
            db.add(merchant)
    merchants = list(db.scalars(select(MerchantTemplate).where(MerchantTemplate.content_pack == PACK_KEY).order_by(MerchantTemplate.id)))
    offer_items = material_items + equipment_items
    existing_offer_pairs = set(db.execute(select(MerchantOfferTemplate.merchant_template_id, MerchantOfferTemplate.item_template_id)).all())
    offers = []
    for merchant_index, merchant in enumerate(merchants):
        for offset in range(15):
            item = offer_items[(merchant_index * 23 + offset * 7) % len(offer_items)]
            pair = (merchant.id, item.id)
            if pair in existing_offer_pairs:
                continue
            equipment_stock = item.item_type == "equipment"
            offers.append(MerchantOfferTemplate(merchant_template_id=merchant.id, item_template_id=item.id,
                base_price=max(item.base_sell_value + 1, int(item.base_sell_value * (2.5 + item.tier * 0.2))),
                min_stock=1 if equipment_stock else 5, max_stock=1 if equipment_stock else 20 + item.tier * 10,
                min_dock_level=max(1, min(10, item.tier)), weight=max(1, 120 - item.tier * 10), is_active=True))
            existing_offer_pairs.add(pair)
    db.add_all(offers)
    db.flush()

    report = {
        "pack": PACK_KEY, "version": PACK_VERSION, "materials": len(material_items), "equipment": len(equipment_items),
        "missions": sum(1 for mission in mission_ids if mission.mission_type != "gathering"),
        "gathering_missions": sum(1 for mission in mission_ids if mission.mission_type == "gathering"),
        "dungeons": sum(1 for dungeon in dungeon_ids if dungeon.content_type == "dungeon"),
        "bosses": sum(1 for dungeon in dungeon_ids if dungeon.content_type == "boss"),
        "professions": len(PROFESSIONS), "merchants": len(merchants), "dock_offers": len(existing_offer_pairs), "errors": [],
    }
    db.add(ContentSeedRun(pack_key=PACK_KEY, version=PACK_VERSION, report_json=json.dumps(report, ensure_ascii=False), applied_at=datetime.now(timezone.utc)))
    db.commit()
    return report
