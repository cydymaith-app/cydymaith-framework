// Tests for assets/order.js: putting tiles and sections in order from simple to advanced, before the page is shown.
// The moves are pure; the page part runs against a small fake page, with the same few calls the real one uses.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const FILE = path.join(__dirname, "..", "phrasebook", "assets", "order.js");
const SOURCE = fs.readFileSync(FILE, "utf8");
const { clean, merge, way, levelOf, leveled } = require(FILE);
const arrange = require(path.join(__dirname, "..", "phrasebook", "assets", "arrange.js"));

// ---- a fake page

class Mark {
  constructor() { this.parentNode = null; }
}

class El {
  constructor(tag, attrs = {}) {
    this.tagName = tag.toUpperCase();
    this.attrs = { ...attrs };
    this.nodes = [];
    this.parentNode = null;
  }
  get children() { return this.nodes.filter((n) => n instanceof El); }
  getAttribute(name) { return name in this.attrs ? this.attrs[name] : null; }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  appendChild(child) {
    if (child.parentNode) child.parentNode.removeChild(child);
    child.parentNode = this;
    this.nodes.push(child);
    return child;
  }
  insertBefore(child, ref) {
    if (child.parentNode) child.parentNode.removeChild(child);
    child.parentNode = this;
    this.nodes.splice(this.nodes.indexOf(ref), 0, child);
    return child;
  }
  removeChild(child) {
    this.nodes.splice(this.nodes.indexOf(child), 1);
    child.parentNode = null;
    return child;
  }
}

const el = (tag, attrs, ...kids) => {
  const node = new El(tag, attrs);
  kids.forEach((k) => node.appendChild(k));
  return node;
};
const tile = (id, level) => el("li", { "data-tile": id, ...(level ? { "data-level": String(level) } : {}) });
const list = (screen, ...tiles) => el("ul", { "data-tiles": "", "data-order": screen }, ...tiles);
const section = (id, level) => el("section", { id, ...(level ? { "data-level": String(level) } : {}) });
const jump = (...ids) => el("ul", { class: "jump" }, ...ids.map((id) => el("li", {}, el("a", { href: `#${id}` }))));
const ids = (parent, name = "data-tile") => parent.children.map((c) => c.getAttribute(name));
const jumpIds = (ul) => ul.children.map((li) => li.children[0].getAttribute("href").slice(1));

// Run order.js on a page with this storage. Returns a way to send it the page's two events.
function load({ prefs, order, site = null, throwing = false, raw = {} } = {}) {
  const listeners = {};
  const store = { ...raw };
  const key = `${site || "phrasebook"}:`;
  if (prefs !== undefined) store[key + "prefs"] = typeof prefs === "string" ? prefs : JSON.stringify(prefs);
  if (order !== undefined) store[key + "order"] = typeof order === "string" ? order : JSON.stringify(order);
  const read = [];
  const context = {
    document: {
      documentElement: { getAttribute: (n) => (n === "data-storage" ? site : null) },
      addEventListener: (type, fn) => { listeners[type] = fn; },
      createComment: () => new Mark(),
    },
    window: {
      localStorage: {
        getItem: (k) => {
          read.push(k);
          if (throwing) throw new Error("blocked");
          return k in store ? store[k] : null;
        },
      },
    },
  };
  vm.runInNewContext(SOURCE, context);
  return {
    read,
    ask: (container) => listeners["phrasebook:order"]({ page: container }),
    peek: (container) => listeners["phrasebook:peek"]({ detail: { page: container } }),
    listeners,
  };
}

// ---- the moves

test("a level is 1 to 3, and anything else counts as the middle one", () => {
  assert.deepEqual(["1", "2", "3"].map(levelOf), [1, 2, 3]);
  for (const bad of [null, undefined, "", "0", "4", "-1", "x", "NaN"]) assert.equal(levelOf(bad), 2, String(bad));
});

