// Tests for phrasebook/assets/search.js: the matching behind the search card. It needs no page, so it runs here.
// The page glue (the card sliding out, focus, the links) is checked in a real browser; see docs/TODO.md.
// Run from the repo root: node --test tests/
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "..", "phrasebook", "assets", "search.js"), "utf8");
// Run in this realm, not a sandbox, so objects it returns compare equal to the ones written here.
const exported = { exports: {} };
vm.runInThisContext(`(function (module) {${SOURCE}\n})`)(exported);
const { fold, base, score, prepareWords, prepareTopics, rank, pageOf } = exported.exports;

// Two made-up languages, "aa" and "bb", with one concept that has two regional forms and a word with a mark on it.
const DICTIONARY = {
  languages: ["aa", "bb"],
  entries: [
    { concept: "one", terms: { aa: [{ text: "Rain", varieties: [] }], bb: [{ text: "Glaw", varieties: [] }] },
      pages: [{ slug: "weather", href: "weather.html#sky.one", title: { aa: "Weather", bb: "Tywydd" } }] },
    { concept: "two", terms: { aa: [{ text: "Light rain", varieties: [] }], bb: [{ text: "Glaw ysgafn", varieties: [] }] },
      pages: [{ slug: "weather", href: "weather.html#sky.two", title: { aa: "Weather", bb: "Tywydd" } },
              { slug: "talk", href: "talk.html#say.two", title: { aa: "Talking", bb: "Siarad" } }] },
    { concept: "three", terms: { aa: [{ text: "Rainbow", varieties: [] }], bb: [{ text: "Enfys", varieties: [] }] },
      pages: [{ slug: "weather", href: "weather.html#sky.three", title: { aa: "Weather", bb: "Tywydd" } }] },
    { concept: "four", terms: { aa: [{ text: "Hello", varieties: [] }],
                                bb: [{ text: "Shwmae", varieties: ["south"] }, { text: "Sut mae", varieties: ["north"] }] },
      pages: [{ slug: "talk", href: "talk.html#say.four", title: { aa: "Talking", bb: "Siarad" } }] },
    { concept: "six", terms: { aa: [{ text: "Flooding", varieties: [] }], bb: [{ text: "Llifogydd", varieties: [] }] },
      also: { bb: ["lifogydd"] },
      pages: [{ slug: "weather", href: "weather.html#rain.six", title: { aa: "Weather", bb: "Tywydd" } }] },
    { concept: "five", terms: { aa: [{ text: "Wind", varieties: [] }], bb: [{ text: "Gwynt ŵy", varieties: [] }] },
      pages: [{ slug: "weather", href: "weather.html#wind.five", title: { aa: "Weather", bb: "Tywydd" } }] },
  ],
};
const LANGS = ["aa", "bb"];
const concepts = (items) => items.map((item) => item.entry.concept);

test("fold: normal form C and lower case, so equal text is equal whatever the capitals or the encoding", () => {
  assert.equal(fold("  RAIN ", "aa"), "rain");
  assert.equal(fold("é", "aa"), fold("é", "aa"));  // a letter and a mark equals the single letter
});

test("fold: a language tag the browser does not know falls back to plain lower-casing", () => {
  assert.equal(fold("RAIN", "not a tag"), "rain");
});

test("base: takes every mark off so a query typed without them can still match", () => {
  assert.equal(base("café", "aa"), "cafe");
  assert.equal(base("ŵŷ", "aa"), "wy");
  assert.equal(base("PLAIN", "aa"), "plain");
});

test("score: the whole text beats the start, which beats the start of a word, which beats the middle", () => {
  assert.equal(score("rain", "rain"), 0);
  assert.equal(score("rainbow", "rain"), 1);
  assert.equal(score("light rain", "rain"), 2);
  assert.equal(score("light-rain", "rain"), 2);
  assert.equal(score("training", "rain"), 3);
  assert.equal(score("sun", "rain"), null);
  assert.equal(score("rain", ""), null);
});

test("rank: the best match first, then the dictionary's own order", () => {
  const words = prepareWords(DICTIONARY, LANGS);
  assert.deepEqual(concepts(rank(words, "rain", LANGS)), ["one", "three", "two"]);
});

test("rank: it finds a word in either language of the pair", () => {
  const words = prepareWords(DICTIONARY, LANGS);
  assert.deepEqual(concepts(rank(words, "enfys", LANGS)), ["three"]);
  assert.deepEqual(concepts(rank(words, "ysgafn", LANGS)), ["two"]);
});

test("rank: capitals in the query never hide a match", () => {
  const words = prepareWords(DICTIONARY, LANGS);
  assert.deepEqual(concepts(rank(words, "GLAW", LANGS)), ["one", "two"]);
});

test("rank: every regional form can be found, not only the first", () => {
  const words = prepareWords(DICTIONARY, LANGS);
  assert.deepEqual(concepts(rank(words, "sut mae", LANGS)), ["four"]);
  assert.deepEqual(concepts(rank(words, "shwmae", LANGS)), ["four"]);
});

test("rank: a query without marks finds a word that has them, after any match that keeps them", () => {
  const words = prepareWords(DICTIONARY, LANGS);
  assert.deepEqual(concepts(rank(words, "wy", LANGS)), ["five"]);
  assert.deepEqual(concepts(rank(words, "gwynt wy", LANGS)), ["five"]);
  assert.deepEqual(concepts(rank(words, "gwynt ŵ", LANGS)), ["five"]);
});

test("rank: an empty or unmatched query finds nothing", () => {
  const words = prepareWords(DICTIONARY, LANGS);
  assert.deepEqual(rank(words, "", LANGS), []);
  assert.deepEqual(rank(words, "   ", LANGS), []);
  assert.deepEqual(rank(words, "zzzz", LANGS), []);
});

test("rank: only the languages asked for are searched", () => {
  const words = prepareWords(DICTIONARY, ["aa"]);
  assert.deepEqual(concepts(rank(words, "glaw", ["aa"])), []);
  assert.deepEqual(concepts(rank(words, "rain", ["aa"])), ["one", "three", "two"]);
});

test("topics: each page appears once, found by its title in either language, and keeps the order of the dictionary", () => {
  const topics = prepareTopics(DICTIONARY, LANGS);
  assert.deepEqual(topics.map((t) => t.page.slug), ["weather", "talk"]);
  assert.deepEqual(rank(topics, "siar", LANGS).map((t) => t.page.slug), ["talk"]);
  assert.deepEqual(rank(topics, "WEATH", LANGS).map((t) => t.page.slug), ["weather"]);
});

test("pageOf: the topic a link belongs to, without the row it points at", () => {
  assert.equal(pageOf("weather.html#sky.one"), "weather.html");
  assert.equal(pageOf("weather.html"), "weather.html");
});

test("rank: a form a word is also heard as finds the word, which is shown by its own terms", () => {
  const words = prepareWords(DICTIONARY, LANGS);
  assert.deepEqual(concepts(rank(words, "lifogydd", LANGS)), ["six"]);
  assert.deepEqual(concepts(rank(words, "llifogydd", LANGS)), ["six"]);
});
