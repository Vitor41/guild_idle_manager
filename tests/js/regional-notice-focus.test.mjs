import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const main = await readFile(new URL("../../app/static/js/main.js", import.meta.url), "utf8");
const dialogs = await readFile(new URL("../../app/static/js/evolution-dialogs.js", import.meta.url), "utf8");
const queueSource = main.match(/const startupModalQueue = \(\(\) => \{[\s\S]*?\n\}\)\(\);/)?.[0];
const noticeStart = dialogs.indexOf("const bindRegionalNoticeFocusReturn =");
const noticeEnd = dialogs.indexOf('\ndocument.querySelectorAll(".evolution-page img")', noticeStart);
assert.ok(queueSource, "startup modal queue is present");
assert.ok(noticeStart >= 0 && noticeEnd > noticeStart, "regional notice enqueue helpers are present");

class FakeDialog {
  constructor(eventId, eventDeadline) {
    this.dataset = { eventId, eventDeadline };
    this.open = false;
    this.listeners = new Map();
  }

  addEventListener(name, callback, options = {}) {
    const listeners = this.listeners.get(name) || [];
    listeners.push({ callback, once: Boolean(options.once) });
    this.listeners.set(name, listeners);
  }

  showModal() { this.open = true; }

  close() {
    this.open = false;
    const listeners = [...(this.listeners.get("close") || [])];
    for (const listener of listeners) listener.callback({ target: this });
    this.listeners.set("close", (this.listeners.get("close") || []).filter((listener) => !listener.once));
  }
}

test("closing the second startup notice returns focus to the Vigília heading", () => {
  const rebellion = new FakeDialog("rebellion", "2030-01-01T01:00:00Z");
  const portal = new FakeDialog("portal", "2030-01-01T02:00:00Z");
  const animationFrames = [];
  const focusCalls = [];
  const heading = { focus(options) { focusCalls.push(options); } };
  const context = vm.createContext({
    HTMLDialogElement: FakeDialog,
    document: {
      querySelectorAll(selector) {
        assert.equal(selector, 'dialog[data-regional-event-notice]');
        return [rebellion, portal];
      },
      getElementById(id) { return id === "events-title" ? heading : null; },
    },
    window: {
      requestAnimationFrame(callback) { animationFrames.push(callback); },
    },
  });

  vm.runInContext(
    `${queueSource}\nwindow.GIMStartupModalQueue = startupModalQueue;\n${dialogs.slice(noticeStart, noticeEnd)}`,
    context,
    { filename: "regional-notice-focus.js" },
  );

  assert.equal(rebellion.open, true);
  assert.equal(portal.open, false);
  assert.equal(rebellion.dataset.focusReturnBound, "true");
  assert.equal(portal.dataset.focusReturnBound, "true");

  rebellion.close();
  for (const callback of animationFrames.splice(0)) callback();
  assert.equal(portal.open, true);
  assert.equal(focusCalls.length, 0, "focus stays in the queue while the portal is open");

  portal.close();
  for (const callback of animationFrames.splice(0)) callback();
  assert.equal(focusCalls.length, 1);
  assert.equal(focusCalls[0].preventScroll, true);
});
