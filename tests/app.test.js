// Tests for phrasebook/assets/app.js. Run from the repo root:  node --test tests/
// The script is run in a sandbox with a minimal stand-in for the page and localStorage.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "..", "phrasebook", "assets", "app.js"), "utf8");
const KEY = "phrasebook:prefs";  // the default, used when the page names no storage

// A regional-form radio: makeRadio("cy", "north"). A theme radio: makeRadio(null, "dark", "appearance").
// A palette swatch also names its accessibility level: makeRadio(null, "red-green-safe", "palette", "safe").
function makeRadio(lang, value, pref, tier) {
  const listeners = {};
  return {
    value,
    lang,
    pref,
    tier,
    checked: false,
    getAttribute: (name) => (name === "data-variety-lang" ? lang : name === "data-pref" ? pref : name === "data-tier" ? tier || null : null),
    addEventListener: (type, fn) => { listeners[type] = fn; },
    fire(type) { listeners[type](); },
  };
}

// readyState "loading" means the script runs in the head, as it does on the real pages.
function run({ stored, storage, radios, langRadios, shareButtons, navigator, withPanel = true, readyState = "loading", site, key = KEY } = {}) {
  const attrs = {};
  const data = Object.assign({}, stored === undefined ? {} : { [key]: stored });
  const localStorage = storage || {
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => { data[k] = String(v); },
  };
  const everything = (selector) => [...(langRadios || []), ...(shareButtons || [])].filter((el) => selector.split(",").some((part) => el.matches(part.trim())));
  const panel = {
    hidden: true,
    querySelectorAll: (selector) => (radios || []).filter((r) => (selector.includes("data-variety-lang") ? r.lang : r.pref)),
  };
  const readyHandlers = [];
  const document = {
    readyState,
    documentElement: {
      getAttribute: (k) => (k === "data-storage" && site !== undefined ? site : null),
      setAttribute: (k, v) => { attrs[k] = v; },
      removeAttribute: (k) => { delete attrs[k]; },
    },
    addEventListener: (type, fn) => { if (type === "DOMContentLoaded") readyHandlers.push(fn); },
    getElementById: (id) => (id === "prefs" && withPanel ? panel : null),
  };
  if (langRadios || shareButtons) document.querySelectorAll = everything;
  vm.runInNewContext(SOURCE, { document, window: { localStorage, navigator } });
  return {
    attrs, data, panel,
    domReady() { readyHandlers.forEach((fn) => fn()); },
  };
}

const saved = (varieties, extra = {}) => JSON.stringify({ v: 4, varieties, ...extra });
const state = (varieties = {}, extra = {}) => ({ v: 4, appearance: "system", palette: "default", picks: {}, varieties, ...extra });

test("applies a saved variety to the page before it is painted", () => {
  const page = run({ stored: saved({ cy: "north" }) });
  assert.equal(page.attrs["data-v-cy"], "north");
});

test("'all' sets no attribute, so every form shows equally", () => {
  const page = run({ stored: saved({ cy: "all" }) });
  assert.deepEqual(page.attrs, {});
});

test("nothing is applied when nothing is stored", () => {
  assert.deepEqual(run().attrs, {});
});

test("corrupt, foreign or wrong-version data is ignored", () => {
  for (const stored of ["{not json", "null", "42", '"north"', JSON.stringify({ v: 5, varieties: { cy: "north" } }),
                        JSON.stringify({ v: 4 }), JSON.stringify({ v: 4, varieties: "north" })]) {
    assert.deepEqual(run({ stored }).attrs, {}, stored);
  }
});

test("values that are not plain identifiers are never applied", () => {
  const page = run({ stored: saved({
    cy: '"><script>alert(1)</script>',
    "X Y": "north",
    gd: ["north"],
    ga: 7,
    ar: "south",
  }) });
  assert.deepEqual(page.attrs, { "data-v-ar": "south" });
});

test("a storage that throws on read does not break the page", () => {
  const storage = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  const page = run({ storage });
  assert.deepEqual(page.attrs, {});
  assert.doesNotThrow(() => page.domReady());
});

test("the control is shown only once the script has run, with the saved choice ticked", () => {
  const radios = [makeRadio("cy", "all"), makeRadio("cy", "north"), makeRadio("cy", "south")];
  const page = run({ stored: saved({ cy: "south" }), radios });
  assert.equal(page.panel.hidden, true);
  page.domReady();
  assert.equal(page.panel.hidden, false);
  assert.deepEqual(radios.map((r) => r.checked), [false, false, true]);
});

