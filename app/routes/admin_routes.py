from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.dependencies import DbSession, get_current_user
from app.core.forms import read_form_fields, read_form_multi_fields
from app.models.user import User
from app.services.mission_service import format_duration_seconds, split_duration_seconds
from app.services.building_service import get_effect_label
from app.services.equipment_service import get_equipment_slot_label
from app.services.content_validation_service import build_content_report
from app.services.admin_service import (
    AdminBuildingError,
    AdminClassError,
    AdminDungeonError,
    AdminDropError,
    AdminItemError,
    AdminMissionError,
    AdminTavernError,
    create_admin_mission,
    get_admin_building_template,
    get_admin_class,
    get_admin_drop,
    get_admin_dungeon,
    get_admin_dungeon_drop,
    get_admin_item,
    get_admin_mission,
    get_admin_tavern_config,
    list_active_admin_items,
    list_admin_building_templates,
    list_admin_classes,
    list_admin_drops,
    list_admin_dungeon_drops,
    list_admin_dungeons,
    list_admin_items,
    list_admin_missions,
    save_admin_building_template,
    save_admin_class,
    save_admin_dungeon,
    save_admin_dungeon_drop,
    save_admin_drop,
    save_admin_item,
    save_admin_mission_order,
    save_admin_tavern_config,
    update_admin_mission,
)


router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
templates.env.globals.update(get_equipment_slot_label=get_equipment_slot_label)


def require_admin(current_user: User | None) -> User | RedirectResponse:
    if current_user is None:
        return RedirectResponse("/login", status_code=303)
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso administrativo indisponivel.")
    return current_user


@router.get("")
def admin_index(
    request: Request,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/index.html",
        context={"current_user": admin_user},
    )


@router.get("/content-report")
def admin_content_report(request: Request, db: DbSession, current_user: User | None = Depends(get_current_user)):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(request=request, name="admin/content_report.html", context={
        "current_user": admin_user, "report": build_content_report(db),
    })


@router.get("/classes")
def admin_classes(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/classes.html",
        context={
            "current_user": admin_user,
            "classes": list_admin_classes(db),
        },
    )


