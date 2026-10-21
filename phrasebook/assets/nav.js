/* Phrasebook framework: keys, and a drag to go back.
   The pages are the navigation: a group is a page of tiles, a topic is a page, and the Back button in the rail goes up one
   level. This script only adds to those links: arrow keys between tiles, Right to open the focused tile, Left or Backspace to
   go back, and a drag of the page with the reading direction, which takes the page out of view and goes back (the Back
   button, the keys and the drag all end the same way). A page that is reached from its parent slides in: that is decided in
   the head by a few lines of Site.document, so it needs no script here. It makes no network request, sets no cookies and
   stores nothing. Without it every link still works. */
(function () {
  "use strict";

  var EDGE = 20;            // touches that start this close to a screen edge are the system's (its own back gesture)
  var DEAD_ZONE = 10;       // pixels a touch moves before it is a scroll or a drag
  var STEEPNESS = 1.5;      // a drag must be this many times wider than tall
  var DISMISS_SHARE = 0.35; // letting go past this share of the width takes the page away
  var FLICK_SPEED = 0.5;    // pixels per millisecond that make a short drag a flick
  var FLICK_MIN = 40;       // the least a flick must have travelled
  var DISMISS_MS = 200;     // how long the page takes to leave

  // ---- the moves, with no page in sight so they can be tested on their own

  // Which move a key means, or null. Right opens and Left goes back, mirrored in a right-to-left page.
  function keyMove(key, rtl) {
    var open = rtl ? "ArrowLeft" : "ArrowRight";
    var back = rtl ? "ArrowRight" : "ArrowLeft";
    if (key === open) return "open";
    if (key === back || key === "Backspace") return "back";
    if (key === "ArrowDown") return "next";
    if (key === "ArrowUp") return "previous";
    if (key === "Home") return "first";
    if (key === "End") return "last";
    return null;
  }

  // Where focus goes among `count` tiles for a move along them. Other moves leave it where it is. It stops at both ends.
  function step(index, count, move) {
    if (count < 1) return -1;
    var last = count - 1;
    if (move === "next") return Math.min(last, index + 1);
    if (move === "previous") return Math.max(0, index - 1);
    if (move === "first") return 0;
    if (move === "last") return last;
    return index;
  }

  // The way the reading direction runs along the screen: right in a left-to-right page, left in a right-to-left one.
  function sign(rtl) { return rtl ? -1 : 1; }

  // What a touch that has moved (dx, dy) is: null while it is still inside the dead zone, then "drag" if it goes with the
  // reading direction and is wide rather than tall, or "scroll" (anything else, left to the browser).
  function lock(dx, dy, rtl) {
    var ax = Math.abs(dx);
    var ay = Math.abs(dy);
    if (Math.max(ax, ay) < DEAD_ZONE) return null;
    return dx * sign(rtl) > 0 && ax >= STEEPNESS * ay ? "drag" : "scroll";
  }

  // How far the page follows the finger: only with the reading direction, never the other way.
  function offset(dx, rtl) {
    return Math.max(0, dx * sign(rtl));
  }

  // Whether letting go takes the page away (true) or lets it spring back (false): dragged far enough, or flicked.
  function shouldDismiss(travelled, width, speed) {
    return travelled >= width * DISMISS_SHARE || (speed >= FLICK_SPEED && travelled >= FLICK_MIN);
  }

  var api = { keyMove: keyMove, step: step, lock: lock, offset: offset, shouldDismiss: shouldDismiss };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  // ---- the page

  var root = document.documentElement;
  var main = document.getElementById("main");
  var rtl = function () { return root.getAttribute("dir") === "rtl"; };
  var leaving = false;

  function backLink() { return document.querySelector("[data-back]"); }

  function goBack() {
    var back = backLink();
    if (back && back.getAttribute("href")) window.location.href = back.getAttribute("href");
  }

  function reducedMotion() {
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  // Take the page out of view in the reading direction, then go back. With no Back link (the home page) nothing happens.
  function dismiss() {
    if (!backLink() || leaving) return;
    leaving = true;
    // Where the browser animates the move between pages, it carries the page away, from wherever the finger left it.
    if (!main || reducedMotion() || "PageRevealEvent" in window) {
      goBack();
      return;
    }
    var finished = false;
    function finish() {
      if (finished) return;
      finished = true;
      goBack();
    }
    main.style.transition = "transform " + DISMISS_MS + "ms ease-out";
    main.style.transform = "translateX(" + sign(rtl()) * window.innerWidth + "px)";
    main.addEventListener("transitionend", finish, { once: true });
    window.setTimeout(finish, DISMISS_MS + 120);  // in case the transition never reports
  }

  function springBack() {
    if (!main) return;
    main.style.transition = "transform 180ms ease-out";
    main.style.transform = "";
    window.setTimeout(function () { main.style.transition = ""; }, 200);
  }

  function onKey(event) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    var target = event.target;
    if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;  // arrows belong to the control
    if (target && target.closest && target.closest("#search-card")) return;  // and so do the keys inside the search card
    var move = keyMove(event.key, rtl());
    if (!move) return;
    var list = target && target.closest ? target.closest("[data-tiles]") : null;
    var links = list ? Array.prototype.slice.call(list.querySelectorAll(".tile-link")) : [];
    var at = links.indexOf(document.activeElement);
    if (move === "back") {
      event.preventDefault();
      dismiss();
    } else if (list && at !== -1) {
      event.preventDefault();
      if (move === "open") {
        window.location.href = links[at].getAttribute("href");
      } else {
        links[step(at, links.length, move)].focus();
      }
    }
  }

  function onDrag() {
    var start = null;
    main.addEventListener("touchstart", function (event) {
      start = null;
      if (!backLink() || leaving || event.touches.length !== 1) return;
      var t = event.touches[0];
      if (t.clientX < EDGE || t.clientX > window.innerWidth - EDGE) return;
      start = { x: t.clientX, y: t.clientY, time: Date.now(), mode: null, travelled: 0 };
    }, { passive: true });
    main.addEventListener("touchmove", function (event) {
      if (!start) return;
      var t = event.touches[0];
      var dx = t.clientX - start.x;
      var dy = t.clientY - start.y;
      if (start.mode === null) {
        start.mode = lock(dx, dy, rtl());
        if (start.mode === null) return;
      }
      if (start.mode !== "drag") {  // a scroll, or the wrong way: leave it to the browser
        start = null;
        return;
      }
      start.travelled = offset(dx, rtl());
      main.style.transition = "none";
      main.style.transform = "translateX(" + sign(rtl()) * start.travelled + "px)";
      if (event.cancelable) event.preventDefault();
    }, { passive: false });
    function release(cancelled) {
      var drag = start;
      start = null;
      if (!drag || drag.mode !== "drag") return;
      var elapsed = Math.max(1, Date.now() - drag.time);
      if (!cancelled && shouldDismiss(drag.travelled, window.innerWidth, drag.travelled / elapsed)) {
        dismiss();
      } else {
        springBack();
      }
    }
    main.addEventListener("touchend", function () { release(false); }, { passive: true });
    main.addEventListener("touchcancel", function () { release(true); }, { passive: true });
  }

  document.addEventListener("keydown", onKey);
  // A plain click on Back leaves the same way a drag does. Modified clicks stay ordinary links.
  var back = backLink();
  if (back) {
    back.addEventListener("click", function (event) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      dismiss();
    });
  }
  if (main) onDrag();
  // Coming back to this page from the browser's own cache must not leave it slid away.
  window.addEventListener("pageshow", function () {
    leaving = false;
    if (main) {
      main.style.transition = "";
      main.style.transform = "";
    }
  });
})();
