import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const main = await readFile(new URL("../../app/static/js/main.js", import.meta.url), "utf8");
const refreshFunction = main.match(/^async function refreshRegionalEventsPageFromServer\([\s\S]*?^\}/m)?.[0];
assert.ok(refreshFunction, "authoritative event-page refresh function is present");

test("a successful refresh updates event cards while preserving form values, focus, details, and scroll", async () => {
  const focusCalls = [];
  const selectionCalls = [];
  const scrollCalls = [];
  const fetchCalls = [];
  const stateCalls = [];
  const oldControl = {
    name: "mercenary_ids", key: "SELECT:mercenary_ids", value: "m1", selectionStart: 2, selectionEnd: 4,
    focus(options) { focusCalls.push(["old", options]); },
    closest(selector) { return selector === "form" ? oldForm : null; },
  };
  const oldForm = { key: "portal-form", elements: [oldControl] };
  oldControl.form = oldForm;
  const oldRoot = {
    isConnected: true,
    contains(node) { return node === oldControl; },
    querySelectorAll(selector) {
      if (selector === "details[open]") return [oldDetails];
      if (selector === "details") return [oldDetails];
      if (selector === "form") return [oldForm];
      return [];
    },
    replaceWith(node) { document.currentRoot = node; this.isConnected = false; },
  };
  const oldDetails = { id: "portal-loot", open: true };

  const newControl = {
    name: "mercenary_ids", key: "SELECT:mercenary_ids", value: "server-default",
    focus(options) { focusCalls.push(["new", options]); },
    setSelectionRange(start, end) { selectionCalls.push([start, end]); },
  };
  const newForm = { key: "portal-form", elements: [newControl] };
  newControl.form = newForm;
  const newDetails = { id: "portal-loot", open: false };
  const incomingRoot = {
    querySelectorAll(selector) {
      if (selector === "details[open]") return [];
      if (selector === "details") return [newDetails];
      if (selector === "form") return [newForm];
      return [];
    },
    querySelector(selector) { return selector === "#portal-loot" ? newDetails : null; },
  };
  const parsedDocument = {
    querySelector(selector) { return selector === ".regional-events-page[data-regional-events]" ? incomingRoot : null; },
  };
  const document = {
    activeElement: oldControl,
    currentRoot: oldRoot,
    querySelector(selector) {
      return selector === ".regional-events-page[data-regional-events]" ? this.currentRoot : null;
    },
    importNode(node) { return node; },
    getElementById() { return null; },
  };
  const window = {
    location: { href: "https://game.test/regional/events?section=portals", pathname: "/regional/events" },
    scrollY: 321,
    scrollTo(options) { scrollCalls.push(options); },
    GIMApplyDesktopArt() {},
    initializeRegionalSupply() {},
    refreshRegionalEventAnchorOffset() {},
  };
  const formState = new Map([["portal-form", new Map([["SELECT:mercenary_ids", { value: "m1" }]])]]);
  const context = vm.createContext({
    URL,
    AbortController,
    document,
    window,
    DOMParser: class { parseFromString() { return parsedDocument; } },
    fetch: async (_url, options) => {
      fetchCalls.push(options);
      return { ok: true, url: window.location.href, text: async () => "fresh event page" };
    },
    captureGameFormState() { return formState; },
    restoreGameFormState(state) { stateCalls.push(["restore", state]); newControl.value = "m1"; },
    getFormStateKey(form) { return form.key; },
    getControlStateKey(control) { return control.key; },
    updateGenericCountdowns() {},
    regionalEventsRefreshRequest: null,
  });
  vm.runInContext(refreshFunction, context, { filename: "regional-events-live-refresh.js" });

  const updated = await context.refreshRegionalEventsPageFromServer();

  assert.equal(updated, true);
  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].method, "GET");
  assert.equal(newControl.value, "m1", "selected team is restored from the form state");
  assert.equal(newDetails.open, true, "expanded details remain expanded");
  assert.equal(focusCalls.length, 1);
  assert.equal(focusCalls[0][0], "new");
  assert.equal(focusCalls[0][1].preventScroll, true);
  assert.equal(scrollCalls.length, 1);
  assert.equal(scrollCalls[0].top, 321);
  assert.equal(scrollCalls[0].behavior, "auto");
  assert.deepEqual(selectionCalls, [[2, 4]]);
  assert.equal(stateCalls[0][0], "restore");
});

