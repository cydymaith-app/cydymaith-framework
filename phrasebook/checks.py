"""Checks: a sheet of what in a language pack has still to be looked up in a reference book, and a sidecar that records the verdicts.

The developer who is not a fluent speaker can still check single words, genders, plurals and the changes a word goes through
against a printed dictionary or a word list. This module does the bookkeeping:

    python3 build.py --check LANG                       print the sheet: words, entries and notes not yet checked
    python3 build.py --mark LANG SOURCE RESULT WORD...  record a verdict for words (or for entries, written page/section/id)

The record is a **sidecar**: `<project>/checks/<language>.json`. The build never reads it and never ships it, so it cannot change
a site. It holds only verdicts, never text from the source: a source is named by a short id and described once, in `sources`.

    {
      "sources": {"dict": "A printed dictionary, its publisher and edition"},
      "words":   {"milk": {"source": "dict", "result": "ok", "by": "A. Person", "date": "2026-10-30", "note": "north"}},
      "entries": {"rain/rain/a-risk-of-rain": {"hash": "3f2a9c1b04", "source": "dict", "result": "ok", "by": "...", "date": "..."}}
    }

A word is a word wherever it appears, so one verdict covers every entry that uses it. An entry's verdict carries a hash of its
text and its "also heard as" forms; if either changes, the verdict is reported as stale and the entry is back on the sheet.
A verdict says what was found: `ok`, `changed` (the text was corrected to match) or `query` (the source and the content disagree
and someone must decide). `note` is optional, short, and in the developer's own words.
"""

import datetime
import hashlib
import json
import pathlib
import re

from .errors import ContentError

RESULTS = ("ok", "changed", "query")
FIELDS = {"source", "result", "by", "date", "note", "hash"}
NOTE_LIMIT = 200
# a run of letters, with an apostrophe or a hyphen allowed between letters (it's, o'clock and north-east stay whole)
WORD = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)
MARK = re.compile(r"\{\{(.*?)\}\}")


def tokens(text):
    """The distinct words of a text, folded to lower case, in the order they first appear. {{ }} marks are not words."""
    seen = []
    for found in WORD.findall(text.replace("{{", " ").replace("}}", " ")):
        word = found.casefold()
        if word not in seen:
            seen.append(word)
    return seen


def texts_of(concept):
    """Every text an entry shows: the text (or each form's text), then its "also heard as" forms."""
    if isinstance(concept, str):
        return [concept]
    shown = [concept["text"]] if isinstance(concept.get("text"), str) else []
    shown += [f["text"] for f in concept.get("forms") or [] if isinstance(f, dict) and isinstance(f.get("text"), str)]
    return shown + [a for a in concept.get("also") or [] if isinstance(a, str)]


def entry_hash(concept):
    """A short fingerprint of what a check looked at: the texts of an entry, in order."""
    return hashlib.sha1("\n".join(texts_of(concept)).encode("utf-8")).hexdigest()[:10]


def entries(raw, language):
    """Every entry of a language, in reading order: [(key, concept)], the key being page/section/id.

    An entry is only listed once, however many sections show it; a concept the pack does not have is left out."""
    pack = (raw["packs"].get(language) or {}).get("pages", {})
    found, seen = [], set()
    for slug, skeleton in raw["pages"].items():
        for section in skeleton["sections"]:
            have = pack.get(slug, {}).get("sections", {}).get(section["id"], {}).get("concepts", {})
            for cid in section["concepts"]:
                key = f"{slug}/{section['id']}/{cid}"
                if cid in have and key not in seen:
                    seen.add(key)
                    found.append((key, have[cid]))
    return found


# ---------------------------------------------------------------- the sidecar


def path_for(project_dir, language):
    return pathlib.Path(project_dir) / "checks" / f"{language}.json"


def empty():
    return {"sources": {}, "words": {}, "entries": {}}


def load(project_dir, language):
    """The sidecar of a language, validated; an empty one when there is none."""
    path = path_for(project_dir, language)
    if not path.is_file():
        return empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as err:
        raise ContentError(f"{path}: not valid JSON: {err}")
    problem = validate(data)
    if problem:
        raise ContentError(f"{path}: {problem}")
    return {**empty(), **data}


def validate(data):
    """What is wrong with a sidecar, as a sentence; None when it is sound."""
    if not isinstance(data, dict) or set(data) - {"sources", "words", "entries"}:
        return "may hold only 'sources', 'words' and 'entries'"
    sources = data.get("sources", {})
    if not isinstance(sources, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) or not v for k, v in sources.items()
    ):
        return "'sources' maps a short id to a description"
    for part in ("words", "entries"):
        for name, verdict in (data.get(part) or {}).items():
            where = f"{part}/{name}"
            if not isinstance(verdict, dict) or set(verdict) - FIELDS:
                return f"{where}: a verdict may hold only {', '.join(sorted(FIELDS))}"
            if verdict.get("source") not in sources:
                return f"{where}: source {verdict.get('source')!r} is not described in 'sources'"
            if verdict.get("result") not in RESULTS:
                return f"{where}: result must be one of {', '.join(RESULTS)}"
            if not isinstance(verdict.get("by"), str) or not verdict["by"].strip():
                return f"{where}: 'by' says who checked"
            try:
                datetime.date.fromisoformat(verdict.get("date", ""))
            except (TypeError, ValueError):
                return f"{where}: 'date' must be a day written like 2026-10-30"
            note = verdict.get("note", "")
            if not isinstance(note, str) or len(note) > NOTE_LIMIT:
                return f"{where}: 'note' is at most {NOTE_LIMIT} characters, in your own words and not copied from the source"
            if part == "entries" and not verdict.get("hash"):
                return f"{where}: an entry's verdict needs the 'hash' it was made against"
            if part == "words" and name != name.casefold():
                return f"{where}: words are written in lower case"
    return None


