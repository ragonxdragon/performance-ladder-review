"""Render the README charts from results.csv and summary.csv.

Run from the repository root:

    uv run --no-project --with matplotlib python results/make_charts.py

CI pins matplotlib (see .github/workflows/ci.yml) so the SVG output is
byte-stable; regenerate with the same version before committing.

Only rows marked measured=yes reach a chart. Each change contributes its
first row in results.csv (its headline metric), and only when both values are
positive numbers, since a log axis has no place for zero. Changes measured
down to zero are listed in the README table instead.
"""

from __future__ import annotations

import csv
import math
from collections import OrderedDict
from pathlib import Path

import matplotlib

matplotlib.use("svg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "charts"

# Transparent backgrounds, so the ink has to read on GitHub's light (#ffffff)
# and dark (#0d1117) page colors. Teal is the accent; gray marks "before".
THEMES = {
    "light": {
        "accent": "#0f766e",
        "before": "#8c959f",
        "ink": "#1f2328",
        "ink2": "#59636e",
        "grid": "#d1d9e0",
    },
    "dark": {
        "accent": "#2dd4bf",
        "before": "#6e7681",
        "ink": "#f0f6fc",
        "ink2": "#9198a1",
        "grid": "#3d444d",
    },
}

PROJECT_TAG = {
    "twinflow (Python, public)": "twinflow",
    "Desktop AI model manager (Rust/TypeScript, private)": "desktop app",
    "Cellular IoT gateway firmware (ESP32, client work, private)": "firmware",
}

SHORT = {
    "Hold the event-log hash until an append changes the log": "Event-log hash held until append",
    "Count repeated sequence numbers in one pass instead of a count per element": "Duplicate count in one pass",
    "Resolve the hook interpreter once, from the virtualenv": "Hook interpreter from virtualenv",
    "Reparse only the unfinished block of a streaming answer; settled blocks are memoized": "Streaming answer render",
    "Lazy-load the message formatting code out of the startup bundle (launch time change not measurable above noise)": "Startup JavaScript",
    "Build the upload scan inside the upload document instead of building and deep-copying it (maintenance line)": "Scan built in place",
    "Reuse one lookup key when storing a tag read": "Tag store lookup key",
    "Send WebSocket frames in writes of up to 1,024 bytes, header and first slice together": "WebSocket write batching",
    "Cap the boot probe's reader link wait and feed the watchdog while waiting": "Boot reader probe",
    "Flush queued unsolicited notifications without an idle sleep in the host loop": "Emulator notification flush",
    "Poll cloud device registration every 0.5 s instead of every 3 s": "Registration poll interval",
    "Extract the reader's XML payload by offset with one copy": "Reader XML unwrap",
    "Parse inventory responses with a filter for the three fields read": "Inventory parse filter",
    "Serialize the status patch once into a buffer sized up front": "Status patch serialization",
    "Wire gzip upload compression to a config flag (opt-in, off by default)": "Gzip upload (opt-in)",
}

TIME_MS = {"us": 1e-3, "ms": 1.0, "s": 1e3}
SIZE_KB = {"B": 1 / 1024, "KB": 1.0}
FAMILIES = [
    ("Time", "milliseconds, log scale"),
    ("Size", "kilobytes, log scale"),
    ("Counts and ratios", "unit per row, log scale"),
]


def number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def load_headlines() -> list[dict]:
    with open(HERE / "results.csv", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    first: OrderedDict[tuple[str, str], dict] = OrderedDict()
    for row in rows:
        first.setdefault((row["project"], row["change"]), row)
    picked = []
    for row in first.values():
        before, after = number(row["before"]), number(row["after"])
        if row["measured"] != "yes" or not before or not after:
            continue
        if before <= 0 or after <= 0:
            continue
        label = SHORT.get(row["change"], row["change"][:40])
        picked.append(
            {
                **row,
                "b": before,
                "a": after,
                "label": f"{label} ({PROJECT_TAG.get(row['project'], row['project'])})",
            }
        )
    return picked


def family(row: dict) -> str:
    if row["unit"] in TIME_MS:
        return "Time"
    if row["unit"] in SIZE_KB:
        return "Size"
    return "Counts and ratios"


def scaled(row: dict, value: float) -> float:
    if row["unit"] in TIME_MS:
        return value * TIME_MS[row["unit"]]
    if row["unit"] in SIZE_KB:
        return value * SIZE_KB[row["unit"]]
    return value


def fmt_time(ms: float) -> str:
    if ms >= 1000:
        return f"{ms / 1000:.3g} s"
    if ms >= 1:
        return f"{ms:.3g} ms"
    return f"{ms * 1000:.3g} us"


def fmt_value(row: dict, value: float) -> str:
    fam = family(row)
    if fam == "Time":
        return fmt_time(value)
    if fam == "Size":
        return f"{value:,.4g} KB" if value >= 1 else f"{value * 1024:.0f} B"
    unit = row["unit"]
    shown = f"{value:,.3g}" if value < 1000 else f"{value:,.0f}"
    if unit.startswith("%"):
        return f"{shown}%"
    if unit.startswith("x "):
        return f"{shown}x"
    return f"{shown} {unit}"


def pair_text(row: dict, before: float, after: float) -> str:
    """Before and after as one label; a count unit is written once, after both numbers."""
    left, right = fmt_value(row, before), fmt_value(row, after)
    unit = row["unit"]
    if family(row) == "Counts and ratios" and not unit.startswith(("%", "x ")):
        left = left.removesuffix(f" {unit}")
    return f"{left}  ->  {right}"


def fmt_factor(f: float) -> str:
    if f >= 100:
        return f"{f:,.0f}x"
    if f >= 10:
        return f"{f:.1f}x"
    return f"{f:.2f}x"


def setup(theme: dict) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "svg.fonttype": "path",
            "svg.hashsalt": "performance-ladder-review",
            "text.color": theme["ink"],
            "axes.labelcolor": theme["ink2"],
            "xtick.color": theme["ink2"],
            "ytick.color": theme["ink"],
            "axes.edgecolor": theme["grid"],
            "axes.linewidth": 1.0,
        }
    )


