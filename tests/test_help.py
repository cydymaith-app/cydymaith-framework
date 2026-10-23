"""Tests of the help book: its anchors, its words, the chapter pages and the contents page (phrasebook/help.py).

Run from the repo root: python3 -m unittest discover -s tests -v
"""

import copy
import json
import pathlib
import re
import sys
import unittest
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import fixture  # noqa: E402
import phrasebook  # noqa: E402
from phrasebook import content, help as helpbook  # noqa: E402
from phrasebook.errors import ContentError  # noqa: E402
from test_framework import ENGINE, Scratch, quiet_build  # noqa: E402

# The anchors in the book today. A test fails when one is renamed or dropped, because every link that names it would break.
# Add to this list when a feature is added; never edit an entry.
ANCHORS = [
    "tiles", "trail", "side-bar", "back", "pager", "jump-links", "keys-and-touch", "drag-back",
    "search", "search-keys", "search-this-page-first", "listen-first-rows", "also-heard", "regional-forms", "sources-notes",
    "sections-order", "levels", "related-topics",
    "settings-groups", "language-toggle", "view-mode", "accessibility", "colour-schemes", "order-setting", "reset-tile-layouts", "what-is-saved",
]

EN = json.loads((ENGINE / "help" / "en.json").read_text(encoding="utf-8"))


def book(sections=None, texts=None):
    """A book with two chapters and a feature that needs an About page, with English text for all of it."""
    sections = sections or [
        {"id": "one", "features": [{"id": "a"}, {"id": "b", "requires": "about"}]},
        {"id": "two", "features": [{"id": "c"}]},
    ]
    texts = texts or {
        "en": {
            "chapters": {"one": {"title": "One", "lede": "First."}, "two": {"title": "Two"}},
            "features": {
                "a": {"title": "A", "body": ["About a."], "keys": "Press a.", "touch": "Tap a."},
                "b": {"title": "B", "body": ["About b."]},
                "c": {"title": "C", "body": [{"list": ["x", "y"]}]},
            },
        }
    }
    return helpbook.Book(sections, texts)


def site_for(proj, help_book, drop_about=False, pair=None):
    raw = content.read(proj)
    ed = content.pick_edition(raw)[1]
    if drop_about:
        ed = {k: v for k, v in ed.items() if k != "about_page"}
    return phrasebook.Site(raw, ed, pair=pair, help_book=help_book)


class AnchorTests(unittest.TestCase):
    def test_the_anchors_are_the_ones_promised(self):
        self.assertEqual(helpbook.Book.load({}).anchors(), ANCHORS)

    def test_every_anchor_has_english_text_and_every_chapter_a_title(self):
        for chapter in helpbook.SECTIONS:
            self.assertTrue(EN["chapters"][chapter["id"]]["title"], chapter["id"])
            for feature in chapter["features"]:
                entry = EN["features"][feature["id"]]
                self.assertTrue(entry["title"] and entry["body"], feature["id"])

    def test_the_english_text_has_no_entry_for_an_anchor_the_book_lacks(self):
        self.assertEqual(set(EN["features"]), set(ANCHORS))

    def test_an_anchor_must_be_safe_and_unique(self):
        for bad in ("Up", "has space", "1st", "a_b", ""):
            with self.assertRaises(ContentError, msg=bad):
                helpbook.check_sections([{"id": "x", "features": [{"id": bad}]}])
        with self.assertRaises(ContentError):
            helpbook.check_sections([{"id": "x", "features": [{"id": "a"}, {"id": "a"}]}])
        with self.assertRaises(ContentError):
            helpbook.check_sections([{"id": "x", "features": [{"id": "a"}]}, {"id": "x", "features": [{"id": "b"}]}])

    def test_a_condition_must_be_one_the_site_can_answer(self):
        with self.assertRaises(ContentError):
            helpbook.check_sections([{"id": "x", "features": [{"id": "a", "requires": "moon"}]}])

    def test_a_feature_with_no_english_text_stops_the_build(self):
        sections = [{"id": "one", "features": [{"id": "a"}, {"id": "missing"}]}]
        texts = copy.deepcopy(book().texts)
        with self.assertRaises(ContentError) as ctx:
            helpbook.Book(sections, texts)
        self.assertIn("missing", str(ctx.exception))

    def test_text_for_an_anchor_that_is_not_in_the_book_is_refused(self):
        texts = copy.deepcopy(book().texts)
        texts["cy"] = {"features": {"typo": {"title": "T", "body": ["x"]}}}
        with self.assertRaises(ContentError) as ctx:
            helpbook.Book(book().sections, texts)
        self.assertIn("typo", str(ctx.exception))

    def test_a_pack_overrides_the_framework_text_and_adds_a_language(self):
        packs = {
            "en": {"help": {"features": {"tiles": {"title": "Squares", "body": ["x"]}}}},
            "fr": {"help": {"features": {"tiles": {"title": "Tuiles", "body": ["y"]}}}},
            "de": {},
        }
        loaded = helpbook.Book.load(packs)
        self.assertEqual(loaded.entry("en", "features", "tiles")[0]["title"], "Squares")
        self.assertEqual(loaded.entry("fr", "features", "tiles"), ({"title": "Tuiles", "body": ["y"]}, "fr"))
        self.assertEqual(loaded.entry("fr", "features", "back")[1], "en", "falls back to English")
        self.assertEqual(loaded.entry("de", "features", "back")[1], "en")
        self.assertTrue(loaded.has_text("fr"))
        self.assertFalse(loaded.has_text("de"))

    def test_coverage_counts_only_a_languages_own_text(self):
        packs = {"fr": {"help": {"features": {"tiles": {"title": "Tuiles", "body": ["y"]}}}}}
        cover = helpbook.Book.load(packs).coverage(["en", "fr", "de"])
        total = len(ANCHORS)
        self.assertEqual(cover, {"en": (total, total), "fr": (1, total), "de": (0, total)})

    def test_a_feature_is_left_out_when_its_condition_does_not_hold(self):
        chapters = book().visible({"about"})
        self.assertEqual([f["id"] for f in chapters[0]["features"]], ["a", "b"])
        chapters = book().visible(set())
        self.assertEqual([f["id"] for f in chapters[0]["features"]], ["a"])

    def test_a_chapter_with_no_feature_left_is_dropped(self):
        sections = [
            {"id": "one", "features": [{"id": "a", "requires": "about"}, {"id": "b", "requires": "about"}]},
            {"id": "two", "features": [{"id": "c"}]},
        ]
        self.assertEqual([c["id"] for c in book(sections).visible(set())], ["two"])


