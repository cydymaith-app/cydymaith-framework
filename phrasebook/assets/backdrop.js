/* Phrasebook framework: the site's backdrop, moving along its drawing from page to page.
   Each page of the route (the home page, the groups and their topics, in reading order) has its own place on the drawing, worked
   out by the build (Site.route_places) and written on the drawing and on the page's main element as data-place="x y". Going to a
   page carries the drawing from where it was to that page's place, so going back carries it back again. A page that is not on the
   route (Settings, About, Help) keeps the drawing where the page before left it, and keeps that place in its history entry for a
   reload or a return. Where it was is kept for this tab only (sessionStorage), as one place and nothing else; it is never sent
   anywhere. When nav.js slides two pages together, the drawing moves with them; otherwise the new page moves it as it arrives.
   The page asks for this with a line right after the drawing, which runs before anything is painted. Without this script each page
   shows its own place, and a page off the route shows the first. */
(function () {
  "use strict";

  var NAME = /^[a-z0-9][a-z0-9._-]*$/;
  var PLACE = /^(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)$/;
  var MOVE_MS = 600;  // the stylesheet's own move between places (.backdrop.route.moving)

  // ---- the moves, with no page in sight so they can be tested on their own

  // A place from the page or from storage, [x, y], or null for anything else.
  function parse(text) {
    var m = typeof text === "string" ? PLACE.exec(text) : null;
    return m ? [parseFloat(m[1]), parseFloat(m[2])] : null;
  }

  function same(a, b) { return !!a && !!b && a[0] === b[0] && a[1] === b[1]; }

  // Where the drawing goes on a page (`to`), and where it comes from (`from`, or null to start there). A page on the route goes
  // to its own place; one off the route stays where its history entry says, else where the last page left it, else at the
  // drawing's start. It moves only from somewhere else.
  function plan(own, kept, last, start) {
    var to = own || kept || last || start;
    return { from: last && !same(last, to) ? last : null, to: to };
  }

  var api = { parse: parse, same: same, plan: plan };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  // ---- the page

  var site = document.documentElement.getAttribute("data-storage");
  var KEY = (site && NAME.test(site) ? site : "phrasebook") + ":place";
  var drawing = null;
  var mine = null;  // this page's place, for a return to it from the browser's cache

  // Storage can be blocked, full or empty (private windows, site data cleared). Never let that break the page.
  function read() {
    try {
      return parse(window.sessionStorage.getItem(KEY));
    } catch (err) {
      return null;
    }
  }

  function write(place) {
    try {
      window.sessionStorage.setItem(KEY, place.join(" "));
    } catch (err) { /* the next page starts at its own place */ }
  }

  function keptPlace() {
    var state = window.history.state;
    return state && typeof state === "object" ? parse(state.place) : null;
  }

  // Keep a place off the route in this page's history entry, beside what is there already (nav.js keeps `from` there).
  function keep(place) {
    try {
      var state = window.history.state;
      var next = {};
      if (state && typeof state === "object") for (var k in state) if (Object.prototype.hasOwnProperty.call(state, k)) next[k] = state[k];
      next.place = place.join(" ");
      window.history.replaceState(next, "");
    } catch (err) { /* a reload starts where the last page was */ }
  }

  function reducedMotion() {
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  function put(place) {
    drawing.style.setProperty("--x", String(place[0]));
    drawing.style.setProperty("--y", String(place[1]));
  }

  // Carry the drawing to `place` over `ms`, from wherever it is now.
  function move(place, ms) {
    if (reducedMotion()) {
      put(place);
      return;
    }
    drawing.style.transitionDuration = ms + "ms";
    drawing.classList.add("moving");
    put(place);
  }

  // Put the drawing at `from` and carry it to `to`: two frames, the first painting it where it was, the second starting it moving.
  // With no `from`, or no motion wanted, it is simply at `to`.
  function arrive(from, to) {
    drawing.classList.remove("moving");
    if (!from || reducedMotion()) {
      put(to);
      return;
    }
    put(from);
    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(function () { move(to, MOVE_MS); });
    });
  }

  // The page asks right after the drawing. As built, the drawing is at the page's own place, or at the start for a page off the
  // route, which is the only one without data-place.
  document.addEventListener("phrasebook:backdrop", function (event) {
    drawing = event.page || null;
    if (!drawing || !drawing.style || !drawing.getAttribute) return;
    var own = parse(drawing.getAttribute("data-place"));
    var start = parse(drawing.style.getPropertyValue("--x").trim() + " " + drawing.style.getPropertyValue("--y").trim());
    var way = plan(own, own ? null : keptPlace(), read(), start);
    mine = way.to;
    write(way.to);
    if (!own) keep(way.to);
    arrive(way.from, way.to);
    drawing.addEventListener("transitionend", function () { drawing.classList.remove("moving"); });
  });

  // nav.js is sliding to another page: go with it, to that page's place if it has one. Where the page is going is kept now, so it
  // arrives already there.
  document.addEventListener("phrasebook:travel", function (event) {
    var page = event.detail && event.detail.page;
    var place = page && page.getAttribute ? parse(page.getAttribute("data-place")) : null;
    if (!drawing || !place) return;
    write(place);
    move(place, event.detail.ms || MOVE_MS);
  });

  // Coming back to this page from the browser's cache: carry the drawing back from wherever the last page left it.
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted || !drawing || !mine) return;
    var last = read();
    write(mine);
    arrive(last && !same(last, mine) ? last : null, mine);
  });
})();
