"""Framework tests. They run on the neutral made-up project in fixture.py, not on any real language.

The point of these tests: the engine (phrasebook/) must work, and must be reusable, with nothing of the
English and Welsh project in it. Run from the repo root:  python3 -m unittest discover -s tests -v
"""

import atexit
import contextlib
import io
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import unittest
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import fixture  # noqa: E402
import phrasebook  # noqa: E402
from phrasebook import channels, cli, content, dictionary, palettes, plural  # noqa: E402
from phrasebook.errors import ContentError  # noqa: E402
from phrasebook.messages import Messages  # noqa: E402

ENGINE = ROOT / "phrasebook"
EN = json.loads((ENGINE / "messages" / "en.json").read_text(encoding="utf-8"))
# A project to check for leaks into the engine: the one named by PHRASEBOOK_PROJECT (a project repository sets it to its own
# content folder, so the real words are checked), else the made-up fixture project.
CHECKED_PROJECT = os.environ.get("PHRASEBOOK_PROJECT")


def plural_engine():
    """A copy of the message catalogue with one plural message added, since the framework itself ships none."""
    folder = pathlib.Path(tempfile.mkdtemp())
    shutil.copytree(ENGINE / "messages", folder / "messages")
    en = json.loads((folder / "messages" / "en.json").read_text(encoding="utf-8"))
    en["entries"] = {"one": "{n} entry", "other": "{n} entries"}
    (folder / "messages" / "en.json").write_text(json.dumps(en, ensure_ascii=False), encoding="utf-8")
    atexit.register(shutil.rmtree, folder, True)
    return folder / "messages"


PLURAL_ENGINE = plural_engine()


def quiet_build(*args, **kw):
    """Build, hiding the warning about draft sources (the fixture has one on purpose)."""
    with contextlib.redirect_stderr(io.StringIO()):
        return phrasebook.build(*args, **kw)


def forms(template):
    return list(template.values()) if isinstance(template, dict) else [template]


class Scratch(unittest.TestCase):
    """Gives each test class a scratch folder and a way to make fresh copies of the fixture."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp())
        cls.count = 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def project(cls, **kw):
        cls.count += 1
        return fixture.make_project(cls.tmp / f"p{cls.count}", **kw)

    @classmethod
    def built(cls, project, **kw):
        cls.count += 1
        out = cls.tmp / f"out{cls.count}"
        quiet_build(out, project_dir=project, **kw)
        return {f.name: f.read_text(encoding="utf-8") for f in out.glob("*.html")}


# ---------------------------------------------------------------- the separation itself


class EngineIsLanguageNeutral(unittest.TestCase):
    """Nothing of any project may live in the engine."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def forbidden(self):
        raw = content.read(pathlib.Path(CHECKED_PROJECT) if CHECKED_PROJECT else fixture.make_project(self.tmp / "checked"))
        words = {"Welsh", "Cymraeg", "Cymru", "Gair", "Llaeth"}
        _, edition = content.pick_edition(raw)
        words.add(edition["name"])
        for code, pack in raw["packs"].items():
            if code != "en":  # English is the framework's fallback catalogue, by design
                words.add(pack["meta"]["name"])
                words.add(pack["meta"]["ui"]["endonym"])
        codes = [c for c in raw["packs"] if c != "en"]
        return words, codes

    def engine_files(self):
        files = [p for p in ENGINE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != "plural.py"]
        return files + [ROOT / "build.py"]  # plural.py is a table of rules for many languages, by design

    def test_the_engine_names_no_language_or_phrase_of_the_project(self):
        words, codes = self.forbidden()
        for f in self.engine_files():
            text = f.read_text(encoding="utf-8")
            for w in words:
                self.assertNotIn(w, text, f"{f.relative_to(ROOT)} mentions {w!r}")
            for c in codes:
                self.assertIsNone(re.search(rf"\b{re.escape(c)}\b(?!=)", text), f"{f.relative_to(ROOT)} mentions the code {c!r}")

    def test_the_engine_ships_no_project_content(self):
        names = {p.name for p in ENGINE.iterdir()}
        self.assertFalse(names & {"data", "packs", "pages", "editions", "structure.json"}, names)

    def test_the_engine_stylesheet_has_no_fonts_or_language_rules(self):
        css = (ENGINE / "assets" / "style.css").read_text(encoding="utf-8")
        self.assertNotIn("@import", css)
        self.assertNotIn("http", css)
        self.assertIsNone(re.search(r'\[lang="', css), "language selectors belong in a project stylesheet")
        self.assertNotIn('"Literata"', css)

    def test_the_engine_stylesheet_uses_logical_properties(self):
        css = (ENGINE / "assets" / "style.css").read_text(encoding="utf-8")
        for physical in (
            "margin-left",
            "margin-right",
            "padding-left",
            "padding-right",
            "border-left",
            "border-right:1px",
            "text-align:left",
            "text-align:right",
        ):
            self.assertNotIn(physical, css, f"use a logical property instead of {physical}")


class FixtureBuildTests(Scratch):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.project()
        cls.pages = cls.built(cls.proj)
        cls.raw = content.read(cls.proj)
        cls.ed = content.pick_edition(cls.raw)[1]

    def test_a_project_the_engine_has_never_seen_builds(self):
        self.assertEqual(
            set(self.pages),
            {
                "index.html",
                "group-g1.html",
                "p1.html",
                "points.html",
                "sources.html",
                "how-to.html",
                "settings.html",
                "about.html",
            },
        )

    def test_no_trace_of_the_real_project_in_the_output(self):
        for name, text in self.pages.items():
            for word in ("Welsh", "Cymraeg", "Gair", 'lang="cy"'):
                self.assertNotIn(word, text, name)

    def test_roles_not_languages_name_the_classes(self):
        p1 = self.pages["p1.html"]
        self.assertIn('class="l1"', p1)
        self.assertIn('class="l2"', p1)
        self.assertNotIn('class="en"', p1)

    def test_text_in_the_second_language_is_marked_and_the_interface_language_is_not(self):
        p1 = self.pages["p1.html"]
        self.assertIn('<html lang="qaa" data-storage="demo-book"', p1)
        self.assertIn('<th scope="row" class="l1">', p1)  # forms or plain; the first language is the interface
        self.assertIn('lang="qab"', p1)
        self.assertEqual(p1.count('lang="qaa"'), 1, "only the document itself is marked as the interface language")

    def test_a_right_to_left_language_is_marked_with_its_direction(self):
        site = phrasebook.Site(self.raw, self.ed, pair=("qaa", "qac"))
        page = site.render_all()["p1.html"]
        self.assertIn('lang="qac" dir="rtl"', page)
        self.assertNotIn('<html lang="qaa" dir', page)

    def test_the_figure_names_the_languages_with_the_names_the_pack_gives(self):
        self.assertIn("Compass rose labelled in Betan and Alphan", self.pages["points.html"])

    def test_the_page_title_comes_from_a_message(self):
        self.assertIn("<title>qaa page | Demo Book</title>", self.pages["p1.html"])

    def test_the_regional_control_names_the_language_through_a_message(self):
        self.assertIn("Betan: regional forms", self.pages["settings.html"])

    def test_no_third_party_request_without_the_project_asking(self):
        for name, text in self.pages.items():
            self.assertIsNone(
                re.search(r'(?:<link[^>]*\shref|\ssrc)="https?://', text), name
            )  # nothing is loaded; a link a person follows is theirs to follow
        self.assertNotIn("fonts.googleapis", "".join(self.pages.values()))

    def test_licence_words_come_from_messages(self):
        sources = self.pages["sources.html"]
        self.assertIn("Written by the author", sources)
        self.assertIn("Public domain", sources)
        self.assertIn("Unreviewed draft", sources)


