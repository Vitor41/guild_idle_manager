from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.core.forms import read_form_multi_fields
from app.models.user import User
from app.services.dungeon_service import (
    DungeonError,
    claim_all_ready_dungeon_loot,
    claim_dungeon_loot,
    format_bulk_dungeon_result,
    format_dungeon_result_message,
    get_dungeons_page_context,
    get_dungeon_supply_quote,
    start_dungeon,
)
from app.services.guild_service import get_current_guild_context


router = APIRouter(prefix="/dungeons")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.post("/supply-quote")
async def supply_quote(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return JSONResponse({"available": False, "reason": "Sessão indisponível."}, status_code=401)
    guild, _resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return JSONResponse({"available": False, "reason": "Guilda indisponível."}, status_code=404)
    form = await read_form_multi_fields(request)
    quote = get_dungeon_supply_quote(
        db, guild,
        (form.get("dungeon_template_id") or [""])[0],
        form.get("mercenary_ids", []),
        (form.get("run_multiplier") or ["1"])[0],
    )
    return JSONResponse(quote)


def _dungeon_error_url(error: object, form: dict[str, list[str]]) -> str:
    query = [("error", str(error))]
    query.extend(("selected_mercenary_id", value) for value in form.get("mercenary_ids", []))
    if (form.get("supply") or [""])[0] == "1":
        query.append(("selected_supply", "1"))
    return "/dungeons?" + urlencode(query, doseq=True)


@router.get("")
def dungeons_index(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    try:
        page = int(request.query_params.get("page", "1"))
    except ValueError:
        page = 1
    content_type = request.query_params.get("type", "dungeon")
    if content_type not in {"dungeon", "boss", "all"}:
        content_type = "dungeon"
    difficulty = request.query_params.get("difficulty", "all")
    if difficulty not in {"all", "normal", "hard", "heroic", "legendary"}:
        difficulty = "all"
    sort = request.query_params.get("sort", "level")
    if sort not in {"level", "time", "xp", "gold", "power"}:
        sort = "level"
    context = get_dungeons_page_context(
        db, guild, request.query_params.get("band", "1-20"), content_type, page, difficulty, sort,
    )
    return templates.TemplateResponse(
        request=request,
        name="dungeons/index.html",
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "error": request.query_params.get("error"),
            "selected_start_mercenary_ids": request.query_params.getlist("selected_mercenary_id"),
            "selected_start_supply": request.query_params.get("selected_supply") == "1",
            "message": request.query_params.get("message"),
            "result_status": request.query_params.get("result"),
            **context,
        },
    )


@router.post("/start")
async def start(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, _ = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    form = await read_form_multi_fields(request)
    try:
        start_dungeon(
            db=db,
            guild=guild,
            dungeon_template_id=(form.get("dungeon_template_id") or [""])[0],
            mercenary_ids=form.get("mercenary_ids", []),
            run_multiplier=(form.get("run_multiplier") or ["1"])[0],
            supply_selected=(form.get("supply") or [""])[0] == "1",
        )
    except DungeonError as error:
        return RedirectResponse(_dungeon_error_url(error, form), status_code=303)

    return RedirectResponse("/dungeons?message=Masmorra%20iniciada.", status_code=303)


@router.post("/claim-all")
def claim_all(db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    try:
        summary = claim_all_ready_dungeon_loot(db, guild, resources)
    except DungeonError as error:
        return RedirectResponse(f"/dungeons?error={quote(str(error))}#loot-disponivel", status_code=303)
    return RedirectResponse(
        f"/dungeons?message={quote(format_bulk_dungeon_result(summary))}#loot-disponivel",
        status_code=303,
    )


@router.post("/{dungeon_run_id}/claim")
def claim(
    dungeon_run_id: int,
    db: DbSession,
    current_user: User | None = Depends(get_current_player),
):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)

    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    try:
        dungeon_run = claim_dungeon_loot(db, guild, resources, dungeon_run_id)
    except DungeonError as error:
        return RedirectResponse(f"/dungeons?error={quote(str(error))}", status_code=303)

    return RedirectResponse(
        f"/dungeons?message={quote(format_dungeon_result_message(dungeon_run))}&result={'success' if dungeon_run.success else 'failed'}",
        status_code=303,
    )
