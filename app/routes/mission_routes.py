from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.core.forms import read_form_multi_fields
from app.models.user import User
from app.services.guild_service import get_current_guild_context
from app.services.mission_service import (
    MissionError,
    claim_all_ready_mission_loot,
    claim_mission_loot,
    format_bulk_mission_result,
    format_result_message,
    get_missions_page_context,
    start_mission,
)


router = APIRouter(prefix="/missions")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _mission_error_url(error: object, form: dict[str, list[str]]) -> str:
    query = [("error", str(error))]
    query.extend(("selected_mercenary_id", value) for value in form.get("mercenary_ids", []))
    if (form.get("supply") or [""])[0] == "1":
        query.append(("selected_supply", "1"))
    return "/missions?" + urlencode(query, doseq=True)


@router.get("")
def missions_index(
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
    category = request.query_params.get("category", "combat")
    if category not in {"combat", "gathering", "all"}:
        category = "combat"
    focus = request.query_params.get("focus", "all")
    if focus not in {"all", "gold", "xp", "equipment"}:
        focus = "all"
    sort = request.query_params.get("sort", "level")
    if sort not in {"level", "time", "xp", "gold", "chance"}:
        sort = "level"
    mode = request.query_params.get("mode", "standard")
    if mode not in {"standard", "long", "all"}:
        mode = "standard"
    if category == "gathering":
        mode = "standard"
    levels: list[int] = []
    for value in request.query_params.getlist("levels"):
        try:
            levels.append(int(value))
        except ValueError:
            continue
    context = get_missions_page_context(
        db, guild, request.query_params.get("band", "1-20"), category, page, focus, sort, mode, tuple(levels),
        request.query_params.get("material", "all"),
    )
    return templates.TemplateResponse(
        request=request,
        name="missions/index.html",
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
    if request.app.state.app_mode == "desktop":
        return RedirectResponse("/regional?error=Novos%20contratos%20s%C3%A3o%20iniciados%20pela%20Vig%C3%ADlia%20Regional", status_code=303)

    guild, _ = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)

    form = await read_form_multi_fields(request)
    try:
        start_mission(
            db=db,
            guild=guild,
            mission_template_id=(form.get("mission_template_id") or [""])[0],
            mercenary_ids=form.get("mercenary_ids", []),
            run_multiplier=(form.get("run_multiplier") or ["1"])[0],
            supply_selected=(form.get("supply") or [""])[0] == "1",
        )
    except MissionError as error:
        return RedirectResponse(_mission_error_url(error, form), status_code=303)

    return RedirectResponse("/missions?message=Missao%20iniciada.", status_code=303)


@router.post("/claim-all")
def claim_all(db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    try:
        summary = claim_all_ready_mission_loot(db, guild, resources)
    except MissionError as error:
        return RedirectResponse(f"/missions?error={quote(str(error))}#loot-disponivel", status_code=303)
    return RedirectResponse(
        f"/missions?message={quote(format_bulk_mission_result(summary))}#loot-disponivel",
        status_code=303,
    )


@router.post("/{mission_run_id}/claim")
def claim(
    mission_run_id: int,
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
        mission_run = claim_mission_loot(
            db=db,
            guild=guild,
            resources=resources,
            mission_run_id=mission_run_id,
        )
    except MissionError as error:
        return RedirectResponse(f"/missions?error={quote(str(error))}", status_code=303)

    return RedirectResponse(
        f"/missions?message={quote(format_result_message(mission_run))}&result={'success' if mission_run.success else 'failed'}",
        status_code=303,
    )
