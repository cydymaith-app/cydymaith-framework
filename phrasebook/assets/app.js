/* Phrasebook framework: remembers display preferences in this browser only.
   Preferences: light or dark appearance, a colour palette, and a regional form per language.
   Storage is localStorage on this device. There are no cookies, no network requests and no analytics.
   The site works without this script: it then follows the device's light or dark setting, uses the default
   palette, and shows every regional form equally. */
(function () {
  "use strict";

  var VERSION = 2;
  var root = document.documentElement;
  // Each site names its own storage (data-storage on <html>), so two phrasebooks on one origin, such as
  // different projects under one github.io name, never read or overwrite each other's choices.
  var NAME = /^[a-z0-9][a-z0-9._-]*$/;
  var site = root.getAttribute("data-storage");
  var KEY = (site && NAME.test(site) ? site : "phrasebook") + ":prefs";
  var LANG = /^[a-z]{2,3}(-[a-z0-9]+)*$/;
  var ID = /^[a-z][a-z0-9-]*$/;
  var APPEARANCES = ["system", "light", "dark"];
  var DEFAULT_PALETTE = "default";

  function empty() {
    return { v: VERSION, appearance: "system", palette: DEFAULT_PALETTE, varieties: {} };
  }

  // Keep only values we understand. Anything else in storage is ignored. Version 1 held only varieties
  // and is still read, so an earlier choice survives the upgrade.
  function clean(raw) {
    var out = empty();
    if (!raw || typeof raw !== "object" || (raw.v !== 1 && raw.v !== VERSION)) return out;
    if (APPEARANCES.indexOf(raw.appearance) !== -1) out.appearance = raw.appearance;
    if (typeof raw.palette === "string" && ID.test(raw.palette)) out.palette = raw.palette;
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

  var prefs = load();

  // Runs in the head, before the first paint, so there is no flash of the wrong theme or emphasis.
  setAppearance(prefs.appearance);
  setPalette(prefs.palette);
  Object.keys(prefs.varieties).forEach(function (lang) {
    setVariety(lang, prefs.varieties[lang]);
  });

  ready(function () {
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
    var palettes = themes.filter(function (r) { return r.getAttribute("data-pref") === "palette"; })
      .map(function (r) { return r.value; });
    if (palettes.indexOf(prefs.palette) === -1) {
      prefs.palette = DEFAULT_PALETTE;
      setPalette(DEFAULT_PALETTE);
    }

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
      if (pref !== "appearance" && pref !== "palette") return;
      r.checked = prefs[pref] === r.value;
      r.addEventListener("change", function () {
        if (!r.checked) return;
        prefs[pref] = r.value;
        if (pref === "appearance") {
          setAppearance(r.value);
        } else {
          setPalette(r.value);
        }
        save(prefs);
      });
    });

    // Shown only now, so without the script there is never a control that does nothing.
    panel.hidden = false;
  });
})();
