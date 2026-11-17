import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const scriptPath = fileURLToPath(new URL("../../app/static/js/regional-supply.js", import.meta.url));
const regionalSupplyScript = readFileSync(scriptPath, "utf8");

function makeEnvironment({ prepared, fetchImpl }) {
  const formListeners = {};
  const checkboxes = [
    { value: "101", checked: true, type: "checkbox", dataset: {}, listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; } },
    { value: "202", checked: false, type: "checkbox", dataset: {}, listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; } },
  ];
  const supply = {
    checked: true,
    disabled: Boolean(prepared),
    listeners: {},
    addEventListener(name, fn) { this.listeners[name] = fn; },
    focus() { this.focused = true; },
  };
  const summary = { textContent: "Cotação salva do preparo." };
  const status = { textContent: "Equipe preparada pré-selecionada." };
  const preparedButton = prepared ? { name: "supply_mode", value: "prepared", disabled: false } : null;
  const prepareButton = prepared ? null : { disabled: false };
  const form = {
    dataset: {
      regionalSupplyInitialized: "false",
      supplyQuoteUrl: "/regional/offers/1/supply-quote",
      preparedMercenaryIds: prepared ? "101" : "",
      preparedTeamAvailable: "true",
      preparedTeamValid: "true",
    },
    querySelector(selector) {
      if (selector === 'input[name="supply"]') return supply;
      if (selector === ".supply-preparation small") return summary;
      if (selector === 'button[name="supply_mode"][value="prepared"]') return preparedButton;
      if (selector === "[data-prepared-team-status]") return status;
      if (selector === "[data-prepare-action]") return prepareButton;
      return null;
    },
    querySelectorAll(selector) {
      if (selector.startsWith('input[name="mercenary_ids"]')) {
        return selector.endsWith(":checked") ? checkboxes.filter((input) => input.checked) : checkboxes;
      }
      if (selector === 'select[name="run_multiplier"]') return [];
      return [];
    },
    addEventListener(name, fn) { formListeners[name] = fn; },
  };
  const root = {
    querySelectorAll(selector) {
      if (selector === ".supply-preparation-progress") return [];
      if (selector === "form[data-supply-quote-url]") return [form];
      return [];
    },
  };
  class FormDataStub {
    constructor(_form) {}
    *[Symbol.iterator]() { return; }
  }
  const context = vm.createContext({
    window: {
      crypto: { randomUUID: () => "regional-supply-test" },
      setInterval,
      clearInterval,
    },
    document: { addEventListener() {} },
    fetch: fetchImpl,
    FormData: FormDataStub,
    URLSearchParams,
    Event,
  });
  vm.runInContext(regionalSupplyScript, context, { filename: "regional-supply.js" });
  context.window.initializeRegionalSupply(root);
  return { checkboxes, formListeners, form, preparedButton, prepareButton, status, supply, summary };
}

test("prepared start does not request inventory or get canceled by a stale negative quote", async () => {
  let quoteRequests = 0;
  const page = makeEnvironment({
    prepared: true,
    fetchImpl: async () => {
      quoteRequests += 1;
      await new Promise((resolve) => setTimeout(resolve, 20));
      return { ok: false, json: async () => ({ available: false, reason: "Sem kits." }) };
    },
  });

  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(quoteRequests, 0);
  assert.match(page.status.textContent, /bônus do suprimento está pronto/);

  page.checkboxes[1].checked = true;
  page.checkboxes[1].listeners.change();
  assert.match(page.status.textContent, /Há reforços selecionados/);
  assert.match(page.status.textContent, /Iniciar sem suprimento/);

  let prevented = false;
  page.formListeners.submit({
    submitter: page.preparedButton,
    preventDefault() { prevented = true; },
  });
  assert.equal(prevented, false);
});

test("a new preparation still blocks a selected supply after a negative quote", async () => {
  const page = makeEnvironment({
    prepared: false,
    fetchImpl: async () => ({
      ok: false,
      json: async () => ({ available: false, reason: "Sem kits." }),
    }),
  });

  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(page.prepareButton.disabled, true);
  assert.match(page.summary.textContent, /Sem kits/);

  let prevented = false;
  page.formListeners.submit({
    submitter: page.prepareButton,
    preventDefault() { prevented = true; },
  });
  assert.equal(prevented, true);
  assert.equal(page.supply.focused, true);
});
