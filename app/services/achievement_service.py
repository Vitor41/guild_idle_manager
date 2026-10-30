from datetime import datetime, timezone

from sqlalchemy import func, select, cast, String
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.models.achievement import AchievementTemplate, CodexEntry, GuildAchievement, GuildCodexUnlock, GuildStat
from app.models.dungeon import DungeonRun, DungeonTemplate
from app.models.guild import Guild, GuildResources
from app.models.item import GuildInventoryItem, GuildItemInstance, ItemTemplate
from app.models.mercenary import Mercenary, MercenaryClass
from app.models.mission import MissionRun, MissionRunMember
from app.models.gathering import GatheringAssignment
from app.models.building import GuildBuilding
from app.repositories.achievement_repository import (
    get_achievement_by_key, get_codex_entry_by_key, get_codex_unlock, get_guild_achievement,
    get_guild_stat, list_active_achievements, list_codex_entries, list_codex_unlocks,
)
from app.models.regional import RegionalEvent, RegionalEventParticipant, RegionalGuildState, RegionalOffer, RegionalRunOutcome
from app.services.display_service import annotate_mercenary_display, clean_generated_name
from app.services.guild_progression_service import add_guild_xp
from app.services.icon_service import get_class_icon_path, get_item_icon_path


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


CAMPAIGN_ACHIEVEMENTS = [
    ("roster_full_20", "Companhia Completa", "Mantenha 20 mercenários ativos simultaneamente.", "active_mercenaries", 20, 1000, 250),
    ("five_initial_classes", "Cinco Caminhos", "Mantenha ao menos um mercenário de cada classe inicial.", "initial_classes", 5, 750, 250),
    ("five_elite_recruits", "Sangue de Elite", "Contrate cinco mercenários Raros ou superiores.", "rare_mercenaries", 5, 1000, 250),
    ("five_professions", "Mãos Especializadas", "Tenha cinco profissões distintas no elenco ativo.", "distinct_professions", 5, 750, 250),
    ("contracts_a_25", "Caçadores de Elite", "Conclua 25 contratos bem-sucedidos de Rank A ou S.", "regional_contract_rank_a_plus", 25, 1500, 350),
    ("contracts_s_10", "Lenda da Vigília", "Conclua 10 contratos bem-sucedidos de Rank S.", "regional_contract_rank_s", 10, 1000, 500),
    ("contracts_party3_100", "Companhia em Marcha", "Conclua 100 contratos com grupos de três ou mais mercenários.", "regional_contract_party3", 100, 3000, 750),
    ("gathering_each_50", "Três Fontes", "Complete 50 ciclos de coleta em madeira, minério e couro.", "gathering_each_family", 50, 1000, 350),
    ("buildings_five_25", "Centro de Poder", "Eleve cinco construções ao nível 25.", "buildings_level_25", 5, 1500, 500),
    ("building_100", "Obra-Prima", "Eleve uma construção ao nível 100.", "max_building_level", 100, 2500, 750),
    ("portals_5", "Além do Véu", "Conclua cinco portais dimensionais.", "portals_completed", 5, 1500, 500),
    ("bosses_a_25", "Quebra-Coroas", "Derrote 25 chefes regionais de Rank A ou S.", "regional_boss_rank_a_plus", 25, 2500, 500),
    ("regional_threat_25", "Guardiões da Pátria", "Reduza 25 pontos de ameaça regional por ações bem-sucedidas da guilda.", "regional_threat_reduced_hundredths", 2500, 1000, 500),
    ("rebellion_success", "Fim da Rebelião", "Contribua para uma rebelião regional bem-sucedida.", "rebellion_successes", 1, 1000, 300),
    ("refine_six_to_10", "Mestre do Refino", "Refine seis equipamentos distintos até +10.", "distinct_items_refined_to_10", 6, 1500, 500),
    ("equipment_codex_100", "Catálogo de Guerra", "Descubra 100 equipamentos no Códex.", "equipment_codex_discovered", 100, 2000, 500),
]

LEGENDARY_MILESTONES = [
    ("bosses_s_10_legendary_weapon", "O Último Desafio", "Derrote 10 chefes regionais de Rank S.", "regional_boss_rank_s", 10, "main_hand"),
    ("rebellions_three_regions_legendary_chest", "Guilda sem Fronteiras", "Contribua com sucesso em rebeliões de três regiões distintas.", "rebellion_three_regions", 3, "chest"),
    ("codex_legendary_10_accessory", "Relíquias Reunidas", "Descubra 10 equipamentos Lendários distintos no Códex.", "legendary_equipment_codex", 10, "ring"),
    ("guild_50_contract_s_50_legendary_helmet", "Maior Guilda de Mercenários", "Alcance nível 50 de guilda e conclua 50 contratos de Rank S.", "guild_50_contract_s_50", 50, "helmet"),
]

