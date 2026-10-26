# The framework

`phrasebook/` is a small static-site generator for multilingual phrasebooks. It contains no language and no phrases. A **project** (a folder under `content/` in the repository that uses it) supplies those. *Cydymaith am iaith* (English and Welsh, with north and south Welsh forms) is the first project, in its own repository, [`cydymaith`](https://github.com/cydymaith-app/cydymaith), which holds this framework as a git submodule in `framework/`.

To make another translator, create a repository with a `content/<project>/` folder and add this one as a submodule (`git submodule add <url> framework`). Its `build.py` puts `framework/` on `sys.path` and calls `phrasebook.cli.main(projects_dir=<its content/ folder>)`; see the `cydymaith` repository for a working example. No framework code changes are needed.

```
phrasebook/                 the framework
  cli.py content.py site.py messages.py plural.py figures.py errors.py colour.py palettes.py icons.py tree.py channels.py dictionary.py
  messages/en.json          every word the framework shows itself (the source of truth for the keys)
  palettes/                 the framework's colour palettes (OKLCH, light and dark each)
  assets/                   style.css, app.js (preferences), order.js (tiles and sections in order), nav.js (keys and swipes), arrange.js and search.js, copied to every site
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
python3 build.py --grades                   # print how demanding each group, page and section is (builds nothing)
```

**Theme screenshots.** `--screenshots` takes one phone-sized picture of every offered palette in its light and its dark variant, each of one example page: the first topic that has a drawing, since it shows the most of the colours (the accent, the star, text and rules). That is 8 pictures for the English and Welsh project, and takes about a minute and a half, so it is a step of its own, not part of every build. The site is copied with the theme set the way the settings page sets it and the page's scripts taken out, and `docs/screenshots/README.md` is written as a gallery. The folder is generated, so git ignores it. A headless Chrome, Chromium or Edge is needed for this step only: it is found from the `PHRASEBOOK_BROWSER` environment variable (a path or a name), then the usual names on the `PATH`, then the usual install places, and the build says so if there is none. Run it again after changing a palette or the layout.

## Project files

| File | What it holds |
|---|---|
| `structure.json` | Navigation groups and page order. A group may name an `icon`, a `level` and a `layout` (`tiles`, the default, or `one-page`; see *One-page groups*). Language neutral. |
| `pages/<slug>.json` | A page skeleton: sections and the ids of their **concepts**. No words. May name a `figure`, an `icon`, a `level` and `related` topics; a section may name a `level` too (see *Grading* and *Related topics*). |
| `packs/<code>/pack.json` | One language: `code`, `name`, `names`, `dir`, `ui`, `groups`, `sources`, `varieties`, `commentary_lang`. |
| `packs/<code>/pages/<slug>.json` | That language's title, lede, default `source`, an optional `more` note, and per section a title, optional `intro` and `box` commentary, and one entry per concept. `more` is a list of body blocks as in an About section (a paragraph, `{"list"}`, `{"quote"}`, `{"links": [{"text", "href"}]}`, `{"share"}`). It closes the topic, after the related row, from the first language of the pair that has one; use it to point to a fuller source. |
| `packs/<code>/help.json` | Optional. That language's text for the help book: `chapters` and `features`, keyed by id. Overrides the framework's English in `phrasebook/help/en.json` where it names the same id. See *The help book*. |
| `editions/<name>.json` | `name`, `languages`, `interface`, `default_pair`, `home` copy, `fonts`, `stylesheets`, and optionally `grading`. |
| `palettes/<id>.json` | Optional. A colour palette added to the framework's own, or one with a framework id that replaces it. See *Themes and palettes*. |
| `icons/<name>.svg` | Optional line icons. A group in `structure.json` or a page skeleton names one with `"icon": "<name>"`. See *Navigation*. |
| `static/` | Files copied to the site as they are. They may add to the framework's files or replace them. |

A concept is `{ "text": "...", "note": "...", "source": "id" }` or `{ "forms": [{ "text": "...", "varieties": ["north"] }] }`. A concept missing from a pack is simply not shown for that language.

- **`also`** (optional, a list of texts in the pack's own language): other forms the word is heard as, such as a changed beginning or a plural. They show as small chips in a full-width row under the word, headed by the message `also_heard`, and are added to `dictionary.json` as `also`, so search finds the word from any of them. Search shows only the word's own terms, never the `also` forms. A form may not repeat the word or itself.
- **`order`** (optional, on a section in a pack, commentary in the pack's `commentary_lang`): one line saying what order the rows run in, such as "lightest to heaviest". Shown under the section heading as the message `section_order`.
- **Listen-first rows.** The first language of the pair is the one heard, so its text leads (large, strong, left in a left-to-right page) and the second sits at the end of the same row, muted. The pair comes from the edition's `default_pair`, so a project for people who listen to a language puts that language first.
- **Accordions** (`Site.fold`): the Settings groups, the About sections and the topics of a one-page group (see *One-page groups*) are `details` elements whose summary is the heading, so they open and close with no script, by tap, Enter or Space, and a screen reader announces them as expandable. The controls inside stay in the page, with their state, while a card is shut, so a choice still works and `:has` filters still apply. On Settings only the first group, Accessibility and appearance, starts open. On About the first section starts open, and a project can choose with `"open": true` or `false` on each section of `about_page` (once any section says, the rest start shut). The arrow is drawn in CSS, takes the muted colour, and needs no icon file. Not yet done: remembering which are open, an open-all control, and showing the current choice in a shut card's summary.
- **Settings page** (`Site.settings_page`): the choices are grouped by what they are for, in accordions (above), and each group holds its choices as headed sub-sections (`Site.subsection`: an `h3` under the group's `h2`, set apart by a rule). A Cy|En toggle at the top right (radios styled as a toggle, so no script) shows the page in one language of the pair at a time, the first language first; every label is rendered once per language of the pair (`both()`), and the stylesheet shows one. The controls and their state exist once. The groups, in this order:
  - **Accessibility and appearance** (`Site.look_group`, open to begin with), holding **View mode**, **Accessibility** and **Colour schemes** in that order, the last two only where the edition offers a choice. The heading messages are `group_look` and `view_mode`.
  - **Order and tile layout** (`Site.order_group`), holding **Order** (simple to advanced, offered only where the levels differ; see *Grading*) and **Tile layout** (put every screen's tiles back in their default order; hidden until `arrange.js` runs). The group is always there, because Tile layout always is. The heading messages are `group_order`, `order_title` and `reset_orders_title`.
  - **Regional forms**, one group per language that has varieties.
  - A project with no About page also gets a group listing How to use the app and Sources (see *About page*).
  The choices inside them:
  - **View mode:** three icon tiles, light, dark and same as device (Carbon `light`, `asleep`, `screen`). The preference is still called `appearance`.
  - **Accessibility:** a three-way control, Standard, Safe colours and High contrast. It **filters** the colour schemes listed, and choosing a level switches to the scheme last picked at that level, or the first it lists (see `app.js`). Each scheme belongs to one level, worked out from its palette file (`palettes.access_level`): `level: AAA` is High contrast; otherwise a `colour_vision` claim makes it Safe colours; otherwise it is Standard. The card appears only when the edition's palettes fall into more than one level. The filter is CSS (`:has` on the checked radio), so it needs no script.
  - **Colour schemes:** each offered palette as a small picture of itself (a top bar, a tile, a card with two lines of text and the accent), drawn from that palette's own colours. `palettes.css` carries them as `--pv-*` custom properties on `.preview[data-palette]`, in light and both dark cases, whatever palette the page is in. The names come from the palette's `names`, a `palette_<id>` message, or the id, in each language of the pair. A level with a single scheme says so.
  - **Regional forms:** a segmented control per language that has varieties.
  - The controls are hidden until `app.js` runs; the language toggle works without it.
  - `app.js` keeps preferences version 3: `appearance`, `palette`, `picks` (the palette last picked at each level) and the varieties. The level shown is the level of the saved palette. Choosing a level returns to the scheme last picked in it, or else the first the level lists; a remembered pick from another level, or one the page does not offer, is ignored. Versions 1 and 2 still read.
- **About page** (`about_page` in the edition): an optional standalone page, `about.html`, outside the group and topic tree. It maps each language it is written in to `{ "title", "lede", "sections": [{ "title", "body": [paragraph, {"list": [...]}] }] }`. A group of radio buttons, styled as a toggle at the top right of the page, shows one language at a time, the first of the pair first, with no script. Each language ends with links to *How to use the app* and the Sources page: the About page is the one place those two are linked from, so the home page and the Settings page do not repeat them. When the edition has it, every page gets an About link (the information icon) in the rail above the settings gear, and the how-to and sources pages sit under About (their Back and trail go to About, not Settings). The title comes from the interface message `about` or a pack's `ui.about`. `about` is a reserved page name.
  - **Body blocks:** a paragraph (a plain string), `{"list": [...]}`, `{"quote": "text"}` (a large statement with the accent rule), `{"links": [{"text", "href"}]}` (an `https://` address or a page of the site such as `sources.html#x`) and `{"share": "https://address"}` (the address as a link, with a Share button that the script reveals only where the browser can share or copy; it makes no request).
  - **Held-back sections:** an About section may carry `"status": "development"`. The release channel leaves it out, drops a language left with no sections, and drops the page if no language is left. The development channel includes everything.
  - **Remembered language:** the Cy|En toggles (Settings and About) remember the language chosen, as `lang` in the preferences (version 4; versions 1 to 3 still read). Without the script the first language of the pair shows.
  - **Home page:** when the edition has the page, the home page's closing line is only the edition's `home.about` note, with no links (and no line at all if there is no note). **An edition with no About page** keeps the links where they were, so nothing becomes unreachable: the home page's closing line links to Sources, and Settings lists *How to use the app* and Sources under *About this app*; the how-to and sources pages then sit under Settings.
- **Related topics** (`"related"` in a page skeleton): an end topic can link to other topics as a row of tiles, so a reader goes from one to another without going back up the tree. `"related": ["where#landscape", "patterns"]` lists the topics to link to, each a page or a `page#section`. The row (`Site.related_tiles`, headed `related` in both languages) follows the topic's sections and comes before the pager. A tile is the tile of the page it opens, with that page's icon, and is named for the section if one is named (so *On the coast* sits in a tile called *Landscape*) and for the page if not. Declared where it is wanted, one way: a topic that should link back says so itself, so seven weather topics do not leave their target with seven tiles. The build fails, naming the file, for a list that is not a list of names, a page related to itself, a page or a section that does not exist, a `#` with no section, a section id that cannot travel in an address, or a page named twice (one tile each). A target held back from the release is left out of that release, and a section that is not published leaves the page's tile pointing at the page.
  - **It is a list of tiles that no one arranges.** The `ul` has `data-tiles`, so the tiles slide in, take the arrow keys and carry `data-level`, but it names no `data-order`, so `arrange.js` and `order.js` leave it as written.
  - **Back returns to the topic it was followed from.** A related tile carries `data-related`. When `nav.js` opens one it adds the topic's file to the address (`#slide=none;from=rain.html;at=landscape`), and the page's head script reads it, keeps it in the history entry (`history.state.from`, which a reload keeps), and takes it out of the address (`where.html#landscape`). `nav.js` points the Back link at that topic, so Back slides back to it, and any other way of opening the page keeps the up-the-tree Back. The trail and the page's own address stay as they are. Where the entry names something that is not a page of this site, it is ignored.
  - **No jump at the handover.** The copy of the page that slides in is scrolled to the section, as far as the page is long enough, and the stylesheet gives every section that has an `id` a `scroll-margin-top` so the real page puts it just under the title bar. The head script scrolls to the section once the page is there.
  - Where the other page cannot be shown, the plain way still carries the marks (and asks the browser's own move to stand down, since it must change the address).
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
- `grading`: optional `{"language", "bounds"}` for how tiles and sections are graded from beginner to advanced; see *Grading*.
- `contact`: optional email address for problem reports (see *The help book*). Without it the help sheet offers only *What's this?*.
- `storage`: optional name under which the browser keeps this site's saved choices (default: the edition name as a slug). Two sites on one origin must not share it.
- `fonts`: stylesheet URLs linked before the framework stylesheet (the English–Welsh project lists none, since it serves its fonts itself). `stylesheets`: stylesheets of the project (files in `static/`) linked after it. Both accept `https://` URLs or `.css` files only. The framework itself links nothing external, so a project that lists no URL makes no third-party request.

## The help book

Help is a book under About: a chapter is a page, `help-<id>.html`, and a feature is a section of it, `help-<id>.html#<feature>`. `how-to.html` is its contents. The plan is in `app-help-plan.md`, and what is still missing is in `app-help-todo.md`.

- **`phrasebook/help.py`** holds the order of the chapters and the anchor of each feature, and no words. An anchor is lower case letters, digits and hyphens, is unique in the book, and is never renamed, because links will name it (an icon's `data-help`, a search result). A feature may name `"requires"`: `about` (the edition has an About page), `varieties` (a language has regional forms), `palettes` (more than one colour scheme), `access` (schemes at more than one accessibility level), `levels` (tiles or sections of more than one level), `related` (a topic links to others) or `contact` (the edition has an address for reports). Without its condition a feature is left out, and a chapter with no feature left is dropped.
- **The words** are in `phrasebook/help/<code>.json` (the framework's own, English complete) and in a pack's `help.json`, the pack's over the framework's. `{ "chapters": { id: { "title", "lede" } }, "features": { id: { "title", "body", "keys", "touch" } } }`. `body` is a list of the blocks of an About section; `keys` and `touch` are one-line answers for the keyboard and for touch and buttons, shown as two labelled lines. An entry makes sense alone, because it will be shown without the rest of its page. A language with no entry shows the English one, marked `lang="en"`. Because an id may appear once on a page, only the first article's sections use the plain anchor as their id; the others take the language as a suffix (`tiles-en`), and every section names its feature in `data-feature`, which is what a script should look for. A link to `#tiles` therefore lands on the first language's article. The build fails for a feature with no English text, and for text under an id the book does not have.
- **A chapter page** has an article in each language of the pair that has help of its own, one shown at a time with the About page's toggle (so it works with no script and the choice is remembered), or just English where neither does. Its trail is Home, About (Settings where the edition has no About page), How to use the app, the chapter; Back goes to the contents. Chapters have Previous and Next links when there is more than one.
- **The build** prints help coverage beside word coverage: `help: en 8/8, cy 0/8`.
- **The help button and the icons** (`Site.help_icon`, `assets/help.js`). A question-mark button (`#help-toggle`) sits in the rail directly above Edit order, so it is the 4th from the bottom on a tile screen, and is on every page that has at least one help icon. It is hidden until `help.js` runs. Pressing it, or Escape, sets or clears `data-helping` on the document element and `aria-pressed` on the button; nothing is stored, so every page begins plain. A help icon is a link, `help-<chapter>.html#<feature>`, marked `data-help="<chapter>#<feature>"` and named by the message `help_icon`; the stylesheet hides it until the page is helping, so without the script it never shows and the book is still reached from About. An icon is made only for a feature the edition shows (`help_chapter_of`). For now icons are on: the trail (an icon at the end of the title bar, in the bar's own text colour, sized so it does not make the bar taller), the tile grids, a topic's jump links, section Order lines, the pager, the Related row, and on Settings the view mode, accessibility, colour schemes, order, tile layout and regional forms. An anchor must never equal an id in the frame (the rail button is `help-toggle`, not `help-button`, for that reason).
- **The sheet** (`Site.help_card`, `assets/help.js`). With the script, pressing a revealed icon does not follow its link: it opens a modal sheet (`#help-card`, a dialog in a dimmed layer; a bottom sheet on a phone, centred on a wide screen) and makes the rest of the page `inert`. The sheet offers **What's this?** first and **Report a problem** second. It has the same Cy|En toggle as Settings and About (radios styled as a toggle, sharing the site's remembered language, so it works with no extra script): both languages of every label are in the page and one is shown, and the text loaded by *What's this?* is placed by language (`place` in `help.js`) so the toggle switches it too; a section in neither language of the pair stays on show. Status messages wait in the page, hidden, and the script shows one (`say`); it never writes text into the page itself. The sheet closes with a small x (an icon button named in both languages), Escape or a tap on the dimmed page, and focus returns to the icon. Modified clicks (ctrl, shift, middle) stay ordinary links.
  - **What's this?** fetches the chapter page for that feature (one request, to a `help-<chapter>.html` of the site itself, which the service worker has cached, so it works offline) and shows only the sections marked `data-feature="<feature>"`, one for each language the chapter is written in, with ids removed. *Read the whole chapter* is a link to the anchor.
  - **Report a problem** is offered only where the edition has `contact`, an email address (an edition field, checked as one plain address). It shows a box for what is wrong and a read-only box of what the app adds: `Page`, `Help`, `Built` (the build date) and `Languages` (the pair, and `rtl` where it applies), most important first, **at most 256 characters** (`MAX_CONTEXT` in `help.js`; longer is a sign the feature is getting too complex, so cut the context and do not raise the limit). *Open email* is a `mailto:` link to the person's own mail app with the subject and the text filled in; *Copy* copies `To`, `Subject` and the text. The app sends nothing, and nothing is stored. The address sits in the page in two pieces (`data-contact-user`, `data-contact-host`) and is joined only by the script, so it is not a line a scraper would take.
  - nav.js and arrange.js leave the keys alone inside the sheet, as they do inside the search card.

## Navigation: tiles, the top bar and the rail

The design is in `docs/mockups/navigation-mockup.png` and is **mobile first** (see `PHILOSOPHY.md`): the base styles are for a phone held in one hand, and `min-width` queries widen them.

**The frame** around every page:

- a **title bar** across the full width, with the title and, on every page below home, the **trail** (Home > group > topic, with the second language shown on wider screens);
- a narrow **rail** below it, down the side: **search** at the top (hidden until `search.js` runs, then it opens the lookup card), **Back** beneath it on every page below home, and the **Settings** gear at the foot;
- the page: a grid of tiles for the home page and for a group, a reading column for a topic.

**Tiles.** The home page shows the groups as large tiles, each an icon on a coloured tile with its name in both languages beneath. A group opens its own page, `group-<id>.html` (generated, one per group), with a tile for each topic. Tiles carry no counts. A topic opens its phrase tables, with its sections as jump links and the previous and next links at the foot. A tile with no icon holds its name instead. Groups with no published topic have no tile and no page, so a held-back group appears only in the development channel. `group-` is a reserved start for topic names, and a group id must be safe in a file name (lower case letters, digits, hyphens).

**Going back.** The Back button in the rail goes up one level: topic to group, group to home. Settings and About go to home, and How to use the app and Sources go to About (or to Settings, listed there under *About this app*, in an edition with no About page).

**Edit order** (`assets/arrange.js`, and the spanner in the rail, which is hidden until the script runs). On the home page and on a group page the tiles can be put in another order. Turning edit order on shows the tiles as icons only, on the screen's surface shade, with a bar that reads *Drag a tile to move it, or tap one and tap where it goes*, and *Save order* and *Reset*. A tile is moved by dragging it over another, or by tapping it and tapping where it goes. With a tile picked up, the arrow keys move it along, and Escape puts it back. Save order (or the spanner again) keeps the order on this device; leaving the page without saving drops the changes. Reset puts the screen back in its default order, and Settings has *Reset tile layouts* for every screen at once.

The order is kept under `<site>:order` in localStorage, separate from the preferences, as `{"v":1,"screens":{"index":["…"]}}`. A screen's list names its tiles by their ids (`data-tile` on each tile, the group id or the page slug), so a saved order survives a change to a tile's labels. Names the screen no longer has are dropped, and a tile added in a later release goes at the end in its default place. The tiles are moved in the page itself, not with CSS `order`, so the reading order, the focus order and the arrow keys agree. While edit order is on, `nav.js` leaves the keys and the swipe alone. A saved order is applied before the first paint and nothing is hidden while it waits, by `order.js` (see *Putting tiles and sections in order*), which also orders the copy of a page that `nav.js` slides in, so tiles arrive where they will stay and do not move when the real page takes their place. It leaves two things on each list for `arrange.js`: `data-written`, the tiles in the order they are written (a saved order is merged into it), and `data-default`, the order the screen has when nothing is saved for it (as written, or by level if the person asked for that), which is where **Reset** goes. Leaving edit order without saving goes back to the saved order, or to `data-default` if there is none.

**Keys, dragging and sliding** (`assets/nav.js`; it sets no cookies and stores nothing, its one request is for a page of the site itself, and every link works without it):

- On a grid, Up and Down move between tiles in reading order, Home and End jump to the ends, **Right opens** the focused tile (so does Enter, since a tile is a link) and **Left or Backspace goes back**. In a right-to-left page Right and Left swap. Arrow keys are left alone inside form controls.
- **Two pages slide as one.** Opening a topic (a tile tapped, or Right) and going back (the Back button, Left, Backspace or a drag) are the same move: this page and the page it goes to sit edge to edge and slide together, as in a phone's home screens. Going in, the page leaves toward the start and the new one arrives from the end; going back, the reverse; a right-to-left page mirrors both. `nav.js` reads the other page once (`fetch`, for an address it has checked is this site's, served from the service worker's cache when there is one, so it works offline), copies its `<main>` into a clipping layer (`.peek`, with no ids or radio names, `inert` and `aria-hidden`) that waits one page-width away, and moves the two with one transform each (`places()`, tested under Node, keeps them exactly one width apart). The rail is given a background while they move so pages go under it, and the title bar stays still. When they have landed the real page loads with `#slide=none` in the address (the mark can also carry `;from=<page>` and `;at=<section id>`, for a related topic: see *Related topics, for developers*), which its head script removes and which stops the browser's own transition, so nothing plays twice. The pointer going down on a tile asks for its topic early, and the page above is asked for once the page has settled, so the other page is nearly always at hand; a tap waits at most 300ms for it.
- **Going back drags.** Dragging the page with the reading direction (right in a left-to-right page) moves it with the finger, and the page above comes in beside it as the two follow the finger. On letting go the two either finish the slide and go back, or spring back together. They finish when dragged past 35% of the width, or flicked quickly (over 0.5px/ms, at least 40px), taking the time that is left of the slide. The drag starts once the touch is clearly sideways (at least 1.5 times as wide as tall, past 10px), so vertical scrolling is untouched, and a drag the wrong way, with more than one finger, or from within 20px of a screen edge (the system's own back gesture) is ignored. A plain click on Back is intercepted for the slide, while ctrl, command, shift and middle clicks stay ordinary links. With reduced motion set there is no slide: it simply goes.
- **When the other page cannot be shown** (no `fetch`, an answer that is not a page, or no answer within a moment) the move is left to the browser or to the page that arrives. Where the browser can animate a move between two pages of the site (cross-document view transitions: Chrome and Edge 126 and later, Safari 18.2 and later), it keeps the old page on screen while the new one loads and slides the two; a script in the head of every page works out the direction from the page it came from (`navigation.activation`): its own parent means going in, one of its own tiles means going back, and anything else (the pager, another site, a reload) plays nothing. Elsewhere the page that arrives slides in alone: `nav.js` puts `#slide=forward` or `#slide=back` in the address, the head script reads it before the first paint (so the card never flashes into place first) and adds `slide-in` or `slide-back`, and takes the mark out of the address again. The referrer is not used. The same head script reads `#slide=none`.
- The stylesheet sets `touch-action: pan-y pinch-zoom` on the page so horizontal movement reaches the drag, and `overflow-x: clip` on the frame so a page off screen cannot make it scroll sideways. A slide in leaves no transform behind (the animation fills `backwards` only), so it cannot override the drag, and a page restored from the browser's cache (`pageshow`) is put back with no layer or transform left.
- Tiles are links named in both languages, so a screen reader reads both. The trail and the grid have labels from interface messages. Nothing on screen shows the outline's numbers.
- `how-to.html` ("How to use the app") is the contents of the help book (see *The help book*). `how-to`, `settings`, `sources` and `index` are reserved names, and so is any name that starts `help-` (as with `group-`).

**The map of the site** (`tree.py`) is written to `tree.json`: group, page, section, word, each with an internal address (`1`, `1.2`, `1.2.3`, `1.2.3.4`), both labels with their language and direction, and an address on a page (every row of a page has an `id`, so a word can be linked to). Nothing on screen reads it today, and it is precached for offline use. The search card reads `dictionary.json` instead (below).

**Search and the lookup card** (`search.js`, `Site.search_card`, `dictionary.py`). Every page holds a shut, hidden card (`#search-card`, `inert`) after the page, with its messages and the language pair in `data-` attributes, so a language never appears in the script. The search button in the rail is hidden until the script loads and then reveals the card's layer. Opening slides the card out from behind the rail (a clipping layer, `visibility` and a transform, mirrored in right-to-left with `--slide`), reads `dictionary.json` once, focuses the field and lists results as the person types; a delete symbol at the end of the field (shown only while it holds text) clears it and keeps the focus there. Each result is a word with its translation (every regional form, joined with `/`), linking to the word's row on its first page (`slug.html#section.concept`, the `id` of the row), and under it a sub-item link for every topic it is in. Topics whose title matches are listed beneath under a heading. Words found on the page being browsed (a topic, or all the pages of a group on a group page) are listed first, each page-first so its link lands on that page's row, then a separator headed "Other results" (the message `search_other`) and the rest; the page lists its pages in the card's `data-scope`, empty on the home, settings and other pages, where there is no separator. Within each part, ranking: the whole text, the start of the text, the start of a word, then anywhere, and every match that had to ignore marks after those. The card is dismissed by Escape, the close x, a tap outside it, or following a link (which closes it at once, so the page that leaves has no card on it); `/` opens it from the keyboard, Down and Up move through the results, and Enter follows the first. The keys inside the card are left alone by `nav.js`. Results are built with `textContent`, never `innerHTML`. A target row gets the surface colour (`:target`). The matching functions need no page and are tested under Node (`tests/search.test.js`).

**Icons** (`icons.py`) are the project's, in `icons/<name>.svg`, named with `"icon"` on a group or a page. The framework ships only three interface icons, `ui-icons/search.svg`, `ui-icons/arrow--left.svg` and `ui-icons/settings.svg`. Every file is checked as a **safe subset of SVG** (shapes and groups with geometry and presentation attributes; no scripts, styles, links, event handlers or `url()` references, no DOCTYPE), then rewritten as one line of markup that takes the text colour, is hidden from screen readers (the label beside it says the same thing) and is **inlined**, so a page makes no request for an icon and the icon follows the palette. A build fails naming the file for an unsafe icon or an `icon` with no file. Record each icon set and its licence in `ASSETS.md`.

### One-page groups

A group with `"layout": "one-page"` in `structure.json` is read as **one page**, the group's own (`group-<id>.html`), instead of a grid of tiles that each open a page. Use it where a group has many small topics that a reader moves between often (the weather forecast).

- **Each topic is an accordion** (`Site.one_page`, using `Site.fold`), shut until opened. Its summary is the topic's tile: the icon and the name in both languages, as an `h2`. Its body is the topic as its own page would show it: the lede, the figure, the sections (their headings an `h3`, boxes an `h4`), the related row and the `more` note.
- **The topics have no pages of their own.** Every address of one points into the group's page: `group-<id>.html#topic-<slug>` for the topic, `#<section>` for a section and `#<section>.<concept>` for a word (`Site.href`, and `content.address` for the dictionary). Related tiles, a group's `links`, search results and the search's list of topics (the dictionary's `topic`) all use them. A related tile between two topics of the same one page is left out: it is an accordion away.
- **An address inside a shut accordion opens it**: the head script for an address nav.js carries (`;at=`), `reveal()` in `nav.js` on arrival and on `hashchange` (a search result on the same page), and the copy of a page that slides in.
- **Order.** The accordions carry their topics' levels (`data-level`) and are what Settings' *Simplest first* and *Most advanced first* put in order, here on the page; the sections inside carry no level and keep their written order. `order.js` takes `DETAILS` as well as `SECTION`.
- **The page is read like a topic:** it is in the Previous and Next run in place of its topics (`Site.run`), as wide as a topic, and has no grid to arrange. The group's `links` follow the accordions as a row of tiles under the Related heading.
- **The build checks** that `layout` is `tiles` or `one-page`, and that on one page no section id is used twice or starts with `topic-`, since each is an id of the one page.
- Not yet done: remembering which accordions are open, an open-all control, and a help-book entry.

### Related topics, for developers

How the pieces fit, for someone changing or extending the feature. For the content author's side (what to write, what it looks like) see the *Related topics* bullet above.

**The address mark.** Opening a page by `nav.js` goes by an address with a mark in the fragment, which the arriving page's head script (`Site.document`, the first `<script>`) reads before the first paint and removes. Its grammar is `#slide=<forward|back|none>` followed by any of `;from=<page.html>` and `;at=<id>`, and nothing else is accepted (the pattern is `^#slide=(forward|back|none)((?:;(?:from|at)=[A-Za-z0-9._-]+)*)$`, so a stray fragment is left alone as an ordinary anchor):

| Part | Written by | Read by | What it does |
|---|---|---|---|
| `slide=none` | `nav.js`, once the two pages have slid together | head script | sets `data-slide="none"` so the browser's own move stands down |
| `slide=forward` / `back` | `nav.js`, when the other page could not be shown | head script | adds `slide-in` or `slide-back`, only where the browser cannot slide pages itself |
| `from=<page.html>` | `nav.js`, for a tile with `data-related` | head script, then `nav.js` | stored as `history.state.from`; `nav.js` points the Back link at it |
| `at=<id>` | `nav.js`, from the `#id` in the tile's `href` | head script | the address becomes `page.html#id` again, and the page is scrolled to it once parsed (`scrollIntoView`) |

**Why `history.state`.** The head script cannot leave the topic in the address (it would show, and be shared), and `nav.js` may not store anything. The history entry is per page visit, survives a reload and the browser's own Back and Forward, and is gone when the tab is, which is the lifetime Back-to-where-you-came-from wants. `cameFrom()` in `nav.js` accepts only a bare file name of this site (`^[a-z0-9-]+\.html$`); anything else in the entry is ignored, so a crafted state cannot send Back anywhere else.

**Where the code is.**

- `phrasebook/content.py`: `check_related` validates the list (called from `validate`, after every skeleton is known).
- `phrasebook/site.py`: `Site.related_tiles` builds the row; `Site.tile(..., related=True)` puts `data-related` on the link; `Site.content_page` places the row after `ORDER_HOOK`; `Site.document` holds the head script.
- `phrasebook/assets/nav.js`: the pure functions `marked`, `anchorOf` and `cameFrom` (exported and tested), then `thisPage`, `openTile`, `travel` and `stageBeside` (which scrolls the copy to `[data-at]`, as far as the page is long enough).
- `phrasebook/assets/style.css`: `section[id]{scroll-margin-top:...}` so a landing section sits under the title bar; the copy is placed with the same gap.
- `phrasebook/messages/en.json`: `related`, the heading and the list's name.

**Things to keep true.**

- A related row is `data-tiles` with no `data-order`. `arrange.js` and `order.js` select `[data-tiles][data-order]`, so the row is never arranged or put in level order; do not add `data-order` to it.
- `nav.js` makes one request, for a page of this site; a related tile adds none. The `#id` in a `href` has to match `^[A-Za-z0-9._-]+$` to travel in the address, which `check_related` enforces for section ids that are linked to.
- Where the browser slides pages itself and the other page cannot be shown, a tile that needs a mark still goes by `none`, so the browser's move does not race the head script's clean-up of the address (`toward()` in `nav.js`).
- The head script, like the order hook, must not contain a closing brace pair: the project check for unrendered templates rejects `}}` anywhere in a page.

**Tests.** `tests/test_tree.py` (`RelatedTopicsTests`): the row, its labels, the held-back and unpublished cases, the validation messages, the head script's pattern. `tests/nav.test.js`: `marked`, `anchorOf`, `cameFrom` and the order of the Back wiring. `tests/test_framework.py`: the `related` message is used. The project's own links are checked in `tests/test_project.py`.

## Grading: how demanding a tile or section is

Each group, page and section has a **level** from 1 (beginner) to 3 (advanced), so that tiles and sections can be put in order from simple to advanced, or the other way round. The level is **worked out from what the group, page or section holds**, and can be set by hand where the rule is plainly wrong. The build writes it on every tile and section (`data-level`), the Settings page offers the order (below), and `python3 build.py --grades` reports it.

**The rule.** A learner finds a single word easier than a short phrase, and a short phrase easier than a sentence. So the level follows the size of a *typical* entry: the **median number of words** in the language being heard (the first language of the edition's `default_pair`, or `grading.language`). The median and not the mean, so one stray single word in a section of sentences does not pull it down, nor one long entry in a section of words push it up.

| Level | The median entry is | Under | Looks like |
|---|---|---|---|
| 1 | words | 1.5 words | *north*, *sunny*, *drizzle* |
| 2 | short phrases | 2.5 words | *in Wales*, *light rain*, *yellow warning* |
| 3 | sentences, or longer phrases | any more | *in the north*, *it will be sunny tomorrow* |

A **word** is a piece of text between white space that holds a letter or a digit, so `north-east` is one word, a lone dash is none, and the `{{ }}` marks that show a stretch of the pack's own language are not counted. An entry that has only regional `forms` is counted by its first form. A concept the pack does not have is left out, not counted as empty. A section is graded from its own entries, a page from every entry on it, and a group from every entry on the pages it lists (not the pages it only links to), so a page's level is not the average of its sections' levels. With nothing to measure, the level is 1.

**Setting a level by hand.** Add `"level": 1`, `2` or `3` to a group in `structure.json`, or to a page or one of its sections in `pages/<slug>.json`. It wins over the rule for that group, page or section only; it does not change the level of what holds it. Do it where the rule is plainly wrong and say why in a comment in the project's tests (see below), and keep such overrides few: if many are needed, change the rule's `grading` settings instead. The usual case is an item that is written as several words but is one thing to learn, such as a day of the week in a language that writes *Day Monday*.

**Putting tiles and sections in order** (`assets/order.js`, the `order` preference in `app.js`, `Site.order_card`). On the **Settings** page a card offers three choices: **Default** (as written, which is the listen-first order and is what everyone gets until they choose), **Simplest first** and **Most advanced first**. The card appears only where the levels differ somewhere, so it is never a control that does nothing; it is `order_title`, `order_hint` and `order_written`, `order_simple` and `order_advanced` in the message catalogue, and a project translates them in each language's pack (the Welsh drafts want a fluent speaker's review). The choice is the `order` field of the preferences, `"written"`, `"simple"` or `"advanced"`; anything else counts as written.

- **What moves.** The tiles on the home page and on a group page (a group's tiles by the group level, a page's tile by the page level), and the sections of a topic with the "On this page" list that names them (a section by its level). A section with no level of its own, such as a drawing, stays where it is while the others move around it. Within a level the written order is kept (a stable sort), so *Most advanced first* is the levels reversed and not the whole page reversed.
- **A saved order wins.** A screen whose tiles the person has arranged themselves (*Edit order*) keeps their order, and the setting orders only the screens they have not arranged. Reset on a screen goes to the setting's order, and *Reset every screen* in Settings does the same.
- **Before anything is painted.** `order.js` is loaded in the head, like `app.js`, and answers a one-line hook the page runs right after each list of tiles and after a topic's sections (`Site.ORDER_HOOK`, an event `phrasebook:order` on the document, so the script needs no global name). `nav.js` sends `phrasebook:peek` for the copy of a page it is about to slide in, so that arrives in order too and nothing moves when the real page takes its place. Where the script is missing the hook does nothing and everything stays as written.
- **The reading order is the order seen.** The tiles and sections are moved in the page itself, never with CSS `order`, so the reading order, the focus order and the arrow keys agree with what is on screen. The moves (the saved-order rules, which are the same as `arrange.js` and tested to agree, and the stable sort) are pure functions tested under Node in `tests/order.test.js`, which also runs the page part against a small fake page: the setting, a saved order winning, sections and the list going together, blocked or nonsense storage, and a second ask changing nothing.
- **It reads this device's storage and nothing else.** No request, no cookie, and it writes nothing; `app.js` writes the choice.

**The edition's `grading` block** is optional:

```json
"grading": { "language": "cy", "bounds": [1.5, 2.5] }
```

`language` is the language whose words are counted (default: the first language of `default_pair`; it must be one of the edition's languages). `bounds` are the two medians at which level 1 gives way to level 2, and level 2 to level 3: two rising positive numbers. The build fails, naming the file, for anything else. The framework counts words by white space and knows no language, so for a language written without spaces between words (Chinese, Japanese, Thai) the count is not a good measure: set `bounds` to suit, or set the levels by hand.

**Checking the grades.** `python3 build.py --grades [--project DIR] [--edition NAME] [--channel NAME]` prints every group, page and section with its level, its median and how many entries it was worked out from, and builds nothing. It grades what the channel publishes (held-back sections are left out unless `--channel development`). A level set by hand has a star, and a note says what the rule would have given:

```
weather-forecast                   level 2   median  1.5  over 120 entries
  sky                              level 1   median  1.0  over  19 entries
  where
    points                         level 1   median  1.0  over   8 entries
    directions                     level 3   median  3.0  over   5 entries
    days                           level 1*  median  2.0  over   7 entries  (the rule says 2)
```

**Reviewing them.** A level is a judgement about difficulty, so it wants a fluent speaker's review like the rest of the content. Read the report as a learner would: the simple things should come first and the complex ones follow. Where one looks wrong, first ask whether the rule is the problem (a different `bounds` might suit the language), and only then set the level by hand. A project should test the grades it cares about, as the English and Welsh project does in `tests/test_project.py`: that single words come below the phrases built on them, that sentence patterns are level 3, and how many levels are set by hand.

The rule is `grading.py` and has no language in it; `tests/test_grading.py` covers counting, the median, the levels and their bounds, the language heard, regional forms, overrides, the validation messages and the report.

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
| Form actions | Actions on forms and cards are **symbols, not words**, wherever a symbol says it: the reader is scanning words to learn, so the only words on a screen should be the ones being learned. A control with no visible text keeps a name for a screen reader and a tooltip (`aria-label` and `title`, from a message). Search has a close **x** and a delete (backspace) symbol that clears the field; the browser's own clear button is hidden so there is only one. Words stay where a symbol is ambiguous or none exists. Icons are in `phrasebook/ui-icons/`. |
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

1. Copy the `cydymaith` repository's `content/cydymaith/` to `content/<new-name>/`, or start from the fixture in `tests/fixture.py`.
2. Replace the packs, pages, structure and edition. Keep `static/` for your fonts and typography.
3. `python3 build.py dist --project content/<new-name>`. If it is the only folder in `content/`, no flag is needed.
4. To publish separately, copy the framework files listed at the top into the new repository.
