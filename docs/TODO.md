# To-do (framework)

Work top to bottom. Tick items off in the commit that completes them. The Welsh translator's own to-do list is in the `cydymaith` repository that uses this framework as a submodule.

## 0. Principles

- [x] **Test that fails on third-party requests**, for both the neutral fixture and the real project.
- [ ] **Decide a framework name.** The package is still called `phrasebook`, a working name, and the repository is `cydymaith-framework`. Decide a name for the framework, and check it for collisions before the first public deploy. A rename touches every import, the docs and the tests, so do it as one change.
- [ ] Format all the Python with black.

## 1. Languages and theming

- [x] **i18n and l10n conformance, and framework kept apart from the content.** `phrasebook/` holds no language; `content/gair-wrth-air/` holds everything of the project. Interface text is in a keyed message catalogue with fallback, placeholders, CLDR plurals and list patterns. Content must be in Unicode normal form C. Direction and language are marked relative to the surrounding text. The CSS uses logical properties and role class names. Details and gaps: `FRAMEWORK.md`.
  - [ ] **Look at it in a real browser**: right-to-left (switch the fixture interface to its right-to-left language), the phone layout, and the menu arrow in both directions.
  - [ ] Warn at build time when a pair language has no `ui` words for the labels shown beside it, instead of silently showing English.
  - [ ] Number formatting by locale (digit shapes, grouping) if any language needs it.
  - [ ] Let the interface language be chosen by the visitor (needs a catalogue in the page and the script).
  - [ ] Allow an interface language that has no phrase pack.
  - [ ] Add plural rules for each new language as it arrives, and consider shipping interface catalogues for common languages in `phrasebook/messages/`.
- [x] **Language-agnostic framework.** Concepts, language packs and editions; any pair from the edition's languages; right-to-left support in the metadata; coverage report. Output for English and Welsh is unchanged apart from capital letters on the compass labels.
- [x] **Save user preferences in the browser's own storage.** Done in `phrasebook/assets/app.js`: one versioned key per site (`<edition>:prefs`, named by the edition so sites on one origin stay apart), every read and write in `try/catch`, anything unrecognised ignored, applied before first paint, and tested with Node. It never touches the network or cookies.
  - [ ] Extend the same object for the language pair as that control arrives. The theme is done (version 2). Bump the version if the shape changes.
- [x] **Regional forms (varieties).** Concepts can hold several forms tagged by variety (for Welsh, north and south). Every form is labelled, and a control emphasises one variety and dims the rest. Needs a hands-on check in a real browser, especially on a phone, where the control sits in the menu drawer.
  - [ ] Search must find any form, so "llefrith" finds "milk" as well as "llaeth". Compare in normal form C and fold case by the language's own rules (`Intl.Collator`), not with ASCII lower-casing.
  - [ ] Consider an "only my variety" mode that hides the other forms, if dimming proves too busy.
  - [ ] Varieties are one flat axis today. Add a second axis (for example formal and colloquial) only if the content needs it.
  - [ ] Research and add more regional pairs, and check each label. Confirm the dimming has enough contrast in the dark theme.
- [ ] **Choose the language pair ("from" and "to").** This replaces the old "swap direction" item and covers any number of languages.
  - Render every language of the edition into each page (all cells present, two shown), so size grows linearly with languages. Without scripts it shows the edition's default pair.
  - Needs table rows turned into CSS grid rows so columns can be reordered. Keep table semantics with explicit roles.
  - Show commentary (notes, intros, boxes) for any displayed language that has it.
  - Home page copy is currently per language, not per pair. Template it so any pair reads naturally.
  - Remember the pair in preferences. Also accept a URL fragment, so a pair can be shared.
