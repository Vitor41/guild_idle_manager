import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const root = new URL("../../", import.meta.url);
const workshopSource = await readFile(new URL("app/static/js/workshop-supply.js", root), "utf8");
const regionalSource = await readFile(new URL("app/static/js/regional-supply.js", root), "utf8");
const mainSource = await readFile(new URL("app/static/js/main.js", root), "utf8");

function makeProgressBox({ startsAt, endsAt, workshop = false }) {
  const bar = {
    value: 0,
    textContent: "0%",
    dataset: workshop ? { startsAt, endsAt } : {},
  };
  const time = { dataset: { ...(workshop ? {} : { startsAt }), endsAt }, textContent: "calculando..." };
  const status = { textContent: workshop ? "Produzindo 100 Kits de Suprimentos" : "Suprimento em preparo" };
  return {
    bar,
    time,
    status,
    node: {
      dataset: {},
      querySelector(selector) {
        if (selector === "time[data-ends-at]") return time;
        if (selector === "progress") return bar;
        if (selector === "strong") return status;
        return null;
      },
    },
  };
}

function makePage(nowMs) {
  const intervals = [];
  const workshopBox = makeProgressBox({
    startsAt: "2026-11-25T12:00:00",
    endsAt: "2026-11-25T18:00:00Z",
    workshop: true,
  });
  const regionalBox = makeProgressBox({
    startsAt: "2026-11-25T12:00:00Z",
    endsAt: "2026-11-25T18:00:00Z",
  });
  const checkbox = { value: "worker-1", checked: true, name: "mercenary_ids", dataset: {}, addEventListener() {} };
  const supply = { checked: true, disabled: true, addEventListener() {} };
  const summary = { textContent: "Preparo já registrado." };
  const supplyLabel = { textContent: "Suprimento em preparo", closest: () => ({ classList: { add() {} } }) };
  const preparedStatus = { textContent: "Equipe preparada pré-selecionada." };
  const preparedButton = { disabled: true, textContent: "Aguardando preparo", dataset: { readyLabel: "Participar com suprimento preparado" } };
  const withoutSupplyButton = { disabled: false, dataset: { startWithoutSupply: "" } };
  const formListeners = {};
  const regionalForm = {
    dataset: {
      supplyQuoteUrl: "/regional/offers/1/supply-quote",
      preparedMercenaryIds: "worker-1",
      preparedTeamAvailable: "true",
      preparedTeamValid: "true",
      preparedTeamCanStart: "true",
    },
    addEventListener(type, listener) { formListeners[type] = listener; },
    querySelector(selector) {
      if (selector === 'input[name="supply"]') return supply;
      if (selector === ".supply-preparation small") return summary;
      if (selector === 'button[name="supply_mode"][value="prepared"]') return preparedButton;
      if (selector === 'fieldset[data-min-party-size]') return { dataset: { minPartySize: "1", maxPartySize: "2" } };
      if (selector === "[data-start-without-supply]") return withoutSupplyButton;
      if (selector === "[data-prepared-team-status]") return preparedStatus;
      if (selector === "[data-supply-preparation-label]") return supplyLabel;
      return null;
    },
    querySelectorAll(selector) {
      if (selector.startsWith('input[name="mercenary_ids"]')) return selector.endsWith(":checked") ? [checkbox] : [checkbox];
      if (selector === "[data-reinforcement-badge]") return [];
      if (selector === 'select[name="run_multiplier"]') return [];
      return [];
    },
  };
  workshopBox.node.closest = () => null;
  regionalBox.node.closest = (selector) => selector === "form" ? regionalForm : null;
  const boxes = [workshopBox.node, regionalBox.node];
  const document = {
    addEventListener() {},
    querySelectorAll(selector) {
      if (selector === ".workshop-batch-form") return [];
      if (selector === "[data-workshop-progress]") return [workshopBox.bar];
      if (selector === 'form[data-supply-quote-url] .supply-preparation-progress') return [regionalBox.node];
      if (selector === 'form[data-supply-quote-url]') return [regionalForm];
      return [];
    },
  };
  const context = vm.createContext({
    Date: class extends Date { static now() { return nowMs; } },
    document,
    window: {
      setInterval(callback, milliseconds) { intervals.push({ callback, milliseconds }); return intervals.length; },
      clearInterval() {},
      setTimeout,
      crypto: { randomUUID: () => "ownership-test" },
    },
    setInterval(callback, milliseconds) { intervals.push({ callback, milliseconds }); return intervals.length; },
    FormData: class { constructor() {} },
    URLSearchParams,
    Event,
  });
  const parserStart = mainSource.indexOf("window.parseUtcTimestamp =");
  const parserEnd = mainSource.indexOf("\n};", parserStart) + 3;
  assert.ok(parserStart >= 0 && parserEnd > parserStart, "the actual main.js UTC parser is available");
  vm.runInContext(mainSource.slice(parserStart, parserEnd), context, { filename: "main.js:parseUtcTimestamp" });
  context.window.initializeWorkshopSupplyControls = undefined;
  vm.runInContext(workshopSource, context, { filename: "workshop-supply.js" });
  vm.runInContext(regionalSource, context, { filename: "regional-supply.js" });
  const partialRoot = {
    querySelectorAll(selector) {
      if (selector === ".workshop-batch-form") return [];
      if (selector === "[data-workshop-progress]") return [workshopBox.bar];
      if (selector === 'form[data-supply-quote-url] .supply-preparation-progress') return [regionalBox.node];
      if (selector === 'form[data-supply-quote-url]') return [regionalForm];
      return [];
    },
  };
  return { context, intervals, partialRoot, workshopBox, regionalBox, preparedButton, formListeners };
}

test("workshop and regional preparation timers keep their own progress on direct and partial initialization", () => {
  const start = Date.parse("2026-11-25T12:00:00Z");
  const page = makePage(start + 3 * 60 * 60 * 1000);
  page.context.window.initializeRegionalSupply(page.partialRoot);
  page.context.window.initializeWorkshopSupplyControls(page.partialRoot);

  assert.equal(page.workshopBox.bar.value, 50, "the workshop uses its six-hour production span at UTC-3");
  assert.equal(page.workshopBox.status.textContent, "Produzindo 100 Kits de Suprimentos", "regional initialization does not relabel the workshop batch");
  assert.equal(page.regionalBox.bar.value, 50, "the regional preparation keeps its own six-hour span");
  assert.equal(page.regionalBox.status.textContent, "Suprimento em preparo");
  assert.equal(page.preparedButton.disabled, true, "the server-backed prepared start remains unavailable before due time");
  assert.equal(page.intervals.length, 2, "direct plus partial initialization does not add duplicate timers");

  page.context.Date.now = () => start + 6 * 60 * 60 * 1000;
  for (const interval of page.intervals) interval.callback();
  assert.equal(page.workshopBox.bar.value, 100);
  assert.equal(page.workshopBox.status.textContent, "Produzindo 100 Kits de Suprimentos");
  assert.equal(page.regionalBox.bar.value, 100);
  assert.equal(page.regionalBox.status.textContent, "Preparação concluída · pronta para iniciar");
  assert.equal(page.preparedButton.disabled, false, "the prepared participation control follows the completed preparation");
});
