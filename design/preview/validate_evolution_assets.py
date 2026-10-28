"""Check the local gameplay evolution art handoff without opening a save."""

import json
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
PREVIEW = ROOT / "design" / "preview"
ASSETS = ROOT / "app" / "static" / "assets" / "desktop" / "evolution"


class PreviewImages(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.sources.append(dict(attrs))


manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
assert manifest["version"] == "0.1.0"
for name, entry in manifest["illustrations"].items():
    path = ASSETS / entry["path"]
    assert path.is_file(), name
    with Image.open(path) as image:
        assert image.size == (entry["width"], entry["height"]), name
    assert path.stat().st_size < 350_000, f"Scene export too large: {name}"

for name, entry in manifest["sprites"].items():
    for size, relative in entry["paths"].items():
        path = ASSETS / relative
        assert path.is_file(), (name, size)
        with Image.open(path) as image:
            assert image.size == (int(size), int(size)), (name, size)
            assert image.mode == "RGBA" and image.getchannel("A").getextrema() == (0, 255), (name, size)

parser = PreviewImages()
parser.feed((PREVIEW / "evolution.html").read_text(encoding="utf-8"))
for attrs in parser.sources:
    assert "alt" in attrs, attrs
    assert (PREVIEW / attrs["src"]).resolve().is_file(), attrs["src"]

assert len(manifest["illustrations"]) == 6
assert len(manifest["sprites"]) == 5
print(f"PASS: 6 local scenes, 15 transparent sprite exports and {len(parser.sources)} preview image references")
