"""Checks: the sheet of what has no verdict from a reference book yet, and the sidecar that records the verdicts."""

import contextlib
import datetime
import io
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import fixture  # noqa: E402
from phrasebook import checks, cli, content  # noqa: E402
from phrasebook.errors import ContentError  # noqa: E402
from test_framework import Scratch  # noqa: E402

SOURCES = {"book": "A printed dictionary"}


def verdict(**kw):
    return {"source": "book", "result": "ok", "by": "A. Person", "date": "2026-10-30", **kw}


class WordTests(unittest.TestCase):
    def test_words_are_lower_cased_once_each_in_order_of_first_use(self):
        self.assertEqual(checks.tokens("Glaw trwm a glaw mân"), ["glaw", "trwm", "a", "mân"])

    def test_an_apostrophe_or_hyphen_between_letters_keeps_a_word_whole_and_marks_are_not_words(self):
        self.assertEqual(checks.tokens("{{o'r}} gogledd-orllewin"), ["o'r", "gogledd-orllewin"])
        self.assertEqual(checks.tokens("74mya, 16 gradd"), ["mya", "gradd"])

    def test_an_entry_shows_its_text_or_forms_and_then_its_also_forms(self):
        self.assertEqual(checks.texts_of({"text": "a", "also": ["b"]}), ["a", "b"])
        self.assertEqual(
            checks.texts_of({"forms": [{"text": "x", "varieties": ["x"]}, {"text": "y"}], "also": ["z"]}), ["x", "y", "z"]
        )
        self.assertEqual(checks.texts_of("plain"), ["plain"])

    def test_the_fingerprint_follows_the_text_and_not_the_note(self):
        base = {"text": "one", "note": "n"}
        self.assertEqual(checks.entry_hash(base), checks.entry_hash({"text": "one", "note": "different"}))
        self.assertNotEqual(checks.entry_hash(base), checks.entry_hash({"text": "two"}))
        self.assertNotEqual(checks.entry_hash(base), checks.entry_hash({"text": "one", "also": ["uno"]}))


class SidecarValidationTests(unittest.TestCase):
    def sidecar(self, **words):
        return {"sources": SOURCES, "words": words, "entries": {}}

    def test_a_sound_sidecar_and_an_empty_one_pass(self):
        self.assertIsNone(checks.validate(self.sidecar(glaw=verdict(note="north"))))
        self.assertIsNone(checks.validate({}))

    def test_a_verdict_must_name_a_described_source_a_known_result_who_and_a_real_day(self):
        self.assertIn("not described", checks.validate(self.sidecar(glaw=verdict(source="other"))))
        self.assertIn("result", checks.validate(self.sidecar(glaw=verdict(result="fine"))))
        self.assertIn("'by'", checks.validate(self.sidecar(glaw=verdict(by=" "))))
        self.assertIn("'date'", checks.validate(self.sidecar(glaw=verdict(date="30/10/2026"))))

    def test_only_verdicts_are_kept_never_text_from_the_source(self):
        self.assertIn("may hold only", checks.validate(self.sidecar(glaw=verdict(definition="copied"))))
        self.assertIn("note", checks.validate(self.sidecar(glaw=verdict(note="x" * (checks.NOTE_LIMIT + 1)))))

    def test_words_are_in_lower_case_and_an_entry_needs_its_hash(self):
        self.assertIn("lower case", checks.validate(self.sidecar(Glaw=verdict())))
        bad = {"sources": SOURCES, "entries": {"p/s/c": verdict()}}
        self.assertIn("hash", checks.validate(bad))

    def test_nothing_else_may_sit_in_the_file(self):
        self.assertIn("may hold only", checks.validate({"extra": 1}))