class PageTests(Scratch):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.project()
        cls.pages = site_for(cls.proj, book()).render_all()

    def test_one_page_per_chapter_and_a_contents_page(self):
        self.assertIn("help-one.html", self.pages)
        self.assertIn("help-two.html", self.pages)
        self.assertIn("how-to.html", self.pages)

    def test_each_feature_is_a_section_with_its_anchor_as_the_id(self):
        page = self.pages["help-one.html"]
        for anchor in ("a", "b"):
            self.assertEqual(page.count(f'<section class="help-feature" id="{anchor}" data-feature="{anchor}"'), 1, anchor)
        self.assertEqual(self.pages["help-two.html"].count('id="c"'), 1)

    def test_the_keys_and_touch_lines_are_shown_when_the_entry_has_them(self):
        page = self.pages["help-one.html"]
        self.assertIn("<dd>Press a.</dd>", page)
        self.assertIn("<dd>Tap a.</dd>", page)
        self.assertEqual(page.count('<dl class="help-ways">'), 1, "b has neither")

    def test_a_list_block_is_rendered(self):
        self.assertIn('<ul class="notes"><li>x</li><li>y</li></ul>', self.pages["help-two.html"])

    def test_the_contents_page_links_every_chapter_and_feature(self):
        page = self.pages["how-to.html"]
        for href in ("help-one.html", "help-one.html#a", "help-one.html#b", "help-two.html", "help-two.html#c"):
            self.assertIn(f'href="{href}"', page, href)

    def test_a_feature_that_needs_an_about_page_is_left_out_of_an_edition_without_one(self):
        pages = site_for(self.proj, book(), drop_about=True).render_all()
        self.assertNotIn('id="b"', pages["help-one.html"])
        self.assertNotIn("help-one.html#b", pages["how-to.html"])
        self.assertIn("help-one.html#a", pages["how-to.html"])

    def test_the_trail_runs_through_about_and_the_contents_and_back_goes_to_the_contents(self):
        page = self.pages["help-one.html"]
        self.assertIn('<a href="about.html">', page)
        self.assertIn('<a href="how-to.html">', page)
        self.assertIn('class="rail-link back" href="how-to.html"', page)
        self.assertIn('<span aria-current="page">', page)

    def test_without_an_about_page_the_trail_runs_through_settings(self):
        pages = site_for(self.proj, book(), drop_about=True).render_all()
        self.assertIn('<a href="settings.html">', pages["help-one.html"])

    def test_chapters_have_a_previous_and_next_link_like_a_book(self):
        self.assertNotIn('class="prev"', self.pages["help-one.html"])
        self.assertIn('class="next" href="help-two.html"', self.pages["help-one.html"])
        self.assertIn('class="prev" href="help-one.html"', self.pages["help-two.html"])
        self.assertNotIn('class="next"', self.pages["help-two.html"])

    def test_a_book_of_one_chapter_has_no_pager(self):
        one = helpbook.SECTIONS[:1]
        keep = {f["id"] for f in one[0]["features"]}
        texts = copy.deepcopy(helpbook.Book.load({}).texts)
        texts["en"]["features"] = {k: v for k, v in texts["en"]["features"].items() if k in keep}
        texts["en"]["chapters"] = {k: v for k, v in texts["en"]["chapters"].items() if k == one[0]["id"]}
        pages = site_for(self.proj, helpbook.Book(one, texts)).render_all()
        self.assertNotIn('class="pager"', pages["help-finding-your-way.html"])

    def test_english_text_in_an_interface_that_is_not_english_is_marked_as_english(self):
        page = self.pages["help-one.html"]
        self.assertIn('<article class="about-text help-text" id="about-en" lang="en">', page)
        self.assertEqual(page.count('class="about-bar"'), 0, "one language, so no toggle")

    def test_a_language_with_help_of_its_own_gets_a_toggle_and_falls_back_per_entry(self):
        texts = copy.deepcopy(book().texts)
        texts["qab"] = {"chapters": {"one": {"title": "Un"}}, "features": {"a": {"title": "Ah", "body": ["Sur a."]}}}
        texts["qac"] = {"features": {"c": {"title": "Cee", "body": ["Sur c."]}}}
        pages = site_for(self.proj, book(texts=texts), pair=("qab", "qac")).render_all()
        page = pages["help-one.html"]
        self.assertEqual(page.count('class="about-bar"'), 1)
        article = page[page.index('id="about-qab"') : page.index('id="about-qac"')]
        self.assertIn("<h2>Ah</h2>", article)
        self.assertRegex(article, r'id="b"[^>]*lang="en"', "a missing entry is English, and says so")
        ids = BuiltBookTests.ids(None, page)
        self.assertEqual(len(ids), len(set(ids)), "an id appears once even with two articles")
        self.assertIn('id="a-qac" data-feature="a"', page, "the second article's sections take the language as a suffix")

    def test_the_conditions_a_site_can_answer_are_the_ones_the_book_may_ask_for(self):
        site = site_for(self.proj, book())
        self.assertLessEqual(site.help_conditions(), set(helpbook.CONDITIONS))
        self.assertNotIn("related", site.help_conditions())
        raw = content.read(self.proj)
        fixture.edit(self.proj / "pages" / "p1.json", lambda d: d.update(related=["points"]))
        related = phrasebook.Site(content.read(self.proj), content.pick_edition(raw)[1], help_book=book())
        self.assertIn("related", related.help_conditions())
        fixture.edit(self.proj / "pages" / "p1.json", lambda d: d.pop("related"))

    def test_every_condition_the_real_book_asks_for_exists(self):
        asked = {f.get("requires") for c in helpbook.SECTIONS for f in c["features"]} - {None}
        self.assertLessEqual(asked, set(helpbook.CONDITIONS))

    def test_every_help_page_is_precached_so_it_works_offline(self):
        out = self.tmp / "offline"
        quiet_build(out, project_dir=self.proj)
        self.assertIn('"help-finding-your-way.html"', (out / "sw.js").read_text(encoding="utf-8"))

    def test_a_topic_cannot_take_a_name_that_starts_like_a_help_page(self):
        proj = self.project()
        fixture.write(proj / "pages" / "help-me.json", {"sections": [{"id": "s", "concepts": ["c"]}]})
        fixture.edit(proj / "structure.json", lambda d: d["groups"][0]["pages"].append("help-me"))
        with self.assertRaises(ContentError) as ctx:
            content.validate(content.read(proj))
        self.assertIn("reserved", str(ctx.exception))

    def test_a_pack_help_file_is_read_and_checked_for_normal_form(self):
        proj = self.project()
        fixture.write(proj / "packs" / "qaa" / "help.json", {"features": {"tiles": {"title": "é", "body": ["x"]}}})
        raw = content.read(proj)
        self.assertEqual(raw["packs"]["qaa"]["help"]["features"]["tiles"]["body"], ["x"])
        with self.assertRaises(ContentError) as ctx:
            content.validate(raw)
        self.assertIn("normal form", str(ctx.exception))


