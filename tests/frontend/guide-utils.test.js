import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const { groupCatalogSources } = require("../../app/static/js/guide-utils.js");

const source = (overrides = {}) => ({
  filter_key: "drop", type: "dungeon_or_boss", label: "Chefes", name: "Dragão",
  requirement: "guilda nível 5+", chance: "10% base", quantity: "1 unidade", price: null,
  ...overrides,
});

const item = (rarity, overrides = {}) => ({
  id: rarity, name: "Espada Solar", item_type: "equipment", item_type_label: "Equipamento",
  family: "", equipment_slot: "sword", level_band: "1-10", item_level: 5, rarity,
  ...overrides,
});

test("equivalent activity entries consolidate rarities into one item row", () => {
  const groups = groupCatalogSources([
    { item: item("Raro"), sources: [source()] },
    { item: item("Épico"), sources: [source()] },
  ]);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].entries.length, 1);
  assert.deepEqual(groups[0].entries[0].rarities, ["Raro", "Épico"]);
  assert.match(groups[0].entries[0].itemLabel, /Espada Solar · Equipamento · sword · 1-10/);
  assert.doesNotMatch(groups[0].entries[0].itemLabel, /Tier|T[1-8]/);
});

test("different drop conditions remain separate and retain every chance and requirement", () => {
  const groups = groupCatalogSources([
    { item: item("Raro"), sources: [source()] },
    { item: item("Épico"), sources: [source({ chance: "4% base", requirement: "guilda nível 12+" })] },
    { item: item("Lendário"), sources: [source({ quantity: "1–2 unidades" })] },
  ]);
  assert.equal(groups.length, 3);
  assert.deepEqual(groups.map((group) => [group.source.requirement, group.source.chance, group.source.quantity]), [
    ["guilda nível 5+", "10% base", "1 unidade"],
    ["guilda nível 12+", "4% base", "1 unidade"],
    ["guilda nível 5+", "10% base", "1–2 unidades"],
  ]);
});
