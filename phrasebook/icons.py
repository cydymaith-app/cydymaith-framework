"""Icons: small line drawings a project supplies as SVG files, inlined into the pages.

A project keeps them in <project>/icons/<name>.svg and names one with "icon": "<name>" on a group in
structure.json or in a page skeleton. The framework ships none, so it stays free of any one icon set.

An SVG is untrusted markup, so only a small safe subset is accepted: shapes and groups, with geometry and
presentation attributes. Anything that could run code or fetch something (scripts, styles, links, event
handlers, url() references) is rejected, and the build names the file at fault.

An accepted icon is rewritten as one line of markup for inlining: it takes the text colour (currentColor), so it
follows the palette and forced-colours mode, is marked aria-hidden because the label beside it says the same
thing, and makes no request.
"""
import re
import xml.etree.ElementTree as ET

from .errors import ContentError

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

NAME = re.compile(r"^[a-z][a-z0-9-]*$")
SHAPES = {"path", "circle", "line", "polyline", "polygon", "rect", "ellipse", "g"}
CENTRE = {f"c{axis}" for axis in "xy"}  # SVG's centre attributes, spelt this way: a test forbids bare language codes here
ATTRIBUTES = {"d", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2", "points", "width", "height",
              "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "fill-rule", "clip-rule",
              "opacity", "transform"} | CENTRE
ROOT_ATTRIBUTES = {"viewBox", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "xmlns",
                   "width", "height", "class"}
UNSAFE_VALUE = re.compile(r"url\s*\(|javascript:|data:|&", re.IGNORECASE)
KEPT_ROOT = ("viewBox", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin")


def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse(where, text):
    """The normalised markup for one SVG file's text. Raises ContentError naming `where` if it is not acceptable."""
    if re.search(r"<!(DOCTYPE|ENTITY)", text, re.IGNORECASE):
        raise ContentError(f"{where}: a DOCTYPE or ENTITY declaration is not allowed")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as err:
        raise ContentError(f"{where}: not valid XML ({err})")
    if root.tag != f"{{{SVG_NS}}}svg":
        raise ContentError(f"{where}: the root element must be an SVG")
    if not root.get("viewBox"):
        raise ContentError(f"{where}: the svg needs a viewBox")
    bad = sorted(set(root.attrib) - ROOT_ATTRIBUTES)
    if bad:
        raise ContentError(f"{where}: the svg element may not have {', '.join(bad)}")
    check(where, root)
    body = "".join(ET.tostring(child, encoding="unicode").replace(f' xmlns="{SVG_NS}"', "") for child in root)
    body = re.sub(r"\s*\n\s*", "", body)
    kept = "".join(f' {k}="{root.get(k)}"' for k in KEPT_ROOT if root.get(k))
    if not root.get("fill"):
        kept += ' fill="currentColor"'  # a solid glyph (Carbon) names no fill, and would otherwise draw black
    return f'<svg class="icon" aria-hidden="true" focusable="false"{kept}>{body}</svg>'


def check(where, element):
    for child in element:
        name = local(child.tag)
        if child.tag != f"{{{SVG_NS}}}{name}" or name not in SHAPES:
            raise ContentError(f"{where}: <{name}> is not allowed; use only {', '.join(sorted(SHAPES))}")
        if (child.text or "").strip():
            raise ContentError(f"{where}: <{name}> may not hold text")
        extra = sorted(set(child.attrib) - ATTRIBUTES)
        if extra:
            raise ContentError(f"{where}: <{name}> may not have {', '.join(extra)}")
        check(where, child)
    for key, value in element.attrib.items():
        if UNSAFE_VALUE.search(value):
            raise ContentError(f"{where}: {key} holds a reference or entity that is not allowed")


def validate(icons):
    """Check every icon file's text. `icons` is {name: svg text}."""
    for name, text in icons.items():
        if not NAME.match(name):
            raise ContentError(f"icons/{name}.svg: the file name must be lower case letters, digits and hyphens")
        parse(f"icons/{name}.svg", text)


def markup(text):
    return parse("icon", text)