def compact(value: float, suffix: str = "") -> str:
    if value >= 1e6:
        return f"{value / 1e6:g}M{suffix}"
    if value >= 1e3:
        return f"{value / 1e3:g}K{suffix}"
    return f"{value:g}{suffix}"


def style_axis(ax, theme: dict, log: bool, suffix: str = "") -> None:
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(theme["grid"])
    ax.tick_params(axis="y", length=0, pad=8)
    ax.tick_params(axis="x", colors=theme["ink2"], length=0)
    ax.grid(axis="x", color=theme["grid"], linewidth=1.0, linestyle="-")
    ax.set_axisbelow(True)
    ax.set_facecolor("none")
    if log:
        ax.xaxis.set_major_locator(LogLocator(base=10))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: compact(v, suffix)))


def save(fig, name: str, mode: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        OUT / f"{name}-{mode}.svg",
        format="svg",
        transparent=True,
        bbox_inches="tight",
        pad_inches=0.15,
        metadata={"Date": None, "Creator": None},
    )
    plt.close(fig)


def chart_before_after(rows: list[dict], mode: str) -> None:
    theme = THEMES[mode]
    setup(theme)
    groups = [(name, sub, [r for r in rows if family(r) == name]) for name, sub in FAMILIES]
    groups = [g for g in groups if g[2]]
    heights = [len(g[2]) + 1.4 for g in groups]
    fig, axes = plt.subplots(
        len(groups), 1, figsize=(10, 0.42 * sum(heights) + 1.0), gridspec_kw={"height_ratios": heights}
    )
    axes = axes if len(groups) > 1 else [axes]
    for ax, (name, sub, items) in zip(axes, groups):
        items = sorted(items, key=lambda r: scaled(r, r["b"]) / scaled(r, r["a"]))
        lows = [scaled(r, min(r["a"], r["b"])) for r in items]
        highs = [scaled(r, max(r["a"], r["b"])) for r in items]
        for y, r in enumerate(items):
            b, a = scaled(r, r["b"]), scaled(r, r["a"])
            ax.plot([b, a], [y, y], color=theme["accent"], linewidth=2, solid_capstyle="round", alpha=0.45, zorder=2)
            ax.scatter([b], [y], s=64, facecolor="none", edgecolor=theme["before"], linewidth=2, zorder=3)
            ax.scatter([a], [y], s=64, color=theme["accent"], zorder=4)
            ax.annotate(
                pair_text(r, b, a),
                xy=(1.0, y),
                xycoords=("axes fraction", "data"),
                xytext=(12, 0),
                textcoords="offset points",
                va="center",
                ha="left",
                fontsize=9,
                color=theme["ink2"],
            )
        ax.set_xscale("log")
        ax.set_xlim(min(lows) / 2.5, max(highs) * 2.5)
        ax.set_yticks(range(len(items)), [r["label"] for r in items])
        ax.set_ylim(-0.7, len(items) - 0.3)
        style_axis(ax, theme, log=True)
        ax.set_title(f"{name}  ({sub})", loc="left", fontsize=10.5, color=theme["ink"], fontweight="bold", pad=8)
    handles = [
        Line2D([], [], marker="o", linestyle="none", markersize=8, markerfacecolor="none",
               markeredgecolor=theme["before"], markeredgewidth=2, label="before"),
        Line2D([], [], marker="o", linestyle="none", markersize=8, color=theme["accent"], label="after"),
    ]
    fig.legend(handles=handles, loc="upper right", ncol=2, frameon=False, fontsize=9.5, labelcolor=theme["ink2"],
               bbox_to_anchor=(0.99, 1.0))
    fig.suptitle("Measured before and after, one headline metric per change", x=0.01, ha="left",
                 fontsize=12, fontweight="bold", color=theme["ink"])
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    save(fig, "before-after", mode)


