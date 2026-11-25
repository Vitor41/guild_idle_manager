import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../../app/static/js/gathering-cycle.js", import.meta.url), "utf8");

function makeClassList(initial) {
  const classes = new Set(initial);
  return {
    add(name) { classes.add(name); },
    remove(...names) { names.forEach((name) => classes.delete(name)); },
    contains(name) { return classes.has(name); },
  };
}

test("polling synchronizes gathering states, preserved progress, and warehouse capacity", async () => {
  const warehouseLabel = { textContent: "90 / 100" };
  const warehouseProgress = {
    max: 100,
    value: 90,
    attributes: new Map([["aria-label", "Armazém: 90 de 100"]]),
    setAttribute(name, value) { this.attributes.set(name, value); },
  };
  const capacityState = { hidden: true };
  const targetLabel = { textContent: "Alvo desta designação:" };
  const targetValue = { textContent: "Madeira · Comum" };
  let statusText = "Em produção · Lina";
  let statusWrites = 0;
  const status = {
    classList: makeClassList(["evolution-status--active"]),
    get textContent() { return statusText; },
    set textContent(value) {
      if (value !== statusText) statusWrites += 1;
      statusText = value;
    },
  };
  const catalogWarning = { hidden: true };
  const capacityHelp = { hidden: true };
  const progress = { value: 12 };
  const remaining = { textContent: "48" };
  const cycle = {
    hidden: false,
    isConnected: true,
    dataset: { progressSeconds: "12" },
    querySelector(selector) {
      return { progress, "[data-gathering-remaining]": remaining }[selector] ?? null;
    },
  };
  const card = {
    dataset: { gatheringAssigned: "true", gatheringCard: "wood" },
    querySelector(selector) {
      return {
        "[data-gathering-status]": status,
        "[data-gathering-catalog-warning]": catalogWarning,
        "[data-gathering-capacity-help]": capacityHelp,
        "[data-gathering-cycle]": cycle,
        "[data-gathering-target-label]": targetLabel,
        "[data-gathering-target-value]": targetValue,
      }[selector] ?? null;
    },
  };
  const page = {
    dataset: { gatheringStatusUrl: "/gathering/status" },
    isConnected: true,
    querySelector(selector) {
      return {
        "[data-gathering-warehouse-label]": warehouseLabel,
        "[data-gathering-warehouse-progress]": warehouseProgress,
        "[data-gathering-capacity-state]": capacityState,
      }[selector] ?? null;
    },
    querySelectorAll(selector) {
      if (selector === "[data-gathering-family-count]") return [];
      if (selector === "[data-gathering-card]") return [card];
      return [];
    },
  };
  const document = {
    visibilityState: "visible",
    hidden: false,
    addEventListener() {},
    querySelector: (selector) => selector === "[data-gathering-status-url]" ? page : null,
    querySelectorAll: (selector) => selector === "[data-gathering-cycle]" ? [cycle] : [],
  };
  const intervals = [];
  const window = {
    matchMedia: () => ({ matches: true }),
    setInterval(callback) { intervals.push(callback); return intervals.length; },
    clearInterval() {},
  };
  const states = [
    {
      warehouse: { used: 90, capacity: 100 },
      inventory_by_family: {},
      assignments: { wood: { progress_seconds: 20, capacity_paused: false, catalog_unavailable: false, worker: "Lina", target_item_name: "Madeira", target_item_rarity: "common" } },
    },
    {
      warehouse: { used: 100, capacity: 100 },
      inventory_by_family: {},
      assignments: { wood: { progress_seconds: 23, capacity_paused: true, catalog_unavailable: false, worker: "Lina", target_item_name: "Madeira", target_item_rarity: "common" } },
    },
    {
      warehouse: { used: 100, capacity: 100 },
      inventory_by_family: {},
      assignments: { wood: { progress_seconds: 23, capacity_paused: true, catalog_unavailable: false, worker: "Lina", target_item_name: "Madeira", target_item_rarity: "common" } },
    },
    {
      warehouse: { used: 95, capacity: 120 },
      inventory_by_family: {},
      assignments: { wood: { progress_seconds: 41, capacity_paused: false, catalog_unavailable: false, worker: "Lina", target_item_name: "Madeira", target_item_rarity: "common" } },
    },
  ];
  const fetch = async () => ({ ok: true, json: async () => states.shift() });

  vm.runInNewContext(source, { document, window, fetch });
  window.initializeGatheringCycles();
  const poll = intervals[0];

  await poll();
  assert.equal(status.classList.contains("evolution-status--active"), true);
  assert.equal(cycle.hidden, false);
  assert.equal(progress.value, 20);

  await poll();
  assert.equal(status.textContent, "Pausada · Armazém cheio · Lina");
  assert.equal(status.classList.contains("evolution-status--paused"), true);
  assert.equal(status.classList.contains("evolution-status--active"), false);
  assert.equal(cycle.hidden, true);
  assert.equal(capacityHelp.hidden, false);
  assert.equal(progress.value, 23, "paused progress remains authoritative and does not advance locally");
  assert.equal(warehouseLabel.textContent, "100 / 100");
  assert.equal(warehouseProgress.max, 100);
  assert.equal(warehouseProgress.value, 100);
  assert.equal(warehouseProgress.attributes.get("aria-label"), "Armazém: 100 de 100");
  assert.equal(capacityState.hidden, false);
  const writesWhilePaused = statusWrites;

  await poll();
  assert.equal(statusWrites, writesWhilePaused, "unchanged polling does not repeat the status announcement");
  assert.equal(capacityState.hidden, false);

  await poll();
  assert.equal(status.textContent, "Em produção · Lina");
  assert.equal(status.classList.contains("evolution-status--active"), true);
  assert.equal(status.classList.contains("evolution-status--paused"), false);
  assert.equal(cycle.hidden, false);
  assert.equal(capacityHelp.hidden, true);
  assert.equal(progress.value, 41);
  assert.equal(warehouseLabel.textContent, "95 / 120");
  assert.equal(warehouseProgress.max, 120);
  assert.equal(warehouseProgress.value, 95);
  assert.equal(warehouseProgress.attributes.get("aria-label"), "Armazém: 95 de 120");
  assert.equal(capacityState.hidden, true);
});

