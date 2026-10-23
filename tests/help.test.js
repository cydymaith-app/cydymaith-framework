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
const { apply, toggle, anchor, fit, context, message, mailto, copied, sections, MAX_CONTEXT } = require(FILE);

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

test("nothing is stored, and the only request is for a page of the help book", () => {
  assert.doesNotMatch(SOURCE, /localStorage|sessionStorage|XMLHttpRequest|sendBeacon|document\.cookie|indexedDB/);
  assert.equal((SOURCE.match(/fetch\(/g) || []).length, 1, "one request");
  assert.match(SOURCE, /PAGE\.test\(sheet\.page\)/, "and only after the page name is checked");
  assert.doesNotMatch(SOURCE, /location\.(href|assign|replace)\s*=|location\.(assign|replace)\(/, "the app never opens the mail link itself");
});

test("an anchor is a chapter and a feature in plain lower case, or nothing", () => {
  assert.deepEqual(anchor("your-settings#view-mode"), { chapter: "your-settings", feature: "view-mode", page: "help-your-settings.html" });
  for (const bad of ["", null, "a", "a#", "#b", "a#b#c", "A#b", "a#B", "a b#c", "../x#y", "a#b.html", "1a#b"]) assert.equal(anchor(bad), null, String(bad));
});

test("fit keeps whole lines, most important first, within the limit", () => {
  assert.equal(fit(["aaa", "bbb", "ccc"], 100), "aaa\nbbb\nccc");
  assert.equal(fit(["aaa", "bbb", "ccc"], 7), "aaa\nbbb");
  assert.equal(fit(["aaa", "bbb", "ccc"], 6), "aaa");
  assert.equal(fit(["aaaaaaaaaa", "b"], 5), "aaaa…", "a first line that cannot fit is cut and marked");
  assert.equal(fit([], 10), "");
  assert.ok(fit(["x".repeat(500)], 256).length <= 256);
});

test("the context the app adds is never more than 256 characters, whatever the page", () => {
  assert.equal(MAX_CONTEXT, 256);
  const small = context({ page: "rain.html", help: "reading-a-topic#levels", built: "2026-10-23", pair: "cy>en", dir: "ltr" });
  assert.equal(small, "Page: rain.html\nHelp: reading-a-topic#levels\nBuilt: 2026-10-23\nLanguages: cy>en");
  const huge = context({ page: "p".repeat(400), help: "h".repeat(400), built: "b".repeat(400), pair: "l".repeat(400), dir: "rtl" });
  assert.ok(huge.length <= 256, String(huge.length));
  const long = context({ page: "x".repeat(100), help: "y".repeat(100), built: "2026-10-23", pair: "cy>en", dir: "ltr" }, 256);
  assert.ok(long.length <= 256);
  assert.match(small, /^Page: /, "the page comes first, so it is the last to go");
});

test("a right-to-left language is named in the context", () => {
  assert.match(context({ page: "a.html", pair: "ar>en", dir: "rtl" }), /Languages: ar>en rtl/);
  assert.doesNotMatch(context({ page: "a.html", pair: "cy>en", dir: "ltr" }), /ltr/);
});

test("the message is the person's words, then the lines the app adds", () => {
  assert.equal(message("It is wrong.", "Page: a.html"), "It is wrong.\n\nPage: a.html");
  assert.equal(message("   ", "Page: a.html"), "Page: a.html");
  assert.equal(message(undefined, "Page: a.html"), "Page: a.html");
});

test("the mail link encodes the subject and the body", () => {
  const link = mailto("a@example.org", "Site: problem", "Line one\nHelp: x#y & z");
  assert.equal(link, "mailto:a@example.org?subject=Site%3A%20problem&body=Line%20one%0AHelp%3A%20x%23y%20%26%20z");
  assert.equal(copied("a@example.org", "Subject", "Body"), "To: a@example.org\nSubject: Subject\n\nBody");
});

test("sections picks the text of one feature in each language the chapter has", () => {
  const article = (lang) => ({ getAttribute: (n) => (n === "lang" ? lang : null) });
  const node = (lang) => ({ closest: () => article(lang), getAttribute: () => null });
  const doc = { querySelectorAll: (sel) => (sel === '[data-feature="tiles"]' ? [node("cy"), node("en")] : []) };
  assert.deepEqual(sections(doc, "tiles").map((s) => s.lang), ["cy", "en"]);
  assert.deepEqual(sections(doc, "back"), []);
});
