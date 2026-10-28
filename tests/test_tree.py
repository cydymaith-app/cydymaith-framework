"""Tests of icons, the navigation tree (tree.json), the panel markup and the how-to page.

Framework behaviour runs on the neutral fixture; the project's own icons and tree are checked at the end.
The panel script's moves are tested in nav.test.js. Run from the repo root: python3 -m unittest discover -s tests -v
"""

import html
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
from phrasebook import content, icons, tree  # noqa: E402
from phrasebook.help import Book  # noqa: E402
from phrasebook.errors import ContentError  # noqa: E402
from test_framework import ENGINE, Scratch, quiet_build  # noqa: E402

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="x">{body}</svg>'
)
GOOD = SVG.format(body='<path d="M4 4l16 16" /><circle cx="12" cy="12" r="3" />')


class Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k == "id":
                self.ids.append(v)


def ids_of(html):
    parser = Ids()
    parser.feed(html)
    return parser.ids


def add_icon(proj, name, svg=GOOD):
    path = proj / "icons" / f"{name}.svg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def name_icons(proj, group=None, page=None):
    if group:
        fixture.edit(proj / "structure.json", lambda d: d["groups"][0].update(icon=group))
    if page:
        fixture.edit(proj / "pages" / "p1.json", lambda d: d.update(icon=page))


class IconParsingTests(unittest.TestCase):
    def test_a_good_icon_is_inlined_as_one_line_that_follows_the_text_colour(self):
        markup = icons.markup(GOOD)
        self.assertTrue(markup.startswith('<svg class="icon" aria-hidden="true" focusable="false"'))
        self.assertIn('stroke="currentColor"', markup)
        self.assertIn('viewBox="0 0 24 24"', markup)
        self.assertNotIn("\n", markup)

    def test_what_the_page_does_not_need_is_dropped(self):
        markup = icons.markup(GOOD)
        for gone in ("xmlns", " width=", " height=", "carbon"):
            self.assertNotIn(gone, markup)

    def test_a_comment_in_the_file_is_dropped(self):
        self.assertNotIn("licence", icons.markup("<!-- @license carbon Apache-2.0 -->" + GOOD))

    def test_unsafe_or_odd_svgs_are_rejected(self):
        bad = {
            "a script": SVG.format(body="<script>alert(1)</script>"),
            "an event handler": SVG.format(body='<path d="M0 0" onclick="x()" />'),
            "a url reference": SVG.format(body='<path d="M0 0" fill="url(#a)" />'),
            "a data uri": SVG.format(body='<path d="M0 0" fill="data:x" />'),
            "an external link": SVG.format(body='<path d="M0 0" href="https://example.com/x" />'),
            "a style element": SVG.format(body="<style>*{}</style>"),
            "a foreignObject": SVG.format(body="<foreignObject><div/></foreignObject>"),
            "an image": SVG.format(body='<image href="x.png"/>'),
            "text inside a shape": SVG.format(body='<path d="M0 0">hi</path>'),
            "an entity": SVG.format(body='<path d="M0 0" fill="&amp;"/>'),
            "a doctype": '<!DOCTYPE svg [<!ENTITY x "y">]>' + GOOD,
            "no viewBox": GOOD.replace('viewBox="0 0 24 24"', ""),
            "a root that is not svg": '<html xmlns="http://www.w3.org/2000/svg"></html>',
            "a script attribute on the root": GOOD.replace("<svg ", '<svg onload="x()" ', 1),
            "not xml": "<svg",
            "an element in another namespace": SVG.format(body='<a xmlns="http://www.w3.org/1999/xhtml">x</a>'),
        }
        for why, text in bad.items():
            with self.assertRaises(ContentError, msg=why):
                icons.markup(text)

    def test_the_file_name_must_be_a_safe_identifier(self):
        for name in ("Upper", "has space", "-lead", "9lives"):
            with self.assertRaises(ContentError, msg=name):
                icons.validate({name: GOOD})
        icons.validate({"cloud-rain": GOOD})

    def test_the_framework_ships_only_its_interface_icons_with_their_licence(self):
        found = sorted(p for p in ENGINE.rglob("*.svg"))
        self.assertEqual(
            [f.relative_to(ENGINE).as_posix() for f in found],
            [
                "ui-icons/arrow--left.svg",
                "ui-icons/asleep.svg",
                "ui-icons/backspace.svg",
                "ui-icons/close.svg",
                "ui-icons/headphones.svg",
                "ui-icons/help.svg",
                "ui-icons/information.svg",
                "ui-icons/light.svg",
                "ui-icons/screen.svg",
                "ui-icons/search.svg",
                "ui-icons/settings.svg",
                "ui-icons/tools.svg",
            ],
        )
        self.assertIn("Apache", (ENGINE / "ui-icons" / "LICENSE").read_text(encoding="utf-8"))
        assets = (ROOT / "docs" / "ASSETS.md").read_text(encoding="utf-8")
        for f in found:
            self.assertIn(f"`{f.stem}`", assets)
            icons.markup(f.read_text(encoding="utf-8"))


class IconSiteTests(Scratch):
    def test_an_icon_on_a_group_and_a_page_is_inlined_on_their_tiles_with_the_labels_kept(self):
        proj = self.project()
        add_icon(proj, "weather")
        add_icon(proj, "doc")
        name_icons(proj, group="weather", page="doc")
        pages = self.built(proj)
        self.assertIn(
            '<a class="tile-link" href="group-g1.html"><span class="tile"><svg class="icon" aria-hidden="true"',
            pages["index.html"],
        )
        self.assertIn(
            '<a class="tile-link" href="p1.html"><span class="tile"><svg class="icon" aria-hidden="true"', pages["group-g1.html"]
        )
        self.assertIn(
            '<span class="tile-name"><span class="l1">qaa group</span><span class="l2" lang="qab">qab group</span></span>',
            pages["index.html"],
        )
        self.assertIn('<span class="l1">qaa page</span><span class="l2" lang="qab">qab page</span>', pages["group-g1.html"])

    def test_a_tile_with_no_icon_holds_its_name_and_keeps_the_names_beneath(self):
        pages = self.built(self.project())
        self.assertIn(
            '<span class="tile"><span class="tile-text" aria-hidden="true">qaa group</span></span>', pages["index.html"]
        )
        self.assertIn('<span class="l1">qaa group</span>', pages["index.html"])

    def test_the_only_icons_without_a_project_icon_are_the_frames_own(self):
        pages = self.built(self.project())
        for name, page in pages.items():
            frame = re.sub(
                r'<a class="help-icon".*?</a>|<button type="button" class="help-close".*?</button>', "", page, flags=re.S
            )  # the help icons and the sheet's x, counted apart
            limit = (
                11 if name == "settings.html" else 8
            )  # search, help, back, edit order, about and the gear, and the figure, and the search card's x and delete symbol; the settings page adds three modes
            self.assertLessEqual(frame.count("<svg"), limit, name)
        self.assertEqual(
            re.sub(
                r'<a class="help-icon".*?</a>|<button type="button" class="help-close".*?</button>',
                "",
                pages["index.html"],
                flags=re.S,
            ).count("<svg"),
            7,
            "search, help, edit order, about and the gear in the rail, and the search card's x and delete symbol",
        )

    def test_a_named_icon_must_have_a_file(self):
        proj = self.project()
        name_icons(proj, page="ghost")
        with self.assertRaises(ContentError) as ctx:
            content.validate(content.read(proj))
        self.assertIn("icons/ghost.svg", str(ctx.exception))

    def test_a_group_icon_must_have_a_file_too(self):
        proj = self.project()
        name_icons(proj, group="ghost")
        with self.assertRaises(ContentError) as ctx:
            content.validate(content.read(proj))
        self.assertIn("structure.json", str(ctx.exception))

    def test_the_icon_must_be_a_name_not_something_else(self):
        for bad in (7, ["a"], {"a": 1}, True):
            proj = self.project()
            fixture.edit(proj / "pages" / "p1.json", lambda d, b=bad: d.update(icon=b))
            with self.assertRaises(ContentError, msg=bad):
                content.validate(content.read(proj))

    def test_an_unsafe_icon_file_fails_the_build_naming_the_file(self):
        proj = self.project()
        add_icon(proj, "evil", SVG.format(body='<path d="M0 0" onclick="x()" />'))
        with self.assertRaises(ContentError) as ctx:
            quiet_build(self.tmp / "evil-out", project_dir=proj)
        self.assertIn("icons/evil.svg", str(ctx.exception))

    def test_an_icon_nobody_names_is_allowed_and_not_inlined(self):
        proj = self.project()
        add_icon(proj, "spare", SVG.format(body='<path d="M1 2l3 4" />'))
        self.assertNotIn("M1 2l3 4", "".join(self.built(proj).values()))

    def test_icons_are_inlined_so_no_request_is_made(self):
        proj = self.project()
        add_icon(proj, "doc")
        name_icons(proj, page="doc")
        out = self.tmp / "inline-out"
        quiet_build(out, project_dir=proj)
        self.assertFalse(list(out.rglob("*.svg")), "the svg files are not copied; the markup is in the pages")
        for page in out.glob("*.html"):
            self.assertNotIn("<img", page.read_text(encoding="utf-8"), page.name)