# ---------------------------------------------------------------- the sheet


def sheet(raw, language, sidecar):
    """What is left to check. Returns {"words", "stale", "unchecked", "notes", "total"}:

    words      {word: [entry keys]} for every word with no verdict, in the language's own order of first use
    stale      entry keys whose verdict was made against text that has since changed
    unchecked  entry keys with no verdict at all
    notes      {entry key: [marked stretches]} for entries whose note names a word that changes (the {{ }} marks)
    total      (entries, distinct words)
    """
    pack = (raw["packs"].get(language) or {}).get("pages", {})
    words, stale, unchecked, notes, distinct = {}, [], [], {}, set()
    listed = entries(raw, language)
    for key, concept in listed:
        for word in tokens(" ".join(texts_of(concept))):
            distinct.add(word)
            if word not in sidecar["words"]:
                words.setdefault(word, []).append(key)
        verdict = sidecar["entries"].get(key)
        if verdict is None:
            unchecked.append(key)
        elif verdict["hash"] != entry_hash(concept):
            stale.append(key)
        note = concept.get("note") if isinstance(concept, dict) else None
        if isinstance(note, str) and MARK.search(note):
            notes[key] = MARK.findall(note)
    return {
        "words": dict(sorted(words.items(), key=lambda kv: (kv[0].lstrip("'’-"), kv[0]))),
        "stale": stale,
        "unchecked": unchecked,
        "notes": notes,
        "total": (len(listed), len(distinct)),
    }


def report(language, found, limit=3):
    """The sheet as text: counts first, then stale verdicts, then the words with where they are used, then the changes to check."""
    entries_total, words_total = found["total"]
    lines = [
        f"Check sheet for {language}: {len(found['words'])} of {words_total} words and "
        f"{len(found['unchecked'])} of {entries_total} entries have no verdict.",
        "Look each word up in your reference book, then record it with: build.py --mark "
        f"{language} SOURCE ok|changed|query WORD... --by NAME",
        "",
    ]
    if found["stale"]:
        lines += [f"Stale (the text changed after it was checked): {len(found['stale'])}"]
        lines += [f"  {key}" for key in found["stale"]] + [""]
    lines.append(f"Words to look up ({len(found['words'])}), with where they are used:")
    for word, where in found["words"].items():
        more = f" (+{len(where) - limit})" if len(where) > limit else ""
        lines.append(f"  {word}  {', '.join(where[:limit])}{more}")
    if found["notes"]:
        lines += ["", f"Changes to check, from the entries' notes ({len(found['notes'])}):"]
        lines += [f"  {key}  {', '.join(marked)}" for key, marked in found["notes"].items()]
    return "\n".join(lines)


# ---------------------------------------------------------------- recording


def record(project_dir, raw, language, source, rows, by, today=None):
    """Record verdicts. `rows` is [(name, result, note)], a name being a word or an entry written page/section/id.
    Returns the sidecar written. Nothing is written unless every row is sound.

    A new source id must be described first, by hand, in the file's `sources`: this never invents one."""
    if not by or not by.strip():
        raise ContentError("say who checked, with --by NAME")
    sidecar = load(project_dir, language)
    if source not in sidecar["sources"]:
        raise ContentError(
            f"source {source!r} is not described in {path_for(project_dir, language)}; add it under 'sources' first "
            f"(known: {', '.join(sidecar['sources']) or 'none'})"
        )
    by_key = dict(entries(raw, language))
    day = (today or datetime.date.today()).isoformat()
    for name, result, note in rows:
        if result not in RESULTS:
            raise ContentError(f"result must be one of {', '.join(RESULTS)}, not {result!r}")
        verdict = {"source": source, "result": result, "by": by.strip(), "date": day}
        if note:
            verdict["note"] = note
        if "/" in name:
            if name not in by_key:
                raise ContentError(f"no entry {name!r} in {language}; write page/section/id")
            verdict["hash"] = entry_hash(by_key[name])
            sidecar["entries"][name] = verdict
        else:
            sidecar["words"][name.casefold()] = verdict
    ordered = {"sources": sidecar["sources"], "words": dict(sorted(sidecar["words"].items())), "entries": sidecar["entries"]}
    problem = validate(ordered)
    if problem:
        raise ContentError(problem)
    path = path_for(project_dir, language)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ordered