- [x] **Light/dark appearance and colour palettes.** Done: *Same as device* (default), *Light* and *Dark*, plus a choice of palette. Four ship: `default`, `high-contrast` (AAA), `red-green-safe` and `blue-yellow-safe`. Palettes are OKLCH data (`phrasebook/palettes/`, and a project's own `palettes/`), converted to `palettes.css` at build time; the build fails a palette that breaks its contrast or colour-vision promises. Saved with the other preferences (version 2, which still reads version 1) and applied before first paint. See `FRAMEWORK.md`.
  - [x] **Screenshots of every theme**: `python3 build.py dist --screenshots` writes one picture of each palette, light and dark, into `docs/screenshots` (git-ignored), with a gallery README. Still to do: run it in CI and keep the pictures as a build artifact, so a pull request can show a change to a palette.
  - [ ] **Look at it in real browsers and on real devices**, in each palette and variant: the compass rose, focus rings, the current-page marker, the dimming of other regional forms, the Settings page at phone width.
  - [ ] **Ask people with colour-vision deficiencies to try the palettes.** The checks are arithmetic on simulations; they are not evidence that the palettes work for people.
  - [ ] Choose the palette automatically from `prefers-contrast: more` when the visitor has not chosen, without taking the choice away from them.
  - [ ] Check Windows forced-colours mode by hand, and screen-reader announcement of the radio groups.
  - [ ] Meet the 3:1 contrast for the boundaries of controls (jump links, pager, menu button) in the default palette, or give them text-only identification. `rule-strong` is below 3:1 there; the `high-contrast` palette meets it.
  - [ ] Consider more palettes (monochrome for achromatopsia, a low-glare dark, a sepia) and text-size and line-spacing preferences. Each is a data file or a small control.
- [x] **Tests for the controls and the preferences logic.** Node tests cover reading, validating, applying and saving the preferences; build tests cover the controls, the pre-paint script and the generated palettes.

## 2. App features

- [x] **Installable offline app (PWA).** All pages install with the app and work with no network.
  - Web manifest with a relative `start_url` and `scope`, so it works under the GitHub Pages sub-path. Icons at 192, 512 and maskable sizes, declared per edition and validated.
  - Service worker that pre-caches every built file, with a cache name versioned from a hash of their content. The build generates the file list itself, so new pages are included automatically.
  - Updates arrive silently on the next visit (the new service worker takes over at once; no update banners, no install nags). Installing is the person's choice, through the browser's own menu.
  - Everything is installed at once (the site is small); no per-topic offline choice.
  - No push notifications and no background sync.
  - Tests cover the manifest fields, icon validation and that the pre-cache list matches the built files, on both the real project and the neutral fixture (which has no icons, so the manifest degrades gracefully). Still to check by hand: install and offline behaviour on an iOS device.
- [x] **Client-side search across all entries.** Done with the lookup card below: every word and phrase in both languages of the pair, every regional form, and every topic title, matched with the language's own case rules and then again with accents ignored. See `FRAMEWORK.md`.
- [x] **Dictionary lookup widget.** Done: the search button at the top of the rail opens a card that slides out from behind the rail as an overlay. As the person types, it lists the matching words with their translations, and under each word the topics it is in, as links that land on the word's row. Escape, the Close button, a tap outside and following a link all dismiss it; `/` opens it from the keyboard.
  - The card lists matching words with their translations.
  - Links to matching pages arrive on the card as sub-items.
  - Build on the client-side search above, and use the same normal-form and case-folding rules for matching.
  - The index is `dictionary.json`, generated by every build from the packs and pages (`phrasebook/dictionary.py`), and each page of an entry carries a link to the word's row. It is read once, when the card first opens, and is precached, so search works offline.
  - [ ] **Try the card on a phone**: the slide out from the rail, the keyboard coming up over the results, the Close button, a tap outside, a result link landing on its row, then offline, and TalkBack and VoiceOver.
  - [ ] **Try it right to left** (switch the fixture interface to its right-to-left language): the card should slide out from the other side.
  - [ ] Show the regional form's label (north, south) beside each form on the card, and match a query typed in a third language of an edition with more than two.
  - [ ] Translate the search messages (`search_*` in `phrasebook/messages/en.json`) into Welsh and any other interface language.
- [x] **Tile navigation from the mockup** (`docs/mockups/navigation-mockup.png`), replacing the sidebar menu, the Explore dialog and the home panel. Done: a rail with the Settings gear, a top bar with Back and the trail, tiles for groups and for each group's topics (both languages, Carbon icons), keys (Right goes in, Left goes back, Up and Down move along) and a swipe with the reading direction to go back, and `tree.json` kept for search. Designed mobile first, which is now in `PHILOSOPHY.md`. See `FRAMEWORK.md`.
  - [ ] **Try it on a phone**: tap targets, the card sliding in from the right when a tile is tapped, dragging it back out with a finger (follows the finger, springs back when let go early, leaves on a flick, ignores the screen edge), Back, the rail gear, the tiles at 2 across, install, then offline, and TalkBack.
  - [ ] **Try it with VoiceOver, and right to left** (switch the fixture interface to its right-to-left language).
  - [x] **Site search in the rail.** Done: the button is hidden until `search.js` runs (so without scripts there is no control that does nothing), then opens the card.
  - [ ] Consider a "recent" row of tiles on the home page for the last topics visited, only if it can be kept on the device and without nudging anyone to return.
- [x] **Entries should not repeat the title.** Done: a section heading that matches the page title in both languages (case and normal form ignored) is left out (`repeats_title` in `phrasebook/site.py`); the section keeps its `id`, so links still land. Column headers stay, as they name the languages and appear once per table.
  - [ ] Add a test that a section titled like its page has no `<h2>`, and look at the topic pages in a browser.

## Done

- [x] Release channels: sections marked `development` are held back from the release build (`phrasebook/channels.py`)
- [x] Language-agnostic framework with packs and editions
- [x] Framework separated from the content, with a localisable interface
- [x] Framework moved to its own repository, used by the Welsh app as a submodule
