import json
from functools import lru_cache
from pathlib import Path
from random import sample


NAME_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "mercenary_names.json"


@lru_cache(maxsize=2)
def _load_mercenary_names(catalog_modified_at: int) -> tuple[str, ...]:
    with NAME_CATALOG_PATH.open(encoding="utf-8") as catalog_file:
        catalog = json.load(catalog_file)

    names = catalog.get("names", [])
    if not isinstance(names, list):
        raise RuntimeError("O catalogo de nomes de mercenarios e invalido.")

    unique_names = tuple(dict.fromkeys(name.strip() for name in names if isinstance(name, str) and name.strip()))
    if not unique_names:
        raise RuntimeError("O catalogo de nomes de mercenarios esta vazio.")
    return unique_names


def load_mercenary_names() -> tuple[str, ...]:
    return _load_mercenary_names(NAME_CATALOG_PATH.stat().st_mtime_ns)


def choose_random_mercenary_names(count: int, names_in_use: list[str] | None = None) -> list[str]:
    if count < 1:
        return []

    catalog = load_mercenary_names()
    used_names = {name.casefold() for name in names_in_use or []}
    unused_names = [name for name in catalog if name.casefold() not in used_names]

    if len(unused_names) >= count:
        return sample(unused_names, count)
    if len(catalog) < count:
        raise RuntimeError("O catalogo nao possui nomes suficientes para esta contratacao.")

    selected = list(unused_names)
    remaining_names = [name for name in catalog if name not in selected]
    selected.extend(sample(remaining_names, count - len(selected)))
    return selected