def mark(project_dir, raw, language, source, result, names, by, note=None, today=None):
    """Record one verdict for each name (see `record`)."""
    return record(project_dir, raw, language, source, [(name, result, note) for name in names], by, today)


# ---------------------------------------------------------------- the worklist: a Markdown file to edit and bring back

MARKERS = {" ": None, "x": "ok", "c": "changed", "?": "query"}
ROW = re.compile(r"^- \[(.)\] `([^`]+)`(.*)$")
HEADER = re.compile(r"^(Language|Source|By):[ \t]*(.*)$")
SEPARATOR = " | "


def worklist(language, raw, sidecar, source="", by="", build="python3 build.py", file="worklist.md"):
    """The sheet as a Markdown file to edit. The commands to make it and to bring it back are at its head.

    Each row is `- [ ] `name` - where it is used`. Mark a row by changing the space to `x` (ok), `c` (changed) or `?` (query),
    and write a note after a `|`. The rows left as they were are skipped when it is brought back."""
    found = sheet(raw, language, sidecar)
    by_key = dict(entries(raw, language))
    if not source and len(sidecar["sources"]) == 1:
        source = next(iter(sidecar["sources"]))

    def where(keys):
        shown = texts_of(by_key[keys[0]])[0].replace("|", "/")  # a bar would start a note
        more = f" (and {len(keys) - 1} more)" if len(keys) > 1 else ""
        return f" - {shown}{more}"

    lines = [
        f"# Check worklist: {language}",
        "",
        "## Commands",
        "",
        "Run these from the project's folder. Make this file, edit it, then bring it back:",
        "",
        "```",
        f"{build} --check {language} --out {file}",
        f"{build} --apply {file}",
        "```",
        "",
        "Bringing it back records a verdict for each row you marked, in the sidecar "
        f"`checks/{language}.json`, and then `--check` no longer lists those rows. "
        "Run `--apply` again after any further edit: a row that is already recorded is simply recorded again.",
        "",
        "## How to edit",
        "",
        "- Change the space in `[ ]` to `x` (found, and right), `c` (found, and the content was corrected) or `?` (a question for a person).",
        f"- Add a note after a ` | ` on the same row if you want one: your own words, at most {NOTE_LIMIT} characters, "
        "and never text copied from the source.",
        "- Leave a row as `[ ]` to skip it. Keep the name in backticks as it is: it is how the row is found again.",
        "- Fill in the three lines below. The source must be described in the sidecar's `sources` first.",
        "",
        f"Language: {language}",
        f"Source: {source}",
        f"By: {by}",
        "",
    ]
    if found["stale"]:
        lines += ["## Entries checked before their text changed", ""]
        lines += [f"- [ ] `{key}`{where([key])}" for key in found["stale"]] + [""]
    due = [key for key in found["notes"] if key in found["unchecked"] or key in found["stale"]]
    if due:
        lines += [
            "## Changes in the notes",
            "",
            "An entry whose note names a word that changes shape. Check the note, not the words.",
            "",
        ]
        lines += [f"- [ ] `{key}`{where([key])}" for key in due] + [""]
    lines += [f"## Words ({len(found['words'])})", ""]
    lines += [f"- [ ] `{word}`{where(keys)}" for word, keys in found["words"].items()]
    return "\n".join(lines) + "\n"


def parse_worklist(text):
    """A worklist read back: ({"Language", "Source", "By"}, [(name, result, note)]) for the rows that were marked.

    Raises ContentError, naming the line, for a marker that means nothing or a note that is too long."""
    header, rows = {}, []
    in_code = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        found = HEADER.match(line)
        if found:
            header[found.group(1)] = found.group(2).strip()
            continue
        found = ROW.match(line)
        if not found:
            continue
        marker, name, rest = found.group(1).lower(), found.group(2), found.group(3)
        if marker not in MARKERS:
            raise ContentError(f"line {number}: the marker [{found.group(1)}] means nothing; use x, c, ? or a space")
        if MARKERS[marker] is None:
            continue
        note = rest.split(SEPARATOR, 1)[1].strip() if SEPARATOR in rest else ""
        if len(note) > NOTE_LIMIT:
            raise ContentError(f"line {number}: the note is {len(note)} characters; {NOTE_LIMIT} at most, in your own words")
        rows.append((name, MARKERS[marker], note))
    return header, rows


def apply(project_dir, raw, text, by=None, today=None):
    """Bring a worklist back: record each marked row. Returns (language, number of rows recorded)."""
    header, rows = parse_worklist(text)
    language = header.get("Language")
    if not language or language not in raw["packs"]:
        raise ContentError(f"the worklist's 'Language:' line must name one of: {', '.join(raw['packs'])}")
    if not rows:
        return language, 0
    source = header.get("Source")
    if not source:
        raise ContentError("fill in the 'Source:' line of the worklist, with an id described in the sidecar's 'sources'")
    record(project_dir, raw, language, source, rows, by or header.get("By"), today)
    return language, len(rows)
