"""Reading and checking a project's content.

A project is a folder:
    structure.json                  navigation groups and page order (language neutral)
    pages/<slug>.json               a page skeleton: sections and the ids of their concepts
    packs/<code>/pack.json          one language: name, interface words, group titles, sources, varieties
    packs/<code>/pages/<slug>.json  that language's titles, commentary and one text per concept
    editions/<name>.json            which languages to publish, the default pair, branding and stylesheets
    icons/<name>.svg                line icons that groups and pages name with "icon" (see icons.py)
    palettes/<id>.json              colour palettes the visitor can choose, added to the framework's own (see palettes.py)
    static/                         files copied to the output as they are (project stylesheet, icons)

Nothing in here knows which languages a project uses. Language codes are BCP 47 tags in lower case.
"""
import json
import pathlib
import re
import unicodedata

from . import icons, palettes
from .errors import ContentError
from .figures import FIGURE_CONCEPTS
from .channels import check_status
from .messages import Messages

LANG_CODE = re.compile(r"^[a-z]{2,3}(-[a-z0-9]+)*$")  # also safe inside CSS attribute selectors and attribute names
VARIETY_ID = re.compile(r"^[a-z][a-z0-9-]*$")
STORAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")  # also what app.js accepts as a storage name
STYLESHEET = re.compile(r"^(https://\S+|[A-Za-z0-9_-][A-Za-z0-9_./-]*\.css)$")  # an https URL or a file of the project
ICON_SRC = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_./-]*\.(png|svg)$")  # a file of the project
ICON_PURPOSES = ("any", "maskable", "monochrome")

# Accepted licences for translations: key -> (proper name, URL or None). See docs/ASSETS.md.
# A licence with no proper name is described by an interface message, licence_<key with underscores>.
LICENCES = {
    "public-domain": (None, None),
    "CC0-1.0": ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    "CC-BY-4.0": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "OGL-3.0": ("Open Government Licence v3.0",
                "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"),
    "own": (None, None),
    "draft": (None, None),
}
DRAFT = "draft"  # allowed in a normal build, rejected by --strict
RESERVED_SLUGS = ("index", "sources", "how-to", "settings")
GROUP_PAGE_PREFIX = "group-"  # generated pages, one per group, are group-<id>.html
GROUP_ID = re.compile(r"^[a-z][a-z0-9-]*$")

# Invisible bidirectional controls. They can make text read differently from how it is stored, so content
# must say which way a language runs with "dir" and let the browser do the rest.
BIDI_CONTROLS = re.compile("[؜‎‏‪-‮⁦-⁩]")


# ---------------------------------------------------------------- reading


def read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def read(project_dir):
    """Read every data file of a project into one dict: structure, pages, packs and editions."""
    d = pathlib.Path(project_dir)
    raw = {"structure": read_json(d / "structure.json"),
           "pages": {p.stem: read_json(p) for p in sorted((d / "pages").glob("*.json"))},
           "packs": {}, "editions": {}}
    for pdir in sorted((d / "packs").iterdir()):
        if pdir.is_dir():
            pages_dir = pdir / "pages"
            raw["packs"][pdir.name] = {
                "meta": read_json(pdir / "pack.json"),
                "pages": {p.stem: read_json(p) for p in sorted(pages_dir.glob("*.json"))} if pages_dir.is_dir() else {},
            }
    for f in sorted((d / "editions").glob("*.json")):
        raw["editions"][f.stem] = read_json(f)
    raw["palettes"] = palettes.load(d / "palettes")
    icon_dir = d / "icons"
    raw["icons"] = {f.stem: f.read_text(encoding="utf-8") for f in sorted(icon_dir.glob("*.svg"))} if icon_dir.is_dir() else {}
    return raw


def pick_edition(raw, name=None):
    """Return (name, edition). Without a name, the project must hold exactly one edition."""
    editions = raw["editions"]
    if name is None:
        if len(editions) != 1:
            raise ContentError(f"choose an edition with --edition; found: {', '.join(editions) or 'none'}")
        name = next(iter(editions))
    if name not in editions:
        raise ContentError(f"unknown edition {name!r}; found: {', '.join(editions) or 'none'}")
    return name, editions[name]


# ---------------------------------------------------------------- validating


