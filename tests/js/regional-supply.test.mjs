import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const scriptPath = fileURLToPath(new URL("../../app/static/js/regional-supply.js", import.meta.url));
const regionalSupplyScript = readFileSync(scriptPath, "utf8");

function makeEnvironment({
  prepared,
  fetchImpl,
  teamAvailable = true,
  teamValid = true,
  preparedTeamCanStart = teamAvailable && teamValid,
  nowMs = 6000,
  startsAtMs = 0,
  endsAtMs = 5000,
  minPartySize = 1,
  maxPartySize = 2,
}) {
  const formListeners = {};
  const intervalCallbacks = [];
  const clock = { now: nowMs };
  const checkboxes = [
    {
      value: "101",
      name: "mercenary_ids",
      checked: teamAvailable,
      type: teamAvailable ? "checkbox" : "hidden",
      dataset: teamAvailable ? {} : { preparedMemberHidden: "true" },
      listeners: {},
      addEventListener(name, fn) { this.listeners[name] = fn; },
    },
    { value: "202", name: "mercenary_ids", checked: false, type: "checkbox", dataset: {}, listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; } },
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
  const reinforcementBadge = { dataset: { reinforcementBadge: "202" }, hidden: true };
  const preparedButton = prepared ? {
    name: "supply_mode",
    value: "prepared",
    disabled: true,
    dataset: { readyLabel: "Iniciar com suprimento preparado" },
    textContent: "Aguardando preparo",
  } : null;
  const withoutSupplyButton = { disabled: Boolean(prepared && !preparedTeamCanStart), dataset: { startWithoutSupply: "" } };
  const teamFieldset = { dataset: { minPartySize: String(minPartySize), maxPartySize: String(maxPartySize) } };
  const prepareButton = prepared ? null : { disabled: false };
  const supplyLabel = {
    textContent: "Suprimento em preparo",
    closest() { return { classList: { add() {} } }; },
  };
  const form = {
    dataset: {
      regionalSupplyInitialized: "false",
      supplyQuoteUrl: "/regional/offers/1/supply-quote",
      preparedMercenaryIds: prepared ? "101" : "",
      preparedTeamAvailable: String(teamAvailable),
      preparedTeamValid: String(teamValid),
      preparedTeamCanStart: String(preparedTeamCanStart),
    },
    querySelector(selector) {
      if (selector === 'input[name="supply"]') return supply;
      if (selector === ".supply-preparation small") return summary;
      if (selector === 'button[name="supply_mode"][value="prepared"]') return preparedButton;
      if (selector === "fieldset[data-min-party-size]") return teamFieldset;
      if (selector === "[data-start-without-supply]") return withoutSupplyButton;
      if (selector === "[data-prepared-team-status]") return teamAvailable && teamValid ? status : null;
      if (selector === "[data-supply-preparation-label]") return supplyLabel;
      if (selector === "[data-prepare-action]") return prepareButton;
      return null;
    },
    querySelectorAll(selector) {
      if (selector.startsWith('input[name="mercenary_ids"]')) {
        return selector.endsWith(":checked") ? checkboxes.filter((input) => input.checked) : checkboxes;
      }
      if (selector === "[data-reinforcement-badge]") return [reinforcementBadge];
      if (selector === 'select[name="run_multiplier"]') return [];
      return [];
    },
    addEventListener(name, fn) { formListeners[name] = fn; },
    requestSubmit() { this.requestSubmitCalls = (this.requestSubmitCalls || 0) + 1; },
  };
  const time = {
    dataset: {
      startsAt: new Date(startsAtMs).toISOString(),
      endsAt: new Date(endsAtMs).toISOString(),
    },
    textContent: "calculando",
  };
  const progressStatus = { textContent: "Suprimento em preparo" };
  const progressBar = { value: 0 };
  const progressBox = {
    dataset: {},
    querySelector(selector) {
      if (selector === "time[data-ends-at]") return time;
      if (selector === "progress") return progressBar;
      if (selector === "strong") return progressStatus;
      return null;
    },
    closest(selector) { return selector === "form" ? form : null; },
  };
  const root = {
    querySelectorAll(selector) {
      if (selector === ".supply-preparation-progress") return prepared ? [progressBox] : [];
      if (selector === "form[data-supply-quote-url]") return [form];
      return [];
    },
  };
  class FormDataStub {
    constructor(form) { this.form = form; }
    getAll(name) {
      if (name !== "mercenary_ids") return [];
      return this.form.querySelectorAll('input[name="mercenary_ids"]')
        .filter((input) => input.checked || input.dataset.preparedMemberHidden === "true")
        .map((input) => String(input.value));
    }
    *[Symbol.iterator]() { return; }
  }
  const context = vm.createContext({
    Date: class extends Date { static now() { return clock.now; } },
    window: {
      crypto: { randomUUID: () => "regional-supply-test" },
      setInterval(fn) { intervalCallbacks.push(fn); return intervalCallbacks.length - 1; },
      clearInterval() {},
    },
    document: { addEventListener() {} },
    fetch: fetchImpl,
    FormData: FormDataStub,
    URLSearchParams,
    Event,
  });
  vm.runInContext(regionalSupplyScript, context, { filename: "regional-supply.js" });
  context.window.initializeRegionalSupply(root);
  return {
    checkboxes,
    clock,
    formListeners,
    form,
    intervalCallbacks,
    preparedButton,
    withoutSupplyButton,
    FormDataStub,
    prepareButton,
    progressBar,
    progressStatus,
    status,
    reinforcementBadge,
    supply,
    summary,
    time,
  };
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
  assert.equal(page.preparedButton.disabled, false);
  assert.match(page.status.textContent, /bônus do suprimento está pronto/);
  assert.equal(page.reinforcementBadge.hidden, true, "an unselected reinforcement has no reinforcement badge");

  page.checkboxes[1].checked = true;
  page.formListeners.change({ target: { matches: (selector) => selector === 'input[name="mercenary_ids"]' } });
  assert.equal(page.reinforcementBadge.hidden, false, "selecting a reinforcement shows its badge");
  page.checkboxes[1].listeners.change();
  assert.equal(page.preparedButton.disabled, true);
  assert.equal(page.withoutSupplyButton.disabled, false, "a valid reinforcement team can start without supply");
  assert.match(page.status.textContent, /Há reforços selecionados/);
  assert.match(page.status.textContent, /Iniciar sem suprimento/);

  page.checkboxes[1].checked = false;
  page.formListeners.change({ target: { matches: (selector) => selector === 'input[name="mercenary_ids"]' } });
  assert.equal(page.reinforcementBadge.hidden, true, "removing the selection hides its badge");

  let prevented = false;
  page.formListeners.submit({
    submitter: page.preparedButton,
    preventDefault() { prevented = true; },
  });
  assert.equal(prevented, false);
});

