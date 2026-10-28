"""Colour palettes: how the interface is coloured, in a light and a dark variant each.

A palette is a JSON file, phrasebook/palettes/<id>.json for the framework's own and <project>/palettes/<id>.json
for a project's. A project file with the id of a framework palette replaces it, so a project can recolour a
framework palette or add choices of its own. An edition may make any palette its default ("default_palette").

    {
      "names": {"en": "High contrast"},       optional; the interface text for a project's own palette
      "notes": "Where the colours came from",  optional free text: the source, what was derived, and why
      "extends": "other-id",                   optional: start from that palette (the framework's or the project's) and list
                                               only the colours that differ; names, notes, level and colour_vision are not inherited
      "level": "AA",                           "AA" (default) or "AAA": how much contrast the text must have
      "colour_vision": ["protan", "deutan"],   optional: kinds of colour blindness the palette promises to survive
      "light": {"bg": "oklch(0.97 0.004 220)", "surface": "#ffffff", ...},
      "dark":  {...}
    }

A colour is "oklch(L C h)", "oklab(L a b)" or "#rrggbb". Every role in ROLES is required in both variants, once the
palette has been filled in from the one it extends. The checks run on the finished palette.
The build checks the promises: text contrast for the level, light that is light and dark that is dark, and for
each kind of colour blindness named, that the accent still reads against the background and stays clearly different
from the text colours after simulating that vision (colour.py). A palette that breaks its promise fails the build.
These checks are a safeguard, not a substitute for asking people who see colour differently.

The page picks a palette with data-palette="<id>" on <html> (absent for the edition's default) and a variant with
data-theme="light|dark", or follows the system's light/dark setting when data-theme is absent. See css() for the selectors.
"""

import json
import pathlib
import re

from . import colour
from .errors import ContentError

ENGINE_PALETTES = pathlib.Path(__file__).resolve().parent / "palettes"
ROLES = (
    "bg",
    "surface",
    "ink",
    "muted",
    "rule",
    "rule-strong",
    "accent",
    "star",
    "tile",
    "on-tile",
    "header",
    "on-header",
    "key-1",
    "key-2",
    "key-3",
)
KEYS_OF_WORDS = ("key-1", "key-2", "key-3")  # colours for the matching key words of a row (see site.py, keyed)
DEFAULT = "default"
# The framework's palettes in the order they are offered: the neutral one, the colour schemes, then the accessible ones.
ENGINE_ORDER = (
    DEFAULT,
    "blue-white-red",
    "green-white-red",
    "green-white-orange",
    "red-yellow",
    "black-red-gold",
    "sepia",
    "red-green-safe",
    "blue-yellow-safe",
    "monochrome",
    "high-contrast",
)
ID = re.compile(r"^[a-z][a-z0-9-]*$")
KEYS = {"names", "notes", "extends", "level", "colour_vision", "light", "dark"}
LEVELS = {"AA": {"text": 4.5, "boundary": None, "graphic": 3.0}, "AAA": {"text": 7.0, "boundary": 3.0, "graphic": 4.5}}
TEXT_ROLES = ("ink", "muted", "accent") + KEYS_OF_WORDS  # drawn as text on bg and on surface
LIGHT_MIN, DARK_MAX = 0.70, 0.35  # OKLab lightness of the background that makes a variant honestly light or dark
SEPARATION = 0.12  # OKLab distance the accent must keep from the text colours under simulated colour blindness, and the
# key-word colours from each other and from the ink, in every palette and under each kind of colour blindness it promises