def chart_factor(rows: list[dict], mode: str) -> None:
    theme = THEMES[mode]
    setup(theme)
    items = sorted(rows, key=lambda r: r["b"] / r["a"])
    fig, ax = plt.subplots(figsize=(10, 0.4 * len(items) + 1.3))
    for y, r in enumerate(items):
        f = r["b"] / r["a"]
        ax.plot([1, f], [y, y], color=theme["accent"], linewidth=2, solid_capstyle="round", zorder=2)
        ax.scatter([f], [y], s=64, color=theme["accent"], zorder=3)
        ax.annotate(fmt_factor(f), xy=(f, y), xytext=(8, 0), textcoords="offset points", va="center",
                    ha="left", fontsize=9, color=theme["ink2"])
    ax.set_xscale("log")
    top = max(r["b"] / r["a"] for r in items)
    ax.set_xlim(1, 10 ** (math.ceil(math.log10(top)) + 0.6))
    ax.set_yticks(range(len(items)), [r["label"] for r in items])
    ax.set_ylim(-0.7, len(items) - 0.3)
    style_axis(ax, theme, log=True, suffix="x")
    ax.set_xlabel("before / after (log scale; 1x = no change)", color=theme["ink2"])
    ax.set_title("Reduction factor per measured change", loc="left", fontsize=12, fontweight="bold",
                 color=theme["ink"], pad=10)
    fig.tight_layout()
    save(fig, "reduction-factor", mode)


def chart_verdicts(mode: str) -> None:
    theme = THEMES[mode]
    setup(theme)
    with open(HERE / "summary.csv", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    labels = []
    for r in rows:
        tag = PROJECT_TAG.get(r["project"], r["project"])
        if not r["marker_snapshot"].startswith("main"):
            tag += " (2026-09-04 tree)"
        labels.append(tag)
    verdicts = [("Applied", "markers_applied"), ("Deferred", "markers_deferred"), ("Rejected", "markers_rejected")]
    top = max(int(r[key]) for r in rows for _, key in verdicts)
    fig, axes = plt.subplots(1, 3, figsize=(10, 0.42 * len(rows) + 1.4), sharey=True)
    for ax, (title, key) in zip(axes, verdicts):
        values = [int(r[key]) for r in rows]
        ys = list(range(len(rows)))[::-1]
        ax.barh(ys, values, height=0.45, color=theme["accent"], zorder=2)
        ax.set_xlim(0, top * 1.3)
        for y, v in zip(ys, values):
            ax.annotate(str(v), xy=(v, y), xytext=(5, 0), textcoords="offset points", va="center", ha="left",
                        fontsize=9.5, color=theme["ink"])
        ax.set_yticks(ys, labels)
        ax.set_xticks([])
        style_axis(ax, theme, log=False)
        ax.grid(False)
        ax.spines["bottom"].set_visible(False)
        ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold", color=theme["ink"])
    fig.suptitle("Marker decisions by project (one scale across panels)", x=0.01, ha="left",
                 fontsize=12, fontweight="bold", color=theme["ink"])
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save(fig, "marker-verdicts", mode)


def main() -> None:
    rows = load_headlines()
    for mode in THEMES:
        chart_before_after(rows, mode)
        chart_factor(rows, mode)
        chart_verdicts(mode)
    print(f"{len(rows)} measured headline rows charted; SVGs in {OUT}")


if __name__ == "__main__":
    main()
