import ast
import logging
from pathlib import Path
import sys

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.config import settings
from app.core.dependencies import DbSession, get_current_player
from app.services.guild_service import get_current_guild_context
from app.services.github_releases import (
    check_for_update,
    provider_status,
    read_installed_channel,
)


router = APIRouter()
logger = logging.getLogger("gim.update")
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
            "github_releases_status": provider_status(
                read_installed_channel() if getattr(sys, "frozen", False) else None
            ),
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
        "reason": (
            f"O checkout contém a versão {disk_version}; feche a campanha e reabra o aplicativo."
            if is_newer else "Checkout local já está nesta versão."
        ),
    }


@router.get("/updates/check")
def check_local_update(request: Request, current_user=Depends(get_current_player)):
    if current_user is None:
        return JSONResponse({"channel": "unavailable", "available": False, "reason": "Abra uma campanha para consultar atualizações."}, status_code=401)
    if request.app.state.app_mode == "desktop" and getattr(sys, "frozen", False):
        logger.info("Updater check route requested: version=%s", request.app.version)
        installed_channel = read_installed_channel()
        logger.info("Updater check reading installation marker: channel=%s", installed_channel)
        release_status, _offer = check_for_update(
            request.app.version,
            installed_channel,
            download=False,
        )
        logger.info(
            "Updater check route completed: available=%s version=%s failed=%s",
            release_status.get("available"), release_status.get("available_version"),
            release_status.get("failed", False),
        )
        return JSONResponse({**release_status, "current_version": request.app.version})
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
