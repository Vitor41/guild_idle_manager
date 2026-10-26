import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.models.item import GuildInventoryItem, GuildItemInstance, ItemTemplate


STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
ITEM_MANIFEST_PATH = STATIC_ROOT / "assets" / "items" / "manifest_assets.json"
CLASS_MANIFEST_PATH = STATIC_ROOT / "assets" / "classes" / "manifest_class_icons.json"
EXTENDED_MANIFEST_PATH = STATIC_ROOT / "assets" / "extended" / "manifest_extended_icons.json"

EXTENDED_CLASS_ALIASES = {
    "knight": "cavaleiro",
    "duelist": "duelista",
    "blade": "duelista",
    "assassin": "assassino",
    "sage": "sabio",
    "wizard": "sabio",
    "mentalist": "mentalista",
    "priest": "padre",
    "paladin": "paladino",
    "gunslinger": "pistoleiro",
    "shooter": "pistoleiro",
    "templar": "templario",
    "reaver": "retalhador",
    "reaper": "retalhador",
    "predator": "predador",
    "arcane": "arcano",
    "warlock": "bruxo",
    "high_priest": "sacerdote",
    "sentinel": "sentinela",
    "pathfinder": "patrulheiro",
    "patroller": "patrulheiro",
    "renegade": "renegado",
}

EXTENDED_BUILDING_ALIASES = {
    "housing": "alojamento",
    "lodging": "alojamento",
    "training_ground": "campo_de_treino",
    "blacksmith": "ferreiro",
    "warehouse": "armazem",
    "contract_office": "escritorio_de_contratos",
    "scouts": "exploradores",
    "explorers": "exploradores",
    "tavern": "taverna",
}


MENU_ICONS = {
    "dashboard": "⌂",
    "mercenaries": "⚔",
    "tavern": "♜",
    "missions": "✦",
    "dungeons": "◆",
    "buildings": "▣",
    "inventory": "◈",
    "class_change": "✧",
    "admin": "⚙",
    "logout": "⇥",
}

ITEM_GROUP_ICONS = {
    "sword": "⚔",
    "axe": "⚒",
    "bow": "➴",
    "staff": "✦",
    "dagger": "†",
    "pistol": "⌁",
    "shield": "⬟",
    "helmet": "⛑",
    "chest": "▰",
    "gloves": "▱",
    "boots": "⌞",
    "earring": "◌",
    "ring": "○",
    "belt": "▬",
    "necklace": "◇",
    "wood": "♣",
    "ore": "◆",
    "crystal": "✦",
    "hide": "▧",
    "material": "◈",
    "consumable": "✚",
    "misc": "◇",
}

SLOT_ICONS = {
    "helmet": "⛑",
    "chest": "▰",
    "gloves": "▱",
    "boots": "⌞",
    "main_hand": "⚔",
    "off_hand": "⚔",
    "shield": "⬟",
    "necklace": "◇",
    "earring": "◌",
    "belt": "▬",
    "ring": "○",
}

BUILDING_ICONS = {
    "housing": "⌂",
    "training_ground": "✦",
    "blacksmith": "⚒",
    "warehouse": "▤",
    "contract_office": "✉",
    "scouts": "⌖",
    "tavern": "♜",
}

ITEM_GROUP_ASSET_ALIASES = {
    "sword": "espada_de_ferro", "axe": "machado_de_batalha", "bow": "arco_longo",
    "staff": "cajado_arcano", "dagger": "adaga_simples", "pistol": "besta_leve",
    "mace": "maca_do_clerigo", "spear": "lanca_de_guarda", "wand": "cajado_arcano",
    "book": "grimorio_antigo", "orb": "orbe_arcano", "shield": "escudo_de_madeira",
    "helmet": "elmo_de_ferro", "chest": "peitoral_de_ferro", "heavy_armor": "armadura_reforcada",
    "medium_armor": "cota_de_malha", "light_armor": "armadura_de_couro", "robe": "manto_do_mago",
    "gloves": "luvas_de_couro", "boots": "botas_de_viajante", "earring": "brinco_de_cristal",
    "ring": "anel_simples", "belt": "cinto_de_couro", "necklace": "colar_de_ouro",
    "wood": "madeira_rustica", "ore": "fragmento_de_minerio", "stone": "pedra_bruta",
    "leather": "couro_tratado", "cloth": "tecido_grosseiro", "herb": "erva_medicinal",
    "essence": "essencia_verde", "gem": "gema_azul", "beast": "presa_de_fera",
    "relic": "reliquia_antiga", "catalyst": "po_arcano", "insignia": "insignia_de_guilda",
}


