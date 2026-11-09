import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../../app/static/js/equipment-details.js", import.meta.url), "utf8");

function mountDetails({ mobile = false } = {}) {
  const makeClassList = () => {
    const names = new Set();
    return {
      add: (...values) => values.forEach((value) => names.add(value)),
      remove: (...values) => values.forEach((value) => names.delete(value)),
      toggle: (value, enabled) => enabled ? names.add(value) : names.delete(value),
      contains: (value) => names.has(value),
    };
  };
  const makeElement = () => ({ listeners: new Map(), addEventListener(name, fn) { this.listeners.set(name, fn); }, dispatch(name, event = {}) { this.listeners.get(name)?.(event); } });
  const closeButton = makeElement();
  const trigger = makeElement();
  const panel = makeElement();
  const slot = makeElement();
  const document = { activeElement: {}, querySelectorAll: () => [trigger] };
  trigger.dataset = {};
  trigger.attributes = new Map();
  trigger.setAttribute = (key, value) => trigger.attributes.set(key, value);
  trigger.getBoundingClientRect = () => ({ left: 120, right: 180, top: 160 });
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
    innerWidth: 1024,
    innerHeight: 768,
    matchMedia: () => ({ matches: mobile }),
    addEventListener() {},
    setTimeout(callback) { callback(); return ++timeout; },
    clearTimeout() {},
  };
  vm.runInNewContext(source, { document, window });
  return { trigger, panel, closeButton, document, mobile };
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

test("touch-style click toggles the panel and mobile keeps it in normal flow", () => {
  const ui = mountDetails({ mobile: true });
  ui.trigger.dispatch("click");
  assert.equal(ui.panel.hidden, false);
  assert.equal(ui.panel.style.values.left, undefined);
  ui.trigger.dispatch("click");
  assert.equal(ui.panel.hidden, true);
});