class TreeTests(Scratch):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.project()
        add_icon(cls.proj, "weather")
        add_icon(cls.proj, "doc")
        name_icons(cls.proj, group="weather", page="doc")
        cls.out = cls.tmp / "tree-out"
        quiet_build(cls.out, project_dir=cls.proj)
        cls.doc = json.loads((cls.out / "tree.json").read_text(encoding="utf-8"))
        cls.pages = {f.name: f.read_text(encoding="utf-8") for f in cls.out.glob("*.html")}

    def test_the_tree_is_written_and_precached(self):
        self.assertEqual(self.doc["version"], 1)
        sw = (self.out / "sw.js").read_text(encoding="utf-8")
        self.assertIn('"tree.json"', sw)
        self.assertIn('"nav.js"', sw)
        self.assertIn('"search.js"', sw)
        self.assertIn('"dictionary.json"', sw)

    def test_it_is_nested_with_a_level_at_each_step(self):
        group = self.doc["nodes"][0]
        self.assertEqual((group["id"], group["level"]), ("1", "group"))
        page = group["children"][0]
        self.assertEqual((page["id"], page["level"]), ("1.1", "page"))
        section = page["children"][0]
        self.assertEqual((section["id"], section["level"]), ("1.1.1", "section"))
        word = section["children"][0]
        self.assertEqual((word["id"], word["level"]), ("1.1.1.1", "word"))

    def test_every_id_is_unique_and_a_node_numbers_itself_inside_its_parent(self):
        seen = []

        def walk(nodes, prefix):
            for i, node in enumerate(nodes, 1):
                self.assertEqual(node["id"], f"{prefix}{i}")
                seen.append(node["id"])
                walk(node["children"], node["id"] + ".")

        walk(self.doc["nodes"], "")
        self.assertEqual(len(seen), len(set(seen)))

    def test_every_address_leads_to_a_built_page_and_a_real_element_on_it(self):
        def walk(nodes):
            for node in nodes:
                if node["href"]:
                    page, _, anchor = node["href"].partition("#")
                    self.assertIn(page, self.pages, node["href"])
                    if anchor:
                        self.assertIn(anchor, ids_of(self.pages[page]), node["href"])
                walk(node["children"])

        walk(self.doc["nodes"])

    def test_groups_have_no_page_of_their_own_in_the_tree_and_the_rest_do(self):
        def walk(nodes):
            for node in nodes:
                self.assertEqual(node["href"] is None, node["level"] == "group", node["id"])
                walk(node["children"])

        walk(self.doc["nodes"])

    def test_labels_come_in_both_languages_of_the_pair_with_their_language_and_direction(self):
        word = self.doc["nodes"][0]["children"][0]["children"][0]["children"][0]
        self.assertEqual(word["first"]["lang"], "qaa")
        self.assertEqual(word["second"]["lang"], "qab")
        self.assertTrue(word["first"]["text"] and word["second"]["text"])
        self.assertEqual({word["first"]["dir"], word["second"]["dir"]}, {"ltr"})

    def test_a_right_to_left_language_is_marked_as_such(self):
        raw = content.read(self.proj)
        site = phrasebook.Site(raw, content.pick_edition(raw)[1], pair=("qaa", "qac"))
        word = tree.build(site)[0]["children"][0]["children"][0]["children"][0]
        self.assertEqual(word["second"]["dir"], "rtl")

    def test_swapping_the_pair_swaps_the_labels(self):
        raw = content.read(self.proj)
        ed = content.pick_edition(raw)[1]
        a = tree.build(phrasebook.Site(raw, ed, pair=("qaa", "qab")))[0]
        b = tree.build(phrasebook.Site(raw, ed, pair=("qab", "qaa")))[0]
        self.assertEqual(a["first"]["text"], b["second"]["text"])
        self.assertEqual(a["second"]["text"], b["first"]["text"])

    def test_icons_are_named_on_groups_and_pages_only_and_their_markup_is_included_once(self):
        group = self.doc["nodes"][0]
        self.assertEqual(group["icon"], "weather")
        self.assertEqual(group["children"][0]["icon"], "doc")
        self.assertIsNone(group["children"][0]["children"][0]["icon"])
        self.assertEqual(set(self.doc["icons"]), {"weather", "doc"})
        for markup in self.doc["icons"].values():
            self.assertTrue(markup.startswith('<svg class="icon" aria-hidden="true"'))

    def test_it_carries_no_interface_wording_because_nothing_on_screen_reads_it(self):
        self.assertNotIn("messages", self.doc)

    def test_the_interface_language_and_direction_are_recorded(self):
        self.assertEqual((self.doc["lang"], self.doc["dir"]), ("qaa", "ltr"))

    def test_held_back_sections_are_left_out_of_the_release_tree_and_kept_in_development(self):
        proj = self.project()
        fixture.edit(proj / "pages" / "p1.json", lambda d: d["sections"][1].update(status="development"))
        release, development = self.tmp / "rel", self.tmp / "dev"
        quiet_build(release, project_dir=proj)
        quiet_build(development, project_dir=proj, channel="development")

        def sections(out):
            doc = json.loads((out / "tree.json").read_text(encoding="utf-8"))
            return [
                s["href"] for g in doc["nodes"] for p in g["children"] for s in p["children"] if s["href"].startswith("p1.html#")
            ]

        self.assertNotIn("p1.html#s2", sections(release))
        self.assertIn("p1.html#s2", sections(development))

    def test_every_word_of_a_section_gets_an_address_on_its_page(self):
        page = self.pages["p1.html"]
        for node in self.doc["nodes"][0]["children"][0]["children"]:
            for word in node["children"]:
                self.assertIn(word["href"].partition("#")[2], ids_of(page))


