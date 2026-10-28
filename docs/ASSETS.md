# Assets and licensing

Everything in this repository is open: code, the interface icons and the colour palettes. Nothing is used under a licence that restricts copying, modifying or redistributing it. A project built with the framework keeps its own record of its fonts, icons, palettes and content in its own `docs/ASSETS.md`, and follows the policy below.

This is a working policy, not legal advice.

## Accepted licences

| Kind | Accepted |
|---|---|
| Public domain | Public domain works, CC0 |
| Code | MIT, BSD, Apache-2.0, ISC |
| Fonts | SIL Open Font License 1.1 |
| Text and data | CC BY 4.0, Open Government Licence v3.0 (UK), and anything above |
| Images and icons | CC0, CC BY, MIT-style icon sets |

## Not accepted

- Non-commercial (NC) or no-derivatives (ND) licences.
- "Free for personal use", "free for non-commercial use", or no stated licence.
- Share-alike licences (CC BY-SA, GPL) for data, because they would force the same licence onto the whole phrasebook. Ask first if a source is valuable enough to justify it.
- Copying from a copyrighted phrasebook or dictionary, even a little at a time.

## Icons in use

| Set | Licence | Source |
|---|---|---|
| IBM Carbon, `@carbon/icons` 11.91.0 | Apache-2.0 | https://carbon-design-system.com, https://github.com/carbon-design-system/carbon |

The eleven Carbon icons below are copied from the npm package `@carbon/icons@11.91.0` (the `svg/32` set) into `phrasebook/ui-icons/` for the framework's own chrome, with the package's Apache-2.0 `LICENSE` beside them. Licence read on 2026-10-21 in the package and in the repository root. Re-check the licence and version before each release.

The paths are unmodified. The only change is a one-line comment added at the top of each file naming the package, version and licence. The build adds `fill="currentColor"` when inlining, because Carbon's files name no fill.

| Icon | Used for |
|---|---|
| `search` | The search button in the side rail |
| `arrow--left` | Back |
| `settings` | The gear |
| `information` | About, above the gear |
| `light` | The light appearance on the settings page |
| `asleep` | The dark appearance |
| `screen` | The appearance that follows the device |
| `tools` | Edit order, on the home page and a group page |
| `chat` | The "Also heard as" label above alternative forms: a speech bubble, "also said as" (it replaced `headphones`, which looked like an audio player) |
| `help` | The help button in the side rail, and the help icons it reveals |
| `close` | The x that closes the help sheet and the search card |
| `backspace` | Clears the search field (drawn for this site, see below) |

- Apache-2.0 needs the licence text kept with copies, and changes stated. The `LICENSE` file is in the icons folder, and a test fails if it goes missing. The licence does not cover IBM's names or trademarks.
- **Drawn for this site:** `backspace`, the delete symbol at the end of the search field, which clears it. Carbon has no backspace key. It is a 32px-grid, 2px round-stroke outline, so it is a different style from the filled Carbon icons and may need redrawing to match. It is the framework's own work, released under the same MIT licence as the code, and carries a comment saying so.
- **The framework ships twelve interface icons** in `phrasebook/ui-icons/`, with the licence beside them. They are chrome, not content, so they live in the framework and a project does not need to supply them. A test fails if anything else appears there (eleven from Carbon and the one above).
- A project's own icons go in its `icons/` folder and are named with `icon` on a group or a page. Each file is checked as a safe SVG subset at build time (shapes only; no scripts, styles, links or references), then inlined, so a page makes no request for an icon.
- Icons are decorative beside their labels, so they are hidden from screen readers.
- **Not yet checked: BBC GEL icon sets.** The BBC's Global Experience Language ([BBC GEL iconography](https://www.bbc.co.uk/gel/features/iconography#licensing)) has alternative icon sets that are free for non-commercial use only. Under the policy above, a non-commercial licence is not accepted, so none of them may be used unless the BBC grants other terms. The page could not be fetched while writing this note, so the wording was not verified.

## Colour palettes in use

| Palette | Where it came from | Licence |
|---|---|---|
| `phrasebook/palettes/*.json` (`default`, `blue-white-red`, `green-white-red`, `green-white-orange`, `red-yellow`, `black-red-gold`, `sepia`, `red-green-safe`, `blue-yellow-safe`, `monochrome`, `high-contrast`) | Written for this project. Values chosen by the author and checked by the build. The five colour schemes start from the nominal colours of a flag, named in each file's `notes`, and are darkened or lightened until the text contrast holds. | Same as the code: MIT |

A project can replace any of these with a palette of its own in its `palettes/` folder, and records where those colours came from in its own `docs/ASSETS.md`.

## Licences for this repository

| Part | Licence |
|---|---|
| Code (`build.py`, `phrasebook/`, `tests/`) | MIT, see `LICENSE` |
| Interface icons | Apache-2.0, the licence file is beside them |