test("choosing a variety updates the page and is remembered", () => {
  const radios = [makeRadio("cy", "all"), makeRadio("cy", "north"), makeRadio("cy", "south")];
  const page = run({ radios });
  page.domReady();
  assert.deepEqual(radios.map((r) => r.checked), [true, false, false]);
  radios[1].checked = true;
  radios[1].fire("change");
  assert.equal(page.attrs["data-v-cy"], "north");
  assert.deepEqual(JSON.parse(page.data[KEY]), state({ cy: "north" }));
  radios[0].checked = true;
  radios[0].fire("change");
  assert.deepEqual(page.attrs, {});
  assert.deepEqual(JSON.parse(page.data[KEY]), state());
});

test("choosing still works when saving fails", () => {
  const radios = [makeRadio("cy", "all"), makeRadio("cy", "north")];
  const storage = { getItem: () => null, setItem() { throw new Error("quota"); } };
  const page = run({ storage, radios });
  page.domReady();
  radios[1].checked = true;
  assert.doesNotThrow(() => radios[1].fire("change"));
  assert.equal(page.attrs["data-v-cy"], "north");
});

test("a saved variety that the page does not offer counts as all", () => {
  const radios = [makeRadio("cy", "all"), makeRadio("cy", "north")];
  const page = run({ stored: saved({ cy: "west" }), radios });
  assert.equal(page.attrs["data-v-cy"], "west"); // applied in the head, before the control exists
  page.domReady();
  assert.deepEqual(page.attrs, {});
  assert.deepEqual(radios.map((r) => r.checked), [true, false]);
});

test("each language keeps its own choice", () => {
  const radios = [makeRadio("cy", "all"), makeRadio("cy", "north"), makeRadio("gd", "all"), makeRadio("gd", "island")];
  const page = run({ radios });
  page.domReady();
  radios[1].checked = true; radios[1].fire("change");
  radios[3].checked = true; radios[3].fire("change");
  assert.deepEqual(page.attrs, { "data-v-cy": "north", "data-v-gd": "island" });
});

test("pages without the control are left alone", () => {
  const page = run({ withPanel: false });
  assert.doesNotThrow(() => page.domReady());
});

test("runs at once when the page has already loaded", () => {
  const radios = [makeRadio("cy", "all")];
  const page = run({ radios, readyState: "complete" });
  assert.equal(page.panel.hidden, false);
});

test("the script makes no network requests, sets no cookies and loads nothing", () => {
  for (const banned of ["fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket", "document.cookie", "http:", "https:", "import(", "eval("]) {
    assert.ok(!SOURCE.includes(banned), `app.js must not use ${banned}`);
  }
});

test("the storage key comes from the page, so two sites on one origin stay apart", () => {
  const a = run({ site: "site-a", key: "site-a:prefs", stored: saved({ cy: "north" }) });
  assert.equal(a.attrs["data-v-cy"], "north");
  const b = run({ site: "site-b", key: "site-a:prefs", stored: saved({ cy: "north" }) });
  assert.deepEqual(b.attrs, {}, "another site's saved choice is not read");
});

test("choosing is saved under the page's own key", () => {
  const radios = [makeRadio("cy", "all"), makeRadio("cy", "north")];
  const page = run({ site: "site-a", radios });
  page.domReady();
  radios[1].checked = true;
  radios[1].fire("change");
  assert.deepEqual(Object.keys(page.data), ["site-a:prefs"]);
});

test("an unsafe or missing storage name falls back to the default key", () => {
  for (const site of ['x"><script>', "Has Space", "", "UPPER", "-lead"]) {
    const page = run({ site, stored: saved({ cy: "south" }) });
    assert.equal(page.attrs["data-v-cy"], "south", JSON.stringify(site));
  }
});

// ---- appearance and palette

test("a saved appearance and palette are applied before the page is painted", () => {
  const page = run({ stored: saved({}, { appearance: "dark", palette: "high-contrast" }) });
  assert.deepEqual(page.attrs, { "data-theme": "dark", "data-palette": "high-contrast" });
});

