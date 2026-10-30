import json
import re

from app.services.display_service import clean_generated_name, localize_bonus_text


EMPTY_RESULT_VIEW = {
    "xp_awards": [],
    "level_ups": [],
    "guild_progress": [],
    "items": [],
    "notes": [],
    "has_details": False,
}


def serialize_result_details(
    xp_awards: list[str],
    level_ups: list[str],
    guild_progress: list[str],
    items: list[str],
    notes: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "version": 1,
            "xp_awards": xp_awards,
            "level_ups": level_ups,
            "guild_progress": guild_progress,
            "items": items,
            "notes": notes or [],
        },
        ensure_ascii=False,
    )


def _normalize_entries(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [
        str(value).strip().replace(" para o nivel ", " para o nível ")
        for value in values if str(value).strip()
    ]


def _normalize_item_entries(values: object) -> list[str]:
    return [localize_bonus_text(clean_generated_name(value)) for value in _normalize_entries(values)]


def _finalize_view(view: dict[str, list[str]]) -> dict[str, object]:
    return {
        **view,
        "has_details": any(view.values()),
    }


def _parse_legacy_result(details: str) -> dict[str, object]:
    summary, separator, item_text = details.partition("Itens obtidos:")
    reward_match = re.search(r"XP ganho:\s*\d+\.\s*", summary)
    event_text = summary[reward_match.end():] if reward_match else summary
    sentences = [sentence.strip() for sentence in re.findall(r"[^.]+(?:\.|$)", event_text) if sentence.strip()]

    view: dict[str, list[str]] = {
        "xp_awards": [],
        "level_ups": [],
        "guild_progress": [],
        "items": [],
        "notes": [],
    }
    for sentence in sentences:
        if sentence.startswith("Guilda "):
            view["guild_progress"].append(sentence)
        elif " recebeu " in sentence and " XP" in sentence:
            view["xp_awards"].append(sentence)
        elif " subiu para o nivel " in sentence or " subiu para o nível " in sentence:
            view["level_ups"].append(sentence)
        else:
            view["notes"].append(sentence)

    cleaned_items = item_text.strip() if separator else ""
    if cleaned_items and cleaned_items not in {"Nenhum item encontrado.", "Nenhum item encontrado"}:
        view["items"].append(localize_bonus_text(clean_generated_name(cleaned_items)))
    return _finalize_view(view)


def parse_result_details(details: str | None) -> dict[str, object]:
    if not details:
        return dict(EMPTY_RESULT_VIEW)
    try:
        parsed = json.loads(details)
    except (json.JSONDecodeError, TypeError):
        return _parse_legacy_result(details)
    if not isinstance(parsed, dict):
        return _parse_legacy_result(details)

    view = {
        "xp_awards": _normalize_entries(parsed.get("xp_awards")),
        "level_ups": _normalize_entries(parsed.get("level_ups")),
        "guild_progress": _normalize_entries(parsed.get("guild_progress")),
        "items": _normalize_item_entries(parsed.get("items")),
        "notes": _normalize_entries(parsed.get("notes")),
    }
    return _finalize_view(view)