ACHIEVEMENT_CRITERION_LABELS = {
    "active_mercenaries": "Mercenários ativos",
    "bosses_defeated": "Chefes derrotados",
    "buildings_level_25": "Construções no nível 25",
    "class_changes": "Trocas de classe concluídas",
    "codex_discovered": "Registros descobertos no Códex",
    "crafted_count": "Itens fabricados",
    "distinct_items_refined_to_10": "Equipamentos distintos refinados até +10",
    "distinct_professions": "Profissões distintas no elenco",
    "dock_purchases": "Ofertas compradas nas Docas",
    "dungeons_completed": "Masmorras concluídas",
    "equipment_codex_discovered": "Equipamentos descobertos no Códex",
    "first_hire": "Mercenários contratados",
    "gathering_completed": "Coletas concluídas",
    "gathering_each_family": "Ciclos de coleta por recurso",
    "guild_50_contract_s_50": "Nível da guilda e contratos de Rank S",
    "guild_level": "Nível da guilda",
    "initial_classes": "Classes iniciais representadas",
    "items_discovered": "Itens descobertos",
    "legendary_equipment_codex": "Equipamentos Lendários descobertos",
    "market_sales": "Vendas coletadas no Mercado",
    "max_building_level": "Maior nível de construção",
    "mercenary_count": "Mercenários no elenco",
    "mercenaries_hired": "Mercenários contratados ao longo da jornada",
    "missions_completed": "Missões concluídas",
    "profession_bonus_uses": "Bônus de profissão usados",
    "rare_mercenaries": "Mercenários Raros ou superiores contratados",
    "rebellion_successes": "Rebeliões bem-sucedidas",
    "rebellion_three_regions": "Regiões distintas com rebeliões bem-sucedidas",
    "refined_count": "Refinamentos concluídos",
    "regional_boss_rank_a_plus": "Chefes regionais de Rank A ou S derrotados",
    "regional_boss_rank_s": "Chefes regionais de Rank S derrotados",
    "regional_contract_party3": "Contratos concluídos com grupos de três ou mais",
    "regional_contract_rank_a_plus": "Contratos de Rank A ou S concluídos",
    "regional_contract_rank_s": "Contratos de Rank S concluídos",
    "regional_threat_reduced_hundredths": "Ameaça regional reduzida em centésimos",
    "portals_completed": "Portais concluídos",
}


class AchievementError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_campaign_achievement_catalog(db: Session) -> bool:
    """Add new campaign achievements without resetting existing progress or claims."""
    changed = False
    for row in CAMPAIGN_ACHIEVEMENTS:
        key, title, description, criterion, threshold, reward_gold, reward_xp = row
        existing = get_achievement_by_key(db, key)
        if existing is None:
            db.add(AchievementTemplate(
                key=key,
                title=title,
                description=description,
                criterion_type=criterion,
                threshold=threshold,
                reward_gold=reward_gold,
                reward_xp=reward_xp,
                is_active=True,
            ))
            changed = True

    for key, title, description, criterion, threshold, slot in LEGENDARY_MILESTONES:
        existing = get_achievement_by_key(db, key)
        item = db.scalar(select(ItemTemplate).where(
            ItemTemplate.item_type == "equipment",
            ItemTemplate.rarity == "legendary",
            ItemTemplate.equipment_slot == slot,
            ItemTemplate.is_active.is_(True),
        ).order_by(ItemTemplate.required_level, ItemTemplate.id).limit(1))
        if item is None:
            continue
        if existing is None:
            db.add(AchievementTemplate(
                key=key,
                title=title,
                description=description,
                criterion_type=criterion,
                threshold=threshold,
                reward_gold=0,
                reward_xp=0,
                reward_item_template_id=item.id,
                is_active=True,
            ))
            changed = True
        elif existing.reward_item_template_id is None:
            existing.reward_item_template_id = item.id
            db.add(existing)
            changed = True
    if changed:
        db.flush()
    return changed


