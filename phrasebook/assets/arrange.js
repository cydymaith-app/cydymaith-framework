/* Phrasebook framework: arranging the tiles on the home page and on a group page.
   The spanner in the rail turns edit order on. Then a tile can be dragged to a new place, or tapped and then tapped where it
   should go, and the arrow keys move a picked tile (Escape puts it back). Save order, or the spanner again, saves the order on this
   device. Leaving the page without saving discards the changes. Reset puts one screen back in its default order, and Settings
   resets them all. The order has its own key in localStorage, separate from the preferences, and is sent nowhere. A saved order is
   applied before anything is painted, and to the copy of a page that nav.js slides in, by order.js (loaded in the head), which also
   puts a screen that has no saved order in order from simple to advanced when the person asks for that. It leaves two things on each
   list for this script: the order as written (data-written) and the order the screen has when nothing is saved (data-default), which
   is where Reset goes. Without this script the tiles keep the order they were given and no control is shown. */
(function () {
  "use strict";

  var VERSION = 1;
  var ID = /^[a-z0-9][a-z0-9-]{0,63}$/;
  var SCREEN = /^(index|group-[a-z0-9-]+)$/;
  var MAX_TILES = 200;
  var MOVE_MIN = 8;       // pixels a press must travel before it is a drag
  var SLIDE_MS = 180;     // how long a tile takes to slide into its new place

  // ---- the moves, with no page in sight so they can be tested on their own

  // Keep only saved orders this script understands. Anything else in storage is ignored.
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

  // The saved order, then any tile it does not name (one added in a later release) in its default order. A name the screen
  // no longer has is dropped.
  function merge(defaults, saved) {
    var kept = saved.filter(function (id) { return defaults.indexOf(id) !== -1; });
    return kept.concat(defaults.filter(function (id) { return kept.indexOf(id) === -1; }));
  }

  // The order with the tile at `from` taken out and put at `to`, clamped to the ends. The others keep their order.
  function move(ids, from, to) {
    var out = ids.slice();
    if (from < 0 || from >= out.length) return out;
    var id = out.splice(from, 1)[0];
    out.splice(Math.max(0, Math.min(out.length, to)), 0, id);
    return out;
  }

  // The tile whose centre is nearest the point, or -1 when there are none. `rects` are the tiles' rectangles in order.
  function targetIndex(point, rects) {
    var best = -1;
    var bestDistance = Infinity;
    rects.forEach(function (r, i) {
      var dx = point.x - (r.left + r.width / 2);
      var dy = point.y - (r.top + r.height / 2);
      var d = dx * dx + dy * dy;
      if (d < bestDistance) {
        best = i;
        bestDistance = d;
      }
    });
    return best;
  }

  // How far an arrow key moves along the tiles: 1 for the next, -1 for the previous, 0 for any other key. Left and Right
  // swap in a right-to-left page, as they do for the rest of the site.
  function arrowDir(key, rtl) {
    if (key === "ArrowRight") return rtl ? -1 : 1;
    if (key === "ArrowLeft") return rtl ? 1 : -1;
    if (key === "ArrowDown") return 1;
    if (key === "ArrowUp") return -1;
    return 0;
  }

  var api = { clean: clean, merge: merge, move: move, targetIndex: targetIndex, arrowDir: arrowDir };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  // ---- the page

  var root = document.documentElement;
  var site = root.getAttribute("data-storage");
  var NAME = /^[a-z0-9][a-z0-9._-]*$/;
  // Each site names its own storage (data-storage on <html>), as preferences do, so two sites on one origin never share an order.
  var KEY = (site && NAME.test(site) ? site : "phrasebook") + ":order";
  var list = document.querySelector("[data-tiles][data-order]");
  var screen = list ? list.getAttribute("data-order") : "";
  var button = document.getElementById("arrange-button");
  var bar = document.querySelector("[data-arrange-bar]");
  var live = document.querySelector("[data-arrange-status]");
  var resetBox = document.querySelector("[data-reset-orders]");
  var resetStatus = resetBox ? resetBox.querySelector("[data-reset-status]") : null;
  var data = clean(null);
  var defaults = [];  // the tiles in the order they are written, which a saved order is merged into
  var fallback = [];  // the order the screen has with nothing saved for it: as written, or simple to advanced if the person asked
  var state = { arranging: false, picked: null, press: null, ignoreClick: false };

  // Storage can be blocked, full or empty (private windows, site data cleared). Never let that break the page.
  function load() {
    try {
      return clean(JSON.parse(window.localStorage.getItem(KEY)));
    } catch (err) {
      return clean(null);
    }
  }

  function persist() {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(data));
      return true;
    } catch (err) {
      return false;
    }
  }

  function tiles() {
    return list ? Array.prototype.slice.call(list.querySelectorAll(":scope > li[data-tile]")) : [];
  }

  function idOf(li) { return li.getAttribute("data-tile"); }
  function linkOf(li) { return li.querySelector(".tile-link"); }
  function tileIds() { return tiles().map(idOf); }

  // The ids order.js left on the list in `name`, if they are all still tiles of this list; otherwise the tiles as they stand.
  function listed(name) {
    var now = tileIds();
    var ids = (list.getAttribute(name) || "").split(" ").filter(Boolean);
    return ids.length === now.length && ids.every(function (id) { return now.indexOf(id) !== -1; }) ? ids : now;
  }
  function indexOf(li) { return tiles().indexOf(li); }

  // A tile's name as a screen reader should hear it: both languages.
  function name(li) {
    return [li.querySelector(".l1"), li.querySelector(".l2")]
      .filter(Boolean)
      .map(function (node) { return node.textContent; })
      .join(" / ");
  }

  function fill(template, values) {
    return String(template || "").replace(/\{(\w+)\}/g, function (all, key) {
      return key in values ? values[key] : all;
    });
  }

  // Says a message from the bar's data attributes in the live region. `li` names a tile and its place, when there is one.
  function say(attribute, li) {
    if (!live || !bar) return;
    var total = tiles().length;
    live.textContent = fill(bar.getAttribute(attribute), {
      name: li ? name(li) : "",
      n: li ? indexOf(li) + 1 : "",
      total: total,
    });
  }

  function reducedMotion() {
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  // Puts the tiles in `ids` order. With `animate`, each tile slides from where it was, so the move can be followed.
  function reorder(ids, animate) {
    var items = tiles();
    var byId = {};
    items.forEach(function (li) { byId[idOf(li)] = li; });
    var before = items.map(function (li) { return li.getBoundingClientRect(); });
    ids.forEach(function (id) { if (byId[id]) list.appendChild(byId[id]); });
    if (!animate || reducedMotion()) return;
    items.forEach(function (li, i) {
      var now = li.getBoundingClientRect();
      var dx = before[i].left - now.left;
      var dy = before[i].top - now.top;
      if (!dx && !dy) return;
      li.style.transition = "none";
      li.style.transform = "translate(" + dx + "px," + dy + "px)";
      li.getBoundingClientRect();  // draw the start position before the slide begins
      li.style.transition = "transform " + SLIDE_MS + "ms ease-out";
      li.style.transform = "";
      window.setTimeout(function () { li.style.transition = ""; }, SLIDE_MS + 50);
    });
  }

  // The order to show: the saved one for this screen, or the default.
  function wanted() {
    var saved = data.screens[screen];
    return saved ? merge(defaults, saved) : fallback.slice();
  }

  // Moves one tile to place `to`. The order is kept only in the page until it is saved.
  function place(li, to) {
    var ids = tileIds();
    var from = ids.indexOf(idOf(li));
    if (from === to) return false;
    var focused = document.activeElement === linkOf(li);  // moving a node drops focus, so put it back
    reorder(move(ids, from, to), true);
    if (focused) linkOf(li).focus({ preventScroll: true });
    say("data-moved", li);
    return true;
  }

  function setArranging(on) {
    state.arranging = on;
    if (on) root.setAttribute("data-arranging", "");
    else root.removeAttribute("data-arranging");
    if (button) button.setAttribute("aria-pressed", on ? "true" : "false");
    // In edit order the tiles show only their icons, so each link is named here, and the name is dropped again afterwards.
    tiles().forEach(function (li) {
      if (on) linkOf(li).setAttribute("aria-label", name(li));
      else linkOf(li).removeAttribute("aria-label");
    });
  }

  function pick(li) {
    unpick();
    state.picked = { li: li, origin: indexOf(li) };
    li.classList.add("is-picked");
    say("data-picked", li);
  }

  function unpick() {
    if (state.picked) state.picked.li.classList.remove("is-picked");
    state.picked = null;
  }

  // Moves the picked tile one place along, or leaves it where it is at either end.
  function nudge(dir) {
    var li = state.picked.li;
    place(li, Math.max(0, Math.min(tiles().length - 1, indexOf(li) + dir)));
  }

  // Puts the picked tile back where it was when it was picked up.
  function cancel() {
    var picked = state.picked;
    place(picked.li, picked.origin);
    unpick();
    say("data-cancelled", picked.li);
  }

  // With nothing picked, an arrow key moves focus along the tiles and stops at both ends.
  function browse(dir) {
    var items = tiles();
    var at = items.map(linkOf).indexOf(document.activeElement);
    var to = at === -1 ? (dir > 0 ? 0 : items.length - 1) : Math.max(0, Math.min(items.length - 1, at + dir));
    linkOf(items[to]).focus({ preventScroll: true });
  }

  // Leaves edit order. `keep` saves the order on this device; otherwise the changes are dropped and the saved order returns.
  function leave(keep) {
    unpick();
    if (keep) {
      data.screens[screen] = tileIds();
      say(persist() ? "data-saved" : "data-failed");
    }
    setArranging(false);
    reorder(wanted(), false);
  }

  function resetScreen() {
    unpick();
    delete data.screens[screen];
    if (!persist()) say("data-failed");
    reorder(fallback.slice(), true);
    say("data-reset");
  }

  function resetAll() {
    data.screens = {};
    var ok = persist();
    if (resetStatus) resetStatus.textContent = resetStatus.getAttribute(ok ? "data-done" : "data-failed");
  }

  function toggle() {
    if (state.arranging) leave(true);
    else setArranging(true);
  }

  // A tap picks a tile up, and a second tap on another tile puts it in that tile's place. Tapping the picked tile again sets it down.
  function onClick(event) {
    if (!state.arranging) return;  // not arranging: the link goes in as usual
    event.preventDefault();        // while arranging a tile is never followed
    // The click that ends a drag is not a tap. Only that one click is ignored, so a tap straight after a drag still counts.
    if (state.ignoreClick) {
      state.ignoreClick = false;
      return;
    }
    var li = event.target.closest ? event.target.closest("li[data-tile]") : null;
    if (!li) return;
    if (!state.picked) {
      pick(li);
    } else if (state.picked.li === li) {
      unpick();
    } else {
      var picked = state.picked.li;
      unpick();
      place(picked, indexOf(li));
    }
  }

  function onKey(event) {
    if (!state.arranging || event.altKey || event.ctrlKey || event.metaKey) return;
    var target = event.target;
    if (target && (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) || (target.closest && target.closest("#search-card")))) return;
    if (event.key === "Escape" && state.picked) {
      event.preventDefault();
      cancel();
      return;
    }
    var dir = arrowDir(event.key, root.getAttribute("dir") === "rtl");
    if (!dir) return;
    event.preventDefault();
    if (state.picked) nudge(dir);
    else browse(dir);
  }

  // A press becomes a drag once it has moved. The tile then follows the pointer, taking each place it passes over.
  function onDown(event) {
    if (!state.arranging || (event.pointerType === "mouse" && event.button !== 0)) return;
    var li = event.target.closest ? event.target.closest("li[data-tile]") : null;
    state.ignoreClick = false;  // a new press: any click from an earlier drag has had its chance
    if (li) state.press = { li: li, id: event.pointerId, x: event.clientX, y: event.clientY, dragging: false };
  }

  function onMove(event) {
    var press = state.press;
    if (!press || event.pointerId !== press.id) return;
    if (!press.dragging) {
      if (Math.max(Math.abs(event.clientX - press.x), Math.abs(event.clientY - press.y)) < MOVE_MIN) return;
      press.dragging = true;
      list.setPointerCapture(press.id);
      pick(press.li);
      press.li.classList.add("is-dragging");
    }
    var rects = tiles().map(function (li) { return li.getBoundingClientRect(); });
    var to = targetIndex({ x: event.clientX, y: event.clientY }, rects);
    if (to !== -1) place(press.li, to);
  }

  function onUp(event) {
    var press = state.press;
    if (!press || event.pointerId !== press.id) return;
    state.press = null;
    if (!press.dragging) return;  // a tap: the click does the rest
    press.li.classList.remove("is-dragging");
    unpick();
    state.ignoreClick = true;
  }

  function init() {
    data = load();
    if (list) {
      defaults = listed("data-written");
      fallback = listed("data-default");
      reorder(wanted(), false);
    }
    if (list && bar && button) {
      button.hidden = false;
      button.addEventListener("click", toggle);
      bar.querySelector("[data-arrange-done]").addEventListener("click", function () { leave(true); });
      bar.querySelector("[data-arrange-reset]").addEventListener("click", resetScreen);
      list.addEventListener("click", onClick);
      list.addEventListener("pointerdown", onDown);
      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
      document.addEventListener("pointercancel", onUp);
      document.addEventListener("keydown", onKey);
    }
    if (resetBox) {
      resetBox.hidden = false;
      resetBox.querySelector("button").addEventListener("click", resetAll);
    }
    // Back from the browser's cache keeps the page as it was left: an unsaved order is dropped, as on any other leave.
    window.addEventListener("pageshow", function (event) {
      if (event.persisted && state.arranging) leave(false);
    });
  }

  init();
})();