def validate(raw):
    """Check the whole project. Raises ContentError with a message naming the file at fault."""
    structure, pages, packs = raw["structure"], raw["pages"], raw["packs"]
    group_ids = [g.get("id") for g in structure.get("groups", [])]
    if not group_ids or any(not g for g in group_ids) or len(set(group_ids)) != len(group_ids):
        raise ContentError("structure.json: every group needs a unique id")
    for gid in group_ids:
        if not isinstance(gid, str) or not GROUP_ID.match(gid):
            raise ContentError(f"structure.json: group id {gid!r} must be lower case letters, digits and hyphens, starting with a letter")
    listed = [slug for g in structure["groups"] for slug in g.get("pages", [])]
    for slug in listed:
        if slug not in pages:
            raise ContentError(f"structure.json lists '{slug}' but pages/{slug}.json does not exist")
    if len(set(listed)) != len(listed):
        raise ContentError("structure.json lists a page more than once")
    for slug in pages:
        if slug not in listed:
            raise ContentError(f"pages/{slug}.json is not listed in any group in structure.json")
        if slug in RESERVED_SLUGS or slug.startswith(GROUP_PAGE_PREFIX):
            raise ContentError(f"'{slug}' is reserved for a generated page")
    for slug, p in pages.items():
        validate_skeleton(slug, p)
    icons.validate(raw["icons"])
    for g in structure["groups"]:
        check_icon(f"structure.json group {g['id']!r}", g.get("icon"), raw["icons"])
    for slug, p in pages.items():
        check_icon(f"pages/{slug}.json", p.get("icon"), raw["icons"])
    for code, pack in packs.items():
        validate_pack(code, pack, raw)
    palettes.validate(raw["palettes"], LANG_CODE)
    for pid, palette in raw["palettes"].items():
        validate_text(f"palettes/{pid}.json", palette.get("names", {}))
    for name, ed in raw["editions"].items():
        validate_edition(name, ed, packs, raw["palettes"])
    Messages(packs).validate()


def check_icon(where, name, available):
    """An optional "icon" must name a file in the project's icons/ folder."""
    if name is None:
        return
    if not isinstance(name, str) or name not in available:
        raise ContentError(f"{where}: icon {name!r} has no file icons/{name}.svg" if isinstance(name, str)
                           else f"{where}: 'icon' must be the name of a file in icons/")


def validate_text(where, value):
    """Every string must be in Unicode normal form C and free of invisible bidirectional controls.

    Normal form C keeps one letter one code point, so equal text compares equal and searches find it.
    """
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise ContentError(f"{where}: text is not in Unicode normal form C (a letter with a separate accent?): {value!r}")
        if BIDI_CONTROLS.search(value):
            raise ContentError(f"{where}: text contains an invisible bidirectional control; use the pack's 'dir' instead")
    elif isinstance(value, dict):
        for k, v in value.items():
            validate_text(f"{where}/{k}", v)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            validate_text(f"{where}[{i}]", v)


def validate_skeleton(slug, p):
    if not p.get("sections"):
        raise ContentError(f"pages/{slug}.json: needs at least one section")
    seen_sections, seen_concepts = set(), set()
    for s in p["sections"]:
        sid = s.get("id")
        if not sid or sid in seen_sections:
            raise ContentError(f"pages/{slug}.json: section id missing or repeated: {sid!r}")
        seen_sections.add(sid)
        if not s.get("concepts"):
            raise ContentError(f"pages/{slug}.json/{sid}: needs at least one concept")
        check_status(f"pages/{slug}.json/{sid}", s)
        for cid in s["concepts"]:
            if cid in seen_concepts:
                raise ContentError(f"pages/{slug}.json/{sid}: concept id repeated on the page: {cid!r}")
            seen_concepts.add(cid)
    fig = p.get("figure")
    if fig:
        if fig not in FIGURE_CONCEPTS:
            raise ContentError(f"pages/{slug}.json: unknown figure {fig!r}")
        missing = [c for c in FIGURE_CONCEPTS[fig] if c not in seen_concepts]
        if missing:
            raise ContentError(f"pages/{slug}.json: figure {fig!r} needs concepts {', '.join(missing)}")


def validate_sources(owner, sources):
    """Check a pack's sources list. Returns the list of source ids."""
    if not sources:
        raise ContentError(f"{owner}: needs at least one entry in 'sources'")
    ids = []
    for s in sources:
        sid = s.get("id")
        if not sid or sid in ids:
            raise ContentError(f"{owner}: source id missing or repeated: {sid!r}")
        ids.append(sid)
        if not s.get("title"):
            raise ContentError(f"{owner}: source '{sid}' needs a title")
        if s.get("licence") not in LICENCES:
            raise ContentError(f"{owner}: source '{sid}' has licence {s.get('licence')!r}; "
                               f"accepted: {', '.join(LICENCES)}")
        if s.get("url") and not s["url"].startswith("https://"):
            raise ContentError(f"{owner}: source '{sid}' url must start with https://")
    return ids


