from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


HEX_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{6}\b")
IMAGE_SOURCE_PATTERN = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)
LOGO_HINT_PATTERN = re.compile(r"logo|brand", re.IGNORECASE)


@dataclass(frozen=True)
class BrandTheme:
    primary: str
    accent: str
    background: str
    surface: str
    text: str
    muted: str
    line: str
    button_text: str = "#ffffff"
    logo_url: str | None = None


DEFAULT_THEME = BrandTheme(
    primary="#0f766e",
    accent="#0f766e",
    background="#f7f5ef",
    surface="#ffffff",
    text="#101828",
    muted="#667085",
    line="#d8e1e7",
)

BRAND_OVERRIDES: dict[str, BrandTheme] = {
    "greyradius.com": BrandTheme(
        primary="#101f43",
        accent="#f2673b",
        background="#ffffff",
        surface="#ffffff",
        text="#101f43",
        muted="#6d7b99",
        line="#e4e9f2",
        logo_url="https://greyradius.com/assets/images/logo.png",
    ),
    "kairozcorporation.com": BrandTheme(
        primary="#008080",
        accent="#008080",
        background="#ffffff",
        surface="#ffffff",
        text="#0a1119",
        muted="#4b535d",
        line="#cce6e6",
        logo_url="https://kairozcorporation.com/wp-content/uploads/2025/07/Green-Modern-Tree-Logo-Design-4-1.png",
    ),
}


def theme_for_business(name: str | None, website: str | None) -> BrandTheme:
    """Return a landing-page theme from a business website with safe fallbacks."""
    del name
    hostname = _hostname(website)
    if not hostname:
        return DEFAULT_THEME
    if hostname in BRAND_OVERRIDES:
        return BRAND_OVERRIDES[hostname]
    return _theme_from_website(hostname, website or "") or DEFAULT_THEME


def theme_to_dict(theme: BrandTheme) -> dict[str, str]:
    data = {
        "primary": theme.primary,
        "accent": theme.accent,
        "background": theme.background,
        "surface": theme.surface,
        "text": theme.text,
        "muted": theme.muted,
        "line": theme.line,
        "button_text": theme.button_text,
    }
    if theme.logo_url:
        data["logo_url"] = theme.logo_url
    return data


def theme_from_dict(value: object) -> BrandTheme | None:
    if not isinstance(value, dict):
        return None
    required = ("primary", "accent", "background", "surface", "text", "muted", "line")
    if not all(isinstance(value.get(key), str) and _is_hex(value[key]) for key in required):
        return None
    button_text = value.get("button_text", "#ffffff")
    logo_url = value.get("logo_url")
    return BrandTheme(
        primary=value["primary"],
        accent=value["accent"],
        background=value["background"],
        surface=value["surface"],
        text=value["text"],
        muted=value["muted"],
        line=value["line"],
        button_text=button_text if isinstance(button_text, str) and _is_hex(button_text) else "#ffffff",
        logo_url=logo_url if isinstance(logo_url, str) and _is_http_url(logo_url) else None,
    )


def public_theme_style(theme: BrandTheme) -> str:
    variables = {
        "--accent": theme.accent,
        "--ink": theme.text,
        "--muted": theme.muted,
        "--line": theme.line,
        "--public-primary": theme.primary,
        "--public-accent": theme.accent,
        "--public-accent-dark": _darken(theme.accent),
        "--public-bg": theme.background,
        "--public-surface": theme.surface,
        "--public-text": theme.text,
        "--public-muted": theme.muted,
        "--public-line": theme.line,
        "--public-button-text": theme.button_text,
    }
    declarations = " ".join(f"{name}: {escape(value)};" for name, value in variables.items())
    return f":root {{ {declarations} }}"


