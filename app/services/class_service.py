from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mercenary import MercenaryClass
from app.repositories.class_change_repository import create_transition, get_transition_by_classes
from app.repositories.mercenary_repository import (
    create_mercenary_class,
    get_mercenary_class_by_code,
    get_mercenary_class_by_name,
)
from app.services.balance_service import CLASS_PRIMARY_ATTRIBUTES, CLASS_SUCCESS_BONUS, ROLE_DESCRIPTIONS
from app.services.display_service import ATTRIBUTE_LABELS, class_label
from app.services.icon_service import get_class_icon_path
from app.repositories.skill_repository import list_active_skills_for_class
from app.services.skill_service import effect_label, effect_suffix


WEAPON_PROFILE_LABELS = {
    "any": "Uso geral", "melee": "Espadas, machados, martelos e lanças",
    "light": "Adagas, espadas leves e rapieiras", "arcane": "Cajados, varinhas, grimórios e orbes",
    "holy": "Maças, cetros, livros sagrados e escudos", "ranged": "Arcos, bestas e armas de distância",
    "dual": "Armas leves em ambas as mãos", "bow": "Arcos e bestas", "staff": "Cajados",
}

CLASS_WEAPON_LABELS = {
    **{code: "Espadas, machados, martelos, lanças e armaduras pesadas" for code in ("warrior", "knight", "templar")},
    **{code: "Espadas leves, adagas e duas armas" for code in ("blade", "reaper", "rogue", "assassin", "ninja", "predator", "shinobi")},
    **{code: "Cajados, varinhas, grimórios, orbes e vestes" for code in ("mage", "wizard", "mentalist", "arcane", "warlock")},
    **{code: "Maças, cetros, livros sagrados, escudos e malhas" for code in ("cleric", "priest", "paladin", "high_priest", "sentinel")},
    **{code: "Arcos, bestas, lanças leves e armaduras leves" for code in ("archer", "ranger", "shooter", "patroller", "renegade")},
}


def get_weapon_profile_label(mercenary_class: MercenaryClass) -> str:
    return CLASS_WEAPON_LABELS.get(mercenary_class.code or "", WEAPON_PROFILE_LABELS.get(
        mercenary_class.allowed_weapon_profile, "Equipamentos compatíveis com a função"
    ))


