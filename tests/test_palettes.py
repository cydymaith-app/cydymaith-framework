"""Tests of the colour maths (colour.py) and of palette validation and CSS (palettes.py).

Building sites with palettes is tested in test_framework.py (PaletteSiteTests). Run from the repo root:
python3 -m unittest discover -s tests -v
"""

import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from phrasebook import colour, palettes  # noqa: E402
from phrasebook.content import LANG_CODE  # noqa: E402
from phrasebook.errors import ContentError  # noqa: E402

ENGINE_PALETTES = ROOT / "phrasebook" / "palettes"

# The colours the site had before palettes were data, written out so a refactor cannot change the default look.
ORIGINAL_LIGHT = {
    "bg": "#f1f4f5",
    "surface": "#ffffff",
    "ink": "#16252d",
    "muted": "#566972",
    "rule": "#d3dbdf",
    "rule-strong": "#9db0b9",
    "accent": "#b01e2e",
    "star": "#e2e9ec",
}
ORIGINAL_DARK = {
    "bg": "#11191e",
    "surface": "#172228",
    "ink": "#e4ebee",
    "muted": "#93a4ad",
    "rule": "#2a3941",
    "rule-strong": "#4d626d",
    "accent": "#ff7a87",
    "star": "#24343c",
}


def hexes(colours):
    return {role: colour.rgb_to_hex(rgb) for role, rgb in colours.items()}


class ColourTests(unittest.TestCase):
    def test_black_and_white_in_oklab(self):
        self.assertAlmostEqual(colour.rgb_to_oklab((1, 1, 1))[0], 1.0, places=5)
        self.assertEqual(colour.rgb_to_oklab((0, 0, 0)), (0.0, 0.0, 0.0))

    def test_the_wcag_extremes_and_symmetry(self):
        self.assertAlmostEqual(colour.contrast((0, 0, 0), (1, 1, 1)), 21.0, places=6)
        self.assertAlmostEqual(colour.contrast((1, 1, 1), (0, 0, 0)), 21.0, places=6)
        self.assertAlmostEqual(colour.contrast((0.3, 0.4, 0.5), (0.3, 0.4, 0.5)), 1.0, places=6)

    def test_hex_survives_a_round_trip_through_oklab(self):
        for value in list(ORIGINAL_LIGHT.values()) + list(ORIGINAL_DARK.values()) + ["#000000", "#ff0000", "#00ff7f", "#123456"]:
            rgb = colour.hex_to_rgb(value)
            self.assertEqual(colour.rgb_to_hex(colour.oklab_to_rgb(*colour.rgb_to_oklab(rgb))), value)

    def test_a_colour_outside_srgb_is_pulled_in_keeping_lightness_and_hue(self):
        L, C, h = 0.6, 0.4, 140  # far more chroma than sRGB has at this lightness
        rgb = colour.oklab_to_rgb(*colour.oklch_to_oklab(L, C, h))
        self.assertTrue(all(0 <= c <= 1 for c in rgb))
        L2, C2, h2 = colour.oklab_to_oklch(*colour.rgb_to_oklab(rgb))
        self.assertAlmostEqual(L2, L, delta=0.01)
        self.assertAlmostEqual(h2, h, delta=2)
        self.assertLess(C2, C)

    def test_every_accepted_colour_form(self):
        self.assertEqual(colour.rgb_to_hex(colour.parse("#B01E2E")), "#b01e2e")
        self.assertEqual(colour.rgb_to_hex(colour.parse("oklch(1 0 0)")), "#ffffff")
        self.assertEqual(colour.rgb_to_hex(colour.parse("oklab(0 0 0)")), "#000000")
        self.assertEqual(colour.parse(" oklch(0.5  0.1 200) "), colour.parse("oklch(0.5 0.1 200)"))

    def test_text_that_is_not_a_colour_is_rejected(self):
        for bad in (
            "red",
            "#fff",
            "#12345g",
            "oklch(2 0 0)",
            "oklch(0.5 0.9 10)",
            "oklch(0.5 -0.1 10)",
            "oklch(0.5 0.1)",
            "oklab(0.5 0.9 0)",
            "rgb(1 2 3)",
            "",
            7,
            None,
            ["#ffffff"],
        ):
            self.assertIsNone(colour.parse(bad), bad)

    def test_greys_look_the_same_to_everyone(self):
        for kind in colour.DEFICIENCIES:
            for grey in ((0.5, 0.5, 0.5), (0.1, 0.1, 0.1), (1, 1, 1), (0, 0, 0)):
                simulated = colour.simulate(grey, kind)
                self.assertTrue(all(abs(a - b) < 0.01 for a, b in zip(simulated, grey)), (kind, grey, simulated))

    def test_red_and_green_converge_for_red_green_colour_blindness_only(self):
        red, green = colour.parse("oklch(0.6 0.15 25)"), colour.parse("oklch(0.6 0.15 145)")  # the same lightness
        normal = colour.distance(red, green)
        for kind in ("protan", "deutan"):
            self.assertLess(colour.distance(colour.simulate(red, kind), colour.simulate(green, kind)), normal / 2, kind)
        self.assertGreater(colour.distance(colour.simulate(red, "tritan"), colour.simulate(green, "tritan")), normal / 2)

    def test_the_distance_of_a_colour_from_itself_is_zero(self):
        self.assertEqual(colour.distance((0.2, 0.4, 0.6), (0.2, 0.4, 0.6)), 0.0)


class ShippedPaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.palettes = palettes.load()

    def test_the_default_comes_first_and_the_others_are_the_colour_vision_and_contrast_choices(self):
        self.assertEqual(list(self.palettes)[0], "default")
        self.assertEqual(set(self.palettes), {"default", "high-contrast", "red-green", "red-green-safe", "blue-yellow-safe"})

    def test_every_shipped_palette_passes_its_own_promises(self):
        palettes.validate(self.palettes, LANG_CODE)

    def test_the_default_palette_still_has_the_original_colours(self):
        resolved = palettes.resolve(self.palettes["default"])
        for variant, original in (("light", ORIGINAL_LIGHT), ("dark", ORIGINAL_DARK)):
            ours = hexes(resolved[variant])
            self.assertEqual({role: ours[role] for role in original}, original)  # the eight the site started with
            self.assertIn("tile", ours)

    def test_the_high_contrast_palette_meets_the_stricter_level(self):
        self.assertEqual(self.palettes["high-contrast"]["level"], "AAA")
        for variant, colours in palettes.resolve(self.palettes["high-contrast"]).items():
            for role in palettes.TEXT_ROLES:
                for ground in ("bg", "surface"):
                    self.assertGreaterEqual(colour.contrast(colours[role], colours[ground]), 7.0, (variant, role, ground))

    def test_the_colour_vision_palettes_name_what_they_promise(self):
        self.assertEqual(self.palettes["red-green-safe"]["colour_vision"], ["protan", "deutan"])
        self.assertEqual(self.palettes["blue-yellow-safe"]["colour_vision"], ["tritan"])

    def test_the_check_discriminates_the_default_red_is_not_safe_for_red_green_colour_blindness(self):
        claiming = copy.deepcopy(self.palettes["default"])
        claiming["colour_vision"] = ["protan", "deutan"]
        with self.assertRaises(ContentError) as ctx:
            palettes.validate({"default": claiming}, LANG_CODE)
        self.assertIn("hard to tell", str(ctx.exception))

    def test_the_default_palette_is_not_held_to_the_strict_level(self):
        strict = copy.deepcopy(self.palettes["default"])
        strict["level"] = "AAA"
        with self.assertRaises(ContentError):
            palettes.validate({"default": strict}, LANG_CODE)


