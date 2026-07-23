"""
One matplotlib style for every KPI chart, built on the data-viz reference
palette (CVD-validated, light surface). Import `apply_style()` once per script
and use SERIES / STATUS / INK by role — never raw hex in the KPI scripts.
"""
from __future__ import annotations

# Categorical slots, fixed order (never cycled). See references/palette.md.
SERIES = [
    "#2a78d6",  # 1 blue
    "#008300",  # 2 green
    "#e87ba4",  # 3 magenta
    "#eda100",  # 4 yellow
    "#1baf7a",  # 5 aqua
    "#eb6834",  # 6 orange
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]

STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

INK = {
    "surface": "#fcfcfb",
    "primary": "#0b0b0b",
    "secondary": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "baseline": "#c3c2b7",
}


def apply_style() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.dpi": 130,
        "savefig.dpi": 130,
        "figure.facecolor": INK["surface"],
        "axes.facecolor": INK["surface"],
        "savefig.facecolor": INK["surface"],
        "font.family": "sans-serif",
        # DejaVu Sans is bundled with matplotlib and carries the arrow/unicode
        # glyphs used in scenario labels (Helvetica Neue does not).
        "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
        "font.size": 11,
        "axes.edgecolor": INK["baseline"],
        "axes.linewidth": 1.0,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": INK["grid"],
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK["primary"],
        "axes.labelcolor": INK["secondary"],
        "text.color": INK["primary"],
        "xtick.color": INK["muted"],
        "ytick.color": INK["muted"],
        "xtick.labelcolor": INK["secondary"],
        "ytick.labelcolor": INK["secondary"],
        "legend.frameon": False,
        "legend.fontsize": 10,
    })


def savefig(fig, name: str) -> None:
    from pathlib import Path
    out = Path(__file__).resolve().parent / "results" / name
    fig.savefig(out, bbox_inches="tight")
    print(f"  wrote {out.relative_to(out.parent.parent)}")