test("simplest first puts the lower levels first and most advanced first the higher, and the same level keeps its written place", () => {
  const items = [["a", 3], ["b", 1], ["c", 2], ["d", 1], ["e", 3], ["f", 2]].map(([id, level]) => ({ id, level }));
  assert.deepEqual(leveled(items, "simple"), ["b", "d", "c", "f", "a", "e"]);
  assert.deepEqual(leveled(items, "advanced"), ["a", "e", "c", "f", "b", "d"]);
  assert.deepEqual(leveled([], "simple"), []);
  assert.deepEqual(leveled(items.map((i) => ({ ...i, level: 2 })), "advanced"), ["a", "b", "c", "d", "e", "f"], "all equal: as written");
});

test("only the two directions mean anything", () => {
  assert.equal(way({ order: "simple" }), "simple");
  assert.equal(way({ order: "advanced" }), "advanced");
  for (const bad of [{ order: "written" }, { order: "SIMPLE" }, { order: 1 }, { order: ["simple"] }, {}, null, undefined, "simple", 7]) {
    assert.equal(way(bad), null, JSON.stringify(bad));
  }
});

test("a saved tile order is read the way arrange.js reads it, whatever is in storage", () => {
  const cases = [
    null, undefined, "x", 7, [], {}, { v: 2, screens: { index: ["a"] } }, { v: 1 }, { v: 1, screens: [] },
    { v: 1, screens: { index: ["a", "b", "a", 3, null, "Bad Id", "../x", "c"] } },
    { v: 1, screens: { "group-x": ["z"], index: [], other: ["a"], "group-": ["a"], "group-Y": ["a"] } },
    { v: 1, screens: { index: "abc", "group-ok": ["a"] } },
    { v: 1, screens: { index: Array.from({ length: 300 }, (_, i) => "t" + i) } },
  ];
  for (const raw of cases) assert.deepEqual(clean(raw), arrange.clean(raw), JSON.stringify(raw));
});

test("a saved order is merged into the written one the way arrange.js merges it", () => {
  const written = ["a", "b", "c", "d"];
  for (const saved of [["c", "a"], ["d", "c", "b", "a"], ["zzz", "b"], [], ["a", "b", "c", "d"]]) {
    assert.deepEqual(merge(written, saved), arrange.merge(written, saved), JSON.stringify(saved));
  }
  assert.deepEqual(merge(written, ["c", "a"]), ["c", "a", "b", "d"]);
});

// ---- tiles

test("with no choice the tiles stay as written, and the two orders arrange.js needs are left on the list", () => {
  const ul = list("index", tile("a", 3), tile("b", 1), tile("c", 2));
  const page = load();
  page.ask(el("div", {}, ul));
  assert.deepEqual(ids(ul), ["a", "b", "c"]);
  assert.equal(ul.getAttribute("data-written"), "a b c");
  assert.equal(ul.getAttribute("data-default"), "a b c");
});

test("simplest first and most advanced first put the tiles in order, and the written order is kept beside them", () => {
  for (const [order, wanted] of [["simple", ["b", "d", "c", "a"]], ["advanced", ["a", "c", "b", "d"]]]) {
    const ul = list("group-weather", tile("a", 3), tile("b", 1), tile("c", 2), tile("d", 1));
    load({ prefs: { order } }).ask(el("div", {}, ul));
    assert.deepEqual(ids(ul), wanted, order);
    assert.equal(ul.getAttribute("data-written"), "a b c d", order);
    assert.equal(ul.getAttribute("data-default"), wanted.join(" "), order);
  }
});

test("a screen the person arranged keeps their order, and the setting orders only the screens they have not", () => {
  const order = { v: 1, screens: { index: ["c", "a"] } };
  const mine = list("index", tile("a", 1), tile("b", 3), tile("c", 2), tile("d", 1));
  const other = list("group-x", tile("a", 3), tile("b", 1), tile("c", 2));
  load({ prefs: { order: "advanced" }, order }).ask(el("div", {}, mine, other));
  assert.deepEqual(ids(mine), ["c", "a", "b", "d"], "their order, then the tiles they did not place, as written");
  assert.deepEqual(ids(other), ["a", "c", "b"], "no saved order here, so most advanced first");
  assert.equal(mine.getAttribute("data-default"), "b c a d", "Reset goes to the setting, not to their order");
  assert.equal(mine.getAttribute("data-written"), "a b c d");
});

