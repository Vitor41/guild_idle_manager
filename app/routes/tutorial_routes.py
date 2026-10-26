from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_user
from app.models.user import User
from app.services.guild_service import get_current_guild_context


router = APIRouter(prefix="/tutorial")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")

TUTORIAL_STEPS = (
    ("Boas-vindas", "Bem-vindo ao Guild Idle Manager. Você administra uma guilda, contrata mercenários e organiza sua progressão."),
    ("Sua guilda", "A guilda é o centro da progressão. Construções liberam recursos, capacidade e novas possibilidades."),
    ("Taverna", "Contrate Aprendizes e visitantes especiais na Taverna. Compare atributos, raridade e potencial antes de investir."),
    ("Atributos", "FOR favorece dano físico; AGI, precisão e mobilidade; INT, magia e suporte; VIT, resistência; SOR, oportunidades."),
    ("Classes", "Aprendizes evoluem no nível correto. O Guia de Classes mostra caminhos, requisitos e perfis de cada especialização."),
    ("Missões", "Missões geram XP, ouro, itens e materiais. Escolha um grupo dentro dos requisitos e observe a chance estimada."),
    ("Coleta", "Expedições de coleta são fontes confiáveis de materiais e possuem faixas próprias até o nível 350."),
    ("Profissões", "Treine uma profissão para especializar um mercenário. A profissão compatível aumenta a quantidade coletada."),
    ("Equipamentos", "Armas, armaduras e acessórios melhoram atributos. Respeite nível, classe e slots ao equipar."),
    ("Masmorras", "Masmorras e chefes exigem grupos mais fortes, mas oferecem materiais e equipamentos de maior qualidade."),
    ("Docas", "Evolua as Docas para receber mercantes rotativos. O estoque é limitado e cada rotação usa o relógio do servidor."),
    ("Progresso idle", "Sua guilda produz ouro durante a ausência até o limite offline. Volte para coletar e reinvestir."),
    ("Pronto para liderar", "Você já conhece o essencial. Monte seu grupo, escolha objetivos e avance no seu próprio ritmo."),
)


def _set_status(db: DbSession, user: User, status: str) -> None:
    user.tutorial_status = status
    db.add(user)
    db.commit()


@router.post("/start")
def start(db: DbSession, current_user: User | None = Depends(get_current_user)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    current_user.tutorial_status = "in_progress"
    db.add(current_user)
    db.commit()
    return RedirectResponse("/tutorial?step=1", status_code=303)


@router.post("/decline")
def decline(db: DbSession, current_user: User | None = Depends(get_current_user)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    _set_status(db, current_user, "declined")
    return RedirectResponse("/dashboard", status_code=303)


@router.get("")
def tutorial_page(request: Request, db: DbSession, current_user: User | None = Depends(get_current_user)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    guild, resources = get_current_guild_context(db, current_user.id)
    try:
        step = int(request.query_params.get("step", "1"))
    except ValueError:
        step = 1
    step = max(1, min(step, len(TUTORIAL_STEPS)))
    return templates.TemplateResponse(request=request, name="tutorial/index.html", context={
        "current_user": current_user, "guild": guild, "resources": resources, "steps": TUTORIAL_STEPS,
        "step": step, "step_data": TUTORIAL_STEPS[step - 1], "replay": request.query_params.get("replay") == "1",
    })


@router.post("/complete")
def complete(db: DbSession, current_user: User | None = Depends(get_current_user)):
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    _set_status(db, current_user, "completed")
    return RedirectResponse("/dashboard?message=Tutorial%20concluido.", status_code=303)
