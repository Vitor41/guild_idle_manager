import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../../app/static/js/building-reset.js", import.meta.url), "utf8");

function createDialog() {
  const listeners = {};
  const cancel = { focusCalls: [], focus(options) { this.focusCalls.push(options); } };
  const button = { textContent: "Confirmar reset", disabled: false, dataset: {} };
  const status = { textContent: "" };
  const form = {
    action: "/buildings/reset",
    dataset: {},
    attributes: {},
    querySelector(selector) {
      if (selector === "[data-reset-submit]") return button;
      if (selector === "[data-reset-status]") return status;
      return null;
    },
    addEventListener(name, callback) { listeners[`form:${name}`] = callback; },
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
  };
  const dialog = {
    dataset: {},
    open: true,
    showModalCalls: 0,
    closeCalls: 0,
    listeners,
    showModal() { this.showModalCalls += 1; this.open = true; },
    close() { this.closeCalls += 1; this.open = false; },
    querySelector(selector) {
      if (selector === "[data-reset-cancel]") return cancel;
      if (selector === "[data-building-reset-form]") return form;
      return null;
    },
    addEventListener(name, callback) { listeners[`dialog:${name}`] = callback; },
  };
  return { dialog, form, button, status, cancel, listeners };
}

function createHarness(fetchImpl) {
  const initial = createDialog();
  const assignedUrls = [];
  const formDataInstances = [];
  class FormDataMock {
    constructor(form) {
      this.form = form;
      this.values = { idempotency_key: "fc4bcb53-d612-42bd-8a80-40482df13a9a" };
      formDataInstances.push(this);
    }
    get(name) { return this.values[name] ?? null; }
  }
  const document = {
    querySelectorAll(selector) {
      return selector === "[data-building-reset-dialog]" ? [initial.dialog] : [];
    },
  };
  const window = {
    location: { origin: "http://localhost", assign(url) { assignedUrls.push(url); } },
  };
  const context = vm.createContext({
    document,
    window,
    fetch: (...args) => fetchImpl(...args),
    URL,
    FormData: FormDataMock,
    Number,
    Error,
  });
  vm.runInContext(source, context, { filename: "building-reset.js" });
  return { ...initial, window, assignedUrls, formDataInstances };
}

function submitEvent() {
  return { prevented: false, preventDefault() { this.prevented = true; } };
}

test("a lost POST response navigates to the read-only reset receipt", async () => {
  const calls = [];
  const harness = createHarness(async (url, options) => {
    calls.push({ url: String(url), options });
    if (options.method === "POST") throw new Error("response dropped after commit");
    return { ok: true, async json() { return { completed: true, reset_id: 42 }; } };
  });

  const event = submitEvent();
  await harness.listeners["form:submit"](event);

  assert.equal(event.prevented, true);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(harness.form.dataset.nativeSubmit, "true");
  assert.equal(calls[1].options.method, "GET");
  assert.equal(calls[1].options.cache, "no-store");
  assert.match(calls[1].url, /^http:\/\/localhost\/buildings\/reset\/status\?key=/);
  assert.deepEqual(harness.assignedUrls, ["http://localhost/buildings?reset_id=42"]);
  assert.equal(harness.button.disabled, true);
});

test("an inconclusive status response restores an accessible retry with the same key", async () => {
  const postKeys = [];
  let postCount = 0;
  const harness = createHarness(async (_url, options) => {
    if (options.method === "POST") {
      postKeys.push(options.body.get("idempotency_key"));
      postCount += 1;
      if (postCount === 1) throw new Error("response dropped");
      return { redirected: true, url: "http://localhost/buildings?reset_id=43" };
    }
    return { ok: true, async json() { return { completed: false, reset_id: null }; } };
  });

  await harness.listeners["form:submit"](submitEvent());
  assert.equal(harness.button.disabled, false);
  assert.equal(harness.button.textContent, "Tentar novamente");
  assert.match(harness.status.textContent, /Não foi possível confirmar/);
  assert.equal(harness.form.attributes["aria-busy"], undefined);

  await harness.listeners["form:submit"](submitEvent());
  assert.deepEqual(postKeys, [
    "fc4bcb53-d612-42bd-8a80-40482df13a9a",
    "fc4bcb53-d612-42bd-8a80-40482df13a9a",
  ]);
  assert.deepEqual(harness.assignedUrls, ["/buildings?reset_id=43"]);
});

test("a failed status lookup keeps the user informed and enables safe retry", async () => {
  const harness = createHarness(async (_url, options) => {
    if (options.method === "POST") throw new Error("response dropped");
    throw new Error("status service unavailable");
  });

  await harness.listeners["form:submit"](submitEvent());

  assert.equal(harness.button.disabled, false);
  assert.equal(harness.button.textContent, "Tentar novamente");
  assert.match(harness.status.textContent, /sem cobrar duas vezes/);
});

test("a partial-navigation preview opens once and focuses Cancelar; a result page adds no preview", () => {
  const harness = createHarness(async () => ({ ok: true }));
  const next = createDialog();
  const replacedRoot = {
    querySelectorAll(selector) {
      return selector === "[data-building-reset-dialog]" ? [next.dialog] : [];
    },
  };

  harness.window.initializeBuildingResetDialogs(replacedRoot);
  harness.window.initializeBuildingResetDialogs(replacedRoot);
  harness.window.initializeBuildingResetDialogs({ querySelectorAll() { return []; } });

  assert.equal(next.dialog.showModalCalls, 1);
  assert.equal(next.cancel.focusCalls.length, 1);
  assert.equal(next.cancel.focusCalls[0].preventScroll, true);
  assert.equal(typeof next.listeners["dialog:cancel"], "function");
});
