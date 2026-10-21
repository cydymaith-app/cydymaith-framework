"""Release channels: which sections a build includes.

A section marked "status": "development" in pages/<slug>.json is held back from the release channel, the
default. The development channel includes it. Every channel validates the whole project, so held-back content
must stay correct; only the output differs. A page left with no sections is dropped from the release, with
its pack pages and its place in structure.json.

    python3 build.py dist                          release: held-back sections are left out
    python3 build.py dist --channel development    everything, including held-back sections
"""
import copy

from .errors import ContentError
from .figures import FIGURE_CONCEPTS

RELEASE = "release"
DEVELOPMENT = "development"
CHANNELS = (RELEASE, DEVELOPMENT)
HELD_BACK = "development"  # the only status a section may carry; a section without one is released


def check_status(where, section):
    """A section's optional 'status' must be a known value."""
    status = section.get("status")
    if status is not None and status != HELD_BACK:
        raise ContentError(f"{where}: unknown status {status!r}; accepted: {HELD_BACK}")


def select(raw, channel=RELEASE):
    """Return the project as the channel publishes it. The input is not changed."""
    if channel not in CHANNELS:
        raise ContentError(f"unknown channel {channel!r}; choose one of: {', '.join(CHANNELS)}")
    if channel == DEVELOPMENT:
        return raw
    out = copy.deepcopy(raw)
    for slug, page in out["pages"].items():
        held = {s["id"] for s in page["sections"] if s.get("status") == HELD_BACK}
        if not held:
            continue
        page["sections"] = [s for s in page["sections"] if s["id"] not in held]
        if page.get("figure") and not set(FIGURE_CONCEPTS[page["figure"]]) <= _concepts(page):
            raise ContentError(f"pages/{slug}.json: the figure needs concepts held back with a section: {page['figure']}")
        for pack in out["packs"].values():
            pp = pack["pages"].get(slug)
            if pp:
                pp["sections"] = {sid: sec for sid, sec in pp.get("sections", {}).items() if sid not in held}
    kept = {slug for slug, page in out["pages"].items() if page["sections"]}
    for slug in set(out["pages"]) - kept:
        del out["pages"][slug]
        for pack in out["packs"].values():
            pack["pages"].pop(slug, None)
    for group in out["structure"]["groups"]:
        group["pages"] = [slug for slug in group.get("pages", []) if slug in kept]
    out["structure"]["groups"] = [g for g in out["structure"]["groups"] if g["pages"]]
    return out


def _concepts(page):
    return {c for s in page["sections"] for c in s["concepts"]}

