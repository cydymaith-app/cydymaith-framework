"""A neutral made-up project for testing the framework with no real language in sight.

Languages use the private-use codes qaa, qab and qac:
    qaa  Alphan   left to right, the interface language
    qab  Betan    left to right, two varieties (x and y)
    qac  Gammic   right to left
"""

import json
import pathlib

from phrasebook.figures import FIGURE_CONCEPTS

LANGS = {"qaa": ("Alphan", "ltr"), "qab": ("Betan", "ltr"), "qac": ("Gammic", "rtl")}
ENDONYMS = {"qaa": "Alphish", "qab": "Betish", "qac": "Gammish"}


def write(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def edit(path, fn):
    """Read a JSON file, let fn change it in place, write it back."""
    path = pathlib.Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    write(path, data)


def make_project(root, interface="qaa", ui_extra=None):
    """Write the project into `root` (created) and return the path. ui_extra: {code: extra ui table}."""
    root = pathlib.Path(root)
    ui_extra = ui_extra or {}
    write(root / "structure.json", {"groups": [{"id": "g1", "pages": ["p1", "points"]}]})
    write(
        root / "pages" / "p1.json",
        {"sections": [{"id": "s1", "concepts": ["c1"]}, {"id": "s2", "concepts": ["c2"]}, {"id": "s3", "concepts": ["c3"]}]},
    )
    write(
        root / "pages" / "points.json",
        {"figure": "compass-rose", "sections": [{"id": "dirs", "concepts": FIGURE_CONCEPTS["compass-rose"]}]},
    )
    for code, (name, direction) in LANGS.items():
        meta = {
            "code": code,
            "name": name,
            "dir": direction,
            "names": {interface: name},
            "ui": {"endonym": ENDONYMS[code], **ui_extra.get(code, {})},
            "groups": {"g1": f"{code} group", "g2": f"{code} second group"},
            "sources": [
                {"id": "own", "title": "Test author", "licence": "own"},
                {"id": "pd", "title": "Old book", "licence": "public-domain"},
                {"id": "dr", "title": "Rough draft", "licence": "draft"},
            ],
        }
        if code == "qab":
            meta["varieties"] = [{"id": "x", "name": "Xish", "short": "X"}, {"id": "y", "name": "Yish", "short": "Y"}]
        write(root / "packs" / code / "pack.json", meta)
        c2 = (
            {"forms": [{"text": f"{code} two-x", "varieties": ["x"]}, {"text": f"{code} two-y", "varieties": ["y"]}]}
            if code == "qab"
            else {"text": f"{code} two", "note": f"A note on {{{{{code} two}}}}"}
        )
        c1 = {"text": f"{code} one", "keys": ["one"], **({"source": "dr", "also": ["qab uno"]} if code == "qab" else {})}
        c3 = {"text": f"{code} three", **({"source": "pd"} if code == "qaa" else {})}
        write(
            root / "packs" / code / "pages" / "p1.json",
            {
                "title": f"{code} page",
                "source": "own",
                "lede": f"{code} lede",
                "sections": {
                    sid: {
                        "title": f"{code} section {sid}",
                        "intro": f"An intro with {{{{{code} word}}}}",
                        **({"order": "in an order"} if sid == "s1" and code == "qab" else {}),
                        "concepts": {cid: concept},
                    }
                    for sid, cid, concept in (("s1", "c1", c1), ("s2", "c2", c2), ("s3", "c3", c3))
                },
            },
        )
        write(
            root / "packs" / code / "pages" / "points.json",
            {
                "title": f"{code} points",
                "source": "own",
                "sections": {
                    "dirs": {
                        "title": f"{code} directions",
                        "concepts": {c: {"text": f"{code}-{c}"} for c in FIGURE_CONCEPTS["compass-rose"]},
                    }
                },
            },
        )
    write(
        root / "editions" / "demo.json",
        {
            "name": "Demo Book",
            "languages": list(LANGS),
            "interface": interface,
            "default_pair": ["qaa", "qab"],
            "contact": "reports@example.org",
            "about_page": {
                code: {
                    "title": f"{code} about",
                    "lede": f"{code} about lede",
                    "sections": [
                        {"title": f"{code} aims", "body": [f"{code} first paragraph", {"list": [f"{code} one", f"{code} two"]}]},
                        {"title": f"{code} principle", "body": [{"quote": f"{code} founding statement"}]},
                        {
                            "title": f"{code} more",
                            "body": [
                                {
                                    "links": [
                                        {"text": f"{code} outside", "href": "https://example.org/x"},
                                        {"text": f"{code} sources", "href": "sources.html"},
                                    ]
                                },
                                {"share": "https://example.org/book/"},
                            ],
                        },
                        {"title": f"{code} soon", "status": "development", "body": [f"{code} not yet"]},
                    ],
                }
                for code in ("qaa", "qab")
            },
            "home": {
                "headline": {c: f"{c} headline" for c in LANGS},
                "lede": {"qaa": "A lede."},
                "about": {"qaa": "Lorem ipsum."},
            },
        },
    )
    return root


def pseudo(template):
    """A pseudo-translation: accented look-alikes inside « », placeholders untouched."""
    import re

    table = str.maketrans("aeiouAEIOUcnst", "àéîõüÀÉÎÕÜçñšţ")
    parts = re.split(r"(\{\w+\})", template)
    return "«" + "".join(p if p.startswith("{") else p.translate(table) for p in parts) + "»"
