"""Colour maths for palettes: OKLab and OKLCH, sRGB gamut mapping, WCAG contrast and colour-vision simulation.

Palettes are written in OKLCH because equal steps in lightness look equal, so a designer can pick a lightness
for each role and know how it will read. The pages need plain sRGB hex, so colours are gamut-mapped by
reducing chroma at constant lightness and hue until they fit. Everything is standard library.

References: Björn Ottosson, "A perceptual color space for image processing" (OKLab, 2020); WCAG 2.2 relative
luminance and contrast ratio; Machado, Oliveira and Fernandes, "A Physiologically-based Model for Simulation
of Color Vision Deficiency" (2009), severity 1.0.
"""
import math
import re

HEX = re.compile(r"^#([0-9a-fA-F]{6})$")
FUNCTION = re.compile(r"^(oklch|oklab)\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*\)$")


def to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def from_linear(c):
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def linear_to_oklab(r, g, b):
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = math.cbrt(l), math.cbrt(m), math.cbrt(s)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklab_to_linear(lightness, a, b):
    l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def oklch_to_oklab(lightness, chroma, hue):
    h = math.radians(hue)
    return lightness, chroma * math.cos(h), chroma * math.sin(h)


def oklab_to_oklch(lightness, a, b):
    hue = math.degrees(math.atan2(b, a)) % 360
    return lightness, math.hypot(a, b), hue


def hex_to_rgb(text):
    """'#rrggbb' -> (r, g, b), each 0..1 and sRGB-encoded."""
    value = HEX.match(text).group(1)
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{round(min(1.0, max(0.0, c)) * 255):02x}" for c in rgb)


def rgb_to_oklab(rgb):
    return linear_to_oklab(*(to_linear(c) for c in rgb))


def in_gamut(linear, eps=1e-6):
    return all(-eps <= c <= 1 + eps for c in linear)


def oklab_to_rgb(lightness, a, b):
    """Gamut-map an OKLab colour to sRGB by reducing chroma at constant lightness and hue."""
    lightness = min(1.0, max(0.0, lightness))
    linear = oklab_to_linear(lightness, a, b)
    if not in_gamut(linear):
        _, chroma, hue = oklab_to_oklch(lightness, a, b)
        low, high = 0.0, chroma
        for _ in range(40):
            mid = (low + high) / 2
            if in_gamut(oklab_to_linear(*oklch_to_oklab(lightness, mid, hue))):
                low = mid
            else:
                high = mid
        linear = oklab_to_linear(*oklch_to_oklab(lightness, low, hue))
    return tuple(from_linear(c) for c in linear)


def parse(text):
    """A palette colour: '#rrggbb', 'oklch(L C h)' or 'oklab(L a b)'. Returns sRGB (r, g, b), or None if not valid."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    if HEX.match(text):
        return hex_to_rgb(text)
    found = FUNCTION.match(text)
    if not found:
        return None
    kind, x, y, z = found.group(1), *(float(v) for v in found.group(2, 3, 4))
    if not 0 <= x <= 1:
        return None
    if kind == "oklch":
        if y < 0 or y > 0.5:
            return None
        return oklab_to_rgb(*oklch_to_oklab(x, y, z))
    if abs(y) > 0.5 or abs(z) > 0.5:
        return None
    return oklab_to_rgb(x, y, z)


def luminance(rgb):
    r, g, b = (to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(first, second):
    """WCAG contrast ratio of two sRGB colours, 1 to 21."""
    a, b = luminance(first), luminance(second)
    if a < b:
        a, b = b, a
    return (a + 0.05) / (b + 0.05)


def distance(first, second):
    """Euclidean distance in OKLab. About 0.02 is just noticeable; 0.1 and more is plainly different."""
    return math.dist(rgb_to_oklab(first), rgb_to_oklab(second))


# Machado et al. (2009), severity 1.0, applied to linear RGB.
DEFICIENCIES = {
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def simulate(rgb, kind):
    """How an sRGB colour looks to someone with complete protanopia, deuteranopia or tritanopia."""
    linear = [to_linear(c) for c in rgb]
    return tuple(from_linear(sum(m * c for m, c in zip(row, linear))) for row in DEFICIENCIES[kind])
