// Tests for phrasebook/assets/nav.js: keys, and the drag that takes a page away. The moves need no page, so they run here.
// The page glue (focus, the Back link, touch events, the slide) is checked in a real browser; see docs/TODO.md.
// Run from the repo root: node --test tests/
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "..", "phrasebook", "assets", "nav.js"), "utf8");
// Run in this realm, not a sandbox, so objects it returns compare equal to the ones written here.
const exported = { exports: {} };
vm.runInThisContext(`(function (module) {${SOURCE}\n})`)(exported);
const { keyMove, step, lock, offset, shouldDismiss } = exported.exports;

test("keys: Right opens the focused tile and Left goes back, mirrored in right-to-left", () => {
  assert.equal(keyMove("ArrowRight", false), "open");
  assert.equal(keyMove("ArrowLeft", false), "back");
  assert.equal(keyMove("ArrowRight", true), "back");
  assert.equal(keyMove("ArrowLeft", true), "open");
});

test("keys: Backspace goes back in either direction, and Up, Down, Home and End move along the tiles", () => {
  for (const rtl of [false, true]) {
    assert.equal(keyMove("Backspace", rtl), "back");
    assert.equal(keyMove("ArrowDown", rtl), "next");
    assert.equal(keyMove("ArrowUp", rtl), "previous");
    assert.equal(keyMove("Home", rtl), "first");
    assert.equal(keyMove("End", rtl), "last");
  }
});

test("keys: anything else is left alone, including Enter, which is the link's own action", () => {
  for (const key of ["Enter", " ", "a", "Escape", "Tab", "PageDown"]) {
    assert.equal(keyMove(key, false), null, key);
  }
});

test("moving along the tiles stops at both ends", () => {
  assert.equal(step(0, 4, "next"), 1);
  assert.equal(step(3, 4, "next"), 3, "no wrap past the last");
  assert.equal(step(0, 4, "previous"), 0, "no wrap before the first");
  assert.equal(step(2, 4, "previous"), 1);
  assert.equal(step(2, 4, "first"), 0);
  assert.equal(step(1, 4, "last"), 3);
});

test("a move that is not along the tiles leaves focus where it is, and no tiles means no place", () => {
  assert.equal(step(2, 4, "open"), 2);
  assert.equal(step(2, 4, "back"), 2);
  assert.equal(step(0, 0, "next"), -1);
  assert.equal(step(0, 1, "next"), 0);
});

test("a touch is undecided until it leaves the dead zone", () => {
  assert.equal(lock(0, 0, false), null);
  assert.equal(lock(9, 0, false), null);
  assert.equal(lock(6, 6, false), null);
  assert.equal(lock(0, -9, false), null);
});

test("a wide touch with the reading direction is a drag", () => {
  assert.equal(lock(10, 0, false), "drag");
  assert.equal(lock(60, 20, false), "drag");
  assert.equal(lock(60, 40, false), "drag", "exactly one and a half times as wide as tall is enough");
  assert.equal(lock(-60, 20, true), "drag", "with the reading direction in a right-to-left page is leftwards");
});

test("a mostly vertical touch is a scroll, however it started", () => {
  assert.equal(lock(10, 30, false), "scroll");
  assert.equal(lock(40, 61, false), "scroll", "just too steep");
  assert.equal(lock(0, 80, false), "scroll");
  assert.equal(lock(0, -80, true), "scroll");
});

test("a touch against the reading direction is not a drag, so the page cannot be dragged the wrong way", () => {
  assert.equal(lock(-60, 0, false), "scroll");
  assert.equal(lock(60, 0, true), "scroll");
});

test("the page follows the finger only with the reading direction", () => {
  assert.equal(offset(80, false), 80);
  assert.equal(offset(-80, false), 0, "never negative");
  assert.equal(offset(-80, true), 80, "leftwards in a right-to-left page");
  assert.equal(offset(80, true), 0);
  assert.equal(offset(0, false), 0);
});

test("letting go far enough takes the page away", () => {
  assert.equal(shouldDismiss(140, 400, 0.1), true, "35% of 400 is 140");
  assert.equal(shouldDismiss(139, 400, 0.1), false, "a little short");
  assert.equal(shouldDismiss(400, 400, 0), true);
  assert.equal(shouldDismiss(0, 400, 0), false);
});

test("a quick flick takes the page away even when short", () => {
  assert.equal(shouldDismiss(40, 400, 0.5), true);
  assert.equal(shouldDismiss(39, 400, 2), false, "a flick must have travelled a little");
  assert.equal(shouldDismiss(80, 400, 0.49), false, "a slow short drag springs back");
});

test("the script makes no network request, sets no cookies and stores nothing", () => {
  for (const banned of ["fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket", "document.cookie", "localStorage",
                        "sessionStorage", "http:", "https:", "import(", "eval(", "document.write", "new Function", "innerHTML"]) {
    assert.ok(!SOURCE.includes(banned), `nav.js must not use ${banned}`);
  }
});

test("only dragging back is a gesture: the page never acts on a drag the other way", () => {
  assert.ok(!SOURCE.includes("swipe"), "the old yes-or-no swipe is gone");
  assert.ok(SOURCE.includes("dx * sign(rtl) > 0"), "a drag has to go with the reading direction");
});

test("the page glue guards the cases the plan names", () => {
  assert.ok(SOURCE.includes("t.clientX < EDGE"), "touches at the screen edge are ignored");
  assert.ok(SOURCE.includes("event.touches.length !== 1"), "a second finger is ignored");
  assert.ok(SOURCE.includes("reducedMotion()"), "reduced motion skips the slide");
  assert.ok(SOURCE.includes('"pageshow"'), "a page restored from the cache is put back");
});
