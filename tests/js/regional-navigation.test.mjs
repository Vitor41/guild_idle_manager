import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const main = await readFile(new URL("../../app/static/js/main.js", import.meta.url), "utf8");
const fragmentHelper = main.match(/^function preserveRequestedNavigationFragment\([\s\S]*?^\}/m)?.[0];
const sidebarSyncFunction = main.match(/^function syncCurrentSidebarPage\([\s\S]*?^\}/m)?.[0];
const navigationRevisionDeclaration = main.match(/^let gameNavigationRevision = 0;$/m)?.[0];
const beginNavigationFunction = main.match(/^function beginGameNavigation\([\s\S]*?^\}/m)?.[0];
const currentNavigationFunction = main.match(/^function isCurrentGameNavigation\([\s\S]*?^\}/m)?.[0];
const replaceFunction = main.match(/^function replaceGameContent\([\s\S]*?^\}(?=\r?\n\r?\nfunction regionalNoticeMatches)/m)?.[0];
const noticeSyncFunction = main.match(/^function syncRegionalEventNoticeDialogs\([\s\S]*?^\}/m)?.[0];
const clickStart = main.indexOf('document.addEventListener("click", async (event) => {');
const clickEnd = main.indexOf("\n});", clickStart) + 4;
const submitStart = main.indexOf('document.addEventListener("submit", async (event) => {');
const submitEnd = main.indexOf("\n});", submitStart) + 4;
const submitHandler = main.slice(submitStart, submitEnd);
assert.ok(fragmentHelper, "fragment helper is present");
assert.ok(sidebarSyncFunction, "current sidebar page helper is present");
assert.ok(navigationRevisionDeclaration, "navigation revision counter is present");
assert.ok(beginNavigationFunction, "navigation start helper is present");
assert.ok(currentNavigationFunction, "navigation freshness guard is present");
assert.ok(replaceFunction, "partial page replacement function is present");
assert.ok(noticeSyncFunction, "regional notice synchronization is present");
assert.ok(clickStart >= 0 && clickEnd > clickStart, "async navigation click handler is present");
assert.ok(submitStart >= 0 && submitEnd > submitStart, "async form submission handler is present");
const clickHandler = main.slice(clickStart, clickEnd);

class NavigationTestForm {
  constructor() {
    this.method = "post";
    this.action = "/regional/action";
    this.dataset = { gimDiagnosticId: "navigation-test" };
    this.attributes = new Map();
    this.classList = { add() {}, remove() {} };
    this.fields = [];
  }
  closest(selector) { return selector === ".game-shell" ? {} : null; }
  querySelector() { return null; }
  setAttribute(name, value) { this.attributes.set(name, value); }
  removeAttribute(name) { this.attributes.delete(name); }
}

class NavigationTestElement {}

