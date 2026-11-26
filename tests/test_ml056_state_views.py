import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database.connection import create_database_engine
from app.models.guild import Guild
from app.models.mercenary import Mercenary, MercenaryClass
from app.services.campaign_service import CampaignService
from app.services.display_service import status_label
from app.services.profession_service import get_professions_context


ROOT = Path(__file__).resolve().parents[1]


class Ml056StateViewTests(unittest.TestCase):
    def test_building_upgrade_and_reset_keep_progress_cost_and_provenance_states_distinct(self):
        buildings = (ROOT / "app/templates/buildings/index.html").read_text(encoding="utf-8")
        css = (ROOT / "app/static/css/main.css").read_text(encoding="utf-8")

        self.assertIn('class="building-facts"', buildings)
        self.assertIn("Próximo requisito", buildings)
        self.assertIn("Custo para evoluir", buildings)
        self.assertIn("building.level >= building.building_template.max_level", buildings)
        self.assertIn("Não há próxima evolução.", buildings)
        self.assertIn("Saldo indisponível", buildings)
        self.assertNotIn("cost.gold }} ouro, {{ cost.wood", buildings)
        self.assertIn("Benefício atual", buildings)
        self.assertIn("Próximo marco:", buildings)
        self.assertIn('<details class="building-reset-provenance">', buildings)
        self.assertIn("Capacidade após o reset", buildings)
        self.assertIn("Pendências que bloqueiam o reset", buildings)
        self.assertIn(".building-costs dd small.is-short", css)

    def test_class_requirements_show_pending_first_and_preserve_complete_matrix(self):
        class_template = (ROOT / "app/templates/class_change/index.html").read_text(encoding="utf-8")
        self.assertIn("class-requirement-checks--missing", class_template)
        self.assertIn("{% for check in step.checks if not check.met %}", class_template)
        self.assertIn("Ver matriz completa · {{ step.checks|length }} requisitos", class_template)
        self.assertIn("check.missing", class_template)

    def test_professions_context_and_view_use_real_family_icons_cost_duration_and_worker_status(self):
        template = (ROOT / "app/templates/professions/index.html").read_text(encoding="utf-8")
        self.assertIn('data-desktop-item-family="{{ profession.material_family }}"', template)
        self.assertIn("profession.family_label", template)
        self.assertIn("mercenary.status_label", template)
        self.assertIn("profession.training_gold_cost", template)
        self.assertIn("profession.training_duration_seconds", template)
        self.assertNotIn('class="tag">Chance do material principal', template)

        with tempfile.TemporaryDirectory() as temp_dir:
            campaign = CampaignService(Path(temp_dir) / "campaigns").create_campaign(
                "Profissões ML-056", "Guilda das Profissões",
            )
            engine = create_database_engine(f"sqlite:///{campaign.database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            try:
                with factory() as db:
                    guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign.campaign_id))
                    mercenary_class = db.scalar(select(MercenaryClass).order_by(MercenaryClass.id))
                    if mercenary_class is None:
                        mercenary_class = MercenaryClass(
                            name="Classe de teste", code="ml056_test", description="Fixture de teste",
                            base_power=10, base_vitality=10, base_agility=10,
                            base_intelligence=10, base_luck=10,
                        )
                        db.add(mercenary_class)
                        db.flush()
                    db.add(Mercenary(
                        guild_id=guild.id, class_id=mercenary_class.id, name="Trabalhador de teste",
                        level=1, xp=0, status="available", rarity="common", hire_cost=0,
                        power=10, vitality=10, agility=10, intelligence=10, luck=10,
                    ))
                    db.flush()
                    context = get_professions_context(db, guild)
                    self.assertTrue(context["professions"])
                    self.assertTrue(all(profession.material_family for profession in context["professions"]))
                    self.assertTrue(all(profession.family_label for profession in context["professions"]))
                    self.assertTrue(context["mercenaries"])
                    self.assertTrue(all(
                        worker.status_label == status_label(worker.status)
                        for worker in context["mercenaries"]
                    ))
            finally:
                engine.dispose()

    def test_codex_has_one_discovery_count_and_one_state_per_claimable_card(self):
        template = (ROOT / "app/templates/codex/index.html").read_text(encoding="utf-8")
        collection = template.split('id="codex-collection"', 1)[1].split("</section>", 1)[0]
        achievement = template.split('id="codex-achievements"', 1)[1].split('id="codex-legendary"', 1)[0]
        self.assertEqual(template.count('class="codex-discovery-count"'), 1)
        self.assertNotIn("codex-collection-count", template)
        self.assertNotIn("ÍNDICE VISUAL FUNCIONAL", template)
        self.assertIn('aria-valuenow="{{ achievement.progress }}"', achievement)
        self.assertEqual(achievement.count('class="codex-achievement-state"'), 1)
        self.assertNotIn("Estado:", achievement)
        self.assertNotIn("Recompensa entregue", template)
        self.assertIn("category={{ selected_category }}&amp;trail={{ selected_trail }}#codex-entry-{{ selected_codex_entry.id }}", collection)
        self.assertIn('href="/codex?category={{ selected_category }}&amp;trail={{ selected_trail }}&amp;entry={{ entry.id }}#codex-entry-detail"', template)
        self.assertIn('href="/codex?category={{ selected_category }}&amp;trail={{ selected_trail }}#codex-entry-{{ selected_codex_entry.id }}"', template)
        self.assertIn("/codex/achievements/{{ achievement.id }}/claim", achievement)

    def test_final_codex_targets_building_profession_focus_and_profession_eyebrow(self):
        theme = (ROOT / "app/static/css/desktop-theme.css").read_text(encoding="utf-8")

        codex_targets = theme.split(
            'body[data-app-mode="desktop"] .codex-entry-detail .section-heading > a {',
            1,
        )[1].split("}", 1)[0]
        self.assertIn("display: inline-flex", codex_targets)
        self.assertIn("min-width: 40px", codex_targets)
        self.assertIn("min-height: 40px", codex_targets)
        self.assertIn('body[data-app-mode="desktop"] .achievement-card details > summary {', theme)
        self.assertIn("body[data-app-mode=\"desktop\"] .achievement-card details > summary:focus-visible", theme)
        self.assertIn("body[data-app-mode=\"desktop\"] .codex-card a:focus-visible", theme)
        self.assertIn("outline: 3px solid var(--gold-2);", theme)
        self.assertIn("outline-offset: 3px;", theme)
        self.assertIn('body[data-app-mode="desktop"] .building-card button:focus-visible', theme)
        self.assertIn('body[data-app-mode="desktop"] form[action="/professions/train"] button:focus-visible', theme)
        self.assertIn('body[data-app-mode="desktop"] .profession-card .eyebrow { letter-spacing: 0; }', theme)


if __name__ == "__main__":
    unittest.main()
