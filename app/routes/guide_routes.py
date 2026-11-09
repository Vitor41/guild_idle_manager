from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.core.game_balance import OFFLINE_CAP_SECONDS, OFFLINE_MINIMUM_SECONDS
from app.core.game_balance import MARKET_RARITY_SECONDS
from app.core.version import APP_VERSION
from app.models.user import User
from app.services.building_service import get_building_bonus_summary
from app.services.display_service import rarity_label
from app.services.guide_catalog_service import SOURCE_LABELS, build_guide_catalog
from app.services.guild_service import get_current_guild_context
from app.services.offline_progress_service import get_passive_gold_rate


router = APIRouter(prefix="/guide")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _guide_context(request: Request, db, current_user):
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return None
    return {
        "current_user": current_user, "guild": guild, "resources": resources,
        "idle_rate": get_passive_gold_rate(db, guild),
        "offline_minimum_minutes": OFFLINE_MINIMUM_SECONDS // 60,
        "offline_cap_hours": OFFLINE_CAP_SECONDS // 3600,
        "building_bonuses": get_building_bonus_summary(db, guild.id),
        "market_rarity_durations": [
            {
                "rarity": rarity,
                "seconds": seconds,
                "formatted_seconds": f"{seconds:,}".replace(",", "."),
            }
            for rarity, seconds in MARKET_RARITY_SECONDS.items()
        ],
        "market_rarity_label": rarity_label,
    }


