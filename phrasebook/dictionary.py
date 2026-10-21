"""The lookup dictionary: every concept of the edition's languages, with the pages it appears on.

The build writes it as dictionary.json on every run, so adding or editing a page updates the dictionary with
no separate step. Nothing is hand-edited; the packs and page skeletons are the only source.

    {"languages": ["aa", "bb"],
     "entries": [{"concept": "rain",
                  "terms": {"aa": [{"text": "Rain", "varieties": []}], "bb": [{"text": "Glaw", "varieties": []}]},
                  "pages": [{"slug": "weather", "href": "weather.html#types.rain",
                             "title": {"aa": "Types of weather", "bb": "Mathau o dywydd"}}]}]}

Each page lists where the word is: href is the page with the id of the word's row (section id, a dot, the concept), so a
link lands on the word. Entries follow the order of the pages in structure.json. Braces that mark the language's own text in notes
are removed, so a term is the plain word or phrase.
"""

from .content import pages_in_order

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
                if not any(p["slug"] == slug for p in entry["pages"]):
                    entry["pages"].append({"slug": slug, "href": f"{slug}.html#{section['id']}.{cid}", "title": titles})
    return {"languages": languages, "entries": list(entries.values())}
