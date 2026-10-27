/* Phrasebook framework: remembers display preferences in this browser only.
   Preferences: light or dark appearance, a colour palette (and the palette last picked at each accessibility level),
   a regional form per language, the language shown by the Cy|En toggles, whether tiles and sections are put in order from
   simple to advanced, the reverse, or left as written (order.js does the ordering; this only remembers the choice), and
   how the key words of a row are marked: by colour (the default), by underline, or not at all.
   Colour is not offered at the high-contrast level, where the key colours are least distinct. The safe-colours level keeps it:
   its palettes' key colours are checked under simulated colour blindness.
   It also reveals the Share button.
   Storage is localStorage on this device. There are no cookies, no network requests and no analytics.
   The site works without this script: it then follows the device's light or dark setting, uses the default
   palette, and shows every regional form equally. A first-time visitor whose device asks for more contrast starts on the
   high-contrast palette. */
(function () {
  "use strict";

  var VERSION = 4;
  var root = document.documentElement;
  // Each site names its own storage (data-storage on <html>), so two phrasebooks on one origin, such as
  // different projects under one github.io name, never read or overwrite each other's choices.
  var NAME = /^[a-z0-9][a-z0-9._-]*$/;
  var site = root.getAttribute("data-storage");
  var KEY = (site && NAME.test(site) ? site : "phrasebook") + ":prefs";
  var LANG = /^[a-z]{2,3}(-[a-z0-9]+)*$/;
  var ID = /^[a-z][a-z0-9-]*$/;
  var APPEARANCES = ["system", "light", "dark"];
  // The edition's default palette (data-default-palette on <html>, absent for "default") is the page's baseline.
  var DEFAULT_PALETTE = root.getAttribute("data-default-palette");
  if (!DEFAULT_PALETTE || !ID.test(DEFAULT_PALETTE)) DEFAULT_PALETTE = "default";
  var LEVELS = ["standard", "safe", "high"];  // the accessibility levels: standard, safe colours, high contrast
  var ORDERS = ["written", "simple", "advanced"];  // tiles and sections as written, simplest first, most advanced first
  var KEYS = ["colour", "line", "off"];  // key words marked by colour, by underline, or not at all

  function empty() {
    return { v: VERSION, appearance: "system", palette: DEFAULT_PALETTE, order: "written", keys: "colour", picks: {}, varieties: {} };
  }

  // Keep only values we understand. Anything else in storage is ignored. Versions 1 (only varieties) and 2
  // (no remembered picks) are still read, so an earlier choice survives the upgrade.
  function clean(raw) {
    var out = empty();
    if (!raw || typeof raw !== "object" || [1, 2, 3, VERSION].indexOf(raw.v) === -1) return out;
    if (APPEARANCES.indexOf(raw.appearance) !== -1) out.appearance = raw.appearance;
    if (ORDERS.indexOf(raw.order) !== -1) out.order = raw.order;
    if (KEYS.indexOf(raw.keys) !== -1) out.keys = raw.keys;
    if (typeof raw.palette === "string" && ID.test(raw.palette)) out.palette = raw.palette;
    if (typeof raw.lang === "string" && LANG.test(raw.lang)) out.lang = raw.lang;
    if (raw.picks && typeof raw.picks === "object") {
      LEVELS.forEach(function (level) {
        if (typeof raw.picks[level] === "string" && ID.test(raw.picks[level])) out.picks[level] = raw.picks[level];
      });
    }
    var saved = raw.varieties;
    if (!saved || typeof saved !== "object") return out;
    Object.keys(saved).forEach(function (lang) {
      var value = saved[lang];
      if (LANG.test(lang) && typeof value === "string" && (value === "all" || ID.test(value))) {
        out.varieties[lang] = value;
      }
    });
    return out;
  }

  // Storage can be blocked, full or empty (private windows, site data cleared). Never let that break the page.
  function load() {
    try {
      return clean(JSON.parse(window.localStorage.getItem(KEY)));
    } catch (err) {
      return empty();
    }
  }

  function save(prefs) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(prefs));
      return true;
    } catch (err) {
      return false;
    }
  }

  function setVariety(lang, value) {
    if (value === "all") {
      root.removeAttribute("data-v-" + lang);
    } else {
      root.setAttribute("data-v-" + lang, value);
    }
  }

  // "system" sets no attribute, so the stylesheet follows the device's light or dark setting.
  function setAppearance(value) {
    if (value === "system") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", value);
    }
  }

  // Key words are marked by colour unless chosen otherwise, so "colour" sets no attribute.
  function setKeys(value) {
    if (value === "colour") {
      root.removeAttribute("data-keys");
    } else {
      root.setAttribute("data-keys", value);
    }
  }

  // The default palette is the page's baseline and sets no attribute.
  function setPalette(value) {
    if (value === DEFAULT_PALETTE) {
      root.removeAttribute("data-palette");
    } else {
      root.setAttribute("data-palette", value);
    }
  }

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  // The palette to start on when the device asks for more contrast (data-contrast-palette on <html>), if the page offers one.
  var CONTRAST_PALETTE = root.getAttribute("data-contrast-palette");
  if (CONTRAST_PALETTE && !ID.test(CONTRAST_PALETTE)) CONTRAST_PALETTE = null;

  // Nothing is stored yet: the first visit, or storage that is blocked or cleared.
  function firstVisit() {
    try {
      return window.localStorage.getItem(KEY) === null;
    } catch (err) {
      return true;
    }
  }

  function wantsContrast() {
    try {
      return !!(window.matchMedia && window.matchMedia("(prefers-contrast: more)").matches);
    } catch (err) {
      return false;
    }
  }

  var prefs = load();

  // A first-time visitor whose device asks for more contrast starts on the high-contrast palette, so the first screen they
  // see is one they can read. This is a starting point, not a saved choice: anything they pick in Settings replaces it, and it
  // is never applied once they have stored a choice.
  if (CONTRAST_PALETTE && firstVisit() && wantsContrast()) prefs.palette = CONTRAST_PALETTE;

  // Runs in the head, before the first paint, so there is no flash of the wrong theme or emphasis.
  setAppearance(prefs.appearance);
  setPalette(prefs.palette);
  setKeys(prefs.keys);
  Object.keys(prefs.varieties).forEach(function (lang) {
    setVariety(lang, prefs.varieties[lang]);
  });

  // The Cy|En toggles are radios that work with no script; this only remembers the language chosen and shows it again.
  function initLanguage() {
    if (typeof document.querySelectorAll !== "function") return;
    var radios = Array.prototype.slice.call(document.querySelectorAll("input.lang-radio, input.about-radio"));
    radios.forEach(function (r) {
      if (r.value === prefs.lang) r.checked = true;
      r.addEventListener("change", function () {
        if (!r.checked) return;
        prefs.lang = r.value;
        save(prefs);
      });
    });
  }

  // The Share button is hidden until here, and only shown if the browser can share or copy. No request is made.
  function initShare() {
    if (typeof document.querySelectorAll !== "function") return;
    var nav = (window && window.navigator) || {};
    var canCopy = !!(nav.clipboard && nav.clipboard.writeText);
    Array.prototype.slice.call(document.querySelectorAll("button.share")).forEach(function (button) {
      var url = button.getAttribute("data-url");
      if (!url || !(nav.share || canCopy)) return;
      button.hidden = false;
      button.addEventListener("click", function () {
        if (nav.share) {
          nav.share({ url: url }).catch(function () {});
        } else {
          nav.clipboard.writeText(url).then(function () {
            var status = button.parentNode.querySelector(".share-status");
            if (status) status.textContent = button.getAttribute("data-copied") || "";
          }, function () {});
        }
      });
    });
  }

  ready(function () {
    initLanguage();
    initShare();
    var panel = document.getElementById("prefs");
    if (!panel) return;
    var varieties = Array.prototype.slice.call(panel.querySelectorAll("input[data-variety-lang]"));
    var themes = Array.prototype.slice.call(panel.querySelectorAll("input[data-pref]"));

    // A saved value the page does not offer counts as the default.
    var offered = {};
    varieties.forEach(function (r) {
      var lang = r.getAttribute("data-variety-lang");
      (offered[lang] = offered[lang] || []).push(r.value);
    });
    Object.keys(offered).forEach(function (lang) {
      if (prefs.varieties[lang] && offered[lang].indexOf(prefs.varieties[lang]) === -1) {
        delete prefs.varieties[lang];
        setVariety(lang, "all");
      }
    });
    var swatches = themes.filter(function (r) { return r.getAttribute("data-pref") === "palette"; });
    var levelRadios = themes.filter(function (r) { return r.getAttribute("data-pref") === "access"; });
    var note = typeof panel.querySelector === "function" ? panel.querySelector(".colours-only") : null;
    var offered = swatches.map(function (r) { return r.value; });

    // The accessibility level a palette belongs to is written on its swatch.
    function levelOf(id) {
      var found = swatches.filter(function (r) { return r.value === id; })[0];
      return found ? found.getAttribute("data-tier") : null;
    }

    // The palette to use when a level is chosen: the one last picked there, or else the first the level lists.
    function paletteFor(level) {
      var pick = prefs.picks[level];
      if (pick && levelOf(pick) === level) return pick;
      var inLevel = swatches.filter(function (r) { return r.getAttribute("data-tier") === level; });
      var preferred = inLevel.filter(function (r) { return r.value === DEFAULT_PALETTE; })[0];
      return (preferred || inLevel[0] || { value: DEFAULT_PALETTE }).value;
    }

    // A level with a single scheme says so, since there is nothing to choose.
    function showNote(level) {
      if (!note) return;
      var count = swatches.filter(function (r) { return r.getAttribute("data-tier") === level; }).length;
      note.hidden = count > 1;
    }

    // A way of marking key words that suits the accessibility level: a choice a level does not offer is hidden, and one already
    // chosen becomes the underline. Returns true if the choice changed.
    var keyRadios = themes.filter(function (r) { return r.getAttribute("data-pref") === "keys"; });
    function fitKeys(level) {
      var changed = false;
      keyRadios.forEach(function (r) {
        var hide = (r.getAttribute("data-hide-at") || "").split(" ").indexOf(level) !== -1;
        if (r.parentNode) r.parentNode.hidden = hide;
        if (hide && prefs.keys === r.value) {
          prefs.keys = "line";
          setKeys("line");
          keyRadios.forEach(function (k) { k.checked = k.value === "line"; });
          changed = true;
        }
      });
      return changed;
    }

    // A saved palette the page does not offer counts as the default.
    if (swatches.length && offered.indexOf(prefs.palette) === -1) {
      prefs.palette = offered.indexOf(DEFAULT_PALETTE) === -1 ? offered[0] : DEFAULT_PALETTE;
      setPalette(prefs.palette);
    }
    var level = levelOf(prefs.palette);
    levelRadios.forEach(function (r) { r.checked = r.value === level; });
    swatches.forEach(function (r) { r.checked = r.value === prefs.palette; });
    showNote(level);

    varieties.forEach(function (r) {
      var lang = r.getAttribute("data-variety-lang");
      r.checked = (prefs.varieties[lang] || "all") === r.value;
      r.addEventListener("change", function () {
        if (!r.checked) return;
        if (r.value === "all") {
          delete prefs.varieties[lang];
        } else {
          prefs.varieties[lang] = r.value;
        }
        setVariety(lang, r.value);
        save(prefs);
      });
    });

    themes.forEach(function (r) {
      var pref = r.getAttribute("data-pref");
      if (pref !== "appearance" && pref !== "palette" && pref !== "access" && pref !== "order" && pref !== "keys") return;
      if (pref === "appearance") r.checked = prefs.appearance === r.value;
      if (pref === "order") r.checked = prefs.order === r.value;
      if (pref === "keys") r.checked = prefs.keys === r.value;
      r.addEventListener("change", function () {
        if (!r.checked) return;
        if (pref === "appearance") {
          prefs.appearance = r.value;
          setAppearance(r.value);
        } else if (pref === "order") {
          prefs.order = r.value;  // takes effect on the pages that follow; order.js reads it as each one loads
        } else if (pref === "keys") {
          prefs.keys = r.value;
          setKeys(r.value);
        } else if (pref === "palette") {
          prefs.palette = r.value;
          if (levelOf(r.value)) prefs.picks[levelOf(r.value)] = r.value;
          setPalette(r.value);
          fitKeys(levelOf(r.value));
        } else {
          // Choosing a level changes which schemes are listed, and returns to the one last picked there.
          prefs.palette = paletteFor(r.value);
          setPalette(prefs.palette);
          swatches.forEach(function (s) { s.checked = s.value === prefs.palette; });
          showNote(r.value);
          fitKeys(r.value);
        }
        save(prefs);
      });
    });

    if (fitKeys(levelOf(prefs.palette))) save(prefs);

    // Shown only now, so without the script there is never a control that does nothing.
    panel.hidden = false;
  });
})();
