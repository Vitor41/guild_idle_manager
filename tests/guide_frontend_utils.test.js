const test = require("node:test");
const assert = require("node:assert/strict");
const { filterCatalog, findNormalizedMatch } = require("../app/static/js/guide-utils.js");

test("global guide search ignores case and repeated whitespace and returns original text range", () => {
  const text = "Coleta   de   MINÉRIO — tier 4";
  const match = findNormalizedMatch(text, "  coleta de minério  ");
  assert.ok(match);
  assert.equal(text.slice(match.index, match.index + match.length), "Coleta   de   MINÉRIO");
});

test("global guide search returns no match for empty or absent terms", () => {
  assert.equal(findNormalizedMatch("Guia de equipamentos", "   "), null);
  assert.equal(findNormalizedMatch("Guia de equipamentos", "docas"), null);
});

test("catalog combines name, type, family, band, tier, and source filters", () => {
  const items = [
    { id: 1, name: "Minério Antigo", item_type: "material", family: "ore", level_band: "20-29", tier: 2,
      sources: [{ label: "Masmorras", filter_key: "dungeon_or_boss" }, { label: "Docas", filter_key: "docks_possible_offer" }] },
    { id: 2, name: "Minério Raro", item_type: "equipment", family: "ore", level_band: "20-29", tier: 2,
      sources: [{ label: "Docas", filter_key: "docks_possible_offer" }] },
    { id: 3, name: "Erva Clara", item_type: "material", family: "herb", level_band: "1-9", tier: 1, sources: [] },
  ];

  const result = filterCatalog(items, { name: "MINÉRIO", type: "material", family: "ore", band: "20-29", tier: "2", source: "dungeon_or_boss" });
  assert.equal(result.length, 1);
  assert.equal(result[0].item.id, 1);
  assert.deepEqual(result[0].sources.map((source) => source.filter_key), ["dungeon_or_boss"]);
});

test("source filters distinguish commerce from drops and expose source-less items only in all/none", () => {
  const items = [
    { id: 1, name: "Minério", item_type: "material", family: "ore", level_band: "20-29", tier: 2,
      sources: [{ label: "Docas", filter_key: "docks_possible_offer" }] },
    { id: 2, name: "Erva", item_type: "material", family: "herb", level_band: "1-9", tier: 1, sources: [] },
  ];

  assert.deepEqual(filterCatalog(items, { source: "mission" }), []);
  assert.deepEqual(filterCatalog(items, { source: "docks_possible_offer" }).map(({ item }) => item.id), [1]);
  assert.equal(filterCatalog(items, { source: "none" })[0].sources[0].label, "Sem fonte disponível");
  assert.equal(filterCatalog(items, { source: "all" }).length, 2);
});
