from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.crafting import CraftingRecipe, CraftingRecipeMaterial


def get_recipe_by_name(db: Session, name: str) -> CraftingRecipe | None:
    return db.scalar(select(CraftingRecipe).where(CraftingRecipe.name == name))


def get_active_recipe(db: Session, recipe_id: int) -> CraftingRecipe | None:
    return db.scalar(select(CraftingRecipe).options(
        joinedload(CraftingRecipe.output_item_template),
        joinedload(CraftingRecipe.materials).joinedload(CraftingRecipeMaterial.item_template),
    ).where(CraftingRecipe.id == recipe_id, CraftingRecipe.is_active.is_(True)))


def list_active_recipes(db: Session) -> list[CraftingRecipe]:
    return list(db.scalars(select(CraftingRecipe).options(
        joinedload(CraftingRecipe.output_item_template),
        joinedload(CraftingRecipe.materials).joinedload(CraftingRecipeMaterial.item_template),
    ).where(CraftingRecipe.is_active.is_(True)).order_by(CraftingRecipe.required_blacksmith_level, CraftingRecipe.id)).unique())


def create_recipe(db: Session, data: dict[str, object]) -> CraftingRecipe:
    recipe = CraftingRecipe(**data)
    db.add(recipe)
    return recipe
