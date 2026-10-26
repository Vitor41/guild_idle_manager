from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.models.achievement import AchievementTemplate, CodexEntry, GuildAchievement, GuildCodexUnlock, GuildStat
from app.models.dungeon import DungeonRun, DungeonTemplate
from app.models.guild import Guild, GuildResources
from app.models.item import GuildInventoryItem, GuildItemInstance, ItemTemplate
from app.models.mercenary import Mercenary, MercenaryClass
from app.models.mission import MissionRun
from app.models.building import GuildBuilding
from app.repositories.achievement_repository import (
    get_achievement_by_key, get_codex_entry_by_key, get_codex_unlock, get_guild_achievement,
    get_guild_stat, list_active_achievements, list_codex_entries, list_codex_unlocks,
)
from app.services.display_service import annotate_mercenary_display, clean_generated_name
from app.services.guild_progression_service import add_guild_xp


INITIAL_ACHIEVEMENTS = [
    ("first_hire", "Primeiro Recruta", "Contrate seu primeiro mercenário.", "mercenaries_hired", 1, 75, 0),
    ("first_company", "Primeira Companhia", "Contrate 5 mercenários.", "mercenary_count", 5, 100, 0),
    ("recruiter_10", "Olho para Talentos", "Contrate 10 mercenários ao longo da jornada.", "mercenaries_hired", 10, 200, 0),
    ("recruiter_50", "Recrutador Experiente", "Contrate 50 mercenários.", "mercenaries_hired", 50, 750, 100),
    ("recruiter_250", "Nomes para a História", "Contrate 250 mercenários.", "mercenaries_hired", 250, 2500, 500),
    ("first_mission", "Primeira Missão", "Conclua sua primeira missão com sucesso.", "missions_completed", 1, 75, 0),
    ("mission_veteran", "Veterano de Missões", "Conclua 10 missões.", "missions_completed", 10, 150, 0),
    ("mission_50", "Companhia Confiável", "Conclua 50 missões.", "missions_completed", 50, 500, 100),
    ("mission_100", "Nome Reconhecido", "Conclua 100 missões.", "missions_completed", 100, 1000, 200),
    ("mission_500", "Lenda das Missões", "Conclua 500 missões.", "missions_completed", 500, 4000, 750),
    ("first_gathering", "Primeiros Suprimentos", "Conclua sua primeira missão de coleta.", "gathering_completed", 1, 75, 0),
    ("gathering_25", "Armazéns Abastecidos", "Conclua 25 missões de coleta.", "gathering_completed", 25, 300, 50),
    ("gathering_100", "Mestre dos Recursos", "Conclua 100 missões de coleta.", "gathering_completed", 100, 1000, 200),
    ("building_5", "Primeiras Fundações", "Eleve uma construção ao nível 5.", "max_building_level", 5, 150, 0),
    ("building_10", "Fortaleza em Crescimento", "Eleve uma construção ao nível 10.", "max_building_level", 10, 300, 50),
    ("building_25", "Centro Mercenário", "Eleve uma construção ao nível 25.", "max_building_level", 25, 800, 150),
    ("building_50", "Obra-Prima da Guilda", "Eleve uma construção ao nível 50.", "max_building_level", 50, 2000, 500),
    ("first_class_change", "Novo Caminho", "Conclua uma troca de classe.", "class_changes", 1, 250, 50),
    ("class_change_10", "Mestre de Armas", "Conclua 10 trocas de classe.", "class_changes", 10, 1000, 250),
    ("first_dungeon", "Além dos Portões", "Conclua sua primeira masmorra.", "dungeons_completed", 1, 150, 0),
    ("dungeon_delver", "Explorador de Masmorras", "Conclua 5 masmorras.", "dungeons_completed", 5, 250, 0),
    ("dungeon_50", "Cartógrafo do Perigo", "Conclua 50 masmorras.", "dungeons_completed", 50, 1200, 250),
    ("first_boss", "Diante do Chefe", "Derrote seu primeiro chefe.", "bosses_defeated", 1, 300, 50),
    ("boss_10", "Matador de Chefes", "Derrote 10 chefes.", "bosses_defeated", 10, 1500, 300),
    ("guild_growth", "Guilda em Ascensão", "Alcance o nível 10 de guilda.", "guild_level", 10, 300, 0),
    ("guild_50", "Guilda Lendária", "Alcance o nível 50 de guilda.", "guild_level", 50, 2500, 500),
    ("first_craft", "Primeira Forja", "Fabrique seu primeiro item.", "crafted_count", 1, 100, 0),
    ("artisan", "Mestre Artesão", "Fabrique 5 itens.", "crafted_count", 5, 200, 0),
    ("craft_50", "Oficina Incansável", "Fabrique 50 itens.", "crafted_count", 50, 1000, 250),
    ("first_refine", "Aço Aprimorado", "Refine seu primeiro equipamento.", "refined_count", 1, 100, 0),
    ("refiner", "Metal Temperado", "Refine equipamentos 5 vezes.", "refined_count", 5, 200, 0),
    ("market_1", "Primeira Venda", "Colete sua primeira venda no Mercado.", "market_sales", 1, 100, 0),
    ("market_50", "Mercador da Guilda", "Colete 50 vendas no Mercado.", "market_sales", 50, 1000, 200),
    ("dock_1", "Negócio no Cais", "Compre sua primeira oferta nas Docas.", "dock_purchases", 1, 100, 0),
    ("dock_50", "Cliente dos Sete Mares", "Compre 50 ofertas nas Docas.", "dock_purchases", 50, 1000, 200),
    ("profession_1", "Ferramenta Certa", "Use um bônus de profissão em uma coleta.", "profession_bonus_uses", 1, 150, 0),
    ("profession_25", "Especialistas em Campo", "Use bônus de profissão 25 vezes.", "profession_bonus_uses", 25, 750, 150),
    ("collector", "Colecionador", "Descubra 10 itens no Códex.", "items_discovered", 10, 250, 0),
    ("codex_10", "Arquivo Iniciado", "Desbloqueie 10 registros no Códex.", "codex_discovered", 10, 300, 0),
    ("codex_50", "Memória da Guilda", "Desbloqueie 50 registros no Códex.", "codex_discovered", 50, 0, 250),
    ("codex_100", "Cronista", "Desbloqueie 100 registros no Códex.", "codex_discovered", 100, 1000, 0),
    ("codex_250", "Grande Coleção", "Desbloqueie 250 registros no Códex.", "codex_discovered", 250, 0, 1000),
    ("codex_500", "Arquivo Lendário", "Desbloqueie 500 registros no Códex.", "codex_discovered", 500, 5000, 0),
]