def load(project_dir=None, engine_dir=ENGINE_PALETTES):
    """{id: palette}: the project's own palettes first, then the framework's in ENGINE_ORDER. A project file with a
    framework id replaces that palette and keeps its place among the framework's. Palettes that "extend" another are
    filled in from it."""
    found = {}
    for folder in (engine_dir, pathlib.Path(project_dir) if project_dir else None):
        if folder and pathlib.Path(folder).is_dir():
            for path in sorted(pathlib.Path(folder).glob("*.json")):
                found[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    engine = {path.stem for path in pathlib.Path(engine_dir).glob("*.json")} if pathlib.Path(engine_dir).is_dir() else set()
    named = [pid for pid in ENGINE_ORDER if pid in engine]
    first = [pid for pid in found if pid not in engine]
    last = named + sorted(engine - set(named))
    return extend({pid: found[pid] for pid in first + last})


def extend(found):
    """Fill in each palette that has "extends": the parent's colours, with the palette's own listed colours on top, for
    light and dark each. Only the colours are inherited: names, notes, level and colour_vision are the palette's own."""
    done = {}

    def build(pid, trail):
        if pid in done:
            return done[pid]
        palette = found[pid]
        parent = palette.get("extends") if isinstance(palette, dict) else None
        if parent is None:
            done[pid] = palette
            return palette
        where = f"palettes/{pid}.json"
        if not isinstance(parent, str) or parent not in found:
            raise ContentError(f"{where}: 'extends' must name another palette; available: {', '.join(found)}")
        if parent in trail or parent == pid:
            raise ContentError(f"{where}: 'extends' goes round in a circle: {' -> '.join([*trail, pid, parent])}")
        base = build(parent, [*trail, pid])
        out = dict(palette)
        for variant in ("light", "dark"):
            own = palette.get(variant, {})
            if not isinstance(own, dict):
                raise ContentError(f"{where}: '{variant}' must list colours by role")
            out[variant] = {**base.get(variant, {}), **own}
        done[pid] = out
        return out

    return {pid: build(pid, []) for pid in found}


def resolve(palette):
    """{'light': {role: (r, g, b)}, 'dark': {...}} in sRGB. Assumes the palette has been validated."""
    return {variant: {role: colour.parse(palette[variant][role]) for role in ROLES} for variant in ("light", "dark")}


def validate(palettes, lang_code):
    """Check every palette. Raises ContentError naming the file at fault. `lang_code` is the language tag pattern."""
    if DEFAULT not in palettes:
        raise ContentError(f"palettes: there must be a palette with the id {DEFAULT!r}")
    for pid, palette in palettes.items():
        where = f"palettes/{pid}.json"
        if not ID.match(pid):
            raise ContentError(f"{where}: the file name must be lower case letters, digits and hyphens, starting with a letter")
        if not isinstance(palette, dict) or set(palette) - KEYS:
            raise ContentError(
                f"{where}: unknown keys {sorted(set(palette) - KEYS) if isinstance(palette, dict) else palette!r}; "
                f"allowed: {', '.join(sorted(KEYS))}"
            )
        names = palette.get("names", {})
        if not isinstance(names, dict) or any(
            not lang_code.match(k) or not isinstance(v, str) or not v for k, v in names.items()
        ):
            raise ContentError(f"{where}: 'names' must map language codes to the palette's name in that language")
        if "notes" in palette and (not isinstance(palette["notes"], str) or not palette["notes"].strip()):
            raise ContentError(f"{where}: 'notes' must be non-empty text")
        level = palette.get("level", "AA")
        if level not in LEVELS:
            raise ContentError(f"{where}: 'level' must be one of {', '.join(LEVELS)}")
        claims = palette.get("colour_vision", [])
        if not isinstance(claims, list) or any(k not in colour.DEFICIENCIES for k in claims):
            raise ContentError(f"{where}: 'colour_vision' must list kinds from {', '.join(colour.DEFICIENCIES)}")
        for variant in ("light", "dark"):
            roles = palette.get(variant)
            if not isinstance(roles, dict) or set(roles) != set(ROLES):
                raise ContentError(f"{where}: '{variant}' needs exactly the colours {', '.join(ROLES)}")
            for role, text in roles.items():
                if colour.parse(text) is None:
                    raise ContentError(
                        f"{where}: {variant} {role} is not a colour ('#rrggbb', 'oklch(L C h)' or 'oklab(L a b)'): {text!r}"
                    )
        resolved = resolve(palette)
        check_scheme(where, resolved)
        for variant, colours in resolved.items():
            check_contrast(f"{where} {variant}", colours, level)
            check_key_colours(f"{where} {variant}", colours)
            for kind in claims:
                check_colour_vision(f"{where} {variant}", colours, level, kind)


def check_scheme(where, resolved):
    light = colour.rgb_to_oklab(resolved["light"]["bg"])[0]
    dark = colour.rgb_to_oklab(resolved["dark"]["bg"])[0]
    if light < LIGHT_MIN:
        raise ContentError(f"{where}: the light background has lightness {light:.2f}; it needs at least {LIGHT_MIN}")
    if dark > DARK_MAX:
        raise ContentError(f"{where}: the dark background has lightness {dark:.2f}; it needs at most {DARK_MAX}")


def check_contrast(where, colours, level, kind=None):
    needed = LEVELS[level]["text"]
    seen = f" as seen with {kind}" if kind else ""
    for role in TEXT_ROLES:
        for ground in ("bg", "surface"):
            ratio = colour.contrast(colours[role], colours[ground])
            if ratio < needed:
                raise ContentError(
                    f"{where}: {role} on {ground}{seen} has contrast {ratio:.2f}:1; level {level} needs {needed}:1"
                )
    graphic = LEVELS[level]["graphic"]  # the icon drawn on a tile is a graphic, not text (WCAG 1.4.11)
    if colour.contrast(colours["on-tile"], colours["tile"]) < graphic:
        ratio = colour.contrast(colours["on-tile"], colours["tile"])
        raise ContentError(f"{where}: on-tile on tile{seen} has contrast {ratio:.2f}:1; level {level} needs {graphic}:1")
    boundary = LEVELS[level]["boundary"]
    if boundary and colour.contrast(colours["rule-strong"], colours["bg"]) < boundary:
        ratio = colour.contrast(colours["rule-strong"], colours["bg"])
        raise ContentError(f"{where}: rule-strong on bg{seen} has contrast {ratio:.2f}:1; level {level} needs {boundary}:1")


def check_colour_vision(where, colours, level, kind):
    seen = {role: colour.simulate(rgb, kind) for role, rgb in colours.items()}
    check_contrast(where, seen, level, kind)
    check_key_colours(where, seen, kind)
    for other in ("ink", "muted"):
        gap = colour.distance(seen["accent"], seen[other])
        if gap < SEPARATION:
            raise ContentError(
                f"{where}: with {kind} vision the accent is hard to tell from {other} "
                f"(distance {gap:.3f}, needs {SEPARATION}); change its lightness or chroma"
            )


def check_key_colours(where, colours, kind=None):
    """The three key-word colours must be told apart from each other and from the ink (as seen with `kind`, if given)."""
    seen = f" as seen with {kind}" if kind else ""
    for first, second in [(a, b) for i, a in enumerate(KEYS_OF_WORDS) for b in KEYS_OF_WORDS[i + 1 :]] + [
        (k, "ink") for k in KEYS_OF_WORDS
    ]:
        gap = colour.distance(colours[first], colours[second])
        if gap < SEPARATION:
            raise ContentError(
                f"{where}: {first} is hard to tell from {second}{seen} (distance {gap:.3f}, needs {SEPARATION}); "
                f"change its lightness or hue"
            )


ACCESS_LEVELS = ("standard", "safe", "high")  # the settings page offers one list of colour schemes per level


def access_level(palette):
    """The accessibility level a palette belongs to: level AAA is "high" (high contrast); otherwise a palette that
    promises colour vision is "safe" (safe colours); anything else is "standard"."""
    if palette.get("level", "AA") == "AAA":
        return "high"
    return "safe" if palette.get("colour_vision") else "standard"


def keys_by_line(palette):
    """Whether a palette marks key words by underline only, never by colour: at the high-contrast level, where the key colours
    are least distinct, and in a palette that promises to work with no colour vision ("achromat"), where they differ only in
    lightness. The build's check passes those greys, but in use the darkest key is hard to tell from the text."""
    return access_level(palette) == "high" or "achromat" in palette.get("colour_vision", [])


def tokens(colours, prefix="--"):
    return ";".join(f"{prefix}{role}:{colour.rgb_to_hex(colours[role])}" for role in ROLES)


def css(palettes, ids, baseline=DEFAULT):
    """The stylesheet for the offered palettes. The edition's default palette (`baseline`) is the page's baseline, with no attribute.

    Each palette gets three rules (and three more for its preview, see below), all of which win over the baseline in the right cases:
      light:         the variant when nothing says dark
      system dark:   the dark variant when the system prefers dark and the visitor has not chosen light
      chosen dark:   the dark variant when the visitor chose dark
    A palette at the high-contrast level also gets rules that draw key words as underlines, not colour.
    """
    out = ["/* Generated by the phrasebook builder from the palettes. Do not edit. */"]
    for pid in ids:
        resolved = resolve(palettes[pid])
        mark = "" if pid == baseline else f'[data-palette="{pid}"]'
        out.append(f":root{mark}{{{tokens(resolved['light'])};color-scheme:light}}")
        out.append(
            f'@media (prefers-color-scheme:dark){{:root{mark}:not([data-theme="light"]){{{tokens(resolved["dark"])};color-scheme:dark}}}}'
        )
        out.append(f':root{mark}[data-theme="dark"]{{{tokens(resolved["dark"])};color-scheme:dark}}')
    # Where key words are drawn by line (keys_by_line) they are underlined, never coloured, whatever was chosen before the
    # palette changed (the settings page hides Colour there and corrects the choice, but only when it is open).
    for pid in ids:
        if keys_by_line(palettes[pid]):
            mark = "" if pid == baseline else f'[data-palette="{pid}"]'
            key = f':root{mark}:not([data-keys="off"]) .key'
            out.append(
                f"{key}{{color:inherit;text-decoration-line:underline;text-decoration-thickness:.1em;text-underline-offset:.2em}}"
            )
            for n, style in enumerate(("solid", "dotted", "wavy"), 1):
                out.append(f'{key}[data-k="{n}"]{{text-decoration-style:{style}}}')
    # Each palette's own colours for the small picture on the settings page, whatever palette the page is in now.
    for pid in ids:
        resolved = resolve(palettes[pid])
        pick = f'.preview[data-palette="{pid}"]'
        out.append(f":root {pick}{{{tokens(resolved['light'], '--pv-')}}}")
        out.append(
            f'@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]) {pick}{{{tokens(resolved["dark"], "--pv-")}}}}}'
        )
        out.append(f':root[data-theme="dark"] {pick}{{{tokens(resolved["dark"], "--pv-")}}}')
    return "\n".join(out) + "\n"
