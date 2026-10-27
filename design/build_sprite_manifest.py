"""Build the portable desktop sprite manifest and assert known gameplay coverage.

Run from App GIM. Writes only app/static/assets/desktop/manifest.json and
docs/art_direction/SPRITE_COVERAGE.md.
"""

import ast
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "static" / "assets" / "desktop"
DESIGN = ROOT / "design"
DOCS = ROOT / "docs" / "art_direction"
MANIFEST = ASSETS / "manifest.json"

CLASS_CODES = (
    "apprentice", "warrior", "rogue", "mage", "cleric", "archer",
    "knight", "blade", "templar", "reaper", "assassin", "ninja",
    "predator", "shinobi", "wizard", "mentalist", "arcane", "warlock",
    "priest", "paladin", "high_priest", "sentinel", "ranger", "shooter",
    "patroller", "renegade",
)
CLASS_FAMILY = {
    "apprentice": "apprentice",
    **{code: "warrior" for code in ("warrior", "knight", "blade", "templar", "reaper")},
    **{code: "rogue" for code in ("rogue", "assassin", "ninja", "predator", "shinobi")},
    **{code: "mage" for code in ("mage", "wizard", "mentalist", "arcane", "warlock")},
    **{code: "cleric" for code in ("cleric", "priest", "paladin", "high_priest", "sentinel")},
    **{code: "archer" for code in ("archer", "ranger", "shooter", "patroller", "renegade")},
}
BUILDINGS = ("housing", "training_ground", "blacksmith", "warehouse", "contract_office", "scouts", "tavern", "market", "docks")
MATERIALS = ("wood", "ore", "stone", "leather", "cloth", "herb", "essence", "gem", "beast", "relic", "catalyst", "insignia")
ITEMS = ("sword", "axe", "mace", "spear", "dagger", "bow", "staff", "book", "shield", "pistol", "helmet", "chest", "robe", "gloves", "boots", "ring", "necklace", "earring", "belt", "potion")
STATES = ("ready", "progress", "locked", "failed", "saved", "warning")
BIOMES = ("forest", "cave", "fortress", "portal")
CORE = ("guild-sigil", "expedition-map", "dungeon-gate", "resource-gold", "resource-crystal", "boss-crown")
CATALOG_SPRITES = (
    "resource-dungeon-key", "resource-xp", "resource-training-token",
    "resource-tavern-ticket", "resource-merchant-token", "resource-honor-mark",
    "resource-provisions", "item-quest-scroll", "item-hammer",
)