test("prepared offer keeps original members and enforces saved party bounds", () => {
  const page = makeEnvironment({ prepared: true, minPartySize: 1, maxPartySize: 2 });
  page.checkboxes[0].checked = false;
  page.checkboxes[0].listeners.change();
  assert.equal(page.preparedButton.disabled, true);
  assert.equal(page.withoutSupplyButton.disabled, true);
  assert.match(page.status.textContent, /Equipe incompleta/);
  assert.deepEqual(new page.FormDataStub(page.form).getAll("mercenary_ids"), []);

  page.checkboxes[1].checked = true;
  page.checkboxes[1].listeners.change();
  assert.equal(page.preparedButton.disabled, true);
  assert.equal(page.withoutSupplyButton.disabled, true);
  assert.deepEqual(new page.FormDataStub(page.form).getAll("mercenary_ids"), ["202"]);
  assert.match(page.status.textContent, /equipe original do preparo deve permanecer/);
  assert.equal(page.form.requestSubmitCalls || 0, 0, "selection changes never submit automatically");

  page.checkboxes[0].checked = true;
  page.checkboxes[0].listeners.change();
  assert.equal(page.preparedButton.disabled, true, "the saved prepared bonus only accepts the exact team");
  assert.equal(page.withoutSupplyButton.disabled, false, "the original team plus a valid reinforcement may start without supply");
  assert.deepEqual(new page.FormDataStub(page.form).getAll("mercenary_ids"), ["101", "202"]);

  const overLimit = makeEnvironment({ prepared: true, minPartySize: 1, maxPartySize: 1 });
  overLimit.checkboxes[1].checked = true;
  overLimit.checkboxes[1].listeners.change();
  assert.equal(overLimit.preparedButton.disabled, true);
  assert.equal(overLimit.withoutSupplyButton.disabled, true);
  assert.match(overLimit.status.textContent, /acima do limite/);

  const rejectedByServer = makeEnvironment({ prepared: true, preparedTeamCanStart: false });
  assert.equal(rejectedByServer.withoutSupplyButton.disabled, true);
  rejectedByServer.checkboxes[1].checked = true;
  rejectedByServer.checkboxes[1].listeners.change();
  assert.equal(rejectedByServer.withoutSupplyButton.disabled, true, "client updates cannot override the server's prepared-team block");
});

test("prepared start combines availability and deadline for occupied, free, and already expired teams", () => {
  const occupiedBefore = makeEnvironment({ prepared: true, teamAvailable: false, nowMs: 1000 });
  assert.equal(occupiedBefore.preparedButton.disabled, true);
  occupiedBefore.intervalCallbacks[0]();
  assert.equal(occupiedBefore.form.dataset.preparedSupplyReady, "false");
  occupiedBefore.clock.now = 6000;
  occupiedBefore.intervalCallbacks[0]();
  assert.equal(occupiedBefore.form.dataset.preparedSupplyReady, "true");
  assert.equal(occupiedBefore.preparedButton.disabled, true);

  const freeBefore = makeEnvironment({ prepared: true, teamAvailable: true, nowMs: 1000 });
  assert.equal(freeBefore.preparedButton.disabled, true);
  freeBefore.clock.now = 6000;
  freeBefore.intervalCallbacks[0]();
  assert.equal(freeBefore.preparedButton.disabled, false);
  assert.equal(freeBefore.progressBar.value, 100);

  const freeAlreadyExpired = makeEnvironment({ prepared: true, teamAvailable: true, nowMs: 6000 });
  assert.equal(freeAlreadyExpired.preparedButton.disabled, false);
  assert.equal(freeAlreadyExpired.form.dataset.preparedSupplyReady, "true");

  const occupiedAlreadyExpired = makeEnvironment({ prepared: true, teamAvailable: false, nowMs: 6000 });
  assert.equal(occupiedAlreadyExpired.form.dataset.preparedSupplyReady, "true");
  assert.equal(occupiedAlreadyExpired.preparedButton.disabled, true);
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
