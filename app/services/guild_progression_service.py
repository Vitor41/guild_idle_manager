from app.models.guild import Guild
from app.core.game_balance import GUILD_MAX_LEVEL, GUILD_XP_BASE, GUILD_XP_GROWTH


def guild_xp_required_for_level(level: int) -> int:
    normalized = max(1, level)
    return GUILD_XP_BASE + (normalized - 1) * GUILD_XP_GROWTH


def add_guild_xp(guild: Guild, xp_gain: int) -> list[str]:
    if xp_gain <= 0 or guild.level >= GUILD_MAX_LEVEL:
        return []

    guild.xp += xp_gain
    messages: list[str] = [f"Guilda recebeu {xp_gain} XP."]
    while guild.level < GUILD_MAX_LEVEL and guild.xp >= guild_xp_required_for_level(guild.level):
        guild.xp -= guild_xp_required_for_level(guild.level)
        guild.level += 1
        messages.append(f"Guilda subiu para o nível {guild.level}.")

    if guild.level >= GUILD_MAX_LEVEL:
        guild.level = GUILD_MAX_LEVEL
        guild.xp = 0

    return messages


def add_guild_xp_from_mercenary_xp(guild: Guild, total_mercenary_xp: int) -> list[str]:
    if total_mercenary_xp <= 0:
        return []
    return add_guild_xp(guild, max(1, total_mercenary_xp // 10))
