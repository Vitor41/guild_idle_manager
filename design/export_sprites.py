"""Rebuild desktop UI sprites and Windows icon from project-local masters.

Reads only design/masters/*.webp and writes only app/static/assets/desktop/.
"""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MASTERS = ROOT / "design" / "masters"
OUTPUT = ROOT / "app" / "static" / "assets" / "desktop"
SPRITES = OUTPUT / "sprites"


def compose(source: Image.Image, size: int, fill: float = 0.86) -> Image.Image:
    source = source.convert("RGBA")
    alpha = source.getchannel("A")
    bounds = alpha.point(lambda value: 255 if value >= 8 else 0).getbbox()
    if not bounds:
        raise ValueError("source is fully transparent")
    trimmed = source.crop(bounds)
    max_side = round(size * fill)
    trimmed.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(trimmed, ((size - trimmed.width) // 2, (size - trimmed.height) // 2))
    return canvas


def main() -> None:
    masters = sorted(MASTERS.glob("*.webp"))
    if not masters:
        raise SystemExit("No project-local sprite masters found")
    for size in (512, 128, 64):
        (SPRITES / ("master_512" if size == 512 else str(size))).mkdir(parents=True, exist_ok=True)
    for master_path in masters:
        image = Image.open(master_path)
        for size in (512, 128, 64):
            output = SPRITES / ("master_512" if size == 512 else str(size)) / f"{master_path.stem}.png"
            compose(image, size).save(output, optimize=True)
    icon_source = Image.open(MASTERS / "guild-sigil.webp")
    compose(icon_source, 256, 0.92).save(
        OUTPUT / "app-icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Exported {len(masters)} local masters and app-icon.ico")


if __name__ == "__main__":
    main()
