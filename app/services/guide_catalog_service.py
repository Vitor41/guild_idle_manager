"""Player-facing equipment/material catalog derived from active campaign config."""
from app.models.item import ItemTemplate
from app.services.display_service import clean_generated_name, rarity_label
from app.services.icon_service import get_item_icon_path
from app.services.material_source_manifest import build_material_source_manifest


SOURCE_LABELS = {
    "mission": ("Missões", "drop"),
    "dungeon_or_boss": ("Masmorras e Chefes", "drop"),
    "docks_possible_offer": ("Docas", "purchase"),
    "gathering": ("Coleta", "gathering"),
    "salvage": ("Desmontagem", "salvage"),
    "workshop_output": ("Oficina de Suprimentos", "workshop"),
    "crafting_output": ("Ferreiro", "crafting"),
}


def _quantity_text(source: dict, item_type: str) -> str:
    source_type = source["type"]
    quantity_range = source.get("quantity_range")
    if quantity_range:
        low, high = quantity_range
        unit = "instância(s)" if item_type == "equipment" else "unidade(s)"
        range_text = str(low) if low == high else f"{low}–{high}"
        if source_type in {"mission", "dungeon_or_boss"}:
            return f"{range_text} {unit} por entrada de drop; multiplicadores e bônus aplicáveis podem alterar o total"
        return f"{range_text} {unit}"
    if source_type == "gathering":
        return "1 unidade por ciclo; pode haver 1 unidade extra conforme profissão do trabalhador"
    if source_type == "docks_possible_offer":
        low, high = source["stock_range"]
        return f"estoque por rotação: {low}–{high}"
    if source_type in {"workshop_output", "crafting_output"}:
        return f"{source.get('quantity', 1)} unidade(s) por produção"
    return "não se aplica"


def _chance_text(source: dict) -> str:
    source_type = source["type"]
    if source_type in {"mission", "dungeon_or_boss"}:
        return (f"{source['configured_base_chance_percent']}% base por entrada de drop; rola após sucesso, "
                "com modificadores de equipe aplicáveis")
    if source_type == "gathering":
        return "sem chance para a unidade-base; extra depende da profissão (limite configurado de 45%)"
    if source_type == "docks_possible_offer":
        return "compra; sem chance de drop (a oferta depende da rotação)"
    if source_type == "salvage":
        return "resultado da desmontagem; quantidade sorteada entre 1 e 3"
    return "produção por receita; sem chance de drop"


def _guide_icon_path(item_model: ItemTemplate) -> str | None:
    """Return a URL served by the app's only static mount."""
    icon_path = get_item_icon_path(item_model)
    if icon_path and icon_path.startswith("/assets/"):
        return f"/static{icon_path}"
    return icon_path


def build_guide_catalog(db) -> dict[str, object]:
    manifest = build_material_source_manifest(db)
    item_by_id = {item.id: item for item in db.query(ItemTemplate).filter(
        ItemTemplate.is_active.is_(True), ItemTemplate.item_type.in_(("material", "equipment"))
    ).all()}
    entries: list[dict[str, object]] = []
    for category in ("materials", "equipment"):
        for record in manifest[category]:
            item = record["item"]
            model = item_by_id.get(item["id"])
            if not item["active"] or model is None:
                continue
            sources = []
            for raw in record["sources"]:
                label_data = SOURCE_LABELS.get(raw["type"])
                if label_data is None:
                    continue
                label, source_filter = label_data
                name = raw.get("name") or raw.get("merchant") or raw.get("recipe") or raw.get("equipment") or label
                if raw["type"] == "dungeon_or_boss":
                    label = "Chefes" if raw.get("content_type") == "boss" else "Masmorras"
                reqs = []
                if raw.get("min_guild_level", 1) > 1:
                    reqs.append(f"guilda nível {raw['min_guild_level']}+")
                if raw.get("min_mercenary_level", 1) > 1:
                    reqs.append(f"mercenário nível {raw['min_mercenary_level']}+")
                building = raw.get("required_building")
                if building and building[0] and building[1]:
                    reqs.append(f"{building[0]} nível {building[1]}+")
                if raw.get("min_dock_level", 1) > 1:
                    reqs.append(f"Docas nível {raw['min_dock_level']}+")
                if raw["type"] == "gathering":
                    level_range = raw.get("guild_level_range") or [raw.get("guild_level", 1), raw.get("guild_level", 1)]
                    level_text = str(level_range[0]) if level_range[0] == level_range[1] else f"{level_range[0]}–{level_range[1]}"
                    reqs.append(f"Coleta de {raw['family']}; níveis da guilda {level_text}")
                if raw["type"] == "salvage":
                    reqs.append(f"equipamento livre: {clean_generated_name(raw['equipment'])}")
                if raw["type"] == "crafting_output":
                    reqs.append(f"Ferreiro nível {raw['required_blacksmith_level']}+; ingredientes da receita")
                if raw["type"] == "workshop_output":
                    reqs.append("3 Carnes + 2 Ervas; 5 segundos por unidade")
                if raw.get("condition"):
                    reqs.append(clean_generated_name(raw["condition"]))
                sources.append({
                    "type": raw["type"], "filter_key": source_filter, "label": label,
                    "name": clean_generated_name(name),
                    "requirement": "; ".join(reqs) if reqs else "sem requisito adicional registrado",
                    "chance": _chance_text(raw), "quantity": _quantity_text(raw, item["item_type"]),
                    "price": raw.get("effective_unit_price", raw.get("base_price")),
                    "condition": raw.get("condition", ""),
                })
            entries.append({
                "id": item["id"], "name": clean_generated_name(item["name"]),
                "item_type": item["item_type"], "item_type_label": "Equipamento" if item["item_type"] == "equipment" else "Material",
                "family": item.get("family") or "", "tier": item["tier"],
                "equipment_slot": (model.equipment_slot or "") if item["item_type"] == "equipment" else "",
                "level_band": item["level_band"], "item_level": item["item_level"],
                "rarity": rarity_label(item["rarity"]), "icon": _guide_icon_path(model),
                "sources": sources,
            })
    entries.sort(key=lambda row: (row["item_type"], row["family"], row["tier"], row["item_level"], row["name"].casefold()))
    return {
        "version": 1, "items": entries,
        "filters": {
            "families": sorted({str(row["family"]) for row in entries if row["family"]}),
            "tiers": sorted({int(row["tier"]) for row in entries}),
            "level_bands": sorted({str(row["level_band"]) for row in entries}),
            "sources": sorted({source["filter_key"] for row in entries for source in row["sources"]}
                | ({"none"} if any(not row["sources"] for row in entries) else set())),
        },
        "gaps": manifest["gaps"],
    }
