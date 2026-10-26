from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.game_balance import SKILL_EFFECT_CAPS
from app.models.mercenary import Mercenary, MercenaryClass
from app.models.skill import MercenarySkill
from app.repositories.skill_repository import (
    create_skill_template,
    get_mercenary_skill,
    get_skill_template_by_class_and_name,
    list_active_skills_for_class,
    list_mercenary_skills,
)


SKILL_FAMILIES = {
    "warrior": {"warrior", "knight", "templar", "blade", "reaper"},
    "rogue": {"rogue", "assassin", "predator", "ninja", "shinobi"},
    "mage": {"mage", "wizard", "arcane", "mentalist", "warlock"},
    "cleric": {"cleric", "priest", "high_priest", "paladin", "sentinel"},
    "archer": {"archer", "ranger", "patroller", "shooter", "renegade"},
}
CLASS_SKILLS = {
    "apprentice": ("Vontade de Aprender", "xp_reward", 2, "Transforma experiência de campo em aprendizado mais eficiente."),
    "warrior": ("Postura de Combate", "dungeon_power", 5, "Fortalece confrontos diretos e a presença da linha de frente."),
    "knight": ("Guarda de Ferro", "success_chance", 4, "Protege o grupo e reduz o risco em desafios prolongados."),
    "templar": ("Muralha do Juramento", "dungeon_power", 9, "Amplia a resistência do grupo contra chefes e ameaças sombrias."),
    "blade": ("Técnica de Lâmina", "duration_reduction", 5, "Encerra confrontos contra alvos únicos com maior rapidez."),
    "reaper": ("Dança das Lâminas", "drop_chance", 6, "Pressiona inimigos de elite e melhora recompensas de combate."),
    "rogue": ("Leitura de Brechas", "success_chance", 3, "Usa agilidade e inteligência para explorar falhas no plano inimigo."),
    "assassin": ("Golpe Oportunista", "drop_chance", 5, "Favorece recompensas raras em missões contra alvos únicos."),
    "predator": ("Marca da Presa", "gold_reward", 8, "Aumenta o valor de missões de caça e execução."),
    "ninja": ("Véu das Sombras", "duration_reduction", 6, "Reduz o tempo e o risco de operações de infiltração."),
    "shinobi": ("Passo sem Eco", "success_chance", 7, "Coordena infiltrações avançadas sem expor o grupo."),
    "mage": ("Fluxo Arcano", "dungeon_power", 5, "Converte inteligência em poder contra ameaças mágicas."),
    "wizard": ("Conhecimento Antigo", "xp_reward", 7, "Aprofunda descobertas em ruínas, bibliotecas e masmorras arcanas."),
    "arcane": ("Convergência Rúnica", "dungeon_power", 11, "Concentra energia arcana para superar desafios de alto poder."),
    "mentalist": ("Pressão Psíquica", "success_chance", 5, "Reduz falhas contra inimigos inteligentes e conjuradores."),
    "warlock": ("Pacto do Véu", "drop_chance", 7, "Revela componentes arcanos ocultos em conteúdo avançado."),
    "cleric": ("Prece de Amparo", "success_chance", 3, "Estabiliza a equipe e reduz consequências de planos arriscados."),
    "priest": ("Bênção Serena", "xp_reward", 6, "Sustenta jornadas longas e melhora o aprendizado do grupo."),
    "high_priest": ("Milagre da Alvorada", "success_chance", 8, "Oferece segurança excepcional em desafios prolongados."),
    "paladin": ("Juramento Sagrado", "dungeon_power", 7, "Fortalece combates contra mortos-vivos, demônios e chefes."),
    "sentinel": ("Égide Inabalável", "dungeon_power", 11, "Consolida uma linha de frente preparada para o endgame."),
    "archer": ("Mira Estável", "success_chance", 3, "Aumenta a precisão em patrulhas, caçadas e combate à distância."),
    "ranger": ("Rastreamento Silencioso", "drop_chance", 5, "Encontra loot adicional em exploração e coleta."),
    "patroller": ("Domínio da Fronteira", "gold_reward", 8, "Melhora missões de patrulha e exploração de regiões perigosas."),
    "shooter": ("Disparo Decisivo", "duration_reduction", 6, "Resolve missões rápidas com precisão e ritmo agressivo."),
    "renegade": ("Último Cartucho", "drop_chance", 7, "Arrisca uma execução precisa para obter recompensas superiores."),
}


