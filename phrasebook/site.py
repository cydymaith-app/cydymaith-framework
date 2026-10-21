"""Renders one edition of a project, for one pair of languages, into HTML.

Roles, not languages: the first language of the pair ("l1", the left column in a left-to-right interface)
and the second ("l2"). Nothing here knows what the languages are. Every word the framework shows itself
comes from messages.py; every word of the phrasebook comes from the language packs.

Language and direction: text in a language other than the one around it carries lang="..." and, when the
writing direction differs, dir="...". The document itself carries the interface language and direction.
"""
import html
import json
import pathlib
import re

from . import colour, icons, palettes
from .figures import FIGURES
from .content import LICENCES, STORAGE_NAME
from .messages import Messages

UI_ICONS = pathlib.Path(__file__).resolve().parent / "ui-icons"  # the framework's own chrome icons, apart from any project's

e = html.escape
MARK = re.compile(r"\{\{(.+?)\}\}")


class Site:
    """Renders one edition for one pair of languages: `frm` is shown first, `to` second."""

    def __init__(self, raw, edition, pair=None, messages=None):
        self.raw = raw
        self.edition = edition
        self.name = edition["name"]
        self.langs = edition["languages"]
        self.interface = edition["interface"]
        self.frm, self.to = pair or edition["default_pair"]
        self.skel = raw["pages"]
        self.packs = raw["packs"]
        self.messages = messages or Messages(raw["packs"])
        self.palettes = raw["palettes"]
        self.palette_ids = edition.get("palettes") or list(self.palettes)
        # Only pages with at least one row available in both languages are published for this pair.
        self.slugs = [s for g in raw["structure"]["groups"] for s in g["pages"] if self.count_entries(s)]
        self.icons = {name: icons.markup(text) for name, text in raw["icons"].items()}
        self.ui_icons = {f.stem: icons.markup(f.read_text(encoding="utf-8")) for f in sorted(UI_ICONS.glob("*.svg"))}
        self.groups = [{"id": g["id"], "icon": g.get("icon"), "pages": [s for s in g["pages"] if s in self.slugs]}
                       for g in raw["structure"]["groups"]]
        self.groups = [g for g in self.groups if g["pages"]]

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
            return [{"text": f["text"], "varieties": list(f.get("varieties", [])), "note": f.get("note")}
                    for f in concept["forms"]]
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

    def form_markup(self, code, form, show, cls):
        names = {v["id"]: v for v in self.varieties(code)}
        tags = "".join(f'<abbr class="vtag" title="{e(names[v]["name"])}">{e(names[v]["short"])}</abbr>'
                       for v in form["varieties"])
        note = f'<small class="note">{self.markup(code, form["note"])}</small>' if form["note"] else ""
        cls_attr = f' class="{cls}"' if cls else ""
        return (f'<span class="form" data-lang="{e(code)}" data-show="{" ".join(show)}">'
                f'<span{cls_attr}{self.la(code)}>{e(form["text"])}</span>{tags}{note}</span>')

    def is_plain(self, forms):
        return len(forms) == 1 and not forms[0]["varieties"] and not forms[0]["note"]

    def varieties_css(self):
        """Dim the forms that do not apply to the variety chosen for a language. Generated from the packs."""
        rules = []
        for code in self.langs:
            for v in self.varieties(code):
                rules.append(f'html[data-v-{code}="{v["id"]}"] .form[data-lang="{code}"]'
                             f':not([data-show~="{v["id"]}"]){{opacity:.55;font-size:.92em}}')
        return "/* Generated by the phrasebook builder from the varieties in the packs. Do not edit. */\n" + "\n".join(rules) + "\n"

    APPEARANCES = ("system", "light", "dark")

    def palette_label(self, pid):
        """A palette's name for the interface: (text, language it is written in)."""
        names = self.palettes[pid].get("names", {})
        if self.interface in names:
            return names[self.interface], self.interface
        key = "palette_" + pid.replace("-", "_")
        if self.messages.has(key):
            return self.messages.format(self.interface, key)
        if "en" in names:
            return names["en"], "en"
        if names:
            code, text = next(iter(names.items()))
            return text, code
        return pid, self.interface

    @staticmethod
    def radio(name, value, label, attrs, checked):
        return (f'<label><input type="radio" name="{name}" value="{value}" {attrs}'
                f'{" checked" if checked else ""}> {label}</label>')

    def theme_controls(self):
        """Light or dark, and a colour palette. The palette choice appears only when the edition offers more than one."""
        appearance = "".join(
            self.radio("appearance", v, self.h("appearance_" + v), 'data-pref="appearance"', v == "system")
            for v in self.APPEARANCES)
        fields = [f'<fieldset class="pref"><legend>{self.h("appearance")}</legend>{appearance}</fieldset>']
        if len(self.palette_ids) > 1:
            choices = "".join(
                self.radio("palette", pid, self.inline(*self.palette_label(pid)[::-1]), 'data-pref="palette"',
                           pid == palettes.DEFAULT)
                for pid in self.palette_ids)
            fields.append(f'<fieldset class="pref"><legend>{self.h("colours")}</legend>{choices}</fieldset>')
        return "".join(fields)

    def variety_fields(self):
        """A choice per displayed language that has varieties."""
        fields = []
        for code in (self.frm, self.to):
            varieties = self.varieties(code)
            if not varieties:
                continue
            options = [("all", e(self.plain("variety_all")))] + [(v["id"], self.commentary(code, v["name"])) for v in varieties]
            radios = "".join(
                f'<label><input type="radio" name="variety-{e(code)}" value="{vid}" data-variety-lang="{e(code)}"'
                f'{" checked" if vid == "all" else ""}> {label}</label>' for vid, label in options)
            legend = self.h("regional_forms", language=e(self.language_name(code)))
            fields.append(f'<fieldset class="pref"><legend>{legend}</legend>{radios}</fieldset>')
        return "".join(fields)

    def prefs_controls(self):
        """Every choice the visitor can make. Hidden until app.js runs, so it is never a dead control."""
        return f'<div class="prefs" id="prefs" hidden>{self.theme_controls()}{self.variety_fields()}</div>'

    def palettes_css(self):
        return palettes.css(self.palettes, self.palette_ids)

    # -- structure

    def rows(self, slug, section):
        """Concept ids of a section that exist in both languages of the pair."""
        return [cid for cid in section["concepts"]
                if self.concept(self.frm, slug, section["id"], cid) and self.concept(self.to, slug, section["id"], cid)]

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

    def prose(self, getter):
        """First (code, text) from the pair, then the rest of the edition, where getter returns something."""
        for code in [self.frm, self.to] + [c for c in self.langs if c not in (self.frm, self.to)]:
            v = getter(code)
            if v:
                return code, v
        return None, None

    def brand_small(self):
        return self.h("pair_label", first=self.inline(self.frm, self.endonym(self.frm)),
                      second=self.inline(self.to, self.endonym(self.to)))

    # -- navigation

    def pager(self, current):
        seq = self.sequence()
        i = seq.index(current)

        def link(slug, cls, key):
            if slug == "index":
                t = self.ui_text(self.frm, "main_menu")
                c = self.ui_text(self.to, "main_menu")
                first = f'<span class="t"{self.la(t[1])}>{e(t[0])}</span>'
                second = f'<span class="c"{self.la(c[1])}>{e(c[0])}</span>'
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
        return f'<nav class="pager" aria-label="{e(self.plain("pager_label"))}">{"".join(parts)}</nav>'

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
            gid = current[len("group-"):]
            steps.append((None, self.pair_spans(self.group_title(frm, gid), self.group_title(to, gid))))
        elif current in self.slugs:
            gid = self.group_of(current)["id"]
            steps.append((f"group-{gid}.html", self.pair_spans(self.group_title(frm, gid), self.group_title(to, gid))))
            steps.append((None, self.pair_spans(self.title(frm, current), self.title(to, current))))
        elif current == "settings":
            steps.append((None, self.ui_pair("settings")))
        else:  # the how-to and sources pages sit under settings
            steps += [("settings.html", self.ui_pair("settings")), (None, self.ui_pair("how_to" if current == "how-to" else current))]
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
        back = (f'<a class="rail-link back" href="{steps[-2][0]}" data-back aria-label="{name}" title="{name}">'
                f'{self.ui_icons["arrow--left"]}</a>')
        items = []
        for href, (first, second) in steps:
            inner = f"{first}{second}"
            items.append(f'<li><a href="{href}">{inner}</a></li>' if href else f'<li><span aria-current="page">{inner}</span></li>')
        return back, f'<nav aria-label="{e(self.plain("trail_label"))}"><ol class="trail">{"".join(items)}</ol></nav>'

    def tile(self, href, first, second, icon):
        """A large touch target: the icon on a tile, with the name in both languages beneath. No icon, the name goes in the tile."""
        l1, l2 = self.pair_spans(first, second)
        inner = self.icon_html(icon) or f'<span class="tile-text" aria-hidden="true">{e(first)}</span>'
        return (f'<li><a class="tile-link" href="{href}"><span class="tile">{inner}</span>'
                f'<span class="tile-name">{l1}{l2}</span></a></li>')

    def tiles(self, items):
        return f'<ul class="tiles" data-tiles aria-label="{e(self.plain("topics_label"))}">{"".join(items)}</ul>'

    # -- pages

    def render_section(self, slug, section):
        frm, to, sid = self.frm, self.to, section["id"]
        rows = []
        for cid in self.rows(slug, section):
            cf, ct = self.concept(frm, slug, sid, cid), self.concept(to, slug, sid, cid)
            notes = "".join(f'<small class="note">{self.markup(code, c["note"])}</small>'
                            for code, c in ((frm, cf), (to, ct)) if c.get("note"))
            ff, ft = self.forms_of(cf), self.forms_of(ct)
            if self.is_plain(ff):
                head = f'<th scope="row" class="l1"{self.la(frm)}>{e(ff[0]["text"])}</th>'
            else:
                forms = "".join(self.form_markup(frm, f, s, None) for f, s in zip(ff, self.show_sets(frm, ff)))
                head = f'<th scope="row" class="l1"><span class="forms">{forms}</span></th>'
            if self.is_plain(ft):
                cell = f'<span class="l2"{self.la(to)}>{e(ft[0]["text"])}</span>'
            else:
                forms = "".join(self.form_markup(to, f, s, "l2") for f, s in zip(ft, self.show_sets(to, ft)))
                cell = f'<span class="forms">{forms}</span>'
            rows.append(f'<tr id="{sid}.{cid}">{head}<td>{cell}{notes}</td></tr>')
        intro = "".join(f'<p class="intro">{self.markup(code, sec["intro"])}</p>'
                        for code in (frm, to) for sec in [self.pack_section(code, slug, sid)] if sec.get("intro"))
        box = "".join(f'<div class="box"><h3>{self.commentary(code, sec["box"]["title"])}</h3><p>{self.markup(code, sec["box"]["body"])}</p></div>'
                      for code in (frm, to) for sec in [self.pack_section(code, slug, sid)] if sec.get("box"))
        return (f'<section id="{sid}"><h2>{self.inline(frm, self.pack_section(frm, slug, sid)["title"])}'
                f'<span class="l2"{self.la(to)}>{e(self.pack_section(to, slug, sid)["title"])}</span></h2>{intro}'
                f'<table class="terms"><thead><tr><th scope="col">{self.inline(frm, self.endonym(frm))}</th>'
                f'<th scope="col">{self.inline(to, self.endonym(to))}</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table>{box}</section>')

    def search_card(self):
        """The dictionary lookup card, shut and hidden. search.js reveals the layer and the rail button, and fills the results
        from dictionary.json as the person types, so without scripts there is no control that does nothing."""
        pair = json.dumps([[self.frm, self.dir_of(self.frm)], [self.to, self.dir_of(self.to)]])
        hint = self.plain("search_hint", first=self.endonym(self.frm), second=self.endonym(self.to))
        name = e(self.plain("search"))
        return (
            '<div class="search-layer" hidden>'
            f'<div class="search-card" id="search-card" role="search" aria-label="{name}" inert '
            f'data-dictionary="dictionary.json" data-pair="{e(pair)}" data-hint="{e(hint)}" '
            f'data-none="{e(self.plain("search_none"))}" data-error="{e(self.plain("search_error"))}">'
            '<div class="search-head"><label class="search-field">'
            f'<span class="sr-only">{name}</span>'
            f'<input id="search-input" type="search" placeholder="{e(self.plain("search_placeholder"))}" autocomplete="off" '
            'autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="search"></label>'
            f'<button type="button" class="search-close">{e(self.plain("search_close"))}</button></div>'
            '<p class="search-status" id="search-status" role="status"></p>'
            '<div class="search-body"><ul class="search-results" id="search-results"></ul>'
            f'<h2 class="search-topics" hidden>{e(self.plain("search_topics"))}</h2>'
            '<ul class="search-pages" id="search-pages"></ul></div>'
            '</div></div>'
        )

    def shell(self, current, content, with_pager=True, wide=False):
        """The frame around every page: a title bar across the top (title and trail), then a rail (search, Back, settings) and the page."""
        pager = self.pager(current) if with_pager else ""
        back, trail = self.top_bar(current)
        current_mark = ' aria-current="page"' if current == "settings" else ""
        settings = (f'<a class="rail-link" href="settings.html" aria-label="{e(self.plain("settings"))}"{current_mark}>'
                    f'{self.ui_icons["settings"]}</a>')
        search_name = e(self.plain("search"))
        search = (f'<button type="button" class="rail-link search" id="search-button" hidden aria-label="{search_name}" '
                  f'title="{search_name}" aria-expanded="false" aria-controls="search-card">{self.ui_icons["search"]}</button>')
        return (
            f'<a class="skip" href="#main">{self.h("skip_to_content")}</a>'
            '<div class="app">'
            f'<header class="topbar"><div class="titles{" has-trail" if trail else ""}"><a class="brand" href="index.html"><span class="word">{e(self.name)}</span>'
            f'<small>{self.brand_small()}</small></a>{trail}</div></header>'
            f'<nav class="rail" aria-label="{e(self.plain("settings"))}"><div class="rail-group">{search}{back}</div>{settings}</nav>'
            f'<main id="main"><div class="{"page wide" if wide else "page"}">{content}{pager}</div></main>'
            f'{self.search_card()}'
            '</div>'
        )

    def content_page(self, slug):
        frm, to = self.frm, self.to
        sections = self.sections(slug)
        jump = ""
        if len(sections) >= 3:
            jump = (f'<ul class="jump" aria-label="{e(self.plain("on_this_page"))}">'
                    + "".join(f'<li><a href="#{s["id"]}">{self.inline(frm, self.pack_section(frm, slug, s["id"])["title"])}</a></li>'
                              for s in sections)
                    + "</ul>")
        fig = self.skel[slug].get("figure")
        figure = FIGURES[fig](self, slug) if fig else ""
        lcode, lede = self.prose(lambda c: self.pack_page(c, slug).get("lede"))
        lede_html = f'<p class="lede"{self.la(lcode)}>{e(lede)}</p>' if lede else ""
        head = (f'<header><h1>{self.inline(frm, self.title(frm, slug))}</h1>'
                f'<p class="title-l2"{self.la(to)}>{e(self.title(to, slug))}</p>'
                f'{lede_html}</header>')
        return head + figure + jump + "".join(self.render_section(slug, s) for s in sections)

    def home_page(self):
        frm, to = self.frm, self.to
        home = self.edition.get("home", {})
        groups = [self.tile(f"group-{g['id']}.html", self.group_title(frm, g["id"]), self.group_title(to, g["id"]), g.get("icon"))
                  for g in self.groups]
        lcode, lede = self.prose(lambda c: home.get("lede", {}).get(c))
        acode, about = self.prose(lambda c: home.get("about", {}).get(c))
        link = f'<a href="sources.html">{self.h("sources_link")}</a>'
        return (
            f'<header><p class="kicker">{self.ui_html(frm, "phrasebook")} / {self.ui_html(to, "phrasebook")}</p>'
            f'<h1>{self.inline(frm, home["headline"][frm])}</h1>'
            f'<p class="title-l2"{self.la(to)}>{e(home["headline"][to])}</p>'
            f'<p class="lede">{self.inline(lcode, lede) if lede else ""}</p></header>'
            + self.tiles(groups)
            + f'<p class="about">{self.h("home_about", about=self.inline(acode, about) if about else "", link=link)}</p>'
        )

    def group_page(self, group):
        """One group's topics as tiles."""
        frm, to, gid = self.frm, self.to, group["id"]
        head = (f'<header><h1>{self.inline(frm, self.group_title(frm, gid))}</h1>'
                f'<p class="title-l2"{self.la(to)}>{e(self.group_title(to, gid))}</p></header>')
        pages = [self.tile(f"{slug}.html", self.title(frm, slug), self.title(to, slug), self.skel[slug].get("icon"))
                 for slug in group["pages"]]
        return head + self.tiles(pages)

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
                    rows.append(f'<tr><th scope="row" class="l1">{title}{note}</th>'
                                f'<td>{self.inline(code, self.endonym(code))}</td>'
                                f'<td>{licence}</td><td>{n}</td></tr>')
            sections.append(
                f'<section id="{slug}"><h2>{self.inline(self.frm, self.title(self.frm, slug))}'
                f'<span class="l2"{self.la(self.to)}>{e(self.title(self.to, slug))}</span></h2>'
                f'<table class="terms"><thead><tr><th scope="col">{self.h("col_source")}</th>'
                f'<th scope="col">{self.h("col_language")}</th><th scope="col">{self.h("col_licence")}</th>'
                f'<th scope="col">{self.h("col_entries")}</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></section>')
        second, lang2 = self.ui_text(self.to, "sources")
        head = ('<header>'
                f'<h1>{self.ui_html(self.frm, "sources")}</h1>'
                f'<p class="title-l2"{self.la(lang2)}>{e(second)}</p>'
                f'<p class="lede">{self.h("sources_lede")}</p></header>')
        return head + "".join(sections)

    def theme_color(self):
        """The installed app's toolbar colour: the accent of the default palette, light variant."""
        return colour.rgb_to_hex(palettes.resolve(self.palettes[palettes.DEFAULT])["light"]["accent"])

    def background_color(self):
        """The installed app's splash background: the background of the default palette, light variant."""
        return colour.rgb_to_hex(palettes.resolve(self.palettes[palettes.DEFAULT])["light"]["bg"])

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
        """The visitor's choices (appearance, colours, regional forms), on a page of their own. Words only from messages."""
        second, lang2 = self.ui_text(self.to, "settings")
        head = ('<header>'
                f'<h1>{self.ui_html(self.frm, "settings")}</h1>'
                f'<p class="title-l2"{self.la(lang2)}>{e(second)}</p>'
                f'<p class="lede">{self.h("settings_lede")}</p></header>')
        about = (f'<section id="about"><h2>{self.h("about_app")}</h2><ul class="links">'
                 + "".join(f'<li><a href="{href}">{l1}{l2}</a></li>'
                           for href, key in (("how-to.html", "how_to"), ("sources.html", "sources"))
                           for l1, l2 in [self.ui_pair(key)])
                 + "</ul></section>")
        return (head + f'<section id="settings">{self.prefs_controls()}'
                f'<noscript><p class="intro">{self.h("settings_no_script")}</p></noscript></section>' + about)

    def how_to_page(self):
        """How to move through the tree: keys, touch and buttons. Words only from the interface messages."""
        h = self.h
        moves = "".join(
            f'<tr><th scope="row" class="l1">{h("how_to_move_" + m)}</th><td>{h("how_to_keys_" + m)}</td>'
            f'<td>{h("how_to_touch_" + m)}</td></tr>' for m in ("open", "back", "along", "settings"))
        second, lang2 = self.ui_text(self.to, "how_to")
        head = ('<header>'
                f'<h1>{self.ui_html(self.frm, "how_to")}</h1>'
                f'<p class="title-l2"{self.la(lang2)}>{e(second)}</p>'
                f'<p class="lede">{h("how_to_lede")}</p></header>')
        tree = f'<section id="tree"><h2>{h("how_to_tree_title")}</h2><p class="intro">{h("how_to_tree")}</p></section>'
        table = (f'<section id="moves"><h2>{h("how_to_moves_title")}</h2>'
                 f'<table class="terms"><thead><tr><th scope="col">{h("how_to_col_move")}</th>'
                 f'<th scope="col">{h("how_to_col_keys")}</th><th scope="col">{h("how_to_col_touch")}</th></tr></thead>'
                 f'<tbody>{moves}</tbody></table></section>')
        notes = "".join(f"<li>{h(key)}</li>" for key in ("how_to_note_edge", "how_to_note_reader", "how_to_note_offline"))
        return head + tree + table + f'<section id="notes"><h2>{h("how_to_notes_title")}</h2><ul class="notes">{notes}</ul></section>'

    def storage_name(self):
        """The name this site keeps its saved choices under in the browser: the edition's `storage`, else its name as a slug."""
        named = self.edition.get("storage")
        if named:
            return named
        slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
        return slug if STORAGE_NAME.match(slug) else "phrasebook"

    def document(self, title, body, parent=None):
        # The script is blocking on purpose: it sets the saved preferences before the first paint.
        script = '<script src="app.js"></script>\n<script src="nav.js" defer></script>\n<script src="search.js" defer></script>\n'
        fonts = "".join(f'<link rel="stylesheet" href="{e(href)}">\n' for href in self.edition.get("fonts", []))
        extra = '<link rel="stylesheet" href="varieties.css">\n' if self.has_varieties() else ""
        extra += "".join(f'<link rel="stylesheet" href="{e(href)}">\n' for href in self.edition.get("stylesheets", []))
        direction = ' dir="rtl"' if self.dir_of(self.interface) == "rtl" else ""
        storage = f' data-storage="{e(self.storage_name())}"'
        # A page reached from its parent slides in from the side. Decided in the head, before the first paint, so the card
        # never flashes into place first. Arriving any other way (a sibling, a reload from elsewhere, Back) plays nothing.
        slide = ""
        if parent:
            storage += f' data-parent="{e(parent)}"'
            slide = ('<script>(function(d){var p=d.documentElement.getAttribute("data-parent"),r=d.referrer;'
                     'if(!p||r.indexOf(location.origin)!==0||window.PageRevealEvent)return;'
                     'if((r.split("#")[0].split("?")[0].split("/").pop()||"index.html")===p)'
                     'd.documentElement.classList.add("slide-in")})(document)</script>\n')
        # Where the browser animates moves between pages itself (cross-document view transitions), say which way the page
        # moves: in from the end when this page's parent is the page we came from, in from the start when we came from
        # one of this page's own tiles. Any other move (a sibling, another site, a reload) plays nothing.
        slide += ('<script>(function(w,d){if(!("PageRevealEvent" in w))return;'
                  'w.addEventListener("pagereveal",function(e){var t=e.viewTransition;if(!t)return;'
                  '["ready","finished","updateCallbackDone"].forEach(function(k){if(t[k])t[k].catch(function(){})});'
                  'var a=w.navigation&&w.navigation.activation,u=a&&a.from&&a.from.url,r=d.documentElement;'
                  'if(!u||u.indexOf(location.origin)!==0)return t.skipTransition();'
                  'var f=u.split("#")[0].split("?")[0].split("/").pop()||"index.html",p=r.getAttribute("data-parent"),'
                  'g=[].some.call(d.querySelectorAll("[data-tiles] a"),function(x){return x.getAttribute("href")===f});'
                  'if(p&&f===p)r.setAttribute("data-slide","forward");'
                  'else if(g)r.setAttribute("data-slide","back");'
                  'else t.skipTransition()})})(window,document)</script>\n')
        icon = next((i for i in self.edition.get("icons", []) if i.get("purpose", "any") == "any"), None)
        touch_icon = f'<link rel="apple-touch-icon" href="{e(icon["src"])}">\n' if icon else ""
        # Deferred and best-effort: a site that fails to install still works as a normal page.
        register = ('<script>if("serviceWorker" in navigator){addEventListener("load",function(){'
                    'navigator.serviceWorker.register("sw.js")});}</script>\n')
        return (f"<!doctype html>\n<html lang=\"{e(self.interface)}\"{direction}{storage}>\n<head>\n<meta charset=\"utf-8\">\n"
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                f"{slide}<title>{e(title)}</title>\n"
                f'<link rel="manifest" href="manifest.json">\n'
                f'<meta name="theme-color" content="{self.theme_color()}">\n{touch_icon}'
                f"{script}{fonts}"
                f'<link rel="stylesheet" href="palettes.css">\n<link rel="stylesheet" href="style.css">\n{extra}'
                f"</head>\n<body>\n{body}\n{register}</body>\n</html>\n")

    def render_all(self):
        """Return {filename: html} for every page."""
        def page(key, title, body, **shell):
            return self.document(title, self.shell(key, body, **shell), self.parent_of(key))

        out = {"index.html": page("index", self.name, self.home_page(), with_pager=False, wide=True)}
        for group in self.groups:
            key = f"group-{group['id']}"
            out[f"{key}.html"] = page(key, self.plain("page_title", page=self.group_title(self.frm, group["id"]), site=self.name),
                                      self.group_page(group), with_pager=False, wide=True)
        for slug in self.slugs:
            out[f"{slug}.html"] = page(slug, self.plain("page_title", page=self.title(self.frm, slug), site=self.name),
                                       self.content_page(slug))
        out["settings.html"] = page("settings", self.plain("page_title", page=self.ui_text(self.frm, "settings")[0], site=self.name),
                                    self.settings_page(), with_pager=False)
        out["how-to.html"] = page("how-to", self.plain("page_title", page=self.ui_text(self.frm, "how_to")[0], site=self.name),
                                  self.how_to_page(), with_pager=False)
        out["sources.html"] = page("sources", self.plain("page_title", page=self.ui_text(self.frm, "sources")[0], site=self.name),
                                   self.sources_page(), with_pager=False)
        return out
