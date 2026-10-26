"""The help book: chapters of short entries, one per feature, each reachable by a fixed anchor.

This file holds the order and the anchors, and no words. A chapter is a page, help-<id>.html; a feature is a section of it,
help-<id>.html#<feature>, so the rest of the app can link to one feature (an icon's data-help, a search result) and a reader
can be shown just that part. Anchors are never renamed: a renamed anchor breaks every link that names it.

The words come from, in order for each language:
  1. the project's pack, packs/<code>/help.json,
  2. the framework's own catalogue, phrasebook/help/<code>.json,
  3. finally the English catalogue, which is complete and is the source of truth for the anchors.

A catalogue is {"chapters": {id: {"title", "lede"}}, "features": {id: {"title", "body", "keys", "touch"}}}. `body` is a list of the
blocks of an About section (a paragraph, or {"list": [...]}, {"links": [...]}); `keys` and `touch` are optional one-line answers for
the keyboard and for touch and buttons. An entry must make sense alone, because it may be shown without the rest of its page.
"""

import json
import pathlib
import re

from .errors import ContentError

HELP_DIR = pathlib.Path(__file__).resolve().parent / "help"
ANCHOR = re.compile(r"^[a-z][a-z0-9-]*$")
PAGE_PREFIX = "help-"  # generated chapter pages are help-<id>.html
# What a feature can ask of the edition before it is shown: "about" (an About page), "varieties" (a language has regional forms), "palettes" (more than one
# colour scheme), "access" (schemes at more than one accessibility level), "levels" (tiles or sections of more than one level), "related" (a topic links to others), "contact" (the edition has an address for reports).
CONDITIONS = ("about", "varieties", "palettes", "access", "levels", "related", "contact")

# The book, in reading order. Add a chapter here only with its English text; the build refuses a feature with none.
SECTIONS = [
    {
        "id": "finding-your-way",
        "features": [
            {"id": "tiles"},
            {"id": "trail"},
            {"id": "side-bar"},
            {"id": "back"},
            {"id": "pager"},
            {"id": "jump-links"},
            {"id": "keys-and-touch"},
            {"id": "drag-back"},
        ],
    },
    {
        "id": "looking-up-words",
        "features": [
            {"id": "search"},
            {"id": "search-keys"},
            {"id": "search-this-page-first"},
            {"id": "listen-first-rows"},
            {"id": "also-heard"},
            {"id": "regional-forms", "requires": "varieties"},
            {"id": "sources-notes"},
        ],
    },
    {
        "id": "reading-a-topic",
        "features": [
            {"id": "sections-order"},
            {"id": "levels", "requires": "levels"},
            {"id": "related-topics", "requires": "related"},
        ],
    },
    {
        "id": "your-settings",
        "features": [
            {"id": "settings-groups"},
            {"id": "language-toggle"},
            {"id": "view-mode"},
            {"id": "accessibility", "requires": "access"},
            {"id": "colour-schemes", "requires": "palettes"},
            {"id": "order-setting", "requires": "levels"},
            {"id": "reset-tile-layouts"},
            {"id": "what-is-saved"},
        ],
    },
    {
        "id": "arranging-tiles",
        "features": [
            {"id": "edit-order"},
            {"id": "moving-tiles"},
            {"id": "saving-order"},
        ],
    },
    {
        "id": "offline-and-install",
        "features": [
            {"id": "offline"},
            {"id": "install"},
            {"id": "no-script"},
            {"id": "share", "requires": "about"},
        ],
    },
    {
        "id": "using-help",
        "features": [
            {"id": "help-button"},
            {"id": "help-icons"},
            {"id": "report-a-problem", "requires": "contact"},
        ],
    },
]


def check_sections(sections):
    """Raise a ContentError for anchors that are not safe, repeated, or ask for a condition that does not exist."""
    seen = set()
    for chapter in sections:
        for ident in [chapter["id"]] + [f["id"] for f in chapter["features"]]:
            if not ANCHOR.match(ident):
                raise ContentError(f"help: {ident!r} must be lower case letters, digits and hyphens, starting with a letter")
        for feature in chapter["features"]:
            if feature["id"] in seen:
                raise ContentError(f"help: the anchor {feature['id']!r} is used twice")
            seen.add(feature["id"])
            if feature.get("requires") not in (None, *CONDITIONS):
                raise ContentError(f"help: {feature['id']!r} asks for {feature['requires']!r}, which is not one of {CONDITIONS}")
    if len({c["id"] for c in sections}) != len(sections):
        raise ContentError("help: a chapter is listed twice")


class Book:
    """The chapters and the words, in every language that has any."""

    def __init__(self, sections, texts):
        check_sections(sections)
        self.sections = sections
        self.texts = texts  # {code: {"chapters": {...}, "features": {...}}}
        self.check_texts()

    @classmethod
    def load(cls, packs, sections=None, engine_dir=HELP_DIR):
        """Read the framework's catalogues and the packs' own help files into a book."""
        texts = {}
        for path in sorted(pathlib.Path(engine_dir).glob("*.json")):
            texts[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        for code, pack in packs.items():
            own = pack.get("help")
            if own:
                merged = texts.setdefault(code, {})
                for kind in ("chapters", "features"):
                    merged[kind] = {**merged.get(kind, {}), **own.get(kind, {})}
        return cls(SECTIONS if sections is None else sections, texts)

    # -- checks

    def anchors(self):
        return [f["id"] for c in self.sections for f in c["features"]]

    def check_texts(self):
        english = self.texts.get("en")
        if english is None:
            raise ContentError("help: the framework needs help/en.json")
        for chapter in self.sections:
            if chapter["id"] not in english.get("chapters", {}):
                raise ContentError(f"help/en.json: no chapter text for {chapter['id']!r}")
        for anchor in self.anchors():
            if anchor not in english.get("features", {}):
                raise ContentError(f"help/en.json: no text for the feature {anchor!r}")
        known = set(self.anchors())
        chapters = {c["id"] for c in self.sections}
        for code, text in self.texts.items():
            for kind, valid in (("features", known), ("chapters", chapters)):
                for ident in text.get(kind, {}):
                    if ident not in valid:
                        raise ContentError(f"help ({code}): {ident!r} under {kind!r} is not in the book")

    # -- lookups

    def has_text(self, code):
        """Whether the language has any help of its own (an English fallback does not count)."""
        text = self.texts.get(code, {})
        return bool(text.get("features") or text.get("chapters"))

    def entry(self, code, kind, ident):
        """(entry, language it is written in): the language's own, else English."""
        for lang in (code, "en"):
            found = self.texts.get(lang, {}).get(kind, {}).get(ident)
            if found:
                return found, lang
        raise KeyError(ident)

    def visible(self, conditions):
        """The chapters with only the features whose condition holds; a chapter left with none is dropped."""
        out = []
        for chapter in self.sections:
            features = [f for f in chapter["features"] if f.get("requires") is None or f["requires"] in conditions]
            if features:
                out.append({**chapter, "features": features})
        return out

    def coverage(self, codes):
        """{language: (features with text of its own, features in the book)}."""
        anchors = self.anchors()
        return {
            code: (sum(1 for a in anchors if a in self.texts.get(code, {}).get("features", {})), len(anchors)) for code in codes
        }