class AchievementError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def seed_achievements_and_codex(db: Session) -> None:
    changed = False
    for key, title, description, criterion, threshold, reward_gold, reward_xp in INITIAL_ACHIEVEMENTS:
        if get_achievement_by_key(db, key):
            continue
        db.add(AchievementTemplate(key=key, title=title, description=description, criterion_type=criterion,
                                   threshold=threshold, reward_gold=reward_gold, reward_xp=reward_xp, is_active=True))
        changed = True
    catalogs = [
        ("class", list(db.scalars(select(MercenaryClass).where(MercenaryClass.is_active.is_(True))))),
        ("item", list(db.scalars(select(ItemTemplate).where(ItemTemplate.is_active.is_(True))))),
        ("dungeon", list(db.scalars(select(DungeonTemplate).where(DungeonTemplate.is_active.is_(True))))),
    ]
    for category, entries in catalogs:
        for entry in entries:
            ref = str(entry.code if category == "class" else entry.id)
            key = f"{category}:{ref}"
            if get_codex_entry_by_key(db, key):
                continue
            raw_title = getattr(entry, "display_name", None) or entry.name
            title = clean_generated_name(raw_title) if category == "item" else raw_title
            db.add(CodexEntry(key=key, category=category, reference_key=ref,
                              title=title,
                              description=entry.description,
                              rarity=getattr(entry, "rarity", "common")))
            changed = True
    if changed:
        db.commit()


def record_guild_stat(db: Session, guild_id: int, key: str, amount: int = 1, commit: bool = False) -> GuildStat:
    stat = get_guild_stat(db, guild_id, key)
    if stat is None:
        stat = GuildStat(guild_id=guild_id, key=key, value=0)
    stat.value += amount
    db.add(stat)
    if commit:
        db.commit()
    return stat


def _unlock_entry(db: Session, guild_id: int, key: str) -> None:
    entry = get_codex_entry_by_key(db, key)
    if entry is not None and get_codex_unlock(db, guild_id, entry.id) is None:
        db.add(GuildCodexUnlock(guild_id=guild_id, codex_entry_id=entry.id))


def unlock_codex_reference(db: Session, guild_id: int, category: str, reference_key: str | int) -> None:
    _unlock_entry(db, guild_id, f"{category}:{reference_key}")


def sync_codex(db: Session, guild: Guild) -> None:
    class_codes = set(db.scalars(select(MercenaryClass.code).join(Mercenary).where(Mercenary.guild_id == guild.id)).all())
    for code in class_codes:
        if code:
            _unlock_entry(db, guild.id, f"class:{code}")
    item_ids = set(db.scalars(select(GuildInventoryItem.item_template_id).where(GuildInventoryItem.guild_id == guild.id)).all())
    item_ids.update(db.scalars(select(GuildItemInstance.item_template_id).where(GuildItemInstance.guild_id == guild.id)).all())
    for item_id in item_ids:
        _unlock_entry(db, guild.id, f"item:{item_id}")
    dungeon_ids = set(db.scalars(select(DungeonRun.dungeon_template_id).where(
        DungeonRun.guild_id == guild.id, DungeonRun.status == "completed"
    )).all())
    for dungeon_id in dungeon_ids:
        _unlock_entry(db, guild.id, f"dungeon:{dungeon_id}")
    db.commit()


