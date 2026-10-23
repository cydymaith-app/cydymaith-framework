// Tests for assets/help.js: the help button that shows and hides the help icons. Run from the repo root:  node --test tests/
// The moves are pure; the page part runs against a small fake page with the few calls the real one uses.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const FILE = path.join(__dirname, "..", "phrasebook", "assets", "help.js");
const SOURCE = fs.readFileSync(FILE, "utf8");
const { apply, toggle } = require(FILE);

function fakeRoot() {
  const attrs = {};
  return {
    attrs,
    setAttribute: (n, v) => { attrs[n] = v; },
    removeAttribute: (n) => { delete attrs[n]; },
    hasAttribute: (n) => n in attrs,
  };
}

function fakeButton() {
  const attrs = { "aria-pressed": "false" };
  const listeners = {};
  return {
    attrs,
    hidden: true,
    setAttribute: (n, v) => { attrs[n] = v; },
    addEventListener: (type, fn) => { listeners[type] = fn; },
    click() { listeners.click(); },
  };
}

test("apply marks the page and the button, and removes both again", () => {
  const root = fakeRoot();
  const button = fakeButton();
  assert.equal(apply(root, button, true), true);
  assert.ok(root.hasAttribute("data-helping"));
  assert.equal(button.attrs["aria-pressed"], "true");
  assert.equal(apply(root, button, false), false);
  assert.ok(!root.hasAttribute("data-helping"));
  assert.equal(button.attrs["aria-pressed"], "false");
});

test("toggle flips the state each time", () => {
  const root = fakeRoot();
  const button = fakeButton();
  assert.equal(toggle(root, button), true);
  assert.equal(toggle(root, button), false);
  assert.equal(toggle(root, button), true);
  assert.equal(button.attrs["aria-pressed"], "true");
});

function runPage(button) {
  const root = fakeRoot();
  const listeners = {};
  const document = {
    documentElement: root,
    getElementById: (id) => (id === "help-toggle" ? button : null),
    addEventListener: (type, fn) => { listeners[type] = fn; },
  };
  vm.runInNewContext(SOURCE, { document });
  return { root, listeners };
}

test("on a page with the button, the script shows it and the button turns help on and off", () => {
  const button = fakeButton();
  const { root } = runPage(button);
  assert.equal(button.hidden, false);
  button.click();
  assert.ok(root.hasAttribute("data-helping"));
  button.click();
  assert.ok(!root.hasAttribute("data-helping"));
});

test("Escape turns help off, and does nothing when it is already off", () => {
  const button = fakeButton();
  const { root, listeners } = runPage(button);
  listeners.keydown({ key: "Escape" });
  assert.ok(!root.hasAttribute("data-helping"));
  button.click();
  listeners.keydown({ key: "a" });
  assert.ok(root.hasAttribute("data-helping"));
  listeners.keydown({ key: "Escape" });
  assert.ok(!root.hasAttribute("data-helping"));
  assert.equal(button.attrs["aria-pressed"], "false");
});

test("a page with no button is left alone", () => {
  const { root, listeners } = runPage(null);
  assert.deepEqual(listeners, {});
  assert.deepEqual(root.attrs, {});
});

test("nothing is stored and nothing is requested", () => {
  assert.doesNotMatch(SOURCE, /localStorage|sessionStorage|fetch\(|XMLHttpRequest|document\.cookie/);
});
