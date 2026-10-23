/* Phrasebook framework: keys, and moving between pages sideways.
   The pages are the navigation: a group is a page of tiles, a topic is a page, and the Back button in the rail goes up one
   level. This script only adds to those links: arrow keys between tiles, Right to open the focused tile, Left or Backspace to
   go back, and a drag of the page with the reading direction. Opening a topic and going back are one move: the page and the
   one it goes to sit edge to edge and slide together, following the finger in a drag, and the real page takes its place when
   they have landed (the tap, the keys, the Back button and the drag all end the same way). To show the other page it reads that
   page of this site once, from the service worker's cache when there is one; that is its only request, it goes to no other
   site, and it sets no cookies and stores nothing. A tile that is a related topic (data-related) tells the page it opens which
   topic it was followed from, so that Back returns there. Where it cannot, the page that is reached from its parent still slides in:
   that is decided in the head by a few lines of Site.document. Without this script every link still works. */
(function () {
  "use strict";

  var EDGE = 20;            // touches that start this close to a screen edge are the system's (its own back gesture)
  var DEAD_ZONE = 10;       // pixels a touch moves before it is a scroll or a drag
  var STEEPNESS = 1.5;      // a drag must be this many times wider than tall
  var DISMISS_SHARE = 0.35; // letting go past this share of the width takes the page away
  var FLICK_SPEED = 0.5;    // pixels per millisecond that make a short drag a flick
  var FLICK_MIN = 40;       // the least a flick must have travelled
  var SLIDE_MS = 260;       // how long the two pages take to slide together, from the start (less from partway)
  var MIN_MS = 120;         // the least a slide that has begun takes to finish
  var SPRING_MS = 180;      // how long a drag that is let go too soon takes to spring back
  var WAIT_MS = 300;        // how long a tap waits for the other page before going there the plain way
  var EASE = "cubic-bezier(.2,.8,.2,1)";
  var PAGE = /^[a-z0-9-]+\.html$/;       // a page of this site, as a related topic names the one it came from
  var ANCHOR = /^[A-Za-z0-9._-]+$/;      // a section id that can travel in the address

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

  // Where the two pages are when they have gone x pixels along their move: the one leaving, and the one arriving, which waits
  // one width away and comes in beside it, so the two always sit edge to edge. Opening a topic (forward) the pages go toward
  // the start; going back they go toward the end; a right-to-left page mirrors both.
  function places(x, width, forward, rtl) {
    var out = (forward ? -1 : 1) * sign(rtl);
    return { leaving: out * x, arriving: out * (x - width) };
  }

  // The address with the way the page goes (see Site.document, which reads it and takes it out again): #slide=<direction>, then
  // ;from=<page> for a related topic, the topic Back returns to, and ;at=<id> for the section the address named, which it would
  // otherwise have used itself.
  function marked(href, direction, from) {
    var cut = href.indexOf("#");
    var base = cut === -1 ? href : href.slice(0, cut);
    var at = cut === -1 ? "" : href.slice(cut + 1);
    return base + "#slide=" + direction + (from ? ";from=" + from : "") + (at && ANCHOR.test(at) ? ";at=" + at : "");
  }

  // The section an address names, if it is one that can be linked to; otherwise null.
  function anchorOf(href) {
    var at = href.indexOf("#") === -1 ? "" : href.slice(href.indexOf("#") + 1);
    return at && ANCHOR.test(at) ? at : null;
  }

  // The topic this page was opened from as a related topic, as the head left it in the history entry; null if it was not (or
  // the entry says something that is not a page of this site). Its Back goes there.
  function cameFrom(state) {
    var from = state && typeof state === "object" ? state.from : null;
    return typeof from === "string" && PAGE.test(from) ? from : null;
  }

  var api = { keyMove: keyMove, step: step, lock: lock, offset: offset, shouldDismiss: shouldDismiss, places: places, marked: marked, anchorOf: anchorOf, cameFrom: cameFrom };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  // ---- the page

  var root = document.documentElement;
  var main = document.getElementById("main");
  var rtl = function () { return root.getAttribute("dir") === "rtl"; };
  var leaving = false;
  var stage = null;  // the other page, set beside this one while the two move together; null when nothing is moving
  var along = 0;     // how far along their move the two pages are, in pixels

  function backLink() { return document.querySelector("[data-back]"); }

  function reducedMotion() {
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  // The way the page goes, carried in the address for the next page, for when the other page could not be set beside this
  // one: its head slides it in from the same side (see Site.document) and takes the mark out again. Only where the browser
  // does not move the pages itself; otherwise its own move does it, and the address is left alone.
  function toward(href, direction, from) {
    var native = "PageRevealEvent" in window;
    if (native && !from && anchorOf(href) === null) return href;
    // Where the browser slides the pages itself, a mark that has to go in the address (the topic Back returns to, a section)
    // says "none", so its own move stands down rather than racing the head's clean-up of the address.
    return marked(href, native ? "none" : direction, from);
  }

  // ---- the other page

  var pages = {};  // address -> the promise of that page's main element, asked for once

  function sameSite(href) {
    try {
      return new URL(href, window.location.href).origin === window.location.origin;
    } catch (err) {
      return false;
    }
  }

  // The main element of a page of this site, to be set beside this one, or null if it cannot be had. This is the only
  // request the script makes, and only for a page of this site (the service worker has them cached, so it works offline).
  function neighbour(href) {
    if (!pages[href]) {
      if (!window.fetch || !window.DOMParser || !sameSite(href)) {
        pages[href] = Promise.resolve(null);
      } else {
        pages[href] = window.fetch(href)
          .then(function (response) { return response.ok ? response.text() : null; })
          .then(function (text) {
            var found = text ? new DOMParser().parseFromString(text, "text/html").getElementById("main") : null;
            return found ? document.importNode(found, true) : null;
          })
          .catch(function () { return null; });
      }
    }
    return pages[href];
  }

  // The same, but not worth waiting long for: null if it is not at hand in a moment.
  function ready(href) {
    var late = new Promise(function (resolve) { window.setTimeout(function () { resolve(null); }, WAIT_MS); });
    return Promise.race([neighbour(href), late]);
  }

  // ---- the two pages moving together

  // Put a copy of the other page's main in a layer that covers the page area and clips it, waiting where it will come in from.
  // The copy is only for the eye: it has no ids or radio names to clash with this page's, and it is inert and hidden from
  // screen readers.
  function stageBeside(other, forward, at) {
    var copy = other.cloneNode(true);
    var each = function (selector, name) {
      Array.prototype.forEach.call(copy.querySelectorAll(selector), function (node) { node.removeAttribute(name); });
    };
    var target = at && ANCHOR.test(at) ? copy.querySelector('[id="' + at + '"]') : null;
    if (target) target.setAttribute("data-at", "");  // marked before the ids go, so the copy can be scrolled to it below
    copy.removeAttribute("id");
    each("[id]", "id");
    each("[name]", "name");
    Array.prototype.forEach.call(copy.querySelectorAll("script"), function (node) { node.parentNode.removeChild(node); });
    copy.setAttribute("aria-hidden", "true");
    copy.setAttribute("inert", "");
    copy.className = (copy.className + " peek-page").trim();
    // Let the other scripts finish the copy before it is seen (arrange.js puts its tiles in the saved order).
    document.dispatchEvent(new CustomEvent("phrasebook:peek", { detail: { page: copy } }));
    var layer = document.createElement("div");
    layer.className = "peek";
    layer.appendChild(copy);
    document.body.appendChild(layer);
    root.classList.add("is-sliding");
    stage = { layer: layer, page: copy, forward: forward, width: layer.getBoundingClientRect().width };
    // Where the address names a section, the real page will be scrolled to it a little under the title bar (the stylesheet's
    // scroll-margin-top), as far as the page is long enough to go. The copy is put there now, so the handover shows no jump.
    var landing = copy.querySelector("[data-at]");
    if (landing) {
      var gap = parseFloat(window.getComputedStyle(root).fontSize) || 16;
      var down = landing.getBoundingClientRect().top - copy.getBoundingClientRect().top - gap;
      var most = Math.max(0, copy.offsetHeight - layer.clientHeight);
      copy.style.top = -Math.min(Math.max(0, down), most) + "px";
    }
    place(along);
    void layer.offsetWidth;  // settle the first place, so that the next one is animated from it
  }

  function place(x) {
    along = x;
    if (!stage) {
      main.style.transform = "translateX(" + sign(rtl()) * x + "px)";
      return;
    }
    var at = places(x, stage.width, stage.forward, rtl());
    main.style.transform = "translateX(" + at.leaving + "px)";
    stage.page.style.transform = "translateX(" + at.arriving + "px)";
  }

  function clearStage() {
    if (stage) {
      stage.layer.parentNode.removeChild(stage.layer);
      stage = null;
    }
    root.classList.remove("is-sliding");
    along = 0;
    if (main) {
      main.style.transition = "";
      main.style.transform = "";
    }
  }

  // Carry the two pages to x pixels along, then call `then`. The timer is in case the transition never reports.
  function glide(x, ms, then) {
    var finished = false;
    function finish(event) {
      if (finished || (event && event.target !== main)) return;  // a transition inside the page is not this one
      finished = true;
      main.removeEventListener("transitionend", finish);
      then();
    }
    var transition = "transform " + ms + "ms " + EASE;
    main.style.transition = transition;
    if (stage) stage.page.style.transition = transition;
    place(x);
    main.addEventListener("transitionend", finish);
    window.setTimeout(finish, ms + 120);
  }

  // Go to `href` by moving there: the other page comes in beside this one as they slide together, then the real page takes
  // its place with no move of its own (its head is told so by #slide=none). If the other page is not at hand in a moment, or
  // the browser cannot show it, go the plain way, which slides the new page in after this one has left, or lets the browser do it.
  // `from` is the page a related topic is followed from, which the page it opens makes the place Back returns to.
  function travel(href, forward, from) {
    leaving = true;
    if (!main || reducedMotion()) {
      window.location.href = from || anchorOf(href) !== null ? marked(href, "none", from) : href;
      return;
    }
    ready(href).then(function (other) {
      if (!other && !stage) {
        window.location.href = toward(href, forward ? "forward" : "back", from);
        return;
      }
      if (!stage) stageBeside(other, forward, anchorOf(href));
      var width = stage.width;
      glide(width, Math.max(MIN_MS, Math.round(SLIDE_MS * (1 - along / width))), function () {
        window.location.href = marked(href, "none", from);
      });
    });
  }

  function open(href, from) {
    if (!leaving) travel(href, true, from);
  }

  // The name of this page's file, for a related topic to say where it was followed from.
  function thisPage() {
    var name = window.location.pathname.split("/").pop();
    return name && PAGE.test(name) ? name : "index.html";
  }

  // Open a tile's topic. A related one says which topic it came from; an ordinary tile does not, and Back goes up the tree.
  function openTile(link) {
    open(link.getAttribute("href"), link.hasAttribute("data-related") ? thisPage() : null);
  }

  // Take the page out of view in the reading direction, then go back. With no Back link (the home page) nothing happens.
  function dismiss() {
    var back = backLink();
    if (!back || leaving || !back.getAttribute("href")) return;
    travel(back.getAttribute("href"), false);
  }

  function springBack() {
    if (!main) return;
    if (stage) {
      glide(0, SPRING_MS, clearStage);
      return;
    }
    main.style.transition = "transform " + SPRING_MS + "ms ease-out";
    place(0);
    window.setTimeout(clearStage, SPRING_MS + 20);
  }

  // A tap on a tile opens its topic as a card that slides in beside this page. Modified clicks stay ordinary links.
  function onTile() {
    var tile = function (event) {
      return event.target && event.target.closest ? event.target.closest("[data-tiles] a") : null;
    };
    // Ask for the topic as soon as a finger or pointer goes down, so it is at hand by the time the tap lands.
    document.addEventListener("pointerdown", function (event) {
      var link = tile(event);
      if (link && !root.hasAttribute("data-arranging")) neighbour(link.getAttribute("href"));
    }, { passive: true });
    document.addEventListener("click", function (event) {
      var link = tile(event);
      if (!link || leaving || event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (root.hasAttribute("data-arranging")) return;  // while tiles are being arranged (arrange.js) a tap is its own
      event.preventDefault();
      openTile(link);
    });
  }

  function onKey(event) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    if (root.hasAttribute("data-arranging")) return;  // while tiles are being arranged (arrange.js) the keys are its own
    var target = event.target;
    if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;  // arrows belong to the control
    if (target && target.closest && target.closest("#search-card, #help-card")) return;  // and so do the keys inside the search card and the help sheet
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
        openTile(links[at]);
      } else {
        links[step(at, links.length, move)].focus();
      }
    }
  }

  // A drag with the reading direction takes this page along with the finger and brings the page above it in beside it, the
  // two moving as one. Letting go far enough, or flicking, carries them the rest of the way; otherwise they spring back.
  function onDrag() {
    var start = null;
    main.addEventListener("touchstart", function (event) {
      start = null;
      if (!backLink() || leaving || event.touches.length !== 1 || root.hasAttribute("data-arranging")) return;
      var t = event.touches[0];
      if (t.clientX < EDGE || t.clientX > window.innerWidth - EDGE) return;
      start = { x: t.clientX, y: t.clientY, time: Date.now(), mode: null, travelled: 0, over: false };
      neighbour(backLink().getAttribute("href"));
    }, { passive: true });
    main.addEventListener("touchmove", function (event) {
      if (!start) return;
      var t = event.touches[0];
      var dx = t.clientX - start.x;
      var dy = t.clientY - start.y;
      if (start.mode === null) {
        start.mode = lock(dx, dy, rtl());
        if (start.mode === null) return;
        if (start.mode === "drag") {
          var drag = start;
          neighbour(backLink().getAttribute("href")).then(function (other) {
            if (other && !drag.over && !stage && !leaving) stageBeside(other, false);
          });
        }
      }
      if (start.mode !== "drag") {  // a scroll, or the wrong way: leave it to the browser
        start = null;
        return;
      }
      start.travelled = offset(dx, rtl());
      main.style.transition = "none";
      if (stage) stage.page.style.transition = "none";
      place(start.travelled);
      if (event.cancelable) event.preventDefault();
    }, { passive: false });
    function release(cancelled) {
      var drag = start;
      start = null;
      if (!drag || drag.mode !== "drag") return;
      drag.over = true;
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

  // A page opened from a related tile was told in its history entry which topic that was, and its Back returns there; the
  // address and the trail stay as the page's own. Opened any other way, Back goes up the tree.
  var came = cameFrom(window.history.state);
  if (came && came !== thisPage() && backLink()) backLink().setAttribute("href", came);

  document.addEventListener("keydown", onKey);
  // A plain click on Back leaves the same way a drag does. Modified clicks stay ordinary links.
  var back = backLink();
  if (back) {
    back.addEventListener("click", function (event) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      dismiss();
    });
    // The page above is the one a drag or a tap on Back will want, so have it ready once the page has settled.
    window.setTimeout(function () { neighbour(back.getAttribute("href")); }, 400);
  }
  if (main) onDrag();
  onTile();
  // Coming back to this page from the browser's own cache must not leave it slid away.
  window.addEventListener("pageshow", function () {
    leaving = false;
    clearStage();
  });
})();
