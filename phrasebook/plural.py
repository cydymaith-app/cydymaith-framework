"""Plural categories (CLDR cardinal rules) for whole numbers.

A message that depends on a count holds one text per category ("one", "few", ...) and the category is chosen
by the rules of the language the message is written in, not by English rules.

Simplified on purpose: the rules cover non-negative whole numbers only. CLDR also defines "many" categories
for compact decimals and exact millions (French, Spanish, Italian, Portuguese); counts in a phrasebook never
reach them. To support another language, add a row to RULES.
Codes qaa to qtz are reserved for private use. They get the English rule so tests can use made-up languages.
"""
import re

PRIVATE_USE = re.compile(r"^q[a-t][a-z]$")


def _other(n):
    return "other"


def _one(n):
    return "one" if n == 1 else "other"


def _zero_or_one(n):
    return "one" if n in (0, 1) else "other"


def _cy(n):
    return {0: "zero", 1: "one", 2: "two", 3: "few", 6: "many"}.get(n, "other")


def _ga(n):
    if n == 1:
        return "one"
    if n == 2:
        return "two"
    if 3 <= n <= 6:
        return "few"
    if 7 <= n <= 10:
        return "many"
    return "other"


def _gd(n):
    if n in (1, 11):
        return "one"
    if n in (2, 12):
        return "two"
    if 3 <= n <= 10 or 13 <= n <= 19:
        return "few"
    return "other"


def _ar(n):
    if n == 0:
        return "zero"
    if n == 1:
        return "one"
    if n == 2:
        return "two"
    if 3 <= n % 100 <= 10:
        return "few"
    if 11 <= n % 100 <= 99:
        return "many"
    return "other"


def _ru(n):
    if n % 10 == 1 and n % 100 != 11:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "many"


def _pl(n):
    if n == 1:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "many"


# language -> (categories the language uses, "other" always included; function from a whole number to a category)
RULES = {
    "en": (("one", "other"), _one),
    "de": (("one", "other"), _one),
    "nl": (("one", "other"), _one),
    "sv": (("one", "other"), _one),
    "es": (("one", "other"), _one),
    "it": (("one", "other"), _one),
    "fr": (("one", "other"), _zero_or_one),
    "pt": (("one", "other"), _zero_or_one),
    "cy": (("zero", "one", "two", "few", "many", "other"), _cy),
    "ga": (("one", "two", "few", "many", "other"), _ga),
    "gd": (("one", "two", "few", "other"), _gd),
    "ar": (("zero", "one", "two", "few", "many", "other"), _ar),
    "ru": (("one", "few", "many", "other"), _ru),
    "pl": (("one", "few", "many", "other"), _pl),
    "ja": (("other",), _other),
    "zh": (("other",), _other),
    "ko": (("other",), _other),
    "vi": (("other",), _other),
}


def rule(lang):
    """(categories, function) for a language tag. Raises KeyError for a language without rules."""
    base = lang.split("-")[0]
    if base in RULES:
        return RULES[base]
    if PRIVATE_USE.match(base):
        return RULES["en"]
    raise KeyError(base)


def categories(lang):
    return rule(lang)[0]


def category(lang, n):
    return rule(lang)[1](n)