class SheetTests(Scratch):
    """The fixture's qaa pack: page p1 has "qaa one", "qaa two" (note on a marked stretch) and "qaa three"."""

    def setUp(self):
        self.dir = self.project()
        self.raw = content.read(self.dir)

    def test_every_word_is_listed_once_with_where_it_is_used(self):
        found = checks.sheet(self.raw, "qaa", checks.empty())
        self.assertIn("qaa", found["words"])
        self.assertEqual(found["words"]["one"], ["p1/s1/c1"])
        self.assertEqual(len(found["words"]["qaa"]), len(set(found["words"]["qaa"])), "an entry is named once")
        self.assertGreater(found["total"][0], 3)

    def test_a_checked_word_drops_off_the_sheet_wherever_it_is_used(self):
        side = {**checks.empty(), "sources": SOURCES, "words": {"qaa": verdict()}}
        found = checks.sheet(self.raw, "qaa", side)
        self.assertNotIn("qaa", found["words"])
        self.assertIn("one", found["words"])

    def test_an_entry_checked_against_its_current_text_is_done_and_one_whose_text_changed_is_stale(self):
        concept = dict(checks.entries(self.raw, "qaa"))["p1/s1/c1"]
        side = {**checks.empty(), "sources": SOURCES, "entries": {"p1/s1/c1": verdict(hash=checks.entry_hash(concept))}}
        found = checks.sheet(self.raw, "qaa", side)
        self.assertNotIn("p1/s1/c1", found["unchecked"] + found["stale"])
        side["entries"]["p1/s1/c1"]["hash"] = "0000000000"
        found = checks.sheet(self.raw, "qaa", side)
        self.assertEqual(found["stale"], ["p1/s1/c1"])
        self.assertNotIn("p1/s1/c1", found["unchecked"])

    def test_an_entry_with_a_marked_stretch_in_its_note_is_listed_for_its_grammar(self):
        found = checks.sheet(self.raw, "qaa", checks.empty())
        self.assertEqual(found["notes"], {"p1/s2/c2": ["qaa two"]})

    def test_the_report_gives_the_counts_the_words_and_how_to_record_a_verdict(self):
        text = checks.report("qaa", checks.sheet(self.raw, "qaa", checks.empty()))
        self.assertIn("Check sheet for qaa", text)
        self.assertIn("--mark qaa SOURCE", text)
        self.assertIn("p1/s1/c1", text)


class MarkingTests(Scratch):
    def setUp(self):
        self.dir = self.project()
        self.raw = content.read(self.dir)
        side = checks.path_for(self.dir, "qaa")
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(json.dumps({"sources": SOURCES}), encoding="utf-8")

    def test_marking_words_writes_a_sorted_sidecar_in_lower_case_dated_and_signed(self):
        day = datetime.date(2026, 10, 30)
        checks.mark(self.dir, self.raw, "qaa", "book", "ok", ["Two", "one"], "A. Person", today=day)
        written = json.loads(checks.path_for(self.dir, "qaa").read_text(encoding="utf-8"))
        self.assertEqual(list(written["words"]), ["one", "two"])
        self.assertEqual(written["words"]["one"], {"source": "book", "result": "ok", "by": "A. Person", "date": "2026-10-30"})
        self.assertEqual(checks.load(self.dir, "qaa")["words"]["two"]["by"], "A. Person")

    def test_marking_an_entry_keeps_the_fingerprint_it_was_checked_against(self):
        checks.mark(self.dir, self.raw, "qaa", "book", "changed", ["p1/s1/c1"], "A. Person", note="spelling fixed")
        written = checks.load(self.dir, "qaa")["entries"]["p1/s1/c1"]
        self.assertEqual(written["hash"], checks.entry_hash(dict(checks.entries(self.raw, "qaa"))["p1/s1/c1"]))
        self.assertEqual(written["note"], "spelling fixed")

    def test_a_source_must_be_described_by_hand_first_and_a_result_and_a_name_are_required(self):
        with self.assertRaisesRegex(ContentError, "not described"):
            checks.mark(self.dir, self.raw, "qaa", "invented", "ok", ["one"], "A. Person")
        with self.assertRaisesRegex(ContentError, "result must be"):
            checks.mark(self.dir, self.raw, "qaa", "book", "fine", ["one"], "A. Person")
        with self.assertRaisesRegex(ContentError, "who checked"):
            checks.mark(self.dir, self.raw, "qaa", "book", "ok", ["one"], None)
        with self.assertRaisesRegex(ContentError, "no entry"):
            checks.mark(self.dir, self.raw, "qaa", "book", "ok", ["p1/s1/missing"], "A. Person")

    def test_a_broken_sidecar_is_reported_with_its_path(self):
        checks.path_for(self.dir, "qaa").write_text('{"sources": {}, "words": {"x": {}}}', encoding="utf-8")
        with self.assertRaisesRegex(ContentError, "qaa.json"):
            checks.load(self.dir, "qaa")