test("'system' and the default palette set no attribute, so the stylesheet follows the device", () => {
  const page = run({ stored: saved({}, { appearance: "system", palette: "default" }) });
  assert.deepEqual(page.attrs, {});
});

test("an appearance that is not light, dark or system is ignored", () => {
  for (const appearance of ["blue", "", 7, null, ["dark"], '"><script>']) {
    assert.deepEqual(run({ stored: saved({}, { appearance }) }).attrs, {}, JSON.stringify(appearance));
  }
});

test("a palette that is not a plain identifier is never applied", () => {
  for (const palette of ['x"><script>alert(1)</script>', "Has Space", "UPPER", "-lead", 7, ["a"], null, ""]) {
    assert.deepEqual(run({ stored: saved({}, { palette }) }).attrs, {}, JSON.stringify(palette));
  }
});

test("version 1 data, which held only regional forms, is still read", () => {
  const page = run({ stored: JSON.stringify({ v: 1, varieties: { cy: "north" } }) });
  assert.deepEqual(page.attrs, { "data-v-cy": "north" });
});

test("version 2 data, which had no remembered palette picks, is still read", () => {
  const page = run({ stored: JSON.stringify({ v: 2, appearance: "dark", palette: "high-contrast", varieties: { cy: "south" } }) });
  assert.deepEqual(page.attrs, { "data-theme": "dark", "data-palette": "high-contrast", "data-v-cy": "south" });
});

test("the theme controls show the saved choice", () => {
  const radios = [makeRadio(null, "system", "appearance"), makeRadio(null, "light", "appearance"), makeRadio(null, "dark", "appearance"),
                  makeRadio(null, "default", "palette"), makeRadio(null, "high-contrast", "palette")];
  const page = run({ stored: saved({}, { appearance: "light", palette: "high-contrast" }), radios });
  page.domReady();
  assert.deepEqual(radios.map((r) => r.checked), [false, true, false, false, true]);
  assert.equal(page.panel.hidden, false);
});

test("choosing an appearance updates the page and is remembered", () => {
  const radios = [makeRadio(null, "system", "appearance"), makeRadio(null, "dark", "appearance")];
  const page = run({ radios });
  page.domReady();
  radios[1].checked = true;
  radios[1].fire("change");
  assert.equal(page.attrs["data-theme"], "dark");
  assert.deepEqual(JSON.parse(page.data[KEY]), state({}, { appearance: "dark" }));
  radios[0].checked = true;
  radios[0].fire("change");
  assert.deepEqual(page.attrs, {});
  assert.deepEqual(JSON.parse(page.data[KEY]), state());
});

test("choosing a palette updates the page, and the default removes the attribute", () => {
  const radios = [makeRadio(null, "default", "palette"), makeRadio(null, "red-green-safe", "palette")];
  const page = run({ radios });
  page.domReady();
  radios[1].checked = true;
  radios[1].fire("change");
  assert.equal(page.attrs["data-palette"], "red-green-safe");
  assert.deepEqual(JSON.parse(page.data[KEY]), state({}, { palette: "red-green-safe" }));
  radios[0].checked = true;
  radios[0].fire("change");
  assert.deepEqual(page.attrs, {});
});

test("a saved palette the page does not offer falls back to the default", () => {
  const radios = [makeRadio(null, "default", "palette"), makeRadio(null, "high-contrast", "palette")];
  const page = run({ stored: saved({}, { palette: "retired-palette" }), radios });
  assert.equal(page.attrs["data-palette"], "retired-palette"); // applied in the head, before the control exists
  page.domReady();
  assert.deepEqual(page.attrs, {});
  assert.deepEqual(radios.map((r) => r.checked), [true, false]);
});

test("appearance, palette and regional forms are chosen independently", () => {
  const radios = [makeRadio("cy", "all"), makeRadio("cy", "south"), makeRadio(null, "light", "appearance"), makeRadio(null, "high-contrast", "palette")];
  const page = run({ radios });
  page.domReady();
  for (const i of [1, 2, 3]) { radios[i].checked = true; radios[i].fire("change"); }
  assert.deepEqual(page.attrs, { "data-v-cy": "south", "data-theme": "light", "data-palette": "high-contrast" });
  assert.deepEqual(JSON.parse(page.data[KEY]), state({ cy: "south" }, { appearance: "light", palette: "high-contrast" }));
});