# ---------------------------------------------------------------- messages


class PluralRuleTests(unittest.TestCase):
    def cats(self, lang, numbers):
        return [plural.category(lang, n) for n in numbers]

    def test_english(self):
        self.assertEqual(self.cats("en", [0, 1, 2]), ["other", "one", "other"])

    def test_welsh_has_six_forms(self):
        self.assertEqual(self.cats("cy", [0, 1, 2, 3, 6, 4, 11]), ["zero", "one", "two", "few", "many", "other", "other"])

    def test_russian(self):
        self.assertEqual(
            self.cats("ru", [1, 2, 5, 11, 21, 22, 25, 111]), ["one", "few", "many", "many", "one", "few", "many", "many"]
        )

    def test_polish(self):
        self.assertEqual(self.cats("pl", [1, 2, 5, 12, 22, 0]), ["one", "few", "many", "many", "few", "many"])

    def test_arabic(self):
        self.assertEqual(
            self.cats("ar", [0, 1, 2, 3, 10, 11, 99, 100]), ["zero", "one", "two", "few", "few", "many", "many", "other"]
        )

    def test_irish_and_scottish_gaelic(self):
        self.assertEqual(self.cats("ga", [1, 2, 4, 8, 11]), ["one", "two", "few", "many", "other"])
        self.assertEqual(self.cats("gd", [1, 11, 2, 12, 3, 19, 20]), ["one", "one", "two", "two", "few", "few", "other"])

    def test_french_counts_zero_as_one_and_japanese_has_no_plural(self):
        self.assertEqual(self.cats("fr", [0, 1, 2]), ["one", "one", "other"])
        self.assertEqual(self.cats("ja", [0, 1, 2]), ["other"] * 3)

    def test_a_regional_tag_uses_its_language(self):
        self.assertEqual(plural.category("cy-gwent", 2), "two")

    def test_private_use_codes_are_allowed_and_unknown_languages_are_not(self):
        self.assertEqual(plural.category("qaa", 1), "one")
        with self.assertRaises(KeyError):
            plural.category("zz", 1)

    def test_every_rule_only_produces_declared_categories(self):
        for lang, (declared, _) in plural.RULES.items():
            self.assertEqual(declared[-1], "other", lang)
            produced = {plural.category(lang, n) for n in range(0, 1000)}
            self.assertLessEqual(produced, set(declared), lang)


def packs_with(**ui_by_code):
    return {code: {"meta": {"ui": ui}} for code, ui in ui_by_code.items()}


class MessageTests(unittest.TestCase):
    def test_a_pack_overrides_the_framework_catalogue(self):
        m = Messages(packs_with(qaa={"home": "Casa"}))
        self.assertEqual(m.format("qaa", "home"), ("Casa", "qaa"))

    def test_a_missing_message_falls_back_to_english_and_says_so(self):
        m = Messages(packs_with(qaa={"endonym": "x"}))
        self.assertEqual(m.format("qaa", "home"), ("Home", "en"))

    def test_a_regional_tag_falls_back_to_its_language_first(self):
        m = Messages(packs_with(qaa={"home": "Casa"}))
        self.assertEqual(m.format("qaa-zz", "home"), ("Casa", "qaa"))
        self.assertEqual(m.format("qab-zz", "home"), ("Home", "en"))

    def test_unknown_keys_are_an_error_not_silence(self):
        with self.assertRaises(KeyError):
            Messages({}).format("en", "nope")

    def test_placeholders_are_filled_and_html_mode_escapes_only_the_message(self):
        m = Messages(packs_with(qaa={"home_about": "<b>{about}</b> & {link}"}))
        self.assertEqual(m.format("qaa", "home_about", about="a", link="b")[0], "<b>a</b> & b")
        self.assertEqual(
            m.format("qaa", "home_about", html_mode=True, about="<i>a</i>", link="b")[0], "&lt;b&gt;<i>a</i>&lt;/b&gt; &amp; b"
        )

    def test_a_count_selects_the_plural_form_of_the_messages_own_language(self):
        m = Messages(packs_with(qaa={"entries": {"one": "{n} uno", "other": "{n} mas"}}), engine_dir=PLURAL_ENGINE)
        self.assertEqual(m.format("qaa", "entries", n=1)[0], "1 uno")
        self.assertEqual(m.format("qaa", "entries", n=7)[0], "7 mas")
        self.assertEqual(m.format("en", "entries", n=1)[0], "1 entry")

    def test_a_plural_message_needs_a_count(self):
        with self.assertRaises(ValueError):
            Messages({}, engine_dir=PLURAL_ENGINE).format("en", "entries")

    def test_lists(self):
        m = Messages({})
        self.assertEqual(m.join("en", ["a"]), "a")
        self.assertEqual(m.join("en", ["a", "b"]), "a and b")
        self.assertEqual(m.join("en", ["a", "b", "c"]), "a, b and c")
        self.assertEqual(m.join("en", ["a", "b", "c", "d"]), "a, b, c and d")

    def test_list_patterns_follow_the_locale(self):
        m = Messages(
            packs_with(
                qaa={
                    "list_two": "{first} & {second}",
                    "list_end": "{first} + {second}",
                    "list_start": "{first}; {second}",
                    "list_middle": "{first}; {second}",
                }
            )
        )
        self.assertEqual(m.join("qaa", ["a", "b", "c", "d"]), "a; b; c + d")

    def check(self, **ui):
        Messages(packs_with(**ui), engine_dir=PLURAL_ENGINE).validate()

    def test_the_framework_catalogue_is_valid(self):
        Messages({}).validate()

    def test_a_valid_override_passes(self):
        self.check(qaa={"endonym": "x", "home": "Casa", "entries": {"one": "{n} u", "other": "{n} m"}})

    def test_unknown_message_keys_are_rejected(self):
        with self.assertRaises(ContentError) as ctx:
            self.check(qaa={"hom": "x"})
        self.assertIn("unknown message 'hom'", str(ctx.exception))

    def test_changed_placeholders_are_rejected(self):
        for bad in ("{about}", "{about} {link} {extra}", "{link}"):
            with self.assertRaises(ContentError, msg=bad):
                self.check(qaa={"home_about": bad})

    def test_plural_messages_must_have_plural_forms_and_plain_ones_must_not(self):
        with self.assertRaises(ContentError):
            self.check(qaa={"entries": "{n}"})
        with self.assertRaises(ContentError):
            self.check(qaa={"home": {"one": "a", "other": "b"}})

    def test_a_plural_message_needs_exactly_the_languages_forms(self):
        with self.assertRaises(ContentError) as ctx:
            self.check(cy={"entries": {"one": "{n} a", "other": "{n} b"}})
        self.assertIn("zero, one, two, few, many, other", str(ctx.exception))
        self.check(cy={"entries": {c: "{n} x" for c in plural.categories("cy")}})

    def test_a_language_without_rules_is_told_where_to_add_them(self):
        with self.assertRaises(ContentError) as ctx:
            self.check(zz={"entries": {"one": "{n} a", "other": "{n} b"}})
        self.assertIn("plural.py", str(ctx.exception))

    def test_empty_text_is_rejected(self):
        with self.assertRaises(ContentError):
            self.check(qaa={"home": ""})

    def test_the_catalogue_uses_unicode_not_html_entities(self):
        for key, template in EN.items():
            for text in forms(template):
                self.assertIsNone(re.search(r"&\w+;", text), key)


