"""Draw the README banners from site/data/figures.json.

Usage:
    python design/banner.py

Writes assets/banner-light.svg, assets/banner-dark.svg and
assets/social-card.svg. The plot on the
right is the real mean CAR path after disclosure with its 95% band. Convert
to PNG with rsvg-convert.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGURES = ROOT / "site" / "data" / "figures.json"
DOME = ROOT / "design" / "marks" / "dome.svg"
FONT = "'Public Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif"
THEMES = {
    "light": {"ground": "#eef1f4", "ink": "#111418", "muted": "#4f5864", "line": "#c9d0d8",
              "accent": "#1f44d6", "band": "rgba(31,68,214,0.14)"},
    "dark": {"ground": "#0e1116", "ink": "#eef1f4", "muted": "#a3acb8", "line": "#2a313b",
             "accent": "#7d95ff", "band": "rgba(125,149,255,0.18)"},
}


def dome_paths() -> str:
    text = DOME.read_text()
    start = text.index("<path")
    end = text.index("</g>")
    return text[start:end]


def plot(path: list[dict], x0: float, x1: float, zero: float, k: float) -> tuple[str, str]:
    last = path[-1]["day"]

    def x(day: float) -> float:
        return x0 + (x1 - x0) * day / last

    def y(value: float) -> float:
        return zero - value * 100 * k

    upper = [f"{x(q['day']):.1f},{y(q['mean'] + 1.96 * q['se']):.1f}" for q in path]
    lower = [f"{x(q['day']):.1f},{y(q['mean'] - 1.96 * q['se']):.1f}" for q in reversed(path)]
    line = [f"{x(q['day']):.1f},{y(q['mean']):.1f}" for q in path]
    return "M" + "L".join(upper + lower) + "Z", "M" + "L".join(line)


def banner(theme: dict[str, str], path: list[dict]) -> str:
    band, line = plot(path, 710, 1140, 300, 34)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="420" viewBox="0 0 1200 420">
  <title>CapitolAlpha: do members of Congress beat the market? No. Copying 4,456 disclosed purchases earned no alpha.</title>
  <rect width="1200" height="420" fill="{theme['ground']}"/>
  <g font-family="{FONT}">
    <text x="64" y="84" font-size="18" font-weight="700" fill="{theme['ink']}">CapitolAlpha</text>
    <text x="64" y="150" font-size="48" font-weight="700" letter-spacing="-1.4" fill="{theme['ink']}">Do members of</text>
    <text x="64" y="202" font-size="48" font-weight="700" letter-spacing="-1.4" fill="{theme['ink']}">Congress beat</text>
    <text x="64" y="254" font-size="48" font-weight="700" letter-spacing="-1.4" fill="{theme['ink']}">the market? No.</text>
    <text x="64" y="304" font-size="17" fill="{theme['muted']}">4,456 purchases, 2020 to 2025. Copying</text>
    <text x="64" y="328" font-size="17" fill="{theme['muted']}">them after disclosure earned no alpha.</text>
    <text x="710" y="374" font-size="13" fill="{theme['muted']}">0</text>
    <text x="1140" y="374" font-size="13" text-anchor="end" fill="{theme['muted']}">+125 trading days</text>
    <text x="710" y="396" font-size="13" fill="{theme['muted']}">Mean abnormal return after disclosure, with its 95% band</text>
  </g>
  <g transform="translate(470 108) scale(0.96)" fill="none" stroke="{theme['ink']}" stroke-width="1.5"
     stroke-linecap="round" stroke-linejoin="round">
    {dome_paths()}
  </g>
  <path d="{band}" fill="{theme['band']}"/>
  <line x1="470" y1="300" x2="1140" y2="300" stroke="{theme['ink']}" stroke-width="1.5"/>
  <path d="{line}" fill="none" stroke="{theme['accent']}" stroke-width="2.5" stroke-linejoin="round"/>
</svg>
"""


def social(theme: dict[str, str], path: list[dict]) -> str:
    band, line = plot(path, 840, 1136, 470, 40)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="{theme['ground']}"/>
  <g font-family="{FONT}">
    <text x="64" y="96" font-size="24" font-weight="700" fill="{theme['ink']}">CapitolAlpha</text>
    <text x="64" y="206" font-size="68" font-weight="700" letter-spacing="-2.2" fill="{theme['ink']}">Do members of</text>
    <text x="64" y="278" font-size="68" font-weight="700" letter-spacing="-2.2" fill="{theme['ink']}">Congress beat</text>
    <text x="64" y="350" font-size="68" font-weight="700" letter-spacing="-2.2" fill="{theme['ink']}">the market? No.</text>
    <text x="64" y="420" font-size="22" fill="{theme['muted']}">4,456 purchases, 2020 to 2025. Copying them</text>
    <text x="64" y="452" font-size="22" fill="{theme['muted']}">after disclosure earned no four-factor alpha.</text>
    <text x="840" y="562" font-size="16" fill="{theme['muted']}">Mean abnormal return, days 0 to 125</text>
    <text x="840" y="586" font-size="16" fill="{theme['muted']}">after disclosure, with its 95% band</text>
  </g>
  <g transform="translate(560 214) scale(1.3)" fill="none" stroke="{theme['ink']}" stroke-width="1.3"
     stroke-linecap="round" stroke-linejoin="round">
    {dome_paths()}
  </g>
  <path d="{band}" fill="{theme['band']}"/>
  <line x1="560" y1="470" x2="1136" y2="470" stroke="{theme['ink']}" stroke-width="2"/>
  <path d="{line}" fill="none" stroke="{theme['accent']}" stroke-width="3" stroke-linejoin="round"/>
</svg>
"""


def main() -> None:
    path = json.loads(FIGURES.read_text())["car_disclosure"]
    for name, theme in THEMES.items():
        (ROOT / "assets" / f"banner-{name}.svg").write_text(banner(theme, path))
    (ROOT / "assets" / "social-card.svg").write_text(social(THEMES["light"], path))


if __name__ == "__main__":
    main()
