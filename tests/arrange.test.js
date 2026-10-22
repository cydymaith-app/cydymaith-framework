// Tests for phrasebook/assets/arrange.js: the saved order, the merge with the defaults, the moves and the keys. The moves need no
// page, so they run here. The page glue (drag, tap, focus, the slide, the storage on a real page) is checked in a browser.
// Run from the repo root: node --test tests/
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "..", "phrasebook", "assets", "arrange.js"), "utf8");
// Run in this realm, not a sandbox, so objects it returns compare equal to the ones written here.
const exported = { exports: {} };
vm.runInThisContext(`(function (module) {${SOURCE}\n})`)(exported);
const { clean, merge, move, targetIndex, arrowDir } = exported.exports;

test("a saved order is kept only for a screen the page has, and only ids that are safe", () => {
  const raw = {
    v: 1,
    screens: {
      index: ["g2", "g1", "g2", "Bad Id", 7, "g3"],
      "group-weather": ["rain"],
      "other-page": ["x"],
      "group-news": "not a list",
    },
  };
  assert.deepEqual(clean(raw), { v: 1, screens: { index: ["g2", "g1", "g3"], "group-weather": ["rain"] } });
});

test("anything that is not this version of the saved order is ignored", () => {
  const empty = { v: 1, screens: {} };
  assert.deepEqual(clean(null), empty);
  assert.deepEqual(clean("text"), empty);
  assert.deepEqual(clean({ v: 2, screens: { index: ["g1"] } }), empty);
  assert.deepEqual(clean({ v: 1, screens: [] }), { v: 1, screens: {} });
});

test("a saved order holds at most 200 tiles", () => {
  const ids = Array.from({ length: 250 }, (_, i) => `t${i}`);
  assert.equal(clean({ v: 1, screens: { index: ids } }).screens.index.length, 200);
});

test("merge keeps the saved order, drops names the screen no longer has, and appends new tiles in default order", () => {
  const defaults = ["a", "b", "c", "d"];
  assert.deepEqual(merge(defaults, ["c", "a", "gone"]), ["c", "a", "b", "d"]);
  assert.deepEqual(merge(defaults, []), ["a", "b", "c", "d"]);
  assert.deepEqual(merge(defaults, ["d", "c", "b", "a"]), ["d", "c", "b", "a"]);
});

test("move takes a tile from one place and puts it in another, and the rest keep their order", () => {
  assert.deepEqual(move(["a", "b", "c", "d"], 0, 2), ["b", "c", "a", "d"]);
  assert.deepEqual(move(["a", "b", "c", "d"], 3, 0), ["d", "a", "b", "c"]);
  assert.deepEqual(move(["a", "b", "c", "d"], 1, 2), ["a", "c", "b", "d"]);
});

test("move clamps the place to the ends and ignores a tile that is not there", () => {
  assert.deepEqual(move(["a", "b", "c"], 0, 9), ["b", "c", "a"]);
  assert.deepEqual(move(["a", "b", "c"], 2, -4), ["c", "a", "b"]);
  assert.deepEqual(move(["a", "b"], 5, 0), ["a", "b"]);
});

test("move does not change the list it was given", () => {
  const ids = ["a", "b", "c"];
  move(ids, 0, 2);
  assert.deepEqual(ids, ["a", "b", "c"]);
});

test("targetIndex is the tile whose centre is nearest the pointer, or -1 with no tiles", () => {
  const rects = [
    { left: 0, top: 0, width: 100, height: 100 },
    { left: 110, top: 0, width: 100, height: 100 },
    { left: 0, top: 110, width: 100, height: 100 },
  ];
  assert.equal(targetIndex({ x: 20, y: 20 }, rects), 0);
  assert.equal(targetIndex({ x: 190, y: 40 }, rects), 1);
  assert.equal(targetIndex({ x: 40, y: 190 }, rects), 2);
  assert.equal(targetIndex({ x: 0, y: 0 }, []), -1);
});

test("arrowDir: Right and Down are the next tile, Left and Up the previous, swapped in a right-to-left page", () => {
  assert.equal(arrowDir("ArrowRight", false), 1);
  assert.equal(arrowDir("ArrowDown", false), 1);
  assert.equal(arrowDir("ArrowLeft", false), -1);
  assert.equal(arrowDir("ArrowUp", false), -1);
  assert.equal(arrowDir("ArrowRight", true), -1);
  assert.equal(arrowDir("ArrowLeft", true), 1);
});

test("arrowDir: any other key is not an arrow", () => {
  assert.equal(arrowDir("Enter", false), 0);
  assert.equal(arrowDir("Backspace", false), 0);
  assert.equal(arrowDir("Escape", true), 0);
});
