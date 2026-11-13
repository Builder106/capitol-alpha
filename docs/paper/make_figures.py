"""Draw the paper's figures as TikZ from site/data/figures.json.

Usage:
    python docs/paper/make_figures.py

Writes docs/paper/figures/car.tex and docs/paper/figures/lag.tex. The input
holds aggregates only (written by pipeline.site_figures), so the figures can
be rebuilt without CRSP access. Standard library only; plain TikZ output, so
the paper compiles without pgfplots.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIGURES = HERE.parent.parent / "site" / "data" / "figures.json"
OUT = HERE / "figures"
Z = 1.96


def car_figure(disclosure: list[dict], transaction: list[dict]) -> str:
    width, height = 12.0, 6.0
    last = 125
    y_min, y_max = -1.6, 1.0

    def x(day: float) -> float:
        return width * day / last

    def y(percent: float) -> float:
        return height * (percent - y_min) / (y_max - y_min)

    def point(q: dict, value: float) -> str:
        return f"({x(q['day']):.3f},{y(value * 100):.3f})"

    upper = [point(q, q["mean"] + Z * q["se"]) for q in disclosure]
    lower = [point(q, q["mean"] - Z * q["se"]) for q in reversed(disclosure)]
    band = " -- ".join(upper + lower) + " -- cycle"
    mean_d = " -- ".join(point(q, q["mean"]) for q in disclosure)
    mean_t = " -- ".join(point(q, q["mean"]) for q in transaction)

    lines = [
        "\\begin{tikzpicture}[font=\\small]",
        f"  \\fill[accent!22] {band};",
        f"  \\draw[gray!70] (0,{y(0):.3f}) -- ({width},{y(0):.3f});",
        f"  \\draw[black!55, dashed, line width=0.8pt] {mean_t};",
        f"  \\draw[accent, line width=1.2pt] {mean_d};",
        f"  \\draw (0,0) -- ({width},0);",
        f"  \\draw (0,0) -- (0,{height});",
    ]
    for day in (0, 20, 40, 62, 80, 100, 125):
        lines.append(f"  \\draw ({x(day):.3f},0) -- ({x(day):.3f},-0.08) node[below] {{{day}}};")
    tick = -1.5
    while tick <= y_max + 1e-9:
        label = f"${tick:+.1f}$" if abs(tick) > 1e-9 else "0"
        lines.append(f"  \\draw (0,{y(tick):.3f}) -- (-0.08,{y(tick):.3f}) node[left] {{{label}}};")
        tick = round(tick + 0.5, 1)
    lines += [
        f"  \\node[below] at ({width / 2},-0.55) {{Trading days after the event}};",
        f"  \\node[rotate=90, above] at (-0.85,{height / 2}) {{Mean CAR (\\%)}};",
        f"  \\draw[accent, line width=1.2pt] (0.3,{height - 0.3:.2f}) -- (0.9,{height - 0.3:.2f})"
        " node[right, black] {From disclosure, with 95\\% band};",
        f"  \\draw[black!55, dashed, line width=0.8pt] (0.3,{height - 0.75:.2f}) -- (0.9,{height - 0.75:.2f})"
        " node[right, black] {From the trade date};",
        "\\end{tikzpicture}",
    ]
    return "\n".join(lines) + "\n"


def lag_figure(lag: dict) -> str:
    bins = lag["bins"]
    regular = [b for b in bins if b["to"] - b["from"] == 4]
    tail = [b for b in bins if b["to"] - b["from"] != 4]
    width, height = 12.0, 5.0
    slots = len(regular) + 1 + len(tail)
    step = width / slots
    top = 4500

    def y(count: float) -> float:
        return height * count / top

    lines = ["\\begin{tikzpicture}[font=\\small]"]
    for i, b in enumerate(regular):
        shade = "accent!70" if b["to"] < lag["deadline_days"] else "black!45"
        lines.append(
            f"  \\fill[{shade}] ({i * step + 0.03:.3f},0) rectangle ({(i + 1) * step - 0.03:.3f},{y(b['trades']):.3f});"
        )
    for j, b in enumerate(tail):
        i = len(regular) + 1 + j
        lines.append(
            f"  \\fill[black!45] ({i * step + 0.03:.3f},0) rectangle ({(i + 1) * step - 0.03:.3f},{y(b['trades']):.3f});"
        )
        lines.append(
            f"  \\node[below] at ({(i + 0.5) * step:.3f},0) {{{b['from']}+}};"
        )
    deadline = step * lag["deadline_days"] / 5
    lines += [
        f"  \\draw (0,0) -- ({width},0);",
        f"  \\draw (0,0) -- (0,{height});",
        f"  \\draw[dashed] ({deadline:.3f},0) -- ({deadline:.3f},{height - 0.2:.2f})"
        f" node[above] {{{lag['deadline_days']}-day deadline}};",
    ]
    for day in range(0, 90, 15):
        lines.append(f"  \\node[below] at ({step * day / 5:.3f},0) {{{day}}};")
    for count in range(0, top + 1, 1000):
        lines.append(f"  \\draw (0,{y(count):.3f}) -- (-0.08,{y(count):.3f}) node[left] {{{count:,}}};")
    lines += [
        f"  \\node[below] at ({width / 2},-0.5) {{Days from trade to disclosure (5-day bins)}};",
        f"  \\node[rotate=90, above] at (-1.0,{height / 2}) {{Trades}};",
        "\\end{tikzpicture}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    data = json.loads(FIGURES.read_text())
    OUT.mkdir(exist_ok=True)
    (OUT / "car.tex").write_text(car_figure(data["car_disclosure"], data["car_transaction"]))
    (OUT / "lag.tex").write_text(lag_figure(data["lag"]))


if __name__ == "__main__":
    main()
