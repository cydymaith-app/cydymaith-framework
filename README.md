# Cydymaith framework

A small static-site generator for multilingual phrasebooks: a navigation tree, one page per topic, two languages side by side, installable and usable offline. It contains no language and no phrases. A **project**, kept in its own repository, supplies those.

The first project is [Cydymaith am iaith](https://github.com/cydymaith-app/cydymaith) (English and Welsh), which includes this repository as a git submodule.

## Using it

Requires Python 3.12 or later. There are no run-time dependencies; formatting the code needs [black](https://black.readthedocs.io/) (`pip install -r requirements-dev.txt`). Node 20 or later is optional and only runs the tests for the small browser scripts.

```sh
python3 build.py dist --project path/to/project   # write a project's site to dist/
python3 build.py --grades --project path/to/project   # print how demanding each group, page and section is (builds nothing)
python3 -m unittest discover -s tests -v          # run every test, on a made-up neutral project
python3 -m black .                                 # format the Python (CI runs `black --check .`)
```

A project is a `content/<project>/` folder (`structure.json`, `pages/`, `packs/<code>/`, `editions/`, and optional `palettes/`, `icons/` and `static/`). Its own repository adds this one as a submodule (`git submodule add https://github.com/cydymaith-app/cydymaith-framework.git framework`) and has a short `build.py` that puts `framework/` on the path and calls `phrasebook.cli.main(projects_dir=<its content/ folder>)`.

The file formats, the conventions (BCP 47 tags, `lang` and `dir`, logical CSS, keyed messages with CLDR plurals and fallback, Unicode normal form C), what is not done yet, and how to start another translator are in [docs/FRAMEWORK.md](docs/FRAMEWORK.md). Licences for the assets are in [docs/ASSETS.md](docs/ASSETS.md). This repository has no to-do list of its own: the framework's features and the general features it enables are section 3 of the `docs/TODO.md` in the [cydymaith](https://github.com/cydymaith-app/cydymaith) repository that uses it.

## Grading your content

Every group, page and section has a **level** from 1 (beginner) to 3 (advanced), so that tiles and sections can be ordered from simple to advanced, or the reverse for more advanced users. You do not write the levels: the framework **works them out from what each one holds**, and you step in only where it gets one wrong.

- **The rule.** A single word is easier than a short phrase, and a short phrase easier than a sentence, so the level follows the size of a typical entry: the median number of words in the language being heard (the first language of the edition's `default_pair`). Under 1.5 words is level 1, under 2.5 is level 2, and more is level 3. *north* is level 1; *in the north* and *it will be sunny tomorrow* come after it.
- **Check it.** `python3 build.py --grades --project path/to/project` prints every group, page and section with its level, its median and how many entries it was worked out from. It builds nothing. Read it as a learner would: simple things first, complex ones following.
- **Correct it.** Where the rule is plainly wrong, add `"level": 1`, `2` or `3` to the group (in `structure.json`), page or section (in `pages/<slug>.json`). The report stars it and says what the rule would have given. Keep these few, say why in a test, and have a fluent speaker review the grades with the rest of the content.
- **Tune it.** For a language that does not fit, an edition can set `"grading": {"language": "...", "bounds": [1.5, 2.5]}`. The framework counts words by white space, so for a language written without spaces set the bounds to suit or set the levels by hand.
- **Order the tiles and sections by it.** The build writes the level on every tile and section (`data-level`), and the Settings page offers **Default** (as written, which stays the default), **Simplest first** and **Most advanced first**, once the levels differ somewhere. A screen whose tiles a person has arranged themselves keeps their order, and the same level keeps the written order. The tiles and sections are moved before the page is painted (`assets/order.js`) and in the copy of a page that slides in, so nothing is seen moving. Translate the `order_*` messages in each language's pack.

The reference, with the rules for what counts as a word, how a group and a page are graded, and the errors the build gives, is in [docs/FRAMEWORK.md](docs/FRAMEWORK.md#grading-how-demanding-a-tile-or-section-is).

## The promises

No sign-up, no accounts, no ads, no tracking, no payments, no addictive features, and no request to any other site. Tests fail if a build breaks them.

## Licence

Code: [MIT](LICENSE). The interface icons are Apache-2.0, see [docs/ASSETS.md](docs/ASSETS.md).