def evaluate_achievements(db: Session, guild: Guild) -> list[GuildAchievement]:
    stat_keys = (
        "mercenaries_hired", "gathering_completed", "class_changes", "bosses_defeated",
        "market_sales", "dock_purchases", "profession_bonus_uses", "crafted_count", "refined_count",
    )
    stats = {key: (get_guild_stat(db, guild.id, key) or GuildStat(value=0)).value for key in stat_keys}
    values = {
        "mercenary_count": db.scalar(select(func.count(Mercenary.id)).where(Mercenary.guild_id == guild.id, Mercenary.status != "dismissed")) or 0,
        "missions_completed": db.scalar(select(func.count(MissionRun.id)).where(MissionRun.guild_id == guild.id, MissionRun.status == "completed")) or 0,
        "dungeons_completed": db.scalar(select(func.count(DungeonRun.id)).where(DungeonRun.guild_id == guild.id, DungeonRun.status == "completed")) or 0,
        "guild_level": guild.level,
        **stats,
        "max_building_level": db.scalar(select(func.max(GuildBuilding.level)).where(GuildBuilding.guild_id == guild.id)) or 0,
        "items_discovered": db.scalar(select(func.count(GuildCodexUnlock.id)).join(CodexEntry).where(
            GuildCodexUnlock.guild_id == guild.id, CodexEntry.category == "item"
        )) or 0,
        "codex_discovered": db.scalar(select(func.count(GuildCodexUnlock.id)).where(GuildCodexUnlock.guild_id == guild.id)) or 0,
    }
    for template in list_active_achievements(db):
        achievement = get_guild_achievement(db, guild.id, template.id)
        if achievement is None:
            achievement = GuildAchievement(guild_id=guild.id, achievement_template_id=template.id)
        achievement.progress = min(template.threshold, values.get(template.criterion_type, 0))
        if achievement.progress >= template.threshold and achievement.unlocked_at is None:
            achievement.unlocked_at = utc_now()
        db.add(achievement)
    db.commit()
    return list(db.scalars(select(GuildAchievement).where(GuildAchievement.guild_id == guild.id)))


def get_codex_context(db: Session, guild: Guild, unlocked_only: bool = True, category: str = "all") -> dict[str, object]:
    sync_codex(db, guild)
    achievements = evaluate_achievements(db, guild)
    by_template = {a.achievement_template_id: a for a in achievements}
    achievement_cards = [{"template": t, "progress": by_template[t.id]} for t in list_active_achievements(db)]
    unlocked_ids = {unlock.codex_entry_id for unlock in list_codex_unlocks(db, guild.id)}
    entries = list_codex_entries(db)
    catalog_total = len(entries)
    for entry in entries:
        entry.is_unlocked = entry.id in unlocked_ids
        if entry.category == "item":
            set_committed_value(entry, "title", clean_generated_name(entry.title))
    if unlocked_only:
        entries = [entry for entry in entries if entry.is_unlocked]
    if category in {"class", "item", "dungeon"}:
        entries = [entry for entry in entries if entry.category == category]
    mercenary_collection = list(db.scalars(select(Mercenary).where(
        Mercenary.guild_id == guild.id, Mercenary.status != "dismissed"
    ).order_by(Mercenary.rarity, Mercenary.name)))
    for mercenary in mercenary_collection:
        annotate_mercenary_display(mercenary)
    return {
        "achievement_cards": achievement_cards,
        "codex_entries": entries,
        "unlocked_count": len(unlocked_ids),
        "total_count": catalog_total,
        "selected_unlocked_only": unlocked_only,
        "selected_category": category,
        "mercenary_collection": mercenary_collection,
    }


def claim_achievement(db: Session, guild: Guild, resources: GuildResources | None, achievement_id: int) -> dict[str, int]:
    if resources is None:
        raise AchievementError("Recursos da guilda indisponiveis.")
    achievement = db.scalar(select(GuildAchievement).where(
        GuildAchievement.id == achievement_id, GuildAchievement.guild_id == guild.id
    ))
    if achievement is None or achievement.unlocked_at is None:
        raise AchievementError("Conquista indisponivel.")
    if achievement.claimed_at is not None:
        raise AchievementError("Recompensa ja coletada.")
    reward_gold = achievement.achievement_template.reward_gold
    reward_xp = achievement.achievement_template.reward_xp
    resources.gold += reward_gold
    if reward_xp:
        add_guild_xp(guild, reward_xp)
    achievement.claimed_at = utc_now()
    db.add(resources)
    db.add(achievement)
    db.add(guild)
    db.commit()
    return {"gold": reward_gold, "xp": reward_xp}
