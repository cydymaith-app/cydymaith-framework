/* Phrasebook framework: the help button.
   A question-mark button in the rail turns help on and off. Every page that has help icons (links to the help book, marked
   data-help="<chapter>#<feature>") carries the button, hidden. Help icons are hidden by the stylesheet until the page says it is
   helping: this script sets data-helping on the document element, and the stylesheet shows the icons. Pressing the button again, or
   Escape, puts the page back as it was. Nothing is stored, so every page begins plain, and nothing is sent anywhere.
   Without this script the button stays hidden and the icons stay hidden, and the help book is still reached from About. */
(function () {
  "use strict";

  var MARK = "data-helping";

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

  var api = { apply: apply, toggle: toggle };

  // ---- the page

  function init(doc) {
    var button = typeof doc.getElementById === "function" ? doc.getElementById("help-toggle") : null;
    if (!button) return;
    var root = doc.documentElement;
    button.hidden = false;
    button.addEventListener("click", function () { toggle(root, button); });
    doc.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && root.hasAttribute(MARK)) apply(root, button, false);
    });
  }

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document !== "undefined") init(document);
})();
