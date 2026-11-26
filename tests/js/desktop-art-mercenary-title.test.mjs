import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../../app/static/js/desktop-art.js", import.meta.url), "utf8");

function extract(expression, label) {
  const match = source.match(expression);
  assert.ok(match, `${label} is present`);
  return match[0];
}

const normalizeKey = extract(/^  function normalizeKey\([\s\S]*?^  \}/m, "class normalizer");
const classAliases = extract(/^  const classAliases = \{[\s\S]*?^  \};/m, "class aliases");
const classSpriteKey = extract(/^  function classSpriteKey\([\s\S]*?^  \}/m, "canonical class resolver");
const applyTitleArt = extract(/^  function applyTitleArt\([\s\S]*?^  \}/m, "detail title art guard");

function makeHarness() {
  const helpers = new Function(
    "makeImage",
    [normalizeKey, classAliases, classSpriteKey, applyTitleArt, "return {classSpriteKey, applyTitleArt};"].join("\n"),
  )((src, className) => ({ src, className, remove() { this.removed = true; } }));

  const makePage = ({ classCode = null, titleArt = [] } = {}) => {
    const detailMark = classCode ? { dataset: { desktopClass: classCode } } : null;
    const title = {
      images: titleArt,
      querySelector(selector) { return selector === ".desktop-title-art" ? this.images.find((image) => !image.removed) || null : null; },
      prepend(image) { this.images.unshift(image); },
    };
    const root = {
      querySelector(selector) { return selector === ".desktop-detail-class-mark" ? detailMark : null; },
      querySelectorAll(selector) { return selector === ".desktop-title-art" ? title.images.filter((image) => !image.removed) : []; },
    };
    return { root, title, detailMark };
  };

  return { helpers, makePage };
}

test("mercenary detail keeps its canonical Mage/Guerreiro mark through direct, partial, and repeated initialization", () => {
  const { helpers, makePage } = makeHarness();
  const sprites = { "class-mage": {}, "class-warrior": {} };
  const classMap = { classes: { mage: "class-mage", warrior: "class-warrior" } };
  assert.equal(helpers.classSpriteKey("Mago", classMap, sprites), "class-mage");
  assert.equal(helpers.classSpriteKey("Guerreiro", classMap, sprites), "class-warrior");

  const directMage = makePage({ classCode: "Mago" });
  helpers.applyTitleArt(directMage.root, directMage.title, "class-warrior", (key) => `/sprites/${key}`);
  assert.equal(directMage.detailMark.dataset.desktopClass, "Mago");
  assert.equal(directMage.title.images.length, 0, "the generic Warrior navigation sprite is not added to a Mage detail");

  const partialWarrior = makePage({
    classCode: "Guerreiro",
    titleArt: [{ className: "desktop-title-art", src: "/sprites/class-warrior", remove() { this.removed = true; } }],
  });
  helpers.applyTitleArt(partialWarrior.root, partialWarrior.title, "class-warrior", (key) => `/sprites/${key}`);
  helpers.applyTitleArt(partialWarrior.root, partialWarrior.title, "class-warrior", (key) => `/sprites/${key}`);
  assert.equal(partialWarrior.title.images.filter((image) => !image.removed).length, 0, "partial replacement removes stale generic art and repeated initialization stays clean");
});

test("mercenary list keeps its generic route sprite exactly once", () => {
  const { helpers, makePage } = makeHarness();
  const listing = makePage();
  helpers.applyTitleArt(listing.root, listing.title, "class-warrior", (key) => `/sprites/${key}`);
  helpers.applyTitleArt(listing.root, listing.title, "class-warrior", (key) => `/sprites/${key}`);
  assert.equal(listing.title.images.filter((image) => !image.removed).length, 1);
  assert.equal(listing.title.images[0].src, "/sprites/class-warrior");
});
