import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../../", import.meta.url);
const main = await readFile(new URL("app/static/js/main.js", root), "utf8");
const desktopArt = await readFile(new URL("app/static/js/desktop-art.js", root), "utf8");
const baseTemplate = await readFile(new URL("app/templates/base.html", root), "utf8");
const campaignsTemplate = await readFile(new URL("app/templates/desktop/campaigns.html", root), "utf8");
const dashboardTemplate = await readFile(new URL("app/templates/dashboard.html", root), "utf8");
const missionsTemplate = await readFile(new URL("app/templates/missions/index.html", root), "utf8");
const mainCss = await readFile(new URL("app/static/css/main.css", root), "utf8");
const desktopTheme = await readFile(new URL("app/static/css/desktop-theme.css", root), "utf8");
const desktopEvolution = await readFile(new URL("app/static/css/desktop-evolution.css", root), "utf8");

function extract(source, expression, label) {
  const match = source.match(expression);
  assert.ok(match, `${label} is present`);
  return match[0];
}

test("resource totals format server values immediately and refresh partial navigation once", async () => {
  const element = (kind, text) => ({ dataset: { resourceTotal: kind }, textContent: text });
  const elements = [element("gold", "1234567"), element("wood", "23.456")];
  const document = {
    querySelector() { return elements.length ? elements[0] : null; },
    querySelectorAll() { return elements; },
  };
  let fetchCount = 0;
  let resolveFetch;
  const fetch = () => {
    fetchCount += 1;
    return new Promise((resolve) => { resolveFetch = resolve; });
  };
  const sources = [
    extract(main, /^const resourceTotalFormatter = .*;$/m, "resource formatter"),
    "let resourceTotalsRequest = null;",
    extract(main, /^function parseResourceTotal\([\s\S]*?^\}/m, "resource parser"),
    extract(main, /^function formatResourceTotals\([\s\S]*?^\}/m, "resource formatter helper"),
    extract(main, /^async function refreshResourceTotals\([\s\S]*?^\}/m, "resource refresh helper"),
    "return {formatResourceTotals, refreshResourceTotals};",
  ];
  const helpers = new Function("document", "fetch", sources.join("\n"))(document, fetch);

  helpers.formatResourceTotals();
  helpers.formatResourceTotals();
  assert.deepEqual(elements.map((item) => item.textContent), ["1.234.567", "23.456"]);

  const first = helpers.refreshResourceTotals();
  const insertedAfterNavigation = element("gold", "7654321");
  elements.push(insertedAfterNavigation);
  const second = helpers.refreshResourceTotals();
  assert.equal(fetchCount, 1, "overlapping polling and navigation share one request");
  assert.equal(insertedAfterNavigation.textContent, "7.654.321", "inserted server value is localized before the fetch returns");

  resolveFetch({ ok: true, json: async () => ({ gold: 8_765_432, wood: 23456 }) });
  await Promise.all([first, second]);
  assert.deepEqual(elements.map((item) => item.textContent), ["8.765.432", "23.456", "8.765.432"]);
  assert.equal(fetchCount, 1);
});

test("header treasury and offline help are one keyboard and pointer controlled popover", () => {
  const popovers = [];
  const makePopover = (name) => {
    const listeners = new Map();
    const summary = { focused: 0, focus() { this.focused += 1; } };
    const item = {
      name,
      open: false,
      dataset: {},
      summary,
      addEventListener(type, callback) { listeners.set(type, [...(listeners.get(type) || []), callback]); },
      fire(type) { for (const callback of listeners.get(type) || []) callback(); },
      listenerCount(type) { return (listeners.get(type) || []).length; },
      contains(target) { return target === this || target === summary || target === `${name}-inside`; },
      querySelector(selector) { return selector === "summary" ? summary : null; },
    };
    popovers.push(item);
    return item;
  };
  const treasury = makePopover("treasury");
  const offline = makePopover("offline");
  const document = {
    querySelectorAll() { return popovers; },
    querySelector() { return popovers.find((item) => item.open) || null; },
    addEventListener() {},
  };
  const helpers = new Function(
    "document",
    [
      extract(main, /^function initializeHeaderPopovers\([\s\S]*?^\}/m, "popover initializer"),
      extract(main, /^function closeOtherHeaderPopovers\([\s\S]*?^\}/m, "popover exclusivity helper"),
      extract(main, /^function dismissHeaderPopoversOutside\([\s\S]*?^\}/m, "outside dismissal helper"),
      extract(main, /^function dismissHeaderPopoverOnEscape\([\s\S]*?^\}/m, "Escape dismissal helper"),
      "return {initializeHeaderPopovers, dismissHeaderPopoversOutside, dismissHeaderPopoverOnEscape};",
    ].join("\n"),
  )(document);

  helpers.initializeHeaderPopovers();
  helpers.initializeHeaderPopovers();
  assert.equal(treasury.listenerCount("toggle"), 1, "reinitialization stays idempotent");
  treasury.open = true;
  offline.open = true;
  treasury.fire("toggle");
  assert.equal(offline.open, false, "opening Treasury closes Offline help");

  treasury.open = true;
  helpers.dismissHeaderPopoversOutside({ target: "outside" });
  assert.equal(treasury.open, false, "outside click closes an open popover");

  offline.open = true;
  let prevented = false;
  helpers.dismissHeaderPopoverOnEscape({ key: "Escape", preventDefault() { prevented = true; } });
  assert.equal(offline.open, false);
  assert.equal(offline.summary.focused, 1, "Escape returns focus to the opener");
  assert.equal(prevented, true);
  assert.match(main, /document\.addEventListener\("click", dismissHeaderPopoversOutside\)/);
  assert.match(main, /document\.addEventListener\("keydown", dismissHeaderPopoverOnEscape\)/);
  assert.match(mainCss, /\.offline-help\[open\] \.offline-help__popover \{ display: block; \}/);
  assert.doesNotMatch(mainCss, /\.offline-action:hover \.offline-help__popover|\.offline-action:focus-within \.offline-help__popover/);
});