def normalize_icon_group(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace(" ", "_")


def normalize_asset_key(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")


@lru_cache(maxsize=4)
def _load_manifest(path_value: str, modified_at: int) -> dict[str, object]:
    try:
        with Path(path_value).open(encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
    except (OSError, json.JSONDecodeError):
        return {}
    return manifest if isinstance(manifest, dict) else {}


def _read_manifest(path: Path) -> tuple[dict[str, object], int]:
    try:
        modified_at = path.stat().st_mtime_ns
    except OSError:
        return {}, 0
    return _load_manifest(str(path), modified_at), modified_at


def _resolve_static_path(asset: dict[str, object]) -> str | None:
    url = str(asset.get("url_128") or "")
    if url.startswith("/static/"):
        relative_path = url.removeprefix("/static")
    else:
        source_path = str(asset.get("path_128") or "").replace("\\", "/")
        marker = "app/static"
        relative_path = source_path[source_path.index(marker) + len(marker):] if marker in source_path else ""
    if not relative_path:
        return None
    static_root = STATIC_ROOT.resolve()
    local_path = (STATIC_ROOT / relative_path.lstrip("/")).resolve()
    if not local_path.is_relative_to(static_root):
        return None
    return relative_path if local_path.is_file() else None


def _resolve_extended_static_path(icon_value: object) -> str | None:
    relative_icon = str(icon_value or "").replace("\\", "/").lstrip("/")
    if not relative_icon:
        return None
    relative_path = f"/assets/extended/{relative_icon}"
    static_root = STATIC_ROOT.resolve()
    local_path = (STATIC_ROOT / relative_path.lstrip("/")).resolve()
    if not local_path.is_relative_to(static_root):
        return None
    return relative_path if local_path.is_file() else None


@lru_cache(maxsize=2)
def _build_item_asset_index(modified_at: int) -> dict[str, str]:
    manifest = _load_manifest(str(ITEM_MANIFEST_PATH), modified_at)
    index: dict[str, str] = {}
    assets = manifest.get("assets", [])
    if not isinstance(assets, list):
        return index
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        icon_path = _resolve_static_path(asset)
        if not icon_path:
            continue
        aliases = asset.get("aliases", [])
        candidates = [asset.get("slug"), asset.get("display_name"), asset.get("asset_id")]
        if isinstance(aliases, list):
            candidates.extend(aliases)
        for candidate in candidates:
            key = normalize_asset_key(str(candidate or ""))
            if key:
                index[key.removeprefix("item_")] = icon_path
    return index


@lru_cache(maxsize=2)
def _build_class_asset_index(modified_at: int) -> dict[str, str]:
    manifest = _load_manifest(str(CLASS_MANIFEST_PATH), modified_at)
    index: dict[str, str] = {}
    classes = manifest.get("classes", [])
    if not isinstance(classes, list):
        return index
    for class_asset in classes:
        if not isinstance(class_asset, dict):
            continue
        icon_path = _resolve_static_path(class_asset)
        if not icon_path:
            continue
        aliases = class_asset.get("aliases", [])
        candidates = [class_asset.get("code"), class_asset.get("label"), class_asset.get("class_id")]
        if isinstance(aliases, list):
            candidates.extend(aliases)
        for candidate in candidates:
            key = normalize_asset_key(str(candidate or ""))
            if key:
                index[key.removeprefix("class_")] = icon_path
    return index


@lru_cache(maxsize=2)
def _build_extended_asset_index(modified_at: int) -> dict[str, dict[str, str]]:
    manifest = _load_manifest(str(EXTENDED_MANIFEST_PATH), modified_at)
    index: dict[str, dict[str, str]] = {
        "specialization": {},
        "final_class": {},
        "building": {},
    }
    for manifest_key, asset in manifest.items():
        if not isinstance(asset, dict):
            continue
        icon_type = str(asset.get("type") or "")
        if icon_type not in index:
            continue
        icon_path = _resolve_extended_static_path(asset.get("icon"))
        if not icon_path:
            continue
        for candidate in (manifest_key, asset.get("key"), asset.get("label")):
            key = normalize_asset_key(str(candidate or ""))
            if key:
                index[icon_type][key] = icon_path
    return index


def get_extended_icon_path(key_or_name: object, icon_type: str) -> str | None:
    _, modified_at = _read_manifest(EXTENDED_MANIFEST_PATH)
    if not modified_at:
        return None
    index = _build_extended_asset_index(modified_at).get(icon_type, {})
    candidates: list[str] = []
    if isinstance(key_or_name, str):
        candidates.append(key_or_name)
    else:
        for attribute in ("code", "effect_type", "display_name", "name"):
            value = getattr(key_or_name, attribute, None)
            if value:
                candidates.append(str(value))
    aliases = EXTENDED_BUILDING_ALIASES if icon_type == "building" else EXTENDED_CLASS_ALIASES
    for candidate in candidates:
        normalized = normalize_asset_key(candidate)
        resolved_key = aliases.get(normalized, normalized)
        if icon_path := index.get(resolved_key):
            return icon_path
    return None


def get_specialization_icon_path(class_key_or_name: object) -> str | None:
    return get_extended_icon_path(class_key_or_name, "specialization")


def get_final_class_icon_path(class_key_or_name: object) -> str | None:
    return get_extended_icon_path(class_key_or_name, "final_class")


def get_building_icon_path(building_key_or_name: object) -> str | None:
    return get_extended_icon_path(building_key_or_name, "building")


def infer_item_icon_group(item_template: ItemTemplate) -> str:
    explicit = normalize_icon_group(item_template.icon_group)
    if explicit:
        return explicit
    name = item_template.name.lower()
    slot = item_template.equipment_slot or ""
    if "espada" in name:
        return "sword"
    if "machado" in name:
        return "axe"
    if "arco" in name:
        return "bow"
    if "cajado" in name:
        return "staff"
    if "anel" in name or slot == "ring":
        return "ring"
    if "amuleto" in name or "colar" in name or slot == "necklace":
        return "necklace"
    if "armadura" in name or slot == "chest":
        return "chest"
    if "madeira" in name:
        return "wood"
    if "minerio" in name or "minério" in name:
        return "ore"
    if "cristal" in name:
        return "crystal"
    if "pele" in name:
        return "hide"
    return item_template.item_type


def get_item_icon(item: ItemTemplate | GuildItemInstance | GuildInventoryItem) -> str:
    item_template = item.item_template if hasattr(item, "item_template") else item
    return ITEM_GROUP_ICONS.get(infer_item_icon_group(item_template), ITEM_GROUP_ICONS["misc"])


def get_item_icon_path(item: ItemTemplate | GuildItemInstance | GuildInventoryItem) -> str | None:
    item_template = item.item_template if hasattr(item, "item_template") else item
    _, modified_at = _read_manifest(ITEM_MANIFEST_PATH)
    if not modified_at:
        return None
    index = _build_item_asset_index(modified_at)
    candidates = [item_template.name, item_template.icon_group, infer_item_icon_group(item_template), item_template.equipment_slot]
    for candidate in candidates:
        key = normalize_asset_key(candidate)
        if key and key in index:
            return index[key]
    group_alias = ITEM_GROUP_ASSET_ALIASES.get(infer_item_icon_group(item_template))
    if group_alias:
        return index.get(group_alias)
    return None


def get_class_icon_path(class_key_or_name: object) -> str | None:
    extended_path = (
        get_specialization_icon_path(class_key_or_name)
        or get_final_class_icon_path(class_key_or_name)
    )
    if extended_path:
        return extended_path
    _, modified_at = _read_manifest(CLASS_MANIFEST_PATH)
    if not modified_at:
        return None
    index = _build_class_asset_index(modified_at)
    candidates: list[str] = []
    if isinstance(class_key_or_name, str):
        candidates.append(class_key_or_name)
    else:
        for attribute in ("code", "display_name", "name"):
            value = getattr(class_key_or_name, attribute, None)
            if value:
                candidates.append(str(value))
    for candidate in candidates:
        icon_path = index.get(normalize_asset_key(candidate))
        if icon_path:
            return icon_path
    return None


def get_slot_icon(slot: str) -> str:
    return SLOT_ICONS.get(slot, "◇")


def get_building_icon(effect_type: str) -> str:
    if effect_type == "market":
        return "$"
    return BUILDING_ICONS.get(effect_type, "◇")
