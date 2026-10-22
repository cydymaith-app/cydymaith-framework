# The framework

`phrasebook/` is a small static-site generator for multilingual phrasebooks. It contains no language and no phrases. A **project** (a folder under `content/` in the repository that uses it) supplies those. *Cydymaith am iaith* (English and Welsh, with north and south Welsh forms) is the first project, in its own repository, [`cydymaith`](https://github.com/cydymaith-app/cydymaith), which holds this framework as a git submodule in `framework/`.

To make another translator, create a repository with a `content/<project>/` folder and add this one as a submodule (`git submodule add <url> framework`). Its `build.py` puts `framework/` on `sys.path` and calls `phrasebook.cli.main(projects_dir=<its content/ folder>)`; see the `cydymaith` repository for a working example. No framework code changes are needed.

```
phrasebook/                 the framework
  cli.py content.py site.py messages.py plural.py figures.py errors.py colour.py palettes.py icons.py tree.py channels.py dictionary.py
  messages/en.json          every word the framework shows itself (the source of truth for the keys)
  palettes/                 the framework's colour palettes (OKLCH, light and dark each)
  assets/                   style.css, app.js (preferences) and nav.js (keys and swipes), copied to every site
  ui-icons/                 the framework's own interface icons (search, back, settings), inlined into pages, never copied as files
build.py                    entry point (a project's own build.py does the same with its content/ folder)
tests/                      framework tests, on a neutral made-up project (fixture.py)

A project (in its own repository, beside this framework in framework/):

content/<project>/          one translator
  structure.json  pages/  packs/<code>/  editions/  palettes/  icons/  static/
```

`tests/test_framework.py` fails if the framework names a language, a phrase or a project (`EngineIsLanguageNeutral`). It checks the made-up fixture project by default. A project repository sets `PHRASEBOOK_PROJECT` to its own content folder and runs that test, so its real words are checked too.

## Building

```sh
python3 build.py dist                       # the only project in content/
python3 build.py dist --project path/to/p   # any project folder
python3 build.py dist --edition NAME        # when a project holds several editions
python3 build.py dist --strict              # fail while any source is still an unreviewed draft
python3 build.py dist --screenshots         # also screenshot every theme into docs/screenshots (needs a browser)
python3 build.py dist --screenshots DIR     # ...or into DIR
```

**Theme screenshots.** `--screenshots` takes one phone-sized picture of every offered palette in its light and its dark variant, each of one example page: the first topic that has a drawing, since it shows the most of the colours (the accent, the star, text and rules). That is 8 pictures for the English and Welsh project, and takes about a minute and a half, so it is a step of its own, not part of every build. The site is copied with the theme set the way the settings page sets it and the page's scripts taken out, and `docs/screenshots/README.md` is written as a gallery. The folder is generated, so git ignores it. A headless Chrome, Chromium or Edge is needed for this step only: it is found from the `PHRASEBOOK_BROWSER` environment variable (a path or a name), then the usual names on the `PATH`, then the usual install places, and the build says so if there is none. Run it again after changing a palette or the layout.

## Project files

| File | What it holds |
|---|---|
| `structure.json` | Navigation groups and page order. A group may name an `icon`. Language neutral. |
| `pages/<slug>.json` | A page skeleton: sections and the ids of their **concepts**. No words. May name a `figure` and an `icon`. |
| `packs/<code>/pack.json` | One language: `code`, `name`, `names`, `dir`, `ui`, `groups`, `sources`, `varieties`, `commentary_lang`. |
| `packs/<code>/pages/<slug>.json` | That language's title, lede, default `source`, and per section a title, optional `intro` and `box` commentary, and one entry per concept. |
| `editions/<name>.json` | `name`, `languages`, `interface`, `default_pair`, `home` copy, `fonts`, `stylesheets`. |
| `palettes/<id>.json` | Optional. A colour palette added to the framework's own, or one with a framework id that replaces it. See *Themes and palettes*. |
| `icons/<name>.svg` | Optional line icons. A group in `structure.json` or a page skeleton names one with `"icon": "<name>"`. See *Navigation*. |
| `static/` | Files copied to the site as they are. They may add to the framework's files or replace them. |

A concept is `{ "text": "...", "note": "...", "source": "id" }` or `{ "forms": [{ "text": "...", "varieties": ["north"] }] }`. A concept missing from a pack is simply not shown for that language.

- **`also`** (optional, a list of texts in the pack's own language): other forms the word is heard as, such as a changed beginning or a plural. They show as small chips in a full-width row under the word, headed by the message `also_heard`, and are added to `dictionary.json` as `also`, so search finds the word from any of them. Search shows only the word's own terms, never the `also` forms. A form may not repeat the word or itself.
- **`order`** (optional, on a section in a pack, commentary in the pack's `commentary_lang`): one line saying what order the rows run in, such as "lightest to heaviest". Shown under the section heading as the message `section_order`.
- **Listen-first rows.** The first language of the pair is the one heard, so its text leads (large, strong, left in a left-to-right page) and the second sits at the end of the same row, muted. The pair comes from the edition's `default_pair`, so a project for people who listen to a language puts that language first.
- **Settings page** (`Site.settings_page`): every choice is visible at once, on cards, instead of an accordion. A Cy|En toggle at the top right (radios styled as a toggle, so no script) shows the page in one language of the pair at a time, the first language first; every label is rendered once per language of the pair (`both()`), and the stylesheet shows one. The controls and their state exist once. The cards:
  - **Appearance:** three icon tiles, light, dark and same as device (Carbon `light`, `asleep`, `screen`).
  - **Accessibility:** a three-way control, Standard, Safe colours and High contrast. It **filters** the colour schemes listed and changes no scheme. Each scheme belongs to one level, worked out from its palette file (`palettes.access_level`): `level: AAA` is High contrast; otherwise a `colour_vision` claim makes it Safe colours; otherwise it is Standard. The card appears only when the edition's palettes fall into more than one level. The filter is CSS (`:has` on the checked radio), so it needs no script.
  - **Colour schemes:** each offered palette as a small picture of itself (a top bar, a tile, a card with two lines of text and the accent), drawn from that palette's own colours. `palettes.css` carries them as `--pv-*` custom properties on `.preview[data-palette]`, in light and both dark cases, whatever palette the page is in. The names come from the palette's `names`, a `palette_<id>` message, or the id, in each language of the pair. A level with a single scheme says so.
  - **Regional forms:** a segmented control per language that has varieties.
  - The controls are hidden until `app.js` runs; the language toggle works without it.
  - `app.js` keeps preferences version 3: `appearance`, `palette`, `picks` (the palette last picked at each level) and the varieties. The level shown is the level of the saved palette. Choosing a level returns to the scheme last picked in it, or else the first the level lists; a remembered pick from another level, or one the page does not offer, is ignored. Versions 1 and 2 still read.
- **About page** (`about_page` in the edition): an optional standalone page, `about.html`, outside the group and topic tree. It maps each language it is written in to `{ "title", "lede", "sections": [{ "title", "body": [paragraph, {"list": [...]}] }] }`. A group of radio buttons, styled as a toggle at the top right of the page, shows one language at a time, the first of the pair first, with no script. Each language ends with a link to the Sources page. When the edition has it, every page gets an About link (the information icon) in the rail above the settings gear, and the Settings page lists it. The title comes from the interface message `about` or a pack's `ui.about`. `about` is a reserved page name.
- **Linked tiles** (`"links": ["slug"]` on a group in `structure.json`): the group shows a tile for a page that lives in another group, after its own tiles. The page stays in the one group that lists it in `pages` (that group is its Back and trail), so a shared page such as days or places is written once. A link must name an existing page that the group does not list itself. A link never keeps a group alive: a group with no pages of its own is dropped from a channel, and a link to a held-back page is dropped. Linked tiles are not repeated in `tree.json`.

### Pack fields

- `code`: a lower-case BCP 47 tag (`fr`, `zh-hant`, `cy-gwent`). It must match the folder name.
- `name`: the language's English name. `names`: optional `{ "<locale>": "<name written in that locale>" }`, used when the interface is in that locale.
- `dir`: `ltr` (default) or `rtl`.
- `ui`: the language's own interface wording. `endonym` (the language's name for itself) is required. Every other key is optional and overrides the framework catalogue for this language (see below).
- `commentary_lang`: the language the pack's notes, intros and boxes are written in. Default: the interface language. Stretches in `{{double braces}}` are in the pack's own language.
- `varieties`: regional or other variants (`id`, `name`, `short`) that concepts can tag their `forms` with.
- `sources`: where the texts come from, each with an accepted licence. See `ASSETS.md`.

### Edition fields

- `languages`: every pack to publish. `interface`: the language the interface is in, one of them. `default_pair`: the two languages shown first.
- `home.headline` needs a text for each language of the default pair. `home.lede` and `home.about` are optional, per language.
- `palettes`: optional list of palette ids to offer, which must include `default`. Omit it to offer every palette available (the framework's and the project's).
- `storage`: optional name under which the browser keeps this site's saved choices (default: the edition name as a slug). Two sites on one origin must not share it.
- `fonts`: stylesheet URLs linked before the framework stylesheet (the English–Welsh project lists none, since it serves its fonts itself). `stylesheets`: stylesheets of the project (files in `static/`) linked after it. Both accept `https://` URLs or `.css` files only. The framework itself links nothing external, so a project that lists no URL makes no third-party request.

## Navigation: tiles, the top bar and the rail

The design is in `docs/mockups/navigation-mockup.png` and is **mobile first** (see `PHILOSOPHY.md`): the base styles are for a phone held in one hand, and `min-width` queries widen them.

**The frame** around every page:

- a **title bar** across the full width, with the title and, on every page below home, the **trail** (Home > group > topic, with the second language shown on wider screens);
- a narrow **rail** below it, down the side: **search** at the top (hidden until `search.js` runs, then it opens the lookup card), **Back** beneath it on every page below home, and the **Settings** gear at the foot;
- the page: a grid of tiles for the home page and for a group, a reading column for a topic.

**Tiles.** The home page shows the groups as large tiles, each an icon on a coloured tile with its name in both languages beneath. A group opens its own page, `group-<id>.html` (generated, one per group), with a tile for each topic. Tiles carry no counts. A topic opens its phrase tables, with its sections as jump links and the previous and next links at the foot. A tile with no icon holds its name instead. Groups with no published topic have no tile and no page, so a held-back group appears only in the development channel. `group-` is a reserved start for topic names, and a group id must be safe in a file name (lower case letters, digits, hyphens).

**Going back.** The Back button in the rail goes up one level: topic to group, group to home. Settings goes to home, and How to use the app and Sources go to Settings, where they are listed under *About this app*.

**Edit order** (`assets/arrange.js`, and the spanner in the rail, which is hidden until the script runs). On the home page and on a group page the tiles can be put in another order. Turning edit order on shows the tiles as icons only, on the screen's surface shade, with a bar that reads *Drag a tile to move it, or tap one and tap where it goes*, and *Save order* and *Reset*. A tile is moved by dragging it over another, or by tapping it and tapping where it goes. With a tile picked up, the arrow keys move it along, and Escape puts it back. Save order (or the spanner again) keeps the order on this device; leaving the page without saving drops the changes. Reset puts the screen back in its default order, and Settings has *Reset tile layouts* for every screen at once.

The order is kept under `<site>:order` in localStorage, separate from the preferences, as `{"v":1,"screens":{"index":["…"]}}`. A screen's list names its tiles by their ids (`data-tile` on each tile, the group id or the page slug), so a saved order survives a change to a tile's labels. Names the screen no longer has are dropped, and a tile added in a later release goes at the end in its default place. The tiles are moved in the page itself, not with CSS `order`, so the reading order, the focus order and the arrow keys agree. While edit order is on, `nav.js` leaves the keys and the swipe alone. A saved order is applied before the first paint: the head hides the tiles only when one is waiting (`data-arrange-pending`), and `arrange.js` removes that as soon as it has put them in order.

**Keys, dragging and sliding** (`assets/nav.js`, which makes no request and stores nothing; every link works without it):

- On a grid, Up and Down move between tiles in reading order, Home and End jump to the ends, **Right opens** the focused tile (so does Enter, since a tile is a link) and **Left or Backspace goes back**. In a right-to-left page Right and Left swap. Arrow keys are left alone inside form controls.
- **Going in slides.** A page reached from its parent (a tile tapped, not the pager, a reload or Back) slides in from the side the reading runs from. Each page records its parent in `data-parent` on `<html>`, and a few lines in the head (`Site.document`) compare it with the referrer before the first paint, so the card never flashes into place first. The title bar and the rail stay still: only the page moves.
- **Pages slide side by side.** Where the browser can animate a move between two pages of the site (cross-document view transitions: Chrome and Edge 126 and later, Safari 18.2 and later), the old page is kept on screen while the new one loads, and the two slide together as if they sat next to each other: going in, the old page leaves toward the start and the new one arrives from the end; going back (the Back button, the keys, the drag or the browser's own back) the reverse, mirrored in a right-to-left page. A script in the head of every page works out the direction from the page it came from (`navigation.activation`): its own parent means going in, one of its own tiles means going back, and anything else (the pager, another site, a reload) plays nothing. Only the page is named for the transition, so the title bar and the rail stay still. Elsewhere the older slide-in above is used, and the head script leaves it off where this works. A drag that is let go hands the page to the browser from wherever the finger left it. With reduced motion set there is no slide. Still to check by hand on a phone, in both reading directions.
- **Going back drags.** Dragging the page with the reading direction (right in a left-to-right page) moves it with the finger, and on letting go it either leaves in a short slide and goes back, or springs back. It leaves when dragged past 35% of the width, or flicked quickly (over 0.5px/ms, at least 40px). The drag starts once the touch is clearly sideways (at least 1.5 times as wide as tall, past 10px), so vertical scrolling is untouched, and a drag the wrong way, with more than one finger, or from within 20px of a screen edge (the system's own back gesture) is ignored. The Back button, Left and Backspace leave the same way. A plain click on Back is intercepted for the slide, while ctrl, command, shift and middle clicks stay ordinary links. With reduced motion set, there is no slide: it simply goes back.
- The stylesheet sets `touch-action: pan-y pinch-zoom` on the page so horizontal movement reaches the drag, and `overflow-x: clip` on the frame so a page off screen cannot make it scroll sideways. A slide in leaves no transform behind (the animation fills `backwards` only), so it cannot override the drag.
- Tiles are links named in both languages, so a screen reader reads both. The trail and the grid have labels from interface messages. Nothing on screen shows the outline's numbers.
- `how-to.html` ("How to use the app") is generated from interface messages and explains all of this. `how-to`, `settings`, `sources` and `index` are reserved names.

**The map of the site** (`tree.py`) is written to `tree.json`: group, page, section, word, each with an internal address (`1`, `1.2`, `1.2.3`, `1.2.3.4`), both labels with their language and direction, and an address on a page (every row of a page has an `id`, so a word can be linked to). Nothing on screen reads it today, and it is precached for offline use. The search card reads `dictionary.json` instead (below).

**Search and the lookup card** (`search.js`, `Site.search_card`, `dictionary.py`). Every page holds a shut, hidden card (`#search-card`, `inert`) after the page, with its messages and the language pair in `data-` attributes, so a language never appears in the script. The search button in the rail is hidden until the script loads and then reveals the card's layer. Opening slides the card out from behind the rail (a clipping layer, `visibility` and a transform, mirrored in right-to-left with `--slide`), reads `dictionary.json` once, focuses the field and lists results as the person types. Each result is a word with its translation (every regional form, joined with `/`), linking to the word's row on its first page (`slug.html#section.concept`, the `id` of the row), and under it a sub-item link for every topic it is in. Topics whose title matches are listed beneath under a heading. Words found on the page being browsed (a topic, or all the pages of a group on a group page) are listed first, each page-first so its link lands on that page's row, then a separator headed "Other results" (the message `search_other`) and the rest; the page lists its pages in the card's `data-scope`, empty on the home, settings and other pages, where there is no separator. Within each part, ranking: the whole text, the start of the text, the start of a word, then anywhere, and every match that had to ignore marks after those. The card is dismissed by Escape, the Close button, a tap outside it, or following a link (which closes it at once, so the page that leaves has no card on it); `/` opens it from the keyboard, Down and Up move through the results, and Enter follows the first. The keys inside the card are left alone by `nav.js`. Results are built with `textContent`, never `innerHTML`. A target row gets the surface colour (`:target`). The matching functions need no page and are tested under Node (`tests/search.test.js`).

**Icons** (`icons.py`) are the project's, in `icons/<name>.svg`, named with `"icon"` on a group or a page. The framework ships only three interface icons, `ui-icons/search.svg`, `ui-icons/arrow--left.svg` and `ui-icons/settings.svg`. Every file is checked as a **safe subset of SVG** (shapes and groups with geometry and presentation attributes; no scripts, styles, links, event handlers or `url()` references, no DOCTYPE), then rewritten as one line of markup that takes the text colour, is hidden from screen readers (the label beside it says the same thing) and is **inlined**, so a page makes no request for an icon and the icon follows the palette. A build fails naming the file for an unsafe icon or an `icon` with no file. Record each icon set and its licence in `ASSETS.md`.

## Themes and palettes

The framework colours the interface from data, so appearance and colour-blindness support are built in and a project can extend them.

**What the visitor can choose** (on the **Settings** page, linked from the menu; the controls appear once the script runs and are remembered in this browser only):

- *Appearance*: same as the device (default), light, or dark.
- *Colours*: a palette. The framework ships four: `default`, `high-contrast`, `red-green-safe` (for protanopia and deuteranopia) and `blue-yellow-safe` (for tritanopia).

The two choices are independent, so every palette has a light and a dark variant. The page sets `data-theme` (light or dark, absent when following the device) and `data-palette` (absent for the default) on `<html>` before first paint.

**A palette** is a JSON file of ten colour roles (`bg`, `surface`, `ink`, `muted`, `rule`, `rule-strong`, `accent`, `star`, `tile`, `on-tile`) for `light` and for `dark`. `tile` is the background of a topic tile and `on-tile` the icon drawn on it. Colours are written in OKLCH (`oklch(0.5 0.17 258)`), where equal steps in lightness look equal, or as OKLab or `#rrggbb`. The build converts them to sRGB hex, reducing chroma where a colour is outside sRGB, and writes `palettes.css`. `style.css` sets no colour of its own.

```json
{
  "names": { "en": "Sepia" },
  "notes": "Where the colours came from, what was derived and why.",
  "level": "AA",
  "colour_vision": ["protan", "deutan"],
  "light": { "bg": "oklch(0.95 0.03 85)", "surface": "oklch(1 0 0)", "ink": "...", "muted": "...", "rule": "...", "rule-strong": "...", "accent": "...", "star": "..." },
  "dark": { }
}
```

**Promises the build checks.** A palette that breaks one fails the build, naming the file:

- Text (`ink`, `muted`, `accent`) on `bg` and on `surface` meets the `level`: WCAG contrast 4.5:1 for `AA` (the default) or 7:1 for `AAA`, which also needs `rule-strong` at 3:1 against `bg`.
- The icon on a tile (`on-tile` on `tile`) is a graphic, so it needs 3:1 at level `AA` and 4.5:1 at `AAA`.
- The light variant has a light background and the dark variant a dark one, so `color-scheme` is truthful.
- For each kind in `colour_vision` (`protan`, `deutan`, `tritan`), the colours are simulated (Machado et al. 2009) and the text contrast must still hold, and the accent must stay at least 0.12 away in OKLab from `ink` and from `muted`, so the accent never relies on hue alone. The `default` palette does not claim this, and fails the red–green check if it does.

These checks catch mistakes. They do not replace asking people who see colour differently.

**Extending.**

- Add `palettes/<id>.json` to a project. It is offered to visitors automatically, or list the ids the edition should offer in `palettes`.
- A project palette names itself in `names`, per interface language. A framework palette's name is an interface message (`palette_<id>` with hyphens as underscores), so it can be translated like any other. With no name for the interface language, the English name is shown, then the id.
- A project file named `default.json` (or any other framework id) replaces the framework's palette of that name. A project that wants its own baseline colours replaces `default`.
- Roles are fixed by the framework stylesheet. A project that needs another colour adds its own custom property in its own stylesheet and sets it per palette there.

`notes` is free text for provenance. The installed app's toolbar colour and splash background (`theme_color`, `background_color` in the manifest, and the `theme-color` tag) come from the `default` palette's light accent and background, so a project that recolours `default` recolours the installed app too. Icons are project files and are not recoloured.

Also handled: Windows forced-colours mode keeps the current-page marker and the compass visible.

## Interface messages

Every word the framework shows is a message in `phrasebook/messages/en.json`, with a key such as `skip_to_content`. A text is looked up in this order, and the language it was actually found in is kept:

1. the `ui` table in the language's pack,
2. a catalogue `phrasebook/messages/<locale>.json`, if the framework ships one,
3. each of those again for the parent tag (`zh-hant`, then `zh`),
4. finally English, which is complete.

A fallback is never disguised: English text inside another interface is rendered as `<span lang="en">`, with `dir` if the directions differ.

- **Placeholders** such as `{first}` are checked against the English message, so a translation cannot lose or invent one. The build fails on a mismatch.
- **Plurals** (no shipped message needs one today; a search will) are tables of CLDR categories: `{ "one": "{n} entry", "other": "{n} entries" }`. The category comes from the rules of the language the message is written in (`plural.py`). A translation must give exactly the forms its language uses (Welsh: zero, one, two, few, many, other).
- **Word order and punctuation** belong to the message: the pair label (`{first} → {second}`), page titles, list patterns, the full stop after the figure description.
- **Names of languages and licences**: a language writes its own name in `endonym`. Licences with a proper name (CC BY 4.0) keep it; plain-words licences ("Public domain") are messages.

To localise the interface for a language, add the keys to its pack's `ui`. To ship a catalogue for everyone, add `phrasebook/messages/<locale>.json`.

## Conventions followed

| Area | What the framework does |
|---|---|
| Language tags | BCP 47, lower case. Script and region subtags are allowed (`zh-hant`). Used in `lang`, in CSS selectors and in file names. |
| `lang` and `dir` | `<html>` carries the interface language, and `dir` when it is right to left. Any text in another language is wrapped with `lang`, plus `dir` where the direction differs, relative to the text around it, including commentary in a third language. |
| Direction | The stylesheet uses logical properties only (`margin-inline-start`, `text-align: start`), mirrors the menu arrow, and swaps the notch insets for right-to-left. A test fails if a physical property returns. The compass drawing stays a map: east is on the right. |
| Messages | Keyed catalogue, fallback chain, placeholders, CLDR plurals, list patterns, no sentences built from fragments. |
| Unicode | All content is checked to be in normal form C (one letter, one code point, so `ŵ` is always U+0175). Invisible bidirectional controls are rejected: set `dir` instead. Files are UTF-8. |
| Identifiers | Concept ids are language-neutral keys, never display text. Class names name roles (`l1`, `l2`), not languages. |
| Fonts and scripts | The framework has only system font stacks. Fonts are the project's choice (`fonts`, `stylesheets`) and must be open-licence (see `ASSETS.md`). |
| Privacy | No external request unless an edition lists one. Saved choices live in this browser only, under a key named by the edition so sites on one origin stay apart. |

## Not implemented yet

Be aware of these before relying on the framework for a language that needs them.

- **Number formatting.** Counts are written as plain Western digits, with no grouping separators and no locale digit shapes (Arabic-Indic, Devanagari). Counts in a phrasebook stay small, so this is harmless today.
- **Plural rules** exist for the languages listed in `plural.py` and cover whole numbers only. Add a row to support another language. The build says so when a message needs rules that are missing.
- **Collation and search.** Entries are in curated order, so nothing is sorted. Search compares in normal form C and folds case with each term's own language (`toLocaleLowerCase(lang)`, never ASCII lower-casing), then again with combining marks removed, so a regional form finds its concept and a query typed without accents still finds a word that has them, ranked after the exact matches. See section 3 of the app's `docs/TODO.md` (the cydymaith repository).
- **Interface language needs a pack.** `interface` must be one of the edition's languages. An interface language with no phrases cannot be chosen yet.
- **One interface per build.** The interface language is fixed at build time. A switchable interface would need a catalogue in the page and a script.
- **Variety names and short labels** (`North`, `N`) are commentary text in the pack's `commentary_lang`, not catalogue messages.
- **Hyphenation, line breaking and vertical or ruby text** are left to the browser. Languages that need more (Thai word breaks, vertical Mongolian) need project CSS and testing by a speaker.
- **Palettes are checked by arithmetic, not by people.** Contrast and simulated colour-blindness distances are tested, but no one has used the palettes on a real screen, in sunlight, or with a colour-vision deficiency. A palette may also be chosen automatically from `prefers-contrast` in future; today the visitor chooses.
- **The tiles and the frame are checked by tests and in headless Edge, not by people.** The key and swipe moves are unit tested, and a real browser has confirmed the layout at phone and desktop widths and the arrow keys on a grid. Nobody has yet used swipes on a phone, TalkBack or VoiceOver with it, or looked at it right to left.
- **No browser check yet.** The right-to-left layout and the phone layout are built from logical properties and tested for structure, but nobody has looked at them in a real browser.
- **BCP 47 is only pattern-checked.** The code is not looked up in the IANA registry.

## Adding a language to a project

1. `packs/<code>/pack.json`: copy another pack, set `code`, `name`, `dir`, `ui.endonym`, group titles, and `sources`.
2. `packs/<code>/pages/<slug>.json` for the pages you can fill. Partial coverage is fine.
3. Add the code to `languages` and to `home.headline` in an edition.
4. Add `ui` words (`home`, `main_menu`, `sources`, `phrasebook`) so the labels beside the pair are in that language. Without them they show in English, marked `lang="en"`.
5. If you also translate the interface, add the rest of the keys to `ui`, with plural forms for your language. For a language not in `plural.py`, add its rule first.
6. Run the tests.

## Starting a new translator

1. Copy the `cydymaith` repository's `content/gair-wrth-air/` to `content/<new-name>/`, or start from the fixture in `tests/fixture.py`.
2. Replace the packs, pages, structure and edition. Keep `static/` for your fonts and typography.
3. `python3 build.py dist --project content/<new-name>`. If it is the only folder in `content/`, no flag is needed.
4. To publish separately, copy the framework files listed at the top into the new repository.
