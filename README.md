# Cydymaith framework

A small static-site generator for multilingual phrasebooks: a navigation tree, one page per topic, two languages side by side, installable and usable offline. It contains no language and no phrases. A **project**, kept in its own repository, supplies those.

The first project is [Cydymaith am iaith](https://github.com/cydymaith-app/cydymaith) (English and Welsh), which includes this repository as a git submodule.

## Using it

Requires Python 3.12 or later. There are no run-time dependencies; formatting the code needs [black](https://black.readthedocs.io/) (`pip install -r requirements-dev.txt`). Node 20 or later is optional and only runs the tests for the small browser scripts.

```sh
python3 build.py dist --project path/to/project   # write a project's site to dist/
python3 -m unittest discover -s tests -v          # run every test, on a made-up neutral project
python3 -m black .                                 # format the Python (CI runs `black --check .`)
```

A project is a `content/<project>/` folder (`structure.json`, `pages/`, `packs/<code>/`, `editions/`, and optional `palettes/`, `icons/` and `static/`). Its own repository adds this one as a submodule (`git submodule add https://github.com/cydymaith-app/cydymaith-framework.git framework`) and has a short `build.py` that puts `framework/` on the path and calls `phrasebook.cli.main(projects_dir=<its content/ folder>)`.

The file formats, the conventions (BCP 47 tags, `lang` and `dir`, logical CSS, keyed messages with CLDR plurals and fallback, Unicode normal form C), what is not done yet, and how to start another translator are in [docs/FRAMEWORK.md](docs/FRAMEWORK.md). Licences for the assets are in [docs/ASSETS.md](docs/ASSETS.md). This repository has no to-do list of its own: the framework's features and the general features it enables are section 3 of the `docs/TODO.md` in the [cydymaith](https://github.com/cydymaith-app/cydymaith) repository that uses it.

## The promises

No sign-up, no accounts, no ads, no tracking, no payments, no addictive features, and no request to any other site. Tests fail if a build breaks them.

## Licence

Code: [MIT](LICENSE). The interface icons are Apache-2.0, see [docs/ASSETS.md](docs/ASSETS.md).