ITEM_GROUPS = {
    "sword": "item-sword", "axe": "item-axe", "mace": "item-mace", "spear": "item-spear",
    "dagger": "item-dagger", "bow": "item-bow", "staff": "item-staff", "wand": "item-staff",
    "book": "item-book", "orb": "item-staff", "pistol": "item-pistol", "crossbow": "item-bow",
    "shield": "item-shield", "helmet": "item-helmet", "chest": "item-chest",
    "heavy_armor": "item-chest", "medium_armor": "item-chest", "light_armor": "item-chest",
    "robe": "item-robe", "gloves": "item-gloves", "boots": "item-boots",
    "ring": "item-ring", "necklace": "item-necklace", "earring": "item-earring", "belt": "item-belt",
    "wood": "material-wood", "ore": "material-ore", "stone": "material-stone",
    "leather": "material-leather", "hide": "material-leather", "cloth": "material-cloth",
    "herb": "material-herb", "essence": "material-essence", "gem": "material-gem",
    "crystal": "resource-crystal", "beast": "material-beast", "relic": "material-relic",
    "catalyst": "material-catalyst", "insignia": "material-insignia",
    "material": "material-relic", "consumable": "item-potion", "misc": "material-relic",
    "ancient_relic": "material-relic", "dungeon_key": "resource-dungeon-key",
    "gold": "resource-gold", "guild_xp": "resource-xp", "xp": "resource-xp",
    "hammer": "item-hammer", "honor_mark": "resource-honor-mark",
    "medal": "resource-honor-mark", "merchant_token": "resource-merchant-token",
    "provisions": "resource-provisions", "quest_scroll": "item-quest-scroll",
    "tavern_ticket": "resource-tavern-ticket", "training_token": "resource-training-token",
}
SLOTS = {
    "main_hand": "item-sword", "off_hand": "item-dagger", "shield": "item-shield",
    "helmet": "item-helmet", "chest": "item-chest", "gloves": "item-gloves",
    "boots": "item-boots", "earring": "item-earring", "ring": "item-ring",
    "belt": "item-belt", "necklace": "item-necklace",
    "weapon": "item-sword", "armor": "item-chest", "accessory": "item-ring",
}
MENU = {
    "dashboard": "guild-sigil", "mercenaries": "class-warrior", "tavern": "building-tavern",
    "professions": "building-training_ground", "missions": "expedition-map",
    "dungeons": "dungeon-gate", "inventory": "building-warehouse",
    "blacksmith": "building-blacksmith", "market": "building-market",
    "docks": "building-docks", "buildings": "building-housing",
    "class_change": "class-apprentice", "guild_progress": "guild-sigil",
    "classes": "class-apprentice", "tiers": "material-gem",
    "codex": "material-relic", "guide": "item-book", "campaigns": "guild-sigil",
    "tutorial": "item-book", "skills": "class-mage", "achievements": "material-insignia",
}
RESOURCES = {
    "gold": "resource-gold", "wood": "material-wood", "ore": "material-ore",
    "crystals": "resource-crystal", "xp": "resource-xp", "reputation": "guild-sigil",
}
MISSION_TYPES = {
    "standard": "expedition-map", "combat": "class-warrior", "patrol": "expedition-map",
    "escort": "class-knight", "hunt": "class-ranger", "exploration": "expedition-map",
    "investigation": "expedition-map", "defense": "class-sentinel", "rescue": "class-paladin",
    "contract": "building-contract_office", "story": "item-book", "elite": "boss-crown",
    "gathering": "material-wood", "long_idle": "status-progress",
}
GATHERING = {
    "woodcutter": "material-wood", "miner": "material-ore", "herbalist": "material-herb",
    "leatherworker": "material-leather", "weaver": "material-cloth",
    "prospector": "material-gem", "reliquary": "material-relic",
    "alchemist": "material-essence",
}
DUNGEON_BIOMES = {
    "mines": "biome-cave", "woods": "biome-forest", "catacombs": "biome-cave",
    "ruins": "biome-fortress", "fortress": "biome-fortress", "tower": "biome-fortress",
    "caves": "biome-cave", "swamp": "biome-forest", "sanctuary": "biome-fortress",
    "portal": "biome-portal", "abyss": "biome-cave", "lost_city": "biome-fortress",
}
STATUS_MAP = {
    "available": "status-ready", "busy": "status-progress", "in_progress": "status-progress",
    "completed": "status-ready", "ready_to_collect": "status-ready", "failed": "status-failed",
    "active": "status-ready", "expired": "status-warning", "hired": "status-ready",
    "dismissed": "status-failed", "locked": "status-locked", "saved": "status-saved",
    "saving": "status-progress", "save_error": "status-warning",
}
ACTIONS = {
    "continue_campaign": "guild-sigil", "new_campaign": "guild-sigil",
    "recruit": "building-tavern", "start_mission": "expedition-map",
    "enter_dungeon": "dungeon-gate", "collect": "status-ready",
    "equip": "item-shield", "upgrade_building": "building-training_ground",
    "craft": "building-blacksmith", "refine": "building-blacksmith",
    "salvage": "item-axe", "sell": "building-market", "buy": "building-docks",
    "class_change": "class-apprentice", "confirm": "status-ready",
    "cancel": "status-warning", "dismiss": "status-failed",
    "open_guide": "item-book", "export_save": "status-saved",
    "import_save": "guild-sigil", "restore_backup": "status-warning",
}


def syntax_tree(relative: str) -> ast.Module:
    return ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)


def assigned_value(tree: ast.Module, name: str, function: str | None = None) -> ast.expr:
    scope = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function), None) if function else tree
    if scope is None:
        raise ValueError(f"Catalog function missing: {function}")
    for node in scope.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return node.value
    raise ValueError(f"Catalog assignment missing: {name}")


def dict_string_values(node: ast.AST, field: str) -> set[str]:
    values = set()
    for entry in ast.walk(node):
        if not isinstance(entry, ast.Dict):
            continue
        for key, value in zip(entry.keys, entry.values):
            if isinstance(key, ast.Constant) and key.value == field and isinstance(value, ast.Constant) and isinstance(value.value, str):
                values.add(value.value)
    return values