def validate_pack(code, pack, raw):
    where = f"packs/{code}"
    meta = pack["meta"]
    if meta.get("code") != code:
        raise ContentError(f"{where}/pack.json: 'code' must be {code!r}")
    if not LANG_CODE.match(code):
        raise ContentError(f"{where}: the language code must be a lower case BCP 47 tag, such as 'fr' or 'zh-hant'")
    if not meta.get("name"):
        raise ContentError(f"{where}/pack.json: missing 'name'")
    names = meta.get("names", {})
    if not isinstance(names, dict) or any(not LANG_CODE.match(k) or not v or not isinstance(v, str) for k, v in names.items()):
        raise ContentError(f"{where}/pack.json: 'names' must map language codes to the language's name in that language")
    if meta.get("commentary_lang") is not None and not LANG_CODE.match(str(meta["commentary_lang"])):
        raise ContentError(f"{where}/pack.json: 'commentary_lang' must be a language code")
    variety_ids = validate_varieties(where, meta.get("varieties", []))
    if meta.get("dir", "ltr") not in ("ltr", "rtl"):
        raise ContentError(f"{where}/pack.json: 'dir' must be ltr or rtl")
    if not meta.get("ui", {}).get("endonym"):
        raise ContentError(f"{where}/pack.json: missing ui word 'endonym' (the language's name for itself)")
    for g in raw["structure"]["groups"]:
        if not meta.get("groups", {}).get(g["id"]):
            raise ContentError(f"{where}/pack.json: missing group title for '{g['id']}'")
    source_ids = validate_sources(where, meta.get("sources"))
    validate_text(f"{where}/pack.json", meta)
    for slug, pp in pack["pages"].items():
        skel = raw["pages"].get(slug)
        if skel is None:
            raise ContentError(f"{where}/pages/{slug}.json has no matching pages/{slug}.json")
        if not pp.get("title"):
            raise ContentError(f"{where}/pages/{slug}.json: missing 'title'")
        if pp.get("source") not in source_ids:
            raise ContentError(f"{where}/pages/{slug}.json: 'source' must be one of {source_ids}")
        validate_text(f"{where}/pages/{slug}.json", pp)
        concepts_of = {s["id"]: set(s["concepts"]) for s in skel["sections"]}
        for sid, sec in pp.get("sections", {}).items():
            if sid not in concepts_of:
                raise ContentError(f"{where}/pages/{slug}.json: unknown section {sid!r}")
            if not sec.get("title"):
                raise ContentError(f"{where}/pages/{slug}.json/{sid}: missing 'title'")
            for cid, c in sec.get("concepts", {}).items():
                if cid not in concepts_of[sid]:
                    raise ContentError(f"{where}/pages/{slug}.json/{sid}: unknown concept {cid!r}")
                validate_concept(f"{where}/pages/{slug}.json/{sid}", cid, c, variety_ids)
                if c.get("source") is not None and c["source"] not in source_ids:
                    raise ContentError(f"{where}/pages/{slug}.json/{sid}: concept {cid!r} names unknown source {c['source']!r}")


def validate_varieties(where, varieties):
    """Check a pack's declared varieties. Returns their ids."""
    ids = []
    for v in varieties:
        vid = v.get("id")
        if not (vid and v.get("name") and v.get("short")):
            raise ContentError(f"{where}/pack.json: each variety needs 'id', 'name' and 'short'")
        if not VARIETY_ID.match(vid) or vid == "all":
            raise ContentError(f"{where}/pack.json: variety id {vid!r} must be lower case letters, digits or hyphens, and not 'all'")
        if vid in ids:
            raise ContentError(f"{where}/pack.json: variety id repeated: {vid!r}")
        ids.append(vid)
    return ids


def validate_concept(where, cid, c, variety_ids):
    """A concept has either one 'text' or a list of 'forms' tagged with varieties."""
    forms = c.get("forms")
    if bool(c.get("text")) == bool(forms):
        raise ContentError(f"{where}: concept {cid!r} needs exactly one of 'text' or 'forms'")
    if not forms:
        return
    if not variety_ids:
        raise ContentError(f"{where}: concept {cid!r} uses 'forms' but the pack declares no varieties")
    seen = []
    for f in forms:
        if not f.get("text"):
            raise ContentError(f"{where}: concept {cid!r} has a form without 'text'")
        unknown = [v for v in f.get("varieties", []) if v not in variety_ids]
        if unknown:
            raise ContentError(f"{where}: concept {cid!r} form {f['text']!r} names undeclared varieties: {', '.join(unknown)}")
        if f["text"] in seen:
            raise ContentError(f"{where}: concept {cid!r} lists the form {f['text']!r} twice")
        seen.append(f["text"])


