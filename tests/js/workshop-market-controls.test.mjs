import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const root = new URL("../../", import.meta.url);
const workshopSource = await readFile(new URL("app/static/js/workshop-supply.js", root), "utf8");
const marketMaxSource = await readFile(new URL("app/static/js/market-max.js", root), "utf8");
const mainSource = await readFile(new URL("app/static/js/main.js", root), "utf8");
const baseTemplate = await readFile(new URL("app/templates/base.html", root), "utf8");
const workshopTemplate = await readFile(new URL("app/templates/workshops/index.html", root), "utf8");

function makeEventTarget() {
  const listeners = new Map();
  return {
    addEventListener(type, listener) { listeners.set(type, [...(listeners.get(type) || []), listener]); },
    fire(type, event = {}) { for (const listener of listeners.get(type) || []) listener(event); },
    listenerCount(type) { return (listeners.get(type) || []).length; },
  };
}

function makeWorkshopForm({ value = "1", maximum = "5", serverDisabled = false } = {}) {
  const input = Object.assign(makeEventTarget(), { value, min: "1", max: maximum, step: "1", disabled: false });
  input.dispatchEvent = (event) => input.fire(event.type, event);
  const estimate = { dataset: { meatPerKit: "3", herbsPerKit: "2", secondsPerKit: "25" }, textContent: "" };
  const submit = { dataset: {}, disabled: serverDisabled };
  const maxButton = Object.assign(makeEventTarget(), {});
  const form = {
    dataset: {},
    querySelector(selector) {
      return ({
        "#workshop-quantity": input,
        "[data-workshop-estimate]": estimate,
        "[data-workshop-submit]": submit,
        "[data-workshop-max]": maxButton,
      })[selector] || null;
    },
  };
  return { form, input, estimate, submit, maxButton };
}

function loadWorkshop(document) {
  const intervals = [];
  const context = vm.createContext({
    document,
    window: {
      setInterval(callback, milliseconds) { intervals.push({ callback, milliseconds }); return intervals.length; },
    },
    Event: class { constructor(type, options = {}) { this.type = type; Object.assign(this, options); } },
  });
  vm.runInContext(workshopSource, context, { filename: "workshop-supply.js" });
  return { initialize: context.window.initializeWorkshopSupplyControls, intervals };
}

test("workshop controls initialize after direct and partial navigation and reject invalid quantities", () => {
  const first = makeWorkshopForm();
  const directForms = [first.form];
  const document = { querySelectorAll: (selector) => selector === ".workshop-batch-form" ? directForms : [] };
  const { initialize, intervals } = loadWorkshop(document);
  assert.equal(first.input.listenerCount("input"), 1, "direct page loading initializes the controls");
  const firstRoot = { querySelectorAll: (selector) => selector === ".workshop-batch-form" ? [first.form] : [] };

  initialize(firstRoot);
  initialize(firstRoot);
  assert.equal(first.input.listenerCount("input"), 1, "reinitializing the same content does not duplicate handlers");
  assert.equal(first.submit.disabled, false);
  assert.match(first.estimate.textContent, /3 Carnes \+ 2 Ervas/);
  assert.match(first.estimate.textContent, /25 segundo/);
  assert.equal(intervals.length, 1, "the progress clock is installed only once");

  first.input.value = "";
  first.input.fire("input");
  assert.equal(first.submit.disabled, true);
  assert.match(first.estimate.textContent, /quantidade válida/);
  assert.doesNotMatch(first.estimate.textContent, /Custo:/);

  for (const invalid of ["0", "1.5", "0.5", "6"]) {
    first.input.value = invalid;
    first.input.fire("input");
    assert.equal(first.submit.disabled, true, `${invalid} is rejected`);
  }
  first.input.value = "2";
  first.input.fire("input");
  assert.equal(first.submit.disabled, false);
  assert.match(first.estimate.textContent, /6 Carnes \+ 4 Ervas/);
  assert.match(first.estimate.textContent, /50 segundo/);

  first.maxButton.fire("click");
  assert.equal(first.input.value, "5");
  assert.match(first.estimate.textContent, /15 Carnes \+ 10 Ervas/);

  const serverBlocked = makeWorkshopForm({ serverDisabled: true });
  const secondRoot = { querySelectorAll: (selector) => selector === ".workshop-batch-form" ? [serverBlocked.form] : [] };
  initialize(secondRoot);
  assert.equal(serverBlocked.submit.disabled, true, "server-rendered unavailability stays authoritative");
  assert.equal(intervals.length, 1, "partial navigation reuses the existing timer");
});