def real_catalog_codes() -> dict[str, set[str]]:
    """Read current source catalogs without importing the application or its database."""
    item_data = json.loads((ROOT / "app/static/assets/items/manifest_assets.json").read_text(encoding="utf-8"))
    item_assets = item_data["assets"]
    massive = syntax_tree("app/seeds/massive_content.py")
    class_tree = syntax_tree("app/services/class_service.py")
    building_tree = syntax_tree("app/services/building_service.py")
    item_service = syntax_tree("app/services/item_service.py")
    mission_service = syntax_tree("app/services/mission_service.py")

    families = ast.literal_eval(assigned_value(massive, "families", "_material_rows"))
    categories = ast.literal_eval(assigned_value(massive, "categories", "_equipment_rows"))
    equipment = [row for _, rows in categories for row in rows]
    professions = ast.literal_eval(assigned_value(massive, "PROFESSIONS"))
    mission_types = set(ast.literal_eval(assigned_value(massive, "types", "_mission_rows")))
    mission_rows = next(node for node in massive.body if isinstance(node, ast.FunctionDef) and node.name == "_mission_rows")
    gathering_rows = next(node for node in massive.body if isinstance(node, ast.FunctionDef) and node.name == "_gathering_rows")
    mission_types |= dict_string_values(gathering_rows, "mission_type")
    mission_types |= dict_string_values(mission_service, "mission_type")
    for node in ast.walk(mission_rows):
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "mission_type" for target in node.targets):
            mission_types |= {value.value for value in ast.walk(node.value) if isinstance(value, ast.Constant) and isinstance(value.value, str)}
    building_codes = dict_string_values(assigned_value(building_tree, "INITIAL_BUILDING_TEMPLATES"), "effect_type")
    building_codes |= {
        keyword.value.value
        for call in ast.walk(massive) if isinstance(call, ast.Call)
        for keyword in call.keywords
        if keyword.arg == "effect_type" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str)
    }
    return {
        "classes": dict_string_values(assigned_value(class_tree, "CLASS_TREE"), "code"),
        "buildings": building_codes,
        "material_families": set(families),
        "item_icon_groups": {asset["icon_group"] for asset in item_assets if asset.get("icon_group")}
            | {row[2] for row in equipment} | set(families) | dict_string_values(item_service, "icon_group"),
        "equipment_slots": {asset["equipment_slot"] for asset in item_assets if asset.get("equipment_slot")}
            | {row[1] for row in equipment},
        "mission_types": mission_types,
        "gathering_professions": {row[0] for row in professions},
        "dungeon_biomes": set(ast.literal_eval(assigned_value(massive, "biomes", "_dungeon_rows"))),
    }


