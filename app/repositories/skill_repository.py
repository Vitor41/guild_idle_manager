from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.skill import MercenarySkill, SkillTemplate


def get_skill_template_by_class_and_name(db: Session, class_id: int, name: str) -> SkillTemplate | None:
    return db.scalar(select(SkillTemplate).where(SkillTemplate.class_id == class_id, SkillTemplate.name == name))


def create_skill_template(db: Session, data: dict[str, object]) -> SkillTemplate:
    skill = SkillTemplate(**data)
    db.add(skill)
    return skill


def list_active_skills_for_class(db: Session, class_id: int) -> list[SkillTemplate]:
    return list(db.scalars(select(SkillTemplate).where(
        SkillTemplate.class_id == class_id, SkillTemplate.is_active.is_(True)
    ).order_by(SkillTemplate.id)))


def get_mercenary_skill(db: Session, mercenary_id: int, skill_template_id: int) -> MercenarySkill | None:
    return db.scalar(select(MercenarySkill).where(
        MercenarySkill.mercenary_id == mercenary_id,
        MercenarySkill.skill_template_id == skill_template_id,
    ))


def list_mercenary_skills(db: Session, mercenary_id: int) -> list[MercenarySkill]:
    return list(db.scalars(select(MercenarySkill).options(joinedload(MercenarySkill.skill_template)).where(
        MercenarySkill.mercenary_id == mercenary_id
    ).order_by(MercenarySkill.id)))