test("names in a saved order that the screen no longer has are dropped", () => {
  const ul = list("index", tile("a", 1), tile("b", 1));
  load({ order: { v: 1, screens: { index: ["gone", "b", "also-gone"] } } }).ask(el("div", {}, ul));
  assert.deepEqual(ids(ul), ["b", "a"]);
});

test("a tile with no level counts as the middle one", () => {
  const ul = list("index", tile("a", 3), tile("b"), tile("c", 1));
  load({ prefs: { order: "simple" } }).ask(el("div", {}, ul));
  assert.deepEqual(ids(ul), ["c", "b", "a"]);
});

test("asking again changes nothing and keeps the written order it first saw", () => {
  const ul = list("index", tile("a", 3), tile("b", 1), tile("c", 2));
  const page = load({ prefs: { order: "simple" } });
  const container = el("div", {}, ul);
  page.ask(container);
  const once = ids(ul);
  page.ask(container);
  assert.deepEqual(ids(ul), once);
  assert.equal(ul.getAttribute("data-written"), "a b c");
  const asFirst = load({ prefs: { order: "advanced" } });
  asFirst.ask(container);
  assert.deepEqual(ids(ul), ["a", "c", "b"], "a changed choice is worked from the written order, not from the last result");
});

test("storage that is blocked, empty or nonsense leaves everything as written", () => {
  for (const options of [{ throwing: true }, {}, { prefs: "not json", order: "{{" }, { prefs: "null", order: "7" }, { prefs: [], order: [] }]) {
    const ul = list("index", tile("a", 3), tile("b", 1), tile("c", 2));
    load(options).ask(el("div", {}, ul));
    assert.deepEqual(ids(ul), ["a", "b", "c"], JSON.stringify(options));
  }
});

test("a page that names its storage is read from that, and a name that is not a safe name falls back", () => {
  const ul = list("index", tile("a", 3), tile("b", 1));
  const page = load({ site: "demo-book", prefs: { order: "simple" } });
  page.ask(el("div", {}, ul));
  assert.deepEqual(ids(ul), ["b", "a"]);
  assert.deepEqual(page.read, ["demo-book:prefs", "demo-book:order"]);
  const bad = load({ site: "A b/c" });
  bad.ask(el("div", {}, list("index", tile("a", 1))));
  assert.deepEqual(bad.read, ["phrasebook:prefs", "phrasebook:order"]);
});

// ---- sections

test("the sections of a topic and its On this page list go into the same order", () => {
  const ul = jump("s1", "s2", "s3", "s4");
  const page = el("div", {}, el("header"), ul, section("s1", 3), section("s2", 1), section("s3", 2), section("s4", 1), el("nav", { class: "pager" }));
  load({ prefs: { order: "simple" } }).ask(page);
  assert.deepEqual(ids(page, "id").filter(Boolean), ["s2", "s4", "s3", "s1"]);
  assert.deepEqual(jumpIds(ul), ["s2", "s4", "s3", "s1"]);
  assert.equal(page.children[page.children.length - 1].tagName, "NAV", "what follows the sections stays after them");
  assert.ok(page.nodes.every((n) => n instanceof El), "no marks left behind");
  assert.ok(ul.nodes.every((n) => n instanceof El), "none in the list either");
});

