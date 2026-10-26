from datetime import datetime, timedelta, timezone
from math import ceil
from random import choice, randint

from sqlalchemy.orm import Session

from app.models.guild import Guild, GuildResources
from app.models.mercenary import MercenaryClass
from app.models.tavern import GuildTavernState, TavernConfig, TavernSpecialOffer
from app.repositories.mercenary_repository import (
    count_mercenaries_by_guild,
    create_mercenary,
    get_mercenary_class_by_code,
    list_active_mercenary_names_by_guild,
)
from app.repositories.tavern_repository import (
    create_guild_tavern_state,
    create_special_offer,
    create_tavern_config,
    get_active_special_offer,
    get_guild_tavern_state,
    get_tavern_config,
    list_special_offers_by_guild,
)
from app.services.balance_service import (
    APPRENTICE_RARITY_CAPS,
    SPECIAL_RARITY_CAPS,
    TAVERN_MANUAL_REFRESH_COST,
    calculate_power_score,
    get_mercenary_power_range,
    rarity_progression_bonus_percent,
)
from app.services.building_service import ensure_guild_buildings, get_building_level, get_mercenary_limit
from app.services.display_service import class_label, rarity_label
from app.services.guild_progression_service import add_guild_xp
from app.services.mercenary_name_service import choose_random_mercenary_names
from app.services.icon_service import get_class_icon_path
from app.services.building_balance_service import tavern_values
from app.services.achievement_service import record_guild_stat


class TavernError(ValueError):
    pass


