"""Key words: the few words of a row that carry its meaning, marked so the two languages can be matched by eye.

A concept may list `keys` in its pack, such as ["Glaw", "gwynt"], and the other language lists the words that match them in
the same order, ["rain", "wind"]. The first key of each language is drawn in the first key colour, and so on, up to MAX_KEYS.
A key may be None to leave a colour unused in a row, so a word can keep the same colour from row to row: ["Glaw", None, "law"]
draws the first and third colours. The text itself stays plain, so search, grading and the dictionary never see the keys.
"""

import re
import unicodedata

MAX_KEYS = 3


def fold(text):
    return unicodedata.normalize("NFC", text or "")


def find(text, keys):
    """[(start, end, n)] for each key that appears in `text` as a whole word, n counting from 0: the first stretch for each key
    that does not overlap one already taken, ignoring case. A key that is not found is left out."""
    text = fold(text)
    taken, found = [], []
    for n, key in enumerate(keys):
        if key is None:
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(fold(key)) + r"(?!\w)", re.IGNORECASE)
        for hit in pattern.finditer(text):
            if all(hit.end() <= a or hit.start() >= b for a, b in taken):
                taken.append((hit.start(), hit.end()))
                found.append((hit.start(), hit.end(), n))
                break
    return sorted(found)


def missing(texts, keys):
    """The keys that appear in none of `texts`."""
    return [key for n, key in enumerate(keys) if key is not None and not any(n in {m[2] for m in find(t, keys)} for t in texts)]


def problem(keys, texts):
    """Why `keys` cannot be used with the concept whose forms are `texts`, or None if they can."""
    if (
        not isinstance(keys, list)
        or not 1 <= len(keys) <= MAX_KEYS
        or all(k is None for k in keys)
        or any(k is not None and (not isinstance(k, str) or not k.strip()) for k in keys)
    ):
        return f"'keys' must be a list of 1 to {MAX_KEYS} non-empty texts, where null leaves a colour unused"
    words = [fold(k).casefold() for k in keys if k is not None]
    if len(set(words)) != len(words):
        return "'keys' repeats a word"
    lost = missing(texts, keys)
    if lost:
        return f"'keys' names {', '.join(repr(k) for k in lost)}, which is not a whole word of the text (or overlaps another key)"
    return None