test("choosing a theme still works when saving fails", () => {
  const radios = [makeRadio(null, "system", "appearance"), makeRadio(null, "dark", "appearance")];
  const storage = { getItem: () => null, setItem() { throw new Error("quota"); } };
  const page = run({ storage, radios });
  page.domReady();
  radios[1].checked = true;
  assert.doesNotThrow(() => radios[1].fire("change"));
  assert.equal(page.attrs["data-theme"], "dark");
});

// ---- accessibility levels: standard, safe colours, high contrast

const levelPage = (stored) => {
  const radios = {
    levels: [makeRadio(null, "standard", "access"), makeRadio(null, "safe", "access"), makeRadio(null, "high", "access")],
    palettes: [makeRadio(null, "default", "palette", "standard"), makeRadio(null, "yellow-green", "palette", "standard"),
               makeRadio(null, "red-green-safe", "palette", "safe"), makeRadio(null, "blue-yellow-safe", "palette", "safe"),
               makeRadio(null, "high-contrast", "palette", "high")],
  };
  const page = run({ stored, radios: [...radios.levels, ...radios.palettes] });
  page.domReady();
  return { page, ...radios };
};
const ticked = (list) => list.filter((r) => r.checked).map((r) => r.value);

test("the level shown is the level of the saved palette", () => {
  const { levels, palettes } = levelPage(saved({}, { palette: "red-green-safe" }));
  assert.deepEqual(ticked(levels), ["safe"]);
  assert.deepEqual(ticked(palettes), ["red-green-safe"]);
});

test("with nothing saved the level is standard and the palette is the default", () => {
  const { levels, palettes } = levelPage();
  assert.deepEqual(ticked(levels), ["standard"]);
  assert.deepEqual(ticked(palettes), ["default"]);
});

test("choosing a level selects the first scheme in it, and changes no attribute but the palette", () => {
  const { page, levels, palettes } = levelPage();
  levels[2].checked = true;
  levels[2].fire("change");
  assert.equal(page.attrs["data-palette"], "high-contrast");
  assert.deepEqual(ticked(palettes), ["high-contrast"]);
  assert.deepEqual(JSON.parse(page.data[KEY]).palette, "high-contrast");
  levels[0].checked = true;
  levels[0].fire("change");
  assert.deepEqual(page.attrs, {});
  assert.deepEqual(ticked(palettes), ["default"]);
});

test("each level remembers the scheme last picked in it", () => {
  const { page, levels, palettes } = levelPage();
  palettes[3].checked = true;  // blue-yellow-safe is not offered until the level is safe, but the pick is recorded by its tier
  palettes[3].fire("change");
  assert.deepEqual(JSON.parse(page.data[KEY]).picks, { safe: "blue-yellow-safe" });
  levels[0].checked = true;
  levels[0].fire("change");
  assert.equal(page.attrs["data-palette"], undefined);
  levels[1].checked = true;
  levels[1].fire("change");
  assert.equal(page.attrs["data-palette"], "blue-yellow-safe");
  assert.deepEqual(ticked(palettes), ["blue-yellow-safe"]);
});

test("a remembered pick that the page no longer offers in that level is ignored", () => {
  const { page, levels } = levelPage(saved({}, { picks: { safe: "retired-palette", high: "red-green-safe" } }));
  levels[1].checked = true;
  levels[1].fire("change");
  assert.equal(page.attrs["data-palette"], "red-green-safe");  // the first scheme of the safe level
  levels[2].checked = true;
  levels[2].fire("change");
  assert.equal(page.attrs["data-palette"], "high-contrast");  // a pick from the wrong level does not count
});

test("remembered picks that are not plain identifiers are never kept", () => {
  const { page, levels } = levelPage(saved({}, { picks: { safe: '"><script>', high: 7, standard: ["a"], other: "x" } }));
  levels[1].checked = true;
  levels[1].fire("change");
  assert.deepEqual(JSON.parse(page.data[KEY]).picks, {});
});

test("a level with one scheme shows the note, and a level with several hides it", () => {
  const note = { hidden: true };
  const radios = [makeRadio(null, "standard", "access"), makeRadio(null, "high", "access"),
                  makeRadio(null, "default", "palette", "standard"), makeRadio(null, "yellow-green", "palette", "standard"),
                  makeRadio(null, "high-contrast", "palette", "high")];
  const page = run({ radios });
  page.panel.querySelector = (selector) => (selector === ".colours-only" ? note : null);
  page.domReady();
  assert.equal(note.hidden, true);
  radios[1].checked = true;
  radios[1].fire("change");
  assert.equal(note.hidden, false);
  radios[0].checked = true;
  radios[0].fire("change");
  assert.equal(note.hidden, true);
});