@router.get("")
def game_guide(request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    context = _guide_context(request, db, current_user)
    if context is None:
        return RedirectResponse("/guild/create", status_code=303)
    return templates.TemplateResponse(request=request, name="guide/index.html", context=context,
        headers={"Cache-Control": "no-store"})


@router.get("/catalog.json")
def guide_catalog_api(db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return JSONResponse({"error": "Autenticação necessária."}, status_code=401, headers={"Cache-Control": "no-store"})
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return JSONResponse({"error": "Guilda não encontrada."}, status_code=404, headers={"Cache-Control": "no-store"})
    return JSONResponse(build_guide_catalog(db), headers={"Cache-Control": "no-store"})


class _GuideMarkdownParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    SKIP_CLASSES = {"guide-search", "guide-index", "guide-rate", "guide-private-value", "guide-catalog-controls",
        "guide-source-index", "guide-catalog-status", "guide-catalog-error", "guide-catalog-empty",
        "guide-catalog-table-wrap", "guide-actions"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self.stack: list[str] = []
        self.inside = False
        self.skip_depth = 0
        self.skip_tag_depths: list[int] = []
        self.depth = 0
        self.link_stack: list[tuple[int, str]] = []
        self.in_table_header = False
        self.table_column_count = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if not self.inside:
            if tag == "section" and "game-guide" in classes:
                self.inside = True
                self.depth = 1
                self.stack.append(tag)
            return
        if tag not in self.VOID:
            self.depth += 1
            self.stack.append(tag)
        if self.skip_depth:
            if tag not in self.VOID:
                self.skip_depth += 1
            return
        if classes & self.SKIP_CLASSES:
            self.skip_depth = 1
            self.skip_tag_depths.append(self.depth)
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.output.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "p":
            self.output.append("\n\n")
        elif tag == "li":
            self.output.append("\n- ")
        elif tag in {"ul", "ol", "article", "section", "div", "header", "aside", "nav"}:
            self.output.append("\n")
        elif tag == "br":
            self.output.append("\n")
        elif tag in {"strong", "b"}:
            self.output.append(" **")
        elif tag in {"em", "i"}:
            self.output.append(" *")
        elif tag == "a":
            self.link_stack.append((self.depth, attrs.get("href", "")))
            self.output.append("[")
        elif tag == "table":
            self.output.append("\n\n")
        elif tag == "thead":
            self.in_table_header = True
        elif tag == "tr":
            self.table_column_count = 0
            self.output.append("| ")

    def handle_endtag(self, tag):
        if not self.inside:
            return
        if self.skip_depth:
            self.skip_depth -= 1
            if self.skip_depth == 0 and self.skip_tag_depths:
                self.skip_tag_depths.pop()
        else:
            if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
                self.output.append("\n")
            elif tag in {"p", "li", "article", "section", "div", "header", "aside", "nav"}:
                self.output.append("\n")
            elif tag in {"strong", "b"}:
                self.output.append("** ")
            elif tag in {"em", "i"}:
                self.output.append("* ")
            elif tag == "a":
                link = self.link_stack.pop()[1] if self.link_stack else ""
                self.output.append(f"]({link})" if link else "]")
            elif tag in {"th", "td"}:
                self.table_column_count += 1
                self.output.append(" | ")
            elif tag == "tr":
                self.output.append("\n")
                if self.in_table_header and self.table_column_count:
                    self.output.append("| " + " | ".join(["---"] * self.table_column_count) + " |\n")
            elif tag == "thead":
                self.in_table_header = False
            elif tag == "table":
                self.output.append("\n")
        if tag not in self.VOID and self.stack:
            popped = self.stack.pop()
            self.depth -= 1
            if popped == "section" and self.depth == 0:
                self.inside = False

    def handle_data(self, data):
        if self.inside and not self.skip_depth:
            self.output.append(data)


def _markdown_escape(value: object) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>])", r"\\\1", text)


def _catalog_markdown(catalog: dict[str, object]) -> str:
    rows = catalog["items"]
    lines = ["## Equipamentos e Materiais", "", "Catálogo da campanha atual. As fontes abaixo são configuração ativa; requisitos e rotação podem limitar quando aparecem no jogo.", ""]
    if not rows:
        return "\n".join(lines + ["Nenhum equipamento ou material ativo neste catálogo.", ""])
    for row in rows:
        slot_text = f" · espaço {_markdown_escape(row['equipment_slot'])}" if row["equipment_slot"] else ""
        lines.extend([f"### {_markdown_escape(row['name'])}", "",
            f"{_markdown_escape(row['item_type_label'])}{slot_text} · {_markdown_escape(row['rarity'])} · Tier {row['tier']} · faixa {_markdown_escape(row['level_band'])} · nível {row['item_level']}", ""])
        if not row["sources"]:
            lines.extend(["**Sem fonte disponível.**", ""])
            continue
        for source in row["sources"]:
            price_text = f" Preço unitário registrado: {_markdown_escape(source['price'])} ouro." if source["price"] else ""
            lines.append(f"- **{_markdown_escape(source['label'])}** — {_markdown_escape(source['name'])}. {_markdown_escape(source['chance'])}. Quantidade: {_markdown_escape(source['quantity'])}. Requisito: {_markdown_escape(source['requirement'])}.{price_text}")
        lines.append("")
    return "\n".join(lines)


@router.get("/export.md")
def export_guide_markdown(request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    context = _guide_context(request, db, current_user)
    if context is None:
        return RedirectResponse("/guild/create", status_code=303)
    rendered = templates.TemplateResponse(request=request, name="guide/index.html", context=context).body.decode("utf-8")
    parser = _GuideMarkdownParser()
    parser.feed(rendered)
    canonical_guide = re.sub(r"\n{3,}", "\n\n", "".join(parser.output)).strip()
    catalog = build_guide_catalog(db)
    generated = datetime.now().astimezone().date().isoformat()
    markdown = (f"# Guia do Jogo — Guild Idle Manager\n\nVersão: {APP_VERSION}  \nGerado em: {generated}\n\n"
        + canonical_guide + "\n\n" + _catalog_markdown(catalog) + "\n")
    return Response(markdown, media_type="text/markdown", headers={
        "Content-Disposition": 'attachment; filename="guia-guild-idle-manager.md"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })
