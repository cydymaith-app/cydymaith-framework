"""Screenshots of every theme: each palette in its light and dark variant, on one example page.

    python3 build.py dist --screenshots [DIR]     DIR defaults to docs/screenshots

The page is the built site's, so what is shown is what is published. For each theme the site is copied to a scratch folder
with the theme set the way the settings page would set it (data-theme and data-palette on <html>) and the page's scripts taken
out, so nothing resets it, and a headless Chromium-based browser (Chrome, Chromium or Edge) takes a phone-sized picture of
it. A README with the whole set as a gallery is written beside them. The pictures are generated, so git ignores them.

A browser is needed only for this step. It is found from the PHRASEBOOK_BROWSER environment variable, then the usual names on
the PATH, then the usual install places. The build fails, saying so, if there is none.
"""

import os
import pathlib
import re
import shutil
import signal
import subprocess
import tempfile
import time

from .errors import ContentError

VARIANTS = ("light", "dark")
SIZE = (500, 780)  # a phone; a headless browser's window does not go narrower than about 500px
TIMEOUT = 90
NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge")
PLACES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)
SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>\s*", re.DOTALL)
HTML_TAG = re.compile(r"<html\b([^>]*)>")


def find_browser(env=None, which=shutil.which, exists=os.path.isfile):
    """The path of a Chromium-based browser, or a ContentError saying how to provide one."""
    env = os.environ if env is None else env
    named = env.get("PHRASEBOOK_BROWSER")
    if named:
        found = which(named) or (named if exists(named) else None)
        if not found:
            raise ContentError(f"PHRASEBOOK_BROWSER is {named!r}, which is not a browser that can be run")
        return found
    for name in NAMES:
        found = which(name)
        if found:
            return found
    for place in PLACES:
        if exists(place):
            return place
    raise ContentError(
        "no Chrome, Chromium or Edge found for the screenshots; install one, or set PHRASEBOOK_BROWSER to its path"
    )


def themed(page, palette, variant, default_palette):
    """A built page with a theme set and its scripts removed, so it shows that theme and nothing resets it."""
    page = SCRIPT.sub("", page)
    attrs = f' data-theme="{variant}"' + (f' data-palette="{palette}"' if palette != default_palette else "")
    return HTML_TAG.sub(lambda m: f"<html{m.group(1)}{attrs}>", page, count=1)


def end(proc):
    """Stop the browser and everything it started: a headless browser does not always quit by itself."""
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except OSError:
        proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def run_browser(command, target, timeout=TIMEOUT):
    """Run the browser until the screenshot `target` has been written and has stopped growing, then end it.

    A separate function so tests can stand a fake in its place.
    """
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name != "nt":
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(command, **kwargs)
    deadline = time.monotonic() + timeout
    last = -1
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return
            size = target.stat().st_size if target.exists() else 0
            if size and size == last:
                return
            last = size
            time.sleep(0.4)
    finally:
        end(proc)


def command(browser, profile, size, target, url):
    flags = [
        "--headless=new",
        "--disable-gpu",
        "--disable-extensions",
        "--no-first-run",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        f"--window-size={size[0]},{size[1]}",
        f"--user-data-dir={profile}",
    ]
    if hasattr(os, "geteuid") and os.geteuid() == 0:  # a container's root cannot use the browser's sandbox
        flags.append("--no-sandbox")
    return [browser, *flags, f"--screenshot={target}", url]


def shoot(site_dir, out_dir, palettes, page, default_palette="default", browser=None, size=SIZE, labels=None):
    """Take every picture: one example `page` (a file name in site_dir) for each palette, in its light and its dark variant.

    Returns [(palette id, variant, path)] and writes README.md beside them. `labels` maps palette ids to names.
    """
    browser = browser or find_browser()
    site_dir, out_dir = pathlib.Path(site_dir).resolve(), pathlib.Path(out_dir).resolve()  # the browser runs elsewhere
    out_dir.mkdir(parents=True, exist_ok=True)
    taken = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as scratch:  # a browser that lingers may still hold a file
        scratch = pathlib.Path(scratch)
        for palette in palettes:
            for variant in VARIANTS:
                themed_site = scratch / f"{palette}-{variant}"
                shutil.copytree(site_dir, themed_site)
                shown = themed_site / page
                shown.write_text(themed(shown.read_text(encoding="utf-8"), palette, variant, default_palette), encoding="utf-8")
                target = out_dir / f"{palette}-{variant}.png"
                target.unlink(missing_ok=True)
                run_browser(command(browser, scratch / f"profile-{len(taken)}", size, target, shown.resolve().as_uri()), target)
                if not target.is_file() or target.stat().st_size == 0:
                    raise ContentError(
                        f"the browser took no screenshot of {page} in {palette} ({variant}); "
                        f"is {browser} a Chromium-based browser that can run headless?"
                    )
                taken.append((palette, variant, target))
    write_gallery(out_dir, palettes, page, labels or {})
    return taken


def write_gallery(out_dir, palettes, page, names):
    lines = [
        "# Theme screenshots",
        "",
        f"Every palette in its light and dark variant, on a phone-sized screen, each showing the page `{page}`. Generated by "
        "`python3 build.py dist --screenshots`, and ignored by git. Do not edit: run it again after changing a palette or the layout.",
        "",
        "| Palette | Light | Dark |",
        "|---|---|---|",
    ]
    for palette in palettes:
        lines.append(
            f"| {names.get(palette, palette)} | ![{palette} light]({palette}-light.png) | ![{palette} dark]({palette}-dark.png) |"
        )
    (pathlib.Path(out_dir) / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
