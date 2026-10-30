"""One-time initial content pack for newly created offline campaigns."""

from sqlalchemy.orm import Session

from app.seeds import run_massive_content_seed
from app.services.achievement_service import seed_achievements_and_codex
from app.services.building_service import seed_initial_building_templates
from app.services.class_service import seed_class_tree
from app.services.crafting_service import seed_crafting_recipes
from app.services.dungeon_service import (
    apply_introductory_boss_access_rule,
    seed_initial_dungeon_drops,
    seed_initial_dungeon_templates,
)
from app.services.item_service import seed_initial_items, seed_initial_mission_drops
from app.services.mercenary_service import cleanup_orphaned_dismissed_mercenaries, seed_initial_mercenary_classes
from app.services.mission_service import repair_long_idle_mission_catalog, seed_initial_mission_templates, seed_long_idle_missions
from app.services.prd2_balance_service import apply_prd2_balance
from app.services.prd3_dungeon_balance_service import (
    apply_dungeon_explorer_unlock_fix,
    apply_prd3_dungeon_balance,
)
from app.services.skill_service import seed_class_skills
from app.services.tavern_service import seed_tavern_config
from app.services.content_refinement_service import run_progression_refinement


def apply_initial_campaign_content(db: Session) -> None:
    """Apply the existing web game's initial catalogs and balance once to a fresh save."""
    seed_initial_mercenary_classes(db)
    seed_class_tree(db)
    seed_initial_mission_templates(db)
    seed_initial_building_templates(db)
    seed_tavern_config(db)
    seed_initial_items(db)
    seed_initial_mission_drops(db)
    seed_initial_dungeon_templates(db)
    seed_initial_dungeon_drops(db)
    seed_class_skills(db)
    run_massive_content_seed(db, deactivate_legacy_defaults=True)
    run_progression_refinement(db)
    seed_long_idle_missions(db)
    apply_prd2_balance(db)
    repair_long_idle_mission_catalog(db)
    apply_prd3_dungeon_balance(db)
    apply_dungeon_explorer_unlock_fix(db)
    apply_introductory_boss_access_rule(db)
    seed_crafting_recipes(db)
    seed_achievements_and_codex(db)
    cleanup_orphaned_dismissed_mercenaries(db)
