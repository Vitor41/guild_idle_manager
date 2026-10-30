import ast
from pathlib import Path
import sys
import threading

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.config import settings
from app.core.dependencies import DbSession, get_current_player
from app.services.guild_service import get_current_guild_context
from app.services.github_releases import provider_status


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
        context={
            "current_user": current_user,
            "guild": guild,
            "resources": resources,
            "release_version": request.app.version,
            "is_packaged": getattr(sys, "frozen", False),
            "github_releases_status": provider_status(),
            "can_restart_local_checkout": (
                request.app.state.app_mode == "desktop"
                and settings.app_env == "local"
                and not getattr(sys, "frozen", False)
            ),
        },
    )


def _local_checkout_update_status(request: Request) -> dict[str, object]:
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
        return {
            "channel": "dev-local",
            "current_version": request.app.version,
            "available": False,
            "reason": "Não foi possível ler uma versão local válida do checkout.",
        }
    return {
        "channel": "dev-local",
        "current_version": request.app.version,
        "available_version": disk_version,
        "available": is_newer,
        "apply_action": "Reiniciar e aplicar a versão já presente no checkout." if is_newer else None,
        "reason": "Checkout local já está nesta versão." if not is_newer else None,
    }


def _schedule_local_checkout_restart(callback) -> None:
    timer = threading.Timer(0.75, callback)
    timer.daemon = True
    timer.start()


@router.get("/updates/check")
def check_local_update(request: Request, current_user=Depends(get_current_player)):
    if current_user is None:
        return JSONResponse({"channel": "unavailable", "available": False, "reason": "Abra uma campanha para consultar atualizações."}, status_code=401)
    if settings.app_env != "local" or getattr(sys, "frozen", False):
        release_status = provider_status()
        return JSONResponse({
            **release_status,
            "current_version": request.app.version,
            "reason": release_status["reason"],
            "manual_action": (
                "Obtenha o novo GuildIdleManager-DEV-Setup.exe pelo mesmo canal que forneceu esta instalação, "
                "feche completamente o jogo e execute o Setup sobre a instalação DEV existente. "
                "O Setup gerenciado substitui apenas os arquivos do aplicativo; os saves ficam em "
                "%LOCALAPPDATA%\\GuildIdleManager\\saves."
            ),
        })
    return JSONResponse(_local_checkout_update_status(request))


@router.post("/updates/apply-local")
def apply_local_checkout_update(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_player),
):
    if current_user is None:
        return JSONResponse({"reason": "Abra uma campanha para aplicar a versão local."}, status_code=401)
    if (
        request.app.state.app_mode != "desktop"
        or settings.app_env != "local"
        or getattr(sys, "frozen", False)
    ):
        return JSONResponse({"reason": "A ação só está disponível no checkout desktop local."}, status_code=404)

    status = _local_checkout_update_status(request)
    if not status.get("available"):
        return JSONResponse(status, status_code=409)
    restart_callback = getattr(request.app.state, "request_local_checkout_restart", None)
    if not callable(restart_callback):
        return JSONResponse({"reason": "O launcher não disponibilizou o reinício gracioso."}, status_code=503)

    background_tasks.add_task(_schedule_local_checkout_restart, restart_callback)
    return JSONResponse({
        "channel": "dev-local",
        "restarting": True,
        "current_version": request.app.version,
        "available_version": status["available_version"],
        "reason": "A janela será fechada e o checkout local reiniciado.",
    })
