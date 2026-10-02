"""Render docs/before_after.png from the measured result files."""

from __future__ import annotations

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import NullFormatter  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e3e2de"
SERIES = {
    "ddmin": ("#eb6834", "Delta debugging (ddmin)"),
    "bisect": ("#1baf7a", "Binary splitting"),
    "pool": ("#2a78d6", "polluterpool"),
}
ORDER = ["ddmin", "bisect", "pool"]


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9, length=3, width=0.8)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def bars(ax, values, title, subtitle, fmt, ylabel):
    xs = range(len(ORDER))
    heights = [values[k] for k in ORDER]
    ax.bar(
        xs,
        heights,
        width=0.52,
        color=[SERIES[k][0] for k in ORDER],
        edgecolor=SURFACE,
        linewidth=2,
    )
    for x, height in zip(xs, heights):
        ax.text(
            x,
            height * 1.03,
            fmt.format(height),
            ha="center",
            va="bottom",
            fontsize=10,
            color=INK,
            fontweight="bold",
        )
    ax.set_xticks(list(xs))
    ax.set_xticklabels([SERIES[k][1].replace(" (ddmin)", "") for k in ORDER], fontsize=9)
    ax.set_ylim(0, max(heights) * 1.18)
    ax.set_ylabel(ylabel, fontsize=9, color=MUTED)
    ax.set_title(title, loc="left", fontsize=11, color=INK, fontweight="bold", pad=14)
    ax.text(
        0,
        1.015,
        subtitle,
        transform=ax.transAxes,
        fontsize=9,
        color=MUTED,
        va="bottom",
    )
    style(ax)


def lines(ax, rows, xkey, title, subtitle, xlabel):
    xs = [row[xkey] for row in rows]
    for key in ORDER:
        ax.plot(
            xs,
            [row[key]["executions"] for row in rows],
            color=SERIES[key][0],
            linewidth=2,
            marker="o",
            markersize=5.5,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            label=SERIES[key][1],
        )
    ax.set_xscale("log", base=2)
    ax.set_yscale("log", base=10)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(x) for x in xs])
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel(xlabel, fontsize=9, color=MUTED)
    ax.set_ylabel("test executions (log scale)", fontsize=9, color=MUTED)
    ax.set_title(title, loc="left", fontsize=11, color=INK, fontweight="bold", pad=14)
    ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=9, color=MUTED, va="bottom")
    style(ax)
    for key in ORDER:
        ax.annotate(
            f"{rows[-1][key]['executions']:,.0f}",
            (xs[-1], rows[-1][key]["executions"]),
            textcoords="offset points",
            xytext=(6, -3),
            fontsize=8.5,
            color=INK,
        )


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs = os.path.join(root, "docs")
    with open(os.path.join(docs, "results_real.json"), encoding="utf-8") as handle:
        real = json.load(handle)
    with open(os.path.join(docs, "results_sweep.json"), encoding="utf-8") as handle:
        sweep = json.load(handle)

    fig, axes = plt.subplots(2, 2, figsize=(12.4, 8.6))
    fig.patch.set_facecolor(SURFACE)

    strategies = real["strategies"]
    bars(
        axes[0][0],
        {k: strategies[k]["executions"] for k in ORDER},
        "Test executions to name every polluter",
        f"real pytest suite, {real['suite_tests']} tests, {real['victims']} victims, "
        f"{real['pairs']} polluter-victim pairs",
        "{:,.0f}",
        "test executions",
    )
    bars(
        axes[0][1],
        {k: strategies[k]["wall_seconds"] for k in ORDER},
        "Wall clock to name every polluter",
        "same suite, one fresh pytest process per candidate order",
        "{:,.0f}s",
        "seconds",
    )
    lines(
        axes[1][0],
        sweep["by_size"],
        "n_tests",
        "Executions as the suite grows",
        f"exact order-dependency model, 8 victims, mean of {sweep['repeats']} suites",
        "tests in suite",
    )
    lines(
        axes[1][1],
        sweep["by_victims"],
        "n_victims",
        "Executions as victims accumulate",
        f"exact model, 800 tests, mean of {sweep['repeats']} suites",
        "order dependent victims in suite",
    )

    handles, labels = axes[1][0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=10,
        bbox_to_anchor=(0.5, -0.004),
    )
    fig.suptitle(
        "polluterpool: localizing order dependent test failures",
        x=0.009,
        y=0.985,
        ha="left",
        fontsize=14,
        color=INK,
        fontweight="bold",
    )
    fig.text(
        0.009,
        0.947,
        "Lower is better. Every strategy returns the identical, complete set of "
        "polluter-victim pairs; only the cost of getting there differs.",
        fontsize=9.5,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.045, 1, 0.935))
    out = os.path.join(docs, "before_after.png")
    fig.savefig(out, dpi=170, facecolor=SURFACE)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
