from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_player
from app.core.forms import read_form_fields
from app.models.user import User
from app.services.guild_service import get_current_guild_context
from app.services.profession_service import ProfessionError, complete_profession_training, get_professions_context, start_profession_training


router = APIRouter(prefix="/professions")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("")
def professions_index(request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    return templates.TemplateResponse(request=request, name="professions/index.html", context={
        "current_user": current_user, "guild": guild, "resources": resources,
        "message": request.query_params.get("message"), "error": request.query_params.get("error"),
        **get_professions_context(db, guild),
    })


@router.post("/train")
async def train(request: Request, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None or resources is None:
        return RedirectResponse("/guild/create", status_code=303)
    form = await read_form_fields(request)
    try:
        start_profession_training(db, guild, resources, int(form.get("mercenary_id", "0")), int(form.get("profession_id", "0")))
    except (ValueError, ProfessionError) as error:
        return RedirectResponse(f"/professions?error={quote(str(error))}", status_code=303)
    return RedirectResponse("/professions?message=Treinamento%20iniciado.", status_code=303)


@router.post("/trainings/{training_id}/complete")
def complete(training_id: int, db: DbSession, current_user: User | None = Depends(get_current_player)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, _ = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    try:
        complete_profession_training(db, guild, training_id)
    except ProfessionError as error:
        return RedirectResponse(f"/professions?error={quote(str(error))}", status_code=303)
    return RedirectResponse("/professions?message=Profissao%20concluida.", status_code=303)
