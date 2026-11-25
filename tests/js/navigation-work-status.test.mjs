import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const main = await readFile(new URL("../../app/static/js/main.js", import.meta.url), "utf8");
const statusFunction = main.match(/^async function refreshNavigationWorkIndicators\([\s\S]*?^\}/m)?.[0];
assert.ok(statusFunction, "navigation status refresh function is present");

function makeLink() {
  let indicator = {
    dataset: { state: "ready" },
    remove() { indicator = null; },
  };
  const attributes = new Map([["aria-label", "Old stale ready status"]]);
  return {
    dataset: { navWorkMenu: "regional_events", navWorkLabel: "Eventos Regionais", workState: "ready" },
    title: "Old stale ready status",
    querySelector(selector) { return selector === ".nav-work-indicator" ? indicator : null; },
    append(node) { indicator = node; },
    removeAttribute(name) {
      if (name === "data-work-state") delete this.dataset.workState;
      else attributes.delete(name);
      if (name === "title") this.title = "";
    },
    setAttribute(name, value) { attributes.set(name, value); },
    getAttribute(name) { return attributes.get(name) ?? null; },
    get indicator() { return indicator; },
  };
}

function setup(response) {
  const link = makeLink();
  const context = vm.createContext({
    AbortController,
    Number,
    document: {
      querySelectorAll: () => [link],
      createElement: () => ({ dataset: {}, setAttribute(name, value) { this[name] = value; } }),
    },
    fetch: async () => response,
    window: {},
    navigationWorkStatusRequest: null,
    navigationWorkStatusController: null,
  });
  vm.runInContext(statusFunction, context, { filename: "navigation-work-status.js" });
  return { context, link };
}

test("failed or incomplete polling clears stale green and reports unavailable status", async () => {
  for (const response of [
    { ok: false },
    { ok: true, json: async () => ({ menus: {} }) },
    { ok: true, json: async () => ({ menus: { regional_events: { active: 0, ready: 0 } } }) },
  ]) {
    const { context, link } = setup(response);
    await context.refreshNavigationWorkIndicators();
    assert.equal(link.dataset.workState, "unknown");
    assert.equal(link.indicator?.dataset.state, "unknown");
    assert.equal(link.getAttribute("aria-label"), "Eventos Regionais: status indisponível");
    assert.equal(link.title, "Eventos Regionais: status indisponível");
  }
});

test("a complete zero result clears the unavailable marker instead of treating absent data as zero", async () => {
  const { context, link } = setup({
    ok: true,
    json: async () => ({ menus: { regional_events: { active: 0, ready: 0, state: "none", label: "Eventos Regionais" } } }),
  });
  await context.refreshNavigationWorkIndicators();
  assert.equal(link.dataset.workState, undefined);
  assert.equal(link.indicator, null);
  assert.equal(link.getAttribute("aria-label"), null);
  assert.equal(link.title, "");
});
