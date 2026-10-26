"""The lookup dictionary: every concept of the edition's languages, with the pages it appears on.

The build writes it as dictionary.json on every run, so adding or editing a page updates the dictionary with
no separate step. Nothing is hand-edited; the packs and page skeletons are the only source.

    {"languages": ["aa", "bb"],
     "entries": [{"concept": "rain",
                  "terms": {"aa": [{"text": "Rain", "varieties": []}], "bb": [{"text": "Glaw", "varieties": []}]},
                  "also": {"bb": ["law"]},
                  "pages": [{"slug": "weather", "href": "weather.html#types.rain",
                             "title": {"aa": "Types of weather", "bb": "Mathau o dywydd"}}]}]}

Each page lists where the word is: href is the page with the id of the word's row (section id, a dot, the concept), so a
link lands on the word. A page shown inside a one-page group's page links there instead (group-<id>.html#section.concept),
and adds "topic", the address of its accordion, for the list of topics. Entries follow the order of the pages in structure.json. Braces that mark the language's own text in notes
are removed, so a term is the plain word or phrase. "also" holds the other forms a word is heard as (a changed beginning, a
plural), by language. Search matches them but shows only the terms, so a person who heard "law" finds "glaw".
"""

from .content import address, one_page_homes, pages_in_order

BRACES = ("{{", "}}")


def _plain(text):
    return text.replace(BRACES[0], "").replace(BRACES[1], "")


def _terms(concept):
    """The texts of one concept in one language, as a list of {text, varieties}."""
    if "forms" in concept:
        return [{"text": _plain(f["text"]), "varieties": list(f.get("varieties", []))} for f in concept["forms"]]
    return [{"text": _plain(concept["text"]), "varieties": []}]


def index(raw, edition):
    """Build the dictionary for an edition. Returns a dict ready to write as JSON."""
    languages = list(edition["languages"])
    entries = {}
    structure = raw["structure"]
    homes = one_page_homes(structure)
    for slug in pages_in_order(raw):
        page = raw["pages"][slug]
        titles = {code: raw["packs"][code]["pages"][slug]["title"] for code in languages if slug in raw["packs"][code]["pages"]}
        for section in page["sections"]:
            for cid in section["concepts"]:
                entry = entries.setdefault(cid, {"concept": cid, "terms": {}, "pages": []})
                for code in languages:
                    pack_page = raw["packs"][code]["pages"].get(slug, {})
                    concept = pack_page.get("sections", {}).get(section["id"], {}).get("concepts", {}).get(cid)
                    if concept and code not in entry["terms"]:
                        entry["terms"][code] = _terms(concept)
                        if concept.get("also"):
                            entry.setdefault("also", {})[code] = [_plain(a) for a in concept["also"]]
                if not any(p["slug"] == slug for p in entry["pages"]):
                    found = {"slug": slug, "href": address(structure, slug, f"{section['id']}.{cid}"), "title": titles}
                    if slug in homes:  # on a one-page group the topic is an accordion of the group's page, not a page of its own
                        found["topic"] = address(structure, slug)
                    entry["pages"].append(found)
    return {"languages": languages, "entries": list(entries.values())}
