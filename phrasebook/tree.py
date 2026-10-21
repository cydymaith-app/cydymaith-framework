"""The map of the site: group, page, section, word, each with an internal address (1, 1.2, 1.2.3, 1.2.3.4).

Built from a Site, so it follows the language pair, the interface language and the release channel, and written to
tree.json. The pages themselves are the navigation (a group is a page of tiles, a topic is a page), so nothing on screen
reads this file today. It is what a search will use to place a result in the site, and what any other client of the
content can read. The address is never shown to a person. Nothing here knows which languages or phrases a project holds.

Each node: id, level, icon (a name, for groups and pages), first and second (the label in each language of the pair,
with its language and direction), href (a page, a section or one word; groups have none) and children.
"""


def label(site, code, text):
    return {"text": text, "lang": code, "dir": site.dir_of(code)}


def build(site):
    """The tree as nested dicts, ready for json."""
    frm, to = site.frm, site.to

    def node(nid, level, first, second, href=None, icon=None, children=None):
        return {"id": nid, "level": level, "icon": icon, "first": first, "second": second, "href": href,
                "children": children or []}

    groups = []
    for gi, group in enumerate(site.groups, 1):
        pages = []
        for pi, slug in enumerate(group["pages"], 1):
            sections = []
            for si, section in enumerate(site.sections(slug), 1):
                sid = section["id"]
                words = []
                for wi, cid in enumerate(site.rows(slug, section), 1):
                    text_from = site.forms_of(site.concept(frm, slug, sid, cid))[0]["text"]
                    text_to = site.forms_of(site.concept(to, slug, sid, cid))[0]["text"]
                    words.append(node(f"{gi}.{pi}.{si}.{wi}", "word", label(site, frm, text_from), label(site, to, text_to),
                                      href=f"{slug}.html#{sid}.{cid}"))
                sections.append(node(
                    f"{gi}.{pi}.{si}", "section",
                    label(site, frm, site.pack_section(frm, slug, sid)["title"]),
                    label(site, to, site.pack_section(to, slug, sid)["title"]),
                    href=f"{slug}.html#{sid}", children=words))
            pages.append(node(
                f"{gi}.{pi}", "page", label(site, frm, site.title(frm, slug)), label(site, to, site.title(to, slug)),
                href=f"{slug}.html", icon=site.skel[slug].get("icon"), children=sections))
        groups.append(node(
            str(gi), "group", label(site, frm, site.group_title(frm, group["id"])),
            label(site, to, site.group_title(to, group["id"])), icon=group.get("icon"), children=pages))
    return groups


def document(site):
    """The whole map, with the markup of the icons it names, as one json-ready dict."""
    nodes = build(site)
    used = set()

    def collect(items):
        for item in items:
            if item["icon"]:
                used.add(item["icon"])
            collect(item["children"])

    collect(nodes)
    return {"version": 1, "lang": site.interface, "dir": site.dir_of(site.interface),
            "icons": {name: site.icons[name] for name in sorted(used)}, "nodes": nodes}
