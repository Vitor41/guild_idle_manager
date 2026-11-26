import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../../", import.meta.url);
const main = await readFile(new URL("app/static/js/main.js", root), "utf8");
const initializerSource = main.match(/^function initializeUpdateChecks\([\s\S]*?^\}/m)?.[0];
assert.ok(initializerSource, "update check initializer exists in the shared shell");

function createRoot(button, status, statusSelector) {
  return {
    querySelectorAll() { return [button]; },
    querySelector(selector) { return selector === statusSelector ? status : null; },
  };
}

function createButton({ packaged = false, queryEnabled = true } = {}) {
  const listeners = new Map();
  return {
    dataset: packaged ? { updateQueryEnabled: String(queryEnabled) } : {},
    disabled: false,
    hasAttribute(name) { return packaged && name === "data-check-release-update"; },
    addEventListener(name, callback) { listeners.set(name, [...(listeners.get(name) || []), callback]); },
    listeners(name) { return listeners.get(name) || []; },
  };
}

function loadInitializer(fetchImpl) {
  return new Function("fetch", `${initializerSource}\nreturn initializeUpdateChecks;`)(fetchImpl);
}

test("updates check initializes after direct and partial navigation without duplicate requests", async () => {
  let requestCount = 0;
  const init = loadInitializer(async () => {
    requestCount += 1;
    return { ok: true, json: async () => ({ available: true, available_version: "0.11.0" }) };
  });

  const directButton = createButton({ packaged: true });
  const directStatus = { textContent: "" };
  const directRoot = createRoot(directButton, directStatus, "[data-release-update-status]");
  init(directRoot);
  init(directRoot);
  assert.equal(directButton.listeners("click").length, 1, "direct page binds once");
  await directButton.listeners("click")[0]();
  assert.match(directStatus.textContent, /0\.11\.0 está disponível/);
  assert.equal(requestCount, 1);

  const partialButton = createButton();
  const partialStatus = { textContent: "" };
  const partialRoot = createRoot(partialButton, partialStatus, "[data-local-update-status]");
  init(partialRoot);
  init(partialRoot);
  assert.equal(partialButton.listeners("click").length, 1, "new partial page binds once");
  await partialButton.listeners("click")[0]();
  assert.match(partialStatus.textContent, /Versão 0\.11\.0 detectada/);
  assert.equal(requestCount, 2, "one GET per deliberate click");
});

test("updates check reports a recoverable error and remains usable for retry", async () => {
  let requestCount = 0;
  const init = loadInitializer(async () => {
    requestCount += 1;
    if (requestCount === 1) throw new Error("Falha de rede temporária.");
    return { ok: true, json: async () => ({ available: false, current_version: "0.11.0", reason: "Checkout local já está nesta versão." }) };
  });
  const button = createButton();
  const status = { textContent: "" };
  init(createRoot(button, status, "[data-local-update-status]"));

  const click = button.listeners("click")[0];
  await click();
  assert.equal(status.textContent, "Falha de rede temporária.");
  assert.equal(button.disabled, false);
  await click();
  assert.equal(status.textContent, "Checkout local já está nesta versão.");
  assert.equal(requestCount, 2);
  assert.equal(button.disabled, false);
});
