/* Phrasebook framework: search, and the dictionary lookup card.
   The search button at the top of the rail opens a card that slides out beside it. As the person types, the card lists the
   words and phrases that match, each with its translation, and under each one the topics it appears in, which are links.
   The words come from dictionary.json, which every build writes from the packs, so a new page is searchable with no extra
   step. It is read once, when the card is first opened, and the service worker has it cached, so search works offline. The
   script makes no other request, sets no cookies and stores nothing. Without it the button stays hidden, so there is never
   a control that does nothing.

   Matching follows the language of each term: text is put in normal form C and lower-cased by that language's own rules
   (never ASCII lower-casing), so a capital letter in the query never hides a match. A second pass ignores accents and
   other marks, so a query typed without them still finds a word that has them, and ranks below a match that keeps them. */
(function () {
  "use strict";

  var MAX_WORDS = 40;  // the most words listed at once
  var MAX_TOPICS = 8;  // the most topics listed at once
  var MARK_PENALTY = 10;  // a match that had to ignore marks ranks after every match that did not

  // ---- the matching, with no page in sight so it can be tested on its own

  function lower(text, lang) {
    try {
      return text.toLocaleLowerCase(lang);
    } catch (err) {  // not a language tag this browser knows
      return text.toLowerCase();
    }
  }

  // Normal form C, lower case in the language's own way, with no leading or trailing space. Marks are kept.
  function fold(text, lang) {
    return lower(String(text).normalize("NFC"), lang).trim();
  }

  // The same, with every combining mark taken off: the letters only.
  function base(text, lang) {
    return lower(String(text).normalize("NFD").replace(/\p{M}+/gu, "").normalize("NFC"), lang).trim();
  }

  // How well `query` matches `text` (both already folded): 0 is the whole text, 1 the start of it, 2 the start of a word
  // in it, 3 anywhere in it, null no match.
  function score(text, query) {
    if (!query) return null;
    if (text === query) return 0;
    var at = text.indexOf(query);
    if (at === -1) return null;
    if (at === 0) return 1;
    while (at !== -1) {
      if (!/[\p{L}\p{N}]/u.test(text.charAt(at - 1))) return 2;
      at = text.indexOf(query, at + 1);
    }
    return 3;
  }

  // One term against one query, keeping marks first and ignoring them second.
  function scoreTerm(key, query) {
    var exact = score(key.fold, query.fold);
    if (exact !== null) return exact;
    var loose = score(key.base, query.base);
    return loose === null ? null : loose + MARK_PENALTY;
  }

  // Keys for one text in each language it is written in: [{lang, fold, base}].
  function keysOf(texts, langs) {
    var keys = [];
    langs.forEach(function (lang) {
      (texts[lang] || []).forEach(function (text) {
        keys.push({ lang: lang, fold: fold(text, lang), base: base(text, lang) });
      });
    });
    return keys;
  }

  // The words: one item for each dictionary entry, searchable in the languages given.
  function prepareWords(dictionary, langs) {
    return dictionary.entries.map(function (entry, order) {
      var texts = {};
      langs.forEach(function (lang) {
        texts[lang] = (entry.terms[lang] || []).map(function (t) { return t.text; })
          .concat((entry.also && entry.also[lang]) || []);
      });
      return { order: order, entry: entry, keys: keysOf(texts, langs) };
    });
  }

  // The topics: each page that holds any word, once, searchable by its title in the languages given.
  function prepareTopics(dictionary, langs) {
    var seen = {};
    var topics = [];
    dictionary.entries.forEach(function (entry) {
      entry.pages.forEach(function (page) {
        if (seen[page.slug]) return;
        seen[page.slug] = true;
        var texts = {};
        langs.forEach(function (lang) { texts[lang] = page.title[lang] ? [page.title[lang]] : []; });
        topics.push({ order: topics.length, page: page, keys: keysOf(texts, langs) });
      });
    });
    return topics;
  }

  // The items that match `query`, best first, then in the dictionary's order.
  function rank(items, query, langs) {
    var queries = {};
    langs.forEach(function (lang) { queries[lang] = { fold: fold(query, lang), base: base(query, lang) }; });
    var hits = [];
    items.forEach(function (item) {
      var best = null;
      item.keys.forEach(function (key) {
        var s = scoreTerm(key, queries[key.lang]);
        if (s !== null && (best === null || s < best)) best = s;
      });
      if (best !== null) hits.push({ item: item, rank: best });
    });
    hits.sort(function (a, b) { return a.rank - b.rank || a.item.order - b.item.order; });
    return hits.map(function (h) { return h.item; });
  }

  // The page's file name without its fragment: the topic a link belongs to.
  function pageOf(href) {
    return String(href).split("#")[0];
  }

  // Split ranked words into those found on the pages being browsed (`scope`, a list of page file names) and the rest, each
  // keeping its order. A word found there lists that page first, so its link lands on the row in front of the person.
  function partition(items, scope) {
    var here = [];
    var other = [];
    items.forEach(function (item) {
      var pages = item.entry.pages;
      var near = pages.filter(function (p) { return scope.indexOf(pageOf(p.href)) !== -1; });
      if (!near.length) {
        other.push(item);
        return;
      }
      var rest = pages.filter(function (p) { return near.indexOf(p) === -1; });
      here.push({ order: item.order, keys: item.keys, entry: Object.assign({}, item.entry, { pages: near.concat(rest) }) });
    });
    return { here: here, other: other };
  }

  var api = { fold: fold, base: base, score: score, prepareWords: prepareWords, prepareTopics: prepareTopics,
              rank: rank, pageOf: pageOf, partition: partition, MAX_WORDS: MAX_WORDS, MAX_TOPICS: MAX_TOPICS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  // ---- the page

  var card = document.getElementById("search-card");
  var button = document.getElementById("search-button");
  var input = document.getElementById("search-input");
  var status = document.getElementById("search-status");
  var results = document.getElementById("search-results");
  var topicList = document.getElementById("search-pages");
  if (!card || !button || !input || !status || !results || !topicList) return;
  var layer = card.parentNode;
  var heading = card.querySelector(".search-topics");
  var closer = card.querySelector(".search-close");
  var clearer = card.querySelector(".search-clear");

  var pair;
  try {
    pair = JSON.parse(card.getAttribute("data-pair"));
  } catch (err) {
    return;
  }
  if (!Array.isArray(pair) || pair.length < 2) return;
  var langs = pair.map(function (p) { return p[0]; });
  var dirs = {};
  pair.forEach(function (p) { dirs[p[0]] = p[1]; });

  var scope = [];
  try {
    scope = JSON.parse(card.getAttribute("data-scope") || "[]");
  } catch (err) {
    scope = [];
  }
  if (!Array.isArray(scope)) scope = [];

  var words = null;    // prepared when the dictionary arrives
  var topics = null;
  var loading = false;
  var failed = false;
  var isOpen = false;

  function text(key) { return card.getAttribute("data-" + key) || ""; }

  function make(tag, cls, content) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (content !== undefined) node.textContent = content;
    return node;
  }

  // Text in one of the pair's languages, marked with its language and direction.
  function spoken(content, lang, cls) {
    var node = make("span", cls, content);
    node.setAttribute("lang", lang);
    node.setAttribute("dir", dirs[lang] || "auto");
    return node;
  }

  function forms(entry, lang) {
    return (entry.terms[lang] || []).map(function (t) { return t.text; }).join(" / ");
  }

  function pairInto(parent, first, second) {
    if (first) parent.appendChild(spoken(first, langs[0], "l1"));
    if (first && second) parent.appendChild(document.createTextNode(" "));
    if (second) parent.appendChild(spoken(second, langs[1], "l2"));
  }

  function renderWord(item) {
    var entry = item.entry;
    var li = make("li", "search-result");
    var link = make("a", "search-term");
    link.href = entry.pages[0].href;
    pairInto(link, forms(entry, langs[0]), forms(entry, langs[1]));
    li.appendChild(link);
    var sub = make("ul", "search-sub");
    entry.pages.forEach(function (page) {
      var row = make("li");
      var a = make("a");
      a.href = page.href;
      pairInto(a, page.title[langs[0]], page.title[langs[1]]);
      row.appendChild(a);
      sub.appendChild(row);
    });
    li.appendChild(sub);
    return li;
  }

  function renderTopic(item) {
    var li = make("li", "search-result");
    var link = make("a", "search-term");
    link.href = pageOf(item.page.href);
    pairInto(link, item.page.title[langs[0]], item.page.title[langs[1]]);
    li.appendChild(link);
    return li;
  }

  function clear(list) {
    while (list.firstChild) list.removeChild(list.firstChild);
  }

  function render() {
    clear(results);
    clear(topicList);
    heading.hidden = true;
    var query = input.value;
    if (clearer) clearer.hidden = !query;
    if (failed) {
      status.textContent = text("error");
      return;
    }
    if (!query.trim() || !words) {
      status.textContent = text("hint");
      return;
    }
    var split = partition(rank(words, query, langs), scope);
    split.here = split.here.slice(0, MAX_WORDS);
    split.other = split.other.slice(0, MAX_WORDS - split.here.length);
    var found = split.here.concat(split.other);
    var foundTopics = rank(topics, query, langs).slice(0, MAX_TOPICS);
    if (!found.length && !foundTopics.length) {
      status.textContent = text("none");
      return;
    }
    status.textContent = "";
    split.here.forEach(function (item) { results.appendChild(renderWord(item)); });
    if (split.here.length && split.other.length) results.appendChild(make("li", "search-divider", text("other")));
    split.other.forEach(function (item) { results.appendChild(renderWord(item)); });
    foundTopics.forEach(function (item) { topicList.appendChild(renderTopic(item)); });
    heading.hidden = foundTopics.length === 0;
  }

  // The dictionary is read once, the first time the card opens.
  function load() {
    if (words || loading || failed) return;
    loading = true;
    fetch(text("dictionary")).then(function (response) {
      if (!response.ok) throw new Error(String(response.status));
      return response.json();
    }).then(function (dictionary) {
      words = prepareWords(dictionary, langs);
      topics = prepareTopics(dictionary, langs);
      loading = false;
      render();
    }).catch(function () {
      loading = false;
      failed = true;
      render();
    });
  }

  function open() {
    if (isOpen) return;
    isOpen = true;
    card.removeAttribute("data-instant");
    card.removeAttribute("inert");
    card.setAttribute("data-open", "");
    button.setAttribute("aria-expanded", "true");
    render();
    load();
    input.focus();
  }

  // Slide away, or vanish at once (`instant`) when the page is about to change, so the page that leaves has no card on it.
  function close(returnFocus, instant) {
    if (!isOpen) return;
    isOpen = false;
    if (instant) card.setAttribute("data-instant", "");
    card.removeAttribute("data-open");
    card.setAttribute("inert", "");
    button.setAttribute("aria-expanded", "false");
    if (returnFocus) button.focus();
  }

  layer.hidden = false;
  button.hidden = false;
  render();

  button.addEventListener("click", function () {
    if (isOpen) close(true, false); else open();
  });
  closer.addEventListener("click", function () { close(true, false); });
  if (clearer) clearer.addEventListener("click", function () { input.value = ""; render(); input.focus(); });
  input.addEventListener("input", render);

  // A plain click on a result leaves for that page, with the card gone at once.
  card.addEventListener("click", function (event) {
    var link = event.target && event.target.closest ? event.target.closest("a") : null;
    if (link && !event.defaultPrevented) close(false, true);
  });

  // Tapping anywhere else dismisses the card.
  document.addEventListener("click", function (event) {
    if (!isOpen || card.contains(event.target) || button.contains(event.target)) return;
    close(false, false);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && isOpen) {
      event.preventDefault();
      close(true, false);
      return;
    }
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    var target = event.target;
    var typing = target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName);
    if (event.key === "/" && !typing && !isOpen) {
      event.preventDefault();
      open();
      return;
    }
    if (!card.contains(target)) return;
    var links = Array.prototype.slice.call(card.querySelectorAll(".search-results a, .search-pages a"));
    if (event.key === "Enter" && target === input && links.length) {
      event.preventDefault();
      links[0].click();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      var at = links.indexOf(document.activeElement);
      var to = event.key === "ArrowDown" ? at + 1 : at - 1;
      if (event.key === "ArrowUp" && at <= 0) {
        event.preventDefault();
        input.focus();
      } else if (links[to]) {
        event.preventDefault();
        links[to].focus();
      }
    }
  });

  // Coming back from the browser's own cache must not show the card open.
  window.addEventListener("pageshow", function (event) { if (event.persisted) close(false, true); });
})();