def class_family(code: str | None) -> str:
    normalized = (code or "").lower()
    if normalized == "apprentice":
        return "apprentice"
    for family, codes in SKILL_FAMILIES.items():
        if normalized in codes:
            return family
    return "apprentice"


def seed_class_skills(db: Session) -> None:
    classes = list(db.scalars(select(MercenaryClass).where(MercenaryClass.is_active.is_(True))))
    changed = False
    for mercenary_class in classes:
        blueprint = CLASS_SKILLS.get(mercenary_class.code or "", CLASS_SKILLS["apprentice"])
        name, effect_type, base_value, description = blueprint
        if not list_active_skills_for_class(db, mercenary_class.id):
            create_skill_template(db, {
                "class_id": mercenary_class.id,
                "name": name,
                "description": description,
                "effect_type": effect_type,
                "effect_value": base_value,
                "max_level": 10,
                "is_active": True,
            })
            changed = True
    if changed:
        db.commit()


def refine_class_skills(db: Session) -> int:
    changed = 0
    for mercenary_class in db.scalars(select(MercenaryClass).where(MercenaryClass.is_active.is_(True))):
        blueprint = CLASS_SKILLS.get(mercenary_class.code or "", CLASS_SKILLS["apprentice"])
        name, effect_type, value, description = blueprint
        templates = list(mercenary_class.skill_templates)
        primary = next((template for template in templates if template.name == name), templates[0] if templates else None)
        if primary is None:
            primary = create_skill_template(db, {
                "class_id": mercenary_class.id, "name": name, "description": description,
                "effect_type": effect_type, "effect_value": value, "max_level": 10, "is_active": True,
            })
        else:
            primary.name = name
            primary.description = description
            primary.effect_type = effect_type
            primary.effect_value = value
            primary.is_active = True
        for template in templates:
            if template is not primary:
                template.is_active = False
        changed += 1
    return changed


def ensure_mercenary_skills(db: Session, mercenary: Mercenary) -> list[MercenarySkill]:
    changed = False
    for template in list_active_skills_for_class(db, mercenary.class_id):
        if get_mercenary_skill(db, mercenary.id, template.id):
            continue
        db.add(MercenarySkill(mercenary_id=mercenary.id, skill_template_id=template.id, level=1))
        changed = True
    if changed:
        db.commit()
    return list_mercenary_skills(db, mercenary.id)


def get_mercenary_skill_effects(db: Session, mercenary: Mercenary) -> dict[str, int]:
    effects: dict[str, int] = {}
    for skill in ensure_mercenary_skills(db, mercenary):
        template = skill.skill_template
        if not template.is_active:
            continue
        value = template.effect_value * skill.level
        effects[template.effect_type] = effects.get(template.effect_type, 0) + value
    return {key: min(value, SKILL_EFFECT_CAPS.get(key, value)) for key, value in effects.items()}


def get_party_skill_effects(db: Session, mercenaries: list[Mercenary]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for mercenary in mercenaries:
        for effect_type, value in get_mercenary_skill_effects(db, mercenary).items():
            totals[effect_type] = totals.get(effect_type, 0) + value
    return {key: min(value, SKILL_EFFECT_CAPS.get(key, value)) for key, value in totals.items()}


def effect_label(effect_type: str) -> str:
    return {
        "success_chance": "Chance de sucesso",
        "xp_reward": "XP recebido",
        "gold_reward": "Ouro recebido",
        "duration_reduction": "Reducao de tempo",
        "dungeon_power": "Poder em masmorra",
        "drop_chance": "Chance de drop",
    }.get(effect_type, effect_type)


def effect_suffix(effect_type: str) -> str:
    return " pontos" if effect_type == "dungeon_power" else "%"
