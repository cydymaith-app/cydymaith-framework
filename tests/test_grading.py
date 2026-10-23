"""Grading: how demanding each group, page and section is, worked out from the size of a typical entry."""

import contextlib
import io
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import fixture  # noqa: E402
from phrasebook import cli, content, grading  # noqa: E402
from phrasebook.errors import ContentError  # noqa: E402
from test_framework import Scratch  # noqa: E402


class CountingTests(unittest.TestCase):
    def test_words_are_pieces_separated_by_white_space_that_hold_a_letter_or_a_digit(self):
        self.assertEqual(grading.count_words("north"), 1)
        self.assertEqual(grading.count_words("in the north"), 3)
        self.assertEqual(grading.count_words("  it's   sunny  "), 2)
        self.assertEqual(grading.count_words("north-east"), 1, "a hyphen joins one word")
        self.assertEqual(grading.count_words("a - b"), 2, "a dash on its own is not a word")
        self.assertEqual(grading.count_words("2.00pm"), 1)
        self.assertEqual(grading.count_words(""), 0)

    def test_marks_around_a_stretch_in_the_pack_language_are_not_words(self):
        self.assertEqual(grading.count_words("{{am}} softens {{gwynt}}"), 3)
        self.assertEqual(grading.count_words("{{two words}}"), 2)

    def test_an_entry_is_read_as_a_string_a_text_or_the_first_regional_form(self):
        self.assertEqual(grading.entry_text("plain"), "plain")
        self.assertEqual(grading.entry_text({"text": "with text", "note": "a note"}), "with text")
        self.assertEqual(grading.entry_text({"forms": [{"text": "first", "varieties": ["x"]}, {"text": "second"}]}), "first")
        self.assertIsNone(grading.entry_text({"note": "no text at all"}))
        self.assertIsNone(grading.entry_text(None))

    def test_the_median_is_the_middle_and_the_mean_of_the_middle_two_when_there_is_no_one_middle(self):
        self.assertEqual(grading.median([3, 1, 2]), 2)
        self.assertEqual(grading.median([1, 2, 3, 4]), 2.5)
        self.assertEqual(grading.median([5]), 5)
        self.assertIsNone(grading.median([]))

    def test_one_stray_entry_does_not_move_a_section_but_a_mean_would(self):
        sentences_and_one_word = [5, 5, 5, 4, 1]
        words_and_one_sentence = [1, 1, 1, 1, 7]
        self.assertEqual(grading.level_for(grading.median(sentences_and_one_word)), 3)
        self.assertEqual(grading.level_for(grading.median(words_and_one_sentence)), 1)

    def test_the_levels_break_at_the_bounds_and_nothing_to_measure_is_level_one(self):
        self.assertEqual([grading.level_for(x) for x in (1, 1.49, 1.5, 2, 2.49, 2.5, 3, 9)], [1, 1, 2, 2, 2, 3, 3, 3])
        self.assertEqual(grading.level_for(None), 1)
        self.assertEqual([grading.level_for(x, (2, 4)) for x in (1.9, 2, 3.9, 4)], [1, 2, 2, 3])