@router.get("/classes/{class_id}/edit")
def edit_class_form(
    class_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    mercenary_class = get_admin_class(db, class_id)
    if mercenary_class is None:
        return RedirectResponse("/admin/classes", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin/class_form.html",
        context={"current_user": admin_user, "class": mercenary_class, "classes": list_admin_classes(db), "error": None, "form": {}},
    )


@router.post("/classes/{class_id}/edit")
async def edit_class_submit(
    class_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    mercenary_class = get_admin_class(db, class_id)
    if mercenary_class is None:
        return RedirectResponse("/admin/classes", status_code=303)
    form = await read_form_fields(request)
    try:
        save_admin_class(db, form, mercenary_class)
    except AdminClassError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/class_form.html",
            context={"current_user": admin_user, "class": mercenary_class, "classes": list_admin_classes(db), "error": str(error), "form": form},
            status_code=400,
        )
    return RedirectResponse("/admin/classes", status_code=303)


@router.get("/tavern")
def admin_tavern(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/tavern.html",
        context={
            "current_user": admin_user,
            "config": get_admin_tavern_config(db),
            "error": None,
            "form": {},
        },
    )


@router.post("/tavern")
async def admin_tavern_submit(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    form = await read_form_fields(request)
    try:
        config = save_admin_tavern_config(db, form)
    except AdminTavernError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/tavern.html",
            context={
                "current_user": admin_user,
                "config": form,
                "error": str(error),
                "form": form,
            },
            status_code=400,
        )
    return templates.TemplateResponse(
        request=request,
        name="admin/tavern.html",
        context={"current_user": admin_user, "config": config, "error": None, "message": "Configuracao salva.", "form": {}},
    )


@router.get("/missions")
def admin_missions(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/missions.html",
        context={
            "current_user": admin_user,
            "missions": list_admin_missions(db),
            "message": request.query_params.get("message"),
            "format_duration": format_duration_seconds,
        },
    )


@router.get("/missions/create")
def create_mission_form(
    request: Request,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/edit_mission.html",
        context={
            "current_user": admin_user,
            "mission": None,
            "error": None,
            "form": {},
            "split_duration": split_duration_seconds,
        },
    )


@router.post("/missions/reorder")
async def reorder_missions_submit(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    form = await read_form_multi_fields(request)
    try:
        save_admin_mission_order(db, form.get("mission_ids", []))
    except AdminMissionError as error:
        return RedirectResponse(f"/admin/missions?message={quote(str(error))}", status_code=303)
    return RedirectResponse("/admin/missions?message=Ordem das missões atualizada.", status_code=303)


@router.post("/missions/create")
async def create_mission_submit(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    form = await read_form_fields(request)
    try:
        create_admin_mission(db, form)
    except AdminMissionError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/edit_mission.html",
            context={
                "current_user": admin_user,
                "mission": None,
                "error": str(error),
                "form": form,
                "split_duration": split_duration_seconds,
            },
            status_code=400,
        )
    return RedirectResponse("/admin/missions?message=Missao criada.", status_code=303)


@router.get("/missions/{mission_template_id}/edit")
def edit_mission_form(
    mission_template_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    mission = get_admin_mission(db, mission_template_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Missao nao encontrada.")
    return templates.TemplateResponse(
        request=request,
        name="admin/edit_mission.html",
        context={
            "current_user": admin_user,
            "mission": mission,
            "error": None,
            "form": {},
            "split_duration": split_duration_seconds,
        },
    )


@router.post("/missions/{mission_template_id}/edit")
async def edit_mission_submit(
    mission_template_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    form = await read_form_fields(request)
    try:
        update_admin_mission(db=db, mission_template_id=mission_template_id, form=form)
    except AdminMissionError as error:
        mission = get_admin_mission(db, mission_template_id)
        return templates.TemplateResponse(
            request=request,
            name="admin/edit_mission.html",
            context={
                "current_user": admin_user,
                "mission": mission,
                "error": str(error),
                "form": form,
                "split_duration": split_duration_seconds,
            },
            status_code=400,
        )
    return RedirectResponse("/admin/missions?message=Missao atualizada.", status_code=303)


@router.get("/buildings")
def admin_buildings(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/buildings.html",
        context={
            "current_user": admin_user,
            "buildings": list_admin_building_templates(db),
            "get_effect_label": get_effect_label,
            "message": request.query_params.get("message"),
        },
    )


@router.get("/buildings/create")
def create_building_form(request: Request, current_user: User | None = Depends(get_current_user)):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/building_form.html",
        context={"current_user": admin_user, "building": None, "error": None, "form": {}},
    )


@router.post("/buildings/create")
async def create_building_submit(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    form = await read_form_fields(request)
    try:
        save_admin_building_template(db, form)
    except AdminBuildingError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/building_form.html",
            context={"current_user": admin_user, "building": None, "error": str(error), "form": form},
            status_code=400,
        )
    return RedirectResponse("/admin/buildings?message=Construcao criada.", status_code=303)


@router.get("/buildings/{building_template_id}/edit")
def edit_building_form(
    building_template_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    building = get_admin_building_template(db, building_template_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Construcao nao encontrada.")
    return templates.TemplateResponse(
        request=request,
        name="admin/building_form.html",
        context={"current_user": admin_user, "building": building, "error": None, "form": {}},
    )


@router.post("/buildings/{building_template_id}/edit")
async def edit_building_submit(
    building_template_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    building = get_admin_building_template(db, building_template_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Construcao nao encontrada.")
    form = await read_form_fields(request)
    try:
        save_admin_building_template(db, form, building)
    except AdminBuildingError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/building_form.html",
            context={"current_user": admin_user, "building": building, "error": str(error), "form": form},
            status_code=400,
        )
    return RedirectResponse("/admin/buildings?message=Construcao atualizada.", status_code=303)


@router.get("/dungeons")
def admin_dungeons(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/dungeons.html",
        context={
            "current_user": admin_user,
            "dungeons": list_admin_dungeons(db),
            "message": request.query_params.get("message"),
            "format_duration": format_duration_seconds,
        },
    )


@router.get("/dungeons/create")
def create_dungeon_form(request: Request, current_user: User | None = Depends(get_current_user)):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/dungeon_form.html",
        context={"current_user": admin_user, "dungeon": None, "error": None, "form": {}, "split_duration": split_duration_seconds},
    )


@router.post("/dungeons/create")
async def create_dungeon_submit(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    form = await read_form_fields(request)
    try:
        save_admin_dungeon(db, form)
    except AdminDungeonError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/dungeon_form.html",
            context={"current_user": admin_user, "dungeon": None, "error": str(error), "form": form, "split_duration": split_duration_seconds},
            status_code=400,
        )
    return RedirectResponse("/admin/dungeons?message=Masmorra criada.", status_code=303)


@router.get("/dungeons/{dungeon_template_id}/edit")
def edit_dungeon_form(
    dungeon_template_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    dungeon = get_admin_dungeon(db, dungeon_template_id)
    if dungeon is None:
        raise HTTPException(status_code=404, detail="Masmorra não encontrada.")
    return templates.TemplateResponse(
        request=request,
        name="admin/dungeon_form.html",
        context={"current_user": admin_user, "dungeon": dungeon, "error": None, "form": {}, "split_duration": split_duration_seconds},
    )


@router.post("/dungeons/{dungeon_template_id}/edit")
async def edit_dungeon_submit(
    dungeon_template_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    dungeon = get_admin_dungeon(db, dungeon_template_id)
    if dungeon is None:
        raise HTTPException(status_code=404, detail="Masmorra não encontrada.")
    form = await read_form_fields(request)
    try:
        save_admin_dungeon(db, form, dungeon)
    except AdminDungeonError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/dungeon_form.html",
            context={"current_user": admin_user, "dungeon": dungeon, "error": str(error), "form": form, "split_duration": split_duration_seconds},
            status_code=400,
        )
    return RedirectResponse("/admin/dungeons?message=Masmorra atualizada.", status_code=303)


@router.get("/items")
def admin_items(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    items = list_admin_items(db)
    for item in items:
        item.slot_label = get_equipment_slot_label(item.equipment_slot) if item.equipment_slot else "-"
    return templates.TemplateResponse(
        request=request,
        name="admin/items.html",
        context={
            "current_user": admin_user,
            "items": items,
            "message": request.query_params.get("message"),
            "get_equipment_slot_label": get_equipment_slot_label,
        },
    )


@router.get("/items/create")
def create_item_form(request: Request, current_user: User | None = Depends(get_current_user)):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/item_form.html",
        context={
            "current_user": admin_user,
            "item": None,
            "error": None,
            "form": {},
            "get_equipment_slot_label": get_equipment_slot_label,
        },
    )


@router.post("/items/create")
async def create_item_submit(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    form = await read_form_fields(request)
    try:
        save_admin_item(db, form)
    except AdminItemError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/item_form.html",
            context={
                "current_user": admin_user,
                "item": None,
                "error": str(error),
                "form": form,
                "get_equipment_slot_label": get_equipment_slot_label,
            },
            status_code=400,
        )
    return RedirectResponse("/admin/items?message=Item criado.", status_code=303)


@router.get("/items/{item_template_id}/edit")
def edit_item_form(
    item_template_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    item = get_admin_item(db, item_template_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item nao encontrado.")
    return templates.TemplateResponse(
        request=request,
        name="admin/item_form.html",
        context={
            "current_user": admin_user,
            "item": item,
            "error": None,
            "form": {},
            "get_equipment_slot_label": get_equipment_slot_label,
        },
    )


@router.post("/items/{item_template_id}/edit")
async def edit_item_submit(
    item_template_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    item = get_admin_item(db, item_template_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item nao encontrado.")
    form = await read_form_fields(request)
    try:
        save_admin_item(db, form, item)
    except AdminItemError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/item_form.html",
            context={
                "current_user": admin_user,
                "item": item,
                "error": str(error),
                "form": form,
                "get_equipment_slot_label": get_equipment_slot_label,
            },
            status_code=400,
        )
    return RedirectResponse("/admin/items?message=Item atualizado.", status_code=303)


@router.get("/mission-drops")
def admin_mission_drops(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/mission_drops.html",
        context={
            "current_user": admin_user,
            "drops": list_admin_drops(db),
            "message": request.query_params.get("message"),
        },
    )


@router.get("/mission-drops/create")
def create_drop_form(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/mission_drop_form.html",
        context={
            "current_user": admin_user,
            "drop": None,
            "missions": list_admin_missions(db),
            "items": list_active_admin_items(db),
            "error": None,
        },
    )


@router.post("/mission-drops/create")
async def create_drop_submit(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    form = await read_form_fields(request)
    try:
        save_admin_drop(db, form)
    except AdminDropError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/mission_drop_form.html",
            context={
                "current_user": admin_user,
                "drop": None,
                "missions": list_admin_missions(db),
                "items": list_active_admin_items(db),
                "error": str(error),
                "form": form,
            },
            status_code=400,
        )
    return RedirectResponse("/admin/mission-drops?message=Drop criado.", status_code=303)


@router.get("/mission-drops/{drop_id}/edit")
def edit_drop_form(
    drop_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    drop = get_admin_drop(db, drop_id)
    if drop is None:
        raise HTTPException(status_code=404, detail="Drop nao encontrado.")
    return templates.TemplateResponse(
        request=request,
        name="admin/mission_drop_form.html",
        context={
            "current_user": admin_user,
            "drop": drop,
            "missions": list_admin_missions(db),
            "items": list_active_admin_items(db),
            "error": None,
        },
    )


@router.post("/mission-drops/{drop_id}/edit")
async def edit_drop_submit(
    drop_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    drop = get_admin_drop(db, drop_id)
    if drop is None:
        raise HTTPException(status_code=404, detail="Drop nao encontrado.")
    form = await read_form_fields(request)
    try:
        save_admin_drop(db, form, drop)
    except AdminDropError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/mission_drop_form.html",
            context={
                "current_user": admin_user,
                "drop": drop,
                "missions": list_admin_missions(db),
                "items": list_active_admin_items(db),
                "error": str(error),
                "form": form,
            },
            status_code=400,
        )
    return RedirectResponse("/admin/mission-drops?message=Drop atualizado.", status_code=303)


@router.get("/dungeon-drops")
def admin_dungeon_drops(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/dungeon_drops.html",
        context={
            "current_user": admin_user,
            "drops": list_admin_dungeon_drops(db),
            "message": request.query_params.get("message"),
        },
    )


@router.get("/dungeon-drops/create")
def create_dungeon_drop_form(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    return templates.TemplateResponse(
        request=request,
        name="admin/dungeon_drop_form.html",
        context={
            "current_user": admin_user,
            "drop": None,
            "dungeons": list_admin_dungeons(db),
            "items": list_active_admin_items(db),
            "error": None,
            "form": {},
        },
    )


@router.post("/dungeon-drops/create")
async def create_dungeon_drop_submit(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    form = await read_form_fields(request)
    try:
        save_admin_dungeon_drop(db, form)
    except AdminDropError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/dungeon_drop_form.html",
            context={
                "current_user": admin_user,
                "drop": None,
                "dungeons": list_admin_dungeons(db),
                "items": list_active_admin_items(db),
                "error": str(error),
                "form": form,
            },
            status_code=400,
        )
    return RedirectResponse("/admin/dungeon-drops?message=Drop criado.", status_code=303)


@router.get("/dungeon-drops/{drop_id}/edit")
def edit_dungeon_drop_form(
    drop_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    drop = get_admin_dungeon_drop(db, drop_id)
    if drop is None:
        raise HTTPException(status_code=404, detail="Drop nao encontrado.")
    return templates.TemplateResponse(
        request=request,
        name="admin/dungeon_drop_form.html",
        context={
            "current_user": admin_user,
            "drop": drop,
            "dungeons": list_admin_dungeons(db),
            "items": list_active_admin_items(db),
            "error": None,
            "form": {},
        },
    )


@router.post("/dungeon-drops/{drop_id}/edit")
async def edit_dungeon_drop_submit(
    drop_id: int,
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
):
    admin_user = require_admin(current_user)
    if isinstance(admin_user, RedirectResponse):
        return admin_user
    drop = get_admin_dungeon_drop(db, drop_id)
    if drop is None:
        raise HTTPException(status_code=404, detail="Drop nao encontrado.")
    form = await read_form_fields(request)
    try:
        save_admin_dungeon_drop(db, form, drop)
    except AdminDropError as error:
        return templates.TemplateResponse(
            request=request,
            name="admin/dungeon_drop_form.html",
            context={
                "current_user": admin_user,
                "drop": drop,
                "dungeons": list_admin_dungeons(db),
                "items": list_active_admin_items(db),
                "error": str(error),
                "form": form,
            },
            status_code=400,
        )
    return RedirectResponse("/admin/dungeon-drops?message=Drop atualizado.", status_code=303)