test("async navigation keeps a requested portal fragment through a redirect and focuses the portal", async () => {
  const requestedUrl = "http://localhost/regional?tab=portals#regional-event-42";
  const redirectedUrl = "http://localhost/regional?tab=current";
  const requestedCalls = [];
  const historyCalls = [];
  const scrollCalls = [];
  const focusCalls = [];
  const resetInitializerCalls = [];
  const updateCheckInitializerCalls = [];
  const noticeSyncCalls = [];
  let clickHandlerCallback;
  const incomingMain = { innerHTML: "fresh regional page" };
  const currentMain = { innerHTML: "old page" };
  const portalCard = {
    focus(options) { focusCalls.push(options); },
    scrollIntoView(options) { scrollCalls.push(options); },
  };
  const parsedDocument = {
    title: "Vigília",
    querySelector(selector) {
      if (selector === ".game-shell") return incomingMain;
      return null;
    },
    querySelectorAll() { return []; },
  };
  const link = {
    href: requestedUrl,
    hasAttribute() { return false; },
    setAttribute() {},
  };
  const menuLink = (href) => ({
    href,
    attributes: new Map(),
    setAttribute(name, value) { this.attributes.set(name, value); },
    removeAttribute(name) { this.attributes.delete(name); },
    getAttribute(name) { return this.attributes.get(name) ?? null; },
  });
  const regionalMenuLink = menuLink("http://localhost/regional");
  const eventsMenuLink = menuLink("http://localhost/regional/events");
  const document = {
    title: "Anterior",
    body: { dataset: {} },
    documentElement: { scrollHeight: 1800 },
    addEventListener(name, callback) {
      if (name === "click" && !clickHandlerCallback) clickHandlerCallback = callback;
    },
    querySelector(selector) { return selector === ".game-shell" ? currentMain : null; },
    querySelectorAll(selector) {
      return selector === ".sidebar-nav a[href]" ? [regionalMenuLink, eventsMenuLink] : [];
    },
    getElementById(id) { return id === "regional-event-42" ? portalCard : null; },
  };
  const window = {
    location: { origin: "http://localhost", pathname: "/updates", href: "http://localhost/updates" },
    innerHeight: 600,
    scrollY: 240,
    history: { replaceState(_state, _title, url) { historyCalls.push(url); } },
    requestAnimationFrame(callback) { callback(); },
    scrollTo(options) { scrollCalls.push(options); },
    GIMApplyDesktopArt() {},
    initializeBuildingResetDialogs(root) { resetInitializerCalls.push(root); },
    locationAssignCalls: [],
  };
  window.location.assign = (url) => window.locationAssignCalls.push(url);
  const stubs = [
    "initializeGameGuideForContent", "initializeEquipmentDetails", "initializeMarketEstimates", "initializeGatheringCycles",
    "initializeUpdateChecks", "initializeClassGuideIndex", "initializeDockPurchaseEstimates",
    "updateGenericCountdowns", "initializeSalvagePreviews",
    "restoreGameFormState", "initializeRegionalSupply", "initializeRegionalComparison", "refreshResourceTotals", "initializeHeaderPopovers",
    "showActionToast", "refreshNavigationWorkIndicators",
  ];
  const context = vm.createContext({
    URL,
    Map,
    document,
    window,
    DOMParser: class { parseFromString() { return parsedDocument; } },
    captureGameFormState: () => new Map(),
    fetch: async (url, options) => {
      requestedCalls.push({ url: String(url), options });
      return { ok: true, url: redirectedUrl, text: async () => "redirected html" };
    },
    ...Object.fromEntries(stubs.map((name) => [name, (root) => {
      if (name === "initializeUpdateChecks") updateCheckInitializerCalls.push(root);
    }])),
    syncRegionalEventNoticeDialogs(...args) { noticeSyncCalls.push(args); },
  });

  vm.runInContext(`${navigationRevisionDeclaration}\n${beginNavigationFunction}\n${currentNavigationFunction}\n${fragmentHelper}\n${sidebarSyncFunction}\n${replaceFunction}\n${clickHandler}`, context, { filename: "main-navigation.js" });
  const event = {
    button: 0,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    altKey: false,
    defaultPrevented: false,
    target: {
      closest(selector) {
        return selector === "[data-regional-notice-close]" ? null : link;
      },
    },
    preventDefault() { this.defaultPrevented = true; },
  };
  await clickHandlerCallback(event);

  assert.equal(event.defaultPrevented, true);
  assert.equal(requestedCalls.length, 1);
  assert.equal(requestedCalls[0].options.method, "GET");
  assert.equal(requestedCalls[0].url, requestedUrl);
  assert.equal(noticeSyncCalls.length, 1);
  assert.equal(noticeSyncCalls[0][1], true, "anchored event navigation suppresses startup notices");
  assert.deepEqual(historyCalls, ["/regional?tab=current#regional-event-42"]);
  assert.equal(window.locationAssignCalls.length, 0);
  assert.equal(focusCalls.length, 1);
  assert.equal(focusCalls[0].preventScroll, true);
  assert.equal(scrollCalls.length, 1);
  assert.equal(scrollCalls[0].block, "start");
  assert.equal(scrollCalls[0].behavior, "auto");
  assert.equal(document.body.dataset.route, "/regional");
  assert.equal(regionalMenuLink.getAttribute("aria-current"), "page");
  assert.equal(eventsMenuLink.getAttribute("aria-current"), null);
  assert.deepEqual(resetInitializerCalls, [currentMain]);
  assert.deepEqual(updateCheckInitializerCalls, [currentMain]);
});

