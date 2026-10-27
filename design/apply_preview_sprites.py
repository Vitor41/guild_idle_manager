"""Switch the five local previews to the desktop-only sprite set.

Idempotent: existing desktop sprite URLs are retained. Run from App GIM.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "design" / "preview"
PREFIX = "../../app/static/assets/desktop/sprites/"

LEGACY = {
    "../../app/static/assets/extended/buildings/ui_128/building_ferreiro.png": "building-blacksmith",
    "../../app/static/assets/extended/buildings/ui_128/building_taverna.png": "building-tavern",
    "../../app/static/img/classes/128/class_apprentice.png": "class-apprentice",
    "../../app/static/img/classes/128/class_archer.png": "class-archer",
    "../../app/static/img/classes/128/class_cleric.png": "class-cleric",
    "../../app/static/img/classes/128/class_mage.png": "class-mage",
    "../../app/static/img/classes/128/class_warrior.png": "class-warrior",
    "../../app/static/img/items/128/resources/moeda_de_ouro.png": "resource-gold",
    "../../app/static/img/items/128/materials/madeira_rustica.png": "material-wood",
    "../../app/static/img/items/128/materials/galho_de_carvalho.png": "material-wood",
    "../../app/static/img/items/128/materials/fragmento_de_minerio.png": "material-ore",
    "../../app/static/img/items/128/materials/barra_de_ferro.png": "material-ore",
    "../../app/static/img/items/128/materials/cristal_bruto.png": "resource-crystal",
    "../../app/static/img/items/128/materials/couro_tratado.png": "material-leather",
    "../../app/static/img/items/128/materials/erva_medicinal.png": "material-herb",
    "../../app/static/img/items/128/weapons/arco_do_cacador.png": "item-bow",
    "../../app/static/img/items/128/weapons/cajado_arcano.png": "item-staff",
    "../../app/static/img/items/128/weapons/espada_de_ferro.png": "item-sword",
    "../../app/static/img/items/128/armors/armadura_reforcada.png": "item-chest",
    "../../app/static/img/items/128/armors/botas_de_viajante.png": "item-boots",
    "../../app/static/img/items/128/accessories/amuleto_do_cacador.png": "item-necklace",
}
NAV = {
    "Salão da guilda": "guild-sigil", "Mercenários": "class-warrior",
    "Missões": "expedition-map", "Missões e masmorras": "expedition-map",
    "Masmorras": "dungeon-gate", "Taverna": "building-tavern",
    "Construções": "building-housing", "Inventário": "building-warehouse",
    "Inventário e recursos": "building-warehouse", "Códex e guia": "material-relic",
}
STATUS = {"ready": "status-ready", "active": "status-progress", "locked-label": "status-locked"}


def nav_replace(match: re.Match[str]) -> str:
    opening, label = match.groups()
    key = NAV.get(label.strip())
    if key is None:
        raise ValueError(f"unmapped preview navigation: {label}")
    return f'{opening}<img class="nav-sprite" src="{PREFIX}64/{key}.png" alt=""> {label}</a>'


def status_replace(match: re.Match[str]) -> str:
    opening, css_class = match.groups()
    key = STATUS.get(css_class.split()[-1])
    if key is None:
        return match.group(0)
    return f'{opening}<img class="state-sprite" src="{PREFIX}64/{key}.png" alt=""> '


def main() -> None:
    for name in ("index.html", "roster.html", "operations.html", "tavern.html", "inventory.html"):
        path = PREVIEW / name
        html = path.read_text(encoding="utf-8")
        for original, key in LEGACY.items():
            html = html.replace(original, f"{PREFIX}128/{key}.png")
        html = html.replace(
            "../../app/static/assets/desktop/illustrations/ranger-portrait.webp",
            "../../app/static/assets/desktop/portraits/portrait-archer.webp",
        )
        html = re.sub(r'(<a class="nav-item[^>]*>)<span aria-hidden="true">.*?</span>\s*([^<]+)</a>', nav_replace, html)
        html = html.replace('<b aria-hidden="true">◈</b>', f'<img class="top-gold-sprite" src="{PREFIX}64/resource-gold.png" alt="">')
        html = re.sub(r'(<span class="state ([^"]+)">)(?:●|◷|⌑)\s*', status_replace, html)
        html = html.replace(f'<span class="availability">● ', f'<span class="availability"><img class="state-sprite" src="{PREFIX}64/status-ready.png" alt=""> ')
        html = html.replace(f'<span class="availability busy">◷ ', f'<span class="availability busy"><img class="state-sprite" src="{PREFIX}64/status-progress.png" alt=""> ')
        path.write_text(html, encoding="utf-8")
        print(name)


if __name__ == "__main__":
    main()
