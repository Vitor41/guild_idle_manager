import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const mainSource = await readFile(new URL("../../app/static/js/main.js", import.meta.url), "utf8");
const guideSource = await readFile(new URL("../../app/static/js/guide.js", import.meta.url), "utf8");
const utilsSource = await readFile(new URL("../../app/static/js/guide-utils.js", import.meta.url), "utf8");
const globalSubmitHandler = mainSource.match(/document\.addEventListener\("submit", async \(event\) => \{[\s\S]*?^\}\);/m)?.[0];
assert.ok(globalSubmitHandler, "global form submit handler is present");
const helperSource = mainSource.match(/^let guideAssetLoadPromise = null;\r?\nfunction initializeGameGuideForContent\([\s\S]*?^\}/m)?.[0];
assert.ok(helperSource, "partial-navigation Guide initializer is present");
const replacementSource = mainSource.match(/^function replaceGameContent\([\s\S]*?^\}/m)?.[0];
assert.match(replacementSource || "", /initializeGameGuideForContent\(parsedDocument, currentMain\)/);

function makeGuideFixture({ initialRoot }) {
  const listeners = new Map();
  const fetchCalls = [];
  const exportDestinations = [];
  const searchRanges = [];
  let activeRoot = initialRoot;
  const searchFocusTargets = [];
  const searchStatus = { textContent: "" };
  const exportStatus = { textContent: "", setAttribute(name, value) { this[name] = value; } };
  const exportFeedback = { hidden: true };
  const exportProgress = { hidden: true };
  const loadedAssets = [];
  const attemptedAssets = [];
  let failNextAssetLoad = false;
  let genericFormDataCalls = 0;
  const exportButton = {
    disabled: false,
    textContent: "Baixar Guia em Markdown",
    addEventListener(name, callback) { listeners.set(`export:${name}`, callback); },
    setAttribute(name, value) { this[name] = value; },
    removeAttribute(name) { delete this[name]; },
  };
  const searchInput = { value: "portal", focus() { searchFocusTargets.push("input"); } };
  class HTMLFormElementStub {}
  const searchForm = Object.assign(new HTMLFormElementStub(), {
    method: "get",
    dataset: {},
    closest(selector) { return selector === ".game-shell" ? {} : null; },
    addEventListener(name, callback) { listeners.set(`search:${name}`, callback); },
    querySelector(selector) { return selector === "#guide-search-query" ? searchInput : null; },
  });
  const rows = { children: [], replaceChildren(...children) { this.children = children; }, append(child) { this.children.push(child); } };
  const catalogStatus = { textContent: "", hidden: false };
  const retryButton = { dataset: {}, listeners: {}, addEventListener(name, callback) { this.listeners[name] = callback; } };
  const errorMessage = { textContent: "Não foi possível carregar o catálogo agora." };
  const catalogError = {
    hidden: true,
    setAttribute(name, value) { this[name] = value; },
    querySelector(selector) {
      if (selector === "p") return errorMessage;
      if (selector === "[data-guide-catalog-retry]") return retryButton;
      return null;
    },
  };
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
    nodeValue: "O portal aparece antes do portal.",
    parentElement: { closest() { return null; } },
  };
  const document = {
    addEventListener(name, callback) {
      if (name === "submit") listeners.set("document:submit", callback);
    },
    createTextNode(text) { return { nodeValue: text }; },
    head: { append(script) {
      attemptedAssets.push(script.src);
      if (failNextAssetLoad) {
        failNextAssetLoad = false;
        script.listeners.error?.(new Error("fixture load failure"));
        return;
      }
      loadedAssets.push(script.src);
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
        parentNode: { replaceChild() {}, normalize() {} },
        scrollIntoView() {},
        focus() { searchFocusTargets.push("result"); },
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
    createRange() {
      let start = null;
      let end = null;
      return {
        setStart(node, index) { start = { node, index }; },
        setEnd(node, index) { end = { node, index }; },
        surroundContents(mark) { searchRanges.push({ start, end, mark }); },
      };
    },
  };
  const window = {
    GuideUtils: undefined,
    location: { origin: "https://guide.test" },
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
  const URLApi = class extends URL {};
  URLApi.createObjectURL = () => "blob:fixture";
  URLApi.revokeObjectURL = () => {};
  const context = vm.createContext({
    document,
    window,
    fetch,
    HTMLFormElement: HTMLFormElementStub,
    FormData: class {
      constructor() {
        genericFormDataCalls += 1;
        throw new Error("Guide search reached the generic game form handler");
      }
    },
    URL: URLApi,
    console: { error() {} },
    NodeFilter: { SHOW_TEXT: 4 },
    matchMedia: () => ({ matches: true }),
  });
  return {
    context, document, listeners, fetchCalls, exportDestinations, searchRanges, searchFocusTargets, root, searchStatus,
    exportStatus, exportButton, catalogStatus,
    catalogError, errorMessage, retryButton, loadedAssets, attemptedAssets,
    searchForm, searchInput, genericFormDataCalls: () => genericFormDataCalls,
    failNextAssetLoad() { failNextAssetLoad = true; },
    setCurrentRoot(value) { activeRoot = value; },
    parsedDocument: {
      querySelectorAll() { return [
        { getAttribute: () => "/static/js/guide-utils.js?v=fixture" },
        { getAttribute: () => "/static/js/guide.js?v=fixture" },
      ]; },
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

test("Guide Enter and button searches stay in the Guide before the global form handler", async () => {
  const fixture = makeGuideFixture({ initialRoot: null });
  vm.runInContext(helperSource, fixture.context);
  vm.runInContext(globalSubmitHandler, fixture.context);
  fixture.setCurrentRoot(fixture.root);
  fixture.context.initializeGameGuideForContent(fixture.parsedDocument, fixture.currentMain);
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(fixture.loadedAssets, [
    "https://guide.test/static/js/guide-utils.js?v=fixture",
    "https://guide.test/static/js/guide.js?v=fixture",
  ], "partial navigation loads the real Guide assets before binding the search");

  const localSearch = fixture.listeners.get("search:submit");
  const globalSubmit = fixture.listeners.get("document:submit");
  assert.equal(typeof localSearch, "function");
  assert.equal(typeof globalSubmit, "function");

  const scenarios = [
    { term: "portal", status: /Resultado encontrado para portal/, hasMatch: true },
    { term: "missing-term", status: /Nenhum resultado para missing-term/, hasMatch: false },
    { term: "", status: /Digite um termo para pesquisar/, hasMatch: false },
  ];
  for (const scenario of scenarios) {
    for (const submission of [
      { kind: "Enter", submitter: null },
      { kind: "button", submitter: { type: "submit", name: "search", value: "Buscar" } },
    ]) {
      fixture.searchInput.value = scenario.term;
      const rangesBefore = fixture.searchRanges.length;
      const event = {
        target: fixture.searchForm,
        submitter: submission.submitter,
        defaultPrevented: false,
        preventDefault() { this.defaultPrevented = true; },
      };
      localSearch(event);
      assert.equal(event.defaultPrevented, true, `${submission.kind} search is consumed by the Guide`);
      await assert.doesNotReject(() => globalSubmit(event), `${submission.kind} does not reach generic navigation`);
      assert.match(fixture.searchStatus.textContent, scenario.status);
      assert.equal(fixture.searchInput.value, scenario.term, `${submission.kind} keeps the search term`);
      assert.equal(fixture.searchRanges.length, rangesBefore + Number(scenario.hasMatch),
        `${submission.kind} ${scenario.term || "empty"} result state is represented accurately`);
      if (scenario.hasMatch) assert.equal(fixture.searchFocusTargets.at(-1), "result");
      if (!scenario.term) assert.equal(fixture.searchFocusTargets.at(-1), "input");
    }
  }

  assert.equal(fixture.searchRanges.length, 2, "found search is highlighted for Enter and button");
  for (const result of fixture.searchRanges) {
    assert.equal(result.start.node.nodeValue.slice(result.start.index, result.end.index), "portal",
      "each interaction highlights the first matching result");
    assert.equal(result.start.index, 2);
  }
  assert.equal(fixture.genericFormDataCalls(), 0, "the global handler never serializes a Guide search as gameplay navigation");
  assert.deepEqual(fixture.fetchCalls, ["/guide/catalog.json"], "only the catalog request runs; search stays local");
});

test("partial Guide loading accepts only exact versioned same-origin static script paths", async () => {
  const fixture = makeGuideFixture({ initialRoot: null });
  vm.runInContext(helperSource, fixture.context);
  fixture.setCurrentRoot(fixture.root);
  const invalidSources = [
    "https://outside.invalid/static/js/guide-utils.js?v=fixture",
    "//outside.invalid/static/js/guide-utils.js?v=fixture",
    "https://guide.test/static/js/guide-utils.js.evil?v=fixture",
    "https://guide.test/static/js/guide-utils.js/extra?v=fixture",
    "https://guide.test/static/js/%67uide-utils.js?v=fixture",
    "data:text/javascript,window.alert(1)",
    "javascript:window.alert(1)",
    "file:///static/js/guide-utils.js",
  ];

  for (const expectedFile of ["guide-utils.js", "guide.js"]) {
    for (const invalidSource of invalidSources) {
      fixture.parsedDocument.querySelectorAll = () => expectedFile === "guide-utils.js"
        ? [
          { getAttribute: () => invalidSource },
          { getAttribute: () => "/static/js/guide.js?v=fixture" },
        ]
        : [
          { getAttribute: () => "/static/js/guide-utils.js?v=fixture" },
          { getAttribute: () => invalidSource.replace("guide-utils.js", "guide.js") },
        ];
      fixture.context.initializeGameGuideForContent(fixture.parsedDocument, fixture.currentMain);
      assert.equal(fixture.loadedAssets.length, 0, `${expectedFile} rejected ${invalidSource}`);
      assert.equal(fixture.catalogError.hidden, false);
      assert.match(fixture.errorMessage.textContent, /Saia e abra o Guia novamente/);
      assert.equal(typeof fixture.retryButton.listeners.click, "function");
    }
  }
});

test("a failed script load exposes a retry that completes on the same Guide root", async () => {
  const fixture = makeGuideFixture({ initialRoot: null });
  vm.runInContext(helperSource, fixture.context);
  fixture.setCurrentRoot(fixture.root);
  fixture.failNextAssetLoad();
  fixture.context.initializeGameGuideForContent(fixture.parsedDocument, fixture.currentMain);
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(fixture.loadedAssets.length, 0);
  assert.equal(fixture.catalogError.hidden, false);
  assert.equal(typeof fixture.retryButton.listeners.click, "function");
  fixture.retryButton.listeners.click();
  await verifyGuideInteractions(fixture);

  assert.equal(fixture.attemptedAssets.length, 3, "one failed utility load is retried, then both safe assets load");
  assert.equal(fixture.loadedAssets.length, 2);
});