function createNavigationHarness(fetchImplementation) {
  let clickHandlerCallback = null;
  let submitHandlerCallback = null;
  const historyCalls = [];
  const scrollCalls = [];
  const locationAssignCalls = [];
  let currentMain = { innerHTML: "initial content" };
  const menuLink = (href) => ({
    href,
    attributes: new Map(),
    setAttribute(name, value) { this.attributes.set(name, value); },
    removeAttribute(name) { this.attributes.delete(name); },
    getAttribute(name) { return this.attributes.get(name) ?? null; },
  });
  const regionalMenuLink = menuLink("http://localhost/regional");
  const eventsMenuLink = menuLink("http://localhost/regional/events");
  const document = {
    title: "Painel",
    body: { dataset: { route: "/dashboard" } },
    documentElement: { scrollHeight: 1800 },
    addEventListener(name, callback) {
      if (name === "click" && !clickHandlerCallback) clickHandlerCallback = callback;
      if (name === "submit" && !submitHandlerCallback) submitHandlerCallback = callback;
    },
    querySelector(selector) {
      if (selector === ".game-shell") return currentMain;
      return null;
    },
    querySelectorAll(selector) {
      return selector === ".sidebar-nav a[href]" ? [regionalMenuLink, eventsMenuLink] : [];
    },
    getElementById() { return null; },
  };
  const window = {
    location: { origin: "http://localhost", pathname: "/dashboard", href: "http://localhost/dashboard" },
    innerHeight: 600,
    scrollY: 120,
    history: { replaceState(_state, _title, url) { historyCalls.push(url); } },
    requestAnimationFrame(callback) { callback(); },
    scrollTo(options) { scrollCalls.push(options); },
    GIMApplyDesktopArt() {},
    initializeBuildingResetDialogs() {},
    locationAssignCalls,
  };
  window.location.assign = (url) => locationAssignCalls.push(String(url));
  const stubs = [
    "initializeClassGuideIndex", "initializeWorkshopSupplyControls", "initializeDockPurchaseEstimates",
    "initializeUpdateChecks", "initializeGameGuideForContent", "initializeEquipmentDetails",
    "initializeMarketEstimates", "initializeGatheringCycles", "updateGenericCountdowns",
    "initializeSalvagePreviews", "restoreGameFormState", "refreshResourceTotals",
    "initializeHeaderPopovers", "initializeRegionalSupply", "initializeRegionalComparison",
    "showActionToast", "refreshNavigationWorkIndicators",
  ];
  const context = vm.createContext({
    URL,
    Map,
    document,
    window,
    DOMParser: class {
      parseFromString(html) {
        const page = html === "central html"
          ? { title: "Eventos regionais", route: "/regional/events" }
          : { title: "Vigília", route: "/regional" };
        return {
          title: page.title,
          querySelector(selector) {
            if (selector === ".game-shell") return { innerHTML: html };
            return null;
          },
          querySelectorAll() { return []; },
        };
      }
    },
    captureGameFormState: () => new Map(),
    fetch: fetchImplementation,
    HTMLFormElement: NavigationTestForm,
    HTMLElement: NavigationTestElement,
    FormData: class extends Map { constructor(form) { super(form.fields); } },
    URLSearchParams,
    getFormSubmitAction: (form) => form.action,
    preservePageContext: (url) => new URL(url, "http://localhost"),
    createGameplayDiagnosticId: () => "generated-navigation-test",
    ...Object.fromEntries(stubs.map((name) => [name, () => {}])),
    syncRegionalEventNoticeDialogs() {},
  });
  vm.runInContext(
    `${navigationRevisionDeclaration}\n${beginNavigationFunction}\n${currentNavigationFunction}\n${fragmentHelper}\n${sidebarSyncFunction}\n${replaceFunction}\n${clickHandler}\n${submitHandler}`,
    context,
    { filename: "main-navigation-race.js" },
  );
  const click = (path) => {
    const link = {
      href: `http://localhost${path}`,
      hasAttribute() { return false; },
      setAttribute() {},
    };
    const event = {
      button: 0,
      ctrlKey: false,
      metaKey: false,
      shiftKey: false,
      altKey: false,
      defaultPrevented: false,
      target: {
        closest(selector) {
          return selector === "[data-regional-notice-close]" ? null : link;
        },
      },
      preventDefault() { this.defaultPrevented = true; },
    };
    return clickHandlerCallback(event);
  };
  const submit = (form) => {
    const event = {
      target: form,
      submitter: null,
      defaultPrevented: false,
      preventDefault() { this.defaultPrevented = true; },
    };
    return submitHandlerCallback(event);
  };
  return {
    click,
    submit,
    document,
    get currentMain() { return currentMain; },
    replaceRoot(root) { currentMain = root; },
    historyCalls,
    locationAssignCalls,
    regionalMenuLink,
    eventsMenuLink,
    scrollCalls,
  };
}

