"""Resolve offline campaign evolution art through its checked-in manifest."""

from functools import lru_cache
import json
from pathlib import Path


_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "static" / "assets" / "desktop" / "evolution" / "manifest.json"
_ASSET_ROOT = "/static/assets/desktop/evolution/"


@lru_cache(maxsize=1)
def _manifest() -> dict[str, object]:
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def get_evolution_art_context() -> dict[str, object]:
    manifest = _manifest()
    illustrations = {}
    for key, asset in manifest["illustrations"].items():
        relative = asset["path"]
        illustrations[key] = {
            "src": _ASSET_ROOT + relative,
            "width": asset["width"],
            "height": asset["height"],
            "fallback": asset["fallback"],
        }
    sprites = {}
    for key, asset in manifest["sprites"].items():
        sprites[key] = {
            size: _ASSET_ROOT + relative
            for size, relative in asset["paths"].items()
        }
    return {"evolution_art": {"illustrations": illustrations, "sprites": sprites}}
