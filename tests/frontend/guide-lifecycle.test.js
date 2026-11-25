import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const mainSource = await readFile(new URL("../../app/static/js/main.js", import.meta.url), "utf8");
const guideSource = await readFile(new URL("../../app/static/js/guide.js", import.meta.url), "utf8");
const utilsSource = await readFile(new URL("../../app/static/js/guide-utils.js", import.meta.url), "utf8");
const helperSource = mainSource.match(/^let guideAssetLoadPromise = null;\r?\nfunction initializeGameGuideForContent\([\s\S]*?^\}/m)?.[0];
assert.ok(helperSource, "partial-navigation Guide initializer is present");
const replacementSource = mainSource.match(/^function replaceGameContent\([\s\S]*?^\}/m)?.[0];
assert.match(replacementSource || "", /initializeGameGuideForContent\(parsedDocument, currentMain\)/);

function makeGuideFixture({ initialRoot }) {
  const listeners = new Map();
  const fetchCalls = [];
  const exportDestinations = [];
  let activeRoot = initialRoot;
  const searchStatus = { textContent: "" };
  const exportStatus = { textContent: "", setAttribute(name, value) { this[name] = value; } };
  const exportFeedback = { hidden: true };
  const exportProgress = { hidden: true };
  const exportButton = {
    disabled: false,
    textContent: "Baixar Guia em Markdown",
    addEventListener(name, callback) { listeners.set(`export:${name}`, callback); },
    setAttribute(name, value) { this[name] = value; },
    removeAttribute(name) { delete this[name]; },
  };
  const searchInput = { value: "portal", focus() {} };
  const searchForm = {
    addEventListener(name, callback) { listeners.set(`search:${name}`, callback); },
    querySelector(selector) { return selector === "#guide-search-query" ? searchInput : null; },
  };
  const rows = { children: [], replaceChildren(...children) { this.children = children; }, append(child) { this.children.push(child); } };
  const catalogStatus = { textContent: "", hidden: false };
  const catalogError = { hidden: true };
  const catalogEmpty = { hidden: false };
  const tableWrap = { hidden: true };
  const catalogNodes = new Map([
    ["[data-guide-catalog-rows]", rows],
    ["[data-guide-catalog-status]", catalogStatus],
    ["[data-guide-catalog-error]", catalogError],
    ["[data-guide-catalog-empty]", catalogEmpty],
    ["[data-guide-catalog-wrap]", tableWrap],
  ]);
  const catalogRoot = {
    querySelector(selector) { return catalogNodes.get(selector) || null; },
    querySelectorAll() { return []; },
  };
  const rootNodes = new Map([
    ["[data-guide-search-form]", searchForm],
    ["[data-guide-search-status]", searchStatus],
    ["#equipamentos-materiais", catalogRoot],
    ["[data-guide-export]", exportButton],
    ["[data-guide-export-status]", exportStatus],
    ["[data-guide-export-feedback]", exportFeedback],
    ["[data-guide-export-progress]", exportProgress],
  ]);
  const root = { querySelector(selector) { return rootNodes.get(selector) || null; } };
  const textNode = {
    nodeValue: "O portal aparece no Guia.",
    parentElement: { closest() { return null; } },
  };
  const document = {
    head: { append(script) {
      const asset = script.src.includes("guide-utils.js") ? utilsSource : guideSource;
      vm.runInContext(asset, context);
      script.listeners.load?.();
    } },
    querySelector(selector) { return selector === ".game-guide" ? activeRoot : null; },
    createElement(tagName) {
      if (tagName === "script") return {
        listeners: {},
        addEventListener(name, callback) { this.listeners[name] = callback; },
      };
      if (tagName === "mark") return {
        textContent: "portal",
        scrollIntoView() {},
        focus() {},
      };
      return { append() {}, setAttribute() {}, addEventListener() {} };
    },
    createTreeWalker() {
      let walked = false;
      return { currentNode: null, nextNode() {
        if (walked) return false;
        walked = true;
        this.currentNode = textNode;
        return true;
      } };
    },
    createRange() { return { setStart() {}, setEnd() {}, surroundContents() {} }; },
  };
  const window = {
    GuideUtils: undefined,
    pywebview: { api: { async export_guide_markdown(markdown) {
      exportDestinations.push(markdown);
      return { ok: true, path: "fixture/guide.md" };
    } } },
  };
  const fetch = async (url) => {
    fetchCalls.push(url);
    if (url === "/guide/catalog.json") return { ok: true, json: async () => ({ items: [], filters: {} }) };
    return {
      ok: true,
      headers: { get(name) { return name === "content-type" ? "text/markdown; charset=utf-8" : 'attachment; filename="guide.md"'; } },
      blob: async () => ({ size: 7, text: async () => "# Guia" }),
    };
  };
  const context = vm.createContext({
    document,
    window,
    fetch,
    URL: { createObjectURL: () => "blob:fixture", revokeObjectURL() {} },
    console: { error() {} },
    NodeFilter: { SHOW_TEXT: 4 },
    matchMedia: () => ({ matches: true }),
  });
  return {
    context, document, listeners, fetchCalls, exportDestinations, root, searchStatus,
    exportStatus, exportButton, catalogStatus,
    setCurrentRoot(value) { activeRoot = value; },
    parsedDocument: {
      querySelector(selector) {
        if (selector.includes("guide-utils.js")) return { getAttribute: () => "/static/js/guide-utils.js?v=fixture" };
        if (selector.includes("guide.js")) return { getAttribute: () => "/static/js/guide.js?v=fixture" };
        return null;
      },
    },
    currentMain: { querySelector(selector) { return selector === ".game-guide" ? root : null; } },
  };
}

async function verifyGuideInteractions(fixture) {
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(fixture.fetchCalls.filter((path) => path === "/guide/catalog.json").length, 1);
  assert.match(fixture.catalogStatus.textContent, /0 item\(ns\)/);
  fixture.listeners.get("search:submit")({ preventDefault() {} });
  assert.match(fixture.searchStatus.textContent, /Resultado encontrado para portal/);
  await fixture.listeners.get("export:click")();
  assert.match(fixture.exportStatus.textContent, /Guia salvo em: fixture\/guide\.md/);
  assert.deepEqual(fixture.exportDestinations, ["# Guia"]);
}

test("the Guide initializes directly and after partial navigation from another page", async () => {
  const direct = makeGuideFixture({ initialRoot: null });
  direct.setCurrentRoot(direct.root);
  vm.runInContext(utilsSource, direct.context);
  vm.runInContext(guideSource, direct.context);
  await verifyGuideInteractions(direct);

  const partial = makeGuideFixture({ initialRoot: null });
  vm.runInContext(helperSource, partial.context);
  assert.equal(partial.fetchCalls.length, 0, "the prior non-Guide page has no Guide requests");
  partial.setCurrentRoot(partial.root);
  partial.context.initializeGameGuideForContent(partial.parsedDocument, partial.currentMain);
  await verifyGuideInteractions(partial);

  partial.context.initializeGameGuideForContent(partial.parsedDocument, partial.currentMain);
  assert.equal(partial.listeners.get("search:submit") !== undefined, true);
  assert.equal(partial.fetchCalls.filter((path) => path === "/guide/catalog.json").length, 1,
    "reinitializing the same root does not duplicate handlers or catalog requests");
});