class PaletteRejectionTests(unittest.TestCase):
    def setUp(self):
        self.base = palettes.load()["default"]

    def rejects(self, mutate, expect):
        palette = copy.deepcopy(self.base)
        mutate(palette)
        with self.assertRaises(ContentError) as ctx:
            palettes.validate({"default": palette}, LANG_CODE)
        self.assertIn(expect, str(ctx.exception))

    def test_a_missing_colour(self):
        self.rejects(lambda p: p["light"].pop("accent"), "needs exactly the colours")

    def test_an_invented_colour_role(self):
        self.rejects(lambda p: p["dark"].update(shadow="#000000"), "needs exactly the colours")

    def test_notes_must_be_text_when_given(self):
        for bad in ("", "   ", 7, ["x"]):
            self.rejects(lambda p, b=bad: p.update(notes=b), "'notes' must be non-empty text")
        palette = copy.deepcopy(self.base)
        palette["notes"] = "Where these colours came from."
        palettes.validate({"default": palette}, LANG_CODE)

    def test_a_missing_variant(self):
        self.rejects(lambda p: p.pop("dark"), "'dark' needs exactly")

    def test_a_colour_that_is_not_one(self):
        self.rejects(lambda p: p["light"].update(ink="dark slate"), "is not a colour")

    def test_an_unknown_key_is_caught_rather_than_ignored(self):
        self.rejects(lambda p: p.update(**{"colour-vision": ["tritan"]}), "unknown keys")

    def test_an_unknown_level_or_kind_of_colour_blindness(self):
        self.rejects(lambda p: p.update(level="AAAA"), "'level' must be one of")
        self.rejects(lambda p: p.update(colour_vision=["achromat"]), "'colour_vision' must list")

    def test_names_must_be_text_by_language(self):
        self.rejects(lambda p: p.update(names={"en": ""}), "'names' must map")
        self.rejects(lambda p: p.update(names={"EN US": "x"}), "'names' must map")
        self.rejects(lambda p: p.update(names=["x"]), "'names' must map")

    def test_text_without_enough_contrast(self):
        self.rejects(lambda p: p["light"].update(muted="oklch(0.75 0.02 228)"), "muted on bg")
        self.rejects(lambda p: p["dark"].update(accent="oklch(0.35 0.1 20)"), "accent on bg")
        self.rejects(lambda p: p["dark"].update(ink="oklch(0.3 0.01 230)"), "ink on")

    def test_an_icon_that_cannot_be_seen_on_its_tile(self):
        self.rejects(lambda p: p["light"].update(**{"on-tile": "oklch(0.8 0.03 225)"}), "on-tile on tile")
        self.rejects(
            lambda p: p["dark"].update(tile="oklch(0.33 0.03 230)", **{"on-tile": "oklch(0.45 0.03 230)"}), "on-tile on tile"
        )

    def test_the_tile_roles_are_required(self):
        self.rejects(lambda p: p["light"].pop("tile"), "needs exactly the colours")
        self.rejects(lambda p: p["dark"].pop("on-tile"), "needs exactly the colours")

    def test_a_light_variant_that_is_dark_and_the_reverse(self):
        self.rejects(lambda p: p["light"].update(bg="oklch(0.5 0 0)"), "light background")
        self.rejects(lambda p: p["dark"].update(bg="oklch(0.6 0 0)"), "dark background")

    def test_a_palette_file_name_must_be_a_safe_identifier(self):
        for bad in ("Upper", "has space", "-lead", "9lives", 'q"uote'):
            with self.assertRaises(ContentError, msg=bad):
                palettes.validate({"default": self.base, bad: self.base}, LANG_CODE)

    def test_there_must_be_a_default(self):
        with self.assertRaises(ContentError):
            palettes.validate({"other": self.base}, LANG_CODE)


class KeyColourTests(unittest.TestCase):
    def test_every_shipped_palette_has_three_key_colours_in_both_variants(self):
        for pid, palette in palettes.load().items():
            for variant in ("light", "dark"):
                for role in palettes.KEYS_OF_WORDS:
                    self.assertIn(role, palette[variant], f"{pid} {variant}")
                    self.assertTrue(palette[variant][role].startswith("oklch("), f"{pid} {variant} {role}")

    def test_two_key_colours_that_are_the_same_are_rejected(self):
        palette = copy.deepcopy(palettes.load()["default"])
        palette["light"]["key-2"] = palette["light"]["key-1"]
        with self.assertRaises(ContentError) as ctx:
            palettes.validate({"default": palette}, LANG_CODE)
        self.assertIn("key-1 is hard to tell from key-2", str(ctx.exception))

    def test_a_key_colour_too_pale_for_the_level_is_rejected(self):
        palette = copy.deepcopy(palettes.load()["default"])
        palette["light"]["key-3"] = "oklch(0.8 0.14 305)"
        with self.assertRaises(ContentError) as ctx:
            palettes.validate({"default": palette}, LANG_CODE)
        self.assertIn("key-3", str(ctx.exception))

    def test_the_css_carries_the_key_colours(self):
        css = palettes.css(palettes.load(), ["default"])
        for role in palettes.KEYS_OF_WORDS:
            self.assertIn(f"--{role}:", css)


class PaletteCssTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all = palettes.load()
        cls.css = palettes.css(cls.all, list(cls.all))

    def test_the_default_is_the_baseline_with_no_attribute(self):
        self.assertIn(":root{--bg:#f1f4f5;", self.css)
        self.assertIn('@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#11191e;', self.css)
        self.assertIn(':root[data-theme="dark"]{--bg:#11191e;', self.css)

    def test_each_other_palette_has_a_light_a_system_dark_and_a_chosen_dark_rule(self):
        for pid in self.all:
            if pid == "default":
                continue
            self.assertIn(f':root[data-palette="{pid}"]{{--bg:', self.css)
            self.assertIn(f'(prefers-color-scheme:dark){{:root[data-palette="{pid}"]:not([data-theme="light"]){{--bg:', self.css)
            self.assertIn(f':root[data-palette="{pid}"][data-theme="dark"]{{--bg:', self.css)

    def test_every_rule_sets_every_role_and_the_colour_scheme(self):
        rules = [line for line in self.css.splitlines() if "--bg:" in line]
        self.assertEqual(len(rules), 3 * len(self.all))
        for rule in rules:
            for role in palettes.ROLES:
                self.assertIn(f"--{role}:#", rule)
            self.assertRegex(rule, r"color-scheme:(light|dark)")

    def test_only_the_offered_palettes_are_written(self):
        css = palettes.css(self.all, ["default", "high-contrast"])
        self.assertIn('data-palette="high-contrast"', css)
        self.assertNotIn("red-green-safe", css)

    def test_light_rules_say_light_and_dark_rules_say_dark(self):
        for line in self.css.splitlines():
            if ".preview" in line:
                self.assertNotRegex(line, r"(?<!prefers-)color-scheme:")  # a preview paints a picture, not the page
            elif line.startswith(":root") and "[data-theme" not in line:
                self.assertTrue(line.endswith("color-scheme:light}"), line)
            elif "[data-theme=" in line:
                self.assertTrue(line.rstrip("}").endswith("color-scheme:dark"), line)

    def test_every_palette_gets_a_preview_in_light_and_both_dark_cases(self):
        for pid in self.all:
            pick = f'.preview[data-palette="{pid}"]'
            lines = [line for line in self.css.splitlines() if pick in line]
            self.assertEqual(len(lines), 3, pid)
            self.assertTrue(all("--pv-bg:" in line for line in lines), pid)
            self.assertIn(':not([data-theme="light"])', lines[1])
            self.assertIn('[data-theme="dark"]', lines[2])

    def test_the_preview_colours_are_the_palettes_own_not_the_pages(self):
        resolved = palettes.resolve(self.all["high-contrast"])
        line = next(
            l
            for l in self.css.splitlines()
            if '.preview[data-palette="high-contrast"]' in l and "@media" not in l and "data-theme" not in l
        )
        self.assertIn("--pv-ink:" + colour.rgb_to_hex(resolved["light"]["ink"]), line)

    def test_the_output_is_stable(self):
        self.assertEqual(self.css, palettes.css(palettes.load(), list(self.all)))

    def test_the_css_needs_no_third_party_request(self):
        self.assertNotIn("http", self.css)
        self.assertNotIn("@import", self.css)


class LoadingTests(unittest.TestCase):
    def test_a_project_palette_is_added_after_the_framework_ones(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "sepia.json").write_text(json.dumps(palettes.load()["default"]), encoding="utf-8")
            loaded = palettes.load(tmp)
        self.assertEqual(list(loaded)[0], "default")
        self.assertEqual(list(loaded)[-1], "sepia")

    def test_a_project_palette_with_a_framework_id_replaces_it(self):
        import tempfile

        mine = copy.deepcopy(palettes.load()["default"])
        mine["light"]["accent"] = "oklch(0.45 0.15 150)"
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "default.json").write_text(json.dumps(mine), encoding="utf-8")
            loaded = palettes.load(tmp)
        self.assertEqual(loaded["default"]["light"]["accent"], "oklch(0.45 0.15 150)")
        self.assertEqual(list(loaded)[0], "default")

    def test_a_project_with_no_palettes_folder_gets_the_framework_ones(self):
        self.assertEqual(set(palettes.load("no/such/folder")), set(palettes.load()))


if __name__ == "__main__":
    unittest.main()