class GradeTests(Scratch):
    """The fixture: page p1 has three two-word entries (qaa one, qaa two, qaa three); `points` has eight one-word entries."""

    def graded(self, proj, **kw):
        raw = content.read(proj)
        content.validate(raw)
        _, ed = content.pick_edition(raw)
        return grading.grade(raw, ed, **kw)

    def test_each_section_page_and_group_gets_a_level_from_what_it_holds(self):
        g = self.graded(self.project())
        self.assertEqual(g["language"], "qaa", "the language heard is the first of the default pair")
        self.assertEqual(g["bounds"], grading.BOUNDS)
        group = g["groups"][0]
        self.assertEqual(group["id"], "g1")
        pages = {p["id"]: p for p in group["pages"]}
        self.assertEqual([s["level"] for s in pages["p1"]["sections"]], [2, 2, 2])
        self.assertEqual(pages["p1"]["level"], 2)
        self.assertEqual(pages["points"]["level"], 1)
        self.assertEqual(pages["points"]["sections"][0]["entries"], 8)
        self.assertEqual(group["entries"], 11)
        self.assertEqual(group["median"], 1.0)
        self.assertEqual(group["level"], 1, "a group takes the typical entry of every page it lists")

    def test_a_level_set_by_hand_wins_and_the_rule_is_kept_beside_it(self):
        proj = self.project()
        fixture.edit(proj / "pages" / "p1.json", lambda d: d["sections"][0].update(level=1))
        fixture.edit(proj / "pages" / "points.json", lambda d: d.update(level=3))
        fixture.edit(proj / "structure.json", lambda d: d["groups"][0].update(level=2))
        group = self.graded(proj)["groups"][0]
        pages = {p["id"]: p for p in group["pages"]}
        s1 = pages["p1"]["sections"][0]
        self.assertEqual((s1["level"], s1["computed"], s1["by_hand"]), (1, 2, True))
        self.assertEqual((pages["points"]["level"], pages["points"]["computed"], pages["points"]["by_hand"]), (3, 1, True))
        self.assertEqual((group["level"], group["computed"], group["by_hand"]), (2, 1, True))
        self.assertFalse(pages["p1"]["by_hand"])
        self.assertEqual(pages["p1"]["level"], 2, "a section set by hand does not move its page")

    def test_the_words_are_counted_in_the_language_heard_and_the_edition_can_choose_another(self):
        proj = self.project()
        fixture.edit(
            proj / "packs" / "qaa" / "pages" / "p1.json",
            lambda d: d["sections"]["s1"]["concepts"]["c1"].update(text="one two three four five"),
        )
        first = self.graded(proj)["groups"][0]["pages"][0]["sections"][0]
        self.assertEqual((first["level"], first["median"]), (3, 5.0))
        fixture.edit(proj / "editions" / "demo.json", lambda d: d.update(grading={"language": "qab"}))
        raw = content.read(proj)
        _, ed = content.pick_edition(raw)
        other = grading.grade(raw, ed)
        self.assertEqual(other["language"], "qab")
        self.assertEqual(other["groups"][0]["pages"][0]["sections"][0]["level"], 2, "qab says 'qab one': two words")

    def test_an_entry_with_only_regional_forms_is_counted_by_its_first_form(self):
        proj = self.project()
        fixture.edit(proj / "editions" / "demo.json", lambda d: d.update(grading={"language": "qab"}))
        section = self.graded(proj)["groups"][0]["pages"][0]["sections"][1]
        self.assertEqual((section["entries"], section["median"]), (1, 2.0), "qab two-x")

    def test_entries_the_pack_does_not_have_are_left_out_not_counted_as_nothing(self):
        proj = self.project()
        fixture.edit(proj / "packs" / "qaa" / "pages" / "points.json", lambda d: d["sections"]["dirs"]["concepts"].pop("north"))
        raw = content.read(proj)
        _, ed = content.pick_edition(raw)
        dirs = grading.grade(raw, ed)["groups"][0]["pages"][1]["sections"][0]
        self.assertEqual(dirs["entries"], 7)
        self.assertEqual(dirs["level"], 1)

    def test_the_bounds_can_be_moved_by_the_edition(self):
        proj = self.project()
        fixture.edit(proj / "editions" / "demo.json", lambda d: d.update(grading={"bounds": [2, 3]}))
        pages = {p["id"]: p for p in self.graded(proj)["groups"][0]["pages"]}
        self.assertEqual(pages["p1"]["level"], 2, "two words is level 2 once the first bound is two")
        self.assertEqual(pages["points"]["level"], 1)