// ---- the Cy|En toggles remember their language

// An element stand-in for the toggles and the Share button: matches() answers the selectors the script uses.
function makeToggle(className, value) {
  const listeners = {};
  return {
    value,
    checked: false,
    matches: (selector) => selector === "input." + className,
    addEventListener: (type, fn) => { listeners[type] = fn; },
    fire(type) { listeners[type](); },
  };
}

test("version 3 data, which had no remembered language, is still read", () => {
  const page = run({ stored: JSON.stringify({ v: 3, appearance: "dark", palette: "default", picks: {}, varieties: {} }) });
  assert.deepEqual(page.attrs, { "data-theme": "dark" });
});

test("the saved language is ticked on every toggle, Settings and About alike", () => {
  const settings = [makeToggle("lang-radio", "cy"), makeToggle("lang-radio", "en")];
  const about = [makeToggle("about-radio", "cy"), makeToggle("about-radio", "en")];
  const page = run({ stored: saved({}, { lang: "en" }), langRadios: [...settings, ...about] });
  page.domReady();
  assert.deepEqual([...settings, ...about].map((r) => r.checked), [false, true, false, true]);
});

test("a language the page does not offer changes nothing", () => {
  const radios = [makeToggle("lang-radio", "cy"), makeToggle("lang-radio", "en")];
  const page = run({ stored: saved({}, { lang: "fr" }), langRadios: radios });
  page.domReady();
  assert.deepEqual(radios.map((r) => r.checked), [false, false]);
});

test("choosing a language is remembered, with the other choices kept", () => {
  const radios = [makeToggle("about-radio", "cy"), makeToggle("about-radio", "en")];
  const page = run({ stored: saved({}, { appearance: "dark" }), langRadios: radios });
  page.domReady();
  radios[1].checked = true;
  radios[1].fire("change");
  assert.deepEqual(JSON.parse(page.data[KEY]), state({}, { appearance: "dark", lang: "en" }));
});

test("a language that is not a plain language tag is never kept", () => {
  for (const lang of ['x"><script>', "UPPER", 7, ["cy"], null, ""]) {
    const radios = [makeToggle("lang-radio", "cy")];
    const page = run({ stored: saved({}, { lang }), langRadios: radios });
    page.domReady();
    assert.equal(radios[0].checked, false, JSON.stringify(lang));
  }
});

// ---- the Share button

function makeButton(url) {
  const listeners = {};
  const status = { textContent: "" };
  return {
    hidden: true,
    status,
    matches: (selector) => selector === "button.share",
    getAttribute: (name) => (name === "data-url" ? url : name === "data-copied" ? "Link copied" : null),
    parentNode: { querySelector: () => status },
    addEventListener: (type, fn) => { listeners[type] = fn; },
    click() { listeners.click(); },
  };
}

test("the Share button stays hidden when the browser can neither share nor copy", () => {
  const button = makeButton("https://example.org/");
  run({ shareButtons: [button], navigator: {} }).domReady();
  assert.equal(button.hidden, true);
});

test("the Share button shows and uses the browser's share sheet when there is one", async () => {
  const shared = [];
  const button = makeButton("https://example.org/");
  run({ shareButtons: [button], navigator: { share: (data) => { shared.push(data); return Promise.resolve(); } } }).domReady();
  assert.equal(button.hidden, false);
  button.click();
  assert.equal(JSON.stringify(shared), JSON.stringify([{ url: "https://example.org/" }]));
});

test("without a share sheet the Share button copies the address and says so", async () => {
  const copied = [];
  const button = makeButton("https://example.org/");
  run({ shareButtons: [button], navigator: { clipboard: { writeText: (t) => { copied.push(t); return Promise.resolve(); } } } }).domReady();
  assert.equal(button.hidden, false);
  button.click();
  await Promise.resolve();
  await Promise.resolve();
  assert.deepEqual(copied, ["https://example.org/"]);
  assert.equal(button.status.textContent, "Link copied");
});
