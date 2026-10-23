# App help: to do

Checked against: `fa9a1ba`, 2026-10-23 (after Phase 3 part 1; the audit was re-run by hand against the code, as the `app-help` skill describes).
Plan: help is a book under About, `help-<chapter>.html#<feature>`, with hidden in-context icons, a rail button that reveals them, and a dismissable overlay. See `app-help-plan.md` and `.claude/skills/app-help/SKILL.md`.

## Where help stands today

- **The book exists.** `how-to.html` is its contents. Six chapters are published, with 33 features in all, in English and in a Welsh draft: *Finding your way*, *Looking up words*, *Reading a topic*, *Your settings*, *Arranging tiles*, *Offline and on your device*. A seventh, *Using help* (3 features), is written and tested but not shown, because the help button it describes does not exist (the `ask` condition in `Site.help_conditions`).
- Features that depend on the edition (regional forms, colour schemes, accessibility levels, tile levels, related topics, the About page) appear only where the edition has them.
- The old `how_to_*` messages are gone. Only `how_to`, `how_to_lede`, `how_to_col_keys`, `how_to_col_touch` and `help_chapters_label` remain.
- The Welsh body exists (`content/cydymaith/packs/cy/help.json`), as first drafts, all logged in `docs/REVIEW.md`. It is unchecked by a fluent speaker.
- **Still missing:** the in-context icons, the rail button, the sheet, the overlay and the report. Nothing on a screen yet links to a chapter; the only way in is About, then How to use the app.

## Framework work for the help mechanism

Done:

- [x] Book pages under About, with stable anchors, English in the framework and Welsh in the pack. Back and the trail go to the contents page and then About.
- [x] Address shape decided: flat `help-<chapter>.html#<feature>`; `help-` is reserved.
- [x] Offline: the pages are precached with the rest of the site.
- [x] `FRAMEWORK.md` updated (project files, reserved names, the help book).
- [x] Tests: anchors, text, conditions, ids, contents links, both languages (`tests/test_help.py`).

Still to do:

- [ ] Rail button, in the **4th slot from the bottom** (decided 2026-10-23), directly above the edit-order spanner ([site.py](../phrasebook/site.py), the rail's lower group). It also carries the report-issue idea (`docs/TODO.md` 3.6 merged into 3.7).
- [ ] Hidden in-context help icons on features and tiles, each with `data-help="<chapter>#<feature>"`. Decide which features and tiles get one (a control, a tile, a section; not every row).
- [ ] Sheet on each icon: **What's this?** first, **Report a problem** second.
- [ ] Overlay that loads the text of one feature from its chapter page (cached offline), not a copy. Look for `[data-feature="<anchor>"]`, since ids carry a language suffix in the second article. Dismiss by Escape, a close button and a tap outside; focus returns to the icon; inert background.
- [ ] Without the script, each icon is an ordinary link to `help-<chapter>.html#<feature>`. They are hidden until the script runs, as the search button is.
- [ ] Report a problem: context of at most 256 characters, a preview, *Open email* (`mailto:`) and *Copy*; no background sending.
- [ ] Make `ask` true in `Site.help_conditions` when the above exists, and check chapter 7 against what was built.
- [ ] Tests for the mechanism: every `data-help` resolves to an anchor; every anchor is linked from an icon; both languages present; an anchor's text stands alone.
- [ ] The fragment problem: `help-<chapter>.html#tiles` always lands on the first language's article, even when the second is selected. Either accept it, or have the script open the right article from the address.

## Gaps

### Missing

- [ ] **Help itself** (chapter 7): written, not shown. Waits for the mechanism above.
- [ ] **The compass rose and other drawings** on topic pages (`figure`): a labelled drawing with no explanation. Low priority; probably "no help needed", decide when icons exist.
- [ ] **Language pair.** The site chooses the pair and Settings cannot change it (`docs/TODO.md`, "Choose the language pair"). The help says so in *Which language comes first*; update it when the control exists.
- [ ] **The edit-order bar's spoken announcements** for a screen reader (`arrange_picked`, `arrange_moved`): not described. Probably enough as it is.

### Thin, stale, one language, unreachable

- [ ] **Welsh interface wording the help names but the screen does not show:** the search card's `Cau` (Close) and `Canlyniadau eraill` (Other results), and the section `Trefn:` (Order) line. Where: `content/cydymaith/packs/cy/pack.json` `ui` (`search_close`, `search_other`, `section_order`). Add them once the owner confirms the wording.
- [ ] **Unreachable from a control.** The only door is About, then the link at the foot of the About page. The icons and the rail button fix this. Settings hints (`appearance_hint`, `access_hint`, `order_hint`) are labels, not help: link each to its chapter.
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
