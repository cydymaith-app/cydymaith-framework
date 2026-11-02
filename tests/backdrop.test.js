// Tests for assets/backdrop.js: where the site's backdrop goes on a page, and where it comes from.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { parse, same, plan } = require(path.join(__dirname, "..", "phrasebook", "assets", "backdrop.js"));

test("a place is two numbers with one space between", () => {
  assert.deepEqual(parse("232 95"), [232, 95]);
  assert.deepEqual(parse("594.8 271.7"), [594.8, 271.7]);
  assert.deepEqual(parse("-3 0.5"), [-3, 0.5]);
});

test("anything else is not a place", () => {
  for (const bad of [null, undefined, 7, "", "232", "232  95", "232,95", "232 95 1", "a b", "232 95;x", " 232 95"]) {
    assert.equal(parse(bad), null, String(bad));
  }
});

test("two places are the same only when both are there and equal", () => {
  assert.equal(same([1, 2], [1, 2]), true);
  assert.equal(same([1, 2], [2, 1]), false);
  assert.equal(same(null, [1, 2]), false);
  assert.equal(same(null, null), false);
});

test("a page on the route goes to its own place, from where the last page left the drawing", () => {
  assert.deepEqual(plan([10, 20], null, [1, 2], [0, 0]), { from: [1, 2], to: [10, 20] });
});

test("going back to a page carries the drawing back to that page's place", () => {
  const home = [232, 95];
  const deeper = plan([500, 200], null, home, home);
  const back = plan(home, null, deeper.to, home);
  assert.deepEqual(back, { from: [500, 200], to: home });
});

test("arriving where the drawing already is does not move it", () => {
  assert.deepEqual(plan([10, 20], null, [10, 20], [0, 0]), { from: null, to: [10, 20] });
});

test("a page off the route stays where the last page left the drawing", () => {
  assert.deepEqual(plan(null, null, [300, 200], [0, 0]), { from: null, to: [300, 200] });
});

test("a page off the route returned to keeps the place in its history entry", () => {
  assert.deepEqual(plan(null, [300, 200], [600, 100], [0, 0]), { from: [600, 100], to: [300, 200] });
});

test("with nothing remembered the drawing starts at the start, and does not move", () => {
  assert.deepEqual(plan(null, null, null, [232, 95]), { from: null, to: [232, 95] });
  assert.deepEqual(plan([10, 20], null, null, [232, 95]), { from: null, to: [10, 20] });
});