test("the most recently requested regional page wins when responses arrive out of order", async () => {
  const pending = new Map();
  const fetchImplementation = (url) => new Promise((resolve, reject) => {
    const parsed = new URL(String(url));
    const key = parsed.searchParams.has("crSlow") ? "slow" : "fast";
    pending.set(key, { resolve, reject, url: parsed.href });
  });
  const harness = createNavigationHarness(fetchImplementation);
  const slowRequest = harness.click("/regional?crSlow=1");
  const fastRequest = harness.click("/regional/events?crFast=1");

  pending.get("fast").resolve({ ok: true, url: pending.get("fast").url, text: async () => "central html" });
  await fastRequest;
  pending.get("slow").resolve({ ok: true, url: pending.get("slow").url, text: async () => "regional html" });
  await slowRequest;

  assert.equal(harness.document.body.dataset.route, "/regional/events");
  assert.equal(harness.document.title, "Eventos regionais");
  assert.equal(harness.currentMain.innerHTML, "central html");
  assert.deepEqual(harness.historyCalls, ["/regional/events?crFast=1"]);
  assert.equal(harness.regionalMenuLink.getAttribute("aria-current"), null);
  assert.equal(harness.eventsMenuLink.getAttribute("aria-current"), "page");
  assert.equal(harness.locationAssignCalls.length, 0);
});

test("an obsolete navigation error does not trigger fallback over the winning page", async () => {
  const pending = new Map();
  const fetchImplementation = (url) => new Promise((resolve, reject) => {
    const parsed = new URL(String(url));
    const key = parsed.searchParams.has("crSlow") ? "slow" : "fast";
    pending.set(key, { resolve, reject, url: parsed.href });
  });
  const harness = createNavigationHarness(fetchImplementation);
  const slowRequest = harness.click("/regional?crSlow=1");
  const fastRequest = harness.click("/regional/events?crFast=1");

  pending.get("fast").resolve({ ok: true, url: pending.get("fast").url, text: async () => "central html" });
  await fastRequest;
  pending.get("slow").reject(new Error("late response error"));
  await slowRequest;

  assert.equal(harness.document.body.dataset.route, "/regional/events");
  assert.equal(harness.document.title, "Eventos regionais");
  assert.deepEqual(harness.historyCalls, ["/regional/events?crFast=1"]);
  assert.equal(harness.locationAssignCalls.length, 0, "a stale error must not perform a full-page fallback");
});

test("a response is ignored if the game shell root changed while it was loading", async () => {
  let resolveResponse;
  const harness = createNavigationHarness(() => new Promise((resolve) => { resolveResponse = resolve; }));
  const request = harness.click("/regional?rootChanged=1");
  const replacementRoot = { innerHTML: "new campaign root" };
  harness.replaceRoot(replacementRoot);
  harness.document.body.dataset.route = "/regional/events";
  harness.document.title = "Eventos regionais";
  resolveResponse({ ok: true, url: "http://localhost/regional?rootChanged=1", text: async () => "regional html" });
  await request;

  assert.equal(harness.currentMain, replacementRoot);
  assert.equal(harness.currentMain.innerHTML, "new campaign root");
  assert.equal(harness.document.body.dataset.route, "/regional/events");
  assert.deepEqual(harness.historyCalls, []);
});

test("a current navigation error can still fall back and a later request can retry", async () => {
  let calls = 0;
  const harness = createNavigationHarness(async (url) => {
    calls += 1;
    if (calls === 1) throw new Error("temporary network error");
    return { ok: true, url: String(url), text: async () => "central html" };
  });

  await harness.click("/regional?crRetry=1");
  assert.deepEqual(harness.locationAssignCalls, ["http://localhost/regional?crRetry=1"]);
  await harness.click("/regional/events?crRetry=2");

  assert.equal(calls, 2);
  assert.equal(harness.document.body.dataset.route, "/regional/events");
  assert.equal(harness.document.title, "Eventos regionais");
  assert.equal(harness.currentMain.innerHTML, "central html");
  assert.deepEqual(harness.historyCalls, ["/regional/events?crRetry=2"]);
});