class LocalisedInterfaceTests(Scratch):
    """Every interface string must come from the catalogue. A pseudo-translation proves it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pseudo_ui = {
            k: ({c: fixture.pseudo(t) for c, t in v.items()} if isinstance(v, dict) else fixture.pseudo(v)) for k, v in EN.items()
        }
        cls.proj = cls.project(ui_extra={code: pseudo_ui for code in fixture.LANGS})
        cls.raw = content.read(cls.proj)
        cls.ed = content.pick_edition(cls.raw)[1]
        cls.messages = Messages(cls.raw["packs"])
        cls.pages = phrasebook.Site(cls.raw, cls.ed, messages=cls.messages).render_all()

    def test_the_pseudo_translation_is_valid(self):
        content.validate(self.raw)

    def test_no_english_interface_text_survives(self):
        html_all = "\n".join(self.pages.values())
        leaks = []
        for key, template in EN.items():
            for text in forms(template):
                literal = re.sub(r"\{\w+\}", "", text).strip(" ,.:|→")
                if len(literal) >= 4 and literal in html_all:
                    leaks.append((key, literal))
        self.assertEqual(leaks, [], "hard-coded or fallen-back English in the output")

    def test_the_pseudo_text_is_what_reaches_the_page(self):
        home = self.pages["index.html"]
        self.assertIn(fixture.pseudo("Skip to content"), home)

    def test_every_message_is_used_and_none_is_missing(self):
        self.messages.join("qaa", ["a", "b"])  # the two-item list pattern is not reached by the pages
        self.assertEqual(set(EN) - self.messages.used, set(), "messages nothing uses")
        self.assertLessEqual(self.messages.used, set(EN))

    def test_attributes_are_localised_too(self):
        everything = "".join(self.pages.values())
        for key in ("pager_label", "on_this_page", "trail_label", "topics_label"):
            self.assertIn(f'aria-label="{fixture.pseudo(EN[key])}"', everything, key)

    def test_a_pack_without_translations_falls_back_visibly_to_english(self):
        proj = self.project(interface="qab")
        pages = self.built(proj)
        page = pages["index.html"]
        self.assertIn('<html lang="qab" data-storage="demo-book">', page)
        self.assertIn('<span lang="en">Skip to content</span>', page)
        self.assertNotIn('<span lang="qab">Skip', page)

    def test_a_right_to_left_interface_sets_the_document_direction_and_marks_english(self):
        proj = self.project(interface="qac")
        page = self.built(proj)["index.html"]
        self.assertIn('<html lang="qac" dir="rtl" data-storage="demo-book">', page)
        self.assertIn('<span lang="en" dir="ltr">Skip to content</span>', page)

    def test_the_pair_arrow_is_part_of_the_message_not_the_code(self):
        proj = self.project(ui_extra={"qaa": {"pair_label": "{second} ← {first}"}})
        page = self.built(proj)["index.html"]
        self.assertIn("<small>", page)
        self.assertRegex(page, r"<small><span lang=\"qab\">Betish</span> ← Alphish</small>")


class CommentaryLanguageTests(Scratch):
    def test_commentary_in_another_language_is_marked_as_such(self):
        proj = self.project()
        fixture.edit(proj / "packs" / "qac" / "pack.json", lambda d: d.update(commentary_lang="qab"))
        site = phrasebook.Site(content.read(proj), content.pick_edition(content.read(proj))[1], pair=("qaa", "qac"))
        page = site.render_all()["p1.html"]
        self.assertIn(
            '<small class="note"><span lang="qab">A note on <span lang="qac" dir="rtl">qac two</span></span></small>', page
        )

    def test_commentary_defaults_to_the_interface_language(self):
        proj = self.project()
        raw = content.read(proj)
        site = phrasebook.Site(raw, content.pick_edition(raw)[1], pair=("qaa", "qab"))
        self.assertEqual(site.markup("qab", "A {{word}}"), 'A <span lang="qab">word</span>')

    def test_commentary_language_must_be_a_language_code(self):
        proj = self.project()
        fixture.edit(proj / "packs" / "qab" / "pack.json", lambda d: d.update(commentary_lang="Not A Code"))
        with self.assertRaises(ContentError):
            content.validate(content.read(proj))


# ---------------------------------------------------------------- listen-first rows, order lines and linked tiles


class ListenFirstTests(Scratch):
    def site(self, proj, pair=("qaa", "qab")):
        raw = content.read(proj)
        return phrasebook.Site(raw, content.pick_edition(raw)[1], pair=pair), raw

    def test_other_forms_a_word_is_heard_as_are_shown_under_its_row_in_the_language_they_are_written_in(self):
        proj = self.project()
        fixture.edit(
            proj / "packs" / "qab" / "pages" / "p1.json", lambda d: d["sections"]["s1"]["concepts"]["c1"].update(also=["qab uno"])
        )
        page = self.site(proj)[0].render_all()["p1.html"]
        self.assertRegex(page, r'<tr class="also-row"><td colspan="2"><span class="also-label">.*?Also heard as.*?</span> ')
        self.assertIn('<span class="also-form" lang="qab">qab uno</span>', page)

    def test_only_a_row_that_has_other_forms_gets_an_extra_row(self):
        page = self.site(self.project())[0].render_all()["p1.html"]
        self.assertEqual(page.count('class="also-row"'), 1)

    def test_the_other_forms_must_be_new_non_empty_texts(self):
        for bad in ([""], "qab one", ["qab one"], ["x", "x"]):
            proj = self.project()
            fixture.edit(
                proj / "packs" / "qab" / "pages" / "p1.json",
                lambda d, bad=bad: d["sections"]["s1"]["concepts"]["c1"].update(also=bad),
            )
            with self.assertRaises(ContentError, msg=repr(bad)):
                content.validate(content.read(proj))

    def test_the_dictionary_carries_the_other_forms_for_search(self):
        proj = self.project()
        fixture.edit(
            proj / "packs" / "qab" / "pages" / "p1.json", lambda d: d["sections"]["s1"]["concepts"]["c1"].update(also=["qab uno"])
        )
        site, raw = self.site(proj)
        entry = next(e for e in dictionary.index(raw, content.pick_edition(raw)[1])["entries"] if e["concept"] == "c1")
        self.assertEqual(entry["also"], {"qab": ["qab uno"]})
        self.assertEqual([t["text"] for t in entry["terms"]["qab"]], ["qab one"])

    def test_a_section_can_say_in_what_order_its_words_run(self):
        proj = self.project()
        fixture.edit(
            proj / "packs" / "qab" / "pages" / "p1.json", lambda d: d["sections"]["s1"].update(order="lightest to heaviest")
        )
        page = self.site(proj)[0].render_all()["p1.html"]
        self.assertRegex(page, r'<p class="order">.*?Order: lightest to heaviest.*?</p>')

    def test_a_group_shows_the_pages_it_links_to_as_tiles_after_its_own(self):
        proj = self.project()
        fixture.edit(
            proj / "structure.json",
            lambda d: d.update(groups=[{"id": "g1", "pages": ["p1"], "links": ["points"]}, {"id": "g2", "pages": ["points"]}]),
        )
        fixture.edit(proj / "packs" / "qab" / "pack.json", lambda d: d["groups"].update(g2="qab group two"))
        fixture.edit(proj / "packs" / "qaa" / "pack.json", lambda d: d["groups"].update(g2="qaa group two"))
        fixture.edit(proj / "packs" / "qac" / "pack.json", lambda d: d["groups"].update(g2="qac group two"))
        pages = self.site(proj)[0].render_all()
        g1 = pages["group-g1.html"]
        self.assertLess(g1.index('href="p1.html"'), g1.index('href="points.html"'))
        self.assertIn('href="points.html"', pages["group-g2.html"])

    def test_a_link_must_name_a_page_that_is_not_already_in_the_group(self):
        for links in (["nowhere"], ["p1"], ["points", "points"]):
            proj = self.project()
            fixture.edit(proj / "structure.json", lambda d, links=links: d["groups"][0].update(links=links))
            with self.assertRaises(ContentError, msg=repr(links)):
                content.validate(content.read(proj))

    def test_a_held_back_page_leaves_the_links_that_point_at_it_and_a_link_does_not_keep_a_group_alive(self):
        proj = self.project()
        fixture.edit(
            proj / "structure.json",
            lambda d: d.update(
                groups=[
                    {"id": "g1", "pages": ["p1"]},
                    {"id": "g2", "pages": ["points"], "links": ["p1"]},
                    {"id": "g3", "pages": [], "links": ["points"]},
                ]
            ),
        )
        for code in fixture.LANGS:
            fixture.edit(proj / "packs" / code / "pack.json", lambda d: d["groups"].update(g2="two", g3="three"))
        fixture.edit(proj / "pages" / "p1.json", lambda d: [s.update(status="development") for s in d["sections"]])
        selected = channels.select(content.read(proj))
        self.assertEqual([g["id"] for g in selected["structure"]["groups"]], ["g2"])
        self.assertEqual(selected["structure"]["groups"][0]["links"], [])


# ---------------------------------------------------------------- the About page


class AboutPageTests(Scratch):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.project()
        cls.pages = cls.built(cls.proj)

    def test_the_page_has_each_language_and_shows_the_first_of_the_pair(self):
        page = self.pages["about.html"]
        self.assertIn('<article class="about-text" id="about-qaa"><header><h1>qaa about</h1>', page)
        self.assertIn('<article class="about-text" id="about-qab" lang="qab"><header><h1>qab about</h1>', page)
        self.assertIn('<input type="radio" class="about-radio" name="about-lang" id="about-lang-qaa" value="qaa" checked>', page)
        self.assertNotIn('id="about-lang-qab" value="qab" checked', page)

    def test_the_toggle_names_each_language_in_that_language_and_needs_no_script(self):
        page = self.pages["about.html"]
        bar = page[page.index('<div class="about-bar"') : page.index("</div>", page.index('<div class="about-bar"'))]
        self.assertIn('<label for="about-lang-qaa">Alphish</label>', bar)
        self.assertIn('<label for="about-lang-qab"><span lang="qab">Betish</span></label>', bar)
        self.assertNotIn("<script", page[page.index('<main id="main">') : page.index("</main>")])

    def test_the_sections_render_as_paragraphs_and_lists_and_link_to_the_sources(self):
        page = self.pages["about.html"]
        self.assertIn(
            '<section><h2>qaa aims</h2><p>qaa first paragraph</p><ul class="notes"><li>qaa one</li><li>qaa two</li></ul></section>',
            page,
        )
        self.assertEqual(page.count('<p class="about-more"><a href="sources.html">'), 2)

    def test_the_page_is_not_in_the_pager_and_its_trail_leads_home(self):
        page = self.pages["about.html"]
        self.assertNotIn('class="pager"', page)
        self.assertIn('<li><a href="index.html">', page)
        self.assertIn('<span aria-current="page">', page)

    def test_every_page_links_to_it_from_the_rail_above_the_settings_gear(self):
        for name, page in self.pages.items():
            rail = page[page.index('<nav class="rail"') : page.index("</nav>", page.index('<nav class="rail"'))]
            self.assertLess(rail.index('href="about.html"'), rail.rindex('href="settings.html"'), name)
        self.assertIn('href="about.html" aria-label="About" title="About" aria-current="page"', self.pages["about.html"])
        self.assertNotIn('href="about.html" aria-label="About" title="About" aria-current', self.pages["p1.html"])

    def test_the_settings_page_lists_it_with_the_other_pages_about_the_app(self):
        self.assertIn('<li><a href="about.html">', self.pages["settings.html"])

    def test_a_project_without_the_page_has_no_page_and_no_rail_link(self):
        proj = self.project()
        fixture.edit(proj / "editions" / "demo.json", lambda d: d.pop("about_page"))
        pages = self.built(proj)
        self.assertNotIn("about.html", pages)
        for name, page in pages.items():
            self.assertNotIn("about.html", page, name)

    def test_one_language_has_no_toggle(self):
        proj = self.project()
        fixture.edit(proj / "editions" / "demo.json", lambda d: d["about_page"].pop("qab"))
        page = self.built(proj)["about.html"]
        self.assertNotIn("about-bar", page)
        self.assertNotIn('id="about-qab"', page)

    def test_the_page_is_checked(self):
        for bad in (
            {"zzz": {"title": "t", "sections": [{"title": "s", "body": ["b"]}]}},
            {"qaa": {"sections": [{"title": "s", "body": ["b"]}]}},
            {"qaa": {"title": "t", "sections": []}},
            {"qaa": {"title": "t", "sections": [{"title": "s", "body": []}]}},
            {"qaa": {"title": "t", "sections": [{"title": "s", "body": [{"list": []}]}]}},
            {"qaa": {"title": "t", "sections": [{"title": "s", "body": [3]}]}},
            {},
        ):
            proj = self.project()
            fixture.edit(proj / "editions" / "demo.json", lambda d, bad=bad: d.update(about_page=bad))
            with self.assertRaises(ContentError, msg=repr(bad)):
                content.validate(content.read(proj))

    def test_a_quote_links_and_a_share_address_render(self):
        page = self.pages["about.html"]
        self.assertIn('<blockquote class="principle"><p>qaa founding statement</p></blockquote>', page)
        self.assertIn(
            '<ul class="links"><li><a href="https://example.org/x">qaa outside</a></li><li><a href="sources.html">qaa sources</a></li></ul>',
            page,
        )
        self.assertIn('<a href="https://example.org/book/">https://example.org/book/</a>', page)
        self.assertRegex(
            page, r'<button type="button" class="share" data-url="https://example.org/book/" data-copied="[^"]+" hidden>'
        )
        self.assertIn('class="share-status" role="status"', page)

    def test_a_held_back_about_section_is_left_out_of_the_release_but_built_in_development(self):
        self.assertNotIn("qaa soon", self.pages["about.html"])
        out = self.tmp / "about-dev"
        quiet_build(out, project_dir=self.proj, channel="development")
        self.assertIn("qaa soon", (out / "about.html").read_text(encoding="utf-8"))

    def test_a_language_with_every_section_held_back_is_dropped_and_so_is_a_page_with_none(self):
        proj = self.project()
        fixture.edit(
            proj / "editions" / "demo.json",
            lambda d: [s.update(status="development") for s in d["about_page"]["qab"]["sections"]],
        )
        page = self.built(proj)["about.html"]
        self.assertNotIn('id="about-qab"', page)
        self.assertNotIn("about-bar", page)
        fixture.edit(
            proj / "editions" / "demo.json",
            lambda d: [s.update(status="development") for s in d["about_page"]["qaa"]["sections"]],
        )
        pages = self.built(proj)
        self.assertNotIn("about.html", pages)
        for name, text in pages.items():
            self.assertNotIn("about.html", text, name)

    def test_a_section_status_must_be_a_known_one(self):
        proj = self.project()
        fixture.edit(proj / "editions" / "demo.json", lambda d: d["about_page"]["qaa"]["sections"][0].update(status="soon"))
        with self.assertRaises(ContentError):
            content.validate(content.read(proj))

    def test_the_new_blocks_are_checked(self):
        bad_blocks = (
            {"quote": ""},
            {"quote": 3},
            {"links": []},
            {"links": [{"text": "x", "href": "http://example.org"}]},
            {"links": [{"text": "x", "href": "javascript:alert(1)"}]},
            {"links": [{"text": "", "href": "https://example.org"}]},
            {"links": [{"text": "x"}]},
            {"share": "http://example.org"},
            {"share": "https://example.org with space"},
            {"share": ""},
            {"quote": "a", "list": ["b"]},
            {"mystery": "x"},
        )
        for block in bad_blocks:
            proj = self.project()
            fixture.edit(
                proj / "editions" / "demo.json",
                lambda d, block=block: d["about_page"]["qaa"]["sections"][0]["body"].append(block),
            )
            with self.assertRaises(ContentError, msg=repr(block)):
                content.validate(content.read(proj))

    def test_a_link_may_name_a_page_of_the_site_with_an_anchor(self):
        proj = self.project()
        fixture.edit(
            proj / "editions" / "demo.json",
            lambda d: d["about_page"]["qaa"]["sections"][0]["body"].append({"links": [{"text": "x", "href": "p1.html#s1"}]}),
        )
        content.validate(content.read(proj))

    def test_the_home_page_links_to_the_about_page_beside_the_sources(self):
        home = self.pages["index.html"]
        self.assertLess(home.index('<a href="about.html">'), home.index('<a href="sources.html">'))
        proj = self.project()
        fixture.edit(proj / "editions" / "demo.json", lambda d: d.pop("about_page"))
        self.assertNotIn('<a href="about.html">', self.built(proj)["index.html"])

    def test_about_is_a_reserved_page_name(self):
        proj = self.project()
        shutil.copy(proj / "pages" / "p1.json", proj / "pages" / "about.json")
        with self.assertRaises(ContentError):
            content.validate(content.read(proj))


# ---------------------------------------------------------------- text rules


class TextRuleTests(Scratch):
    def rejects(self, mutate, path, fragment):
        proj = self.project()
        fixture.edit(proj / path, mutate)
        with self.assertRaises(ContentError) as ctx:
            content.validate(content.read(proj))
        self.assertIn(fragment, str(ctx.exception))

    def test_text_must_be_in_normal_form_c(self):
        self.rejects(lambda d: d.update(title="ŵ"), "packs/qaa/pages/p1.json", "normal form C")

    def test_a_precomposed_letter_is_fine(self):
        proj = self.project()
        fixture.edit(proj / "packs" / "qaa" / "pages" / "p1.json", lambda d: d.update(title="ŵŷ"))
        content.validate(content.read(proj))

    def test_pack_metadata_is_checked_too(self):
        self.rejects(lambda d: d["groups"].update(g1="é"), "packs/qaa/pack.json", "normal form C")

    def test_edition_text_is_checked_too(self):
        self.rejects(lambda d: d.update(name="é"), "editions/demo.json", "normal form C")

    def test_invisible_bidirectional_controls_are_rejected(self):
        for char in ("‮", "⁦", "‏", "؜"):
            self.rejects(lambda d, c=char: d.update(title="a" + c + "b"), "packs/qac/pages/p1.json", "bidirectional")


# ---------------------------------------------------------------- editions and stylesheets


class StorageNameTests(Scratch):
    def page(self, **fields):
        proj = self.project()
        fixture.edit(proj / "editions" / "demo.json", lambda d: d.update(fields))
        return self.built(proj)["p1.html"]

    def test_the_default_is_a_slug_of_the_edition_name(self):
        self.assertIn('data-storage="demo-book"', self.page())

    def test_an_edition_can_name_its_own_storage(self):
        self.assertIn('data-storage="my.site_1"', self.page(storage="my.site_1"))

    def test_a_name_that_is_not_a_safe_identifier_is_rejected(self):
        for bad in ('x"y', "Has Space", "UPPER", "-lead", "a:b"):
            proj = self.project()
            fixture.edit(proj / "editions" / "demo.json", lambda d, b=bad: d.update(storage=b))
            with self.assertRaises(ContentError, msg=bad):
                content.validate(content.read(proj))

    def test_a_name_with_no_usable_letters_falls_back(self):
        proj = self.project()
        fixture.edit(proj / "editions" / "demo.json", lambda d: d.update(name="\u5c71"))
        self.assertIn('data-storage="phrasebook"', self.built(proj)["p1.html"])

    def test_storage_is_named_even_without_varieties_because_themes_are_saved(self):
        proj = self.project()
        for code in fixture.LANGS:
            fixture.edit(proj / "packs" / code / "pack.json", lambda d: d.pop("varieties", None))
        for code in fixture.LANGS:
            fixture.edit(
                proj / "packs" / code / "pages" / "p1.json",
                lambda d: d["sections"]["s2"]["concepts"].update(c2={"text": "plain"}),
            )
        page = self.built(proj)["p1.html"]
        self.assertIn('data-storage="demo-book"', page)
        self.assertIn('<script src="app.js"></script>', page)
        self.assertNotIn("data-variety-lang", page)


class StylesheetTests(Scratch):
    def edit_edition(self, proj, **fields):
        fixture.edit(proj / "editions" / "demo.json", lambda d: d.update(fields))

    def test_a_project_stylesheet_is_copied_and_linked_after_the_framework_one(self):
        proj = self.project()
        (proj / "static").mkdir()
        (proj / "static" / "extra.css").write_text("body{color:red}\n", encoding="utf-8")
        self.edit_edition(proj, stylesheets=["extra.css"])
        out = self.tmp / "css-out"
        quiet_build(out, project_dir=proj)
        page = (out / "p1.html").read_text(encoding="utf-8")
        self.assertLess(page.index('href="style.css"'), page.index('href="extra.css"'))
        self.assertTrue((out / "extra.css").is_file())
        self.assertTrue((out / "style.css").is_file())

    def test_fonts_are_linked_before_the_framework_stylesheet(self):
        proj = self.project()
        self.edit_edition(proj, fonts=["https://fonts.example/f.css"])
        page = self.built(proj)["p1.html"]
        self.assertLess(page.index("fonts.example"), page.index('href="style.css"'))

    def test_a_listed_stylesheet_must_exist(self):
        proj = self.project()
        self.edit_edition(proj, stylesheets=["missing.css"])
        with self.assertRaises(ContentError) as ctx:
            quiet_build(self.tmp / "x", project_dir=proj)
        self.assertIn("missing.css", str(ctx.exception))

    def test_unsafe_stylesheet_names_are_rejected(self):
        for bad in ("http://insecure.example/a.css", "../up.css", "/abs.css", "a.js", "javascript:alert(1)", "a b.css"):
            proj = self.project()
            self.edit_edition(proj, stylesheets=[bad])
            with self.assertRaises(ContentError, msg=bad):
                content.validate(content.read(proj))

    def test_folders_of_static_files_are_copied_whole(self):
        proj = self.project()
        (proj / "static" / "fonts").mkdir(parents=True)
        (proj / "static" / "fonts" / "a.woff2").write_bytes(b"wOF2")
        (proj / "static" / ".hidden").write_text("x", encoding="utf-8")
        out = self.tmp / "nested-out"
        quiet_build(out, project_dir=proj)
        self.assertEqual((out / "fonts" / "a.woff2").read_bytes(), b"wOF2")
        self.assertFalse((out / ".hidden").exists())

    def test_a_project_file_can_replace_a_framework_asset(self):
        proj = self.project()
        (proj / "static").mkdir()
        (proj / "static" / "style.css").write_text("/* mine */\n", encoding="utf-8")
        out = self.tmp / "replace-out"
        quiet_build(out, project_dir=proj)
        self.assertEqual((out / "style.css").read_text(encoding="utf-8"), "/* mine */\n")


class InstallTests(Scratch):
    """The manifest and service worker that make a build installable (section 3.2 of the app's docs/TODO.md: Installable offline app)."""

    def edit_edition(self, proj, **fields):
        fixture.edit(proj / "editions" / "demo.json", lambda d: d.update(fields))

    def test_a_project_with_no_icons_still_gets_a_valid_manifest(self):
        proj = self.project()
        out = self.tmp / "no-icons-out"
        quiet_build(out, project_dir=proj)
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "Demo Book")
        self.assertEqual(manifest["display"], "standalone")
        self.assertNotIn("icons", manifest)

    def test_icons_are_copied_and_listed_in_the_manifest(self):
        proj = self.project()
        (proj / "static" / "icons").mkdir(parents=True)
        (proj / "static" / "icons" / "i.png").write_bytes(b"\x89PNG")
        self.edit_edition(proj, icons=[{"src": "icons/i.png", "sizes": "192x192", "type": "image/png"}])
        out = self.tmp / "icons-out"
        quiet_build(out, project_dir=proj)
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["icons"], [{"src": "icons/i.png", "sizes": "192x192", "type": "image/png"}])
        self.assertEqual((out / "icons" / "i.png").read_bytes(), b"\x89PNG")

    def test_a_listed_icon_must_exist(self):
        proj = self.project()
        self.edit_edition(proj, icons=[{"src": "missing.png", "sizes": "192x192", "type": "image/png"}])
        with self.assertRaises(ContentError) as ctx:
            quiet_build(self.tmp / "x", project_dir=proj)
        self.assertIn("missing.png", str(ctx.exception))

    def test_unsafe_or_incomplete_icons_are_rejected(self):
        bad = [
            {"src": "../up.png", "sizes": "192x192", "type": "image/png"},
            {"src": "a.gif", "sizes": "192x192", "type": "image/png"},
            {"src": "a.png", "sizes": "192x192"},
            {"src": "a.png", "type": "image/png"},
            {"src": "a.png", "sizes": "192x192", "type": "image/png", "purpose": "invisible"},
        ]
        for icon in bad:
            proj = self.project()
            self.edit_edition(proj, icons=[icon])
            with self.assertRaises(ContentError, msg=icon):
                content.validate(content.read(proj))

    def test_a_short_name_overrides_the_full_name_in_the_manifest(self):
        proj = self.project()
        self.edit_edition(proj, short_name="Demo")
        out = self.tmp / "short-name-out"
        quiet_build(out, project_dir=proj)
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["short_name"], "Demo")

    def test_every_page_links_the_manifest_and_registers_the_service_worker(self):
        proj = self.project()
        page = self.built(proj)["p1.html"]
        self.assertIn('<link rel="manifest" href="manifest.json">', page)
        self.assertIn('navigator.serviceWorker.register("sw.js")', page)

    def test_start_url_is_a_precached_file_not_a_bare_directory(self):
        """A directory-style start_url ("./") is a different URL from the precached "index.html" to the
        cache, so relaunching offline would miss the cache and fail. start_url must name the file exactly.
        """
        proj = self.project()
        out = self.tmp / "start-url-out"
        quiet_build(out, project_dir=proj)
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        sw = (out / "sw.js").read_text(encoding="utf-8")
        files = json.loads(re.search(r"const FILES = (\[.*\]);", sw).group(1))
        self.assertIn(manifest["start_url"].lstrip("./"), files)

    def test_the_service_worker_precaches_exactly_the_built_files(self):
        proj = self.project()
        out = self.tmp / "sw-out"
        quiet_build(out, project_dir=proj)
        sw = (out / "sw.js").read_text(encoding="utf-8")
        files = json.loads(re.search(r"const FILES = (\[.*\]);", sw).group(1))
        on_disk = {str(p.relative_to(out)).replace("\\", "/") for p in out.rglob("*") if p.is_file() and p.name != "sw.js"}
        self.assertEqual(set(files), on_disk)
        self.assertNotIn("sw.js", files)

    def test_the_cache_version_changes_when_a_built_file_changes(self):
        proj = self.project()
        out1 = self.tmp / "v1"
        quiet_build(out1, project_dir=proj)
        version1 = re.search(r"phrasebook-([0-9a-f]+)", (out1 / "sw.js").read_text(encoding="utf-8")).group(1)
        fixture.edit(proj / "packs" / "qaa" / "pages" / "p1.json", lambda d: d.update(lede="A different lede."))
        out2 = self.tmp / "v2"
        quiet_build(out2, project_dir=proj)
        version2 = re.search(r"phrasebook-([0-9a-f]+)", (out2 / "sw.js").read_text(encoding="utf-8")).group(1)
        self.assertNotEqual(version1, version2)


