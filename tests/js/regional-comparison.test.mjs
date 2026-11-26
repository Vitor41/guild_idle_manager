import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const scriptPath = fileURLToPath(new URL("../../app/static/js/main.js", import.meta.url));
const mainSource = readFileSync(scriptPath, "utf8");
const comparisonFunction = mainSource.match(/^function initializeRegionalComparison\([\s\S]*?^\}/m)?.[0];
assert.ok(comparisonFunction, "regional comparison initializer is present");

test("polling keeps rarity labels localized", async () => {
  const cells = new Map(["tiers", "wealth", "roster", "contracts", "dungeons", "bosses", "successes-failures", "event-wins"]
    .map((field) => [field, { textContent: "valor antigo" }]));
  const row = {
    dataset: { guildStateId: "10" },
    querySelector(selector) {
      const field = selector.match(/data-comparison-field="([^"]+)"/)?.[1];
      return cells.get(field) || null;
    },
  };
  const tableBody = {
    isConnected: true,
    dataset: { refreshUrl: "/regional/regions/vale-fronteira/comparison" },
    querySelectorAll(selector) { return selector === "tr[data-guild-state-id]" ? [row] : []; },
  };
  const root = { querySelector(selector) { return selector === "[data-regional-comparison]" ? tableBody : null; } };
  const window = { setInterval() { return 1; }, clearInterval() {} };
  const document = { visibilityState: "visible" };
  const fetch = async () => ({
    ok: true,
    json: async () => ({
      guilds: {
        "10": {
          wealth: 25,
          roster: 7,
          tier_counts: { common: 4, rare: 3 },
          tier_counts_display: { Comum: 4, Raro: 3 },
          results: { contracts: 1, dungeons: 2, bosses: 0, successes: 2, failures: 1 },
          event_wins: 0,
        },
      },
    }),
  });
  const context = vm.createContext({ window, document, fetch, root });
  vm.runInContext(`let regionalComparisonInterval = null;\n${comparisonFunction}\ninitializeRegionalComparison(root);`, context);
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(cells.get("tiers").textContent, "Comum 4 · Raro 3");
  assert.doesNotMatch(cells.get("tiers").textContent, /common|rare/);
});