class ValidationTests(Scratch):
    def invalid(self, proj, fragment):
        with self.assertRaises(ContentError) as caught:
            content.validate(content.read(proj))
        self.assertIn(fragment, str(caught.exception))

    def test_a_level_must_be_a_whole_number_from_one_to_three_wherever_it_is_set(self):
        for bad in (0, 4, -1, 1.5, "2", True, None, [2]):
            proj = self.project()
            fixture.edit(proj / "pages" / "p1.json", lambda d, bad=bad: d["sections"][0].update(level=bad))
            self.invalid(proj, "pages/p1.json/s1")
            proj = self.project()
            fixture.edit(proj / "pages" / "p1.json", lambda d, bad=bad: d.update(level=bad))
            self.invalid(proj, "pages/p1.json: 'level'")
            proj = self.project()
            fixture.edit(proj / "structure.json", lambda d, bad=bad: d["groups"][0].update(level=bad))
            self.invalid(proj, "structure.json group 'g1'")

    def test_levels_one_to_three_are_accepted_on_a_group_a_page_and_a_section(self):
        proj = self.project()
        fixture.edit(proj / "structure.json", lambda d: d["groups"][0].update(level=3))
        fixture.edit(proj / "pages" / "p1.json", lambda d: (d.update(level=2), d["sections"][0].update(level=1)))
        content.validate(content.read(proj))

    def test_the_editions_grading_block_is_checked(self):
        cases = [
            ({"language": "zzz"}, "grading.language"),
            ({"bounds": [1.5]}, "grading.bounds"),
            ({"bounds": [2.5, 1.5]}, "grading.bounds"),
            ({"bounds": [1.5, 1.5]}, "grading.bounds"),
            ({"bounds": [0, 2]}, "grading.bounds"),
            ({"bounds": ["a", "b"]}, "grading.bounds"),
            ({"bounds": "1.5,2.5"}, "grading.bounds"),
            ({"levels": 5}, "may hold only"),
        ]
        for block, fragment in cases:
            proj = self.project()
            fixture.edit(proj / "editions" / "demo.json", lambda d, block=block: d.update(grading=block))
            self.invalid(proj, fragment)
        proj = self.project()
        fixture.edit(proj / "editions" / "demo.json", lambda d: d.update(grading={"language": "qab", "bounds": [1, 3.5]}))
        content.validate(content.read(proj))


class ReportTests(Scratch):
    def run_report(self, proj, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(cli, "build", side_effect=AssertionError("nothing is built")):
            cli.main(["--grades", "--project", str(proj), *extra])
        return out.getvalue()

    def test_the_command_prints_every_group_page_and_section_and_builds_nothing(self):
        text = self.run_report(self.project())
        lines = text.splitlines()
        self.assertIn("counted in qaa", lines[0])
        self.assertTrue(any(l.startswith("g1 ") and "level 1" in l for l in lines), text)
        self.assertTrue(any(l.startswith("  p1 ") and "level 2" in l for l in lines), text)
        self.assertTrue(any(l.startswith("    s1 ") and "median  2.0" in l and "over   1 entries" in l for l in lines), text)
        self.assertTrue(any(l.startswith("  points ") and "level 1" in l for l in lines), text)

    def test_a_level_set_by_hand_is_starred_and_says_what_the_rule_said(self):
        proj = self.project()
        fixture.edit(proj / "pages" / "p1.json", lambda d: d["sections"][1].update(level=1))
        text = self.run_report(proj)
        starred = [l for l in text.splitlines() if l.startswith("    s2 ")]
        self.assertEqual(len(starred), 1)
        self.assertIn("level 1*", starred[0])
        self.assertIn("(the rule says 2)", starred[0])
        self.assertNotIn("*", [l for l in text.splitlines() if l.startswith("    s1 ")][0].split("median")[0])

    def test_a_level_set_by_hand_that_agrees_with_the_rule_is_starred_without_a_note(self):
        proj = self.project()
        fixture.edit(proj / "pages" / "p1.json", lambda d: d["sections"][1].update(level=2))
        line = [l for l in self.run_report(proj).splitlines() if l.startswith("    s2 ")][0]
        self.assertIn("level 2*", line)
        self.assertNotIn("the rule says", line)

    def test_a_content_error_stops_the_report_with_the_usual_message(self):
        proj = self.project()
        fixture.edit(proj / "pages" / "p1.json", lambda d: d.update(level=9))
        with self.assertRaises(SystemExit) as caught, contextlib.redirect_stdout(io.StringIO()):
            cli.main(["--grades", "--project", str(proj)])
        self.assertIn("content error", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