def seed_achievements_and_codex(db: Session) -> None:
    changed = False
    for key, title, description, criterion, threshold, reward_gold, reward_xp in INITIAL_ACHIEVEMENTS:
        if get_achievement_by_key(db, key):
            continue
        db.add(AchievementTemplate(key=key, title=title, description=description, criterion_type=criterion,
                                   threshold=threshold, reward_gold=reward_gold, reward_xp=reward_xp, is_active=True))
        changed = True
    changed = ensure_campaign_achievement_catalog(db) or changed
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
    ensure_campaign_achievement_catalog(db)
    stat_keys = (
        "mercenaries_hired", "gathering_completed", "class_changes", "bosses_defeated",
        "market_sales", "dock_purchases", "profession_bonus_uses", "crafted_count", "refined_count",
    )
    stats = {key: (get_guild_stat(db, guild.id, key) or GuildStat(value=0)).value for key in stat_keys}
    active_mercenaries = db.scalar(select(func.count(Mercenary.id)).where(
        Mercenary.guild_id == guild.id, Mercenary.status != "dismissed",
    )) or 0
    rare_mercenaries = db.scalar(select(func.count(Mercenary.id)).where(
        Mercenary.guild_id == guild.id,
        Mercenary.status != "dismissed",
        Mercenary.rarity.in_(("rare", "epic", "legendary", "mythic")),
    )) or 0
    initial_classes = db.scalar(select(func.count(func.distinct(Mercenary.class_id))).join(
        MercenaryClass, MercenaryClass.id == Mercenary.class_id,
    ).where(
        Mercenary.guild_id == guild.id,
        Mercenary.status != "dismissed",
        MercenaryClass.tier == 1,
    )) or 0
    distinct_professions = db.scalar(select(func.count(func.distinct(Mercenary.profession_id))).where(
        Mercenary.guild_id == guild.id,
        Mercenary.status != "dismissed",
        Mercenary.profession_id.is_not(None),
    )) or 0

    player_state_id = db.scalar(select(RegionalGuildState.id).where(
        RegionalGuildState.guild_id == guild.id,
        RegionalGuildState.profile == "player",
    ))

    def regional_success_count(offer_type: str, ranks: tuple[str, ...]) -> int:
        if player_state_id is None:
            return 0
        return db.scalar(select(func.count(RegionalRunOutcome.id)).join(
            RegionalOffer, RegionalOffer.id == RegionalRunOutcome.offer_id,
        ).where(
            RegionalRunOutcome.guild_state_id == player_state_id,
            RegionalOffer.offer_type == offer_type,
            RegionalRunOutcome.success.is_(True),
            RegionalRunOutcome.rank.in_(ranks),
        )) or 0

    contract_rank_a_plus = regional_success_count("contract", ("A", "S"))
    contract_rank_s = regional_success_count("contract", ("S",))
    boss_rank_a_plus = regional_success_count("boss", ("A", "S"))
    boss_rank_s = regional_success_count("boss", ("S",))
    contract_party3_ids = []
    if player_state_id is not None:
        contract_party3_ids = list(db.scalars(select(MissionRun.id).join(
            RegionalRunOutcome,
            (RegionalRunOutcome.source_run_id == MissionRun.id)
            & (RegionalRunOutcome.source_type == "mission"),
        ).join(
            RegionalOffer, RegionalOffer.id == RegionalRunOutcome.offer_id,
        ).join(
            MissionRunMember, MissionRunMember.mission_run_id == MissionRun.id,
        ).where(
            RegionalRunOutcome.guild_state_id == player_state_id,
            RegionalRunOutcome.success.is_(True),
            RegionalOffer.offer_type == "contract",
        ).group_by(MissionRun.id).having(
            func.count(func.distinct(MissionRunMember.mercenary_id)) >= 3,
        )))

    gathering_counts = {family: 0 for family in ("wood", "ore", "leather")}
    for family in gathering_counts:
        stat = get_guild_stat(db, guild.id, f"gathering_cycles_{family}")
        gathering_counts[family] = stat.value if stat else 0
    for assignment in db.scalars(select(GatheringAssignment).where(GatheringAssignment.guild_id == guild.id)):
        gathering_counts[assignment.resource_family] = max(
            gathering_counts.get(assignment.resource_family, 0), assignment.cycle_count,
        )

    building_count_25 = db.scalar(select(func.count(GuildBuilding.id)).where(
        GuildBuilding.guild_id == guild.id, GuildBuilding.level >= 25,
    )) or 0
    refined_distinct_10 = db.scalar(select(func.count(GuildStat.id)).where(
        GuildStat.guild_id == guild.id,
        GuildStat.key.like("refined_distinct_to_10:%"),
        GuildStat.value > 0,
    )) or 0

    regional_success_ranks = []
    if player_state_id is not None:
        regional_success_ranks = list(db.scalars(select(RegionalRunOutcome.rank).where(
            RegionalRunOutcome.guild_state_id == player_state_id,
            RegionalRunOutcome.success.is_(True),
        )))
    from app.services.regional_cycle_service import regional_outcome_impact

    threat_reduced_hundredths = sum(
        round(regional_outcome_impact(rank) * 100) for rank in regional_success_ranks
    )
    rebellion_success_query = select(RegionalEventParticipant.id).join(
        RegionalEvent, RegionalEvent.id == RegionalEventParticipant.event_id,
    ).join(
        RegionalGuildState, RegionalGuildState.id == RegionalEventParticipant.guild_state_id,
    ).where(
        RegionalGuildState.guild_id == guild.id,
        RegionalEvent.event_type == "rebellion",
        RegionalEventParticipant.status == "resolved",
        RegionalEventParticipant.success.is_(True),
        RegionalEventParticipant.contribution > 0,
    )
    rebellion_successes = db.scalar(select(func.count()).select_from(rebellion_success_query.subquery())) or 0
    rebellion_three_regions = db.scalar(select(func.count(func.distinct(RegionalEvent.region_code))).select_from(
        RegionalEventParticipant,
    ).join(RegionalEvent, RegionalEvent.id == RegionalEventParticipant.event_id).join(
        RegionalGuildState, RegionalGuildState.id == RegionalEventParticipant.guild_state_id,
    ).where(
        RegionalGuildState.guild_id == guild.id,
        RegionalEvent.event_type == "rebellion",
        RegionalEventParticipant.status == "resolved",
        RegionalEventParticipant.success.is_(True),
        RegionalEventParticipant.contribution > 0,
    )) or 0
    legendary_codex_count = db.scalar(select(func.count(GuildCodexUnlock.id)).join(
        CodexEntry, CodexEntry.id == GuildCodexUnlock.codex_entry_id,
    ).join(
        ItemTemplate, cast(ItemTemplate.id, String) == CodexEntry.reference_key,
    ).where(
        GuildCodexUnlock.guild_id == guild.id,
        CodexEntry.category == "item",
        ItemTemplate.item_type == "equipment",
        ItemTemplate.rarity == "legendary",
    )) or 0
    equipment_codex_count = db.scalar(select(func.count(GuildCodexUnlock.id)).join(
        CodexEntry, CodexEntry.id == GuildCodexUnlock.codex_entry_id,
    ).join(
        ItemTemplate, cast(ItemTemplate.id, String) == CodexEntry.reference_key,
    ).where(
        GuildCodexUnlock.guild_id == guild.id,
        CodexEntry.category == "item",
        ItemTemplate.item_type == "equipment",
    )) or 0
    values = {
        "mercenary_count": active_mercenaries,
        "active_mercenaries": active_mercenaries,
        "initial_classes": initial_classes,
        "rare_mercenaries": rare_mercenaries,
        "distinct_professions": distinct_professions,
        "missions_completed": db.scalar(select(func.count(MissionRun.id)).where(MissionRun.guild_id == guild.id, MissionRun.status == "completed")) or 0,
        "dungeons_completed": db.scalar(select(func.count(DungeonRun.id)).where(DungeonRun.guild_id == guild.id, DungeonRun.status == "completed")) or 0,
        "guild_level": guild.level,
        **stats,
        "max_building_level": db.scalar(select(func.max(GuildBuilding.level)).where(GuildBuilding.guild_id == guild.id)) or 0,
        "items_discovered": db.scalar(select(func.count(GuildCodexUnlock.id)).join(CodexEntry).where(
            GuildCodexUnlock.guild_id == guild.id, CodexEntry.category == "item"
        )) or 0,
        "codex_discovered": db.scalar(select(func.count(GuildCodexUnlock.id)).where(GuildCodexUnlock.guild_id == guild.id)) or 0,
        "regional_contract_rank_a_plus": contract_rank_a_plus,
        "regional_contract_rank_s": contract_rank_s,
        "regional_contract_party3": len(contract_party3_ids),
        "gathering_each_family": min(gathering_counts.values(), default=0),
        "buildings_level_25": building_count_25,
        "portals_completed": stats.get("portals_completed", 0),
        "regional_boss_rank_a_plus": boss_rank_a_plus,
        "regional_boss_rank_s": boss_rank_s,
        "regional_threat_reduced_hundredths": threat_reduced_hundredths,
        "rebellion_successes": rebellion_successes,
        "rebellion_three_regions": rebellion_three_regions,
        "distinct_items_refined_to_10": refined_distinct_10,
        "equipment_codex_discovered": equipment_codex_count,
        "legendary_equipment_codex": legendary_codex_count,
        "guild_50_contract_s_50": contract_rank_s if guild.level >= 50 else 0,
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


def get_codex_context(
    db: Session,
    guild: Guild,
    unlocked_only: bool = True,
    category: str = "all",
    trail: str = "all",
) -> dict[str, object]:
    sync_codex(db, guild)
    achievements = evaluate_achievements(db, guild)
    by_template = {a.achievement_template_id: a for a in achievements}
    event_criteria = {"portals_completed", "regional_boss_rank_a_plus", "regional_boss_rank_s",
                      "regional_threat_reduced_hundredths", "rebellion_successes", "rebellion_three_regions"}
    collection_criteria = {"items_discovered", "codex_discovered", "equipment_codex_discovered",
                           "legendary_equipment_codex"}
    achievement_cards = []
    for template in list_active_achievements(db):
        criterion = template.criterion_type
        achievement_trail = ("events" if criterion in event_criteria or criterion.startswith("regional_")
                             else "collection" if criterion in collection_criteria
                             else "progression")
        if trail in {"progression", "collection", "events"} and trail != achievement_trail:
            continue
        achievement_cards.append({
            "template": template,
            "progress": by_template[template.id],
            "trail": achievement_trail,
            "criterion_label": ACHIEVEMENT_CRITERION_LABELS.get(criterion, "Progresso da guilda"),
        })
    legendary_achievement_cards = []
    for template in list_active_achievements(db):
        if template.reward_item_template is None:
            continue
        legendary_achievement_cards.append({
            "template": template,
            "progress": by_template[template.id],
            "criterion_label": ACHIEVEMENT_CRITERION_LABELS.get(
                template.criterion_type, "Progresso da guilda"
            ),
        })
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
    item_ids = [int(entry.reference_key) for entry in entries if entry.category == "item" and entry.reference_key.isdigit()]
    items_by_id = {
        item.id: item
        for item in db.scalars(select(ItemTemplate).where(ItemTemplate.id.in_(item_ids)))
    } if item_ids else {}
    for entry in entries:
        if entry.category == "class":
            entry.icon_path = get_class_icon_path(entry.reference_key)
        elif entry.category == "item":
            item = items_by_id.get(int(entry.reference_key)) if entry.reference_key.isdigit() else None
            entry.icon_path = get_item_icon_path(item) if item is not None else None
        else:
            entry.icon_path = "assets/desktop/sprites/64/dungeon-gate.png"
    mercenary_collection = list(db.scalars(select(Mercenary).where(
        Mercenary.guild_id == guild.id, Mercenary.status != "dismissed"
    ).order_by(Mercenary.rarity, Mercenary.name)))
    for mercenary in mercenary_collection:
        annotate_mercenary_display(mercenary)
    return {
        "achievement_cards": achievement_cards,
        "legendary_achievement_cards": legendary_achievement_cards,
        "codex_entries": entries,
        "unlocked_count": len(unlocked_ids),
        "total_count": catalog_total,
        "selected_unlocked_only": unlocked_only,
        "selected_category": category,
        "selected_trail": trail if trail in {"all", "progression", "collection", "events"} else "all",
        "mercenary_collection": mercenary_collection,
    }


def claim_achievement(db: Session, guild: Guild, resources: GuildResources | None, achievement_id: int) -> dict[str, int | str | None]:
    if resources is None:
        raise AchievementError("Recursos da guilda indisponiveis.")
    achievement = db.scalar(select(GuildAchievement).where(
        GuildAchievement.id == achievement_id, GuildAchievement.guild_id == guild.id
    ).with_for_update())
    if achievement is None or achievement.unlocked_at is None:
        raise AchievementError("Conquista indisponivel.")
    if achievement.claimed_at is not None:
        raise AchievementError("Recompensa ja coletada.")
    reward_gold = achievement.achievement_template.reward_gold
    reward_xp = achievement.achievement_template.reward_xp
    reward_item_name = None
    item_template = achievement.achievement_template.reward_item_template
    if item_template is not None:
        if item_template.item_type != "equipment" or not item_template.equipment_slot:
            raise AchievementError("O equipamento da recompensa não está configurado corretamente.")
        from app.services.equipment_service import create_equipment_instance_from_template

        create_equipment_instance_from_template(db, guild.id, item_template)
        reward_item_name = clean_generated_name(item_template.name)
    resources.gold += reward_gold
    if reward_xp:
        add_guild_xp(guild, reward_xp)
    achievement.claimed_at = utc_now()
    db.add(resources)
    db.add(achievement)
    db.add(guild)
    db.commit()
    from app.services.display_service import rarity_label

    return {
        "gold": reward_gold,
        "xp": reward_xp,
        "item": reward_item_name,
        "item_rarity_label": rarity_label(item_template.rarity) if item_template is not None else None,
    }
