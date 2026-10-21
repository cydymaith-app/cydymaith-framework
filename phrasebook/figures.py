"""Figures: drawings built from a page's concepts, so they translate with the page.

A page skeleton may name a figure ("figure": "compass-rose"). The figure needs certain concept ids on that page;
the build checks they are there. Any project can use a figure; a new kind of figure is new code here.
"""

import html
import math

e = html.escape

FIGURE_CONCEPTS = {
    "compass-rose": ["north", "south", "east", "west", "north-east", "north-west", "south-east", "south-west"],
}


def rose_svg(site, slug):
    """Compass rose labelled from the concepts north, south, ... in the site's pair of languages.

    The geometry is a map, so east stays on the right even in a right-to-left interface.
    """
    ids = FIGURE_CONCEPTS["compass-rose"]
    f = {i: site.text(site.frm, slug, i) for i in ids}
    t = {i: site.text(site.to, slug, i) for i in ids}
    if not all(f.values()) or not all(t.values()):
        return ""
    cx = oy = 200
    ring, r_card, r_inter, r_in = 104, 92, 56, 22

    def pt(deg, r):
        a = math.radians(deg)
        return cx + r * math.sin(a), oy - r * math.cos(a)

    verts = []
    for k in range(16):
        r = r_card if k % 4 == 0 else (r_inter if k % 4 == 2 else r_in)
        verts.append(pt(k * 22.5, r))
    fmt = lambda pts: " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    star = fmt(verts)
    needle = fmt([verts[0], verts[1], (cx, oy), verts[15]])

    ticks = []
    for k in range(16):
        length = 12 if k % 4 == 0 else (8 if k % 2 == 0 else 5)
        x1, y1 = pt(k * 22.5, ring)
        x2, y2 = pt(k * 22.5, ring + length)
        ticks.append(f'<line class="tick" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')

    def label(x, y, text, cls, anchor):
        return f'<text class="{cls}" x="{x}" y="{y}" text-anchor="{anchor}">{e(text)}</text>'

    def stacked(x, y, text, anchor):
        """Compound points written with a hyphen break after it; other texts stay on one line."""
        head, sep, tail = text.partition("-")
        if not sep:
            return [label(x, y + 9, text, "w2", anchor)]
        return [label(x, y, head + sep, "w2", anchor), label(x, y + 18, tail, "w2", anchor)]

    labels = [
        label(200, 58, t["north"], "w2", "middle"),
        label(200, 75, f["north"], "w1", "middle"),
        label(200, 338, t["south"], "w2", "middle"),
        label(200, 355, f["south"], "w1", "middle"),
        label(326, 205, t["east"], "w2", "start"),
        label(326, 222, f["east"], "w1", "start"),
        label(74, 205, t["west"], "w2", "end"),
        label(74, 222, f["west"], "w1", "end"),
        *stacked(288, 100, t["north-east"], "start"),
        label(288, 135, f["north-east"], "w1", "start"),
        *stacked(112, 100, t["north-west"], "end"),
        label(112, 135, f["north-west"], "w1", "end"),
        *stacked(288, 276, t["south-east"], "start"),
        label(288, 311, f["south-east"], "w1", "start"),
        *stacked(112, 276, t["south-west"], "end"),
        label(112, 311, f["south-west"], "w1", "end"),
    ]
    items = [site.plain("rose_item", first=f[i], second=t[i]) for i in ids]
    desc = site.plain("rose_desc", list=site.messages.join(site.interface, items))
    title = site.plain("rose_title", first=site.language_name(site.frm), second=site.language_name(site.to))
    return (
        '<svg class="rose" viewBox="-20 34 440 330" role="img" aria-labelledby="rose-t rose-d" xmlns="http://www.w3.org/2000/svg">'
        f'<title id="rose-t">{e(title)}</title>'
        f'<desc id="rose-d">{e(desc)}</desc>'
        f'<circle class="ring" cx="{cx}" cy="{oy}" r="{ring}"/>'
        + "".join(ticks)
        + f'<polygon class="star" points="{star}"/>'
        + f'<polygon class="needle" points="{needle}"/>'
        + "".join(labels)
        + "</svg>"
    )


FIGURES = {"compass-rose": rose_svg}