test("a refreshed portal attempt summary keeps focus by its stable id and retains expansion", async () => {
  const focusCalls = [];
  const scrollCalls = [];
  const oldSummary = { id: "portal-next-attempt-summary" };
  const newSummary = { id: "portal-next-attempt-summary", focus(options) { focusCalls.push(options); } };
  const oldDetails = { id: "portal-next-attempt", open: true };
  const newDetails = { id: "portal-next-attempt", open: false };
  const oldRoot = {
    isConnected: true,
    contains(node) { return node === oldSummary; },
    querySelectorAll(selector) {
      if (selector === "details[open]") return [oldDetails];
      if (selector === "details") return [oldDetails];
      return [];
    },
    replaceWith(node) { document.currentRoot = node; this.isConnected = false; },
  };
  const incomingRoot = {
    querySelectorAll(selector) {
      if (selector === "details[open]") return [];
      if (selector === "details") return [newDetails];
      return [];
    },
    querySelector(selector) { return selector === "#portal-next-attempt" ? newDetails : null; },
  };
  const parsedDocument = {
    querySelector(selector) { return selector === ".regional-events-page[data-regional-events]" ? incomingRoot : null; },
  };
  const document = {
    activeElement: oldSummary,
    currentRoot: oldRoot,
    querySelector(selector) { return selector === ".regional-events-page[data-regional-events]" ? this.currentRoot : null; },
    importNode(node) { return node; },
    getElementById(id) { return id === newSummary.id ? newSummary : null; },
  };
  const window = {
    location: { href: "https://game.test/regional/events?section=portals", pathname: "/regional/events" },
    scrollY: 400,
    scrollTo(options) { scrollCalls.push(options); },
  };
  const context = vm.createContext({
    URL,
    AbortController,
    document,
    window,
    DOMParser: class { parseFromString() { return parsedDocument; } },
    fetch: async () => ({ ok: true, url: window.location.href, text: async () => "fresh event page" }),
    captureGameFormState() { return new Map(); },
    restoreGameFormState() {},
    updateGenericCountdowns() {},
    regionalEventsRefreshRequest: null,
  });
  vm.runInContext(refreshFunction, context, { filename: "regional-events-focus-summary.js" });

  const updated = await context.refreshRegionalEventsPageFromServer();

  assert.equal(updated, true);
  assert.equal(focusCalls.length, 1);
  assert.equal(focusCalls[0].preventScroll, true);
  assert.equal(newDetails.open, true);
  assert.equal(scrollCalls.length, 1);
  assert.equal(scrollCalls[0].top, 400);
  assert.equal(scrollCalls[0].behavior, "auto");
});

test("a failed page refresh leaves the last rendered state intact", async () => {
  const oldRoot = { isConnected: true, replaceWith() { assert.fail("failed request must not replace the page"); } };
  const document = {
    querySelector() { return oldRoot; },
    activeElement: null,
  };
  const context = vm.createContext({
    URL,
    AbortController,
    document,
    window: { location: { href: "https://game.test/regional/events", pathname: "/regional/events" } },
    fetch: async () => ({ ok: false }),
    regionalEventsRefreshRequest: null,
  });
  vm.runInContext(refreshFunction, context, { filename: "regional-events-live-refresh-failure.js" });

  const updated = await context.refreshRegionalEventsPageFromServer();

  assert.equal(updated, false);
  assert.equal(oldRoot.isConnected, true);
});
