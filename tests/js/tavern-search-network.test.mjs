import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const main = await readFile(new URL("../../app/static/js/main.js", import.meta.url), "utf8");
const fetchHelper = main.match(/async function fetchTavernStateAfterUncertainAction\(previousUrl\) \{[\s\S]*?\n\}/)?.[0];
const lockHelper = main.match(/function lockTavernActionsUntilReload\(form, submitter, previousUrl\) \{[\s\S]*?\n\}/)?.[0];
assert.ok(fetchHelper, "uncertain action GET recovery helper is present");
assert.ok(lockHelper, "uncertain action mutation lock helper is present");

function loadHelpers({ fetch, document, HTMLElement }) {
  return new Function(
    "fetch",
    "document",
    "HTMLElement",
    `${fetchHelper}\n${lockHelper}\nreturn { fetchTavernStateAfterUncertainAction, lockTavernActionsUntilReload };`,
  )(fetch, document, HTMLElement);
}

test("uncertain search uses only a no-store GET when synchronization fails", async () => {
  const requests = [];
  const { fetchTavernStateAfterUncertainAction } = loadHelpers({
    fetch: async (url, options) => {
      requests.push({ url, options });
      return { ok: false, status: 503 };
    },
    document: {},
    HTMLElement: class {},
  });

  const result = await fetchTavernStateAfterUncertainAction("http://localhost/tavern");

  assert.equal(result, null);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].options.method, "GET");
  assert.equal(requests[0].options.credentials, "same-origin");
  assert.equal(requests[0].options.cache, "no-store");
});

test("successful synchronization returns the fresh page without repeating the POST", async () => {
  const requests = [];
  const { fetchTavernStateAfterUncertainAction } = loadHelpers({
    fetch: async (url, options) => {
      requests.push({ url, options });
      return { ok: true, url, text: async () => "fresh tavern state" };
    },
    document: {},
    HTMLElement: class {},
  });

  const result = await fetchTavernStateAfterUncertainAction("http://localhost/tavern");

  assert.deepEqual(result, { html: "fresh tavern state", url: "http://localhost/tavern" });
  assert.equal(requests.length, 1);
  assert.equal(requests[0].options.method, "GET");
});

test("failed synchronization keeps all candidate and price actions disabled and offers GET reload", () => {
  class FakeElement {}
  const makeButton = (text) => Object.assign(new FakeElement(), {
    disabled: false,
    textContent: text,
    classList: { removed: [], remove(value) { this.removed.push(value); } },
  });
  const searchButton = makeButton("Buscando…");
  const hireButton = makeButton("Contratar Aprendiz");
  const bulkButton = makeButton("Contratar 10");
  const status = Object.assign(new FakeElement(), {
    attributes: {},
    children: [],
    setAttribute(name, value) { this.attributes[name] = value; },
    replaceChildren(...children) {
      this.children = children;
      this.textContent = children.map((child) => child.textContent || "").join("");
    },
  });
  const form = Object.assign(new FakeElement(), {
    querySelector: () => status,
  });
  const document = {
    querySelectorAll(selector) {
      assert.equal(selector, "[data-tavern-candidate-price-mutation] button[type='submit']");
      return [searchButton, hireButton, bulkButton];
    },
    createElement(tagName) { return { tagName: tagName.toUpperCase() }; },
    createTextNode(textContent) { return { textContent }; },
  };
  const { lockTavernActionsUntilReload } = loadHelpers({ fetch: async () => { throw new Error("unused"); }, document, HTMLElement: FakeElement });

  lockTavernActionsUntilReload(form, searchButton, "http://localhost/tavern");

  assert.ok([searchButton, hireButton, bulkButton].every((button) => button.disabled));
  assert.equal(searchButton.textContent, "Aguardando atualização");
  assert.equal(status.attributes.role, "alert");
  assert.equal(status.attributes["aria-live"], "assertive");
  assert.match(status.textContent, /Não foi possível confirmar o resultado da busca/);
  const reloadLink = status.children[1];
  assert.equal(reloadLink.tagName, "A");
  assert.equal(reloadLink.href, "http://localhost/tavern");
  assert.equal(reloadLink.textContent, "Recarregar estado");
});