class FrameTests(Scratch):
    """The frame around every page: a rail, a top bar with Back and the trail, then tiles or a topic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.project()
        add_icon(cls.proj, "weather")
        name_icons(cls.proj, group="weather")
        cls.out = cls.tmp / "frame-out"
        quiet_build(cls.out, project_dir=cls.proj)
        cls.pages = {f.name: f.read_text(encoding="utf-8") for f in cls.out.glob("*.html")}

    def test_every_page_loads_the_key_script_without_blocking(self):
        for name, page in self.pages.items():
            self.assertIn('<script src="nav.js" defer></script>', page, name)
        self.assertTrue((self.out / "nav.js").is_file())

    def test_the_old_sidebar_menu_and_panel_are_gone_from_every_page(self):
        for name, page in self.pages.items():
            for gone in (
                'class="tree"',
                'class="side"',
                "nav-toggle",
                "menu-btn",
                "data-explore",
                "<dialog",
                "data-panel",
                "panel-",
            ):
                self.assertNotIn(gone, page, f"{name}: {gone}")

    def test_every_page_has_the_rail_with_settings_and_the_title_in_the_top_bar(self):
        for name, page in self.pages.items():
            self.assertIn('<nav class="rail"', page, name)
            self.assertIn('href="settings.html"', page, name)
            self.assertIn('<header class="topbar">', page, name)
            self.assertIn('<a class="brand" href="index.html">', page, name)

    def test_the_gear_is_marked_on_the_settings_page_only(self):
        for name, page in self.pages.items():
            self.assertEqual('aria-label="Settings" aria-current="page">' in page, name == "settings.html", name)

    def test_the_home_page_is_tiles_with_no_back_no_trail_and_no_pager(self):
        home = self.pages["index.html"]
        self.assertNotIn("data-back", home)
        self.assertNotIn('class="trail"', home)
        self.assertNotIn('class="pager"', home)
        self.assertIn('<ul class="tiles" data-tiles data-order="index" aria-label=', home)
        self.assertEqual(home.count('class="tile-link"'), 1)
        self.assertIn('<li data-tile="g1" data-level="1"><a class="tile-link" href="group-g1.html">', home)

    def test_a_group_page_has_back_to_home_and_tiles_for_its_topics_without_counts(self):
        page = self.pages["group-g1.html"]
        self.assertIn('<a class="rail-link back" href="index.html" data-back aria-label="Back"', page)
        self.assertEqual(page.count('class="tile-link"'), 2)
        for slug in ("p1", "points"):
            self.assertIn(f'href="{slug}.html"', page)
        self.assertNotIn("tile-count", page)
        self.assertIsNone(re.search(r"\d+ entr", page), "the tiles do not say how many entries a topic has")
        self.assertNotIn('class="pager"', page)

    def test_a_topic_page_has_back_to_its_group_the_trail_and_the_pager(self):
        page = self.pages["p1.html"]
        self.assertIn('<a class="rail-link back" href="group-g1.html" data-back aria-label="Back"', page)
        trail = re.search(r'<ol class="trail">(.*?)</ol>', page).group(1)
        self.assertEqual(
            re.findall(r'<li>(?:<a href="([^"]+)"|<span aria-current="page")', trail), ["index.html", "group-g1.html", ""]
        )
        self.assertEqual(trail.count('aria-current="page"'), 1)
        self.assertIn('class="pager"', page)

    def test_the_generated_pages_go_back_to_the_right_place(self):
        self.assertIn('<a class="rail-link back" href="index.html" data-back aria-label="Back"', self.pages["settings.html"])
        self.assertIn('<a class="rail-link back" href="about.html" data-back aria-label="Back"', self.pages["how-to.html"])
        self.assertIn('<a class="rail-link back" href="about.html" data-back aria-label="Back"', self.pages["sources.html"])

    def test_back_and_the_trail_are_named_by_messages(self):
        page = self.pages["p1.html"]
        self.assertIn('data-back aria-label="Back" title="Back">', page)
        self.assertIn('<nav aria-label="You are here"><ol class="trail">', page)

    def test_the_rail_has_search_then_back_then_settings_and_the_title_bar_has_neither_button(self):
        page = self.pages["p1.html"]
        rail = page[page.index('<nav class="rail"') : page.index("</nav>", page.index('<nav class="rail"'))]
        self.assertLess(rail.index('class="rail-link search"'), rail.index('class="rail-link back"'))
        self.assertLess(rail.index('class="rail-link back"'), rail.index('href="settings.html"'))
        bar = page[page.index('<header class="topbar">') : page.index("</header>")]
        self.assertNotIn("<button", bar)
        self.assertNotIn("data-back", bar)

    def test_the_search_button_is_hidden_until_the_script_that_runs_it_has_loaded(self):
        for name, page in self.pages.items():
            self.assertIn(
                '<button type="button" class="rail-link search" id="search-button" hidden aria-label="Search" '
                'title="Search" aria-expanded="false" aria-controls="search-card">',
                page,
                name,
            )
            self.assertNotIn(
                " disabled",
                page[page.index('id="search-button"') : page.index("</button>", page.index('id="search-button"'))],
                name,
            )

    def test_every_page_holds_the_shut_search_card_with_its_messages_and_the_pair(self):
        for name, page in self.pages.items():
            self.assertIn('<div class="search-layer" hidden>', page, name)
            card = page[page.index('<div class="search-card"') :]
            self.assertIn('id="search-card" role="search" aria-label="Search" inert', card, name)
            self.assertIn('data-dictionary="dictionary.json"', card, name)
            self.assertIn('data-pair="[[&quot;qaa&quot;, &quot;ltr&quot;], [&quot;qab&quot;, &quot;ltr&quot;]]"', card, name)
            self.assertIn('data-hint="Type a word or phrase in Alphish or Betish."', card, name)
            self.assertIn('<input id="search-input" type="search" placeholder="Search words and phrases"', card, name)
            self.assertIn('id="search-results"', card, name)
            self.assertIn('data-other="Other results"', card, name)
            self.assertIn('id="search-pages"', card, name)

    def test_the_search_card_actions_are_symbols_with_names_for_a_screen_reader(self):
        for name, page in self.pages.items():
            card = page[page.index('<div class="search-card"') : page.index('<p class="search-status"')]
            clear = re.search(
                r'<button type="button" class="search-clear" hidden aria-label="Clear" title="Clear">(.*?)</button>', card, re.S
            )
            close = re.search(
                r'<button type="button" class="search-close" aria-label="Close" title="Close">(.*?)</button>', card, re.S
            )
            self.assertTrue(clear and "<svg" in clear.group(1), f"{name}: a delete symbol clears the field")
            self.assertTrue(close and "<svg" in close.group(1), f"{name}: an x closes the card")
            for button in (clear, close):
                self.assertNotRegex(
                    re.sub(r"<svg.*?</svg>", "", button.group(1), flags=re.S).strip(), r"\w", f"{name}: no words on the button"
                )
            self.assertLess(card.index('class="search-field"'), card.index('class="search-clear"'), name)
            self.assertNotIn("<label", card[card.index('class="search-clear"') :], name)

    def test_the_card_names_the_pages_being_browsed_so_search_can_list_them_first(self):
        def scope(name):
            card = self.pages[name][self.pages[name].index('<div class="search-card"') :]
            return json.loads(html.unescape(re.search(r'data-scope="([^"]*)"', card).group(1)))

        self.assertEqual(scope("p1.html"), ["p1.html"])
        self.assertEqual(scope("group-g1.html"), ["p1.html", "points.html"])
        for name in ("index.html", "settings.html", "sources.html"):
            self.assertEqual(scope(name), [], name)

    def test_the_card_comes_after_the_page_and_search_js_loads_after_the_page_is_parsed(self):
        page = self.pages["p1.html"]
        self.assertLess(page.index("</main>"), page.index('<div class="search-layer"'))
        self.assertIn('<script src="search.js" defer></script>', page)
        self.assertTrue((self.out / "search.js").is_file())

    def test_the_home_page_has_search_and_settings_but_no_back(self):
        rail = self.pages["index.html"][self.pages["index.html"].index('<nav class="rail"') :]
        self.assertIn('class="rail-link search"', rail)
        self.assertNotIn('class="rail-link back"', rail)

    def test_the_title_bar_comes_before_the_rail_and_spans_the_page_in_the_stylesheet(self):
        page = self.pages["index.html"]
        self.assertLess(page.index('<header class="topbar">'), page.index('<nav class="rail"'))
        css = (ENGINE / "assets" / "style.css").read_text(encoding="utf-8")
        self.assertIn("grid-column:1/-1", css[css.index(".topbar{") : css.index(".rail{")])

    def test_tiles_name_their_topic_in_both_languages_and_the_icon_is_decorative(self):
        page = self.pages["index.html"]
        self.assertIn('<span class="l1">qaa group</span><span class="l2" lang="qab">qab group</span>', page)
        self.assertIn('aria-hidden="true"', page)

    def test_the_interface_icons_are_inlined_not_fetched(self):
        for name, page in self.pages.items():
            self.assertNotIn("<img", page, name)
        self.assertFalse(list(self.out.rglob("*.svg")))

    def test_the_about_page_links_how_to_and_sources_and_settings_does_not(self):
        about, settings = self.pages["about.html"], self.pages["settings.html"]
        self.assertIn('<a href="how-to.html">', about)
        self.assertIn('<a href="sources.html">', about)
        self.assertNotIn('<a href="how-to.html">', settings)
        self.assertNotIn('<a href="sources.html">', settings)

    def test_how_to_and_sources_sit_under_about_in_the_trail_when_there_is_an_about_page(self):
        for name in ("how-to.html", "sources.html"):
            trail = self.pages[name].split('class="trail"')[1].split("</ol>")[0]
            self.assertEqual(re.findall(r'<li><a href="([^"]+)"', trail), ["index.html", "about.html"], name)

    def test_every_page_but_home_names_its_parent_and_home_names_none(self):
        self.assertNotIn("data-parent", self.pages["index.html"].split("</head>")[0].split("<head>")[0])
        expected = {
            "group-g1.html": "index.html",
            "p1.html": "group-g1.html",
            "points.html": "group-g1.html",
            "settings.html": "index.html",
            "how-to.html": "about.html",
            "sources.html": "about.html",
        }
        for name, parent in expected.items():
            self.assertIn(f' data-parent="{parent}">', self.pages[name].split("<head>")[0], name)

    def test_the_parent_is_where_the_back_button_goes(self):
        for name, page in self.pages.items():
            back = re.search(r'class="rail-link back" href="([^"]+)"', page)
            parent = re.search(r' data-parent="([^"]+)"', page)
            self.assertEqual(back.group(1) if back else None, parent.group(1) if parent else None, name)

    def test_the_slide_in_is_decided_in_the_head_before_the_stylesheet_and_before_the_page(self):
        page = self.pages["p1.html"]
        script = 'd.documentElement.classList.add(m[1]==="back"?"slide-back":"slide-in")'
        self.assertIn(script, page)
        self.assertLess(page.index(script), page.index('<link rel="stylesheet" href="palettes.css">'))
        self.assertLess(page.index(script), page.index("<body>"))
        self.assertIn(script, self.pages["index.html"], "Back arrives on the home page, which slides in from the start")
        self.assertNotIn('class="slide-in', self.pages["index.html"])

    def test_the_head_script_reads_the_way_the_page_goes_from_the_address_and_never_the_referrer(self):
        page = self.pages["p1.html"]
        self.assertIn("/^#slide=(forward|back|none)((?:;(?:from|at)=[A-Za-z0-9._-]+)*)$/.exec(w.location.hash)", page)
        self.assertIn("w.history.replaceState(", page)
        self.assertIn('w.location.pathname+w.location.search+(a?"#"+a[1]:"")', page)
        self.assertNotIn("referrer", page.split("<body>")[0])

    def test_every_page_says_which_way_it_moves_so_the_browser_can_slide_pages_side_by_side(self):
        for name, page in self.pages.items():
            head = page.split("<body>")[0]
            self.assertIn('addEventListener("pagereveal"', head, name)
            self.assertIn('"data-slide","forward"', head, name)
            self.assertIn('"data-slide","back"', head, name)
            self.assertLess(head.index("pagereveal"), head.index('<link rel="stylesheet" href="palettes.css">'), name)

    def test_the_fallback_slide_in_is_left_off_where_the_browser_slides_pages_itself(self):
        self.assertIn("else if(!w.PageRevealEvent)d.documentElement", self.pages["p1.html"])

    def test_a_page_that_arrives_where_the_move_ended_tells_the_browsers_own_move_to_stand_down(self):
        for name, page in self.pages.items():
            head = page.split("<body>")[0]
            self.assertIn('d.documentElement.setAttribute("data-slide","none")', head, name)
            self.assertIn('r.getAttribute("data-slide")==="none"||!u||', head, name)

    def test_the_pager_still_links_topics_in_order(self):
        self.assertIn('href="points.html"', self.pages["p1.html"][self.pages["p1.html"].index('class="pager"') :])


class MobileFirstTests(unittest.TestCase):
    """The site is a companion held in one hand while watching, so the phone is the base design."""

    CSS = (ENGINE / "assets" / "style.css").read_text(encoding="utf-8")

    def test_the_top_and_bottom_insets_apply_only_to_the_installed_app(self):
        """A browser tab keeps its own bars clear of the page; some browsers still report the status bar as an inset on top of that."""
        self.assertEqual(
            self.CSS.count("env(safe-area-inset-top"), 1, "one use of the top inset, and it is the one that is gated"
        )
        self.assertEqual(self.CSS.count("env(safe-area-inset-bottom"), 1)
        gate = next(line for line in self.CSS.splitlines() if "display-mode:standalone" in line)
        self.assertIn("(display-mode:fullscreen)", gate)
        self.assertIn("--inset-top:env(safe-area-inset-top,0px)", gate)
        self.assertIn("--inset-bottom:env(safe-area-inset-bottom,0px)", gate)
        self.assertIn("--inset-top:0px", self.CSS, "with no gate matched there is no inset")

    def test_the_stylesheet_widens_with_min_width_and_never_narrows_with_max_width(self):
        self.assertIn("@media (min-width:600px)", self.CSS)
        self.assertIn("@media (min-width:960px)", self.CSS)
        self.assertIsNone(re.search(r"@media \(max-width", self.CSS), "no desktop-first media query")

    def test_the_base_layout_is_two_tiles_across_and_widens_on_bigger_screens(self):
        base = self.CSS[: self.CSS.index("/* wider screens */")]
        self.assertIn("grid-template-columns:repeat(2,minmax(0,1fr))", base)
        wider = self.CSS[self.CSS.index("/* wider screens */") :]
        self.assertIn("repeat(3,", wider)
        self.assertIn("repeat(4,", wider)

    def test_touch_targets_are_at_least_44_pixels(self):
        for rule in (".rail-link{",):
            self.assertIn("2.75rem", self.CSS[self.CSS.index(rule) : self.CSS.index("}", self.CSS.index(rule))], rule)

    def test_a_page_reached_from_its_parent_slides_in_without_leaving_a_transform_behind(self):
        self.assertIn("@keyframes slide-in{from{transform:translateX(100%)}", self.CSS)
        self.assertIn(".slide-in main{animation:slide-in", self.CSS)
        rule = self.CSS[self.CSS.index(".slide-in main{") : self.CSS.index("}", self.CSS.index(".slide-in main{"))]
        self.assertIn("backwards", rule)
        self.assertNotIn("forwards", rule, "a filled-forwards animation would override the drag's own transform")
        self.assertNotIn(" both", rule)

    def test_pages_slide_side_by_side_while_the_title_bar_and_rail_stay_still(self):
        self.assertIn("@view-transition{navigation:auto}", self.CSS)
        for name in ("page", "topbar", "rail"):
            self.assertIn(f"view-transition-name:{name}", self.CSS)
        self.assertIn("::view-transition-group(page){overflow:clip}", self.CSS)
        for direction in ("forward", "back"):
            for side in ("old", "new"):
                self.assertIn(f':root[data-slide="{direction}"]::view-transition-{side}(page)', self.CSS)
        self.assertIn(':root[dir="rtl"]{--slide:-100%}', self.CSS)

    def test_the_browsers_own_clear_button_is_hidden_so_there_is_only_one(self):
        self.assertIn("-webkit-search-cancel-button", self.CSS)

    def test_the_search_card_slides_out_from_behind_the_rail_inside_a_layer_that_clips_it(self):
        layer = self.CSS[self.CSS.index(".search-layer{") : self.CSS.index("}", self.CSS.index(".search-layer{"))]
        self.assertIn("inset-inline-start:var(--rail)", layer)
        self.assertIn("overflow:hidden", layer)
        self.assertIn("pointer-events:none", layer)
        self.assertIn(".search-layer[hidden]{display:none}", self.CSS)
        self.assertIn(".rail-link[hidden]{display:none}", self.CSS)
        shut = self.CSS[self.CSS.index(".search-card{") : self.CSS.index("}", self.CSS.index(".search-card{"))]
        self.assertIn("visibility:hidden", shut)
        self.assertIn("translateX(calc(var(--slide) * -1))", shut)
        self.assertIn(".search-card[data-open]{visibility:visible;transform:none", self.CSS)

    def test_a_word_found_by_search_is_marked_when_the_page_opens_at_it(self):
        self.assertIn(".terms tr:target{background:var(--bg)}", self.CSS)
        self.assertIn(".terms tr{scroll-margin-top:", self.CSS)

    def test_a_hidden_choice_in_a_segmented_control_really_disappears(self):
        # `#prefs .seg label{display:flex}` would otherwise beat the hidden attribute, and a hidden choice (Colour at high contrast) would show
        self.assertIn("#prefs .seg label{display:flex}", self.CSS)
        self.assertIn("#prefs .seg label[hidden]{display:none}", self.CSS)

    def test_the_slide_comes_from_the_other_side_in_right_to_left(self):
        self.assertIn("@keyframes slide-in-rtl{from{transform:translateX(-100%)}", self.CSS)
        self.assertIn(':root[dir="rtl"].slide-in main{animation-name:slide-in-rtl}', self.CSS)

    def test_the_page_hands_horizontal_touches_to_the_drag_and_keeps_scrolling_and_zoom(self):
        main = self.CSS[self.CSS.index("\nmain{") : self.CSS.index("}", self.CSS.index("\nmain{"))]
        self.assertIn("touch-action:pan-y pinch-zoom", main)

    def test_a_card_off_screen_cannot_make_the_page_scroll_sideways(self):
        app = self.CSS[self.CSS.index(".app{") : self.CSS.index("}", self.CSS.index(".app{"))]
        self.assertIn("overflow-x:clip", app)

    def test_reduced_motion_turns_every_animation_and_transition_off(self):
        self.assertIn("@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}", self.CSS)

    def test_pages_set_the_viewport_for_a_phone(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            phrasebook.build(pathlib.Path(tmp) / "dist", project_dir=fixture.make_project(pathlib.Path(tmp) / "proj"))
            page = (pathlib.Path(tmp) / "dist" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">', page)


class HowToTests(Scratch):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.project()
        fixture.edit(
            cls.proj / "pages" / "p1.json", lambda d: d.update(related=["points"])
        )  # so the Related topics feature applies
        cls.out = cls.tmp / "howto-out"
        quiet_build(cls.out, project_dir=cls.proj)
        cls.pages = {f.name: f.read_text(encoding="utf-8") for f in cls.out.glob("*.html")}

    def test_the_page_is_built_and_linked_from_the_about_page(self):
        self.assertIn("how-to.html", self.pages)
        self.assertIn('<a href="how-to.html">', self.pages["about.html"])

    def test_it_marks_itself_as_the_current_page_and_has_no_pager(self):
        page = self.pages["how-to.html"]
        self.assertIn('<span aria-current="page">', page)
        self.assertNotIn('class="pager"', page)

    def test_it_is_the_contents_of_the_book_and_links_every_chapter_and_feature(self):
        page = self.pages["how-to.html"]
        for chapter in Book.load(content.read(self.proj)["packs"]).sections:
            self.assertIn(f'href="help-{chapter["id"]}.html"', page)
            for feature in chapter[
                "features"
            ]:  # the fixture has regional forms and an address for reports, so every feature is shown
                self.assertIn(f'href="help-{chapter["id"]}.html#{feature["id"]}"', page, feature["id"])

    def test_the_chapter_covers_the_moves_the_keys_the_swipes_and_the_buttons(self):
        page = self.pages["help-finding-your-way.html"]
        book = json.loads((ENGINE / "help" / "en.json").read_text(encoding="utf-8"))
        for anchor in ("tiles", "back", "keys-and-touch", "drag-back", "side-bar"):
            entry = book["features"][anchor]
            self.assertIn(f'<section class="help-feature" id="{anchor}"', page, anchor)
            for field in ("keys", "touch"):
                if entry.get(field):
                    self.assertIn(entry[field].split(".")[0], page, f"{anchor} {field}")

    def test_it_is_a_reserved_name_so_a_project_page_cannot_collide(self):
        proj = self.project()
        fixture.write(proj / "pages" / "how-to.json", {"sections": [{"id": "s", "concepts": ["c"]}]})
        fixture.edit(proj / "structure.json", lambda d: d["groups"][0]["pages"].append("how-to"))
        with self.assertRaises(ContentError) as ctx:
            content.validate(content.read(proj))
        self.assertIn("reserved", str(ctx.exception))

    def test_it_is_precached_so_it_works_offline(self):
        self.assertIn('"how-to.html"', (self.out / "sw.js").read_text(encoding="utf-8"))


class GroupPageNamesTests(Scratch):
    def test_a_topic_cannot_be_named_like_a_group_page(self):
        proj = self.project()
        fixture.write(proj / "pages" / "group-x.json", {"sections": [{"id": "s", "concepts": ["c"]}]})
        fixture.edit(proj / "structure.json", lambda d: d["groups"][0]["pages"].append("group-x"))
        with self.assertRaises(ContentError) as ctx:
            content.validate(content.read(proj))
        self.assertIn("reserved", str(ctx.exception))

    def test_a_group_id_must_be_safe_in_a_file_name(self):
        for bad in ("Upper", "has space", "-lead", "../up", "a/b", "9lives"):
            proj = self.project()
            fixture.edit(proj / "structure.json", lambda d, b=bad: d["groups"][0].update(id=b))
            with self.assertRaises(ContentError, msg=bad):
                content.validate(content.read(proj))


class SettingsPageTests(Scratch):
    """The visitor's choices live on a page of their own, reached from the gear in the rail."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.project()
        cls.out = cls.tmp / "settings-out"
        quiet_build(cls.out, project_dir=cls.proj)
        cls.pages = {f.name: f.read_text(encoding="utf-8") for f in cls.out.glob("*.html")}

    def test_the_page_is_built_and_every_page_reaches_it_from_the_rail(self):
        self.assertIn("settings.html", self.pages)
        for name, page in self.pages.items():
            self.assertIn('href="settings.html"', page, name)

    def test_the_order_of_tiles_and_sections_is_a_choice_of_three_with_as_written_chosen(self):
        page = self.pages["settings.html"]
        self.assertIn('<section class="subsection" aria-labelledby="h-order"><h3 id="h-order">', page)
        for value in ("written", "simple", "advanced"):
            self.assertIn(f'<input type="radio" name="order" value="{value}" data-pref="order"', page)
        self.assertIn('name="order" value="written" data-pref="order" checked', page)
        self.assertEqual(page.count('name="order"'), 3)
        self.assertLess(page.index('id="h-appearance"'), page.index('id="h-order"'), "after the looks, before the regional forms")
        self.assertLess(page.index('id="h-order"'), page.index('data-variety-lang="qab"'))
        for name, other in self.pages.items():
            if name != "settings.html":
                self.assertNotIn('data-pref="order"', other, name)

    def group(self, ident):
        """One top-level fold of the Settings page, from its opening tag to its closing one."""
        page = self.pages["settings.html"]
        start = page.index(f'<details class="fold card" aria-labelledby="{ident}"')
        return page[start : page.index("</details>", start) + len("</details>")]

    def test_view_mode_accessibility_and_colour_schemes_are_one_group_in_that_order(self):
        look = self.group("h-look")
        self.assertIn("Accessibility and appearance", look.split("</summary>")[0])
        parts = re.findall(r'<section class="subsection" aria-labelledby="(h-[a-z]+)"><h3', look)
        self.assertEqual(parts, ["h-appearance", "h-access", "h-colours", "h-keys"])
        self.assertIn("View mode", look)
        self.assertNotIn(">Appearance<", look, "the light and dark choice is called View mode")
        for name in ("appearance", "access", "palette"):
            self.assertIn(f'name="{name}"', look, name)
        self.assertIn(" open>", look.split(">")[0] + ">", "the group opens first")

    def test_order_and_tile_layout_are_one_group_in_that_order(self):
        order = self.group("h-order-group")
        self.assertIn("Order and tile layout", order.split("</summary>")[0])
        parts = re.findall(r'<section class="subsection[^"]*"[^>]*aria-labelledby="(h-[a-z]+)"><h3', order)
        self.assertEqual(parts, ["h-order", "h-layout"])
        self.assertIn('name="order"', order)
        self.assertIn("data-reset-orders", order)
        self.assertIn("Tile layout", order)
        self.assertNotIn(" open>", order.split(">")[0] + ">", "shut until it is opened")

    def test_a_group_has_its_name_as_the_heading_and_each_choice_in_it_a_heading_beneath(self):
        for ident in ("h-look", "h-order-group"):
            group = self.group(ident)
            self.assertTrue(group.split("<summary>")[1].startswith("<h2"), ident)
            self.assertNotIn("<h2", group.split("</summary>")[1], f"{ident}: choices are headed with h3, under the group's h2")
            self.assertIn("<h3", group)

    def test_the_regional_forms_stay_a_group_of_their_own_after_the_others(self):
        page = self.pages["settings.html"]
        self.assertLess(page.index('aria-labelledby="h-order-group"'), page.index('aria-labelledby="h-var-qab"'))
        self.assertNotIn("h-var-qab", self.group("h-look") + self.group("h-order-group"))

    def test_every_control_stays_inside_the_panel_the_script_reveals(self):
        page = self.pages["settings.html"]
        panel = page[page.index('<div class="prefs" id="prefs" hidden>') : page.index("<noscript>")]
        self.assertEqual(panel.count('data-pref="'), page.count('data-pref="'), "every preference radio is in the panel")
        self.assertIn("data-reset-orders", panel)
        self.assertIn('data-variety-lang="qab"', panel)

    def test_the_tile_layout_is_still_offered_when_there_is_no_order_to_choose(self):
        proj = self.project()
        fixture.edit(proj / "structure.json", lambda d: d["groups"][0].update(level=2))
        fixture.edit(proj / "pages" / "p1.json", lambda d: (d.update(level=2), [s.update(level=2) for s in d["sections"]]))
        fixture.edit(proj / "pages" / "points.json", lambda d: (d.update(level=2), [s.update(level=2) for s in d["sections"]]))
        page = self.built(proj)["settings.html"]
        self.assertIn('aria-labelledby="h-order-group"', page)
        self.assertNotIn('id="h-order"', page)
        self.assertIn('id="h-layout"', page)

    def test_the_order_choice_is_said_in_both_languages_of_the_pair_and_says_a_saved_order_wins(self):
        page = self.pages["settings.html"]
        section = page[
            page.index('aria-labelledby="h-order"') : page.index("</section>", page.index('aria-labelledby="h-order"'))
        ]
        self.assertIn("Simplest first", section)
        self.assertIn("Most advanced first", section)
        self.assertIn("keeps your order", section)
        self.assertEqual(
            section.count('class="t" data-n="1"'), section.count('class="t" data-n="2"'), "every text in both languages"
        )

    def test_with_every_level_the_same_there_is_nothing_to_order_and_no_choice_is_offered(self):
        proj = self.project()
        fixture.edit(proj / "structure.json", lambda d: d["groups"][0].update(level=2))
        fixture.edit(proj / "pages" / "p1.json", lambda d: (d.update(level=2), [s.update(level=2) for s in d["sections"]]))
        fixture.edit(proj / "pages" / "points.json", lambda d: (d.update(level=2), [s.update(level=2) for s in d["sections"]]))
        page = self.built(proj)["settings.html"]
        self.assertNotIn('name="order"', page)
        self.assertNotIn('id="h-order"', page)

    def test_one_level_apart_anywhere_is_enough_to_offer_it(self):
        proj = self.project()
        fixture.edit(proj / "structure.json", lambda d: d["groups"][0].update(level=2))
        fixture.edit(proj / "pages" / "p1.json", lambda d: (d.update(level=2), [s.update(level=2) for s in d["sections"]]))
        fixture.edit(proj / "pages" / "points.json", lambda d: (d.update(level=2), [s.update(level=2) for s in d["sections"]]))
        fixture.edit(proj / "pages" / "p1.json", lambda d: d["sections"][0].update(level=3))
        self.assertIn('name="order"', self.built(proj)["settings.html"])

    def test_the_controls_are_on_that_page_only(self):
        for name, page in self.pages.items():
            if name == "settings.html":
                self.assertIn('<div class="prefs" id="prefs" hidden>', page)
                self.assertIn('data-pref="appearance"', page)
                self.assertIn('data-pref="palette"', page)
                self.assertIn('data-variety-lang="qab"', page)
            else:
                self.assertNotIn('id="prefs"', page, name)
                self.assertNotIn("data-pref=", page, name)
                self.assertNotIn("data-variety-lang", page, name)

    def test_the_saved_choices_still_apply_on_every_page(self):
        for name, page in self.pages.items():
            self.assertIn('<script src="app.js"></script>', page, name)
            self.assertIn('data-storage="demo-book"', page, name)

    def test_it_has_no_pager_and_goes_back_home(self):
        page = self.pages["settings.html"]
        self.assertNotIn('class="pager"', page)
        self.assertIn('<a class="rail-link back" href="index.html" data-back aria-label="Back"', page)

    def test_without_scripts_the_page_says_why_there_is_nothing_to_choose(self):
        self.assertIn('<noscript><p class="intro">', self.pages["settings.html"])

    def test_the_page_is_precached_so_it_works_offline(self):
        self.assertIn('"settings.html"', (self.out / "sw.js").read_text(encoding="utf-8"))

    def test_it_is_a_reserved_name(self):
        proj = self.project()
        fixture.write(proj / "pages" / "settings.json", {"sections": [{"id": "s", "concepts": ["c"]}]})
        fixture.edit(proj / "structure.json", lambda d: d["groups"][0]["pages"].append("settings"))
        with self.assertRaises(ContentError) as ctx:
            content.validate(content.read(proj))
        self.assertIn("reserved", str(ctx.exception))

    def test_other_pages_carry_no_settings_fieldsets(self):
        self.assertNotIn("<fieldset", self.pages["p1.html"])