test("catalog recovery refreshes the saved target label and resumes the live status", async () => {
  const warehouseLabel = { textContent: "0 / 0" };
  const warehouseProgress = { max: 0, value: 0, setAttribute() {} };
  const targetLabel = { textContent: "Alvo salvo (indisponível):" };
  const targetValue = { textContent: "Madeira antiga · Rara" };
  const status = {
    textContent: "Indisponível · catálogo · Lina",
    classList: makeClassList(["evolution-status--muted"]),
  };
  const catalogWarning = { hidden: false };
  const capacityHelp = { hidden: false };
  const cycle = { hidden: true, dataset: { progressSeconds: "10" } };
  const card = {
    dataset: { gatheringAssigned: "true", gatheringCard: "wood" },
    querySelector(selector) {
      return {
        "[data-gathering-status]": status,
        "[data-gathering-catalog-warning]": catalogWarning,
        "[data-gathering-capacity-help]": capacityHelp,
        "[data-gathering-cycle]": cycle,
        "[data-gathering-target-label]": targetLabel,
        "[data-gathering-target-value]": targetValue,
      }[selector] ?? null;
    },
  };
  const page = {
    dataset: { gatheringStatusUrl: "/gathering/status" },
    isConnected: true,
    querySelector(selector) {
      return {
        "[data-gathering-warehouse-label]": warehouseLabel,
        "[data-gathering-warehouse-progress]": warehouseProgress,
      }[selector] ?? null;
    },
    querySelectorAll(selector) {
      if (selector === "[data-gathering-family-count]") return [];
      if (selector === "[data-gathering-card]") return [card];
      return [];
    },
  };
  const document = {
    visibilityState: "visible",
    addEventListener() {},
    querySelector: (selector) => selector === "[data-gathering-status-url]" ? page : null,
    querySelectorAll: () => [],
  };
  const intervals = [];
  const window = {
    matchMedia: () => ({ matches: true }),
    setInterval(callback) { intervals.push(callback); return intervals.length; },
    clearInterval() {},
  };
  const fetch = async () => ({
    ok: true,
    json: async () => ({
      warehouse: { used: 6, capacity: 100 },
      inventory_by_family: {},
      assignments: {
        wood: {
          progress_seconds: 30,
          capacity_paused: false,
          catalog_unavailable: false,
          worker: "Lina",
          target_item_name: "Madeira",
          target_item_rarity: "common",
        },
      },
    }),
  });

  vm.runInNewContext(source, { document, window, fetch });
  await intervals[0]();

  assert.equal(targetLabel.textContent, "Alvo desta designação:");
  assert.equal(targetValue.textContent, "Madeira · Comum");
  assert.equal(status.textContent, "Em produção · Lina");
  assert.equal(status.classList.contains("evolution-status--active"), true);
  assert.equal(catalogWarning.hidden, true);
  assert.equal(capacityHelp.hidden, true);
  assert.equal(cycle.hidden, false);
});
