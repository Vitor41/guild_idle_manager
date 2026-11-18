import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../../app/static/js/gathering-cycle.js", import.meta.url), "utf8");

test("catalog recovery refreshes the saved target label and resumes the live status", async () => {
  const warehouseLabel = { textContent: "0 / 0" };
  const warehouseProgress = { max: 0, value: 0 };
  const targetLabel = { textContent: "Alvo salvo (indisponível):" };
  const targetValue = { textContent: "Madeira antiga · Rara" };
  const status = { textContent: "Indisponível · catálogo · Lina" };
  const catalogWarning = { hidden: false };
  const capacityHelp = { hidden: false };
  const cycle = { hidden: true };
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
  assert.equal(catalogWarning.hidden, true);
  assert.equal(capacityHelp.hidden, true);
  assert.equal(cycle.hidden, false);
});