class SidecarIsNotPartOfTheSite(Scratch):
    def test_the_build_ignores_the_sidecar_and_does_not_ship_it(self):
        plain = self.project()
        marked = self.project()
        side = checks.path_for(marked, "qaa")
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(json.dumps({"sources": SOURCES, "words": {"one": verdict()}}), encoding="utf-8")
        self.assertEqual(self.built(plain), self.built(marked))
        self.assertNotIn("A. Person", "".join(self.built(marked).values()))


class CommandLineTests(Scratch):
    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.main(list(args))
        return out.getvalue()

    def test_check_prints_the_sheet(self):
        project = self.project()
        text = self.run_cli("--check", "qaa", "--project", str(project))
        self.assertIn("Check sheet for qaa", text)

    def test_mark_records_and_check_then_leaves_the_word_off_the_sheet(self):
        project = self.project()
        side = checks.path_for(project, "qaa")
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(json.dumps({"sources": SOURCES}), encoding="utf-8")
        said = self.run_cli("--mark", "qaa", "book", "ok", "one", "--by", "A. Person", "--project", str(project))
        self.assertIn("recorded 1", said)
        self.assertNotIn("\n  one  ", self.run_cli("--check", "qaa", "--project", str(project)))

    def test_mark_without_a_word_or_a_name_stops_with_a_content_error(self):
        project = self.project()
        with self.assertRaises(SystemExit) as stopped:
            self.run_cli("--mark", "qaa", "book", "ok", "--project", str(project))
        self.assertIn("content error", str(stopped.exception))


