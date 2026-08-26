import re

_HEX_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def _safe_hex(value, fallback):
    value = str(value or "")
    return value.lower() if _HEX_PATTERN.match(value) else fallback


def shade(hex_color, amount):
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    if amount >= 0:
        adjusted = [round(c + (255 - c) * amount) for c in (r, g, b)]
    else:
        adjusted = [round(c * (1 + amount)) for c in (r, g, b)]
    return "#{:02x}{:02x}{:02x}".format(*(min(255, max(0, c)) for c in adjusted))


def rgb_triplet(hex_color):
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"{r},{g},{b}"


def readable_text(hex_color):
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#212529" if luminance > 0.6 else "#ffffff"


def build_theme(club):
    primary = _safe_hex(getattr(club, "primary_color", None), "#0d6efd")
    secondary = _safe_hex(getattr(club, "secondary_color", None), "#212529")
    return {
        "primary": primary,
        "primary_rgb": rgb_triplet(primary),
        "primary_hover": shade(primary, -0.12),
        "primary_active": shade(primary, -0.22),
        "on_primary": readable_text(primary),
        "secondary": secondary,
        "secondary_rgb": rgb_triplet(secondary),
        "secondary_hover": shade(secondary, -0.12),
        "secondary_active": shade(secondary, -0.4),
        "on_secondary": readable_text(secondary),
        "link": shade(primary, -0.05),
    }
