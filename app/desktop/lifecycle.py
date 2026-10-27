"""Campaign lifecycle orchestration shared by the launcher and HTTP routes."""

from app.desktop.clock_guard import ClockGuard
from app.services.campaign_service import CampaignService


def open_campaign(app, campaigns: CampaignService, clock_guard: ClockGuard, campaign_id: str):
    info, summary, _migration = open_campaign_with_migration(app, campaigns, clock_guard, campaign_id)
    return info, summary


def open_campaign_with_migration(app, campaigns: CampaignService, clock_guard: ClockGuard, campaign_id: str):
    active = getattr(app.state, "active_campaign", None)
    if active is not None and active.campaign_id != campaign_id:
        raise ValueError("Retorne ao menu de campanhas e feche a campanha atual antes de abrir outra.")
    if active is not None:
        return campaigns.inspect_campaign(campaign_id), None, None
    info, migration = campaigns.activate_campaign_with_migration(campaign_id, mark_active=False)
    summary = clock_guard.activate_campaign(info.campaign_id)
    info = campaigns.inspect_campaign(info.campaign_id)
    app.state.active_campaign = info
    getattr(app.state, "suspended_campaigns", set()).discard(info.campaign_id)
    return info, summary, migration


def close_campaign(app, campaigns: CampaignService, clock_guard: ClockGuard) -> None:
    info = getattr(app.state, "active_campaign", None)
    if info is None:
        return
    clock_guard.close_campaign(info.campaign_id, campaigns)
    app.state.active_campaign = None
    getattr(app.state, "suspended_campaigns", set()).discard(info.campaign_id)


def suspend_campaign(app, campaigns: CampaignService, clock_guard: ClockGuard) -> None:
    info = getattr(app.state, "active_campaign", None)
    if info is None:
        return
    clock_guard.suspend_campaign(info.campaign_id)
    campaigns.suspend_active_campaign(info.campaign_id)
    app.state.active_campaign = None
    suspended = getattr(app.state, "suspended_campaigns", set())
    suspended.add(info.campaign_id)
    app.state.suspended_campaigns = suspended


def close_suspended_campaigns(app, campaigns: CampaignService, clock_guard: ClockGuard) -> None:
    for campaign_id in list(getattr(app.state, "suspended_campaigns", set())):
        clock_guard.mark_process_shutdown(campaign_id, campaigns)
        app.state.suspended_campaigns.discard(campaign_id)