CLASS_TREE = [
    {
        "code": "apprentice",
        "name": "Aprendiz",
        "description": "Recruta em treinamento, com potencial definido pela Taverna.",
        "tier": 0,
        "parent": None,
        "required_level": 1,
        "role_type": "balanced",
        "allowed_weapon_profile": "any",
        "base_power": 4,
        "base_vitality": 4,
        "base_agility": 4,
        "base_intelligence": 4,
        "base_luck": 4,
    },
    {
        "code": "warrior",
        "name": "Guerreiro",
        "description": "Combatente resistente para a linha de frente.",
        "tier": 1,
        "parent": "apprentice",
        "required_level": 20,
        "role_type": "frontline",
        "allowed_weapon_profile": "melee",
        "base_power": 8,
        "base_vitality": 8,
        "base_agility": 4,
        "base_intelligence": 2,
        "base_luck": 3,
    },
    {
        "code": "rogue",
        "name": "Ladino",
        "description": "Especialista em infiltração que combina agilidade, técnica e inteligência.",
        "tier": 1,
        "parent": "apprentice",
        "required_level": 20,
        "role_type": "skirmisher",
        "allowed_weapon_profile": "light",
        "base_power": 5,
        "base_vitality": 4,
        "base_agility": 9,
        "base_intelligence": 7,
        "base_luck": 3,
    },
    {
        "code": "mage",
        "name": "Mago",
        "description": "Conjurador de alto intelecto e poder arcano.",
        "tier": 1,
        "parent": "apprentice",
        "required_level": 20,
        "role_type": "caster",
        "allowed_weapon_profile": "arcane",
        "base_power": 7,
        "base_vitality": 3,
        "base_agility": 3,
        "base_intelligence": 9,
        "base_luck": 4,
    },
    {
        "code": "cleric",
        "name": "Clerigo",
        "description": "Devoto equilibrado com foco em suporte e sabedoria.",
        "tier": 1,
        "parent": "apprentice",
        "required_level": 20,
        "role_type": "support",
        "allowed_weapon_profile": "holy",
        "base_power": 4,
        "base_vitality": 5,
        "base_agility": 3,
        "base_intelligence": 8,
        "base_luck": 5,
    },
    {
        "code": "archer",
        "name": "Arqueiro",
        "description": "Atirador agil com bom alcance e precisao.",
        "tier": 1,
        "parent": "apprentice",
        "required_level": 20,
        "role_type": "ranged",
        "allowed_weapon_profile": "ranged",
        "base_power": 6,
        "base_vitality": 4,
        "base_agility": 8,
        "base_intelligence": 3,
        "base_luck": 4,
    },
    {"code": "knight", "name": "Cavaleiro", "parent": "warrior", "tier": 2, "role_type": "tank"},
    {"code": "blade", "name": "Duelista", "parent": "warrior", "tier": 2, "role_type": "duelist"},
    {"code": "templar", "name": "Templario", "parent": "knight", "tier": 3, "role_type": "tank"},
    {"code": "reaper", "name": "Retalhador", "parent": "blade", "tier": 3, "role_type": "duelist"},
    {"code": "assassin", "name": "Assassino", "parent": "rogue", "tier": 2, "role_type": "skirmisher"},
    {"code": "ninja", "name": "Ninja", "parent": "rogue", "tier": 2, "role_type": "skirmisher"},
    {"code": "predator", "name": "Predador", "parent": "assassin", "tier": 3, "role_type": "skirmisher"},
    {"code": "shinobi", "name": "Shinobi", "parent": "ninja", "tier": 3, "role_type": "skirmisher"},
    {"code": "wizard", "name": "Sabio", "parent": "mage", "tier": 2, "role_type": "caster"},
    {"code": "mentalist", "name": "Mentalista", "parent": "mage", "tier": 2, "role_type": "caster"},
    {"code": "arcane", "name": "Arcano", "parent": "wizard", "tier": 3, "role_type": "caster"},
    {"code": "warlock", "name": "Bruxo", "parent": "mentalist", "tier": 3, "role_type": "caster"},
    {"code": "priest", "name": "Padre", "parent": "cleric", "tier": 2, "role_type": "support"},
    {"code": "paladin", "name": "Paladino", "parent": "cleric", "tier": 2, "role_type": "frontline"},
    {"code": "high_priest", "name": "Sacerdote", "parent": "priest", "tier": 3, "role_type": "support"},
    {"code": "sentinel", "name": "Sentinela", "parent": "paladin", "tier": 3, "role_type": "frontline"},
    {"code": "ranger", "name": "Ranger", "parent": "archer", "tier": 2, "role_type": "ranged"},
    {"code": "shooter", "name": "Pistoleiro", "parent": "archer", "tier": 2, "role_type": "ranged"},
    {"code": "patroller", "name": "Patrulheiro", "parent": "ranger", "tier": 3, "role_type": "ranged"},
    {"code": "renegade", "name": "Renegado", "parent": "shooter", "tier": 3, "role_type": "ranged"},
]


def _with_defaults(data: dict[str, object]) -> dict[str, object]:
    parent_code = str(data.get("parent") or "")
    tier = int(data["tier"])
    base = {
        "description": f"Classe de evolucao: {data['name']}.",
        "required_level": 20 if tier == 1 else 100 if tier == 2 else 350,
        "allowed_weapon_profile": "any",
        "base_power": 6 + tier * 2,
        "base_vitality": 5 + tier * 2,
        "base_agility": 5 + tier * 2,
        "base_intelligence": 5 + tier * 2,
        "base_luck": 4 + tier,
        "role_type": "balanced",
        "is_active": True,
    }
    base.update(data)
    base["display_name"] = base["name"]
    base.pop("parent", None)
    if parent_code:
        base["parent_code"] = parent_code
    return base