test("a gameplay POST is still sent while a later page navigation owns the visible result", async () => {
  let resolvePost;
  const requests = [];
  const harness = createNavigationHarness((url, options = {}) => {
    requests.push({ url: String(url), method: options.method || "GET", body: options.body });
    if (options.method === "POST") {
      return new Promise((resolve) => { resolvePost = resolve; });
    }
    return Promise.resolve({ ok: true, url: String(url), text: async () => "central html" });
  });
  const form = new NavigationTestForm();
  const postRequest = harness.submit(form);
  assert.equal(requests[0].method, "POST");
  const pageRequest = harness.click("/regional/events?afterAction=1");
  await pageRequest;
  resolvePost({ ok: true, url: "http://localhost/dashboard", text: async () => "regional html" });
  await postRequest;

  assert.equal(requests[0].url, "http://localhost/regional/action");
  assert.equal(harness.document.body.dataset.route, "/regional/events");
  assert.equal(harness.document.title, "Eventos regionais");
  assert.equal(harness.currentMain.innerHTML, "central html");
  assert.deepEqual(harness.historyCalls, ["/regional/events?afterAction=1"]);
});

test("async navigation marks Events active separately from the Vigília", () => {
  const menuLink = (href) => ({
    href,
    attributes: new Map([["aria-current", "page"]]),
    setAttribute(name, value) { this.attributes.set(name, value); },
    removeAttribute(name) { this.attributes.delete(name); },
    getAttribute(name) { return this.attributes.get(name) ?? null; },
  });
  const regionalMenuLink = menuLink("http://localhost/regional");
  const eventsMenuLink = menuLink("http://localhost/regional/events");
  const context = vm.createContext({
    URL,
    document: { querySelectorAll: () => [regionalMenuLink, eventsMenuLink] },
    window: { location: { origin: "http://localhost" } },
  });
  vm.runInContext(sidebarSyncFunction, context, { filename: "sidebar-navigation.js" });
  context.syncCurrentSidebarPage("/regional/events");
  assert.equal(regionalMenuLink.getAttribute("aria-current"), null);
  assert.equal(eventsMenuLink.getAttribute("aria-current"), "page");
});

test("an event hash target removes startup notices without enqueuing them", () => {
  const queue = { removed: [], enqueued: [], remove(dialog) { this.removed.push(dialog); }, enqueue(dialog) { this.enqueued.push(dialog); } };
  const current = {
    dataset: {},
    open: true,
    closed: false,
    removed: false,
    close() { this.open = false; this.closed = true; },
    remove() { this.removed = true; },
  };
  const incoming = { id: "regional-portal-notice" };
  const document = { querySelectorAll: () => [current] };
  const parsedDocument = { querySelectorAll: () => [incoming] };
  const context = vm.createContext({
    document,
    window: { GIMStartupModalQueue: queue },
  });

  vm.runInContext(noticeSyncFunction, context, { filename: "regional-notice-sync.js" });
  context.syncRegionalEventNoticeDialogs(parsedDocument, true);

  assert.equal(current.closed, true);
  assert.equal(current.removed, true);
  assert.equal(current.dataset.regionalNoticeProgrammaticClose, "true");
  assert.deepEqual(queue.removed, [current]);
  assert.deepEqual(queue.enqueued, []);
});

test("an intentional redirect fragment takes precedence over the requested fragment", () => {
  const output = new Function("window", "URL", `${fragmentHelper}; return preserveRequestedNavigationFragment;`)(
    { location: { origin: "http://localhost" } },
    URL,
  );
  assert.equal(
    output("http://localhost/regional#redirect-target", "http://localhost/regional#requested-target"),
    "http://localhost/regional#redirect-target",
  );
  assert.equal(
    output("https://other.example/regional", "http://localhost/regional#requested-target"),
    "https://other.example/regional",
  );
});
