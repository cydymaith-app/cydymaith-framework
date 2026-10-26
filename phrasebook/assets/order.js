/* Phrasebook framework: puts tiles and sections in order before they are shown.
   A list of tiles (the home page, a group page) and the sections of a topic (or the topics of a one-page group) can be put in order from the simplest to the most
   advanced, or the other way round, by the level each one carries (data-level, 1 to 3, worked out by the build from what it holds).
   The choice is a preference (Settings: Default, Simplest first, Most advanced first). Default leaves everything as written.
   A screen whose tiles the person has arranged themselves (arrange.js) keeps their order and ignores the setting.
   The page asks for this with a line right after each list and after a topic's sections, which runs before anything is painted, so
   nothing is ever seen moving; nav.js asks again for the copy of a page it slides in. Both are events on the document. The same
   level keeps the written order. The order is read from this device's own storage and nothing is sent anywhere. Without this script
   everything stays as written. */
(function () {
  "use strict";

  var ID = /^[a-z0-9][a-z0-9-]{0,63}$/;
  var SCREEN = /^(index|group-[a-z0-9-]+)$/;
  var NAME = /^[a-z0-9][a-z0-9._-]*$/;
  var MAX_TILES = 200;
  var VERSION = 1;  // of the saved tile order, which arrange.js writes

  // ---- the moves, with no page in sight so they can be tested on their own

  // The saved tile orders this script understands, as arrange.js writes them. Anything else in storage is ignored.
  function clean(raw) {
    var out = { v: VERSION, screens: {} };
    if (!raw || typeof raw !== "object" || raw.v !== VERSION || !raw.screens || typeof raw.screens !== "object") return out;
    Object.keys(raw.screens).forEach(function (screen) {
      var saved = raw.screens[screen];
      if (!SCREEN.test(screen) || !Array.isArray(saved)) return;
      var ids = [];
      saved.forEach(function (id) {
        if (typeof id === "string" && ID.test(id) && ids.indexOf(id) === -1 && ids.length < MAX_TILES) ids.push(id);
      });
      if (ids.length) out.screens[screen] = ids;
    });
    return out;
  }

  // The saved order, then any tile it does not name (one added in a later release) in its written place. A name the screen no
  // longer has is dropped.
  function merge(written, saved) {
    var kept = saved.filter(function (id) { return written.indexOf(id) !== -1; });
    return kept.concat(written.filter(function (id) { return kept.indexOf(id) === -1; }));
  }

  // Which way the person asked for: "simple" (simplest first), "advanced" (most advanced first), or null for as written.
  function way(prefs) {
    var order = prefs && typeof prefs === "object" ? prefs.order : null;
    return order === "simple" || order === "advanced" ? order : null;
  }

  // A level from the page: 1 to 3, or 2 (the middle, which moves nothing much) for anything else.
  function levelOf(value) {
    var n = parseInt(value, 10);
    return n >= 1 && n <= 3 ? n : 2;
  }

  // Put `items` ({id, level}) in order for `direction`, and return their ids. Stable: the same level keeps its written order.
  function leveled(items, direction) {
    var sign = direction === "advanced" ? -1 : 1;
    return items
      .map(function (item, index) { return { id: item.id, level: item.level, index: index }; })
      .sort(function (a, b) { return sign * (a.level - b.level) || a.index - b.index; })
      .map(function (item) { return item.id; });
  }

  var api = { clean: clean, merge: merge, way: way, levelOf: levelOf, leveled: leveled };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  // ---- the page

  function attr(el, name) { return typeof el.getAttribute === "function" ? el.getAttribute(name) : null; }

  function kids(el) { return Array.prototype.slice.call(el.children || []); }

  function walk(el, visit) {
    kids(el).forEach(function (child) {
      visit(child);
      walk(child, visit);
    });
  }

  // Storage can be blocked, full or empty (private windows, site data cleared). Never let that break the page.
  function read(key) {
    try {
      return JSON.parse(window.localStorage.getItem(key));
    } catch (err) {
      return null;
    }
  }

  function words(text) { return text ? text.split(" ").filter(Boolean) : []; }

  // Each list of tiles. It keeps two things for arrange.js: the order as written (data-written), which a saved order is merged
  // into and which stays whatever this does, and the order a screen has when nothing is saved for it (data-default), which is where
  // Reset goes. A list asked about twice keeps the written order it first recorded.
  function tiles(list, direction, saved) {
    var items = kids(list).filter(function (li) { return attr(li, "data-tile") !== null; });
    var byId = {};
    items.forEach(function (li) { byId[attr(li, "data-tile")] = li; });
    var written = words(attr(list, "data-written")).filter(function (id) { return byId[id]; });
    if (written.length !== items.length) written = items.map(function (li) { return attr(li, "data-tile"); });
    var plain = direction
      ? leveled(written.map(function (id) { return { id: id, level: levelOf(attr(byId[id], "data-level")) }; }), direction)
      : written;
    var mine = saved[attr(list, "data-order")];
    var ids = mine ? merge(written, mine) : plain;
    list.setAttribute("data-written", written.join(" "));
    list.setAttribute("data-default", plain.join(" "));
    ids.forEach(function (id) { list.appendChild(byId[id]); });
  }

  // Put `moving` (elements) in `order` (their indexes) where they are now, whatever sits between them: a mark is left in each place
  // first, and each element goes to the mark of its turn.
  function reseat(moving, order) {
    var marks = moving.map(function (el) {
      var mark = document.createComment("");
      el.parentNode.insertBefore(mark, el);
      return mark;
    });
    order.forEach(function (index, turn) { marks[turn].parentNode.insertBefore(moving[index], marks[turn]); });
    marks.forEach(function (mark) { mark.parentNode.removeChild(mark); });
  }

  // The sections of a topic, and the "On this page" list that names them, in order for `direction`.
  function sections(found, jump, direction) {
    if (!direction || found.length < 2) return;
    var order = leveled(found.map(function (el, index) { return { id: index, level: levelOf(attr(el, "data-level")) }; }), direction);
    var ids = order.map(function (index) { return attr(found[index], "id"); });
    reseat(found, order);
    if (!jump) return;
    var items = kids(jump);
    var target = function (li) {
      var link = kids(li)[0];
      var href = link ? attr(link, "href") : null;
      return href && href.charAt(0) === "#" ? href.slice(1) : null;
    };
    var turn = items.map(function (li) { return ids.indexOf(target(li)); });
    if (turn.some(function (n) { return n === -1; })) return;  // a link that is not to one of these sections: leave the list be
    reseat(items, items.map(function (li, i) { return i; }).sort(function (a, b) { return turn[a] - turn[b]; }));
  }

  function arrange(container) {
    if (!container) return;
    var site = document.documentElement.getAttribute("data-storage");
    var base = site && NAME.test(site) ? site : "phrasebook";
    var direction = way(read(base + ":prefs"));
    var saved = clean(read(base + ":order")).screens;
    var lists = [];
    var found = [];
    var jump = null;
    walk(container, function (el) {
      if (attr(el, "data-tiles") !== null && attr(el, "data-order") !== null) lists.push(el);
      // A topic's sections, or on a one-page group the topics' accordions (whose sections carry no level, so stay as written).
      else if ((el.tagName === "SECTION" || el.tagName === "DETAILS") && attr(el, "data-level") !== null) found.push(el);
      else if (el.tagName === "UL" && (attr(el, "class") || "").split(" ").indexOf("jump") !== -1) jump = el;
    });
    lists.forEach(function (list) { tiles(list, direction, saved); });
    sections(found, jump, direction);
  }

  // The page asks right after a list and after a topic's sections (the page is the event's `page`); nav.js asks for the copy of a
  // page it is about to slide in (in the event's `detail`).
  function pageOf(event) { return event.page || (event.detail && event.detail.page) || null; }
  document.addEventListener("phrasebook:order", function (event) { arrange(pageOf(event)); });
  document.addEventListener("phrasebook:peek", function (event) { arrange(pageOf(event)); });
})();
