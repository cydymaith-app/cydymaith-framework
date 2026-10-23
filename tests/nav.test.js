// Tests for phrasebook/assets/nav.js: keys, and the drag that takes a page away. The moves need no page, so they run here.
// The page glue (focus, the Back link, touch events, the slide) is checked in a real browser; see section 3 of the app's docs/TODO.md (the cydymaith repository).
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
const { keyMove, step, lock, offset, shouldDismiss, places, marked, anchorOf, cameFrom } = exported.exports;

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

test("the script asks only for pages of this site, sets no cookies and stores nothing", () => {
  for (const banned of ["XMLHttpRequest", "sendBeacon", "WebSocket", "document.cookie", "localStorage",
                        "sessionStorage", "http:", "https:", "import(", "eval(", "document.write", "new Function", "innerHTML"]) {
    assert.ok(!SOURCE.includes(banned), `nav.js must not use ${banned}`);
  }
  // Its one request is for the page it is about to slide in, and only after the address has been checked to be this site's.
  assert.equal(SOURCE.split("fetch(").length - 1, 1, "one request, in one place");
  assert.ok(SOURCE.includes("origin === window.location.origin"), "the address is checked to be this site's");
  assert.ok(SOURCE.indexOf("!sameSite(href)") !== -1 && SOURCE.indexOf("!sameSite(href)") < SOURCE.indexOf("fetch("),
    "the check comes before the request");
});

test("two pages moving together always sit exactly one width apart", () => {
  for (const forward of [true, false]) {
    for (const rtl of [false, true]) {
      for (const x of [0, 1, 120, 399, 400]) {
        const at = places(x, 400, forward, rtl);
        assert.equal(Math.abs(at.arriving - at.leaving), 400, `forward=${forward} rtl=${rtl} x=${x}`);
      }
    }
  }
});

test("opening a topic carries the pages toward the start, going back toward the end, and right-to-left mirrors both", () => {
  assert.deepEqual(places(100, 400, true, false), { leaving: -100, arriving: 300 });
  assert.deepEqual(places(100, 400, false, false), { leaving: 100, arriving: -300 });
  assert.deepEqual(places(100, 400, true, true), { leaving: 100, arriving: -300 });
  assert.deepEqual(places(100, 400, false, true), { leaving: -100, arriving: 300 });
});

test("the other page arrives exactly in place when the move is done, and waits a width away at the start", () => {
  for (const forward of [true, false]) {
    assert.equal(Math.abs(places(400, 400, forward, false).arriving), 0);
    assert.equal(Math.abs(places(0, 400, forward, false).arriving), 400);
    assert.equal(Math.abs(places(0, 400, forward, false).leaving), 0);
  }
});

// ---- related topics: the address a related tile opens, and where Back goes

test("the address says the way the page goes, and the topic a related tile was followed from, and the section to open at", () => {
  assert.equal(marked("where.html", "forward", null), "where.html#slide=forward");
  assert.equal(marked("where.html", "none", null), "where.html#slide=none");
  assert.equal(marked("where.html#landscape", "none", null), "where.html#slide=none;at=landscape");
  assert.equal(marked("where.html", "none", "rain.html"), "where.html#slide=none;from=rain.html");
  assert.equal(marked("where.html#landscape", "none", "rain.html"), "where.html#slide=none;from=rain.html;at=landscape");
});

test("a section that cannot travel in an address is dropped from it, not passed on", () => {
  for (const bad of ["a b", "a;b", "a=b", "a/b", "<x>", "é", "a#b"]) {
    assert.equal(marked(`where.html#${bad}`, "none", null), "where.html#slide=none", JSON.stringify(bad));
    assert.equal(anchorOf(`where.html#${bad}`), null, JSON.stringify(bad));
  }
  assert.equal(anchorOf("where.html#s1.c2"), "s1.c2", "a row of a section is an address too");
  assert.equal(anchorOf("where.html"), null);
  assert.equal(anchorOf("where.html#"), null);
});

test("Back returns to the topic a related tile was followed from only if the history entry names a page of this site", () => {
  assert.equal(cameFrom({ from: "rain.html" }), "rain.html");
  assert.equal(cameFrom({ from: "group-weather-forecast.html" }), "group-weather-forecast.html");
  for (const bad of [null, undefined, {}, { from: "" }, { from: 3 }, { from: ["rain.html"] }, { from: "../rain.html" },
                     { from: "https://example.org/x.html" }, { from: "//example.org/x.html" }, { from: "rain.html?x=1" },
                     { from: "Rain.html" }, { from: "rain" }, { from: "javascript:alert(1)" }, "rain.html", 7, true]) {
    assert.equal(cameFrom(bad), null, JSON.stringify(bad));
  }
});

test("a related tile opens with its marks even where the browser slides the pages itself, and an ordinary tile does not", () => {
  assert.ok(SOURCE.includes('link.hasAttribute("data-related") ? thisPage() : null'), "only a related tile says where it came from");
  assert.ok(SOURCE.includes('if (native && !from && anchorOf(href) === null) return href;'));
  assert.ok(SOURCE.includes('marked(href, native ? "none" : direction, from)'), "the browser's own move stands down when a mark must go in the address");
});

test("Back is pointed at the topic named by the history entry, before the Back link is used for anything", () => {
  const at = SOURCE.indexOf("var came = cameFrom(window.history.state);");
  assert.ok(at !== -1, "the entry is read");
  assert.ok(SOURCE.indexOf('backLink().setAttribute("href", came)') > at);
  assert.ok(at < SOURCE.indexOf('document.addEventListener("keydown", onKey);'), "before the keys and the click are wired");
  assert.ok(at < SOURCE.indexOf("neighbour(back.getAttribute"), "before the page above is asked for");
  assert.ok(SOURCE.includes("came !== thisPage()"), "never a Back to itself");
});

test("the copy of the page a tile opens at a section is scrolled to it, as far as the page is long enough", () => {
  assert.ok(SOURCE.includes('copy.querySelector("[data-at]")'));
  assert.ok(SOURCE.includes("copy.offsetHeight - layer.clientHeight"), "it goes no further than the real page can");
  assert.ok(SOURCE.includes('target.setAttribute("data-at", "")'), "the section is marked before the ids go from the copy");
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
