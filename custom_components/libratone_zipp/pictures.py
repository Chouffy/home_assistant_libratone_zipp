"""Small SVG pictures as data URIs: a color swatch and a drawn (not Libratone's) Zipp in the speaker's color."""
from __future__ import annotations

from urllib.parse import quote

from .const import COLORS

FALLBACK = "#9e9e9e"


def color_hex(code: str | None) -> str:
    return COLORS.get(code or "", ("", FALLBACK))[1]


def _data_uri(svg: str) -> str:
    return "data:image/svg+xml;utf8," + quote(" ".join(svg.split()))


def swatch(code: str | None) -> str:
    return _data_uri(f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r="28" fill="{color_hex(code)}" stroke="#00000033" stroke-width="2"/></svg>""")


def zipp(code: str | None) -> str:
    """Stylized Zipp: fabric-covered cylinder, dark top with touch ring, strap handle."""
    c = color_hex(code)
    weave = "".join(f'<line x1="22" y1="{y}" x2="78" y2="{y}" stroke="#00000014" stroke-width="1.4"/>'
                    for y in range(34, 100, 5))
    return _data_uri(f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120">
        <rect width="100" height="120" fill="#f2f2f2"/>
        <path d="M38 22 C38 6 62 6 62 22" fill="none" stroke="#3b2f2a" stroke-width="5" stroke-linecap="round"/>
        <rect x="22" y="24" width="56" height="80" rx="9" fill="{c}"/>
        {weave}
        <rect x="22" y="24" width="56" height="80" rx="9" fill="url(#shade)"/>
        <ellipse cx="50" cy="25" rx="28" ry="6" fill="#262626"/>
        <ellipse cx="50" cy="25" rx="10" ry="2.4" fill="none" stroke="#bdbdbd" stroke-width="1"/>
        <ellipse cx="50" cy="104" rx="28" ry="5" fill="#00000026"/>
        <defs><linearGradient id="shade" x1="0" x2="1">
          <stop offset="0" stop-color="#000" stop-opacity=".22"/><stop offset=".35" stop-color="#fff" stop-opacity=".10"/>
          <stop offset="1" stop-color="#000" stop-opacity=".28"/></linearGradient></defs></svg>""")