class PaletteSiteTests(Scratch):
    """Light and dark, and colour palettes: built from data, chosen by the visitor, extensible by a project."""

    def edit_edition(self, proj, **fields):
        fixture.edit(proj / "editions" / "demo.json", lambda d: d.update(fields))

    def build_out(self, proj, name):
        out = self.tmp / name
        quiet_build(out, project_dir=proj)
        return out

    def add_palette(self, proj, pid, **fields):
        data = default_palette()
        data.update(fields)
        fixture.write(proj / "palettes" / f"{pid}.json", data)

    def test_palettes_css_is_written_and_linked_before_every_other_stylesheet(self):
        proj = self.project()
        (proj / "static").mkdir()
        (proj / "static" / "extra.css").write_text("body{}\n", encoding="utf-8")
        self.edit_edition(proj, stylesheets=["extra.css"])
        out = self.build_out(proj, "palettes-linked")
        page = (out / "p1.html").read_text(encoding="utf-8")
        self.assertTrue((out / "palettes.css").is_file())
        self.assertLess(page.index('href="palettes.css"'), page.index('href="style.css"'))
        self.assertLess(page.index('href="style.css"'), page.index('href="extra.css"'))

    def test_the_framework_stylesheet_sets_no_colour_of_its_own(self):
        css = (ENGINE / "assets" / "style.css").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", css), "colours belong in a palette")
        self.assertIsNone(re.search(r"--(bg|surface|ink|muted|rule|rule-strong|accent|star):", css))
        self.assertNotIn("color-scheme:", css)

    def test_the_settings_page_has_the_theme_controls_with_every_palette_by_name(self):
        for name, page in self.built(self.project()).items():
            if name != "settings.html":
                self.assertNotIn("data-pref=", page, name)
                continue
            self.assertIn('name="appearance" value="system" data-pref="appearance" checked', page, name)
            for value in ("light", "dark"):
                self.assertIn(f'name="appearance" value="{value}" data-pref="appearance"', page, name)
            for pid in ("default", "high-contrast", "red-green", "red-green-safe", "blue-yellow-safe"):
                self.assertIn(f'name="palette" value="{pid}" data-pref="palette"', page, name)
            self.assertIn('name="palette" value="default" data-pref="palette" checked', page, name)

    def test_the_controls_are_hidden_until_the_script_runs(self):
        page = self.built(self.project())["settings.html"]
        self.assertIn('<div class="prefs" id="prefs" hidden>', page)
        self.assertLess(page.index('<script src="app.js">'), page.index("<body>"))

    def test_the_labels_come_from_the_catalogue_so_they_can_be_translated(self):
        pseudo_ui = {
            k: ({c: fixture.pseudo(x) for c, x in v.items()} if isinstance(v, dict) else fixture.pseudo(v)) for k, v in EN.items()
        }
        page = self.built(self.project(ui_extra={code: pseudo_ui for code in fixture.LANGS}))["settings.html"]
        for key in (
            "appearance",
            "appearance_system",
            "appearance_light",
            "appearance_dark",
            "colours",
            "palette_default",
            "palette_high_contrast",
            "palette_red_green",
            "palette_red_green_safe",
            "palette_blue_yellow_safe",
        ):
            self.assertIn(fixture.pseudo(EN[key]), page, key)

    def test_an_edition_can_offer_a_subset(self):
        proj = self.project()
        self.edit_edition(proj, palettes=["default", "high-contrast"])
        out = self.build_out(proj, "subset")
        page = (out / "settings.html").read_text(encoding="utf-8")
        css = (out / "palettes.css").read_text(encoding="utf-8")
        self.assertIn('value="high-contrast" data-pref="palette"', page)
        self.assertNotIn("red-green-safe", page + css)
        self.assertIn('data-palette="high-contrast"', css)

    def test_one_palette_means_no_colour_choice_but_light_and_dark_remain(self):
        proj = self.project()
        self.edit_edition(proj, palettes=["default"])
        page = self.built(proj)["settings.html"]
        self.assertNotIn('data-pref="palette"', page)
        self.assertIn('data-pref="appearance"', page)

    def test_the_settings_page_has_an_accessibility_level_that_lists_the_schemes_of_that_level(self):
        page = self.built(self.project())["settings.html"]
        for level in ("standard", "safe", "high"):
            self.assertIn(f'name="access" value="{level}" data-pref="access"', page)
        self.assertIn('name="access" value="standard" data-pref="access" checked', page)
        for pid, level in (
            ("default", "standard"),
            ("red-green", "standard"),
            ("red-green-safe", "safe"),
            ("blue-yellow-safe", "safe"),
            ("high-contrast", "high"),
        ):
            at = page.index(f'name="palette" value="{pid}"')
            self.assertIn(f'data-tier="{level}"', page[page.rindex("<label", 0, at) : at], pid)

    def test_each_scheme_is_drawn_as_a_small_picture_of_itself(self):
        page = self.built(self.project())["settings.html"]
        self.assertEqual(page.count('<span class="preview" data-palette='), 5)
        self.assertIn('<span class="preview" data-palette="high-contrast" aria-hidden="true">', page)

    def test_the_level_is_worked_out_from_the_palette_file(self):
        self.assertEqual(palettes.access_level({"level": "AAA"}), "high")
        self.assertEqual(palettes.access_level({"level": "AAA", "colour_vision": ["deutan"]}), "high")
        self.assertEqual(palettes.access_level({"colour_vision": ["tritan"]}), "safe")
        self.assertEqual(palettes.access_level({"level": "AA", "colour_vision": []}), "standard")
        self.assertEqual(palettes.access_level({}), "standard")

    def test_an_edition_whose_palettes_share_one_level_has_no_accessibility_choice_but_still_has_the_colours(self):
        proj = self.project()
        self.edit_edition(proj, palettes=["default", "red-green"])
        page = self.built(proj)["settings.html"]
        self.assertNotIn('data-pref="access"', page)
        self.assertEqual(page.count('data-pref="palette"'), 2)

    def test_the_settings_page_has_a_language_toggle_and_shows_each_text_in_both_languages(self):
        page = self.built(self.project())["settings.html"]
        self.assertIn(
            '<input type="radio" class="lang-radio" name="settings-lang" id="settings-lang-qaa" value="qaa" checked>', page
        )
        self.assertIn('id="settings-lang-qab" value="qab">', page)
        self.assertIn('<div class="lang-bar" role="group" aria-label="Language">', page)
        h1 = page[page.index("<h1>") : page.index("</h1>")]
        self.assertIn(
            '<span class="t" data-n="1"', h1
        )  # the fixture has no Alphish words for settings, so the English fallback is marked
        self.assertIn('<span class="t" data-n="2"', h1)
        self.assertIn("<script", page)  # the page's own scripts are untouched; the toggle itself needs none
        bar = page[page.index('<div class="lang-bar"') :]
        self.assertNotIn("onclick", bar)

    def test_bad_palette_lists_are_rejected(self):
        for bad in (["high-contrast"], ["default", "default"], ["default", "no-such-palette"], "default"):
            proj = self.project()
            self.edit_edition(proj, palettes=bad)
            with self.assertRaises(ContentError, msg=bad):
                content.validate(content.read(proj))

    def test_a_project_can_add_a_palette_and_name_it_in_the_interface_language(self):
        proj = self.project()
        light = {**default_palette()["light"], "bg": "oklch(0.95 0.03 85)"}
        self.add_palette(proj, "sepia", names={"qaa": "Sepia paper"}, light=light)
        out = self.build_out(proj, "added")
        page = (out / "settings.html").read_text(encoding="utf-8")
        self.assertIn('name="palette" value="sepia" data-pref="palette" data-tier="standard">', page)
        self.assertIn('<span class="t" data-n="1">Sepia paper</span>', page)
        self.assertIn(':root[data-palette="sepia"]{--bg:#', (out / "palettes.css").read_text(encoding="utf-8"))

    def test_a_project_palette_with_no_name_for_the_interface_falls_back_to_english_and_then_the_id(self):
        proj = self.project()
        self.add_palette(proj, "plain")
        self.add_palette(proj, "other", names={"en": "Other colours"})
        page = self.built(proj)["settings.html"]
        self.assertIn('<span class="t" data-n="1">plain</span>', page)
        self.assertIn('<span class="t" data-n="1" lang="en">Other colours</span>', page)

    def test_a_palette_named_only_in_another_language_is_marked_with_that_language(self):
        proj = self.project()
        self.add_palette(proj, "foreign", names={"qab": "Betish colours"})
        page = self.built(proj)["settings.html"]
        self.assertIn('<span class="t" data-n="1" lang="qab">Betish colours</span>', page)

    def test_a_project_can_recolour_the_default(self):
        proj = self.project()
        self.add_palette(proj, "default", light={**default_palette()["light"], "accent": "#005a9c"})
        out = self.build_out(proj, "recoloured")
        css = (out / "palettes.css").read_text(encoding="utf-8")
        self.assertIn("--accent:#005a9c", css.splitlines()[1])
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["theme_color"], "#005a9c")  # the installed app wears the project's colours
        self.assertEqual(manifest["background_color"], default_palette_hex("light", "bg"))
        self.assertIn('<meta name="theme-color" content="#005a9c">', (out / "p1.html").read_text(encoding="utf-8"))

    def test_a_project_palette_that_breaks_its_promise_fails_the_build(self):
        proj = self.project()
        self.add_palette(proj, "faint", light={**default_palette()["light"], "ink": "oklch(0.8 0.01 230)"})
        with self.assertRaises(ContentError) as ctx:
            quiet_build(self.tmp / "faint-out", project_dir=proj)
        self.assertIn("palettes/faint.json", str(ctx.exception))
        self.assertIn("ink on", str(ctx.exception))

    def test_a_project_palette_may_promise_colour_vision_and_is_held_to_it(self):
        proj = self.project()
        self.add_palette(proj, "claims", colour_vision=["deutan"])  # the default's red accent is not safe for deutan
        with self.assertRaises(ContentError) as ctx:
            quiet_build(self.tmp / "claims-out", project_dir=proj)
        self.assertIn("deutan", str(ctx.exception))

    def test_palette_names_are_checked_like_other_text(self):
        proj = self.project()
        self.add_palette(proj, "accented", names={"qaa": "é"})  # a separate accent, not normal form C
        with self.assertRaises(ContentError):
            content.validate(content.read(proj))

    def test_the_service_worker_precaches_the_palettes(self):
        out = self.build_out(self.project(), "sw-palettes")
        self.assertIn('"palettes.css"', (out / "sw.js").read_text(encoding="utf-8"))