@lru_cache(maxsize=128)
def _theme_from_website(hostname: str, website: str) -> BrandTheme | None:
    homepage = _fetch_homepage(hostname, website)
    if not homepage:
        return None

    url, body = homepage
    colors = [color.lower() for color in HEX_COLOR_PATTERN.findall(body)]
    if not colors:
        return None

    useful_colors = [color for color in colors if _is_brand_color(color)]
    if not useful_colors:
        return None

    ranked = Counter(useful_colors).most_common()
    most_common_count = ranked[0][1]
    accent = max(
        (color for color, _count in ranked),
        key=lambda color: _accent_score(color) + (Counter(useful_colors)[color] / most_common_count),
    )
    dark_candidates = [color for color in useful_colors if _relative_luminance(color) < 0.24]
    text = min(dark_candidates, key=_relative_luminance) if dark_candidates else DEFAULT_THEME.text
    muted = _blend(text, "#ffffff", 0.42)
    line = _blend(accent, "#ffffff", 0.82)
    background = "#ffffff" if _relative_luminance(accent) < 0.75 else "#f8fafc"
    return BrandTheme(
        primary=text,
        accent=accent,
        background=background,
        surface="#ffffff",
        text=text,
        muted=muted,
        line=line,
        button_text="#ffffff" if _relative_luminance(accent) < 0.58 else "#101828",
        logo_url=_extract_logo_url(url, body),
    )


def _fetch_homepage(hostname: str, website: str) -> tuple[str, str] | None:
    url = website if website.startswith(("http://", "https://")) else f"https://{hostname}"
    try:
        request = Request(url, headers={"User-Agent": "MarketingAgentBrandTheme/1.0"})
        with urlopen(request, timeout=2) as response:
            final_url = response.geturl()
            body = response.read(300_000).decode("utf-8", errors="ignore")
    except Exception:
        return None
    return final_url, body


def _extract_logo_url(base_url: str, body: str) -> str | None:
    candidates = []
    for match in IMAGE_SOURCE_PATTERN.finditer(body):
        tag = match.group(0)
        source = match.group(1)
        if LOGO_HINT_PATTERN.search(tag) or LOGO_HINT_PATTERN.search(source):
            candidates.append(source)
    if not candidates:
        return None
    logo_url = urljoin(base_url, candidates[0])
    parsed = urlparse(logo_url)
    if parsed.scheme not in {"http", "https"}:
        return None
    return logo_url


def _hostname(website: str | None) -> str:
    if not website:
        return ""
    candidate = website.strip()
    if not candidate:
        return ""
    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    return (parsed.hostname or "").removeprefix("www.").lower()


def _is_hex(value: str) -> bool:
    return bool(HEX_COLOR_PATTERN.fullmatch(value))


def _is_http_url(value: str) -> bool:
    return urlparse(value).scheme in {"http", "https"}


def _is_brand_color(hex_color: str) -> bool:
    red, green, blue = _rgb(hex_color)
    max_channel = max(red, green, blue)
    min_channel = min(red, green, blue)
    luminance = _relative_luminance(hex_color)
    saturation = 0 if max_channel == 0 else (max_channel - min_channel) / max_channel
    if luminance < 0.05 or luminance > 0.95:
        return False
    return saturation >= 0.18


def _accent_score(hex_color: str) -> float:
    red, green, blue = _rgb(hex_color)
    max_channel = max(red, green, blue)
    min_channel = min(red, green, blue)
    saturation = 0 if max_channel == 0 else (max_channel - min_channel) / max_channel
    luminance = _relative_luminance(hex_color)
    contrast_penalty = abs(luminance - 0.48)
    return saturation * 2 - contrast_penalty


def _relative_luminance(hex_color: str) -> float:
    red, green, blue = (channel / 255 for channel in _rgb(hex_color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _darken(hex_color: str, amount: float = 0.14) -> str:
    red, green, blue = _rgb(hex_color)
    return _hex((round(red * (1 - amount)), round(green * (1 - amount)), round(blue * (1 - amount))))


def _blend(hex_color: str, other_hex_color: str, amount: float) -> str:
    red, green, blue = _rgb(hex_color)
    other_red, other_green, other_blue = _rgb(other_hex_color)
    return _hex(
        (
            round(red * (1 - amount) + other_red * amount),
            round(green * (1 - amount) + other_green * amount),
            round(blue * (1 - amount) + other_blue * amount),
        )
    )


def _rgb(hex_color: str) -> tuple[int, int, int]:
    clean = hex_color.removeprefix("#")
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)


def _hex(rgb: tuple[int, int, int]) -> str:
    red, green, blue = (max(0, min(255, channel)) for channel in rgb)
    return f"#{red:02x}{green:02x}{blue:02x}"
