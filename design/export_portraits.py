"""Rebuild the six UI archetype portraits from project-local masters."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MASTERS = ROOT / "design" / "portrait_masters"
OUTPUT = ROOT / "app" / "static" / "assets" / "desktop" / "portraits"


def main() -> None:
    masters = sorted(MASTERS.glob("portrait-*.webp"))
    if len(masters) != 6:
        raise SystemExit(f"Expected six local portrait masters, found {len(masters)}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for path in masters:
        image = Image.open(path).convert("RGB")
        if image.size != (896, 1120):
            raise ValueError(f"Wrong master size: {path}")
        image.resize((448, 560), Image.Resampling.LANCZOS).save(
            OUTPUT / path.name, "WEBP", quality=84, method=6
        )
    print("Exported six local portrait masters")


if __name__ == "__main__":
    main()