def seed_class_tree(db: Session) -> None:
    changed = False
    for raw_data in CLASS_TREE:
        data = _with_defaults(raw_data)
        code = str(data.pop("code"))
        parent_code = data.pop("parent_code", None)
        mercenary_class = get_mercenary_class_by_code(db, code) or get_mercenary_class_by_name(db, str(data["name"]))
        if mercenary_class is None:
            mercenary_class = create_mercenary_class(db, {"code": code, **data})
            changed = True
        elif mercenary_class.code is None:
            mercenary_class.code = code
            mercenary_class.display_name = str(data["display_name"])
            mercenary_class.tier = int(data["tier"])
            mercenary_class.required_level = int(data["required_level"])
            mercenary_class.allowed_weapon_profile = str(data["allowed_weapon_profile"])
            mercenary_class.role_type = str(data["role_type"])
            changed = True
        if parent_code:
            parent = get_mercenary_class_by_code(db, str(parent_code))
            if parent is not None and mercenary_class.parent_class_id is None:
                mercenary_class.parent_class_id = parent.id
                changed = True

    if changed:
        db.commit()
    changed = False
    for mercenary_class in db.scalars(select(MercenaryClass).where(MercenaryClass.parent_class_id.is_not(None))):
        parent = db.get(MercenaryClass, mercenary_class.parent_class_id)
        if parent is None:
            continue
        requirement = get_transition_requirements(mercenary_class.tier)
        existing_transition = get_transition_by_classes(db, parent.id, mercenary_class.id)
        if existing_transition:
            if existing_transition.required_training_ground_level != requirement["required_training_ground_level"]:
                existing_transition.required_training_ground_level = requirement["required_training_ground_level"]
                changed = True
            continue
        create_transition(
            db,
            {
                "from_class_id": parent.id,
                "to_class_id": mercenary_class.id,
                **requirement,
                "is_active": True,
            },
        )
        changed = True

    if changed:
        db.commit()


def refine_class_catalog(db: Session) -> int:
    changed = 0
    for raw_data in CLASS_TREE:
        data = _with_defaults(raw_data)
        mercenary_class = get_mercenary_class_by_code(db, str(raw_data["code"]))
        if mercenary_class is None:
            continue
        for field in (
            "description", "role_type", "allowed_weapon_profile",
            "base_power", "base_vitality", "base_agility", "base_intelligence", "base_luck",
        ):
            setattr(mercenary_class, field, data[field])
        changed += 1
    return changed


def get_transition_requirements(target_tier: int) -> dict[str, int]:
    if target_tier <= 1:
        return {
            "required_mercenary_level": 20,
            "required_guild_level": 5,
            "required_training_ground_level": 10,
            "gold_cost": 1000,
            "duration_seconds": 86400,
        }
    if target_tier == 2:
        return {
            "required_mercenary_level": 100,
            "required_guild_level": 15,
            "required_training_ground_level": 25,
            "gold_cost": 5000,
            "duration_seconds": 86400,
        }
    return {
        "required_mercenary_level": 350,
        "required_guild_level": 50,
        "required_training_ground_level": 50,
        "gold_cost": 10000,
        "duration_seconds": 86400,
    }


def get_class_display_name(mercenary_class: MercenaryClass | None) -> str:
    return class_label(mercenary_class)