def validate_edition(name, ed, packs, available_palettes):
    where = f"editions/{name}.json"
    if not ed.get("name"):
        raise ContentError(f"{where}: missing 'name'")
    langs = ed.get("languages") or []
    if len(langs) < 2 or len(set(langs)) != len(langs):
        raise ContentError(f"{where}: 'languages' needs at least two different codes")
    for code in langs:
        if code not in packs:
            raise ContentError(f"{where}: language {code!r} has no pack in packs/")
    if ed.get("interface") not in langs:
        raise ContentError(f"{where}: 'interface' must be one of the languages")
    pair = ed.get("default_pair") or []
    if len(pair) != 2 or pair[0] == pair[1] or any(c not in langs for c in pair):
        raise ContentError(f"{where}: 'default_pair' needs two different languages from the edition")
    for code in pair:
        if not ed.get("home", {}).get("headline", {}).get(code):
            raise ContentError(f"{where}: home.headline needs a text for {code!r}")
    if ed.get("storage") is not None and not STORAGE_NAME.match(str(ed["storage"])):
        raise ContentError(f"{where}: 'storage' must be lower case letters, digits, dots, hyphens or underscores")
    offered = ed.get("palettes")
    if offered is not None:
        if not isinstance(offered, list) or len(set(offered)) != len(offered):
            raise ContentError(f"{where}: 'palettes' must be a list of palette ids with no repeats")
        if palettes.DEFAULT not in offered:
            raise ContentError(f"{where}: 'palettes' must include {palettes.DEFAULT!r}, the baseline every page starts from")
        unknown = [pid for pid in offered if pid not in available_palettes]
        if unknown:
            raise ContentError(f"{where}: unknown palettes: {', '.join(map(str, unknown))}; available: {', '.join(available_palettes)}")
    if ed.get("short_name") is not None and not isinstance(ed["short_name"], str):
        raise ContentError(f"{where}: 'short_name' must be a string")
    for key in ("fonts", "stylesheets"):
        for href in ed.get(key, []):
            if not isinstance(href, str) or not STYLESHEET.match(href) or ".." in href:
                raise ContentError(f"{where}: '{key}' entries must be https URLs or .css files of the project: {href!r}")
    for icon in ed.get("icons", []):
        if not isinstance(icon, dict):
            raise ContentError(f"{where}: each entry in 'icons' must be an object")
        src, sizes, itype = icon.get("src"), icon.get("sizes"), icon.get("type")
        if not isinstance(src, str) or not ICON_SRC.match(src) or ".." in src:
            raise ContentError(f"{where}: icon 'src' must be a .png or .svg file of the project: {src!r}")
        if not sizes or not isinstance(sizes, str):
            raise ContentError(f"{where}: icon {src!r} needs 'sizes'")
        if itype not in ("image/png", "image/svg+xml"):
            raise ContentError(f"{where}: icon {src!r} needs 'type' image/png or image/svg+xml")
        if "purpose" in icon and icon["purpose"] not in ICON_PURPOSES:
            raise ContentError(f"{where}: icon {src!r} has unknown purpose {icon['purpose']!r}; accepted: {', '.join(ICON_PURPOSES)}")
    validate_text(where, ed)


# ---------------------------------------------------------------- reports


def draft_sources(raw, edition):
    """(language, source id) for every unreviewed draft source in the edition's packs."""
    return [(code, s["id"]) for code in edition["languages"]
            for s in raw["packs"][code]["meta"]["sources"] if s["licence"] == DRAFT]


def coverage(raw, edition):
    """{language: (concepts translated, concepts in total)} over every page."""
    total = sum(len(s["concepts"]) for p in raw["pages"].values() for s in p["sections"])
    result = {}
    for code in edition["languages"]:
        have = sum(len(sec.get("concepts", {})) for pp in raw["packs"][code]["pages"].values()
                   for sec in pp.get("sections", {}).values())
        result[code] = (have, total)
    return result


def pages_in_order(raw):
    """Every page slug, in the order structure.json lists them."""
    return [slug for g in raw["structure"]["groups"] for slug in g.get("pages", [])]
