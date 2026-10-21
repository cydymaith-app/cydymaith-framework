"""Tests of the theme screenshots (phrasebook/screenshots.py and the --screenshots flag).

A fake browser stands in for the real one, so these need no browser installed: it reads the page it is asked to show, as
it is at that moment, and writes a small file where the screenshot should go. Run from the repo root:
python3 -m unittest discover -s tests -v
"""
import pathlib
import re
import sys
import unittest
import urllib.parse
import urllib.request
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import phrasebook  # noqa: E402
from phrasebook import channels, cli, content, screenshots  # noqa: E402
from phrasebook.errors import ContentError  # noqa: E402
from test_framework import Scratch, quiet_build  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


class FakeBrowser:
    """Records every request and what the page looked like when it was made, then 'takes' the screenshot."""

    def __init__(self, write=True):
        self.calls, self.write = [], write

    def __call__(self, command, target, timeout=None):
        url = next(a for a in command if a.startswith("file:"))
        page = pathlib.Path(urllib.request.url2pathname(urllib.parse.urlparse(url).path))
        self.calls.append({"command": command, "target": pathlib.Path(target), "html": page.read_text(encoding="utf-8"),
                           "page": page.name})
        if self.write:
            pathlib.Path(target).write_bytes(PNG)


class ShootingTests(Scratch):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.project()
        cls.site_dir = cls.tmp / "site"
        quiet_build(cls.site_dir, project_dir=cls.proj)
        cls.raw = channels.select(content.read(cls.proj))
        cls.ed = content.pick_edition(cls.raw)[1]

    def take(self, name, fake=None):
        fake = fake or FakeBrowser()
        out = self.tmp / name
        with mock.patch.object(screenshots, "run_browser", fake):
            taken = cli.take_screenshots(self.site_dir, self.raw, self.ed, out, browser="fake-browser")
        return fake, taken, out

    def test_there_is_one_picture_for_every_palette_and_variant_and_no_more(self):
        fake, taken, out = self.take("all")
        self.assertEqual(len(fake.calls), 5 * 2)  # five palettes, light and dark, one page
        self.assertEqual(len(taken), 10)
        self.assertEqual(sorted(p.name for p in out.glob("*.png")),
                         sorted(f"{pal}-{v}.png" for pal in ("default", "high-contrast", "red-green", "red-green-safe", "blue-yellow-safe")
                                for v in ("light", "dark")))

    def test_the_one_page_is_the_first_topic_with_a_drawing_because_it_shows_the_most_colour(self):
        fake, _, _ = self.take("pages")
        self.assertEqual({c["page"] for c in fake.calls}, {"points.html"})
        self.assertIn('class="rose"', fake.calls[0]["html"])

    def test_without_a_drawing_the_first_topic_is_used(self):
        raw = self.raw_without_figures()
        fake = FakeBrowser()
        with mock.patch.object(screenshots, "run_browser", fake):
            cli.take_screenshots(self.site_dir, raw, self.ed, self.tmp / "nofig", browser="fake-browser")
        self.assertEqual({c["page"] for c in fake.calls}, {"p1.html"})

    def raw_without_figures(self):
        import copy
        raw = copy.deepcopy(self.raw)
        for page in raw["pages"].values():
            page.pop("figure", None)
        return raw

    def test_a_dark_theme_is_set_the_way_the_settings_page_would_set_it(self):
        fake, _, _ = self.take("dark")
        call = next(c for c in fake.calls if c["target"].name == "high-contrast-dark.png")
        self.assertIn('data-theme="dark" data-palette="high-contrast">', call["html"])

    def test_a_light_theme_says_light_so_the_phone_cannot_pick_dark(self):
        fake, _, _ = self.take("light")
        call = next(c for c in fake.calls if c["target"].name == "red-green-safe-light.png")
        self.assertIn('data-theme="light" data-palette="red-green-safe">', call["html"])

    def test_the_default_palette_is_the_pages_own_so_it_sets_no_palette(self):
        fake, _, _ = self.take("default")
        for call in (c for c in fake.calls if c["target"].name.startswith("default-")):
            self.assertNotIn("data-palette", call["html"])
            self.assertIn("data-theme=", call["html"])

    def test_the_scripts_are_taken_out_so_nothing_resets_the_theme(self):
        fake, _, _ = self.take("scripts")
        for call in fake.calls:
            self.assertNotIn("<script", call["html"], call["target"].name)
        original = (self.site_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn('<script src="app.js">', original, "the built site itself is left as it was")
        self.assertNotIn("data-theme", original)

    def test_the_browser_is_told_to_make_a_phone_sized_headless_screenshot_to_an_absolute_path(self):
        fake, _, out = self.take("command")
        command = fake.calls[0]["command"]
        self.assertEqual(command[0], "fake-browser")
        self.assertIn("--headless=new", command)
        self.assertIn("--window-size=500,780", command)
        self.assertIn("--force-device-scale-factor=1", command)
        shot = next(a for a in command if a.startswith("--screenshot="))
        self.assertTrue(pathlib.Path(shot.split("=", 1)[1]).is_absolute())
        self.assertEqual(pathlib.Path(shot.split("=", 1)[1]).parent, out.resolve())

    def test_every_shot_gets_its_own_profile_so_a_browser_that_lingers_cannot_block_the_next(self):
        fake, _, _ = self.take("profiles")
        profiles = [a for c in fake.calls for a in c["command"] if a.startswith("--user-data-dir=")]
        self.assertEqual(len(profiles), len(set(profiles)))

    def test_a_gallery_lists_every_picture_under_the_palettes_name(self):
        _, _, out = self.take("gallery")
        readme = (out / "README.md").read_text(encoding="utf-8")
        self.assertIn("python3 build.py dist --screenshots", readme)
        for name in ("Default", "High contrast", "Red–green safe", "Blue–yellow safe"):
            self.assertIn(f"| {name} | ", readme)
        for png in out.glob("*.png"):
            self.assertIn(f"]({png.name})", readme)
        self.assertIn("| Palette | Light | Dark |", readme)
        self.assertEqual(readme.count("\n| "), 1 + 5, "a header and a row for each of the five palettes")
        self.assertIn("`points.html`", readme, "it says which page every picture shows")
        self.assertIn("ignored by git", readme)

    def test_a_browser_that_takes_no_picture_fails_the_build_saying_which(self):
        with self.assertRaises(ContentError) as ctx:
            self.take("none", FakeBrowser(write=False))
        message = str(ctx.exception)
        self.assertIn("no screenshot", message)
        self.assertIn("points.html", message)
        self.assertIn("default (light)", message)

    def test_an_empty_picture_counts_as_none(self):
        class Empty(FakeBrowser):
            def __call__(self, command, target, timeout=None):
                super().__call__(command, target, timeout)
                pathlib.Path(target).write_bytes(b"")

        with self.assertRaises(ContentError):
            self.take("empty", Empty())

    def test_old_pictures_are_replaced_not_kept(self):
        out = self.tmp / "replace"
        out.mkdir()
        (out / "default-light.png").write_bytes(b"old")
        self.take("replace")
        fresh = (self.tmp / "replace" / "default-light.png").read_bytes()
        self.assertEqual(fresh, PNG)

    def test_only_the_palettes_an_edition_offers_are_shot(self):
        ed = dict(self.ed, palettes=["default", "high-contrast"])
        fake = FakeBrowser()
        with mock.patch.object(screenshots, "run_browser", fake):
            taken = cli.take_screenshots(self.site_dir, self.raw, ed, self.tmp / "subset", browser="fake-browser")
        self.assertEqual({p for p, *_ in taken}, {"default", "high-contrast"})
        self.assertEqual(len(taken), 2 * 2)


class ThemedPageTests(unittest.TestCase):
    PAGE = '<!doctype html>\n<html lang="en" data-storage="x" data-parent="y.html">\n<head>\n<script src="a.js"></script>\n' \
           '<script>\nvar x = 1;\n</script>\n<title>t</title></head><body><html></html></body></html>\n'

    def test_scripts_of_both_kinds_go_and_the_theme_is_added_to_the_first_html_tag_only(self):
        page = screenshots.themed(self.PAGE, "high-contrast", "dark", "default")
        self.assertNotIn("<script", page)
        self.assertNotIn("var x", page)
        self.assertIn('<html lang="en" data-storage="x" data-parent="y.html" data-theme="dark" data-palette="high-contrast">', page)
        self.assertEqual(page.count("data-theme"), 1)
        self.assertIn("<title>t</title>", page)

    def test_the_default_palette_adds_no_palette_attribute(self):
        page = screenshots.themed(self.PAGE, "default", "light", "default")
        self.assertIn('data-theme="light">', page)
        self.assertNotIn("data-palette", page)

    def test_a_project_can_make_another_palette_its_baseline(self):
        page = screenshots.themed(self.PAGE, "default", "light", "sepia")
        self.assertIn('data-palette="default"', page)


class FindingTheBrowserTests(unittest.TestCase):
    def find(self, env=None, names=(), places=()):
        which = lambda n: f"/usr/bin/{n}" if n in names else None
        exists = lambda p: p in places
        return screenshots.find_browser(env or {}, which=which, exists=exists)

    def test_the_environment_variable_wins_whether_it_is_a_name_or_a_path(self):
        self.assertEqual(self.find({"PHRASEBOOK_BROWSER": "chromium"}, names=("chromium", "google-chrome")), "/usr/bin/chromium")
        self.assertEqual(self.find({"PHRASEBOOK_BROWSER": "/opt/b/browser"}, places=("/opt/b/browser",)), "/opt/b/browser")

    def test_an_environment_variable_that_names_nothing_runnable_is_an_error_not_a_fallback(self):
        with self.assertRaises(ContentError) as ctx:
            self.find({"PHRASEBOOK_BROWSER": "nope"}, names=("chromium",))
        self.assertIn("PHRASEBOOK_BROWSER", str(ctx.exception))

    def test_the_usual_names_are_tried_in_order(self):
        self.assertEqual(self.find(names=("msedge", "google-chrome")), "/usr/bin/google-chrome")
        self.assertEqual(self.find(names=("msedge",)), "/usr/bin/msedge")

    def test_the_usual_install_places_are_tried_last(self):
        place = screenshots.PLACES[0]
        self.assertEqual(self.find(places=(place,)), place)
        self.assertEqual(self.find(names=("chromium",), places=(place,)), "/usr/bin/chromium")

    def test_no_browser_says_how_to_provide_one(self):
        with self.assertRaises(ContentError) as ctx:
            self.find()
        self.assertIn("PHRASEBOOK_BROWSER", str(ctx.exception))
        self.assertIn("Chrome", str(ctx.exception))


class CommandLineFlagTests(Scratch):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proj = cls.project()

    def run_main(self, *argv):
        with mock.patch.object(cli, "take_screenshots", return_value=[1, 2, 3]) as taken:
            with mock.patch("sys.stdout"), mock.patch("sys.stderr"):
                cli.main(list(argv))
        return taken

    def test_the_flag_with_a_folder_uses_it(self):
        taken = self.run_main(str(self.tmp / "o1"), "--project", str(self.proj), "--screenshots", str(self.tmp / "shots"))
        self.assertEqual(taken.call_args[0][3], str(self.tmp / "shots"))

    def test_the_flag_alone_means_docs_screenshots(self):
        taken = self.run_main(str(self.tmp / "o2"), "--project", str(self.proj), "--screenshots")
        self.assertEqual(taken.call_args[0][3], "docs/screenshots")

    def test_the_flag_before_another_option_does_not_swallow_it(self):
        taken = self.run_main(str(self.tmp / "o3"), "--screenshots", "--project", str(self.proj))
        self.assertEqual(taken.call_args[0][3], "docs/screenshots")

    def test_the_output_folder_is_still_the_first_plain_argument(self):
        taken = self.run_main("--screenshots", "--project", str(self.proj), str(self.tmp / "o4"))
        self.assertEqual(str(taken.call_args[0][0]), str(self.tmp / "o4"))

    def test_without_the_flag_no_browser_is_ever_looked_for(self):
        with mock.patch.object(cli, "take_screenshots") as taken, mock.patch.object(screenshots, "find_browser") as find:
            with mock.patch("sys.stdout"), mock.patch("sys.stderr"):
                cli.main([str(self.tmp / "o5"), "--project", str(self.proj)])
        taken.assert_not_called()
        find.assert_not_called()

    def test_a_missing_browser_stops_the_build_with_a_clear_message(self):
        with mock.patch.object(screenshots, "find_browser", side_effect=ContentError("no Chrome, Chromium or Edge found")):
            with self.assertRaises(SystemExit) as ctx:
                with mock.patch("sys.stdout"):
                    cli.main([str(self.tmp / "o6"), "--project", str(self.proj), "--screenshots", str(self.tmp / "s6")])
        self.assertIn("screenshots: no Chrome", str(ctx.exception))


class IgnoredByGitTests(unittest.TestCase):
    def test_the_generated_pictures_are_not_committed(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("docs/screenshots/", lines)


class EndingTheBrowserTests(unittest.TestCase):
    def test_a_finished_browser_is_left_alone(self):
        proc = mock.Mock()
        proc.poll.return_value = 0
        screenshots.end(proc)
        proc.wait.assert_not_called()

    def test_the_run_returns_once_the_picture_has_stopped_growing_and_ends_the_browser(self):
        target = mock.Mock()
        target.exists.return_value = True
        target.stat.return_value = mock.Mock(st_size=100)
        proc = mock.Mock()
        proc.poll.return_value = None
        with mock.patch.object(screenshots.subprocess, "Popen", return_value=proc), \
                mock.patch.object(screenshots, "end") as end, mock.patch.object(screenshots.time, "sleep"):
            screenshots.run_browser(["b"], target, timeout=5)
        end.assert_called_once_with(proc)


if __name__ == "__main__":
    unittest.main()