def main() -> None:
    expected = set(CORE)
    expected.update(CATALOG_SPRITES)
    expected.update("class-" + value for value in CLASS_CODES)
    expected.update("building-" + value for value in BUILDINGS)
    expected.update("material-" + value for value in MATERIALS)
    expected.update("item-" + value for value in ITEMS)
    expected.update("status-" + value for value in STATES)
    expected.update("biome-" + value for value in BIOMES)
    sprites = {}
    missing = []
    for key in sorted(expected):
        paths = {size: f"sprites/{size}/{key}.png" for size in ("64", "128")}
        paths["512"] = f"sprites/master_512/{key}.png"
        master = DESIGN / "masters" / f"{key}.webp"
        if not master.is_file():
            missing.append(str(master.relative_to(ROOT)))
        else:
            with Image.open(master) as source:
                if source.size != (1024, 1024) or not source.convert("RGBA").getchannel("A").getbbox():
                    missing.append(str(master.relative_to(ROOT)) + " (invalid master)")
        for size, relative in paths.items():
            file = ASSETS / relative
            if not file.is_file():
                missing.append(relative)
            elif Image.open(file).size != (int(size), int(size)):
                missing.append(relative + " (wrong dimensions)")
        sprites[key] = {"paths": paths, "master_project_path": f"design/masters/{key}.webp"}
    maps = {
        "classes": {code: "class-" + code for code in CLASS_CODES},
        "buildings": {code: "building-" + code for code in BUILDINGS},
        "material_families": {code: "material-" + code for code in MATERIALS},
        "item_icon_groups": ITEM_GROUPS,
        "equipment_slots": SLOTS,
        "menu": MENU,
        "resources": RESOURCES,
        "mission_types": MISSION_TYPES,
        "gathering_professions": GATHERING,
        "dungeon_biomes": DUNGEON_BIOMES,
        "dungeon_content_types": {"dungeon": "dungeon-gate", "boss": "boss-crown"},
        "statuses": STATUS_MAP,
        "actions": ACTIONS,
    }
    for category, entries in maps.items():
        for code, key in entries.items():
            if key not in expected:
                missing.append(f"{category}.{code} -> {key}")
    catalog_codes = real_catalog_codes()
    for category, codes in catalog_codes.items():
        for code in sorted(codes - maps[category].keys()):
            missing.append(f"real catalog {category}.{code} has no explicit sprite mapping")
    portrait_paths = {code: f"portraits/portrait-{CLASS_FAMILY[code]}.webp" for code in CLASS_CODES}
    for path in sorted(set(portrait_paths.values())):
        if not (ASSETS / path).is_file():
            missing.append(path)
    if missing:
        raise SystemExit("Missing sprite coverage:\n" + "\n".join(missing))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest.pop("reuse", None)
    manifest["sprites"] = sprites
    manifest["icon_maps"] = maps
    manifest["portraits"] = portrait_paths
    manifest["fallbacks"] = {
        "unknown_class_code": "class-apprentice",
        "unknown_equipment_group": "item-sword",
        "unknown_material_family": "material-relic",
        "unknown_building_effect": "building-housing",
        "unknown_mission_type": "expedition-map",
        "unknown_dungeon_biome": "dungeon-gate",
        "unknown_status": "status-warning",
        "portrait_missing": "class emblem for the same class code",
        "rule": "Unknown future content keeps its live localized name and semantic family fallback; never show a broken image or a text-only placeholder for known content.",
    }
    manifest["license_review"] = {
        "new_assets": "Original imagegen output; no third-party visual sources.",
        "legacy_assets": "Excluded from this desktop sprite mapping; provenance not verified for distribution.",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Cobertura de sprites desktop",
        "",
        "Todos os caminhos abaixo resolvem em `app/static/assets/desktop/`; o manifesto é a fonte de mapeamento.",
        "O pacote é independente dos PNGs legados do projeto web. Raridade usa borda e rótulo CSS, sem duplicar imagens.",
        "",
        f"**Sprites canônicos:** {len(sprites)} · **Classes:** {len(CLASS_CODES)}/26 · **Mapeamentos conhecidos:** {sum(map(len, maps.values()))} · **Faltantes:** 0.",
        "**Verificação contra fontes reais:** `app/static/assets/items/manifest_assets.json`, `app/seeds/massive_content.py`, `app/services/class_service.py`, `building_service.py`, `item_service.py` e `mission_service.py`. Os códigos são lidos desses arquivos a cada execução; grupo conhecido sem mapa causa falha.",
        "",
        "## Classes: 26/26",
        "",
        "| Código | Sprite 64 px | Retrato de arquétipo |",
        "|---|---|---|",
    ]
    for code in CLASS_CODES:
        lines.append(f"| `{code}` | `sprites/64/class-{code}.png` | `{portrait_paths[code]}` |")
    lines += ["", "## Cobertura por domínio", "", "| Domínio | Códigos reais mapeados | Estratégia |", "|---|---:|---|"]
    for name, entries in maps.items():
        lines.append(f"| `{name}` | {len(entries)} ({len(catalog_codes[name])} no catálogo real) | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |" if name in catalog_codes else f"| `{name}` | {len(entries)} | Arquivo explícito por código; famílias semânticas compartilham sprite quando apropriado. |")
    lines += [
        "", "## Prova de leitura e fallbacks", "",
        "- `design/preview/class-readability-26.png` compara todos os emblemas em 48 e 24 px sobre superfície sólida. A 24 px, usar sempre nome ou tooltip; 48 px é o tamanho preferido.",
        "- `design/preview/sprite-catalog.html` reúne todas as categorias em slots reais.",
        "- A expansão de conteúdo usa o fallback semântico registrado em `manifest.json` e mantém nome, estado e raridade como texto acessível.",
        "- A resolução deve priorizar: código exato → icon_group/material_family/biome → slot/tipo → fallback do domínio. A raridade não altera o PNG.",
        "", "## Risco de integração", "",
        "A UI atual resolve ícones pelos manifestos legados em `app/services/icon_service.py`. O DEV precisa trocar a resolução para este manifesto e testar caminhos empacotados no WebView2/pywebview. Esta entrega não modifica serviços ou templates de produção.",
    ]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "SPRITE_COVERAGE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(sprites)} sprites and {sum(map(len, maps.values()))} known mappings. Missing: 0")


if __name__ == "__main__":
    main()
