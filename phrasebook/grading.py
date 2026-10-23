"""Grading: how demanding each group, page and section is, from beginner to advanced, worked out from what it holds.

A learner finds a single word easier than a short phrase, and a short phrase easier than a whole sentence. So the grade follows
the size of a typical entry: the median number of words in the language being heard (the first of the edition's `default_pair`,
or the edition's `grading.language`). The median and not the mean, so one stray single word in a section of sentences does not
pull it down, nor one long entry in a section of words push it up.

    level 1  a median under the first bound   words                 north, sunny
    level 2  under the second bound           short phrases         in the north, light rain
    level 3  otherwise                        sentences, longer      it will be sunny tomorrow

The bounds are 1.5 and 2.5 words unless the edition's `grading.bounds` says otherwise. The framework counts words and knows no
language; for a language written without spaces between words it is not a good measure, so set `grading.bounds` for the
edition or set `level` by hand (below).

A group, a page and a section each get a level from the entries they hold: a group from every entry on its listed pages, a
page from every entry on it, a section from its own. Any of them can set `"level": 1`, `2` or `3` in its own file
(a group in structure.json, a page or a section in pages/<slug>.json) to say what the rule gets wrong; that wins, and the report
marks it with a star. The grade is a judgement about difficulty and, like the rest of the content, wants a fluent speaker's review.
"""

LEVELS = 3
BOUNDS = (1.5, 2.5)
LABELS = {1: "words", 2: "short phrases", 3: "sentences"}


def count_words(text):
    """The words in a string: pieces separated by white space that hold a letter or a digit. {{ }} marks are not words."""
    text = text.replace("{{", "").replace("}}", "")
    return len([piece for piece in text.split() if any(ch.isalnum() for ch in piece)])


def entry_text(concept):
    """The text of an entry as heard: a plain string, the `text`, or the first regional form's text. None if it has none."""
    if isinstance(concept, str):
        return concept
    if isinstance(concept, dict):
        if isinstance(concept.get("text"), str):
            return concept["text"]
        for form in concept.get("forms") or []:
            if isinstance(form, dict) and isinstance(form.get("text"), str):
                return form["text"]
    return None


def median(values):
    """The middle of a list of numbers (the mean of the two in the middle when there is an even number); None for none."""
    values = sorted(values)
    if not values:
        return None
    middle = len(values) // 2
    return float(values[middle]) if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


def level_for(typical, bounds=BOUNDS):
    """The level of a section whose typical entry has `typical` words. Nothing to measure is level 1."""
    if typical is None:
        return 1
    for level, bound in enumerate(bounds, start=1):
        if typical < bound:
            return level
    return len(bounds) + 1


def settings(edition):
    """(language, bounds) for an edition: the language whose words are counted, and where the levels break."""
    given = edition.get("grading") or {}
    pair = edition.get("default_pair") or []
    languages = edition.get("languages") or []
    language = given.get("language") or (pair[0] if pair else (languages[0] if languages else None))
    return language, tuple(given.get("bounds") or BOUNDS)


def validate_settings(where, edition):
    """Check an edition's optional `grading` block. Raises ValueError with what is wrong; `where` names the file."""
    given = edition.get("grading")
    if given is None:
        return
    if not isinstance(given, dict) or set(given) - {"language", "bounds"}:
        raise ValueError(f"{where}: 'grading' may hold only 'language' and 'bounds'")
    if "language" in given and given["language"] not in edition.get("languages", []):
        raise ValueError(f"{where}: grading.language {given['language']!r} must be one of the edition's languages")
    if "bounds" in given:
        bounds = given["bounds"]
        ok = isinstance(bounds, list) and len(bounds) == LEVELS - 1
        ok = ok and all(isinstance(b, (int, float)) and not isinstance(b, bool) and b > 0 for b in bounds)
        ok = ok and all(a < b for a, b in zip(bounds, bounds[1:]))
        if not ok:
            raise ValueError(f"{where}: grading.bounds needs {LEVELS - 1} rising positive numbers, such as {list(BOUNDS)}")


def validate_level(where, holder):
    """An optional `level` set by hand on a group, page or section: a whole number from 1 to LEVELS."""
    if "level" not in holder:
        return
    level = holder["level"]
    if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= LEVELS:
        raise ValueError(f"{where}: 'level' must be a whole number from 1 to {LEVELS}, not {level!r}")


def _node(name, sizes, bounds, holder):
    typical = median(sizes)
    computed = level_for(typical, bounds)
    by_hand = "level" in holder
    return {
        "id": name,
        "level": holder["level"] if by_hand else computed,
        "computed": computed,
        "by_hand": by_hand,
        "median": typical,
        "entries": len(sizes),
    }


def grade(raw, edition):
    """Grade a project (as read, and seen through a channel) for an edition.

    Returns {"language", "bounds", "groups": [...]}; each group, page and section is
    {"id", "level", "computed", "by_hand", "median", "entries"}, with "pages" in a group and "sections" in a page.
    """
    language, bounds = settings(edition)
    pack = (raw["packs"].get(language) or {}).get("pages", {})

    def section_sizes(slug, section):
        concepts = (pack.get(slug, {}).get("sections", {}).get(section["id"], {})).get("concepts", {})
        texts = [entry_text(concepts[cid]) for cid in section["concepts"] if cid in concepts]
        return [count_words(text) for text in texts if text is not None]

    groups = []
    for group in raw["structure"]["groups"]:
        pages, group_sizes = [], []
        for slug in group.get("pages", []):
            skeleton = raw["pages"][slug]
            sections, page_sizes = [], []
            for section in skeleton["sections"]:
                sizes = section_sizes(slug, section)
                sections.append(_node(section["id"], sizes, bounds, section))
                page_sizes += sizes
            page = _node(slug, page_sizes, bounds, skeleton)
            page["sections"] = sections
            pages.append(page)
            group_sizes += page_sizes
        node = _node(group["id"], group_sizes, bounds, group)
        node["pages"] = pages
        groups.append(node)
    return {"language": language, "bounds": bounds, "groups": groups}


def levels(graded):
    """The grades as lookups: {"groups": {id: level}, "pages": {slug: level}, "sections": {(slug, id): level}}."""
    found = {"groups": {}, "pages": {}, "sections": {}}
    for group in graded["groups"]:
        found["groups"][group["id"]] = group["level"]
        for page in group["pages"]:
            found["pages"][page["id"]] = page["level"]
            for section in page["sections"]:
                found["sections"][(page["id"], section["id"])] = section["level"]
    return found


def report(graded):
    """The grades as text, one line per group, page and section, for checking them by eye."""
    low, high = graded["bounds"]
    lines = [
        f"Grades by the size of a typical entry: the median words per entry, counted in {graded['language']}.",
        f"Level 1 is words (under {low}), level 2 short phrases (under {high}), level 3 sentences. A star means the level is set by hand.",
        "",
    ]

    def line(depth, node):
        mark = "*" if node["by_hand"] else " "
        typical = "-" if node["median"] is None else f"{node['median']:.1f}"
        note = f"  (the rule says {node['computed']})" if node["by_hand"] and node["level"] != node["computed"] else ""
        label = ("  " * depth + node["id"]).ljust(34)
        lines.append(f"{label} level {node['level']}{mark}  median {typical:>4}  over {node['entries']:>3} entries{note}")

    for group in graded["groups"]:
        line(0, group)
        for page in group["pages"]:
            line(1, page)
            for section in page["sections"]:
                line(2, section)
    return "\n".join(lines)