test("market MAX uses delegated click handling for forms inserted by partial navigation", () => {
  const listeners = new Map();
  const document = { addEventListener(type, listener) { listeners.set(type, listener); } };
  vm.runInNewContext(marketMaxSource, vm.createContext({ document, Event: class { constructor(type, options = {}) { this.type = type; Object.assign(this, options); } } }));

  let inputEvents = 0;
  const quantity = { value: "1", dispatchEvent(event) { if (event.type === "input") inputEvents += 1; } };
  const form = { querySelector: (selector) => selector === "[data-market-quantity]" ? quantity : null };
  const button = { disabled: false, dataset: { max: "7" }, closest: (selector) => selector === "form" ? form : null };
  const insertedAfterNavigationTarget = { closest: (selector) => selector === "[data-market-fill-max]" ? button : null };

  listeners.get("click")({ target: insertedAfterNavigationTarget });
  assert.equal(quantity.value, "7");
  assert.equal(inputEvents, 1);
});

test("the in-scope page controls have explicit direct and partial initialization paths", () => {
  assert.doesNotMatch(workshopTemplate, /<script(?:\s|>)/i, "workshop behavior is not embedded in replaceable page HTML");
  assert.match(baseTemplate, /\/js\/workshop-supply\.js/);
  assert.match(baseTemplate, /\/js\/market-max\.js/);
  assert.match(mainSource, /window\.initializeWorkshopSupplyControls\?\.\(currentMain\)/);
  assert.match(mainSource, /initializeMarketEstimates\(currentMain\)/);
  assert.match(mainSource, /initializeClassGuideIndex\(currentMain\)/);
  assert.match(mainSource, /initializeBuildingResetDialogs\?\.\(currentMain\)/);
  assert.match(mainSource, /initializeEquipmentDetails\?\.\(currentMain\)/);
  assert.match(mainSource, /initializeSalvagePreviews\(\);/);
  assert.match(mainSource, /event\.target\.matches\("\[data-dock-quantity\]"\)/);
});

test("market sale estimate validates integer bounds and preserves server-side stock and slot blocks", async () => {
  const format = mainSource.match(/^const formatMarketEstimate = \(seconds\) => \{[\s\S]*?^\};/m)?.[0];
  const update = mainSource.match(/^function updateMarketEstimate\(node\) \{[\s\S]*?^\}/m)?.[0];
  assert.ok(format && update);

  function run({ initialDisabled = false } = {}) {
    const input = { value: "1", min: "1", max: "5", step: "1" };
    const button = { dataset: {}, disabled: initialDisabled };
    const form = { querySelector: (selector) => selector === "[data-market-quantity]" ? input : selector === ".market-sell-button" ? button : null };
    const node = { dataset: { durationBase: "20", timeReduction: "0" }, textContent: "", closest: () => form };
    const helper = new Function(`${format}\n${update}\nreturn updateMarketEstimate;`)();
    return { helper, input, button, node };
  }

  const { helper, input, button, node } = run();
  for (const invalid of ["", "0", "1.5", "6"]) {
    input.value = invalid;
    helper(node);
    assert.equal(button.disabled, true, `${JSON.stringify(invalid)} disables selling`);
    assert.match(node.textContent, /quantidade válida/);
  }
  input.value = "2";
  helper(node);
  assert.equal(button.disabled, false);
  assert.equal(node.textContent, "Prazo estimado: 40 s.");

  const blocked = run({ initialDisabled: true });
  blocked.input.value = "2";
  blocked.helper(blocked.node);
  assert.equal(blocked.button.disabled, true, "a server-rendered stock or slot block is not undone");
});

