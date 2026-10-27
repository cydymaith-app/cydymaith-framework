"""Renders one edition of a project, for one pair of languages, into HTML.

Roles, not languages: the first language of the pair ("l1", the left column in a left-to-right interface)
and the second ("l2"). Nothing here knows what the languages are. Every word the framework shows itself
comes from messages.py; every word of the phrasebook comes from the language packs.

Language and direction: text in a language other than the one around it carries lang="..." and, when the
writing direction differs, dir="...". The document itself carries the interface language and direction.
"""

import datetime
import html
import json
import pathlib
import re
import unicodedata

from . import colour, grading, icons, keys as keywords, palettes
from .figures import FIGURE_CONCEPTS, FIGURES
from .content import LICENCES, STORAGE_NAME, TOPIC_PREFIX
from .help import PAGE_PREFIX as HELP_PREFIX, Book
from .messages import Messages

UI_ICONS = pathlib.Path(__file__).resolve().parent / "ui-icons"  # the framework's own chrome icons, apart from any project's

e = html.escape
MARK = re.compile(r"\{\{(.+?)\}\}")


class Site:
    """Renders one edition for one pair of languages: `frm` is shown first, `to` second."""

    def __init__(self, raw, edition, pair=None, messages=None, built=None, help_book=None):
        self.raw = raw
        self.built = built  # when the site was built (an aware datetime), shown at the foot of the About page; None shows nothing
        self.edition = edition
        self.name = edition["name"]
        self.langs = edition["languages"]
        self.interface = edition["interface"]
        self.frm, self.to = pair or edition["default_pair"]
        self.skel = raw["pages"]
        self.packs = raw["packs"]
        self.levels = grading.levels(grading.grade(raw, edition))  # how demanding each group, page and section is
        self.messages = messages or Messages(raw["packs"])
        self.book = help_book or Book.load(raw["packs"])  # the help book: its chapters and the words (see help.py)
        self.palettes = raw["palettes"]
        self.default_palette = edition.get("default_palette", palettes.DEFAULT)
        self.palette_ids = edition.get("palettes") or [self.default_palette] + [
            pid for pid in self.palettes if pid != self.default_palette
        ]
        # Only pages with at least one row available in both languages are published for this pair.
        self.slugs = [s for g in raw["structure"]["groups"] for s in g["pages"] if self.count_entries(s)]
        self.icons = {name: icons.markup(text) for name, text in raw["icons"].items()}
        self.ui_icons = {f.stem: icons.markup(f.read_text(encoding="utf-8")) for f in sorted(UI_ICONS.glob("*.svg"))}
        self.groups = [
            {
                "id": g["id"],
                "icon": g.get("icon"),
                "pages": [s for s in g["pages"] if s in self.slugs],
                "links": [s for s in g.get("links", []) if s in self.slugs],
                "layout": g.get("layout", "tiles"),
            }
            for g in raw["structure"]["groups"]
        ]
        self.groups = [g for g in self.groups if g["pages"]]
        # A page of a one-page group has no file of its own: it is an accordion on the group's page (see one_page).
        self.homes = {s: g["id"] for g in self.groups if g["layout"] == "one-page" for s in g["pages"]}

    # -- lookups

    def meta(self, code):
        return self.packs[code]["meta"]

    def endonym(self, code):
        return self.meta(code)["ui"]["endonym"]

    def language_name(self, code):
        """The language's name written in the interface language when the pack says it, else its English name."""
        meta = self.meta(code)
        return meta.get("names", {}).get(self.interface) or meta["name"]

    def pack_page(self, code, slug):
        return self.packs[code]["pages"].get(slug, {})

    def pack_section(self, code, slug, sid):
        return self.pack_page(code, slug).get("sections", {}).get(sid, {})

    def concept(self, code, slug, sid, cid):
        return self.pack_section(code, slug, sid).get("concepts", {}).get(cid)

    def text(self, code, slug, cid):
        """The text of a concept anywhere on the page, or None."""
        for s in self.skel[slug]["sections"]:
            if cid in s["concepts"]:
                c = self.concept(code, slug, s["id"], cid)
                return self.forms_of(c)[0]["text"] if c else None
        return None

    def title(self, code, slug):
        return self.pack_page(code, slug).get("title")

    # -- interface messages

    def plain(self, key, n=None, **params):
        """A message in the interface language as plain text (to be escaped by the caller)."""
        return self.messages.format(self.interface, key, n=n, **params)[0]

    def h(self, key, n=None, **html_params):
        """A message in the interface language as HTML; params are HTML already. Marked if it fell back to another language."""
        text, lang = self.messages.format(self.interface, key, n=n, html_mode=True, **html_params)
        return self.wrap(lang, text)

    def ui_text(self, code, key):
        """An interface word in the language `code`: (text, language it is actually written in)."""
        return self.messages.format(code, key)

    def ui_html(self, code, key):
        text, lang = self.ui_text(code, key)
        return self.inline(lang, text)

    def ui_span(self, cls, code, key):
        text, lang = self.ui_text(code, key)
        return f'<span class="{cls}"{self.la(lang)}>{e(text)}</span>'

    # -- language and direction

    def dir_of(self, code):
        pack = self.packs.get(code)
        return pack["meta"].get("dir", "ltr") if pack else "ltr"

    def la(self, code, ctx=None):
        """lang and dir attributes for text in `code` that sits inside text in `ctx` (default: the interface language)."""
        ctx = ctx or self.interface
        a = f' lang="{e(code)}"' if code != ctx else ""
        if self.dir_of(code) != self.dir_of(ctx):
            a += f' dir="{self.dir_of(code)}"'
        return a

    def wrap(self, code, html_text, ctx=None):
        a = self.la(code, ctx)
        return f"<span{a}>{html_text}</span>" if a else html_text

    def inline(self, code, text, ctx=None):
        return self.wrap(code, e(text), ctx)

    def commentary_lang(self, code):
        """The language a pack's commentary (notes, intros, boxes) is written in; the interface language unless stated."""
        return self.meta(code).get("commentary_lang") or self.interface

    def commentary(self, code, text):
        return self.wrap(self.commentary_lang(code), e(text))

    def markup(self, code, text):
        """Commentary text with {{marked}} stretches in the pack's own language."""
        base = self.commentary_lang(code)
        parts = MARK.split(text)
        inner = "".join(self.inline(code, p, ctx=base) if i % 2 else e(p) for i, p in enumerate(parts))
        return self.wrap(base, inner)

    # -- regional forms

    @staticmethod
    def forms_of(concept):
        """A concept's forms as [{text, varieties, note}]. A plain 'text' is one form used by every variety."""
        if concept.get("forms"):
            return [
                {"text": f["text"], "varieties": list(f.get("varieties", [])), "note": f.get("note")} for f in concept["forms"]
            ]
        return [{"text": concept["text"], "varieties": [], "note": None}]

    def varieties(self, code):
        return self.meta(code).get("varieties", [])

    def has_varieties(self):
        return any(self.varieties(code) for code in self.langs)

    def show_sets(self, code, forms):
        """For each form, the varieties it is emphasised for.

        A form shows for a variety when it is tagged with it or untagged. If no form matches a variety,
        every form shows for it, so a concept known in one region only is never dimmed away.
        """
        shows = [[] for _ in forms]
        for v in self.varieties(code):
            idx = [i for i, f in enumerate(forms) if not f["varieties"] or v["id"] in f["varieties"]]
            for i in idx or range(len(forms)):
                shows[i].append(v["id"])
        return shows

    def keyed(self, text, keys):
        """A row's text, escaped, with its key words (see keys.py) wrapped to be drawn in their colour and underline."""
        if not keys:
            return e(text)
        text, out, at = keywords.fold(text), [], 0
        for start, end, n in keywords.find(text, keys):
            out.append(f'{e(text[at:start])}<span class="key" data-k="{n + 1}">{e(text[start:end])}</span>')
            at = end
        return "".join(out) + e(text[at:])

    def form_markup(self, code, form, show, cls, keys=None):
        names = {v["id"]: v for v in self.varieties(code)}
        tags = "".join(
            f'<abbr class="vtag" title="{e(names[v]["name"])}">{e(names[v]["short"])}</abbr>' for v in form["varieties"]
        )
        note = f'<small class="note">{self.markup(code, form["note"])}</small>' if form["note"] else ""
        cls_attr = f' class="{cls}"' if cls else ""
        return (
            f'<span class="form" data-lang="{e(code)}" data-show="{" ".join(show)}">'
            f'<span{cls_attr}{self.la(code)}>{self.keyed(form["text"], keys)}</span>{tags}{note}</span>'
        )

    def is_plain(self, forms):
        return len(forms) == 1 and not forms[0]["varieties"] and not forms[0]["note"]

    def varieties_css(self):
        """Dim the forms that do not apply to the variety chosen for a language. Generated from the packs."""
        rules = []
        for code in self.langs:
            for v in self.varieties(code):
                rules.append(
                    f'html[data-v-{code}="{v["id"]}"] .form[data-lang="{code}"]'
                    f':not([data-show~="{v["id"]}"]){{opacity:.55;font-size:.92em}}'
                )
        return (
            "/* Generated by the phrasebook builder from the varieties in the packs. Do not edit. */\n" + "\n".join(rules) + "\n"
        )

    APPEARANCES = ("system", "light", "dark")

    def palette_label(self, pid, code=None):
        """A palette's name for the interface (or for the language `code`): (text, language it is written in)."""
        code = code or self.interface
        names = self.palettes[pid].get("names", {})
        if code in names:
            return names[code], code
        key = "palette_" + pid.replace("-", "_")
        if self.messages.has(key):
            return self.messages.format(code, key)
        if "en" in names:
            return names["en"], "en"
        if names:
            first, text = next(iter(names.items()))
            return text, first
        return pid, self.interface

    def both(self, key, **html_params):
        """A message in each language of the pair, as spans of which the language toggle shows one. Params are HTML already."""
        parts = []
        for n, code in enumerate((self.frm, self.to), 1):
            text, lang = self.messages.format(code, key, html_mode=True, **html_params)
            parts.append(f'<span class="t" data-n="{n}"{self.la(lang)}>{text}</span>')
        return "".join(parts)

    def both_named(self, key, code):
        """A message that names the language `code`, in each language of the pair, with the name written in that language:
        the pack's name for it in that language, or else the language's own name for itself (its endonym)."""
        parts = []
        for n, shown in enumerate((self.frm, self.to), 1):
            if shown == self.interface:
                name = self.language_name(code)
            else:
                name = self.meta(code).get("names", {}).get(shown) or self.endonym(code)
            text, lang = self.messages.format(shown, key, html_mode=True, language=e(name))
            parts.append(f'<span class="t" data-n="{n}"{self.la(lang)}>{text}</span>')
        return "".join(parts)

    def both_palette(self, pid):
        """A palette's name in each language of the pair, as `both` does."""
        parts = []
        for n, code in enumerate((self.frm, self.to), 1):
            text, lang = self.palette_label(pid, code)
            parts.append(f'<span class="t" data-n="{n}"{self.la(lang)}>{e(text)}</span>')
        return "".join(parts)

    def language_toggle(self, radio_name, codes):
        """The radios and the bar that choose which language of the pair a page shows. The first radio is checked."""
        radios = "".join(
            f'<input type="radio" class="lang-radio" name="{radio_name}" id="{radio_name}-{e(code)}" value="{e(code)}"'
            f'{" checked" if i == 0 else ""}>'
            for i, code in enumerate(codes)
        )
        labels = "".join(f'<label for="{radio_name}-{e(code)}">{self.inline(code, self.endonym(code))}</label>' for code in codes)
        bar = f'<div class="lang-bar" role="group" aria-label="{e(self.plain("about_language"))}">{labels}</div>'
        return radios, bar

    def fold(self, heading_html, body_html, open_=False, card=False, labelled=None, attrs="", cls=""):
        """A section that opens and closes: a details element whose summary is the heading. It works with no script, and
        the controls inside stay in the page, with their state, while it is shut. `cls` adds a class (a topic's accordion)."""
        cls = " ".join(filter(None, ["fold", "card" if card else "", cls]))
        label = f' aria-labelledby="{labelled}"' if labelled else ""
        return (
            f'<details class="{cls}"{label}{attrs}{" open" if open_ else ""}><summary>{heading_html}</summary>'
            f'<div class="fold-body">{body_html}</div></details>'
        )

    def subsection(self, ident, heading_html, body_html, attrs="", cls=""):
        """A headed part of a fold: an h3 and its controls. A fold groups the choices that belong together (Accessibility and
        appearance; Order and tile layout), and each choice in it is one of these."""
        classes = f"subsection {cls}" if cls else "subsection"
        return f'<section class="{classes}"{attrs} aria-labelledby="{ident}"><h3 id="{ident}">{heading_html}</h3>{body_html}</section>'

    ICONS_FOR_APPEARANCE = {"light": "light", "dark": "asleep", "system": "screen"}

    def view_mode_section(self):
        """View mode: light, dark or the device's own, as three large icon tiles."""
        tiles = "".join(
            f'<label class="mode"><input type="radio" name="appearance" value="{v}" data-pref="appearance"'
            f'{" checked" if v == "system" else ""}><span class="mode-box">{self.ui_icons[self.ICONS_FOR_APPEARANCE[v]]}'
            f'{self.both("appearance_" + v)}</span></label>'
            for v in self.APPEARANCES
        )
        return self.subsection(
            "h-appearance",
            self.both("view_mode") + self.help_icon("view-mode"),
            f'<p class="hint">{self.both("appearance_hint")}</p><div class="modes" role="radiogroup" aria-labelledby="h-appearance">{tiles}</div>',
        )

    def palette_levels(self):
        """The accessibility levels the offered palettes fall into, in the order standard, safe, high."""
        used = {palettes.access_level(self.palettes[pid]) for pid in self.palette_ids}
        return [level for level in palettes.ACCESS_LEVELS if level in used]

    def accessibility_section(self, levels, first):
        """Standard, safe colours or high contrast: chooses which colour schemes are listed. It changes no scheme."""
        radios = "".join(
            f'<label><input type="radio" name="access" value="{level}" data-pref="access"{" checked" if level == first else ""}>'
            f'<span class="seg-label">{self.both("access_" + level)}</span></label>'
            for level in levels
        )
        hints = "".join(f'<p class="hint" data-hint="{level}">{self.both("access_" + level + "_hint")}</p>' for level in levels)
        return self.subsection(
            "h-access",
            self.both("accessibility") + self.help_icon("accessibility"),
            f'<p class="hint">{self.both("access_hint")}</p><div class="seg" role="radiogroup" aria-labelledby="h-access">{radios}</div>{hints}',
        )

    def colours_section(self):
        """Each offered colour scheme as a small picture of itself, drawn from its own colours (see palettes.css)."""
        cards = "".join(
            f'<label class="swatch" data-tier="{palettes.access_level(self.palettes[pid])}">'
            f'<input type="radio" name="palette" value="{pid}" data-pref="palette"{" checked" if pid == self.default_palette else ""}'
            f' data-tier="{palettes.access_level(self.palettes[pid])}">'
            f'<span class="preview" data-palette="{pid}" aria-hidden="true"><i class="pv-bar"></i><i class="pv-tile"><b></b></i>'
            f'<i class="pv-card"><b></b><b></b></i><i class="pv-dot"></i></span>'
            f'<span class="swatch-name">{self.both_palette(pid)}</span></label>'
            for pid in self.palette_ids
        )
        return self.subsection(
            "h-colours",
            self.both("colours") + self.help_icon("colour-schemes"),
            f'<p class="hint">{self.both("colours_hint")}</p>'
            f'<div class="swatches" role="radiogroup" aria-labelledby="h-colours">{cards}</div>'
            f'<p class="hint colours-only" hidden>{self.both("colours_only")}</p>',
        )

    KEY_STYLES = ("colour", "line", "off")  # marked by colour, by underline, or not at all

    def has_keys(self):
        """True when some concept marks key words, so the setting that colours them has something to do."""
        return any(
            "keys" in c
            for pack in self.raw["packs"].values()
            for page in pack["pages"].values()
            for sec in page.get("sections", {}).values()
            for c in sec.get("concepts", {}).values()
        )

    def keys_section(self):
        """How key words are marked: by colour, by underline, or not at all. Colour is hidden at the high-contrast level
        (app.js), where the key colours are least distinct, and a choice of it becomes the underline. Offered only when some concept has key words, so it
        is never a control that does nothing."""
        radios = "".join(
            f'<label><input type="radio" name="keys" value="{v}" data-pref="keys"{" checked" if v == "colour" else ""}'
            f'{" data-hide-at=" + chr(34) + "high" + chr(34) if v == "colour" else ""}>'
            f'<span class="seg-label">{self.both("keys_" + v)}</span></label>'
            for v in self.KEY_STYLES
        )
        return self.subsection(
            "h-keys",
            self.both("keys_title") + self.help_icon("key-words"),
            f'<p class="hint">{self.both("keys_hint")}</p><div class="seg" role="radiogroup" aria-labelledby="h-keys">{radios}</div>',
        )

    def look_group(self):
        """Accessibility and appearance, one fold, open to begin with: the view mode (light, dark or the device's own), the accessibility
        level and the colour schemes. The last two appear only when the edition offers a choice."""
        parts = self.view_mode_section()
        if len(self.palette_ids) > 1:
            levels = self.palette_levels()
            if len(levels) > 1:
                parts += self.accessibility_section(levels, palettes.access_level(self.palettes[self.default_palette]))
            parts += self.colours_section()
        if self.has_keys():
            parts += self.keys_section()
        return self.fold(f'<h2 id="h-look">{self.both("group_look")}</h2>', parts, open_=True, card=True, labelled="h-look")

    def variety_fields(self):
        """A choice per displayed language that has varieties."""
        fields = []
        for code in (self.frm, self.to):
            varieties = self.varieties(code)
            if not varieties:
                continue
            options = [("all", self.both("variety_all"))] + [(v["id"], self.commentary(code, v["name"])) for v in varieties]
            radios = "".join(
                f'<label><input type="radio" name="variety-{e(code)}" value="{vid}" data-variety-lang="{e(code)}"'
                f'{" checked" if vid == "all" else ""}><span class="seg-label">{label}</span></label>'
                for vid, label in options
            )
            legend = self.both_named("regional_forms", code)
            fields.append(
                self.fold(
                    f'<h2 id="h-var-{e(code)}">{legend}{self.help_icon("regional-forms")}</h2>',
                    f'<div class="seg" role="radiogroup" aria-labelledby="h-var-{e(code)}">{radios}</div>',
                    card=True,
                    labelled=f"h-var-{e(code)}",
                )
            )
        return "".join(fields)

    ORDERS = ("written", "simple", "advanced")  # as written, simplest first, most advanced first

    def has_levels(self):
        """True when the site has something to put in order: tiles or sections of more than one level."""
        found = {level for table in self.levels.values() for level in table.values()}
        return len(found) > 1

    def order_section(self):
        """Put tiles and sections in order from simple to advanced, or the other way round, or leave them as written. Only offered
        when the levels differ somewhere, so it is never a control that does nothing. A screen the visitor has arranged keeps their order.
        """
        if not self.has_levels():
            return ""
        radios = "".join(
            f'<label><input type="radio" name="order" value="{v}" data-pref="order"{" checked" if v == "written" else ""}>'
            f'<span class="seg-label">{self.both("order_" + v)}</span></label>'
            for v in self.ORDERS
        )
        return self.subsection(
            "h-order",
            self.both("order_title") + self.help_icon("order-setting"),
            f'<p class="hint">{self.both("order_hint")}</p><div class="seg" role="radiogroup" aria-labelledby="h-order">{radios}</div>',
        )

    def tile_layout_section(self):
        """Tile layout: every screen's tile order back to the default at once. Hidden until arrange.js runs, like the other choices."""
        return self.subsection(
            "h-layout",
            self.both("reset_orders_title") + self.help_icon("reset-tile-layouts"),
            f'<p class="hint">{self.both("reset_orders_lede")}</p>'
            f'<p><button type="button">{self.h("reset_orders")}</button></p>'
            f'<p class="arrange-status" role="status" data-reset-status '
            f'data-done="{e(self.plain("reset_orders_done"))}" data-failed="{e(self.plain("arrange_failed"))}"></p>',
            attrs=" data-reset-orders hidden",
            cls="reset-orders",
        )

    def order_group(self):
        """Order and tile layout, one fold: the order of tiles and sections from simple to advanced (offered only where the levels
        differ) and putting every tile back where it started."""
        return self.fold(
            f'<h2 id="h-order-group">{self.both("group_order")}</h2>',
            self.order_section() + self.tile_layout_section(),
            card=True,
            labelled="h-order-group",
        )

    def prefs_controls(self):
        """Every choice the visitor can make, in folds that group what belongs together. Hidden until app.js runs, so it is never a
        dead control."""
        return f'<div class="prefs" id="prefs" hidden>{self.look_group()}{self.order_group()}{self.variety_fields()}</div>'

    def palettes_css(self):
        return palettes.css(self.palettes, self.palette_ids, self.default_palette)

    # -- structure

    def rows(self, slug, section):
        """Concept ids of a section that exist in both languages of the pair."""
        return [
            cid
            for cid in section["concepts"]
            if self.concept(self.frm, slug, section["id"], cid) and self.concept(self.to, slug, section["id"], cid)
        ]

    def sections(self, slug):
        return [s for s in self.skel[slug]["sections"] if self.rows(slug, s)]

    def count_entries(self, slug):
        return sum(len(self.rows(slug, s)) for s in self.skel[slug]["sections"])

    def group_of(self, slug):
        for g in self.groups:
            if slug in g["pages"]:
                return g
        raise KeyError(slug)

    def icon_html(self, name):
        """The inline markup of a project icon, or nothing for a name that is not given."""
        return self.icons[name] if name else ""

    def page_icon(self, slug):
        return self.icon_html(self.skel[slug].get("icon"))

    def group_title(self, code, gid):
        return self.meta(code)["groups"][gid]

    def sequence(self):
        return ["index"] + [s for g in self.groups for s in g["pages"]]

    def run(self):
        """The pages Previous and Next go through: the home page, then each topic, where a one-page group is its one page."""
        seq = ["index"]
        for g in self.groups:
            seq += [f"group-{g['id']}"] if g["layout"] == "one-page" else g["pages"]
        return seq

    def href(self, slug, anchor=None):
        """The address of a topic, or of a place in it (`anchor`, a section id or a row's section.concept): its own page, or on a
        one-page group the group's page, at the topic's accordion or at the place."""
        gid = self.homes.get(slug)
        if gid:
            return f"group-{gid}.html#{anchor or TOPIC_PREFIX + slug}"
        return f"{slug}.html#{anchor}" if anchor else f"{slug}.html"

    def prose(self, getter):
        """First (code, text) from the pair, then the rest of the edition, where getter returns something."""
        for code in [self.frm, self.to] + [c for c in self.langs if c not in (self.frm, self.to)]:
            v = getter(code)
            if v:
                return code, v
        return None, None

    def brand_small(self):
        return self.h(
            "pair_label", first=self.inline(self.frm, self.endonym(self.frm)), second=self.inline(self.to, self.endonym(self.to))
        )

    # -- navigation

    def pager(self, current):
        seq = self.run()
        i = seq.index(current)

        def link(slug, cls, key):
            if slug == "index":
                t = self.ui_text(self.frm, "main_menu")
                c = self.ui_text(self.to, "main_menu")
                first = f'<span class="t"{self.la(t[1])}>{e(t[0])}</span>'
                second = f'<span class="c"{self.la(c[1])}>{e(c[0])}</span>'
            elif slug.startswith("group-"):  # a one-page group
                gid = slug[len("group-") :]
                first = f'<span class="t"{self.la(self.frm)}>{e(self.group_title(self.frm, gid))}</span>'
                second = f'<span class="c"{self.la(self.to)}>{e(self.group_title(self.to, gid))}</span>'
            else:
                first = f'<span class="t"{self.la(self.frm)}>{e(self.title(self.frm, slug))}</span>'
                second = f'<span class="c"{self.la(self.to)}>{e(self.title(self.to, slug))}</span>'
            href = "index.html" if slug == "index" else f"{slug}.html"
            return f'<a class="{cls}" href="{href}"><small>{self.h(key)}</small>{first}{second}</a>'

        parts = []
        if i > 0:
            parts.append(link(seq[i - 1], "prev", "previous"))
        if i < len(seq) - 1:
            parts.append(link(seq[i + 1], "next", "next"))
        return f'{self.help_slot("pager")}<nav class="pager" aria-label="{e(self.plain("pager_label"))}">{"".join(parts)}</nav>'

    # -- the frame: Back, the trail and tiles

    def pair_spans(self, a, b):
        return f'<span class="l1"{self.la(self.frm)}>{e(a)}</span>', f'<span class="l2"{self.la(self.to)}>{e(b)}</span>'

    def ui_pair(self, key):
        return self.ui_span("l1", self.frm, key), self.ui_span("l2", self.to, key)

    def steps(self, current):
        """The way from the home page to `current`: [(address, (first, second) labels)], the last step having no address."""
        if current == "index":
            return []
        steps = [("index.html", self.ui_pair("home"))]
        frm, to = self.frm, self.to
        if current.startswith("group-"):
            gid = current[len("group-") :]
            steps.append((None, self.pair_spans(self.group_title(frm, gid), self.group_title(to, gid))))
        elif current in self.slugs:
            gid = self.group_of(current)["id"]
            steps.append((f"group-{gid}.html", self.pair_spans(self.group_title(frm, gid), self.group_title(to, gid))))
            steps.append((None, self.pair_spans(self.title(frm, current), self.title(to, current))))
        elif current in ("settings", "about"):
            steps.append((None, self.ui_pair(current)))
        elif current.startswith(HELP_PREFIX):  # a help chapter sits under the contents page, which sits under About
            under = "about" if self.edition.get("about_page") else "settings"
            steps += [
                (f"{under}.html", self.ui_pair(under)),
                ("how-to.html", self.ui_pair("how_to")),
                (None, self.help_pair("chapters", current[len(HELP_PREFIX) :])),
            ]
        else:  # the how-to and sources pages sit under About, or under Settings where the edition has no About page
            under = "about" if self.edition.get("about_page") else "settings"
            steps += [
                (f"{under}.html", self.ui_pair(under)),
                (None, self.ui_pair("how_to" if current == "how-to" else current)),
            ]
        return steps

    def parent_of(self, current):
        """The address one level up (the Back target), or None for the home page."""
        steps = self.steps(current)
        return steps[-2][0] if len(steps) > 1 else None

    def top_bar(self, current):
        """(Back link for the rail, trail for the top bar). The home page has neither."""
        steps = self.steps(current)
        if not steps:
            return "", ""
        name = e(self.plain("back"))
        back = (
            f'<a class="rail-link back" href="{steps[-2][0]}" data-back aria-label="{name}" title="{name}">'
            f'{self.ui_icons["arrow--left"]}</a>'
        )
        items = []
        for href, (first, second) in steps:
            inner = f"{first}{second}" if href else first  # the page's own heading already gives both languages
            items.append(
                f'<li><a href="{href}">{inner}</a></li>' if href else f'<li><span aria-current="page">{inner}</span></li>'
            )
        return back, f'<nav aria-label="{e(self.plain("trail_label"))}"><ol class="trail">{"".join(items)}</ol></nav>'

    # Right after a list of tiles, and after the sections of a topic, so it runs as soon as they exist and before anything is painted:
    # it asks order.js (loaded in the head) to put them in order, so they are never seen moving. Without that script nothing happens and
    # they stay as written. It is written without a closing brace pair, which the project's check for unrendered templates rejects.
    ORDER_HOOK = '<script>(function(d){var v=new Event("phrasebook:order");v.page=d.currentScript.parentNode;d.dispatchEvent(v)})(document)</script>'

    def tile(self, href, first, second, icon, ident, level=None, related=False):
        """A large touch target: the icon on a tile, with the name in both languages beneath. No icon, the name goes in the tile.
        `ident` names the tile for a saved order (data-tile), so the order is kept whatever the tile's label says. `level` is how
        demanding it is, from 1 to 3 (data-level), for putting the tiles in order from simple to advanced."""
        l1, l2 = self.pair_spans(first, second)
        inner = self.icon_html(icon) or f'<span class="tile-text" aria-hidden="true">{e(first)}</span>'
        graded = f' data-level="{level}"' if level else ""
        followed = " data-related" if related else ""  # Back returns to the topic this was followed from (see nav.js)
        return (
            f'<li data-tile="{e(ident)}"{graded}><a class="tile-link" href="{href}"{followed}><span class="tile">{inner}</span>'
            f'<span class="tile-name">{l1}{l2}</span></a></li>'
        )

    def tiles(self, items, order):
        """A grid of tiles. `order` names the screen whose tile order is saved (data-order), so the script can find it.
        Edit order adds a bar above the grid: a hint, and Done and Reset. Its messages go in data attributes for the script."""
        keys = {
            "picked": "picked",
            "moved": "moved",
            "cancelled": "cancelled",
            "saved": "saved",
            "reset": "reset_done",
            "failed": "failed",
        }
        # The script fills {name}, {n} and {total} in; here they pass through as they are.
        messages = "".join(
            f' data-{attr}="{e(self.plain("arrange_" + key, n="{n}", name="{name}", total="{total}"))}"'
            for attr, key in keys.items()
        )
        bar = (
            f'<div class="arrange-bar" data-arrange-bar{messages}>'
            f'<p class="arrange-hint">{self.h("arrange_hint")}</p>'
            '<div class="arrange-actions">'
            f'<button type="button" data-arrange-done>{self.h("arrange_done")}</button>'
            f'<button type="button" data-arrange-reset>{self.h("arrange_reset")}</button></div></div>'
        )
        # Read aloud, not seen: the script says each change here for a screen reader, so the region stays in the page.
        live = '<p class="sr-only" role="status" data-arrange-status></p>'
        return (
            f'{self.help_slot("tiles")}{bar}{live}<ul class="tiles" data-tiles data-order="{e(order)}" aria-label="{e(self.plain("topics_label"))}">'
            f'{"".join(items)}</ul>{self.ORDER_HOOK}'
        )

    # -- pages

    def repeats_title(self, slug, sid):
        """True when a section's heading says what the page title already says, in both languages of the pair."""

        def same(code):
            fold = lambda t: unicodedata.normalize("NFC", t or "").casefold()
            return fold(self.pack_section(code, slug, sid).get("title")) == fold(self.title(code, slug))

        return same(self.frm) and same(self.to)

    def shown_sections(self, slug, figure):
        """The sections drawn as tables: not one whose every word the page's figure, if it was drawn, already shows."""
        covered = set(FIGURE_CONCEPTS.get(self.skel[slug].get("figure"), ())) if figure else set()
        return [s for s in self.sections(slug) if not set(s["concepts"]) <= covered]

    def render_section(self, slug, section, nested=False):
        """One section: its heading, order line, intro, the table of rows, and its box. `nested` is a section inside a topic's
        accordion on a one-page group: its heading goes a level down, and it carries no level, since there the accordions are
        what is put in order, not the sections."""
        frm, to, sid = self.frm, self.to, section["id"]
        hx, bx = ("h3", "h4") if nested else ("h2", "h3")
        rows = []
        for cid in self.rows(slug, section):
            cf, ct = self.concept(frm, slug, sid, cid), self.concept(to, slug, sid, cid)
            notes = "".join(
                f'<small class="note">{self.markup(code, c["note"])}</small>'
                for code, c in ((frm, cf), (to, ct))
                if c.get("note")
            )
            ff, ft = self.forms_of(cf), self.forms_of(ct)
            if self.is_plain(ff):
                head = f'<th scope="row" class="l1"{self.la(frm)}>{self.keyed(ff[0]["text"], cf.get("keys"))}</th>'
            else:
                forms = "".join(self.form_markup(frm, f, s, None, cf.get("keys")) for f, s in zip(ff, self.show_sets(frm, ff)))
                head = f'<th scope="row" class="l1"><span class="forms">{forms}</span></th>'
            if self.is_plain(ft):
                cell = f'<span class="l2"{self.la(to)}>{self.keyed(ft[0]["text"], ct.get("keys"))}</span>'
            else:
                forms = "".join(self.form_markup(to, f, s, "l2", ct.get("keys")) for f, s in zip(ft, self.show_sets(to, ft)))
                cell = f'<span class="forms">{forms}</span>'
            rows.append(f'<tr id="{sid}.{cid}">{head}<td>{cell}{notes}</td></tr>')
            also = "".join(
                f'<span class="also-form"{self.la(code)}>{e(a)}</span>'
                for code, c in ((frm, cf), (to, ct))
                for a in c.get("also", [])
            )
            if also:
                rows.append(
                    f'<tr class="also-row"><td colspan="2"><span class="also-label" title="{e(self.plain("also_heard"))}">'
                    f"{self.ui_icons['headphones']}<span class=\"sr-only\">{self.h('also_heard')}</span></span> {also}</td></tr>"
                )
        order = "".join(
            f'<p class="order">{self.h("section_order", order=self.markup(code, sec["order"]))}{self.help_icon("sections-order")}</p>'
            for code in (frm, to)
            for sec in [self.pack_section(code, slug, sid)]
            if sec.get("order")
        )
        intro = "".join(
            f'<p class="intro">{self.markup(code, sec["intro"])}</p>'
            for code in (frm, to)
            for sec in [self.pack_section(code, slug, sid)]
            if sec.get("intro")
        )
        box = "".join(
            f'<div class="box"><{bx}>{self.commentary(code, sec["box"]["title"])}</{bx}><p>{self.markup(code, sec["box"]["body"])}</p></div>'
            for code in (frm, to)
            for sec in [self.pack_section(code, slug, sid)]
            if sec.get("box")
        )
        heading = ""
        if not self.repeats_title(slug, sid):
            heading = (
                f'<{hx}>{self.inline(frm, self.pack_section(frm, slug, sid)["title"])}'
                f'<span class="l2"{self.la(to)}>{e(self.pack_section(to, slug, sid)["title"])}</span></{hx}>'
            )
        graded = "" if nested else f' data-level="{self.levels["sections"].get((slug, sid), 1)}"'
        return (
            f'<section id="{sid}"{graded}>{heading}{order}{intro}'
            f'<div class="card"><table class="terms pair"><thead class="sr-only"><tr><th scope="col">{self.inline(frm, self.endonym(frm))}</th>'
            f'<th scope="col">{self.inline(to, self.endonym(to))}</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>{box}</section>'
        )

    def search_scope(self, current):
        """The page files the person is browsing: a topic is its own page, a group is its pages, anywhere else is nothing.
        Search lists the words found there first."""
        if current in self.slugs:
            return [f"{current}.html"]
        for group in self.groups:
            if current == f"group-{group['id']}":
                return list(dict.fromkeys(self.href(slug).split("#")[0] for slug in group["pages"] + group["links"]))
        return []

    def search_card(self, current=None):
        """The dictionary lookup card, shut and hidden. search.js reveals the layer and the rail button, and fills the results
        from dictionary.json as the person types, so without scripts there is no control that does nothing."""
        pair = json.dumps([[self.frm, self.dir_of(self.frm)], [self.to, self.dir_of(self.to)]])
        hint = self.plain("search_hint", first=self.endonym(self.frm), second=self.endonym(self.to))
        name = e(self.plain("search"))
        clear_name, close_name = e(self.plain("search_clear")), e(self.plain("search_close"))
        return (
            '<div class="search-layer" hidden>'
            f'<div class="search-card" id="search-card" role="search" aria-label="{name}" inert '
            f'data-dictionary="dictionary.json" data-pair="{e(pair)}" data-hint="{e(hint)}" '
            f'data-none="{e(self.plain("search_none"))}" data-error="{e(self.plain("search_error"))}" '
            f'data-other="{e(self.plain("search_other"))}" data-scope="{e(json.dumps(self.search_scope(current)))}">'
            '<div class="search-head"><div class="search-box"><label class="search-field">'
            f'<span class="sr-only">{name}</span>'
            f'<input id="search-input" type="search" placeholder="{e(self.plain("search_placeholder"))}" autocomplete="off" '
            'autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="search"></label>'
            # Actions are symbols, not words (see "Form actions are symbols" in FRAMEWORK.md): delete the text, and close the card.
            f'<button type="button" class="search-clear" hidden aria-label="{clear_name}" title="{clear_name}">{self.ui_icons["backspace"]}</button></div>'
            f'<button type="button" class="search-close" aria-label="{close_name}" title="{close_name}">{self.ui_icons["close"]}</button></div>'
            '<p class="search-status" id="search-status" role="status"></p>'
            '<div class="search-body"><ul class="search-results" id="search-results"></ul>'
            f'<h2 class="search-topics" hidden>{e(self.plain("search_topics"))}</h2>'
            '<ul class="search-pages" id="search-pages"></ul></div>'
            "</div></div>"
        )

    def shell(self, current, content, with_pager=True, wide=False):
        """The frame around every page: a title bar across the top (title and trail), then a rail (search, Back, settings) and the page."""
        pager = self.pager(current) if with_pager else ""
        back, trail = self.top_bar(current)
        current_mark = ' aria-current="page"' if current == "settings" else ""
        settings = (
            f'<a class="rail-link" href="settings.html" aria-label="{e(self.plain("settings"))}"{current_mark}>'
            f'{self.ui_icons["settings"]}</a>'
        )
        search_name = e(self.plain("search"))
        search = (
            f'<button type="button" class="rail-link search" id="search-button" hidden aria-label="{search_name}" '
            f'title="{search_name}" aria-expanded="false" aria-controls="search-card">{self.ui_icons["search"]}</button>'
        )
        about = ""
        if self.edition.get("about_page"):
            about_name = e(self.plain("about"))
            about_mark = ' aria-current="page"' if current == "about" else ""
            about = (
                f'<a class="rail-link" href="about.html" aria-label="{about_name}" title="{about_name}"{about_mark}>'
                f'{self.ui_icons["information"]}</a>'
            )
        # The help button turns on the help icons, so it is only on a page that has some. Hidden until help.js runs.
        helping = ""
        trail_help = self.help_icon("trail") if trail else ""  # at the end of the title bar, beside the titles, not under them
        if 'data-help="' in content + pager + trail_help:
            help_name = e(self.plain("help_toggle"))
            helping = (
                f'<button type="button" class="rail-link help-toggle" id="help-toggle" hidden aria-pressed="false" '
                f'aria-label="{help_name}" title="{help_name}">{self.ui_icons["help"]}</button>'
            )
        card = self.help_card() if helping else ""
        # Edit order is for the screens that are tiles: the home page and a group page. Hidden until arrange.js runs.
        arrange = ""
        if current == "index" or current.startswith("group-"):
            arrange_name = e(self.plain("arrange_toggle"))
            arrange = (
                f'<button type="button" class="rail-link arrange-toggle" id="arrange-button" hidden aria-pressed="false" '
                f'aria-label="{arrange_name}" title="{arrange_name}">{self.ui_icons["tools"]}</button>'
            )
        return (
            f'<a class="skip" href="#main">{self.h("skip_to_content")}</a>'
            '<div class="app">'
            f'<header class="topbar"><div class="titles{" has-trail" if trail else ""}"><a class="brand" href="index.html"><span class="word">{e(self.name)}</span>'
            f"<small>{self.brand_small()}</small></a>{trail}</div>{trail_help}</header>"
            f'<nav class="rail" aria-label="{e(self.plain("settings"))}"><div class="rail-group">{search}{back}</div>'
            f'<div class="rail-group">{helping}{arrange}{about}{settings}</div></nav>'
            f'<main id="main"><div class="{"page wide" if wide else "page"}">{content}{pager}</div></main>'
            f"{self.search_card(current)}{card}"
            "</div>"
        )

    def related_tiles(self, slug, entries=None, ident="related"):
        """The Related row of a topic: a tile for each topic it names that is published, after its sections. A tile opens the page, at
        the section if one is named, and is named for that section in both languages (else for the page). The list is a list of
        tiles that slide in and take the arrow keys, but it names no saved order, so it is never arranged or put in order."""
        frm, to = self.frm, self.to
        tiles = []
        for entry in self.skel[slug].get("related", []) if entries is None else entries:
            page, _, sid = entry.partition("#")
            if page == slug or (page in self.homes and self.homes[page] == self.homes.get(slug)):
                continue  # on one page, a topic of the same page is an accordion away, not a tile
            if page not in self.slugs:  # held back from this release, or with nothing to show in this pair
                continue
            if sid and sid not in {s["id"] for s in self.sections(page)}:
                sid = ""  # the section is not published: the page is still worth a tile
            titles = [self.pack_section(code, page, sid).get("title") for code in (frm, to)] if sid else []
            if not titles or not all(titles):
                titles = [self.title(frm, page), self.title(to, page)]
            level = self.levels["sections"].get((page, sid)) if sid else self.levels["pages"].get(page)
            tiles.append(
                self.tile(
                    self.href(page, sid or None),
                    titles[0],
                    titles[1],
                    self.skel[page].get("icon"),
                    f"{page}-{sid}" if sid else page,
                    level,
                    related=True,
                )
            )
        if not tiles:
            return ""
        (first, first_lang), (second, second_lang) = self.ui_text(frm, "related"), self.ui_text(to, "related")
        hx = "h3" if slug in self.homes and ident != "related" else "h2"  # a row inside a topic's accordion is a level down
        heading = f'<{hx} id="h-{ident}">{self.inline(first_lang, first)}<span class="l2"{self.la(second_lang)}>{e(second)}</span>{self.help_icon("related-topics")}</{hx}>'
        return (
            f'<section class="related" aria-labelledby="h-{ident}">{heading}'
            f'<ul class="tiles" data-tiles aria-label="{e(self.plain("related"))}">{"".join(tiles)}</ul></section>'
        )

    def more_note(self, slug):
        """The optional closing note of a topic: the page's `more` blocks (as in an About section) from the first language of the pair
        that has them, after the related row. Used to point to a fuller source."""
        code, blocks = self.prose(lambda c: self.pack_page(c, slug).get("more"))
        if not blocks:
            return ""
        return f'<footer class="more"{self.la(code)}>{"".join(self.about_block(code, b) for b in blocks)}</footer>'

    def content_page(self, slug):
        frm, to = self.frm, self.to
        fig = self.skel[slug].get("figure")
        figure = FIGURES[fig](self, slug) if fig else ""
        sections = self.shown_sections(slug, figure)
        for hidden in self.sections(slug):
            if hidden not in sections:  # a section the figure stands in for keeps its address
                figure = f'<section id="{hidden["id"]}" class="figure">{figure}</section>'
        jump = ""
        if len(sections) >= 3:
            # The list has no visible heading, so its name for a screen reader is given in both languages of the pair.
            label = " / ".join(self.ui_text(code, "on_this_page")[0] for code in (frm, to))
            jump = (
                f'<ul class="jump" aria-label="{e(label)}">'
                + "".join(
                    f'<li><a href="#{s["id"]}">{self.inline(frm, self.pack_section(frm, slug, s["id"])["title"])}</a></li>'
                    for s in sections
                )
                + "</ul>"
                + self.help_slot("jump-links")
            )
        lcode, lede = self.prose(lambda c: self.pack_page(c, slug).get("lede"))
        lede_html = f'<p class="lede"{self.la(lcode)}>{e(lede)}</p>' if lede else ""
        head = (
            f"<header><h1>{self.inline(frm, self.title(frm, slug))}</h1>"
            f'<p class="title-l2"{self.la(to)}>{e(self.title(to, slug))}</p>'
            f"{lede_html}</header>"
        )
        return (
            head
            + figure
            + jump
            + "".join(self.render_section(slug, s) for s in sections)
            + self.ORDER_HOOK
            + self.related_tiles(slug)
            + self.more_note(slug)
        )

    def home_page(self):
        frm, to = self.frm, self.to
        home = self.edition.get("home", {})
        groups = [
            self.tile(
                f"group-{g['id']}.html",
                self.group_title(frm, g["id"]),
                self.group_title(to, g["id"]),
                g.get("icon"),
                g["id"],
                self.levels["groups"].get(g["id"]),
            )
            for g in self.groups
        ]
        lcode, lede = self.prose(lambda c: home.get("lede", {}).get(c))
        acode, about = self.prose(lambda c: home.get("about", {}).get(c))
        if self.edition.get("about_page"):
            # The About page holds the links to the app's own pages, so the closing line is only the note, if there is one.
            closing = f'<p class="about">{self.inline(acode, about)}</p>' if about else ""
        else:
            link = f'<a href="sources.html">{self.h("sources_link")}</a>'
            closing = (
                f'<p class="about">{self.h("home_about", about=self.inline(acode, about), link=link)}</p>'
                if about
                else f'<p class="about">{link}</p>'
            )
        return (
            f'<header><p class="kicker">{self.ui_html(frm, "phrasebook")} / {self.ui_html(to, "phrasebook")}</p>'
            f'<h1>{self.inline(frm, home["headline"][frm])}</h1>'
            f'<p class="title-l2"{self.la(to)}>{e(home["headline"][to])}</p>'
            f'<p class="lede">{self.inline(lcode, lede) if lede else ""}</p></header>' + self.tiles(groups, "index") + closing
        )

    def group_page(self, group):
        """One group's topics as tiles, or on a one-page group as accordions (see one_page)."""
        frm, to, gid = self.frm, self.to, group["id"]
        head = (
            f"<header><h1>{self.inline(frm, self.group_title(frm, gid))}</h1>"
            f'<p class="title-l2"{self.la(to)}>{e(self.group_title(to, gid))}</p></header>'
        )
        if group["layout"] == "one-page":
            return head + self.one_page(group)
        pages = [
            self.tile(
                self.href(slug),
                self.title(frm, slug),
                self.title(to, slug),
                self.skel[slug].get("icon"),
                slug,
                self.levels["pages"].get(slug),
            )
            for slug in group["pages"] + group["links"]
        ]
        return head + self.tiles(pages, f"group-{gid}")

    def one_page(self, group):
        """A one-page group: each of its topics is an accordion, shut until opened, whose summary is the topic's tile (its icon
        and its name in both languages) and whose body is the topic as its own page would show it. The accordions carry the
        topics' levels and are what Settings' order puts in order, here on the page; the sections inside keep their written
        order. The pages the group links to follow as a row of tiles."""
        frm, to = self.frm, self.to
        folds = []
        for slug in group["pages"]:
            ident = f"{TOPIC_PREFIX}{slug}"
            icon = self.skel[slug].get("icon")
            l1, l2 = self.pair_spans(self.title(frm, slug), self.title(to, slug))
            summary = f'<h2 id="h-{ident}">{self.icon_html(icon) if icon else ""}<span class="topic-name">{l1}{l2}</span></h2>'
            lcode, lede = self.prose(lambda c: self.pack_page(c, slug).get("lede"))
            fig = self.skel[slug].get("figure")
            figure = FIGURES[fig](self, slug) if fig else ""
            shown = self.shown_sections(slug, figure)
            for hidden in self.sections(slug):
                if hidden not in shown:  # a section the figure stands in for keeps its address, here as on a page of its own
                    figure = f'<section id="{hidden["id"]}" class="figure">{figure}</section>'
            body = (
                (f'<p class="lede"{self.la(lcode)}>{e(lede)}</p>' if lede else "")
                + figure
                + "".join(self.render_section(slug, s, nested=True) for s in shown)
                + self.related_tiles(slug, ident=f"related-{slug}")
                + self.more_note(slug)
            )
            level = self.levels["pages"].get(slug)
            graded = f' data-level="{level}"' if level else ""
            folds.append(self.fold(summary, body, labelled=f"h-{ident}", attrs=f' id="{ident}"{graded}', cls="topic"))
        links = self.related_tiles(None, entries=group["links"]) if group["links"] else ""
        return f'<div class="topics">{"".join(folds)}</div>{self.ORDER_HOOK}{links}'

    def licence_html(self, key):
        """A licence by its proper name (linked when it has a page), or in words from the interface messages."""
        name, url = LICENCES[key]
        name = e(name) if name else self.h("licence_" + key.replace("-", "_"))
        return f'<a href="{e(url)}">{name}</a>' if url else name

    def source_counts(self, slug):
        """{(language, source id): number of concepts} for one page, over every language of the edition."""
        counts = {}
        for code in self.langs:
            pp = self.pack_page(code, slug)
            for sec in pp.get("sections", {}).values():
                for c in sec.get("concepts", {}).values():
                    key = (code, c.get("source") or pp["source"])
                    counts[key] = counts.get(key, 0) + 1
        return counts

    def sources_page(self):
        """One table per page: each source, its language, its licence and how many entries come from it."""
        sections = []
        for slug in self.sequence()[1:]:
            counts = self.source_counts(slug)
            rows = []
            for code in self.langs:
                for src in self.meta(code)["sources"]:
                    n = counts.get((code, src["id"]), 0)
                    if not n:
                        continue
                    title = e(src["title"])
                    if src.get("url"):
                        title = f'<a href="{e(src["url"])}">{title}</a>'
                    note = f'<small class="note">{e(src["note"])}</small>' if src.get("note") else ""
                    licence = self.licence_html(src["licence"])
                    rows.append(
                        f'<tr><th scope="row" class="l1">{title}{note}</th>'
                        f"<td>{self.inline(code, self.endonym(code))}</td>"
                        f"<td>{licence}</td><td>{n}</td></tr>"
                    )
            sections.append(
                f'<section id="{slug}"><h2>{self.inline(self.frm, self.title(self.frm, slug))}'
                f'<span class="l2"{self.la(self.to)}>{e(self.title(self.to, slug))}</span></h2>'
                f'<table class="terms"><thead><tr><th scope="col">{self.h("col_source")}</th>'
                f'<th scope="col">{self.h("col_language")}</th><th scope="col">{self.h("col_licence")}</th>'
                f'<th scope="col">{self.h("col_entries")}</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></section>'
            )
        second, lang2 = self.ui_text(self.to, "sources")
        head = (
            "<header>"
            f'<h1>{self.ui_html(self.frm, "sources")}</h1>'
            f'<p class="title-l2"{self.la(lang2)}>{e(second)}</p>'
            f'<p class="lede">{self.h("sources_lede")}</p></header>'
        )
        return head + "".join(sections)

    def theme_color(self):
        """The installed app's toolbar colour: the accent of the edition's default palette, light variant."""
        return colour.rgb_to_hex(palettes.resolve(self.palettes[self.default_palette])["light"]["accent"])

    def background_color(self):
        """The installed app's splash background: the background of the edition's default palette, light variant."""
        return colour.rgb_to_hex(palettes.resolve(self.palettes[self.default_palette])["light"]["bg"])

    def manifest(self):
        """A web app manifest so the site installs: relative start_url and scope work under any sub-path.

        start_url names index.html itself, not the bare directory ("./"): the service worker precaches
        files by name, and the cache only matches a request's exact URL, so a directory-style start_url
        would miss the cache and fail offline.
        """
        m = {
            "name": self.name,
            "short_name": self.edition.get("short_name", self.name),
            "start_url": "./index.html",
            "scope": "./",
            "display": "standalone",
            "lang": self.interface,
            "theme_color": self.theme_color(),
            "background_color": self.background_color(),
        }
        if self.dir_of(self.interface) == "rtl":
            m["dir"] = "rtl"
        icons = self.edition.get("icons")
        if icons:
            m["icons"] = icons
        return m

    def settings_page(self):
        """The visitor's choices, in groups (accessibility and appearance; order and tile layout; regional forms), on a page of their own. A toggle at the top
        right shows the page in one language of the pair at a time, with no script. Words only from messages."""
        radios, bar = self.language_toggle("settings-lang", [self.frm, self.to])
        head = (
            f'<div class="page-head"><header><h1>{self.both("settings")}</h1></header>{bar}</div>'
            f'<p class="lede">{self.both("settings_lede")}</p>'
        )
        about = ""
        if not self.edition.get("about_page"):  # with an About page, that is where How to use the app and Sources are linked
            links = "".join(
                f'<li><a href="{href}">{self.both(key)}</a></li>'
                for href, key in (("how-to.html", "how_to"), ("sources.html", "sources"))
            )
            about = self.fold(
                f'<h2>{self.both("about_app")}</h2>', f'<ul class="links">{links}</ul>', card=True, attrs=' id="about"'
            )
        body = (
            head
            + f'<section id="settings">{self.prefs_controls()}'
            + f'<noscript><p class="intro">{self.h("settings_no_script")}</p></noscript></section>'
            + about
        )
        return f'<div class="l10n">{radios}<div class="l10n-body">{body}</div></div>'

    def about_block(self, code, block):
        """One body block of an About section, in the language `code`."""
        if isinstance(block, str):
            return f"<p>{e(block)}</p>"
        kind, value = next(iter(block.items()))
        if kind == "list":
            return f'<ul class="notes">{"".join(f"<li>{e(item)}</li>" for item in value)}</ul>'
        if kind == "quote":
            return f'<blockquote class="principle"><p>{e(value)}</p></blockquote>'
        if kind == "links":
            items = "".join(f'<li><a href="{e(link["href"])}">{e(link["text"])}</a></li>' for link in value)
            return f'<ul class="links">{items}</ul>'
        copied = e(self.ui_text(code, "share_copied")[0])
        return (
            f'<p class="share-line"><a href="{e(value)}">{e(value)}</a> '
            f'<button type="button" class="share" data-url="{e(value)}" data-copied="{copied}" hidden>{self.ui_html(code, "share")}</button>'
            '<span class="share-status" role="status"></span></p>'
        )

    def about_page(self):
        """The About page: the aims and philosophy in each language the edition gives, one shown at a time. The choice is a group of
        radio buttons that a stylesheet turns into a toggle at the top, so it works with no script; the first language of the pair shows first.
        """
        about = self.edition["about_page"]
        codes = []
        for code in [self.frm, self.to, *self.langs]:
            if code in about and code not in codes:
                codes.append(code)
        radios = "".join(
            f'<input type="radio" class="about-radio" name="about-lang" id="about-lang-{e(code)}" value="{e(code)}"'
            f'{" checked" if i == 0 else ""}>'
            for i, code in enumerate(codes)
        )
        labels = "".join(f'<label for="about-lang-{e(code)}">{self.inline(code, self.endonym(code))}</label>' for code in codes)
        toggle = ""
        if len(codes) > 1:
            toggle = f'<div class="about-bar" role="group" aria-label="{e(self.plain("about_language"))}">{labels}</div>'
        articles = []
        for code in codes:
            page = about[code]
            parts = [f'<header><h1>{e(page["title"])}</h1>']
            if page.get("lede"):
                parts.append(f'<p class="lede">{e(page["lede"])}</p>')
            parts.append("</header>")
            sections = page["sections"]
            chosen = any("open" in s for s in sections)  # a project that says which sections are open decides for all of them
            for n, section in enumerate(sections):
                body = "".join(self.about_block(code, block) for block in section["body"])
                is_open = bool(section["open"]) if "open" in section else (n == 0 and not chosen)
                parts.append(self.fold(f'<h2>{e(section["title"])}</h2>', body, open_=is_open))
            parts.append(
                f'<p class="about-more"><a href="how-to.html">{self.ui_html(code, "how_to")}</a> · '
                f'<a href="sources.html">{self.ui_html(code, "sources")}</a></p>'
            )
            if self.built:
                # The label is in the article's language; the time is written the same in all of them, in UTC, so no month names.
                utc = self.built.astimezone(datetime.timezone.utc)
                parts.append(
                    f'<p class="about-built">{self.ui_html(code, "built")} '
                    f'<time datetime="{utc.strftime("%Y-%m-%dT%H:%M:%SZ")}">{utc.strftime("%Y-%m-%d %H:%M")} UTC</time></p>'
                )
            articles.append(f'<article class="about-text" id="about-{e(code)}"{self.la(code)}>{"".join(parts)}</article>')
        return f'<div class="about-page">{radios}{toggle}{"".join(articles)}</div>'

    # -- the help book (see help.py)

    def help_conditions(self):
        """What the edition has that a help feature can ask for."""
        many = len(self.palette_ids) > 1
        found = (
            ("about", bool(self.edition.get("about_page"))),
            ("varieties", self.has_varieties()),
            ("palettes", many),
            ("access", many and len(self.palette_levels()) > 1),
            ("levels", self.has_levels()),
            ("related", any(page.get("related") for page in self.skel.values())),
            ("keys", self.has_keys()),
            ("contact", bool(self.edition.get("contact"))),
        )
        return {name for name, on in found if on}

    def help_chapters(self):
        """The chapters this edition shows, each with only the features that apply to it."""
        return self.book.visible(self.help_conditions())

    def help_pair(self, kind, ident, field="title"):
        """A chapter's or feature's title in each language of the pair, as spans: the language's own, else English, marked as such."""
        spans, seen = [], []
        for cls, code in (("l1", self.frm), ("l2", self.to)):
            entry, lang = self.book.entry(code, kind, ident)
            if (lang, entry[field]) in seen:  # both languages fall back to the same English: say it once
                spans.append("")
            else:
                spans.append(f'<span class="{cls}"{self.la(lang)}>{e(entry[field])}</span>')
            seen.append((lang, entry[field]))
        return tuple(spans)

    def help_title(self, ident):
        """A chapter's title in the first language of the pair, as plain text."""
        return self.book.entry(self.frm, "chapters", ident)[0]["title"]

    def help_chapter_of(self, feature):
        """The chapter this edition shows a feature in, or None: a feature the edition lacks the thing for has no icon either."""
        return next((c["id"] for c in self.help_chapters() for f in c["features"] if f["id"] == feature), None)

    def help_icon(self, feature):
        """A question-mark link to a feature of the help book: hidden by the stylesheet until the rail's help button turns help on
        (help.js), and an ordinary link to help-<chapter>.html#<feature>. Nothing for a feature the edition does not show."""
        chapter = self.help_chapter_of(feature)
        if chapter is None:
            return ""
        title = self.book.entry(self.interface, "features", feature)[0]["title"]
        label = e(self.plain("help_icon", feature=title))
        return (
            f'<a class="help-icon" href="{HELP_PREFIX}{chapter}.html#{feature}" data-help="{chapter}#{feature}" '
            f'data-title="{e(title)}" aria-label="{label}" title="{label}">{self.ui_icons["help"]}</a>'
        )

    def help_status(self, name, key):
        """One message the script can show in a status line: all of them wait in the page, hidden, and help.js shows the one it
        wants. Each is in both languages of the pair, of which the Cy|En toggle shows one."""
        return f'<span data-msg="{name}" hidden>{self.both(key)}</span>'

    def help_card(self):
        """The sheet that a help icon opens, shut and hidden: What's this? (the text of one feature, loaded by help.js from the
        help book), and Report a problem (an email written in the person's mail app) where the edition has an address. The card has
        a Cy|En toggle like the Settings and About pages: the two languages of the pair are in the page, one is shown, and the choice
        is the one remembered for the whole site. The address is kept in two pieces so it does not sit in the page as a line a
        scraper would take. help.js fills the rest in."""
        contact = self.edition.get("contact") or ""
        user, _, host = contact.partition("@")
        built = self.built.strftime("%Y-%m-%d") if self.built else ""
        pair = f"{self.frm}>{self.to}"
        subject = self.plain("help_subject", site=self.name)
        data = (
            f' data-contact-user="{e(user)}" data-contact-host="{e(host)}" data-built="{e(built)}" data-pair="{e(pair)}"'
            f' data-subject="{e(subject)}"'
        )
        radios, bar = self.language_toggle("help-lang", [self.frm, self.to])
        close_name = e(
            " / ".join(self.ui_text(code, "help_close")[0] for code in (self.frm, self.to))
        )  # the x has no words, so its name has both
        sheet_buttons = f'<button type="button" data-act="help">{self.both("help_whats_this")}</button>'
        report_view = ""
        if contact:
            sheet_buttons += f'<button type="button" data-act="report">{self.both("help_report")}</button>'
            report_view = (
                '<div class="help-view" data-view="report" hidden>'
                f'<h3>{self.both("help_report")}</h3>'
                f'<p>{self.both("help_report_lede")}</p>'
                f'<label class="help-label">{self.both("help_report_words")}'
                '<textarea rows="4" data-report-words></textarea></label>'
                f'<label class="help-label">{self.both("help_report_context")}'
                '<textarea rows="4" readonly data-report-added></textarea></label>'
                f'<p class="help-actions"><a class="help-button" data-report-mail href="#">{self.both("help_open_email")}</a>'
                f'<button type="button" data-act="copy">{self.both("help_copy")}</button>'
                f'<button type="button" data-act="back">{self.both("back")}</button></p>'
                f'<p class="help-status" role="status" data-report-status>{self.help_status("copied", "help_copied")}'
                f'{self.help_status("copy-failed", "help_copy_failed")}</p></div>'
            )
        return (
            '<div class="help-layer" hidden>'
            f'<div class="help-card" id="help-card" role="dialog" aria-modal="true" aria-labelledby="help-card-title" inert{data}>'
            f'{radios}<div class="l10n-body">'
            f'<div class="help-head"><h2 id="help-card-title" data-title></h2>{bar}'
            f'<button type="button" class="help-close" data-act="close" aria-label="{close_name}" title="{close_name}">'
            f'{self.ui_icons["close"]}</button></div>'
            f'<div class="help-view" data-view="sheet"><p class="help-actions">{sheet_buttons}</p></div>'
            '<div class="help-view" data-view="help" hidden>'
            f'<p class="help-status" role="status" data-help-status>{self.help_status("loading", "help_loading")}'
            f'{self.help_status("failed", "help_failed")}</p><div data-help-body></div>'
            f'<p class="help-actions"><a class="help-button" data-help-more href="#">{self.both("help_more")}</a>'
            f'<button type="button" data-act="back">{self.both("back")}</button></p></div>'
            f"{report_view}"
            "</div></div></div>"
        )

    def help_slot(self, feature):
        """A line of its own for an icon that has no heading to sit beside; nothing, not even the line, without the icon."""
        icon = self.help_icon(feature)
        return f'<p class="help-slot">{icon}</p>' if icon else ""

    def how_to_page(self):
        """The contents of the help book: each chapter, with a link to each of its features."""
        second, lang2 = self.ui_text(self.to, "how_to")
        head = (
            "<header>"
            f'<h1>{self.ui_html(self.frm, "how_to")}</h1>'
            f'<p class="title-l2"{self.la(lang2)}>{e(second)}</p>'
            f'<p class="lede">{self.h("how_to_lede")}</p></header>'
        )
        chapters = []
        for chapter in self.help_chapters():
            first, second = self.help_pair("chapters", chapter["id"])
            features = "".join(
                f'<li><a href="{HELP_PREFIX}{chapter["id"]}.html#{feature["id"]}">{"".join(self.help_pair("features", feature["id"]))}</a></li>'
                for feature in chapter["features"]
            )
            chapters.append(
                f'<section><h2><a href="{HELP_PREFIX}{chapter["id"]}.html">{first}{second}</a></h2><ul class="links">{features}</ul></section>'
            )
        return head + f'<nav class="help-contents" aria-label="{e(self.plain("help_chapters_label"))}">{"".join(chapters)}</nav>'

    def help_chapter_page(self, ident):
        """One chapter: an article in each language that has help of its own (one shown at a time, as on the About page), and a
        section for each feature, with the feature's anchor as its id. With help in neither language of the pair, English."""
        chapter = next(c for c in self.help_chapters() if c["id"] == ident)
        codes = [code for code in (self.frm, self.to) if self.book.has_text(code)] or ["en"]
        radios = "".join(
            f'<input type="radio" class="about-radio" name="about-lang" id="about-lang-{e(code)}" value="{e(code)}"'
            f'{" checked" if i == 0 else ""}>'
            for i, code in enumerate(codes)
        )
        labels = "".join(
            f'<label for="about-lang-{e(code)}">{self.inline(code, self.endonym(code) if code in self.packs else code)}</label>'
            for code in codes
        )
        toggle = ""
        if len(codes) > 1:
            toggle = f'<div class="about-bar" role="group" aria-label="{e(self.plain("about_language"))}">{labels}</div>'
        articles = "".join(self.help_article(code, chapter, first=(i == 0)) for i, code in enumerate(codes))
        return f'<div class="about-page">{radios}{toggle}{articles}{self.help_pager(ident)}</div>'

    def help_article(self, code, chapter, first=True):
        """One language's article. Only the first article carries the plain anchors as ids, because an id may appear once on a page;
        the others take the language as a suffix (`tiles-en`) and every section names its feature in `data-feature`."""
        intro, intro_lang = self.book.entry(code, "chapters", chapter["id"])
        parts = [f'<header><h1{self.la(intro_lang, code)}>{e(intro["title"])}</h1>']
        if intro.get("lede"):
            parts.append(f'<p class="lede"{self.la(intro_lang, code)}>{e(intro["lede"])}</p>')
        parts.append("</header>")
        for feature in chapter["features"]:
            entry, lang = self.book.entry(code, "features", feature["id"])
            body = "".join(self.about_block(lang, block) for block in entry.get("body", []))
            ways = "".join(
                f"<dt>{self.ui_html(lang, key)}</dt><dd>{e(entry[field])}</dd>"
                for field, key in (("keys", "how_to_col_keys"), ("touch", "how_to_col_touch"))
                if entry.get(field)
            )
            ways = f'<dl class="help-ways">{ways}</dl>' if ways else ""
            parts.append(
                f'<section class="help-feature" id="{e(feature["id"] if first else feature["id"] + "-" + code)}" data-feature="{e(feature["id"])}"'
                f'{self.la(lang, code)}><h2>{e(entry["title"])}</h2>{body}{ways}</section>'
            )
        return f'<article class="about-text help-text" id="about-{e(code)}"{self.la(code)}>{"".join(parts)}</article>'

    def help_pager(self, ident):
        """Previous and next chapter, like a book. Nothing when the book has one chapter."""
        ids = [c["id"] for c in self.help_chapters()]
        i = ids.index(ident)

        def link(other, cls, key):
            first, second = self.help_pair("chapters", other)
            first, second = first.replace('class="l1"', 'class="t"'), second.replace('class="l2"', 'class="c"')
            return f'<a class="{cls}" href="{HELP_PREFIX}{other}.html"><small>{self.h(key)}</small>{first}{second}</a>'

        parts = []
        if i > 0:
            parts.append(link(ids[i - 1], "prev", "previous"))
        if i < len(ids) - 1:
            parts.append(link(ids[i + 1], "next", "next"))
        return f'<nav class="pager" aria-label="{e(self.plain("pager_label"))}">{"".join(parts)}</nav>' if parts else ""

    def storage_name(self):
        """The name this site keeps its saved choices under in the browser: the edition's `storage`, else its name as a slug."""
        named = self.edition.get("storage")
        if named:
            return named
        slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
        return slug if STORAGE_NAME.match(slug) else "phrasebook"

    def document(self, title, body, parent=None):
        # The script is blocking on purpose: it sets the saved preferences before the first paint.
        script = (
            '<script src="app.js"></script>\n<script src="order.js"></script>\n<script src="nav.js" defer></script>\n<script src="search.js" defer></script>\n'
            '<script src="arrange.js" defer></script>\n<script src="help.js" defer></script>\n'
        )
        fonts = "".join(f'<link rel="stylesheet" href="{e(href)}">\n' for href in self.edition.get("fonts", []))
        extra = '<link rel="stylesheet" href="varieties.css">\n' if self.has_varieties() else ""
        extra += "".join(f'<link rel="stylesheet" href="{e(href)}">\n' for href in self.edition.get("stylesheets", []))
        direction = ' dir="rtl"' if self.dir_of(self.interface) == "rtl" else ""
        storage = f' data-storage="{e(self.storage_name())}"'
        if self.default_palette != palettes.DEFAULT:
            storage += f' data-default-palette="{e(self.default_palette)}"'
        if parent:
            storage += f' data-parent="{e(parent)}"'
        # nav.js moves between pages by sliding the two together, and carries the way it went in the address: #slide=none when
        # the page that arrives is already where the move ended, #slide=forward or #slide=back when it could not set the other
        # page beside this one and the new page has to slide in itself. After it may come ;from=<page>, for a related topic, the
        # topic it was followed from (which this script keeps in the history entry, where the page's Back finds it, and which
        # survives a reload), and ;at=<id>, the section the address named, which is scrolled to once the page is there. This head
        # script reads the mark before the first paint, takes it out of the address, and either tells the browser's own move to
        # stand down (none) or, where the browser cannot move pages itself, slides this page in from the matching side. A page
        # reached any other way plays nothing. It does not depend on the referrer, and it stores nothing.
        slide = (
            "<script>(function(d,w){var m=/^#slide=(forward|back|none)((?:;(?:from|at)=[A-Za-z0-9._-]+)*)$/.exec(w.location.hash);"
            "if(!m)return;"
            "var f=/;from=([a-z0-9-]+\\.html)(?:;|$)/.exec(m[2]),a=/;at=([A-Za-z0-9._-]+)(?:;|$)/.exec(m[2]);"
            'try{w.history.replaceState(f?{from:f[1]}:null,"",w.location.pathname+w.location.search+(a?"#"+a[1]:""))}catch(err){};'
            'if(m[1]==="none")d.documentElement.setAttribute("data-slide","none");'
            'else if(!w.PageRevealEvent)d.documentElement.classList.add(m[1]==="back"?"slide-back":"slide-in");'
            'if(a)d.addEventListener("DOMContentLoaded",function(){var t=d.getElementById(a[1]);if(!t)return;'
            'for(var p=t;p;p=p.parentElement)if(p.tagName==="DETAILS")p.open=true;t.scrollIntoView()})'
            "})(document,window)</script>\n"
        )
        # Where the browser animates moves between pages itself (cross-document view transitions), say which way the page
        # moves: in from the end when this page's parent is the page we came from, in from the start when we came from
        # one of this page's own tiles. Any other move (a sibling, another site, a reload) plays nothing.
        slide += (
            '<script>(function(w,d){if(!("PageRevealEvent" in w))return;'
            'w.addEventListener("pagereveal",function(e){var t=e.viewTransition;if(!t)return;'
            '["ready","finished","updateCallbackDone"].forEach(function(k){if(t[k])t[k].catch(function(){})});'
            "var a=w.navigation&&w.navigation.activation,u=a&&a.from&&a.from.url,r=d.documentElement;"
            'if(r.getAttribute("data-slide")==="none"||!u||u.indexOf(location.origin)!==0)return t.skipTransition();'
            'var f=u.split("#")[0].split("?")[0].split("/").pop()||"index.html",p=r.getAttribute("data-parent"),'
            'g=[].some.call(d.querySelectorAll("[data-tiles] a"),function(x){return x.getAttribute("href")===f});'
            'if(p&&f===p)r.setAttribute("data-slide","forward");'
            'else if(g)r.setAttribute("data-slide","back");'
            "else t.skipTransition()})})(window,document)</script>\n"
        )
        icon = next((i for i in self.edition.get("icons", []) if i.get("purpose", "any") == "any"), None)
        touch_icon = f'<link rel="apple-touch-icon" href="{e(icon["src"])}">\n' if icon else ""
        # Deferred and best-effort: a site that fails to install still works as a normal page.
        register = (
            '<script>if("serviceWorker" in navigator){addEventListener("load",function(){'
            'navigator.serviceWorker.register("sw.js")});}</script>\n'
        )
        return (
            f'<!doctype html>\n<html lang="{e(self.interface)}"{direction}{storage}>\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f"{slide}<title>{e(title)}</title>\n"
            f'<link rel="manifest" href="manifest.json">\n'
            f'<meta name="theme-color" content="{self.theme_color()}">\n{touch_icon}'
            f"{script}{fonts}"
            f'<link rel="stylesheet" href="palettes.css">\n<link rel="stylesheet" href="style.css">\n{extra}'
            f"</head>\n<body>\n{body}\n{register}</body>\n</html>\n"
        )

    def render_all(self):
        """Return {filename: html} for every page."""

        def page(key, title, body, **shell):
            return self.document(title, self.shell(key, body, **shell), self.parent_of(key))

        out = {"index.html": page("index", self.name, self.home_page(), with_pager=False, wide=True)}
        for group in self.groups:
            key = f"group-{group['id']}"
            one = group["layout"] == "one-page"  # read like a topic: in the pager's run, and as wide as a topic
            out[f"{key}.html"] = page(
                key,
                self.plain("page_title", page=self.group_title(self.frm, group["id"]), site=self.name),
                self.group_page(group),
                with_pager=one,
                wide=not one,
            )
        for slug in self.slugs:
            if slug in self.homes:
                continue  # shown on its group's page
            out[f"{slug}.html"] = page(
                slug, self.plain("page_title", page=self.title(self.frm, slug), site=self.name), self.content_page(slug)
            )
        out["settings.html"] = page(
            "settings",
            self.plain("page_title", page=self.ui_text(self.frm, "settings")[0], site=self.name),
            self.settings_page(),
            with_pager=False,
        )
        if self.edition.get("about_page"):
            out["about.html"] = page(
                "about",
                self.plain("page_title", page=self.ui_text(self.frm, "about")[0], site=self.name),
                self.about_page(),
                with_pager=False,
            )
        for chapter in self.help_chapters():
            out[f"{HELP_PREFIX}{chapter['id']}.html"] = page(
                f"{HELP_PREFIX}{chapter['id']}",
                self.plain("page_title", page=self.help_title(chapter["id"]), site=self.name),
                self.help_chapter_page(chapter["id"]),
                with_pager=False,
            )
        out["how-to.html"] = page(
            "how-to",
            self.plain("page_title", page=self.ui_text(self.frm, "how_to")[0], site=self.name),
            self.how_to_page(),
            with_pager=False,
        )
        out["sources.html"] = page(
            "sources",
            self.plain("page_title", page=self.ui_text(self.frm, "sources")[0], site=self.name),
            self.sources_page(),
            with_pager=False,
        )
        return out
