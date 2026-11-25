import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const main = await readFile(new URL("../../app/static/js/main.js", import.meta.url), "utf8");
const fragmentHelper = main.match(/^function preserveRequestedNavigationFragment\([\s\S]*?^\}/m)?.[0];
const sidebarSyncFunction = main.match(/^function syncCurrentSidebarPage\([\s\S]*?^\}/m)?.[0];
const replaceFunction = main.match(/^function replaceGameContent\([\s\S]*?^\}(?=\r?\n\r?\nfunction regionalNoticeMatches)/m)?.[0];
const noticeSyncFunction = main.match(/^function syncRegionalEventNoticeDialogs\([\s\S]*?^\}/m)?.[0];
const clickStart = main.indexOf('document.addEventListener("click", async (event) => {');
const clickEnd = main.indexOf("\n});", clickStart) + 4;
assert.ok(fragmentHelper, "fragment helper is present");
assert.ok(sidebarSyncFunction, "current sidebar page helper is present");
assert.ok(replaceFunction, "partial page replacement function is present");
assert.ok(noticeSyncFunction, "regional notice synchronization is present");
assert.ok(clickStart >= 0 && clickEnd > clickStart, "async navigation click handler is present");
const clickHandler = main.slice(clickStart, clickEnd);

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
    "initializeUpdateChecks",
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

  vm.runInContext(`${fragmentHelper}\n${sidebarSyncFunction}\n${replaceFunction}\n${clickHandler}`, context, { filename: "main-navigation.js" });
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