class NoVisibleNumberingTests(unittest.TestCase):
    """The outline's numbers are internal addresses. Nothing on screen or read out may show them."""

    def test_the_styles_and_script_have_no_number_column(self):
        script = (ENGINE / "assets" / "nav.js").read_text(encoding="utf-8")
        styles = (ENGINE / "assets" / "style.css").read_text(encoding="utf-8")
        self.assertNotIn("number", script + styles.replace("font-variant-numeric", ""))

    def test_the_how_to_wording_does_not_teach_numbers(self):
        messages = json.loads((ENGINE / "messages" / "en.json").read_text(encoding="utf-8"))
        for key, text in messages.items():
            if key.startswith("how_to"):
                self.assertIsNone(re.search(r"\d\.\d", text), key)
                self.assertNotIn("numbered", text, key)
        book = (ENGINE / "help" / "en.json").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\d\.\d", book))
        self.assertNotIn("numbered", book)

    def test_the_address_stays_in_the_data_for_tests_and_linking(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            phrasebook.build(pathlib.Path(tmp) / "dist", project_dir=fixture.make_project(pathlib.Path(tmp) / "proj"))
            doc = json.loads((pathlib.Path(tmp) / "dist" / "tree.json").read_text(encoding="utf-8"))
            for page in (pathlib.Path(tmp) / "dist").glob("*.html"):
                text = page.read_text(encoding="utf-8")
                self.assertIsNone(re.search(r">\s*\d+\.\d+(\.\d+)*\s*<", text), page.name)
        self.assertEqual(doc["nodes"][0]["id"], "1")


class ArrangeTests(Scratch):
    """Edit order: the tiles carry their ids and the screen's name, the controls are hidden until the script runs, and a saved
    order is applied before the first paint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.project()
        add_icon(cls.proj, "weather")
        name_icons(cls.proj, group="weather")
        cls.out = cls.tmp / "arrange-out"
        quiet_build(cls.out, project_dir=cls.proj)
        cls.pages = {f.name: f.read_text(encoding="utf-8") for f in cls.out.glob("*.html")}

    def test_the_home_and_group_pages_are_arrangeable_and_the_others_are_not(self):
        for name, page in self.pages.items():
            tiles = 'data-tiles data-order="' in page
            self.assertEqual(tiles, name == "index.html" or name.startswith("group-"), name)
            self.assertEqual('id="arrange-button"' in page, tiles, name)

    def test_each_tile_carries_its_id_and_each_screen_its_name_for_the_saved_order(self):
        home = self.pages["index.html"]
        self.assertIn('data-order="index"', home)
        self.assertIn('<li data-tile="g1" data-level="1"><a class="tile-link" href="group-g1.html">', home)
        group = self.pages["group-g1.html"]
        self.assertIn('data-order="group-g1"', group)
        self.assertIn('<li data-tile="p1" data-level="2"><a class="tile-link" href="p1.html">', group)

    def test_the_spanner_is_hidden_until_the_script_shows_it(self):
        home = self.pages["index.html"]
        self.assertIn('class="rail-link arrange-toggle" id="arrange-button" hidden aria-pressed="false"', home)

    def test_the_bar_is_in_both_languages_and_its_messages_keep_their_placeholders_for_the_script(self):
        home = self.pages["index.html"]
        self.assertIn('data-arrange-bar data-picked="{name} picked up, place {n} of {total}.', home)
        self.assertIn('data-moved="{name} is now place {n} of {total}."', home)
        self.assertIn('data-reset="Order reset to the default."', home)
        self.assertIn('data-arrange-done><span lang="en">Save order</span></button>', home)
        self.assertIn('data-arrange-reset><span lang="en">Reset</span></button>', home)
        self.assertIn('<p class="sr-only" role="status" data-arrange-status></p>', home)

    def test_the_settings_page_has_a_reset_of_every_screen_hidden_until_the_script_runs(self):
        settings = self.pages["settings.html"]
        self.assertIn('<section class="subsection reset-orders" data-reset-orders hidden aria-labelledby="h-layout">', settings)
        self.assertIn('data-done="Every tile is back in its default order."', settings)
        self.assertIn('data-failed="The order could not be saved on this device."', settings)

    def test_every_page_loads_the_arranging_script_after_the_page_and_hides_nothing_while_it_waits(self):
        for name, page in self.pages.items():
            self.assertIn('<script src="arrange.js" defer></script>', page, name)
            self.assertNotIn("data-arrange-pending", page, name)
        self.assertNotIn("data-arrange-pending", (ENGINE / "assets" / "style.css").read_text(encoding="utf-8"))
        self.assertTrue((self.out / "arrange.js").is_file())

    def test_every_tile_list_asks_for_its_order_right_after_it_and_before_anything_is_painted(self):
        hook = '</ul><script>(function(d){var v=new Event("phrasebook:order");v.page=d.currentScript.parentNode;d.dispatchEvent(v)})(document)</script>'
        for name, page in self.pages.items():
            if 'data-tiles data-order="' in page:
                self.assertEqual(page.count(hook), 1, name)
                self.assertLess(page.index(hook), page.index("</main>"), name)
            elif name != "p1.html" and name != "points.html":
                self.assertNotIn("phrasebook:order", page, name)

    def test_a_topic_asks_for_its_order_after_its_sections_and_before_the_pager(self):
        for name in ("p1.html", "points.html"):
            page = self.pages[name]
            self.assertEqual(page.count('new Event("phrasebook:order")'), 1, name)
            self.assertLess(
                max(page.rfind("</section>"), page.rfind("</details>")), page.index('new Event("phrasebook:order")'), name
            )
            if 'class="pager"' in page:
                self.assertLess(page.index('new Event("phrasebook:order")'), page.index('class="pager"'), name)

    def test_the_hook_has_no_pair_of_closing_braces_which_the_check_for_unrendered_templates_rejects(self):
        for name, page in self.pages.items():
            self.assertNotIn("}}", page, name)

    def test_order_js_is_in_the_head_after_app_js_and_before_the_page_so_it_can_answer_the_hook(self):
        for name, page in self.pages.items():
            head = page.split("<body>")[0]
            self.assertIn('<script src="app.js"></script>\n<script src="order.js"></script>\n', head, name)
            self.assertLess(head.index('src="order.js"'), head.index('src="nav.js"'), name)
            self.assertLess(head.index('src="order.js"'), head.index('src="arrange.js"'), name)
            self.assertNotIn('src="order.js" defer', head, name)
        self.assertTrue((self.out / "order.js").is_file())

    def test_each_tile_and_each_section_carries_the_level_the_build_worked_out(self):
        home, group, topic = self.pages["index.html"], self.pages["group-g1.html"], self.pages["p1.html"]
        self.assertIn('<li data-tile="g1" data-level="1"><a class="tile-link"', home)
        self.assertIn('<li data-tile="p1" data-level="2"><a class="tile-link" href="p1.html">', group)
        self.assertIn('<li data-tile="points" data-level="1"><a class="tile-link"', group)
        self.assertIn('<details class="fold sec" id="s1" data-level="2" open>', topic)
        self.assertIn('<details class="fold sec" id="s3" data-level="2" open>', topic)

    def test_arrange_js_takes_its_orders_from_the_lists_so_reset_goes_to_the_default_and_not_to_the_saved_order(self):
        script = (ENGINE / "assets" / "arrange.js").read_text(encoding="utf-8")
        self.assertIn('defaults = listed("data-written")', script)
        self.assertIn('fallback = listed("data-default")', script)
        self.assertIn("reorder(fallback.slice(), true)", script)
        self.assertNotIn("reorder(defaults.slice(), true)", script)
        self.assertNotIn("phrasebook:peek", script, "the copy of a page is ordered by order.js")


class MoreNoteTests(Scratch):
    """A topic can end with a note of its own: body blocks (text and links, as in an About section) from the first language that
    has them, after the related row. It is there to point a reader to a fuller source."""

    MORE = ["Not a full list.", {"links": [{"text": "Fuller list", "href": "https://example.org/list"}]}]

    def with_more(self, more, code="qab"):
        proj = self.project()
        fixture.edit(proj / "packs" / code / "pages" / "p1.json", lambda d: d.update(more=more))
        return proj

    def test_the_note_closes_the_topic_with_its_text_and_links(self):
        page = self.built(self.with_more(self.MORE))["p1.html"]
        note = page[page.index('<footer class="more"') : page.index("</footer>", page.index('<footer class="more"'))]
        self.assertIn('lang="qab"', note)
        self.assertIn("<p>Not a full list.</p>", note)
        self.assertIn('<a href="https://example.org/list">Fuller list</a>', note)
        self.assertLess(page.index('new Event("phrasebook:order")'), page.index('<footer class="more"'))
        self.assertLess(page.index('<footer class="more"'), page.index('class="pager"'))

    def test_it_follows_the_related_row(self):
        proj = self.with_more(self.MORE)
        fixture.edit(proj / "pages" / "p1.json", lambda d: d.update(related=["points"]))
        page = self.built(proj)["p1.html"]
        self.assertLess(page.index('<section class="related"'), page.index('<footer class="more"'))

    def test_a_topic_without_one_has_none(self):
        self.assertNotIn('class="more"', self.built(self.project())["p1.html"])

    def test_the_first_language_of_the_pair_that_has_one_gives_it(self):
        proj = self.with_more(["From the first."], code="qaa")
        fixture.edit(proj / "packs" / "qab" / "pages" / "p1.json", lambda d: d.update(more=["From the second."]))
        page = self.built(proj)["p1.html"]
        self.assertIn("From the first.", page)
        self.assertNotIn("From the second.", page)

    def test_a_bad_note_is_refused_naming_the_file(self):
        for bad in ("text", [], [3], [{"links": [{"text": "x", "href": "http://example.org"}]}]):
            with self.subTest(bad=bad):
                with self.assertRaises(ContentError) as caught:
                    content.validate(content.read(self.with_more(bad)))
                self.assertIn("pages/p1.json", str(caught.exception))


class RelatedTopicsTests(Scratch):
    """An end topic can link to related topics as a row of tiles, after its sections, so a reader can go from one to another
    without going back up the tree. A tile opens the page, at a section if one is named."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.project()
        fixture.edit(cls.proj / "pages" / "p1.json", lambda d: d.update(related=["points"]))
        fixture.edit(cls.proj / "pages" / "points.json", lambda d: d.update(related=["p1#s2"]))
        cls.pages = cls.built(cls.proj)

    def row(self, name):
        page = self.pages[name]
        return page[
            page.index('<section class="related"') : page.index("</section>", page.index('<section class="related"')) + 10
        ]

    def test_the_row_follows_the_sections_and_comes_before_the_pager(self):
        page = self.pages["p1.html"]
        related = page.index('<section class="related"')
        self.assertLess(max(page.rfind("</section>", 0, related), page.rfind("</details>", 0, related)), related)
        self.assertLess(
            page.index('new Event("phrasebook:order")'),
            page.index('<section class="related"'),
            "after the sections' ordering hook",
        )
        self.assertLess(page.index('<section class="related"'), page.index('class="pager"'))

    def test_it_has_a_heading_in_both_languages_and_is_a_list_of_tiles_that_is_never_arranged_or_put_in_order(self):
        row = self.row("p1.html")
        self.assertIn('id="h-related"', row)
        self.assertIn("Related topics", row)
        self.assertIn('<ul class="tiles" data-tiles aria-label="Related topics">', row)
        self.assertNotIn("data-order", row, "no saved order is named, so arrange.js and order.js leave it be")

    def test_a_tile_opens_the_page_and_is_named_for_it_in_both_languages(self):
        row = self.row("p1.html")
        self.assertIn('<a class="tile-link" href="points.html" data-related>', row)
        self.assertIn('<span class="l1">qaa points</span>', row)
        self.assertIn('lang="qab">qab points</span>', row)
        self.assertIn('<li data-tile="points" data-level="1">', row)

    def test_a_tile_that_names_a_section_opens_it_there_and_is_named_for_the_section(self):
        row = self.row("points.html")
        self.assertIn('<a class="tile-link" href="p1.html#s2" data-related>', row)
        self.assertIn('<span class="l1">qaa section s2</span>', row)
        self.assertIn('lang="qab">qab section s2</span>', row)
        self.assertIn('<li data-tile="p1-s2" data-level="2">', row)

    def test_a_topic_with_no_related_list_has_no_row(self):
        self.assertNotIn('class="related"', self.pages["group-g1.html"])
        proj = self.project()
        self.assertNotIn('class="related"', self.built(proj)["p1.html"])

    def test_the_tiles_carry_the_marker_that_makes_back_return_to_the_topic_they_were_followed_from(self):
        for name, page in self.pages.items():
            for link in re.findall(r'<a class="tile-link" href="[^"]+"[^>]*>', page):
                in_row = link in self.row(name) if 'class="related"' in page else False
                self.assertEqual("data-related" in link, in_row, f"{name}: {link}")

    def test_a_target_held_back_from_the_release_is_left_out_and_comes_back_with_it(self):
        proj = self.project()
        fixture.edit(proj / "pages" / "points.json", lambda d: d.update(related=["p1"]))
        fixture.edit(proj / "pages" / "p1.json", lambda d: [sec.update(status="development") for sec in d["sections"]])
        self.assertNotIn('class="related"', self.built(proj)["points.html"])
        self.assertIn('href="p1.html" data-related', self.built(proj, channel="development")["points.html"])

    def test_a_section_that_is_not_published_still_leaves_the_page_worth_a_tile(self):
        proj = self.project()
        fixture.edit(proj / "pages" / "points.json", lambda d: d.update(related=["p1#s2"]))
        fixture.edit(proj / "pages" / "p1.json", lambda d: d["sections"][1].update(status="development"))
        row = self.built(proj)["points.html"]
        row = row[row.index('<section class="related"') :]
        self.assertIn('<a class="tile-link" href="p1.html" data-related>', row, "the page, with no section to land on")
        self.assertIn('<span class="l1">qaa page</span>', row, "named for the page")

    def test_a_figure_section_can_be_linked_to_since_it_keeps_its_address(self):
        proj = self.project()
        fixture.edit(proj / "pages" / "p1.json", lambda d: d.update(related=["points#dirs"]))
        page = self.built(proj)["p1.html"]
        self.assertIn('href="points.html#dirs" data-related', page)

    def invalid(self, related, fragment, **extra):
        proj = self.project()
        fixture.edit(proj / "pages" / "p1.json", lambda d: d.update(related=related, **extra))
        with self.assertRaises(ContentError) as caught:
            content.validate(content.read(proj))
        self.assertIn(fragment, str(caught.exception))
        self.assertIn("pages/p1.json", str(caught.exception))

    def test_a_related_list_is_checked_naming_the_file(self):
        self.invalid("points", "must be a list")
        self.invalid([], "must be a list")
        self.invalid([3], "must be a list")
        self.invalid([None], "must be a list")
        self.invalid(["p1"], "this page itself")
        self.invalid(["p1#s2"], "this page itself")
        self.invalid(["nowhere"], "does not exist")
        self.invalid(["points#nowhere"], "section that page does not have")
        self.invalid(["points#"], "no section after it")
        self.invalid(["points", "points"], "more than once")
        self.invalid(
            ["points", "points#dirs"],
            "more than once",
        )

    def test_a_section_id_that_cannot_travel_in_an_address_cannot_be_linked_to(self):
        proj = self.project()
        fixture.edit(proj / "pages" / "points.json", lambda d: d["sections"][0].update(id="a b"))
        fixture.edit(proj / "pages" / "p1.json", lambda d: d.update(related=["points#a b"]))
        with self.assertRaises(ContentError):
            content.validate(content.read(proj))

    def test_a_valid_list_is_accepted(self):
        proj = self.project()
        fixture.edit(proj / "pages" / "p1.json", lambda d: d.update(related=["points#dirs"]))
        content.validate(content.read(proj))

    def test_the_head_script_reads_the_topic_followed_from_and_the_section_and_keeps_both_out_of_the_address(self):
        head = self.pages["p1.html"].split("<body>")[0]
        self.assertIn("(?:;(?:from|at)=[A-Za-z0-9._-]+)*", head)
        self.assertIn(
            "f?{from:f[1]}:null", head, "the topic goes in the history entry, where Back finds it and a reload keeps it"
        )
        self.assertIn(
            'w.location.pathname+w.location.search+(a?"#"+a[1]:"")', head, "the address is left with the section and nothing else"
        )
        self.assertIn("t.scrollIntoView()", head)
        self.assertNotIn("}}", head)

    def test_a_page_a_link_lands_on_keeps_clear_of_the_title_bar(self):
        css = (ENGINE / "assets" / "style.css").read_text(encoding="utf-8")
        self.assertIn("section[id],.fold.sec[id]{scroll-margin-top:calc(var(--inset-top) + var(--bar) + 1rem)}", css)

    def test_the_heading_is_a_message_so_it_can_be_translated(self):
        messages = json.loads((ENGINE / "messages" / "en.json").read_text(encoding="utf-8"))
        self.assertEqual(messages["related"], "Related topics")


if __name__ == "__main__":
    unittest.main()


class OnePageGroupTests(Scratch):
    """A group with "layout": "one-page" is one page: each of its topics is an accordion, shut until opened, whose summary is the
    topic's tile and whose body is the topic. The topics have no pages of their own, so every address of one points into the
    group's page, and Settings' order puts the accordions in order there."""

    @classmethod
    def one_page(cls, proj):
        fixture.edit(proj / "structure.json", lambda d: d["groups"][0].update(layout="one-page"))
        return proj

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.one_page(cls.project())
        cls.pages = cls.built(cls.proj)
        cls.page = cls.pages["group-g1.html"]

    def test_a_figure_section_keeps_its_address_inside_an_accordion_too(self):
        self.assertIn('<section id="dirs" class="figure">', self.page)

    def test_the_group_page_holds_each_topic_as_a_shut_accordion_named_as_its_tile(self):
        folds = re.findall(r'<details class="fold topic"[^>]*>', self.page)
        self.assertEqual(len(folds), 2)
        self.assertIn('<details class="fold topic" aria-labelledby="h-topic-p1" id="topic-p1" data-level="', self.page)
        self.assertTrue(all(" open" not in f for f in folds), "shut by default")
        self.assertIn('<summary><h2 id="h-topic-p1"><span class="topic-name"><span class="l1">qaa page</span>', self.page)
        self.assertIn('<span class="l2" lang="qab">qab page</span></span></h2></summary>', self.page)

    def test_the_topics_have_no_pages_of_their_own(self):
        self.assertNotIn("p1.html", self.pages)
        self.assertNotIn("points.html", self.pages)
        self.assertNotIn('href="p1.html', self.page)

    def test_inside_an_accordion_the_sections_are_a_level_down_and_carry_no_level(self):
        body = self.page[self.page.index('id="topic-p1"') : self.page.index('id="topic-points"')]
        self.assertIn("qaa lede", body)
        self.assertIn('<details class="fold sec" id="s2" open><summary><h3>', body)
        self.assertNotRegex(
            body, r'<(section|details class="fold sec")[^>]*data-level', "the accordions are put in order, not the sections"
        )
        self.assertIn('<tr id="s1.c1">', body)

    def test_each_section_is_an_accordion_open_to_begin_with_whose_summary_is_its_heading(self):
        body = self.page[self.page.index('id="topic-p1"') : self.page.index('id="topic-points"')]
        for sid in ("s1", "s2"):
            at = body.index(f'<details class="fold sec" id="{sid}"')
            tag = body[at : body.index(">", at)]
            self.assertTrue(tag.endswith(" open"), sid)
            summary = body[body.index("<summary>", at) : body.index("</summary>", at)]
            self.assertIn("<h3>", summary, sid)
            self.assertNotIn("<table", summary, sid)
            self.assertIn('<table class="terms pair">', body[body.index("</summary>", at) :], sid)

    def test_settings_order_puts_the_accordions_in_order_on_the_page(self):
        self.assertLess(self.page.rindex("</details>"), self.page.index('new Event("phrasebook:order")'))
        script = (ENGINE / "assets" / "order.js").read_text(encoding="utf-8")
        self.assertIn('el.tagName === "DETAILS"', script)

    def test_the_page_is_read_like_a_topic_in_the_pagers_run(self):
        self.assertIn('class="pager"', self.page)
        self.assertIn('<a class="prev" href="index.html">', self.page)
        self.assertNotIn('class="tiles" data-tiles data-order', self.page, "no grid of tiles to arrange")

    def test_search_points_into_the_accordions(self):
        out = self.tmp / "dict-out"
        quiet_build(out, project_dir=self.proj)
        entries = json.loads((out / "dictionary.json").read_text(encoding="utf-8"))["entries"]
        c1 = next(e for e in entries if e["concept"] == "c1")
        self.assertEqual(c1["pages"][0]["href"], "group-g1.html#s1.c1")
        self.assertEqual(c1["pages"][0]["topic"], "group-g1.html#topic-p1")
        scope = json.loads(html.unescape(re.search(r'data-scope="([^"]*)"', self.page).group(1)))
        self.assertEqual(scope, ["group-g1.html"])
        self.assertIn("item.page.topic", (ENGINE / "assets" / "search.js").read_text(encoding="utf-8"))

    def test_an_address_inside_a_shut_accordion_opens_it(self):
        self.assertIn('p.tagName==="DETAILS")p.open=true', self.page, "the head script, for an address carried by nav.js")
        script = (ENGINE / "assets" / "nav.js").read_text(encoding="utf-8")
        self.assertIn('window.addEventListener("hashchange", reveal)', script)

    def test_a_related_tile_from_another_group_lands_on_the_accordion_or_its_section(self):
        proj = self.project()

        def two_groups(d):
            d["groups"] = [
                {"id": "g1", "layout": "one-page", "pages": ["p1"]},
                {"id": "g2", "pages": ["points"], "links": ["p1"]},
            ]

        fixture.edit(proj / "structure.json", two_groups)
        for code in fixture.LANGS:
            fixture.edit(proj / "packs" / code / "pack.json", lambda d, code=code: d["groups"].update(g2=f"{code} second"))
        fixture.edit(proj / "pages" / "points.json", lambda d: d.update(related=["p1#s2"]))
        pages = self.built(proj)
        self.assertIn('href="group-g1.html#s2" data-related', pages["points.html"])
        self.assertIn('href="group-g1.html#topic-p1"', pages["group-g2.html"], "a group's link to a one-page topic")

    def test_the_layout_is_checked_naming_the_group(self):
        for fn, fragment in (
            (lambda d: d["groups"][0].update(layout="cards"), "'layout' must be one of"),
            (lambda d: d["groups"][0].update(layout="one-page"), "holds section 's1' twice"),
        ):
            proj = self.project()
            fixture.edit(proj / "structure.json", fn)
            if "twice" in fragment:
                fixture.edit(proj / "pages" / "points.json", lambda d: d["sections"][0].update(id="s1"))
            with self.assertRaises(ContentError) as caught:
                content.validate(content.read(proj))
            self.assertIn(fragment, str(caught.exception))
            self.assertIn("group 'g1'", str(caught.exception))