def default_palette():
    return json.loads((ENGINE / "palettes" / "default.json").read_text(encoding="utf-8"))


def default_palette_hex(variant, role):
    from phrasebook import colour, palettes

    return colour.rgb_to_hex(palettes.resolve(default_palette())[variant][role])


# ---------------------------------------------------------------- command line


class CommandLineTests(Scratch):
    def run_main(self, *argv, projects_dir=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                cli.main(list(argv), projects_dir=projects_dir)
                code = 0
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue()

    def test_a_named_project_builds(self):
        proj = self.project()
        out = self.tmp / "cli-out"
        code, stdout, _ = self.run_main(str(out), "--project", str(proj))
        self.assertEqual(code, 0)
        self.assertIn("wrote 8 pages", stdout)
        self.assertIn("coverage: qaa", stdout)
        self.assertTrue((out / "index.html").is_file())

    def test_strict_fails_on_drafts_with_a_clear_message(self):
        proj = self.project()
        code, _, _ = self.run_main(str(self.tmp / "strict-out"), "--project", str(proj), "--strict")
        self.assertIn("unreviewed draft sources", str(code))

    def test_the_only_project_is_found_without_being_named(self):
        root = self.tmp / "only"
        fixture.make_project(root / "one")
        self.assertEqual(cli.find_project(root).name, "one")

    def test_several_or_no_projects_must_be_chosen(self):
        root = self.tmp / "many"
        fixture.make_project(root / "one")
        fixture.make_project(root / "two")
        with self.assertRaises(ContentError) as ctx:
            cli.find_project(root)
        self.assertIn("--project", str(ctx.exception))
        with self.assertRaises(ContentError):
            cli.find_project(self.tmp / "nowhere")

    def test_a_project_folder_given_by_the_caller_is_built_without_naming_it(self):
        root = self.tmp / "given"
        fixture.make_project(root / "one")
        out = self.tmp / "given-out"
        code, stdout, _ = self.run_main(str(out), projects_dir=root)
        self.assertEqual(code, 0)
        self.assertIn("coverage: ", stdout)
        self.assertTrue((out / "index.html").is_file())

    def test_the_project_folder_defaults_to_content_in_the_current_directory(self):
        root = self.tmp / "cwd"
        fixture.make_project(root / "content" / "one")
        here = pathlib.Path.cwd()
        os.chdir(root)
        try:
            self.assertEqual(cli.find_project().name, "one")
        finally:
            os.chdir(here)


if __name__ == "__main__":
    unittest.main()
