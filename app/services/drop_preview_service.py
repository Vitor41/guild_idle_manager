"""Build safe, presentation-only drop previews from the active resolver rows."""

from __future__ import annotations

from collections.abc import Iterable

from app.services.display_service import clean_generated_name, rarity_label
from app.services.icon_service import get_item_icon_path


def build_drop_preview(entries: Iterable[object] | None) -> dict[str, object]:
    """Normalize active drop rows, withholding the list if any row is inconsistent.

    An empty active list is a valid "base rewards only" state. A missing list,
    missing item template, or malformed active row is reported as unavailable
    so the UI never presents partial or stale loot as confirmed.
    """
    if entries is None:
        return {"available": False, "drops": [], "chance_basis": None}

    normalized: list[dict[str, object]] = []
    try:
        for entry in entries:
            if not getattr(entry, "is_active", False):
                continue
            item = getattr(entry, "item_template", None)
            chance = getattr(entry, "drop_chance", None)
            minimum = getattr(entry, "min_quantity", None)
            maximum = getattr(entry, "max_quantity", None)
            try:
                chance_value, minimum_value, maximum_value = int(chance), int(minimum), int(maximum)
            except (TypeError, ValueError):
                return {"available": False, "drops": [], "chance_basis": None}
            if (
                item is None
                or not getattr(item, "is_active", False)
                or getattr(item, "item_type", None) not in {"equipment", "material"}
                or not getattr(item, "rarity", None)
                or not 0 <= chance_value <= 100
                or minimum_value < 1
                or maximum_value < minimum_value
            ):
                return {"available": False, "drops": [], "chance_basis": None}
            normalized.append({
                "display_name": clean_generated_name(item.name),
                "rarity_class": str(item.rarity).lower(),
                "rarity_label": rarity_label(item.rarity),
                "icon_path": get_item_icon_path(item),
                "chance_percent": chance_value,
                "min_quantity": minimum_value,
                "max_quantity": maximum_value,
                "quantity_unit": "instância(s)" if item.item_type == "equipment" else "unidade(s)",
            })
    except (TypeError, AttributeError, ValueError):
        return {"available": False, "drops": [], "chance_basis": None}

    return {"available": True, "drops": normalized, "chance_basis": "base"}
