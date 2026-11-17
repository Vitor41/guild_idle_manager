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
  assert.equal(groups[0].entries[0].itemLabel, "Espada Solar · Equipamento · sword");
  assert.doesNotMatch(groups[0].entries[0].itemLabel, /Tier|T[1-8]/);
});

test("same item and source consolidate across tier and level variants", () => {
  const groups = groupCatalogSources([
    { item: item("Raro", { tier: 1, item_level: 5, level_band: "1-10" }), sources: [source()] },
    { item: item("Épico", { tier: 4, item_level: 45, level_band: "41-50" }), sources: [source()] },
  ]);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].entries.length, 1);
  assert.deepEqual(groups[0].entries[0].rarities, ["Raro", "Épico"]);
  assert.equal(groups[0].entries[0].itemLabel, "Espada Solar · Equipamento · sword");
});

test("different drop conditions stay visible inside one activity row", () => {
  const groups = groupCatalogSources([
    { item: item("Raro"), sources: [source()] },
    { item: item("Épico"), sources: [source({ chance: "4% base", requirement: "guilda nível 12+" })] },
    { item: item("Lendário"), sources: [source({ quantity: "1–2 unidades" })] },
  ]);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].entries.length, 1);
  assert.deepEqual(groups[0].entries[0].rarities, ["Raro", "Épico", "Lendário"]);
  assert.deepEqual(groups[0].entries[0].variants.map((variant) => [
    variant.source.requirement, variant.source.chance, variant.source.quantity,
  ]), [
    ["guilda nível 5+", "10% base", "1 unidade"],
    ["guilda nível 12+", "4% base", "1 unidade"],
    ["guilda nível 5+", "10% base", "1–2 unidades"],
  ]);
});

test("gathering level bands for one material remain consultable in one collection row", () => {
  const groups = groupCatalogSources([
    { item: item("Comum", { item_type: "material", item_type_label: "Material", family: "wood" }), sources: [source({
      filter_key: "gathering", type: "gathering", label: "Coleta", name: "Coleta",
      requirement: "Coleta de madeira; níveis da guilda 1–10", minimum_guild_level: 1,
    })] },
    { item: item("Raro", { item_type: "material", item_type_label: "Material", family: "wood", tier: 4, item_level: 45, level_band: "41-50" }), sources: [source({
      filter_key: "gathering", type: "gathering", label: "Coleta", name: "Coleta",
      requirement: "Coleta de madeira; níveis da guilda 41–50", minimum_guild_level: 41,
    })] },
  ]);

  assert.equal(groups.length, 1);
  assert.equal(groups[0].entries.length, 1);
  assert.deepEqual(groups[0].entries[0].rarities, ["Comum", "Raro"]);
  assert.deepEqual(groups[0].entries[0].variants.map((variant) => [
    variant.source.minimum_guild_level, variant.source.requirement,
  ]), [
    [1, "Coleta de madeira; níveis da guilda 1–10"],
    [41, "Coleta de madeira; níveis da guilda 41–50"],
  ]);
});