test("desktop art keeps the guild mark and uses the active navigation sprite when a route has no custom art", () => {
  assert.match(desktopArt, /let currentNavigationArtKey = null;/);
  assert.match(desktopArt, /function sidebarRouteMatches\(route, path\)/);
  assert.match(desktopArt, /if \(key && manifest\.sprites\?\.\[key\]\) currentNavigationArtKey = key;/);
  assert.match(desktopArt, /const titleSprite = currentArt\?\.sprite \|\| currentNavigationArtKey;/);
  assert.match(desktopArt, /const existingArt = icon\.querySelector\("\.desktop-nav-art"\)/);
  assert.ok(desktopArt.indexOf('queryRoot.querySelector(".brand-sigil, .seal")') < desktopArt.indexOf("if (!currentArt) return;"));
  assert.match(desktopArt, /queryRoot\.querySelector\("\.crest-placeholder"\)/);
});

test("shell and page links keep the F01-F07 content and actions consistent", () => {
  assert.match(baseTemplate, /desktop-theme\.css[^\"]*\?v=20261126-2/);
  assert.match(main, /GIMApplyDesktopArt\?\.\(document\)/);
  assert.match(main, /refreshResourceTotals\(\);/);
  assert.match(main, /initializeHeaderPopovers\(currentTopbar\)/);
  assert.match(mainCss, /\.game-shell \[id\] \{ scroll-margin-top: calc\(var\(--game-sticky-topbar-height, 0px\) \+ 12px\); \}/);
  assert.match(desktopEvolution, /scroll-margin-top: calc\(var\(--game-sticky-topbar-height, 0px\) \+ 12px\)/);
  assert.match(desktopTheme, /grid-template-columns: auto minmax\(150px, \.8fr\) minmax\(250px, 1fr\) auto/);
  assert.match(desktopTheme, /\.game-topbar > \.topbar-stats > span:nth-child\(1\)[\s\S]*?display: block/);
  assert.match(desktopTheme, /\.game-topbar > \.offline-action \{ grid-column: 1 \/ -1; grid-row: 3;/);

  assert.match(campaignsTemplate, /<h1 id="campaign-page-title">Campanhas<\/h1>/);
  assert.match(campaignsTemplate, /class="campaign-maintenance-actions"/);
  assert.match(campaignsTemplate, /class="campaign-destructive-actions"/);
  assert.match(campaignsTemplate, /Manutenção da campanha/);
  assert.match(campaignsTemplate, /Ações destrutivas/);
  assert.match(campaignsTemplate, /Arquivo de campanha preservado/);
  assert.doesNotMatch(campaignsTemplate, /Campanhas e trabalhadores|SUAS CAMPANHAS|COLETA<\/span>/);

  assert.doesNotMatch(dashboardTemplate, /desktop-hero-actions|Atividades em andamento e recompensas prontas|href="\/missions">Ver operações/);
  assert.match(missionsTemplate, /href="\/regional">Ver ofertas regionais/);
  assert.doesNotMatch(missionsTemplate, /href="\/regional\/events">Ver ofertas regionais/);
  assert.doesNotMatch(missionsTemplate, /href="#available-missions-title">Ver missões/);
});

test("offline return emphasizes the total and displays one cap message", async () => {
  const template = await readFile(new URL("app/templates/base.html", root), "utf8");
  const styles = await readFile(new URL("app/static/css/desktop-theme.css", root), "utf8");
  assert.match(template, /class="offline-gold-total"><dt>Ouro total<\/dt><dd>\+\{\{ offline\.gold \}\}/);
  assert.match(template, /offline\.gold_sources\.warehouse %\} · Bônus do Armazém/);
  assert.match(template, /offline\.cap_reached %\}.*offline-cap-warning/s);
  assert.match(template, /offline\.warning and not offline\.cap_reached/);
  assert.match(styles, /\.offline-gold-total \{ grid-column: 1 \/ -1;/);
});
