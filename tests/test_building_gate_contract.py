import unittest
from types import SimpleNamespace

from app.services.dungeon_service import validate_dungeon_requirements
from app.services.mission_service import validate_mission_requirements
from app.services.building_service import are_dungeons_available


class BuildingGateContractTests(unittest.TestCase):
    def setUp(self):
        # Passing a DB stub that cannot answer building queries proves these
        # validators use only the guild level and the content's own fields.
        self.db = object()
        self.new_guild = SimpleNamespace(id=1, level=1)

    def test_regional_contract_validator_ignores_legacy_office_requirement(self):
        contract = SimpleNamespace(
            required_guild_level=1,
            required_building_type="contract_office",
            required_building_level=100,
        )
        validate_mission_requirements(self.db, self.new_guild, contract)

    def test_normal_mission_validator_ignores_legacy_office_requirement(self):
        mission = SimpleNamespace(
            required_guild_level=1,
            required_building_type="contract_office",
            required_building_level=100,
        )
        validate_mission_requirements(self.db, self.new_guild, mission)

    def test_dungeon_validator_ignores_legacy_scouts_requirement(self):
        dungeon = SimpleNamespace(
            required_guild_level=1,
            required_building_type="scouts",
            required_building_level=100,
        )
        validate_dungeon_requirements(self.db, self.new_guild, dungeon)
        self.assertTrue(are_dungeons_available(self.db, self.new_guild.id))

    def test_boss_validator_ignores_legacy_scouts_requirement(self):
        boss = SimpleNamespace(
            required_guild_level=1,
            required_building_type="scouts",
            required_building_level=100,
        )
        validate_dungeon_requirements(self.db, self.new_guild, boss)
        self.assertTrue(are_dungeons_available(self.db, self.new_guild.id))


if __name__ == "__main__":
    unittest.main()