def get_class_guide_context(db: Session) -> dict[str, object]:
    classes = list(
        db.scalars(
            select(MercenaryClass)
            .where(MercenaryClass.is_active.is_(True))
            .order_by(MercenaryClass.tier, MercenaryClass.id)
        )
    )
    by_id = {mercenary_class.id: mercenary_class for mercenary_class in classes}
    cards: list[dict[str, object]] = []
    for mercenary_class in classes:
        mercenary_class.view_label = get_class_display_name(mercenary_class)
        code = mercenary_class.code or ""
        primary_attributes = CLASS_PRIMARY_ATTRIBUTES.get(code, ())
        parent = by_id.get(mercenary_class.parent_class_id) if mercenary_class.parent_class_id else None
        children = [
            child
            for child in classes
            if child.parent_class_id == mercenary_class.id
        ]
        cards.append(
            {
                "class": mercenary_class,
                "icon_path": get_class_icon_path(mercenary_class),
                "parent_name": get_class_display_name(parent) if parent else None,
                "children_names": [get_class_display_name(child) for child in children],
                "primary_attributes": [
                    ATTRIBUTE_LABELS.get(attribute, attribute.upper())
                    for attribute in primary_attributes
                ],
                "role_description": ROLE_DESCRIPTIONS.get(
                    mercenary_class.role_type,
                    "Classe equilibrada com progressão própria.",
                ),
                "success_bonus": CLASS_SUCCESS_BONUS.get(code, 0),
                "weapon_profile_label": get_weapon_profile_label(mercenary_class),
                "skills": list_active_skills_for_class(db, mercenary_class.id),
            }
        )
    skill_guide = []
    for card in cards:
        for skill in card["skills"]:
            skill_guide.append({
                "skill": skill,
                "class_name": card["class"].view_label,
                "effect_label": effect_label(skill.effect_type),
                "effect_suffix": effect_suffix(skill.effect_type),
                "works_in": "Missões e masmorras; o efeito é somado ao grupo dentro do limite global.",
                "synergy": card["weapon_profile_label"],
            })
    return {
        "class_cards": cards,
        "class_tiers": {
            0: "Classe inicial",
            1: "Primeira classe",
            2: "Especialização",
            3: "Classe final",
        },
        "skill_guide": skill_guide,
        "attribute_guide": [
            {"code": "FOR", "name": "Força", "description": "Amplia poder direto e favorece combate frontal."},
            {"code": "VIT", "name": "Vitalidade", "description": "Sustenta classes defensivas e contribui para o poder total."},
            {"code": "AGI", "name": "Agilidade", "description": "Favorece precisão, infiltração e estilos rápidos."},
            {"code": "INT", "name": "Inteligência", "description": "Fortalece magia, suporte e a leitura técnica do Ladino."},
            {"code": "SOR", "name": "Sorte", "description": "Apoia precisão, crítico e oportunidades de recompensa."},
        ],
        "combination_guide": [
            {"name": "Formação segura", "members": "Guerreiro + Clérigo + Arqueiro", "use": "Tende a funcionar melhor em jornadas longas e masmorras de risco médio."},
            {"name": "Equipe de infiltração", "members": "Ladino + Ninja + Mentalista", "use": "Tende a favorecer missões técnicas, rápidas e com risco controlado."},
            {"name": "Investida agressiva", "members": "Duelista + Assassino + Mago", "use": "Tende a resolver alvos prioritários rapidamente, mas exige bons equipamentos."},
            {"name": "Expedição de coleta", "members": "Ranger + profissão compatível + suporte", "use": "Tende a render mais materiais quando a profissão combina com a família coletada."},
        ],
        "profession_tips": [
            "Profissões bonificam apenas famílias compatíveis e não alteram o papel de combate.",
            "Ranger e Patrulheiro favorecem exploração, mas qualquer classe pode exercer uma profissão.",
            "Docas completam materiais faltantes; missões de coleta continuam sendo a fonte mais eficiente.",
        ],
        "dungeon_tips": [
            "Compare o poder total recomendado antes de iniciar.",
            "Tanque, suporte e dano juntos concedem sinergia, sem impor uma composição única.",
            "Equipamentos, raridade e habilidades ganham peso progressivo nas faixas avançadas.",
        ],
    }
