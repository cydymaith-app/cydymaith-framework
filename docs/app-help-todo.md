# App help: to do

Checked against: `fa9a1ba`, 2026-10-23 (after Phase 3 part 1; the audit was re-run by hand against the code, as the `app-help` skill describes).
Plan: help is a book under About, `help-<chapter>.html#<feature>`, with hidden in-context icons, a rail button that reveals them, and a dismissable overlay. See `app-help-plan.md` and `.claude/skills/app-help/SKILL.md`.

## Where help stands today

- **The book exists.** `how-to.html` is its contents. Six chapters are published, with 33 features in all, in English and in a Welsh draft: *Finding your way*, *Looking up words*, *Reading a topic*, *Your settings*, *Arranging tiles*, *Offline and on your device*. A seventh, *Using help* (3 features, the report one only where the edition has an address), describes the help button, icons, sheet and report, which now exist.
- Features that depend on the edition (regional forms, colour schemes, accessibility levels, tile levels, related topics, the About page) appear only where the edition has them.
- The old `how_to_*` messages are gone. Only `how_to`, `how_to_lede`, `how_to_col_keys`, `how_to_col_touch` and `help_chapters_label` remain.
- The Welsh body exists (`content/cydymaith/packs/cy/help.json`), as first drafts, all logged in `docs/REVIEW.md`. It is unchecked by a fluent speaker.
- **Built since:** the rail help button, a first set of hidden icons, the sheet (What's this? / Report a problem), the overlay and the report. Chapter 7 is published. Checked in headless Edge on the home, a topic and the Settings page.

## Framework work for the help mechanism

Done:

- [x] Book pages under About, with stable anchors, English in the framework and Welsh in the pack. Back and the trail go to the contents page and then About.
- [x] Address shape decided: flat `help-<chapter>.html#<feature>`; `help-` is reserved.
- [x] Offline: the pages are precached with the rest of the site.
- [x] `FRAMEWORK.md` updated (project files, reserved names, the help book).
- [x] Tests: anchors, text, conditions, ids, contents links, both languages (`tests/test_help.py`).

Still to do:

- [x] Rail button, in the **4th slot from the bottom**, directly above the edit-order spanner. Done 2026-10-23 (`#help-toggle`, `help.js`).
- [x] Hidden in-context help icons, each marked `data-help="<chapter>#<feature>"` and a plain link to `help-<chapter>.html#<feature>`. First set done 2026-10-23: the trail, tile grids, jump links, section Order lines, the pager, the Related row, and six Settings choices. Still open: which other features and tiles get one.
- [x] Sheet on each icon: **What's this?** first, **Report a problem** second. Done 2026-10-23.
- [x] Overlay that loads the text of one feature from its chapter page (cached offline). Done: it looks for `[data-feature="<anchor>"]`, so the second language's suffixed ids do not matter, and shows each language the chapter has. Dismissed by Escape, Close and a tap outside; focus returns to the icon; the page behind is inert.
- [x] Without the script, each icon is a plain link to `help-<chapter>.html#<feature>`; with it, the icon opens the sheet. Icons and the button are hidden until the script runs.
- [x] Report a problem: at most 256 characters of context, a preview, *Open email* (`mailto:`) and *Copy*; no background sending. The address is the edition's `contact`, kept in two pieces in the page.
- [x] Chapter 7 is shown (the `ask` condition is gone). The report feature in it needs the edition's `contact`.
- [x] Tests for the mechanism (`tests/test_help.py`, `tests/help.test.js`): every `data-help` resolves to an anchor; the button and card are on exactly the pages with icons; the pure moves (the 256 cap, the mail link, the section picker). Not every anchor is linked from an icon yet, by design: only the first set has icons.
- [ ] The fragment problem (still open): `help-<chapter>.html#tiles` always lands on the first language's article, even when the second is selected. Either accept it, or have the script open the right article from the address.

## Gaps

### Missing

- [x] **Help itself** (chapter 7): shown since the mechanism exists.
- [ ] **The compass rose and other drawings** on topic pages (`figure`): a labelled drawing with no explanation. Low priority; probably "no help needed", decide when icons exist.
- [ ] **Language pair.** The site chooses the pair and Settings cannot change it (`docs/TODO.md`, "Choose the language pair"). The help says so in *Which language comes first*; update it when the control exists.
- [ ] **The edit-order bar's spoken announcements** for a screen reader (`arrange_picked`, `arrange_moved`): not described. Probably enough as it is.

### Thin, stale, one language, unreachable

- [ ] **Welsh interface wording the help names but the screen does not show:** the search card's `Cau` (Close) and `Canlyniadau eraill` (Other results), and the section `Trefn:` (Order) line. Where: `content/cydymaith/packs/cy/pack.json` `ui` (`search_close`, `search_other`, `section_order`). Add them once the owner confirms the wording.
- [x] **Unreachable from a control.** Fixed for the features that now have an icon (press the help button). Settings hints (`appearance_hint`, `access_hint`, `order_hint`) are labels, not help: link each to its chapter.
- [ ] **Read the chapters in a browser**, on a phone and at width: the new styles (`.help-feature`, `.help-ways`, `.help-contents`), the Cy|En toggle on a chapter, the contents page, Previous and Next, and the `#feature` jump.
- [ ] **A fluent speaker checks the Welsh** (see `docs/REVIEW.md`), in particular the terms for spanner, toggle, tile, and the control names the screen does not show yet.
- [ ] **Verify two behaviours against a real browser** that the chapters state from reading the code: picking up a tile with Enter, and the install steps on Android, iPhone and a computer.

## Carried over from `docs/TODO.md`

- [x] Put related topics in the how-to page, in both languages (`docs/TODO.md` 3.2). Done as `help-reading-a-topic.html#related-topics`.
- [x] Put the Order setting in the how-to page, in both languages (`docs/TODO.md` 3.2). Done as `help-your-settings.html#order-setting` and `help-reading-a-topic.html#levels`.
- [ ] When the weather section is complete, use it as the worked example on the how-to page (`docs/TODO.md` Languages and content). Fits *Reading a topic*.

## Checked and fine

- Keyboard and touch for open, back and moving between tiles: correct against `nav.js`.
- The trail, the rail and the Back targets: match `Site.steps` and `Site.shell`, including About and Edit order.
- Search: the `/` key, Up and Down, Enter on the first result, Escape, the "Other results" line and the topic-first order match `search.js` and `FRAMEWORK.md`.
- Settings: the groups, the accessibility levels (choosing a level switches to the scheme last picked there), the Order choice, Reset tile layouts and what is kept match `Site` and `app.js`.
- Rail buttons have accessible names (`aria-label`) for Search, Back, About, Settings and Edit order.
- The install steps reuse the About page's wording in both languages, so the two agree.

## No help needed

- Skip-to-content link: standard, keyboard only.
- Held-back (`status: development`) About sections and the Everyday > Food and drink page: scaffolding, not gaps.

## Disagreements between docs and code

- `FRAMEWORK.md` said `how-to.html` "explains all of this" and described the rail without About or Edit order. Both are fixed (the contents page and the book are described; the rail is covered in the book's *The bar at the side*).
- `FRAMEWORK.md` still says on *Settings page*, under accessibility, that the choice "changes no scheme". `app.js` switches to the scheme last picked at the chosen level. The book says what the code does; correct `FRAMEWORK.md`.
