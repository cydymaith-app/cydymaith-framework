"""Interface messages: every word the framework itself shows, kept out of the code.

A message has a key ("skip_to_content") and a text per locale. Texts come from, in order:
  1. the language pack's own "ui" table (so a project can word the interface for its language),
  2. a catalogue shipped with the framework, phrasebook/messages/<locale>.json,
  3. each in turn for the parent tag (zh-hant, then zh),
  4. finally the English catalogue, which is complete and is the source of truth for the keys.

Every lookup also returns the language the text was actually written in, so a fallback to English inside
an interface in another language is marked lang="en" instead of being passed off as that language.

Text may hold {placeholders}. A message that depends on a count is a table of CLDR plural categories
({"one": "{n} entry", "other": "{n} entries"}) and the category comes from the rules of the message's own language.
Placeholders are checked against the English catalogue, so a translator cannot break a message by mistake.
Numbers are written as plain digits; locale digit shapes and grouping are not implemented (see docs/FRAMEWORK.md).
"""
import html
import json
import pathlib
import re

from . import plural
from .errors import ContentError

ENGINE_MESSAGES = pathlib.Path(__file__).resolve().parent / "messages"
PLACEHOLDER = re.compile(r"\{(\w+)\}")
PACK_ONLY_KEYS = ("endonym",)  # a language's name for itself: pack data, not an interface message


def _placeholders(template):
    forms = template.values() if isinstance(template, dict) else [template]
    return [set(PLACEHOLDER.findall(f)) for f in forms]


class Messages:
    def __init__(self, packs, engine_dir=ENGINE_MESSAGES):
        self.engine = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(pathlib.Path(engine_dir).glob("*.json"))}
        if "en" not in self.engine:
            raise ContentError("the framework needs messages/en.json")
        self.packs = {code: pack["meta"].get("ui", {}) for code, pack in packs.items()}
        self.used = set()  # keys requested so far; the tests use it to find dead and missing messages

    # -- lookup

    def has(self, key):
        """Whether the framework catalogue has this message (the English catalogue holds every key)."""
        return key in self.engine["en"]

    def chain(self, locale):
        """(language, table) pairs to try, most specific first, ending with the English catalogue."""
        parts = locale.split("-")
        out = []
        for i in range(len(parts), 0, -1):
            loc = "-".join(parts[:i])
            out.append((loc, self.packs.get(loc, {})))
            out.append((loc, self.engine.get(loc, {})))
        out.append(("en", self.engine["en"]))
        return out

    def lookup(self, locale, key):
        for lang, table in self.chain(locale):
            if key in table:
                return table[key], lang
        raise KeyError(f"no interface message {key!r}")

    def format(self, locale, key, n=None, html_mode=False, **params):
        """The message for `locale`, filled in. Returns (text, language the text is written in).

        With html_mode the message text is escaped and the params are inserted as they are (already HTML).
        Without it nothing is escaped, and the caller escapes the result.
        """
        template, lang = self.lookup(locale, key)
        self.used.add(key)
        if isinstance(template, dict):
            if n is None:
                raise ValueError(f"message {key!r} depends on a count")
            template = template.get(plural.category(lang, n), template["other"])
        out = []
        for i, piece in enumerate(PLACEHOLDER.split(template)):
            if i % 2:
                out.append(str(n if piece == "n" else params[piece]))
            else:
                out.append(html.escape(piece) if html_mode else piece)
        return "".join(out), lang

    def join(self, locale, items):
        """A list in prose, using the locale's list patterns: "a", "a and b", "a, b and c"."""
        if len(items) == 1:
            return items[0]

        def two(key, first, second):
            return self.format(locale, key, first=first, second=second)[0]

        if len(items) == 2:
            return two("list_two", *items)
        result = two("list_end", items[-2], items[-1])
        for item in reversed(items[1:-2]):
            result = two("list_middle", item, result)
        return two("list_start", items[0], result)

    # -- validation

    def validate(self):
        """Check every catalogue against the English one. Raises ContentError naming the table at fault."""
        en = self.engine["en"]
        for key, template in en.items():
            if isinstance(template, dict) and "other" not in template:
                raise ContentError(f"messages/en.json: plural message {key!r} needs an 'other' form")
        tables = [(f"messages/{loc}.json", loc, t) for loc, t in self.engine.items() if loc != "en"]
        tables += [(f"packs/{code}/pack.json ui", code, t) for code, t in self.packs.items()]
        for where, loc, table in tables:
            for key, template in table.items():
                if key in PACK_ONLY_KEYS and where.startswith("packs/"):
                    if not isinstance(template, str) or not template:
                        raise ContentError(f"{where}: {key!r} must be non-empty text")
                    continue
                if key not in en:
                    raise ContentError(f"{where}: unknown message {key!r}")
                self.validate_message(where, loc, key, template, en[key])

    def validate_message(self, where, loc, key, template, original):
        if isinstance(original, dict) != isinstance(template, dict):
            kind = "a table of plural forms" if isinstance(original, dict) else "plain text"
            raise ContentError(f"{where}: message {key!r} must be {kind}")
        allowed = set().union(*_placeholders(original))
        if isinstance(template, dict):
            try:
                wanted = plural.categories(loc)
            except KeyError:
                raise ContentError(f"{where}: no plural rules for {loc!r}; add them to phrasebook/plural.py")
            if set(template) != set(wanted):
                raise ContentError(f"{where}: message {key!r} needs exactly the plural forms {', '.join(wanted)}")
            texts = list(template.values())
        else:
            texts = [template]
        for text in texts:
            if not isinstance(text, str) or not text:
                raise ContentError(f"{where}: message {key!r} has an empty or non-text form")
        for found in (p for t in texts for p in [set(PLACEHOLDER.findall(t))]):
            if found - allowed:
                raise ContentError(f"{where}: message {key!r} uses unknown placeholders: {', '.join(sorted(found - allowed))}")
            if not isinstance(template, dict) and found != allowed:
                raise ContentError(f"{where}: message {key!r} must use exactly the placeholders: {', '.join(sorted(allowed)) or 'none'}")
