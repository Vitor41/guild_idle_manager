from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_user
from app.core.forms import read_form_fields
from app.models.user import User
from app.services.auth_service import RegistrationError, authenticate_user, register_user
from app.services.guild_service import get_current_guild_context
from app.repositories.guild_repository import get_guild_by_user_id
from app.services.offline_progress_service import process_offline_progress
from app.services.session_service import SESSION_GLOBAL_SECONDS, SESSION_IDLE_SECONDS, expire_stale_online_session, start_offline_period, start_online_session, utc_now


router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def redirect_after_login(db: DbSession, user: User) -> RedirectResponse:
    guild, _ = get_current_guild_context(db, user.id)
    target = "/dashboard" if guild else "/guild/create"
    return RedirectResponse(target, status_code=303)


@router.get("/register")
def register_form(request: Request, current_user: User | None = Depends(get_current_user)):
    if current_user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={"error": None, "form": {}},
    )


@router.post("/register")
async def register_submit(request: Request, db: DbSession):
    form = await read_form_fields(request)
    form_data = {
        "username": str(form.get("username", "")),
        "email": str(form.get("email", "")),
    }
    try:
        register_user(
            db=db,
            username=form_data["username"],
            email=form_data["email"] or None,
            password=str(form.get("password", "")),
            confirm_password=str(form.get("confirm_password", "")),
        )
    except RegistrationError as error:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"error": str(error), "form": form_data},
            status_code=400,
        )
    return RedirectResponse("/login?registered=1", status_code=303)


@router.get("/login")
def login_form(request: Request, current_user: User | None = Depends(get_current_user)):
    if current_user:
        return RedirectResponse("/", status_code=303)
    reason = request.session.pop("session_expired_reason", None)
    messages = {
        "idle": "Sua sessão foi encerrada após 1 hora sem atividade. O progresso offline começou a ser contado.",
        "global": "Sua sessão de 5 horas foi encerrada. Entre novamente para continuar.",
        "replaced": "Esta sessão foi substituída por um novo login.",
        "expired": "Sua sessão expirou. Entre novamente para continuar.",
    }
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"error": None, "registered": request.query_params.get("registered") == "1", "session_message": messages.get(reason)},
    )


@router.post("/login")
async def login_submit(request: Request, db: DbSession):
    form = await read_form_fields(request)
    user = authenticate_user(
        db=db,
        username=str(form.get("username", "")),
        password=str(form.get("password", "")),
    )
    if user is None:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"error": "Usuario ou senha invalidos.", "registered": False, "session_message": None},
            status_code=400,
        )

    guild = get_guild_by_user_id(db, user.id)
    offline_summary = None
    session_token = None
    now = utc_now()
    if guild is not None:
        expire_stale_online_session(db, guild, now)
        offline_summary = process_offline_progress(db, guild)
        session_token = start_online_session(db, guild, now)
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["session_started_at"] = int(now.timestamp())
    request.session["last_activity_at"] = int(now.timestamp())
    request.session["session_global_seconds"] = SESSION_GLOBAL_SECONDS
    request.session["session_idle_seconds"] = SESSION_IDLE_SECONDS
    if session_token is not None:
        request.session["session_token"] = session_token
    if offline_summary is not None:
        request.session["offline_summary"] = offline_summary
    return redirect_after_login(db, user)


@router.get("/logout")
def logout(request: Request, db: DbSession, current_user: User | None = Depends(get_current_user)):
    reason = request.query_params.get("reason") or request.session.get("session_expired_reason")
    if current_user is not None:
        guild = get_guild_by_user_id(db, current_user.id)
        if guild is not None:
            start_offline_period(db, guild, utc_now(), request.session.get("session_token"))
    request.session.clear()
    if reason in {"idle", "global", "replaced", "expired"}:
        request.session["session_expired_reason"] = reason
    return RedirectResponse("/login", status_code=303)
