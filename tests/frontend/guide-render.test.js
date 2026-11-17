import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const guideUtils = require("../../app/static/js/guide-utils.js");
const guideScript = await readFile(new URL("../../app/static/js/guide.js", import.meta.url), "utf8");

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.dataset = {};
    this.hidden = false;
    this.attributes = {};
    this._textContent = "";
  }

  get textContent() {
    return this._textContent + this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this._textContent = String(value ?? "");
    this.children = [];
  }

  append(...elements) { this.children.push(...elements); }
  replaceChildren(...elements) { this._textContent = ""; this.children = [...elements]; }
  addEventListener() {}
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
}

async function renderCatalog(items) {
  const rowsNode = new FakeElement("tbody");
  const statusNode = new FakeElement("p");
  const errorNode = new FakeElement("div");
  const emptyNode = new FakeElement("p");
  const tableWrap = new FakeElement("div");
  const catalogNodes = new Map([
    ["[data-guide-catalog-rows]", rowsNode],
    ["[data-guide-catalog-status]", statusNode],
    ["[data-guide-catalog-error]", errorNode],
    ["[data-guide-catalog-empty]", emptyNode],
    ["[data-guide-catalog-wrap]", tableWrap],
  ]);
  const catalogRoot = {
    querySelector: (selector) => catalogNodes.get(selector) || null,
    querySelectorAll: () => [],
  };
  const root = {
    querySelector: (selector) => selector === "#equipamentos-materiais" ? catalogRoot : null,
  };
  const document = {
    querySelector: (selector) => selector === ".game-guide" ? root : null,
    createElement: (tagName) => new FakeElement(tagName),
  };
  const context = {
    document,
    window: { GuideUtils: guideUtils },
    fetch: async () => ({
      ok: true,
      json: async () => ({ items, filters: { sources: [], families: [], level_bands: [] } }),
    }),
    console,
  };

  vm.runInNewContext(guideScript, context);
  await new Promise((resolve) => setTimeout(resolve, 0));
  return rowsNode.children.filter((row) => row.dataset.guideCatalogRow !== undefined);
}

function gatheringItem(id, rarity, minimumGuildLevel, band, chance) {
  return {
    id, name: "Madeira Arcana", item_type: "material", item_type_label: "Material",
    family: "wood", equipment_slot: null, level_band: band, rarity, icon: null,
    sources: [{
      filter_key: "gathering", type: "gathering", label: "Coleta", name: "Coleta",
      requirement: `Coleta de madeira; níveis da guilda ${band}`,
      recommendation: "", chance, quantity: "1 unidade", price: null, condition: "",
      minimum_guild_level: minimumGuildLevel,
    }],
  };
}

test("rendered collection requirement hides the level band for a single source", async () => {
  const [row] = await renderCatalog([
    gatheringItem(1, "Comum", 1, "1–10", "10% base"),
  ]);
  const requirement = row.children.find((cell) => cell.dataset.label === "Requisito");

  assert.equal(requirement.textContent, "A partir da guilda Nv. 1");
  assert.doesNotMatch(row.textContent, /níveis da guilda 1–10/);
  assert.match(row.textContent, /10% base/);
});

test("rendered collection requirement hides all bands while retaining variant data", async () => {
  const [row] = await renderCatalog([
    gatheringItem(1, "Comum", 1, "1–10", "10% base"),
    gatheringItem(2, "Raro", 41, "41–50", "4% base"),
  ]);
  const requirement = row.children.find((cell) => cell.dataset.label === "Requisito");

  assert.equal(requirement.textContent, "A partir da guilda Nv. 1");
  assert.doesNotMatch(row.textContent, /níveis da guilda (?:1–10|41–50)/);
  assert.match(row.textContent, /10% base/);
  assert.match(row.textContent, /4% base/);
  assert.match(row.textContent, /Comum/);
  assert.match(row.textContent, /Raro/);
});

test("rendered non-collection requirements remain unchanged", async () => {
  const items = [{
    id: 3, name: "Espada do Dragão", item_type: "equipment", item_type_label: "Equipamento",
    family: "", equipment_slot: "sword", level_band: "1-10", rarity: "Raro", icon: null,
    sources: [{
      filter_key: "drop", type: "dungeon_or_boss", label: "Chefes", name: "Dragão do Norte",
      requirement: "Guilda Nv. 5+", recommendation: "", chance: "12% base",
      quantity: "1 unidade", price: null, condition: "",
    }],
  }];
  const [row] = await renderCatalog(items);
  const requirement = row.children.find((cell) => cell.dataset.label === "Requisito");

  assert.equal(requirement.textContent, "Guilda Nv. 5+");
  assert.match(row.textContent, /Guilda Nv\. 5\+/);
  assert.match(row.textContent, /Dragão do Norte/);
});