test("most advanced first reverses the levels and keeps the written order among equals", () => {
  const ul = jump("s1", "s2", "s3", "s4");
  const page = el("div", {}, ul, section("s1", 1), section("s2", 3), section("s3", 1), section("s4", 3));
  load({ prefs: { order: "advanced" } }).ask(page);
  assert.deepEqual(ids(page, "id").filter(Boolean), ["s2", "s4", "s1", "s3"]);
  assert.deepEqual(jumpIds(ul), ["s2", "s4", "s1", "s3"]);
});

test("a section with no level, such as a figure, stays where it is while the others move around it", () => {
  const figure = el("section", { id: "fig", class: "figure" });
  const page = el("div", {}, figure, jump("s1", "s2", "s3"), section("s1", 3), section("s2", 1), section("s3", 2));
  load({ prefs: { order: "simple" } }).ask(page);
  assert.equal(page.children[0], figure);
  assert.deepEqual(page.children.slice(2).map((c) => c.getAttribute("id")), ["s2", "s3", "s1"]);
});

test("sections stay as written with no choice, with one section, and when the list names something else", () => {
  const asWritten = el("div", {}, jump("s1", "s2"), section("s1", 3), section("s2", 1));
  load().ask(asWritten);
  assert.deepEqual(ids(asWritten, "id").filter(Boolean), ["s1", "s2"]);
  assert.deepEqual(jumpIds(asWritten.children[0]), ["s1", "s2"]);
  const single = el("div", {}, jump("s1"), section("s1", 3));
  load({ prefs: { order: "simple" } }).ask(single);
  assert.deepEqual(ids(single, "id").filter(Boolean), ["s1"]);
  const odd = el("div", {}, el("ul", { class: "jump" }, el("li", {}, el("a", { href: "#elsewhere" })), el("li", {}, el("a", { href: "#s2" }))),
    section("s1", 3), section("s2", 1));
  load({ prefs: { order: "simple" } }).ask(odd);
  assert.deepEqual(ids(odd, "id").filter(Boolean), ["s2", "s1"], "the sections still move");
  assert.deepEqual(jumpIds(odd.children[0]), ["elsewhere", "s2"], "a list that is not about these sections is left alone");
});

test("sections with no list above them are put in order all the same", () => {
  const page = el("div", {}, section("s1", 3), section("s2", 1));
  load({ prefs: { order: "simple" } }).ask(page);
  assert.deepEqual(ids(page, "id"), ["s2", "s1"]);
});

// ---- the events

test("it answers the page and the copy nav.js slides in, and ignores a call with no page", () => {
  const page = load({ prefs: { order: "simple" } });
  assert.deepEqual(Object.keys(page.listeners).sort(), ["phrasebook:order", "phrasebook:peek"]);
  const inline = list("index", tile("a", 3), tile("b", 1));
  page.ask(el("div", {}, inline));
  assert.deepEqual(ids(inline), ["b", "a"]);
  const copy = list("index", tile("a", 3), tile("b", 1));
  page.peek(el("main", {}, copy));
  assert.deepEqual(ids(copy), ["b", "a"]);
  assert.doesNotThrow(() => page.ask(null));
  assert.doesNotThrow(() => page.listeners["phrasebook:peek"]({}));
});

test("with no page in sight it only exports its moves", () => {
  assert.deepEqual(Object.keys(require(FILE)).sort(), ["clean", "leveled", "levelOf", "merge", "way"].sort());
});

test("the script makes no request, sets no cookies and writes nothing", () => {
  for (const banned of ["fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket", "document.cookie", "setItem", "removeItem", "sessionStorage",
                        "http:", "https:", "import(", "eval(", "document.write", "new Function", "innerHTML"]) {
    assert.ok(!SOURCE.includes(banned), `order.js must not use ${banned}`);
  }
});

test("it moves nodes in the page and never uses CSS order, so the reading, focus and key orders agree with what is seen", () => {
  assert.ok(!/style\.order|\.order\s*=/.test(SOURCE.replace(/prefs\.order|raw\.order/g, "")), "no CSS order");
  assert.ok(SOURCE.includes("appendChild") && SOURCE.includes("insertBefore"));
});
