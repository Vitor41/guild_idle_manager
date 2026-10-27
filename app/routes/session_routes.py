import json

from fastapi import APIRouter, Depends, Request, Response

from app.core.dependencies import get_current_user
from app.models.user import User
from app.core.dependencies import DbSession
from app.core.forms import read_form_fields
from app.models.campaign import CampaignMetadata


router = APIRouter(prefix="/session")


@router.post("/heartbeat", status_code=204)
def heartbeat(current_user: User | None = Depends(get_current_user)) -> Response:
    if current_user is None:
        return Response(status_code=401)
    return Response(status_code=204)


@router.post("/confirmation-preferences", status_code=204)
async def confirmation_preference(
    request: Request,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
) -> Response:
    if current_user is None:
        return Response(status_code=401)
    form = await read_form_fields(request)
    key = str(form.get("key", "")).strip()[:80]
    if not key or not all(character.isalnum() or character in {"_", "-"} for character in key):
        return Response(status_code=400)
    try:
        preferences = json.loads(current_user.confirmation_preferences or "{}")
    except (TypeError, json.JSONDecodeError):
        preferences = {}
    preferences[key] = False
    serialized = json.dumps(preferences, separators=(",", ":"))
    if isinstance(current_user.id, str):
        campaign = db.get(CampaignMetadata, current_user.id)
        if campaign is None:
            return Response(status_code=404)
        campaign.confirmation_preferences = serialized
    else:
        current_user.confirmation_preferences = serialized
        db.add(current_user)
    db.commit()
    return Response(status_code=204)
