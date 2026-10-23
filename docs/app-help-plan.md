# Help book: implementation plan

Planned 2026-10-23. Covers the book itself. The in-context icons, sheet, overlay and report are later (see `docs/TODO.md` 3.7); the book must leave them ready (Phase 4). The gap list is `app-help-todo.md`.

## Phase 0: decisions (agreed 2026-10-23)

1. **Flat addresses: `help-<section>.html#<feature>`**, not a `help/` folder.
   - Every page sits at the site root and links its CSS, JS and pages relatively. A subfolder would break those links, the slide in `nav.js` and the parent check in the head script.
   - It matches `group-<id>.html`. `help-` becomes a reserved prefix, as `group-` is.
2. **A structured help file, not more flat messages.**
   - `framework/phrasebook/help.py`: the ordered sections and features, with no words.
   - `framework/phrasebook/help/en.json`: English defaults.
   - `content/<project>/packs/<code>/help.json`: that language's text; a project may also override the English.
   - Keeps the rule that the framework holds no Welsh, and avoids dozens of long flat keys.
3. **`how-to.html` stays as the book's contents page.** About already links to it, and tests and the offline cache expect it. Its table of moves becomes the first chapter.

## Phase 1: the skeleton (framework)

**Done 2026-10-23** (commit 1 below): `help.py`, `help/en.json` with the `finding-your-way` chapter (8 features), rendering of the contents and chapter pages, `help-` reserved, coverage in the build output, and tests in `tests/test_help.py`. Differences from the plan:

- A `side-bar` feature was added to the first chapter, because the old text about the bar at the side was stale.
- The `pager` feature is titled "Reading on", so the English title does not trip the test that finds fallen-back interface words.
- The English help text names controls in English, so the framework's leak test skips help articles (they are marked `lang="en"`).
- Coverage is counted over every feature in the book, not only those the edition shows.
- The old `how_to_*` messages were removed now (only `how_to`, `how_to_col_keys`, `how_to_col_touch` and the new `how_to_lede` and `help_chapters_label` remain), not in Phase 3.

1. `help.py`
   - Ordered sections, each with ordered features. Each feature has an anchor id and an optional `requires` condition.
   - Conditions match how Settings decides what to show: the edition has an About page, regional varieties, more than one accessibility level, or tile levels that differ.
   - Anchor ids are lower case with hyphens, unique across the book, and never renamed. A rename is a breaking change.
2. Each entry holds, per language: a title, a body, and optional keyboard and touch lines.
   - The body uses the About page's blocks: paragraphs, `list`, `links`.
   - Keyboard and touch lines show as a "Keyboard / Touch" table, keeping the current Moves format.
3. Rendering in `site.py`
   - One page per section, one `<section id="<feature>">` per feature. Each makes sense alone, with no "see above", so the overlay can later show just that part.
   - Cy|En toggle as on About: one language at a time, first language first, no script needed, choice remembered.
   - `how-to.html` becomes the contents page: a short intro, then a tile per chapter, each listing its features as anchor links.
   - Trail: Home > About > How to use the app > chapter. Back goes up to the contents page.
   - Previous and Next links at the foot of each chapter, like a book (a small new pager; the existing one is tied to topic pages).
   - A feature whose condition is not met is left out, and so is its link. A chapter left empty is dropped.
4. `content.py` rejects topic names that start with `help-`.
5. Offline needs no work: the service worker caches every built file.
6. The build reports help coverage per language beside word coverage, for example `help: en 42/42, cy 3/42`. A missing translation falls back to English. With `--strict`, a missing English entry fails the build.

## Phase 2: tests (framework)

**Done 2026-10-23.** Most of this landed with Phase 1 in `tests/test_help.py`; the rest (anchor ids exactly once, unique ids per page, no unrendered templates or requests to another site, every contents link reaching a real anchor, well-formed entries, normal form C) was added after. The project's own tests cover the pages generically (ids, `{{`, current-page marks).

- Every anchor in `help.py` has English text.
- Anchors are unique, valid ids, and appear exactly once in the built pages.
- A feature whose condition is not met is absent, with its contents link.
- Trail, Back and Previous/Next are right, and `help-` is rejected as a topic name.
- The pages pass the no-external-requests and no-unrendered-template checks.
- Existing `how-to.html` tests are updated: the moves table moves to the `finding-your-way` chapter.
- A frozen list of anchors in a test, so renaming one fails loudly.

## Phase 3: the words

**Part 1 done 2026-10-23: chapter 1, Finding your way.** English in `phrasebook/help/en.json`; Welsh draft in `content/cydymaith/packs/cy/help.json` (with `how_to_col_keys` and `how_to_col_touch` in the pack's `ui`), logged in `docs/REVIEW.md`. Found on the way: two language articles gave every feature id twice, so only the first article now takes the plain anchor (`tiles`) and the others a language suffix (`tiles-en`); sections carry `data-feature`. **Chapter 2, Looking up words, done 2026-10-23** (seven features; `regional-forms` needs `varieties`; English and a Welsh draft, logged in `docs/REVIEW.md`). **Chapters 3 and 4, Reading a topic and Your settings, done 2026-10-23** (English and Welsh drafts). The book's conditions grew to `about`, `varieties`, `palettes`, `access`, `levels` and `related`, so a feature appears only when the edition has the thing it explains. Three plan changes: `language-toggle` is in chapter 4, not 3; `regional-setting` is covered by chapter 2's `regional-forms`; and grades are not marked on the screen, so `levels` explains the Order choice only. Chapters 5 to 7 are still to do.

1. **English, in the framework.** The seven chapters from `app-help-todo.md`:
   1. finding your way
   2. looking up words
   3. reading a topic
   4. your settings
   5. arranging tiles
   6. offline and install
   7. using help

   The existing `how_to_*` text moves into `finding-your-way`; fix the stale "the narrow bar has Back and Settings" on the way.
   Each entry: the task first, keyboard and touch, where the control is, what it saves on the device, and what works without the script. One phone screen each.
2. **Welsh, in the project:** `packs/cy/help.json`, drafted and marked unchecked, with a line per chapter in `docs/REVIEW.md`.
3. Remove the old `how_to_*` message keys once nothing uses them.
4. Re-run the `app-help` skill. The "missing" list should shrink to the mechanism items.

## Phase 4: left ready for the icons

- One anchor per feature, so an icon's `data-help="<section>#<feature>"` maps to `help-<section>.html#<feature>`.
- Sections can be extracted: the overlay will fetch the chapter page (cached offline, as `nav.js` fetches pages) and show only `#<feature>`.
- A plain link to `help-<section>.html#<feature>` is always the fallback without the script.

## Docs to update alongside

- `FRAMEWORK.md`: the help file in the project-files table, `help-` reserved, the trail, and remove "how-to explains all of this".
- `docs/TODO.md` 3.7: tick *The book* when Phase 1 lands; tick the older how-to items (related topics, the Order setting) when Phase 3 covers them.
- Re-run the `app-help` skill after each phase.

## Commits

1. Framework: `help.py`, rendering, tests, and English for `finding-your-way` only. Proves the pipeline end to end.
2. Framework: the remaining English chapters.
3. Main repo: the submodule pointer, `packs/cy/help.json` drafts, and the `REVIEW.md` lines.

## Size

- Phases 1 and 2: a few hundred lines of Python and tests, about the size of the About page work.
- Phase 3: mostly writing, about 40 short entries in English, then Welsh drafts.