SPECIAL_CLASS_CODES = ["warrior", "rogue", "mage", "cleric", "archer"]
RARITY_CAPS = {**APPRENTICE_RARITY_CAPS, **SPECIAL_RARITY_CAPS}
RARITY_COST_FIELDS = {
    "rare": "special_rare_cost",
    "epic": "special_epic_cost",
    "legendary": "special_legendary_cost",
    "mythic": "special_mythic_cost",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def seed_tavern_config(db: Session) -> None:
    if get_tavern_config(db):
        return
    create_tavern_config(db)
    db.commit()


def get_or_create_tavern_config(db: Session) -> TavernConfig:
    config = get_tavern_config(db)
    if config is None:
        config = create_tavern_config(db)
        db.commit()
        db.refresh(config)
    return config


def get_or_create_tavern_state(db: Session, guild_id: int, config: TavernConfig) -> GuildTavernState:
    state = get_guild_tavern_state(db, guild_id)
    if state is None:
        state = create_guild_tavern_state(
            db,
            guild_id=guild_id,
            apprentice_cost=config.base_apprentice_cost,
            next_special_check_at=utc_now(),
        )
        db.commit()
        db.refresh(state)
    return state


def choose_weighted(options: list[tuple[str, int]]) -> str:
    total = sum(max(0, weight) for _, weight in options)
    if total <= 0:
        return options[0][0]
    roll = randint(1, total)
    cursor = 0
    for value, weight in options:
        cursor += max(0, weight)
        if roll <= cursor:
            return value
    return options[-1][0]


def _roll_attributes_once(rarity: str, mercenary_class: MercenaryClass | None = None) -> dict[str, int]:
    cap = RARITY_CAPS.get(rarity, 10)
    floor_value = 1 if rarity in APPRENTICE_RARITY_CAPS else max(1, cap // 4)
    attributes = {
        "power": randint(floor_value, cap),
        "vitality": randint(floor_value, cap),
        "agility": randint(floor_value, cap),
        "intelligence": randint(floor_value, cap),
        "luck": randint(floor_value, cap),
    }
    if mercenary_class is not None:
        role = mercenary_class.role_type
        if role in {"frontline", "tank"}:
            attributes["power"] += cap // 5
            attributes["vitality"] += cap // 5
        elif role == "skirmisher":
            attributes["agility"] += cap // 4
            attributes["luck"] += cap // 6
        elif role == "caster":
            attributes["intelligence"] += cap // 4
        elif role == "support":
            attributes["intelligence"] += cap // 5
            attributes["vitality"] += cap // 6
        elif role == "ranged":
            attributes["agility"] += cap // 5
            attributes["power"] += cap // 6
    return attributes


def roll_attributes(rarity: str, mercenary_class: MercenaryClass | None = None) -> dict[str, int]:
    minimum_power, maximum_power = get_mercenary_power_range(rarity)
    for _ in range(200):
        attributes = _roll_attributes_once(rarity, mercenary_class)
        power_score = tavern_candidate_power(attributes)
        if power_score >= minimum_power and (maximum_power is None or power_score <= maximum_power):
            return attributes

    attributes = _roll_attributes_once(rarity, mercenary_class)
    power_score = tavern_candidate_power(attributes)
    if power_score < minimum_power:
        attributes["power"] += minimum_power - power_score
    return attributes


def tavern_candidate_power(attributes: dict[str, int]) -> int:
    return calculate_power_score({**attributes, "armor": 0})


def get_tavern_apprentice_chances(tavern_level: int, config: TavernConfig) -> dict[str, int | None]:
    return tavern_values(tavern_level, config.common_apprentice_chance, config.uncommon_apprentice_chance)


def get_discounted_hire_cost(base_cost: int, discount_percent: int) -> int:
    return max(1, ceil(base_cost * (100 - discount_percent) / 100))


def generate_apprentice_preview(config: TavernConfig, tavern_level: int = 0) -> dict[str, object]:
    chances = get_tavern_apprentice_chances(tavern_level, config)
    rarity = choose_weighted(
        [
            ("common", int(chances["common_final"])),
            ("uncommon", int(chances["uncommon_final"])),
        ]
    )
    attributes = roll_attributes(rarity)
    return {
        "rarity": rarity,
        "rarity_label": rarity_label(rarity),
        "progression_bonus_percent": rarity_progression_bonus_percent(rarity),
        "attributes": attributes,
        "power_score": tavern_candidate_power(attributes),
        "tavern_signature": f"{tavern_level}:{config.common_apprentice_chance}:{config.uncommon_apprentice_chance}",
    }


def is_valid_apprentice_preview(
    preview: object,
    config: TavernConfig | None = None,
    tavern_level: int | None = None,
) -> bool:
    if not isinstance(preview, dict):
        return False
    rarity = str(preview.get("rarity", ""))
    attributes = preview.get("attributes")
    if rarity not in APPRENTICE_RARITY_CAPS or not isinstance(attributes, dict):
        return False
    try:
        parsed_attributes = {
            attribute: int(attributes[attribute])
            for attribute in ("power", "vitality", "agility", "intelligence", "luck")
        }
    except (KeyError, TypeError, ValueError):
        return False
    cap = APPRENTICE_RARITY_CAPS[rarity]
    if any(value < 1 or value > cap for value in parsed_attributes.values()):
        return False
    minimum_power, maximum_power = get_mercenary_power_range(rarity)
    power_score = tavern_candidate_power(parsed_attributes)
    valid = power_score >= minimum_power and (maximum_power is None or power_score <= maximum_power)
    if config is not None and tavern_level is not None:
        valid = valid and preview.get("tavern_signature") == (
            f"{tavern_level}:{config.common_apprentice_chance}:{config.uncommon_apprentice_chance}"
        )
    return valid


def next_apprentice_cost(current_cost: int, config: TavernConfig) -> int:
    growth = (
        config.apprentice_growth_before_threshold_percent
        if current_cost < config.apprentice_cost_threshold
        else config.apprentice_growth_after_threshold_percent
    )
    return max(current_cost + 1, ceil(current_cost * (1 + growth / 100)))


def refresh_special_offer(db: Session, guild: Guild, state: GuildTavernState, config: TavernConfig) -> TavernSpecialOffer | None:
    now = utc_now()
    active_offer = get_active_special_offer(db, guild.id, now)
    if active_offer is not None:
        current_attributes = {
            "power": active_offer.power,
            "vitality": active_offer.vitality,
            "agility": active_offer.agility,
            "intelligence": active_offer.intelligence,
            "luck": active_offer.luck,
        }
        minimum_power, _ = get_mercenary_power_range(active_offer.rarity)
        current_power = tavern_candidate_power(current_attributes)
        if current_power < minimum_power:
            active_offer.power += minimum_power - current_power
            db.add(active_offer)
            db.commit()
            db.refresh(active_offer)
        return active_offer

    expired_offers = [
        offer for offer in list_special_offers_by_guild(db, guild.id)
        if offer.status == "active" and offer.available_until <= now
    ]
    for offer in expired_offers:
        offer.status = "expired"
        db.add(offer)

    if state.next_special_check_at > now:
        if expired_offers:
            db.commit()
        return None

    state.next_special_check_at = now + timedelta(hours=config.special_spawn_cooldown_hours)
    offer: TavernSpecialOffer | None = None
    if randint(1, 100) <= config.special_spawn_chance:
        rarity = choose_weighted(
            [
                ("rare", config.special_rare_chance),
                ("epic", config.special_epic_chance),
                ("legendary", config.special_legendary_chance),
                ("mythic", config.special_mythic_chance),
            ]
        )
        class_code = choice(SPECIAL_CLASS_CODES)
        mercenary_class = get_mercenary_class_by_code(db, class_code)
        if mercenary_class is not None:
            attributes = roll_attributes(rarity, mercenary_class)
            offer = create_special_offer(
                db,
                {
                    "guild_id": guild.id,
                    "name": choose_random_mercenary_names(
                        1,
                        list_active_mercenary_names_by_guild(db, guild.id),
                    )[0],
                    "class_id": mercenary_class.id,
                    "rarity": rarity,
                    "level": 20,
                    **attributes,
                    "gold_cost": int(getattr(config, RARITY_COST_FIELDS[rarity])),
                    "available_from": now,
                    "available_until": now + timedelta(hours=config.special_offer_duration_hours),
                    "status": "active",
                },
            )
    db.add(state)
    db.commit()
    if offer is not None:
        db.refresh(offer)
    return offer


def get_tavern_page_context(db: Session, guild: Guild, resources: GuildResources | None) -> dict[str, object]:
    ensure_guild_buildings(db, guild.id)
    tavern_level = get_building_level(db, guild.id, "tavern")
    if tavern_level < 1:
        return {"resources": resources, "tavern_level": tavern_level}
    config = get_or_create_tavern_config(db)
    state = get_or_create_tavern_state(db, guild.id, config)
    active_offer = refresh_special_offer(db, guild, state, config)
    bulk_count = 10
    chances = get_tavern_apprentice_chances(tavern_level, config)
    current_base_cost = state.current_apprentice_hire_cost
    current_final_cost = get_discounted_hire_cost(current_base_cost, int(chances["hire_discount_percent"]))
    bulk_costs = calculate_bulk_apprentice_costs(
        state.current_apprentice_hire_cost, config, bulk_count, int(chances["hire_discount_percent"]),
    )
    if active_offer is not None:
        active_offer.rarity_label = rarity_label(active_offer.rarity)
        active_offer.progression_bonus_percent = rarity_progression_bonus_percent(active_offer.rarity)
        active_offer.class_label = class_label(active_offer.mercenary_class)
        active_offer.class_icon_path = get_class_icon_path(active_offer.mercenary_class)
        active_offer.power_score = tavern_candidate_power(
            {
                "power": active_offer.power,
                "vitality": active_offer.vitality,
                "agility": active_offer.agility,
                "intelligence": active_offer.intelligence,
                "luck": active_offer.luck,
            }
        )
    return {
        "resources": resources,
        "config": config,
        "state": state,
        "active_offer": active_offer,
        "tavern_level": tavern_level,
        "mercenary_count": count_mercenaries_by_guild(db, guild.id),
        "mercenary_limit": get_mercenary_limit(db, guild.id),
        "bulk_hire_count": bulk_count,
        "bulk_hire_cost": bulk_costs["final"],
        "bulk_hire_base_cost": bulk_costs["base"],
        "current_apprentice_base_cost": current_base_cost,
        "current_apprentice_final_cost": current_final_cost,
        "apprentice_chances": chances,
        "manual_refresh_cost": TAVERN_MANUAL_REFRESH_COST,
        "now": utc_now(),
    }


def calculate_bulk_apprentice_cost(current_cost: int, config: TavernConfig, count: int) -> int:
    return calculate_bulk_apprentice_costs(current_cost, config, count, 0)["final"]


def calculate_bulk_apprentice_costs(
    current_cost: int,
    config: TavernConfig,
    count: int,
    discount_percent: int,
) -> dict[str, int]:
    base_total = 0
    final_total = 0
    cost = current_cost
    for _ in range(count):
        base_total += cost
        final_total += get_discounted_hire_cost(cost, discount_percent)
        cost = next_apprentice_cost(cost, config)
    return {"base": base_total, "final": final_total}


def validate_hire_capacity(db: Session, guild: Guild) -> None:
    if count_mercenaries_by_guild(db, guild.id) >= get_mercenary_limit(db, guild.id):
        raise TavernError("Limite de mercenarios atingido. Evolua o Alojamento.")


def require_tavern(db: Session, guild: Guild) -> None:
    if get_building_level(db, guild.id, "tavern") < 1:
        raise TavernError("Evolua a Taverna para o nível 1 antes de contratar mercenários.")


def hire_apprentice(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    name: str,
    preview: dict[str, object] | None = None,
) -> None:
    require_tavern(db, guild)
    name = name.strip()
    if not name:
        raise TavernError("Nome do Aprendiz e obrigatorio.")
    if resources is None:
        raise TavernError("Recursos da guilda indisponiveis.")
    config = get_or_create_tavern_config(db)
    state = get_or_create_tavern_state(db, guild.id, config)
    tavern_level = get_building_level(db, guild.id, "tavern")
    chances = get_tavern_apprentice_chances(tavern_level, config)
    apprentice_class = get_mercenary_class_by_code(db, "apprentice")
    if apprentice_class is None:
        raise TavernError("Classe Aprendiz indisponivel.")
    validate_hire_capacity(db, guild)
    final_cost = get_discounted_hire_cost(
        state.current_apprentice_hire_cost, int(chances["hire_discount_percent"]),
    )
    if resources.gold < final_cost:
        raise TavernError("Ouro insuficiente para contratar Aprendiz.")

    rarity = str(preview.get("rarity")) if preview else ""
    attributes = preview.get("attributes") if preview else None
    if not is_valid_apprentice_preview(preview, config, tavern_level):
        generated_preview = generate_apprentice_preview(config, tavern_level)
        rarity = str(generated_preview["rarity"])
        attributes = generated_preview["attributes"]
    validated_attributes = {
        attribute: int(attributes.get(attribute, 1))
        for attribute in ("power", "vitality", "agility", "intelligence", "luck")
    }
    cap = APPRENTICE_RARITY_CAPS[rarity]
    minimum_power, maximum_power = get_mercenary_power_range(rarity)
    power_score = tavern_candidate_power(validated_attributes)
    if (
        any(value < 1 or value > cap for value in validated_attributes.values())
        or power_score < minimum_power
        or (maximum_power is not None and power_score > maximum_power)
    ):
        raise TavernError("A oferta de Aprendiz expirou. Recarregue a Taverna.")
    paid_cost = final_cost
    resources.gold -= paid_cost
    state.apprentice_hire_count += 1
    state.current_apprentice_hire_cost = next_apprentice_cost(state.current_apprentice_hire_cost, config)
    create_mercenary(
        db,
        guild.id,
        apprentice_class,
        name=name,
        rarity=rarity,
        hire_cost=paid_cost,
        **validated_attributes,
    )
    record_guild_stat(db, guild.id, "mercenaries_hired", 1)
    add_guild_xp(guild, 10)
    db.add(resources)
    db.add(state)
    db.add(guild)
    db.commit()


def hire_apprentices_bulk(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    count: int = 10,
) -> None:
    require_tavern(db, guild)
    if resources is None:
        raise TavernError("Recursos da guilda indisponíveis.")
    config = get_or_create_tavern_config(db)
    state = get_or_create_tavern_state(db, guild.id, config)
    apprentice_class = get_mercenary_class_by_code(db, "apprentice")
    if apprentice_class is None:
        raise TavernError("Classe Aprendiz indisponível.")
    current_count = count_mercenaries_by_guild(db, guild.id)
    limit = get_mercenary_limit(db, guild.id)
    if current_count + count > limit:
        raise TavernError("Não há vagas suficientes no Alojamento para contratar 10 Aprendizes.")
    tavern_level = get_building_level(db, guild.id, "tavern")
    chances = get_tavern_apprentice_chances(tavern_level, config)
    discount = int(chances["hire_discount_percent"])
    costs = calculate_bulk_apprentice_costs(state.current_apprentice_hire_cost, config, count, discount)
    total_cost = costs["final"]
    if resources.gold < total_cost:
        raise TavernError(f"Ouro insuficiente. Contratar 10 Aprendizes custa {total_cost} ouro.")

    resources.gold -= total_cost
    names = choose_random_mercenary_names(
        count,
        list_active_mercenary_names_by_guild(db, guild.id),
    )
    for index in range(count):
        rarity = choose_weighted(
            [
                ("common", int(chances["common_final"])),
                ("uncommon", int(chances["uncommon_final"])),
            ]
        )
        attributes = roll_attributes(rarity)
        paid_cost = get_discounted_hire_cost(state.current_apprentice_hire_cost, discount)
        state.apprentice_hire_count += 1
        state.current_apprentice_hire_cost = next_apprentice_cost(state.current_apprentice_hire_cost, config)
        create_mercenary(
            db,
            guild.id,
            apprentice_class,
            name=names[index],
            rarity=rarity,
            hire_cost=paid_cost,
            **attributes,
        )
        record_guild_stat(db, guild.id, "mercenaries_hired", 1)
    add_guild_xp(guild, 10 * count)
    db.add(resources)
    db.add(state)
    db.add(guild)
    db.commit()


def manually_refresh_special_offer(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
) -> TavernSpecialOffer | None:
    require_tavern(db, guild)
    if resources is None:
        raise TavernError("Recursos da guilda indisponíveis.")
    if resources.gold < TAVERN_MANUAL_REFRESH_COST:
        raise TavernError(f"Renovar visitantes custa {TAVERN_MANUAL_REFRESH_COST} ouro.")
    config = get_or_create_tavern_config(db)
    state = get_or_create_tavern_state(db, guild.id, config)
    now = utc_now()
    active_offer = get_active_special_offer(db, guild.id, now)
    if active_offer is None:
        raise TavernError("A renovação só fica disponível quando existe uma oferta especial ativa.")
    for offer in list_special_offers_by_guild(db, guild.id):
        if offer.status == "active":
            offer.status = "expired"
            db.add(offer)
    resources.gold -= TAVERN_MANUAL_REFRESH_COST
    state.next_special_check_at = now
    db.add(resources)
    db.add(state)
    db.commit()
    return refresh_special_offer(db, guild, state, config)


def hire_special_offer(
    db: Session,
    guild: Guild,
    resources: GuildResources | None,
    offer_id: str,
) -> None:
    require_tavern(db, guild)
    if resources is None:
        raise TavernError("Recursos da guilda indisponiveis.")
    try:
        parsed_offer_id = int(offer_id)
    except ValueError as exc:
        raise TavernError("Oferta invalida.") from exc
    config = get_or_create_tavern_config(db)
    state = get_or_create_tavern_state(db, guild.id, config)
    offer = refresh_special_offer(db, guild, state, config)
    if offer is None or offer.id != parsed_offer_id or offer.status != "active":
        raise TavernError("Oferta especial indisponivel.")
    if offer.available_until <= utc_now():
        offer.status = "expired"
        db.add(offer)
        db.commit()
        raise TavernError("Oferta especial expirada.")
    validate_hire_capacity(db, guild)
    if resources.gold < offer.gold_cost:
        raise TavernError("Ouro insuficiente para contratar este mercenario.")

    resources.gold -= offer.gold_cost
    create_mercenary(
        db,
        guild.id,
        offer.mercenary_class,
        name=offer.name,
        level=offer.level,
        rarity=offer.rarity,
        power=offer.power,
        vitality=offer.vitality,
        agility=offer.agility,
        intelligence=offer.intelligence,
        luck=offer.luck,
        hire_cost=offer.gold_cost,
    )
    record_guild_stat(db, guild.id, "mercenaries_hired", 1)
    offer.status = "hired"
    add_guild_xp(guild, 25)
    db.add(resources)
    db.add(offer)
    db.add(guild)
    db.commit()


def tavern_summary(db: Session, guild: Guild) -> dict[str, object]:
    if get_building_level(db, guild.id, "tavern") < 1:
        return {
            "is_built": False,
            "apprentice_cost": 0,
            "special_offer_active": False,
            "next_special_check_at": None,
            "special_offer_name": None,
            "special_offer_rarity": None,
            "special_offer_rarity_label": None,
            "special_offer_until": None,
        }
    config = get_or_create_tavern_config(db)
    state = get_or_create_tavern_state(db, guild.id, config)
    offer = get_active_special_offer(db, guild.id, utc_now())
    if offer is not None:
        offer.rarity_label = rarity_label(offer.rarity)
    return {
        "is_built": True,
        "apprentice_cost": state.current_apprentice_hire_cost,
        "special_offer_active": offer is not None,
        "next_special_check_at": state.next_special_check_at,
        "special_offer_name": offer.name if offer else None,
        "special_offer_rarity": offer.rarity if offer else None,
        "special_offer_rarity_label": offer.rarity_label if offer else None,
        "special_offer_until": offer.available_until if offer else None,
    }