class BuildTests(Scratch):
    def test_the_build_reports_help_coverage_per_language(self):
        import contextlib
        import io

        proj = self.project()
        fixture.write(proj / "packs" / "qab" / "help.json", {"features": {"tiles": {"title": "T", "body": ["x"]}}})
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            phrasebook.cli.main([str(self.tmp / "dist"), "--project", str(proj)])
        total = len(ANCHORS)
        self.assertIn(f"help: qaa 0/{total}, qab 1/{total}", out.getvalue())

    def test_the_stylesheet_styles_the_help_pages(self):
        css = (ENGINE / "assets" / "style.css").read_text(encoding="utf-8")
        for selector in (".help-feature", ".help-ways", ".help-contents"):
            self.assertIn(selector, css)

    def test_help_text_names_no_anchor_it_does_not_have(self):
        for entry in EN["features"].values():
            for block in entry["body"]:
                if isinstance(block, dict) and "links" in block:
                    for link in block["links"]:
                        match = re.match(r"help-([a-z-]+)\.html#([a-z-]+)$", link["href"])
                        if match:
                            self.assertIn(match.group(2), ANCHORS)


class BuiltBookTests(Scratch):
    """The real book, built on the fixture: what the reader gets."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        proj = cls.project()
        fixture.edit(proj / "pages" / "p1.json", lambda d: d.update(related=["points"]))  # so the Related topics feature applies
        cls.pages = cls.built(proj)
        cls.help_pages = {n: t for n, t in cls.pages.items() if n.startswith("help-") or n == "how-to.html"}

    def ids(self, text):
        found = []

        class Collect(HTMLParser):
            def handle_starttag(self, tag, attrs):
                found.extend(v for k, v in attrs if k == "id")

        Collect().feed(text)
        return found

    def test_there_is_a_page_for_every_chapter_and_the_contents(self):
        self.assertEqual(set(self.help_pages), {"how-to.html", "help-finding-your-way.html", "help-looking-up-words.html", "help-reading-a-topic.html", "help-your-settings.html"})

    def test_every_anchor_is_an_id_exactly_once_in_the_book_and_ids_are_unique_on_each_page(self):
        book_ids = [i for name, text in self.help_pages.items() if name.startswith("help-") for i in self.ids(text)]
        for anchor in ANCHORS:
            self.assertEqual(book_ids.count(anchor), 1, anchor)
            self.assertNotIn(anchor, self.ids(self.pages["how-to.html"]), "the contents links to anchors and does not repeat them")
        for name, text in self.help_pages.items():
            ids = self.ids(text)
            self.assertEqual(len(ids), len(set(ids)), f"{name}: duplicate ids")

    def test_the_book_has_no_unrendered_template_and_makes_no_request_to_another_site(self):
        for name, text in self.help_pages.items():
            self.assertNotIn("{{", text, name)
            self.assertNotIn("}}", text, name)
            self.assertNotRegex(text, r'(src|href)="https?://', name)
            self.assertNotIn("<script src=\"http", text, name)

    def test_every_link_in_the_contents_goes_to_a_real_anchor(self):
        chapter_ids = {n: set(self.ids(t)) for n, t in self.pages.items()}
        for href in re.findall(r'href="(help-[a-z-]+\.html)(?:#([a-z-]+))?"', self.pages["how-to.html"]):
            page, anchor = href
            self.assertIn(page, self.pages, page)
            if anchor:
                self.assertIn(anchor, chapter_ids[page], f"{page}#{anchor}")

    def test_every_help_entry_is_well_formed(self):
        for ident, entry in EN["features"].items():
            self.assertTrue(entry["title"].strip(), ident)
            self.assertTrue(entry["body"], ident)
            for block in entry["body"]:
                self.assertTrue(isinstance(block, str) and block.strip() or isinstance(block, dict) and set(block) <= {"list", "links"}, ident)
            for field in ("keys", "touch"):
                if field in entry:
                    self.assertTrue(isinstance(entry[field], str) and entry[field].strip(), f"{ident} {field}")
            self.assertLessEqual(set(entry), {"title", "body", "keys", "touch"}, ident)
        for chapter in EN["chapters"].values():
            self.assertLessEqual(set(chapter), {"title", "lede"})

    def test_help_text_is_in_normal_form_c(self):
        import unicodedata

        text = (ENGINE / "help" / "en.json").read_text(encoding="utf-8")
        self.assertEqual(unicodedata.normalize("NFC", text), text)


if __name__ == "__main__":
    unittest.main()
