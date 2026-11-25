import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const main = await readFile(new URL("../../app/static/js/main.js", import.meta.url), "utf8");
const offsetFunction = main.match(/^function refreshRegionalEventAnchorOffset\(\) \{[\s\S]*?^\}/m)?.[0];

test("regional anchor offset follows the measured sticky header and ignores relative headers", () => {
  assert.ok(offsetFunction, "dynamic regional anchor offset helper is present");
  const values = new Map();
  const topbar = { getBoundingClientRect() { return { height: 139 }; } };
  const document = {
    documentElement: { style: { setProperty(name, value) { values.set(name, value); } } },
    querySelector(selector) { return selector === ".game-topbar" ? topbar : null; },
  };
  let position = "sticky";
  const run = new Function(
    "document",
    "window",
    "ResizeObserver",
    `let regionalEventTopbarObserver = null; let regionalEventTopbarObserved = null; ${offsetFunction}; return refreshRegionalEventAnchorOffset;`,
  )(
    document,
    { getComputedStyle() { return { position, top: "0px" }; } },
    undefined,
  );

  run();
  assert.equal(values.get("--regional-event-sticky-topbar-height"), "139px");
  assert.equal(values.get("--game-sticky-topbar-height"), "139px");
  position = "relative";
  run();
  assert.equal(values.get("--regional-event-sticky-topbar-height"), "0px");
  assert.equal(values.get("--game-sticky-topbar-height"), "0px");
});
