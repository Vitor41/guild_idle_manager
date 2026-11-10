import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../../app/static/js/guide.js", import.meta.url), "utf8");

function mountGuide(fetchImpl, { nativeApi = null, showSaveFilePicker = null } = {}) {
  const listeners = new Map();
  const attributes = new Map();
  const button = {
    disabled: false,
    textContent: "Baixar Guia em Markdown",
    addEventListener: (name, callback) => listeners.set(name, callback),
    setAttribute: (name, value) => attributes.set(name, value),
    removeAttribute: (name) => attributes.delete(name),
  };
  const status = { textContent: "", role: "", setAttribute(name, value) { this[name] = value; } };
  const progress = { hidden: true };
  const feedback = { hidden: true };
  const root = { querySelector(selector) {
    if (selector === "[data-guide-export]") return button;
    if (selector === "[data-guide-export-status]") return status;
    if (selector === "[data-guide-export-progress]") return progress;
    if (selector === "[data-guide-export-feedback]") return feedback;
    return null;
  } };
  let lastDownload;
  const document = {
    querySelector: (selector) => selector === ".game-guide" ? root : null,
    createElement: () => ({ click() { lastDownload = { href: this.href, name: this.download }; } }),
  };
  const window = { GuideUtils: {}, setTimeout() {}, showSaveFilePicker };
  if (nativeApi) window.pywebview = { api: nativeApi };
  const URL = { createObjectURL: () => "blob:guide", revokeObjectURL() {} };
  vm.runInNewContext(source, { document, window, URL, fetch: fetchImpl, console: { error() {} }, matchMedia: () => ({ matches: false }) });
  return { button, status, progress, feedback, attributes, listeners, get lastDownload() { return lastDownload; } };
}

test("desktop export confirms the native destination after the bridge writes the file", async () => {
  let resolveFetch;
  let requests = 0;
  let savedMarkdown = "";
  const ui = mountGuide(() => { requests += 1; return new Promise((resolve) => { resolveFetch = resolve; }); }, {
    nativeApi: { async export_guide_markdown(markdown) { savedMarkdown = markdown; return { ok: true, path: "C:/Guia/guia-atual.md" }; } },
  });
  const pending = ui.listeners.get("click")();
  assert.equal(ui.button.disabled, true);
  assert.equal(ui.attributes.get("aria-busy"), "true");
  assert.equal(ui.progress.hidden, false);
  assert.match(ui.status.textContent, /Preparando/);
  await ui.listeners.get("click")();
  assert.equal(requests, 1);
  resolveFetch({
    ok: true,
    headers: { get: (name) => name === "content-type" ? "text/markdown; charset=utf-8" : 'attachment; filename="guia-atual.md"' },
    blob: async () => ({ size: 18, text: async () => "# Guia" }),
  });
  await pending;
  assert.match(ui.status.textContent, /salvo em: C:\/Guia\/guia-atual\.md/);
  assert.equal(savedMarkdown, "# Guia");
  assert.equal(ui.button.disabled, false);
  assert.equal(ui.progress.hidden, true);
  assert.equal(ui.lastDownload, undefined);
});

test("browser export waits for the Save dialog and confirmed file write", async () => {
  const chunks = [];
  let closeCalls = 0;
  const ui = mountGuide(async () => ({
    ok: true,
    headers: { get: (name) => name === "content-type" ? "text/markdown; charset=utf-8" : 'attachment; filename="guia.md"' },
    blob: async () => ({ size: 15 }),
  }), {
    showSaveFilePicker: async (options) => {
      assert.equal(options.suggestedName, "guia-guild-idle-manager.md");
      return {
        name: "guia.md",
        createWritable: async () => ({ write: async (blob) => chunks.push(blob.size), close: async () => { closeCalls += 1; } }),
        getFile: async () => ({ size: 15 }),
      };
    },
  });
  await ui.listeners.get("click")();
  assert.deepEqual(chunks, [15]);
  assert.equal(closeCalls, 1);
  assert.match(ui.status.textContent, /Guia salvo como guia\.md \(15 bytes\)/);
});

test("export exposes a retryable inline error on network or server failure", async () => {
  const ui = mountGuide(async () => { throw new Error("rede indisponível"); });
  await ui.listeners.get("click")();
  assert.match(ui.status.textContent, /rede indisponível.*Tente novamente/);
  assert.equal(ui.status.role, "alert");
  assert.equal(ui.button.textContent, "Tentar novamente");
  assert.equal(ui.button.disabled, false);
  assert.equal(ui.progress.hidden, true);
});

test("export surfaces a server error without triggering a download", async () => {
  const ui = mountGuide(async () => ({ ok: false, status: 503, headers: { get: () => "text/plain" } }));
  await ui.listeners.get("click")();
  assert.match(ui.status.textContent, /Falha 503/);
  assert.equal(ui.status.role, "alert");
  assert.equal(ui.lastDownload, undefined);
  assert.equal(ui.button.textContent, "Tentar novamente");
});

test("export reports cancellation and unsupported browsers without false success", async () => {
  const cancelled = mountGuide(async () => { throw new DOMException("cancelado", "AbortError"); }, {
    showSaveFilePicker: async () => { throw new DOMException("cancelado", "AbortError"); },
  });
  await cancelled.listeners.get("click")();
  assert.match(cancelled.status.textContent, /Salvamento cancelado/);
  assert.equal(cancelled.status.role, "status");

  const unsupported = mountGuide(async () => ({
    ok: true,
    headers: { get: (name) => name === "content-type" ? "text/markdown" : 'attachment; filename="guia.md"' },
    blob: async () => ({ size: 4 }),
  }));
  await unsupported.listeners.get("click")();
  assert.match(unsupported.status.textContent, /não oferece confirmação de salvamento/);
  assert.equal(unsupported.status.role, "alert");
});
