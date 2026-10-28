"""Rebuild the gameplay evolution art exports from local original masters.

Requires Pillow. The source PNGs are kept outside the packaged app assets.
"""

from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[2]
MASTERS = ROOT / "design" / "preview" / "evolution_masters"
OUTPUT = ROOT / "app" / "static" / "assets" / "desktop" / "evolution"

SCENES = (
    "region-home",
    "regional-vigil",
    "dimensional-portal",
    "regional-rebellion",
    "gathering-worksite",
    "achievement-reliquary",
)
SPRITES = (
    "vigil-tower",
    "portal-gate",
    "rebellion-shield",
    "gathering-kit",
    "achievement-medal",
)


def export_scene(name: str) -> None:
    target = OUTPUT / "illustrations" / f"{name}.webp"
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(MASTERS / f"{name}.png") as source:
        image = ImageOps.fit(source.convert("RGB"), (1600, 900), method=Image.Resampling.LANCZOS)
        image.save(target, "WEBP", quality=84, method=6)


def export_sprite(name: str) -> None:
    with Image.open(MASTERS / f"{name}.png") as source:
        image = source.convert("RGBA")
        alpha = image.getchannel("A")
        bounds = alpha.getbbox()
        if bounds is None:
            raise ValueError(f"Transparent master has no visible pixels: {name}")
        cropped = image.crop(bounds)
        for size, folder in ((512, "master_512"), (128, "ui_128"), (64, "ui_64")):
            target = OUTPUT / "sprites" / folder / f"{name}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            visible = ImageOps.contain(cropped, (round(size * .92), round(size * .92)), Image.Resampling.LANCZOS)
            canvas.alpha_composite(visible, ((size - visible.width) // 2, (size - visible.height) // 2))
            canvas.save(target, "PNG", optimize=True)


if __name__ == "__main__":
    for scene in SCENES:
        export_scene(scene)
    for sprite in SPRITES:
        export_sprite(sprite)
    print(f"Exported {len(SCENES)} scenes and {len(SPRITES)} sprites to {OUTPUT}")
