"""Render a static offline catalog of all desktop sprites for visual review."""

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "app" / "static" / "assets" / "desktop" / "manifest.json"
OUTPUT = ROOT / "design" / "preview" / "sprite-catalog.html"
GROUPS = (
    ("class-", "Classes e evoluções"),
    ("building-", "Construções e locais"),
    ("item-", "Equipamentos e consumíveis"),
    ("material-", "Materiais"),
    ("resource-", "Recursos"),
    ("biome-", "Biomas de masmorra"),
    ("status-", "Estados"),
)


def card(key: str) -> str:
    path = f"../../app/static/assets/desktop/sprites/128/{key}.png"
    label = html.escape(key)
    return (
        f'<figure class="sprite-card"><div class="sprite-size-row">'
        f'<img class="sprite48" src="{path}" alt="">'
        f'<img class="sprite24" src="{path}" alt="">'
        f'</div><figcaption>{label}</figcaption></figure>'
    )


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    keys = sorted(data["sprites"])
    sections = []
    included = set()
    for prefix, title in GROUPS:
        matching = [key for key in keys if key.startswith(prefix)]
        included.update(matching)
        sections.append(f'<section><h2>{title} <small>{len(matching)}</small></h2><div class="sprite-grid">' + "".join(map(card, matching)) + "</div></section>")
    remaining = [key for key in keys if key not in included]
    sections.append(f'<section><h2>Campanha e chefes <small>{len(remaining)}</small></h2><div class="sprite-grid">' + "".join(map(card, remaining)) + "</div></section>")
    portrait_cards = []
    for family in ("apprentice", "warrior", "rogue", "mage", "cleric", "archer"):
        path = f"../../app/static/assets/desktop/portraits/portrait-{family}.webp"
        portrait_cards.append(f'<figure class="portrait-card"><img src="{path}" alt="Retrato do arquétipo {family}"><figcaption>{family}</figcaption></figure>')
    document = f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Catálogo de sprites desktop — Guild Idle Manager</title>
<style>:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#101a1d;color:#f1eadb;font:14px/1.5 "Segoe UI",Tahoma,sans-serif}}main{{max-width:1440px;margin:auto;padding:28px}}h1,h2{{font-family:Georgia,serif;font-weight:400}}h1{{font-size:38px;margin:0 0 9px}}h2{{margin:28px 0 12px;font-size:25px}}h2 small{{font:11px "Segoe UI",sans-serif;color:#9bd498}}p{{color:#b5c6c4}}a{{color:#f5d798}}a:focus-visible{{outline:3px solid #f5d798;outline-offset:3px}}.sprite-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}}.sprite-card{{margin:0;min-height:108px;padding:10px;border:1px solid #375057;background:#1b2a2e}}.sprite-size-row{{display:flex;align-items:center;justify-content:space-around;min-height:60px}}.sprite48{{width:48px;height:48px;object-fit:contain}}.sprite24{{width:24px;height:24px;object-fit:contain}}figcaption{{overflow-wrap:anywhere;font-size:11px;color:#d0ded9}}.portrait-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:10px}}.portrait-card{{margin:0;border:1px solid #375057;background:#1b2a2e;padding:8px}}.portrait-card img{{display:block;width:100%;aspect-ratio:4/5;object-fit:cover;margin-bottom:6px}}.note{{padding:11px 14px;border-left:3px solid #e6b965;background:#1d3033}}@media(max-width:520px){{main{{padding:18px}}.sprite-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}</style></head><body><main>
<p><a href="index.html">← Voltar ao Salão da Guilda</a></p><h1>Catálogo de sprites</h1><p>{len(keys)} símbolos bitmap originais · 64/128 px, master 512 px · prova de leitura a 48 e 24 px. Cada ícone aparece junto do seu código; no jogo, acompanhar por nome ou tooltip.</p>
<p class="note">A raridade é borda e rótulo CSS. Retratos são reutilizados pela família de classe; o emblema individual distingue cada evolução. Nenhuma imagem legada é carregada nesta página.</p>
{''.join(sections)}<section><h2>Retratos de arquétipo <small>6</small></h2><div class="portrait-grid">{''.join(portrait_cards)}</div></section>
</main></body></html>'''
    OUTPUT.write_text(document, encoding="utf-8")
    print(f"Wrote static catalog: {len(keys)} sprites, {len(portrait_cards)} portraits")


if __name__ == "__main__":
    main()
