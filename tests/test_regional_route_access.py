import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database.connection import create_database_engine
from app.models import Base, CampaignMetadata, Guild, RegionalEvent, RegionalEventParticipant, RegionalGuildState, User
from app.routes.regional_routes import (
    _portal_action_blocker,
    _regional_offer_rebellion_access,
    _validated_regional_return_to,
)
from app.services.regional_cycle_service import REGIONS


class RegionalRouteAccessTests(unittest.TestCase):
    def test_home_rebellion_credit_requires_acceptance_and_does_not_unlock_external_portal(self):
        engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            now = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
            campaign_id = str(uuid4())
            home_code, home_name = REGIONS[0]
            external_code, _external_name = next(row for row in REGIONS if row[0] != home_code)
            with Session(engine) as db:
                campaign = CampaignMetadata(
                    campaign_id=campaign_id,
                    campaign_name="Route access",
                    home_region=home_name,
                    created_at_utc=now - timedelta(days=1),
                )
                user = User(username="regional-route-access", password_hash="test")
                db.add_all([campaign, user])
                db.flush()
                guild = Guild(campaign_id=campaign_id, user_id=user.id, name="Route access")
                db.add(guild)
                db.flush()
                player_state = RegionalGuildState(
                    campaign_id=campaign_id,
                    region_code=home_code,
                    slot=0,
                    guild_id=guild.id,
                    name="Route access",
                    profile="player",
                    archetype="player",
                )
                db.add(player_state)
                db.flush()
                home_offer = SimpleNamespace(region_code=home_code, offer_type="contract")
                external_offer = SimpleNamespace(region_code=external_code, offer_type="contract")
                internal_offer = SimpleNamespace(region_code=home_code, offer_type="cpu_internal")

                access_event, reason = _regional_offer_rebellion_access(
                    db, campaign, guild.id, internal_offer, now,
                )
                self.assertIsNone(access_event)
                self.assertEqual(reason, "Oferta indisponível.")

                access_event, reason = _regional_offer_rebellion_access(
                    db, campaign, guild.id, home_offer, now,
                )
                self.assertIsNone(access_event)
                self.assertIsNone(reason)

                event = RegionalEvent(
                    campaign_id=campaign_id,
                    event_type="rebellion",
                    region_code=home_code,
                    trigger_cycle_number=1,
                    rules_version="regional-events-v4",
                    seed="route-access-rebellion",
                    status="active",
                    created_at_utc=now,
                    priority_ends_at_utc=now + timedelta(hours=1),
                    expires_at_utc=now + timedelta(hours=13),
                    summary_json="{}",
                )
                db.add(event)
                db.flush()
                participant = RegionalEventParticipant(
                    event_id=event.id,
                    guild_state_id=player_state.id,
                    status="invited",
                )
                db.add(participant)
                db.flush()

                # Home activities remain usable while the invitation is pending,
                # but they do not receive rebellion credit until it is accepted.
                access_event, reason = _regional_offer_rebellion_access(
                    db, campaign, guild.id, home_offer, now,
                )
                self.assertIsNone(access_event)
                self.assertIsNone(reason)

                participant.status = "accepted"
                event.player_decision = "accept"
                access_event, reason = _regional_offer_rebellion_access(
                    db, campaign, guild.id, home_offer, now,
                )
                self.assertIs(access_event, event)
                self.assertIsNone(reason)

                # An accepted rebellion grants its own regional activities,
                # never entry into a portal outside the guild's home region.
                event.region_code = external_code
                access_event, reason = _regional_offer_rebellion_access(
                    db, campaign, guild.id, external_offer, now,
                )
                self.assertIs(access_event, event)
                self.assertIsNone(reason)
                external_portal = SimpleNamespace(
                    campaign_id=campaign_id,
                    event_type="portal",
                    region_code=external_code,
                    id=999,
                    status="active",
                    expires_at_utc=now + timedelta(hours=3),
                    dungeon_template_id=1,
                )
                blocker = _portal_action_blocker(db, campaign, external_portal, player_state, now)
                self.assertIn("Portais só aceitam entrada na região natal", blocker)
                self.assertNotIn("rebelião aceita", blocker.lower())
        finally:
            engine.dispose()

    def test_event_return_to_allows_only_local_sections_and_event_anchors(self):
        self.assertEqual(
            _validated_regional_return_to({
                "return_to": ["/regional/events?section=rebellions#regional-event-42"],
            }),
            "/regional/events?section=rebellions#regional-event-42",
        )
        self.assertEqual(
            _validated_regional_return_to(
                {"return_to": ["https://example.invalid/phishing"]},
                fallback_anchor="#regional-event-42",
            ),
            "/regional#regional-event-42",
        )
        self.assertEqual(
            _validated_regional_return_to({"return_to": ["//example.invalid/path"]}),
            "/regional",
        )
        self.assertEqual(
            _validated_regional_return_to({
                "return_to": ["/regional/events?section=anything#regional-event-42"],
            }),
            "/regional",
        )


if __name__ == "__main__":
    unittest.main()
