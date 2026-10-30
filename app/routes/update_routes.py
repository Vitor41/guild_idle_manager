import ast
from pathlib import Path
import sys

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.config import settings
from app.core.dependencies import DbSession, get_current_player
from app.services.guild_service import get_current_guild_context


router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
SOURCE_ROOT = Path(__file__).resolve().parents[2]


@router.get("/updates")
def updates(request: Request, db: DbSession, current_user=Depends(get_current_player)):
    if current_user is None:
        destination = "/desktop/campaigns" if request.app.state.app_mode == "desktop" else "/login"
        return RedirectResponse(destination, status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    if guild is None:
        return RedirectResponse("/guild/create", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="updates.html",
        context={"current_user": current_user, "guild": guild, "resources": resources, "release_version": request.app.version},
    )


@router.get("/updates/check")
def check_local_update(request: Request, current_user=Depends(get_current_player)):
    if current_user is None:
        return JSONResponse({"channel": "unavailable", "available": False, "reason": "Abra uma campanha para consultar atualizações."}, status_code=401)
    if settings.app_env != "local" or getattr(sys, "frozen", False):
        return JSONResponse({
            "channel": "production",
            "current_version": request.app.version,
            "available": False,
            "reason": "Esta distribuição não possui feed oficial assinado. Atualizações chegam por um instalador revisado.",
        })
    version_path = SOURCE_ROOT / "app" / "core" / "version.py"
    try:
        syntax = ast.parse(version_path.read_text(encoding="utf-8"), filename=str(version_path))
        assignment = next(
            node for node in syntax.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "APP_VERSION" for target in node.targets)
        )
        disk_version = ast.literal_eval(assignment.value)
        if not isinstance(disk_version, str):
            raise ValueError("APP_VERSION deve ser texto.")
        running = tuple(int(part) for part in request.app.version.split("."))
        available = tuple(int(part) for part in disk_version.split("."))
        is_newer = len(running) == len(available) and available > running
    except (OSError, SyntaxError, StopIteration, ValueError, TypeError):
        return JSONResponse({
            "channel": "dev-local",
            "current_version": request.app.version,
            "available": False,
            "reason": "Não foi possível ler uma versão local válida do checkout.",
        })
    return JSONResponse({
        "channel": "dev-local",
        "current_version": request.app.version,
        "available_version": disk_version,
        "available": is_newer,
        "apply_action": "Feche o jogo e reinicie Iniciando_jogo_dev.bat; use Ctrl+R somente para Jinja, CSS e JavaScript." if is_newer else None,
        "reason": "Checkout local já está nesta versão." if not is_newer else None,
    })
