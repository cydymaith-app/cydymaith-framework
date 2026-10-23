# App help: to do

Checked against: `11f9c05`, 2026-10-23.
Plan: help is a book under About (`help/<section>#feature`) with hidden in-context icons, a rail button that reveals them, and a dismissable overlay. See `.claude/skills/app-help/SKILL.md`.

## Where help stands today

- One page, `how-to.html`, built by `Site.how_to_page` ([site.py:1061](../phrasebook/site.py#L1061)) from `how_to_*` messages. It has three parts: *Finding your way*, a *Moves* table (open, back, along, settings) and three notes (edge drag, screen reader, offline).
- **No Welsh body.** The Welsh pack (`content/cydymaith/packs/cy/pack.json`) has only the `how_to` title. The other 23 `how_to_*` keys fall back to English. The built page is a Welsh title over English text.
- The About page ([edition JSON](../../content/cydymaith/editions/cydymaith.json), `about_page`) has eight sections in both languages. They explain the project's purpose, not the controls.
- No anchors, no `data-help` icons, no rail help button, no overlay exist.
- Controls with their own on-screen text: the edit-order bar (*Drag a tile to move it...*), Settings hints, the search placeholder and hint.

## Proposed book

In the order a new reader meets things. All anchors are new.

1. `help/finding-your-way`: `#tiles`, `#groups-topics`, `#title-bar-trail`, `#back`, `#pager`, `#jump-links`, `#keys-and-touch`, `#drag-back`.
2. `help/looking-up-words`: `#search`, `#search-keys`, `#search-this-page-first`, `#listen-first-rows`, `#also-heard`, `#regional-forms`, `#sources-notes`.
3. `help/reading-a-topic`: `#sections-order`, `#levels`, `#related-topics`, `#language-toggle` (Cy|En on Settings and About).
4. `help/your-settings`: `#view-mode`, `#accessibility`, `#colour-schemes`, `#order-setting`, `#regional-setting`, `#reset-tile-layouts`, `#what-is-saved`.
5. `help/arranging-tiles`: `#edit-order`, `#drag-or-tap`, `#save-reset`.
6. `help/offline-and-install`: `#offline`, `#install`, `#no-script`, `#share`.
7. `help/using-help`: `#help-button`, `#help-icons`.

## Framework work for the help mechanism

- [ ] Book pages under About, with stable anchors, built from messages (English default in the framework catalogue, Welsh in the pack). Back and trail go to About.
- [ ] Decide the address shape: static `help/<section>.html#feature` files, or a flat `help-<section>.html`. `help` and `help-` would be reserved names.
- [ ] Hidden in-context help icons on features and tiles, each with `data-help="<section>#<feature>"`.
- [ ] Rail button, in the **4th slot from the bottom** (decided 2026-10-23). The lower group is now edit-order spanner, About, Settings ([site.py:752](../phrasebook/site.py#L752)), so it goes directly above the spanner. It also carries the report-issue idea: the old flag in `docs/TODO.md` 3.6 is merged into it (see 3.7 there for the flow and the reasons).
- [ ] Sheet on each icon: **What's this?** first, **Report a problem** second.
- [ ] Report a problem: context of at most 256 characters, a preview, *Open email* (`mailto:`) and *Copy*; no background sending. Wording of the sheet and preview needs Welsh.
- [ ] Overlay that loads the text of the anchor, not a copy. Dismiss by Escape, a close button and a tap outside; focus returns to the icon; inert background.
- [ ] Without the script, each icon is an ordinary link to the book page. (They are hidden until the script runs, as the search button is.)
- [ ] Offline: precache the book pages in `sw.js`.
- [ ] Update `FRAMEWORK.md`: reserved names, rail, About links, messages.
- [ ] Tests: every `data-help` resolves to an anchor; every anchor is linked from an icon; both languages present; no anchor text depends on its page.

## Gaps

### Missing

- [ ] **Search and the lookup card.** Rail button, `/` key, results, Up/Down/Enter, Escape, "Other results" section, a word's regional forms. Source: `search.js`, `Site.search_card`, messages `search_*`. Anchor: `help/looking-up-words#search`. Icon on: the search button. Needs Welsh.
- [ ] **Edit order (arranging tiles).** The spanner, drag or tap-and-tap, arrow keys, Escape, Save order, Reset, kept on this device. Source: `arrange.js`. Anchor: `help/arranging-tiles#edit-order`. Icon on: the spanner. Needs Welsh.
- [ ] **Listen-first rows.** The heard language leads, large and left; the other sits muted at the end of the row. Source: `default_pair`, `style.css`. Anchor: `help/looking-up-words#listen-first-rows`. Icon on: a phrase table's header. Needs Welsh.
- [ ] **"Also heard" chips.** Other forms of a word (changed beginnings, plurals) and that search finds them. Source: `also` in packs, message `also_heard`. Anchor: `#also-heard`. Needs Welsh.
- [ ] **Regional forms.** The markers on a row, and the choice in Settings. Source: `varieties.css`, `Site.variety_group`. Anchor: `#regional-forms`. Needs Welsh.
- [ ] **Levels on tiles and sections** and the Order setting (simple first, most advanced first). Source: `grading.py`, `order.js`, `order_*` messages. Anchor: `help/reading-a-topic#levels`. Known item, see *Carried over*. Needs Welsh.
- [ ] **Related topics tiles and Back returning to the topic you came from.** Source: `Site.related_tiles`, `nav.js`. Anchor: `#related-topics`. Known item. Needs Welsh.
- [ ] **Settings: view mode, accessibility level, colour schemes.** What each does; that the accessibility choice filters the schemes listed. Source: `Site.look_group`. Anchors: `#view-mode`, `#accessibility`, `#colour-schemes`. Needs Welsh.
- [ ] **Settings: reset tile layouts.** Source: `reset_orders*` messages. Anchor: `#reset-tile-layouts`. Needs Welsh.
- [ ] **What the app saves on this device.** Preferences (appearance, palette, order, varieties, language), saved tile order, and how to clear them. Source: `app.js`, `order.js`, `arrange.js`. Anchor: `help/your-settings#what-is-saved`. Needs Welsh.
- [ ] **Cy|En language toggle** on Settings and About: shows one language at a time; remembered; works without the script. Source: `Site.about_page`, `Site.settings_page`. Anchor: `#language-toggle`. Needs Welsh.
- [ ] **Pager (previous and next topic) and jump links in a topic.** Source: `Site.pager`, `Site.content_page`. Anchors: `#pager`, `#jump-links`. Needs Welsh.
- [ ] **Title bar and trail.** The trail's second language shows on wider screens. Source: `Site.shell`. Anchor: `#title-bar-trail`. Needs Welsh.
- [ ] **Share button** (About): appears only where the browser can share or copy; makes no request. Source: `{"share"}` block. Anchor: `#share`. Needs Welsh.
- [ ] **Sources page and what a source note means.** Source: `Site.sources_page`. Anchor: `#sources-notes`. Needs Welsh.
- [ ] **Install and offline use.** The About section "Install it for offline use" covers install; the how-to note says only "works without a network". Check they agree. Source: `sw.js`, `manifest.json`. Anchors: `#install`, `#offline`.
- [ ] **Help itself.** The help button and icons. Anchor: `help/using-help#help-button`. New with the mechanism.

### Thin, stale, one language, unreachable

- [ ] **How to use the app: Welsh body.** One language: 23 `how_to_*` keys are missing from the Welsh pack. Where: `content/cydymaith/packs/cy/pack.json` `ui`; English in `framework/phrasebook/messages/en.json:19-39,96-98`. Welsh is a draft: add lines to `docs/REVIEW.md`.
- [ ] **Moves table: Settings row.** Thin: "Tab to the gear" and "Tap the gear" omit that Settings is also reached from the About page's links. Check the row against the real rail (About sits above the gear). Where: `how_to_*_settings`.
- [ ] **Moves table: keys.** Thin: it omits Home/End (mentioned under "along" only), Escape, `/` for search, and the Left arrow in a right-to-left page. Source: `nav.js:31-39`, `search.js:338-360`.
- [ ] **"Finding your way" text.** Stale: "the narrow bar at the side has Back and Settings". The rail also has Search, About and (once the script runs) Edit order. Where: `how_to_tree`.
- [ ] **Edge-drag note.** Thin: says a drag from the very edge is left to the device but not how far (20px) or how to go back instead. Where: `how_to_note_edge`.
- [ ] **Offline note.** Thin: "the whole tree works without a network" once installed. It does not say that it must have been opened once, nor how to update. Where: `how_to_note_offline`.
- [ ] **Settings page hints.** Present (`appearance_hint`, `access_hint`, `order_hint`), but they are labels, not help. Link each to its anchor once the book exists.
- [ ] **About is the only door.** Unreachable from a control: How to use the app is linked only from the foot of About (and Settings in an edition without About). The icons and rail button will fix this.

## Carried over from `docs/TODO.md`

- [ ] Put related topics in the how-to page, in both languages (`docs/TODO.md:182`). Moves to `#related-topics`. Tick the original when done.
- [ ] Put the Order setting in the how-to page, in both languages (`docs/TODO.md:193`). Moves to `#order-setting`. Tick the original when done.
- [ ] When the weather section is complete, use it as the worked example on the how-to page (`docs/TODO.md:71`). Fits `help/reading-a-topic`.

## Checked and fine

- Keyboard and touch for open, back and move between tiles: correct against `nav.js` (Down/Up, Home/End, Right opens, Left and Backspace go back, drag to go back).
- Screen reader note: tiles are links named in both languages (matches `Site.tile`).
- Rail buttons have accessible names (`aria-label`) for Search, Back, About, Settings and Edit order.

## No help needed

- Skip-to-content link: standard, keyboard only.
- Page `Back` in the rail: self-explaining, but still given an anchor (`#back`) so the table has one home.
- Held-back (`status: development`) About sections and the Everyday > Food and drink page: scaffolding, not gaps.

## Disagreements between docs and code

- `FRAMEWORK.md` says `how-to.html` "explains all of this" (keys, dragging, sliding). It explains four moves and three notes. It does not mention search, edit order, levels, related topics, the language toggles, or saved data.
- `FRAMEWORK.md` describes the rail as search, Back and the Settings gear. The code adds About and Edit order, in the lower group.