test("dock offer totals use the server unit price and validate available stock", () => {
  const update = mainSource.match(/^function updateDockPurchaseEstimate\(form\) \{[\s\S]*?^\}/m)?.[0];
  const initialize = mainSource.match(/^function initializeDockPurchaseEstimates\(root = document\) \{[\s\S]*?^\}/m)?.[0];
  assert.ok(update && initialize);
  const helpers = new Function(`${update}\n${initialize}\nreturn {updateDockPurchaseEstimate, initializeDockPurchaseEstimates};`)();

  function makeOffer({ quantity = "1", stock = "4", disabled = false } = {}) {
    const input = { value: quantity, min: "1", max: stock, step: "1" };
    const total = { textContent: "" };
    const button = { disabled };
    const form = {
      dataset: { unitPrice: "148" },
      querySelector(selector) {
        return ({ "[data-dock-quantity]": input, "[data-dock-total]": total, "[data-dock-buy]": button })[selector] || null;
      },
    };
    return { form, input, total, button };
  }

  const direct = makeOffer();
  const document = { querySelectorAll: (selector) => selector === "[data-dock-buy-form]" ? [direct.form] : [] };
  helpers.initializeDockPurchaseEstimates(document);
  assert.equal(direct.total.textContent, "Total: 148 ouro");
  direct.input.value = "2";
  helpers.updateDockPurchaseEstimate(direct.form);
  assert.equal(direct.total.textContent, "Total: 296 ouro");
  direct.input.value = "";
  helpers.updateDockPurchaseEstimate(direct.form);
  assert.equal(direct.button.disabled, true);
  assert.match(direct.total.textContent, /quantidade disponível/);

  const unavailable = makeOffer({ quantity: "1", stock: "0", disabled: true });
  helpers.initializeDockPurchaseEstimates({ querySelectorAll: () => [unavailable.form] });
  unavailable.input.value = "1";
  helpers.updateDockPurchaseEstimate(unavailable.form);
  assert.equal(unavailable.button.disabled, true, "an unavailable offer stays blocked after initialization");
});

test("salvage preview follows selection, valid quantity, and known gold without inventing a balance", () => {
  const format = mainSource.match(/^function formatGenericRemaining\(ms\) \{[\s\S]*?^\}/m)?.[0];
  const update = mainSource.match(/^function updateSalvagePreview\(form\) \{[\s\S]*?^\}/m)?.[0];
  assert.ok(format && update);
  const helper = new Function(`${format}\n${update}\nreturn updateSalvagePreview;`)();
  const option = { dataset: { available: "3", unitSeconds: "10" } };
  const itemSelect = { selectedOptions: [option] };
  const quantityInput = { value: "1", min: "1", max: "1", step: "1" };
  const cost = { textContent: "" };
  const possibleReturn = { textContent: "" };
  const duration = { textContent: "" };
  const submit = { disabled: false };
  const status = { textContent: "", hidden: false };
  const form = {
    dataset: { unitCost: "50", goldKnown: "false", goldBalance: "" },
    querySelector(selector) {
      return ({
        "[data-salvage-item]": itemSelect,
        "[data-salvage-quantity]": quantityInput,
        "[data-salvage-cost]": cost,
        "[data-salvage-return]": possibleReturn,
        "[data-salvage-duration]": duration,
        "[data-salvage-submit]": submit,
        "[data-salvage-status]": status,
      })[selector] || null;
    },
  };

  helper(form);
  assert.equal(cost.textContent, "50 ouro");
  assert.equal(submit.disabled, true);
  assert.match(status.textContent, /Saldo de ouro não informado/);
  assert.equal(status.hidden, false);

  form.dataset.goldKnown = "true";
  form.dataset.goldBalance = "0";
  helper(form);
  assert.match(status.textContent, /Faltam 50 ouro/);

  quantityInput.value = "2";
  form.dataset.goldBalance = "100";
  helper(form);
  assert.equal(quantityInput.max, "3");
  assert.equal(cost.textContent, "100 ouro");
  assert.equal(possibleReturn.textContent, "2–6 materiais");
  assert.equal(duration.textContent, "00:00:20");
  assert.equal(submit.disabled, false);
  assert.equal(status.hidden, true);

  for (const invalid of ["", "0", "1.5", "4"]) {
    quantityInput.value = invalid;
    helper(form);
    assert.equal(submit.disabled, true, `${JSON.stringify(invalid)} is not a usable quantity`);
    assert.equal(cost.textContent, "—");
    assert.equal(possibleReturn.textContent, "—");
    assert.equal(duration.textContent, "—");
    assert.match(status.textContent, /quantidade inteira disponível/);
  }
});
