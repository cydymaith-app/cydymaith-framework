/* Phrasebook framework: help in place.
   A question-mark button in the rail turns help on and off. A page that has help icons (links to the help book, marked
   data-help="<chapter>#<feature>") carries the button, hidden, and a shut card for the sheet. The stylesheet hides the icons until
   the page says it is helping: this script sets data-helping on the document element and the icons show. Pressing the button
   again, or Escape, puts the page back as it was.
   Pressing an icon opens a sheet over the page: "What's this?" first, then "Report a problem" where the site has an address.
   "What's this?" reads the help book's own page for that feature (the service worker has it cached, so it works offline) and shows
   just that feature's text, in each language the chapter is written in; it makes no other request. "Report a problem" shows the
   email it would write: what the person types, then a few lines the app adds (the page, the feature, when the app was built and
   the languages), never more than 256 characters. It opens the person's own mail app, or copies the text. The app sends nothing.
   Nothing is stored, so every page begins plain. Without this script the button and the card stay hidden, the icons never show,
   and the help book is still reached from About; a revealed icon is an ordinary link to its chapter. */
(function () {
  "use strict";

  var MARK = "data-helping";
  var MAX_CONTEXT = 256;  // the most the app adds to a report: longer and the app is getting too complex
  var NAME = /^[a-z][a-z0-9-]*$/;
  var PAGE = /^help-[a-z][a-z0-9-]*\.html$/;

  // ---- the moves, with no page in sight so they can be tested on their own

  // Turn the mode on or off: the mark on the document element, and the state of the button.
  function apply(root, button, on) {
    if (on) root.setAttribute(MARK, "");
    else root.removeAttribute(MARK);
    button.setAttribute("aria-pressed", on ? "true" : "false");
    return on;
  }

  // The other state: on if it is off, off if it is on.
  function toggle(root, button) {
    return apply(root, button, !root.hasAttribute(MARK));
  }

  // "<chapter>#<feature>" as an icon names it, or null for anything else.
  function anchor(text) {
    var parts = String(text || "").split("#");
    if (parts.length !== 2 || !NAME.test(parts[0]) || !NAME.test(parts[1])) return null;
    return { chapter: parts[0], feature: parts[1], page: "help-" + parts[0] + ".html" };
  }

  // Whole lines that fit in `max` characters, most important first. If even the first does not fit it is cut and marked.
  function fit(lines, max) {
    var out = [];
    var length = 0;
    for (var i = 0; i < lines.length; i++) {
      var line = String(lines[i]);
      var cost = line.length + (out.length ? 1 : 0);
      if (length + cost > max) {
        if (!out.length) out.push(line.slice(0, Math.max(0, max - 1)) + "…");
        break;
      }
      out.push(line);
      length += cost;
    }
    return out.join("\n");
  }

  // The lines the app adds to a report, most important first, never more than `max` characters in all.
  function context(info, max) {
    var lines = [];
    if (info.page) lines.push("Page: " + info.page);
    if (info.help) lines.push("Help: " + info.help);
    if (info.built) lines.push("Built: " + info.built);
    var languages = [info.pair, info.dir && info.dir !== "ltr" ? info.dir : ""].filter(Boolean).join(" ");
    if (languages) lines.push("Languages: " + languages);
    return fit(lines, max || MAX_CONTEXT);
  }

  // The person's words, then the lines the app adds.
  function message(words, added) {
    var said = String(words || "").trim();
    return said ? said + "\n\n" + added : added;
  }

  // The link that opens the person's own mail app. Nothing is sent by this script.
  function mailto(address, subject, body) {
    return "mailto:" + address + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(body);
  }

  // What is copied when there is no mail app: the whole message, with whom it is for and what it is about.
  function copied(address, subject, body) {
    return "To: " + address + "\nSubject: " + subject + "\n\n" + body;
  }

  // The sections of a parsed help page that explain one feature: [{lang, node}], one per language the chapter is written in.
  function sections(doc, feature) {
    var found = [];
    var list = doc.querySelectorAll('[data-feature="' + feature + '"]');
    for (var i = 0; i < list.length; i++) {
      var article = list[i].closest ? list[i].closest("article") : null;
      var lang = (article && article.getAttribute("lang")) || list[i].getAttribute("lang") || "";
      found.push({ lang: lang, node: list[i] });
    }
    return found;
  }

  // Which of the pair's two languages a section of the book is written in: 1 (the first), 2 (the second), or 0 when it is in
  // neither (the book falls back to English), in which case it is always shown. `lang` empty means the language of the page.
  function place(lang, pair, page) {
    var wanted = lang || page;
    var at = String(pair || "").split(">").indexOf(wanted);
    return at === -1 ? 0 : at + 1;
  }

  // Show one message of a status line and hide the others; no name hides them all.
  function say(line, name) {
    var all = line.querySelectorAll("[data-msg]");
    for (var i = 0; i < all.length; i++) all[i].hidden = all[i].getAttribute("data-msg") !== name;
  }

  var api = {
    place: place,
    say: say,
    apply: apply, toggle: toggle, anchor: anchor, fit: fit, context: context, message: message, mailto: mailto,
    copied: copied, sections: sections, MAX_CONTEXT: MAX_CONTEXT
  };

  // ---- the page

  function init(doc) {
    var button = typeof doc.getElementById === "function" ? doc.getElementById("help-toggle") : null;
    if (!button) return;
    var root = doc.documentElement;
    button.hidden = false;
    button.addEventListener("click", function () { toggle(root, button); });

    var card = doc.getElementById("help-card");
    var layer = card ? card.parentNode : null;
    var sheet = null;  // the icon that opened the card, and what it names
    var opener = null;

    function view(name) {
      var views = card.querySelectorAll("[data-view]");
      for (var i = 0; i < views.length; i++) views[i].hidden = views[i].getAttribute("data-view") !== name;
      var first = card.querySelector('[data-view="' + name + '"] button, [data-view="' + name + '"] textarea');
      if (first) first.focus();
    }

    function behind(inert) {
      var kids = doc.querySelectorAll(".app > *");
      for (var i = 0; i < kids.length; i++) {
        if (kids[i] === layer) continue;
        if (inert) kids[i].setAttribute("inert", "");
        else kids[i].removeAttribute("inert");
      }
    }

    function isOpen() { return card && !layer.hidden; }

    function close(returnFocus) {
      if (!isOpen()) return;
      layer.hidden = true;
      card.setAttribute("inert", "");
      behind(false);
      if (returnFocus && opener && typeof opener.focus === "function") opener.focus();
      sheet = null;
    }

    function open(icon, named) {
      sheet = named;
      opener = icon;
      card.querySelector("[data-title]").textContent = icon.getAttribute("data-title") || "";
      layer.hidden = false;
      card.removeAttribute("inert");
      behind(true);
      view("sheet");
    }

    function show(name) { view(name); }

    // ---- What's this?
    function loadHelp() {
      var body = card.querySelector("[data-help-body]");
      var more = card.querySelector("[data-help-more]");
      var status = card.querySelector("[data-help-status]");
      more.setAttribute("href", sheet.page + "#" + sheet.feature);
      body.textContent = "";
      say(status, "loading");
      show("help");
      if (!PAGE.test(sheet.page) || typeof fetch !== "function" || typeof DOMParser !== "function") {
        say(status, "failed");
        return;
      }
      var wanted = sheet;
      fetch(sheet.page, { credentials: "same-origin" }).then(function (response) {
        if (!response.ok) throw new Error("status " + response.status);
        return response.text();
      }).then(function (text) {
        if (sheet !== wanted) return;
        var parsed = new DOMParser().parseFromString(text, "text/html");
        var found = sections(parsed, wanted.feature);
        if (!found.length) throw new Error("no section");
        found.forEach(function (one) {
          var copy = doc.importNode(one.node, true);
          copy.removeAttribute("id");
          copy.removeAttribute("data-feature");
          var heading = copy.querySelector("h2");
          if (heading) heading.remove();
          var wrap = doc.createElement("div");
          // One language of the pair at a time, as the toggle chooses (the stylesheet hides the other); a section in neither stays.
          var n = place(one.lang, card.getAttribute("data-pair"), root.getAttribute("lang"));
          wrap.className = n ? "t help-text" : "help-text";  // the stylesheet hides every .t that is not the chosen language
          if (n) wrap.setAttribute("data-n", String(n));
          if (one.lang) wrap.setAttribute("lang", one.lang);
          wrap.appendChild(copy);
          body.appendChild(wrap);
        });
        say(status, null);
      }).catch(function () {
        if (sheet === wanted) say(status, "failed");
      });
    }

    // ---- Report a problem
    function address() {
      var user = card.getAttribute("data-contact-user");
      var host = card.getAttribute("data-contact-host");
      return user && host ? user + "@" + host : "";
    }

    function added() {
      var file = (doc.location && doc.location.pathname ? doc.location.pathname.split("/").pop() : "") || "index.html";
      return context({
        page: file,
        help: sheet ? sheet.chapter + "#" + sheet.feature : "",
        built: card.getAttribute("data-built"),
        pair: card.getAttribute("data-pair"),
        dir: root.getAttribute("dir") || "ltr"
      });
    }

    function preview() {
      var words = card.querySelector("[data-report-words]");
      var shown = card.querySelector("[data-report-added]");
      var link = card.querySelector("[data-report-mail]");
      var text = message(words.value, added());
      shown.value = added();
      if (link) link.setAttribute("href", mailto(address(), card.getAttribute("data-subject"), text));
    }

    function report() {
      var words = card.querySelector("[data-report-words]");
      say(card.querySelector("[data-report-status]"), null);
      preview();
      show("report");
      words.focus();
    }

    function copyMessage() {
      var words = card.querySelector("[data-report-words]");
      var status = card.querySelector("[data-report-status]");
      var text = copied(address(), card.getAttribute("data-subject"), message(words.value, added()));
      var nav = typeof navigator !== "undefined" ? navigator : {};
      if (nav.clipboard && nav.clipboard.writeText) {
        nav.clipboard.writeText(text).then(function () {
          say(status, "copied");
        }, function () {
          say(status, "copy-failed");
        });
      } else {
        say(status, "copy-failed");
      }
    }

    if (card) {
      card.addEventListener("click", function (event) {
        var target = event.target && event.target.closest ? event.target.closest("[data-act]") : null;
        if (!target) return;
        var act = target.getAttribute("data-act");
        if (act === "help") loadHelp();
        else if (act === "report") report();
        else if (act === "copy") copyMessage();
        else if (act === "back") view("sheet");
        else if (act === "close") close(true);
      });
      card.querySelector("[data-report-words]").addEventListener("input", preview);
      // Tapping the dimmed page around the card dismisses it.
      layer.addEventListener("click", function (event) { if (event.target === layer) close(true); });
      // A revealed icon opens the sheet. A click with a modifier key, or a middle click, stays an ordinary link.
      doc.addEventListener("click", function (event) {
        var icon = event.target && event.target.closest ? event.target.closest("a.help-icon") : null;
        if (!icon || event.defaultPrevented || event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        var named = anchor(icon.getAttribute("data-help"));
        if (!named) return;
        event.preventDefault();
        open(icon, named);
      });
    }

    doc.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      if (isOpen()) {
        event.preventDefault();
        close(true);
      } else if (root.hasAttribute(MARK)) {
        apply(root, button, false);
      }
    });
  }

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document !== "undefined") init(document);
})();