class WorklistTests(Scratch):
    """A Markdown worklist is made, edited by hand and brought back."""

    def setUp(self):
        self.dir = self.project()
        self.raw = content.read(self.dir)
        side = checks.path_for(self.dir, "qaa")
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(json.dumps({"sources": SOURCES}), encoding="utf-8")

    def made(self, **kw):
        return checks.worklist("qaa", self.raw, checks.load(self.dir, "qaa"), file="mine.md", **kw)

    def test_the_commands_to_make_and_bring_it_back_are_at_the_head(self):
        text = self.made(by="A. Person")
        head = text.split("## How to edit")[0]
        self.assertIn("build.py --check qaa --out mine.md", head)
        self.assertIn("build.py --apply mine.md", head)
        self.assertTrue(text.startswith("# Check worklist: qaa"))

    def test_the_only_source_is_filled_in_and_the_name_given_is_kept(self):
        text = self.made(by="A. Person")
        self.assertIn("\nSource: book\n", text)
        self.assertIn("\nBy: A. Person\n", text)

    def test_every_unchecked_word_is_a_row_and_shows_an_entry_that_uses_it(self):
        text = self.made()
        self.assertIn("- [ ] `one` - qaa one", text)
        self.assertNotIn("[x]", text)

    def test_a_word_already_checked_is_not_in_the_next_worklist(self):
        checks.mark(self.dir, self.raw, "qaa", "book", "ok", ["one"], "A. Person")
        self.assertNotIn("`one`", self.made())

    def test_marked_rows_are_read_back_with_their_results_and_notes_and_blank_rows_are_skipped(self):
        text = self.made(by="A. Person")
        text = text.replace("- [ ] `one`", "- [x] `one`").replace("- [ ] `two`", "- [c] `two`", 1)
        text = text.replace("- [c] `two` - qaa two", "- [c] `two` - qaa two | spelling fixed", 1)
        text = text.replace("- [ ] `three`", "- [?] `three`")
        header, rows = checks.parse_worklist(text)
        self.assertEqual(header, {"Language": "qaa", "Source": "book", "By": "A. Person"})
        self.assertEqual(rows, [("one", "ok", ""), ("three", "query", ""), ("two", "changed", "spelling fixed")])

    def test_the_commands_in_the_code_block_are_not_read_as_rows(self):
        text = "```\n- [x] `fake`\n```\nLanguage: qaa\n- [x] `real`\n"
        self.assertEqual(checks.parse_worklist(text)[1], [("real", "ok", "")])

    def test_a_marker_that_means_nothing_or_a_note_that_is_too_long_names_its_line(self):
        with self.assertRaisesRegex(ContentError, "line 2: the marker"):
            checks.parse_worklist("Language: qaa\n- [y] `one`\n")
        with self.assertRaisesRegex(ContentError, "line 1: the note"):
            checks.parse_worklist("- [x] `one` | " + "x" * 300)

    def test_applying_records_the_rows_and_a_second_worklist_no_longer_lists_them(self):
        text = self.made(by="A. Person").replace("- [ ] `one`", "- [x] `one`")
        language, count = checks.apply(self.dir, self.raw, text)
        self.assertEqual((language, count), ("qaa", 1))
        self.assertEqual(checks.load(self.dir, "qaa")["words"]["one"]["result"], "ok")
        self.assertNotIn("`one`", self.made())

    def test_an_entry_row_is_recorded_against_its_current_text(self):
        key = "p1/s2/c2"
        text = self.made(by="A. Person")
        self.assertIn(f"- [ ] `{key}`", text)
        checks.apply(self.dir, self.raw, text.replace(f"- [ ] `{key}`", f"- [x] `{key}`"))
        self.assertIn(key, checks.load(self.dir, "qaa")["entries"])
        self.assertNotIn(f"`{key}`", self.made())

    def test_applying_needs_a_source_a_name_and_a_language_and_a_bad_row_writes_nothing(self):
        marked = self.made().replace("- [ ] `one`", "- [x] `one`")
        with self.assertRaisesRegex(ContentError, "who checked"):
            checks.apply(self.dir, self.raw, marked)
        with self.assertRaisesRegex(ContentError, "Source"):
            checks.apply(self.dir, self.raw, marked.replace("Source: book", "Source: "), by="A. Person")
        with self.assertRaisesRegex(ContentError, "Language"):
            checks.apply(self.dir, self.raw, marked.replace("Language: qaa", "Language: zzz"), by="A. Person")
        bad = marked.replace("- [ ] `two`", "- [x] `p9/none/missing`")
        with self.assertRaisesRegex(ContentError, "no entry"):
            checks.apply(self.dir, self.raw, bad, by="A. Person")
        self.assertEqual(checks.load(self.dir, "qaa")["words"], {})

    def test_a_worklist_with_nothing_marked_records_nothing(self):
        self.assertEqual(checks.apply(self.dir, self.raw, self.made(by="A. Person")), ("qaa", 0))
        self.assertFalse("words" in json.loads(checks.path_for(self.dir, "qaa").read_text(encoding="utf-8")))


class WorklistCommandLineTests(Scratch):
    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.main(list(args))
        return out.getvalue()

    def test_out_writes_a_worklist_and_apply_brings_it_back(self):
        project = self.project()
        side = checks.path_for(project, "qaa")
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(json.dumps({"sources": SOURCES}), encoding="utf-8")
        file = self.tmp / "list.md"
        self.run_cli("--check", "qaa", "--out", str(file), "--by", "A. Person", "--project", str(project))
        file.write_text(
            file.read_text(encoding="utf-8").replace("- [ ] `one` - qaa one", "- [x] `one` - qaa one | seen"), encoding="utf-8"
        )
        said = self.run_cli("--apply", str(file), "--project", str(project))
        self.assertIn("recorded 1", said)
        recorded = checks.load(project, "qaa")["words"]["one"]
        self.assertEqual((recorded["by"], recorded["note"]), ("A. Person", "seen"))


if __name__ == "__main__":
    unittest.main()
