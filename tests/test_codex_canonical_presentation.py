import re
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import event, select
from sqlalchemy.orm import sessionmaker

from app.database.connection import create_database_engine
from app.models.achievement import AchievementTemplate, CodexEntry
from app.models.guild import Guild
from app.models.item import ItemTemplate
from app.services.achievement_service import get_codex_context
from app.services.campaign_service import CampaignService
from app.services.display_service import canonical_generated_equipment_description, rarity_label
from app.seeds.massive_content import PACK_KEY


_GENERATED_EQUIPMENT_DESCRIPTION = re.compile(
    r"Equipamento (comum|incomum|raro|épico|lendário|mítico) indicado para progressão "
    r"entre os níveis (\d+) e (\d+)\."
)


class CodexCanonicalPresentationTests(unittest.TestCase):
    def test_shared_equipment_description_helper_only_updates_the_exact_generated_sentence(self):
        self.assertEqual(
            canonical_generated_equipment_description(
                "Equipamento comum indicado para progressão entre os níveis 20 e 39.",
                "rare",
                "20-39",
            ),
            "Equipamento raro indicado para progressão entre os níveis 20 e 39.",
        )
        custom_lore = "Relato antigo da expedição: a relíquia cantava sob a chuva."
        self.assertEqual(
            canonical_generated_equipment_description(custom_lore, "rare", "20-39"),
            custom_lore,
        )
        mismatch = "Equipamento comum indicado para progressão entre os níveis 1 e 19."
        self.assertEqual(
            canonical_generated_equipment_description(mismatch, "rare", "20-39"),
            mismatch,
        )

    def test_item_details_follow_current_template_without_writing_saved_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaigns = CampaignService(Path(temp_dir) / "saves")
            campaign = campaigns.create_campaign("Códex descartável", "Guilda do Códex")
            engine = create_database_engine(f"sqlite:///{campaign.database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            try:
                with factory() as db:
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign.campaign_id))
                    items = list(db.scalars(select(ItemTemplate).where(
                        ItemTemplate.content_pack == PACK_KEY,
                        ItemTemplate.item_type == "equipment",
                        ItemTemplate.slug.like("equipamento_%"),
                    ).order_by(ItemTemplate.id)))
                    entries = {
                        int(entry.reference_key): entry
                        for entry in db.scalars(select(CodexEntry).where(CodexEntry.category == "item"))
                        if entry.reference_key.isdigit()
                    }
                    reward_ids = set(db.scalars(select(AchievementTemplate.reward_item_template_id).where(
                        AchievementTemplate.reward_item_template_id.is_not(None),
                    )))

                    mismatch = None
                    for item in items:
                        entry = entries.get(item.id)
                        if entry is None or item.id in reward_ids:
                            continue
                        description_match = _GENERATED_EQUIPMENT_DESCRIPTION.fullmatch(entry.description or "")
                        band_match = re.fullmatch(r"(\d+)-(\d+)", item.level_band or "")
                        if (
                            description_match is not None
                            and band_match is not None
                            and description_match.group(1) == "comum"
                            and description_match.groups()[1:] == band_match.groups()
                            and item.rarity == "rare"
                        ):
                            mismatch = (item, entry)
                            break
                    self.assertIsNotNone(mismatch, "a campanha deve reproduzir a descrição comum com raridade rara")
                    item, generated_entry = mismatch
                    saved_generated = (generated_entry.description, generated_entry.rarity)
                    saved_item = (item.description, item.rarity)

                    custom_item = next(
                        candidate for candidate in items
                        if candidate.id in entries and candidate.id not in reward_ids and candidate.id != item.id
                    )
                    custom_entry = entries[custom_item.id]
                    custom_entry.description = "Relato antigo da expedição: a relíquia cantava sob a chuva."
                    custom_description = custom_entry.description
                    custom_rarity = custom_entry.rarity

                    missing_entry = CodexEntry(
                        key="item:900000000",
                        category="item",
                        reference_key="900000000",
                        title="Referência sem modelo",
                        description="Registro preservado sem modelo vinculado.",
                        rarity="epic",
                    )
                    db.add(missing_entry)
                    db.commit()
                    missing_id = missing_entry.id

                    writes_to_saved_content = []

                    def track_saved_content_writes(_conn, _cursor, statement, _params, _context, _many):
                        normalized = statement.lstrip().lower()
                        if normalized.startswith("update ") and (
                            "codex_entries" in normalized or "item_templates" in normalized
                        ):
                            writes_to_saved_content.append(statement)

                    event.listen(engine, "before_cursor_execute", track_saved_content_writes)
                    try:
                        context = get_codex_context(db, guild, unlocked_only=False, category="item")
                    finally:
                        event.remove(engine, "before_cursor_execute", track_saved_content_writes)

                    displayed = {entry.id: entry for entry in context["codex_entries"]}
                    generated_view = displayed[generated_entry.id]
                    expected_description = (
                        f"Equipamento {rarity_label(item.rarity).lower()} indicado para progressão "
                        f"entre os níveis {item.level_band.replace('-', ' e ')}."
                    )
                    self.assertEqual(generated_view.rarity, "rare")
                    self.assertEqual(generated_view.description, expected_description)
                    self.assertEqual(displayed[custom_entry.id].description, custom_description)
                    self.assertEqual(displayed[missing_id].rarity, "epic")
                    self.assertEqual(
                        displayed[missing_id].description,
                        "Registro preservado sem modelo vinculado.",
                    )
                    self.assertIsNone(displayed[missing_id].icon_path)
                    self.assertFalse(writes_to_saved_content)

                with factory() as verify_db:
                    persisted_item = verify_db.get(ItemTemplate, item.id)
                    persisted_generated = verify_db.get(CodexEntry, generated_entry.id)
                    persisted_custom = verify_db.get(CodexEntry, custom_entry.id)
                    self.assertEqual((persisted_item.description, persisted_item.rarity), saved_item)
                    self.assertEqual(
                        (persisted_generated.description, persisted_generated.rarity),
                        saved_generated,
                    )
                    self.assertEqual(persisted_custom.description, custom_description)
                    self.assertEqual(persisted_custom.rarity, custom_rarity)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
