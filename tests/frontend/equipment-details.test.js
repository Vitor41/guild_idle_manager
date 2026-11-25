import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../../app/static/js/equipment-details.js", import.meta.url), "utf8");
const mainSource = await readFile(new URL("../../app/static/js/main.js", import.meta.url), "utf8");

function mountDetails({ mobile = false, viewportWidth = mobile ? 390 : 1024, viewportHeight = 768 } = {}) {
  const makeClassList = () => {
    const names = new Set();
    return {
      add: (...values) => values.forEach((value) => names.add(value)),
      remove: (...values) => values.forEach((value) => names.delete(value)),
      toggle: (value, enabled) => enabled ? names.add(value) : names.delete(value),
      contains: (value) => names.has(value),
    };
  };
  const makeElement = () => ({ listeners: new Map(), addEventListener(name, fn) { const handlers = this.listeners.get(name) ?? []; handlers.push(fn); this.listeners.set(name, handlers); }, dispatch(name, event = {}) { this.listeners.get(name)?.forEach((handler) => handler(event)); } });
  const closeButton = makeElement();
  const trigger = makeElement();
  const panel = makeElement();
  const slot = makeElement();
  let currentTriggers = [trigger];
  const document = {
    activeElement: {},
    querySelectorAll: (selector) => selector === "[data-equipment-swap]" ? [] : currentTriggers,
  };
  trigger.dataset = {};
  trigger.attributes = new Map();
  trigger.setAttribute = (key, value) => trigger.attributes.set(key, value);
  trigger.getBoundingClientRect = () => ({ left: 120, right: 180, top: 160, bottom: 190 });
  trigger.closest = () => slot;
  trigger.contains = (node) => node === trigger;
  trigger.matches = (selector) => selector === ":hover" && Boolean(trigger.hovering);
  trigger.focus = () => { document.activeElement = trigger; trigger.dispatch("focus"); };
  panel.hidden = true;
  panel.scrollHeight = 240;
  panel.style = { values: {}, set left(value) { this.values.left = value; }, set top(value) { this.values.top = value; }, set maxHeight(value) { this.values.maxHeight = value; }, removeProperty(name) { delete this.values[name]; } };
  panel.classList = makeClassList();
  panel.matches = (selector) => selector === ":hover" && Boolean(panel.hovering);
  panel.contains = (node) => node === panel || node === closeButton;
  panel.querySelector = () => closeButton;
  slot.querySelector = () => panel;
  slot.contains = (node) => node === trigger || node === panel || node === closeButton;
  let timeout = 0;
  const window = {
    innerWidth: viewportWidth,
    innerHeight: viewportHeight,
    matchMedia: () => ({ matches: mobile }),
    addEventListener() {},
    setTimeout(callback) { callback(); return ++timeout; },
    clearTimeout() {},
  };
  vm.runInNewContext(source, { document, window });
  const main = {
    querySelectorAll: (selector) => selector === "[data-equipment-swap]" ? [] : currentTriggers,
  };
  const addDynamicTrigger = () => {
    const dynamicTrigger = makeElement();
    const dynamicPanel = makeElement();
    const dynamicSlot = makeElement();
    dynamicTrigger.dataset = {};
    dynamicTrigger.attributes = new Map();
    dynamicTrigger.setAttribute = (key, value) => dynamicTrigger.attributes.set(key, value);
    dynamicTrigger.getBoundingClientRect = () => ({ left: 120, right: 180, top: 160 });
    dynamicTrigger.closest = () => dynamicSlot;
    dynamicTrigger.contains = () => false;
    dynamicTrigger.matches = () => false;
    dynamicPanel.hidden = true;
    dynamicPanel.scrollHeight = 240;
    dynamicPanel.style = { values: {}, set left(value) { this.values.left = value; }, set top(value) { this.values.top = value; }, set maxHeight(value) { this.values.maxHeight = value; }, removeProperty(name) { delete this.values[name]; } };
    dynamicPanel.classList = makeClassList();
    dynamicPanel.matches = () => false;
    dynamicPanel.contains = () => false;
    dynamicPanel.querySelector = () => null;
    dynamicSlot.querySelector = () => dynamicPanel;
    dynamicSlot.contains = () => false;
    currentTriggers = [dynamicTrigger];
    return { trigger: dynamicTrigger, panel: dynamicPanel };
  };
  return { trigger, panel, closeButton, document, mobile, main, window, addDynamicTrigger };
}

test("equipment details open on mouse hover and close when pointer leaves", () => {
  const ui = mountDetails();
  ui.trigger.hovering = true;
  ui.trigger.dispatch("pointerenter", { pointerType: "mouse" });
  assert.equal(ui.panel.hidden, false);
  assert.equal(ui.trigger.attributes.get("aria-expanded"), "true");
  assert.equal(ui.panel.style.values.left, "192px");
  ui.trigger.hovering = false;
  ui.trigger.dispatch("pointerleave", { pointerType: "mouse" });
  assert.equal(ui.panel.hidden, true);
  assert.equal(ui.trigger.attributes.get("aria-expanded"), "false");
});

test("equipment details open with keyboard focus and Escape closes while restoring focus", () => {
  const ui = mountDetails();
  ui.trigger.focus();
  assert.equal(ui.panel.hidden, false);
  ui.trigger.dispatch("keydown", { key: "Escape", preventDefault() {} });
  assert.equal(ui.panel.hidden, true);
  assert.equal(ui.trigger.attributes.get("aria-expanded"), "false");
  assert.equal(ui.document.activeElement, ui.trigger);
});

test("touch-style click toggles a viewport-positioned panel on narrow screens", () => {
  const ui = mountDetails({ mobile: true });
  ui.trigger.dispatch("click");
  assert.equal(ui.panel.hidden, false);
  assert.equal(ui.panel.style.values.left, "15px");
  assert.equal(ui.panel.style.values.top, "202px");
  assert.equal(ui.panel.style.values.maxHeight, "744px");
  ui.trigger.dispatch("click");
  assert.equal(ui.panel.hidden, true);

  const reflowed = mountDetails({ mobile: true, viewportWidth: 720 });
  reflowed.trigger.dispatch("click");
  assert.equal(reflowed.panel.style.values.left, "180px");
  assert.equal(reflowed.panel.style.values.top, "202px");

  const constrained = mountDetails({ mobile: true, viewportHeight: 240 });
  constrained.trigger.dispatch("click");
  assert.equal(constrained.panel.style.values.top, "12px");
  assert.equal(constrained.panel.style.values.maxHeight, "216px");
  constrained.closeButton.dispatch("click");
  assert.equal(constrained.panel.hidden, true);
  assert.equal(constrained.document.activeElement, constrained.trigger);
});

test("equipment details initialize after partial navigation and remain idempotent", () => {
  const ui = mountDetails();
  const dynamic = ui.addDynamicTrigger();
  assert.equal(typeof ui.window.initializeEquipmentDetails, "function");
  ui.window.initializeEquipmentDetails(ui.main);
  ui.window.initializeEquipmentDetails(ui.main);
  dynamic.trigger.dispatch("click");
  assert.equal(dynamic.panel.hidden, false);
  assert.equal(dynamic.trigger.attributes.get("aria-expanded"), "true");
  assert.match(mainSource, /currentMain\.innerHTML = incomingMain\.innerHTML;\s*initializeUpdateChecks\(currentMain\);\s*initializeGameGuideForContent\(parsedDocument, currentMain\);\s*window\.initializeEquipmentDetails\?\.\(currentMain\);/);
});
