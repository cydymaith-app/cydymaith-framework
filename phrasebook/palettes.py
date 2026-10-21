"""Colour palettes: how the interface is coloured, in a light and a dark variant each.

A palette is a JSON file, phrasebook/palettes/<id>.json for the framework's own and <project>/palettes/<id>.json
for a project's. A project file with the id of a framework palette replaces it, so a project can recolour the
default or add choices of its own.

    {
      "names": {"en": "High contrast"},       optional; the interface text for a project's own palette
      "notes": "Where the colours came from",  optional free text: the source, what was derived, and why
      "level": "AA",                           "AA" (default) or "AAA": how much contrast the text must have
      "colour_vision": ["protan", "deutan"],   optional: kinds of colour blindness the palette promises to survive
      "light": {"bg": "oklch(0.97 0.004 220)", "surface": "#ffffff", ...},
      "dark":  {...}
    }

A colour is "oklch(L C h)", "oklab(L a b)" or "#rrggbb". Every role in ROLES is required in both variants.
The build checks the promises: text contrast for the level, light that is light and dark that is dark, and for
each kind of colour blindness named, that the accent still reads against the background and stays clearly different
from the text colours after simulating that vision (colour.py). A palette that breaks its promise fails the build.
These checks are a safeguard, not a substitute for asking people who see colour differently.

The page picks a palette with data-palette="<id>" on <html> and a variant with data-theme="light|dark", or follows
the system's light/dark setting when data-theme is absent. See css() for the selectors.
"""

import json
import pathlib
import re

from . import colour
from .errors import ContentError

ENGINE_PALETTES = pathlib.Path(__file__).resolve().parent / "palettes"
ROLES = ("bg", "surface", "ink", "muted", "rule", "rule-strong", "accent", "star", "tile", "on-tile", "header", "on-header")
DEFAULT = "default"
ID = re.compile(r"^[a-z][a-z0-9-]*$")
KEYS = {"names", "notes", "level", "colour_vision", "light", "dark"}
LEVELS = {"AA": {"text": 4.5, "boundary": None, "graphic": 3.0}, "AAA": {"text": 7.0, "boundary": 3.0, "graphic": 4.5}}
TEXT_ROLES = ("ink", "muted", "accent")  # drawn as text on bg and on surface
LIGHT_MIN, DARK_MAX = 0.70, 0.35  # OKLab lightness of the background that makes a variant honestly light or dark
SEPARATION = 0.12  # OKLab distance the accent must keep from the text colours under simulated colour blindness


def load(project_dir=None, engine_dir=ENGINE_PALETTES):
    """{id: palette}: the framework's palettes (default first), then the project's, which may replace them."""
    found = {}
    for folder in (engine_dir, pathlib.Path(project_dir) if project_dir else None):
        if folder and pathlib.Path(folder).is_dir():
            for path in sorted(pathlib.Path(folder).glob("*.json")):
                found[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    ordered = {DEFAULT: found.pop(DEFAULT)} if DEFAULT in found else {}
    ordered.update(found)
    return ordered


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
    for other in ("ink", "muted"):
        gap = colour.distance(seen["accent"], seen[other])
        if gap < SEPARATION:
            raise ContentError(
                f"{where}: with {kind} vision the accent is hard to tell from {other} "
                f"(distance {gap:.3f}, needs {SEPARATION}); change its lightness or chroma"
            )


def tokens(colours):
    return ";".join(f"--{role}:{colour.rgb_to_hex(colours[role])}" for role in ROLES)


def css(palettes, ids):
    """The stylesheet for the offered palettes. The default palette is the page's baseline, with no attribute.

    Each palette gets three rules, all of which win over the baseline in the right cases:
      light:         the variant when nothing says dark
      system dark:   the dark variant when the system prefers dark and the visitor has not chosen light
      chosen dark:   the dark variant when the visitor chose dark
    """
    out = ["/* Generated by the phrasebook builder from the palettes. Do not edit. */"]
    for pid in ids:
        resolved = resolve(palettes[pid])
        mark = "" if pid == DEFAULT else f'[data-palette="{pid}"]'
        out.append(f":root{mark}{{{tokens(resolved['light'])};color-scheme:light}}")
        out.append(
            f'@media (prefers-color-scheme:dark){{:root{mark}:not([data-theme="light"]){{{tokens(resolved["dark"])};color-scheme:dark}}}}'
        )
        out.append(f':root{mark}[data-theme="dark"]{{{tokens(resolved["dark"])};color-scheme:dark}}')
    return "\n".join(out) + "\n"
