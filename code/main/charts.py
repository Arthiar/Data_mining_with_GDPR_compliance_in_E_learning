# charts.py
# Functions for drawing the three types of charts used in the analysis.
# Used by analyse.py — not meant to be run directly.

import textwrap

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


# Apply a consistent visual style to all charts
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#F4F7FB",
    "axes.grid": True,
    "grid.color": "white",
    "grid.linewidth": 1.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#CCCCCC",
    "font.family": "sans-serif",
    "font.size": 11,
})

COLOR_BLUE = "#2E86AB"
COLOR_GREEN = "#44BBA4"
COLOR_RED = "#E84855"
COLOR_ORANGE = "#F5A623"

PASS_THRESHOLD = 50.0


def wrap_long_title(text, max_width=48):
    # Break a long title into multiple lines so it fits on the chart without overflowing.
    return "\n".join(textwrap.wrap(str(text), max_width))


def add_caption(figure, caption_text):
    # Add small italic text at the very bottom of the chart to show the insight.
    figure.text(
        0.5, 0.005,
        textwrap.fill(caption_text, 110),
        ha="center", va="bottom",
        fontsize=8.5, style="italic", color="#555555",
        transform=figure.transFigure,
    )


def draw_histogram(scores, title, output_path, show_pass_line=False, insight=""):
    # Draw a bar chart showing how many students got scores in each range.
    # Adds a red dashed line for the mean, an orange dotted line for the median,
    # and optionally a green line at the 50% pass threshold.

    scores_numeric = pd.to_numeric(scores, errors="coerce").dropna()
    if scores_numeric.empty:
        return False

    fig, ax = plt.subplots(figsize=(10, 6))

    # Draw the histogram bars (each bar covers a score range)
    ax.hist(scores_numeric, bins=10, color=COLOR_BLUE, alpha=0.85, edgecolor="white", linewidth=0.8)

    # Calculate and draw the mean line
    mean_score = scores_numeric.mean()
    ax.axvline(mean_score, color=COLOR_RED, linewidth=2, linestyle="--", label=f"Mean {mean_score:.1f}")

    # Calculate and draw the median line
    median_score = scores_numeric.median()
    ax.axvline(median_score, color=COLOR_ORANGE, linewidth=2, linestyle=":", label=f"Median {median_score:.1f}")

    # Optionally draw a green line at the 50% pass mark and label the pass rate
    if show_pass_line and scores_numeric.max() <= 101:
        ax.axvline(PASS_THRESHOLD, color=COLOR_GREEN, linewidth=2, linestyle="-.",
                   label=f"Pass threshold ({PASS_THRESHOLD:.0f}%)")

        number_passed = int((scores_numeric >= PASS_THRESHOLD).sum())
        percent_passed = 100.0 * number_passed / len(scores_numeric)

        score_range = scores_numeric.max() - scores_numeric.min()
        label_x = PASS_THRESHOLD + score_range * 0.03
        label_y = ax.get_ylim()[1] * 0.88

        ax.text(label_x, label_y, f"Pass rate\n{percent_passed:.1f}%",
                fontsize=10, color=COLOR_GREEN, fontweight="bold",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

    ax.set_title(wrap_long_title(title), fontsize=13, fontweight="bold")
    ax.set_xlabel("Score")
    ax.set_ylabel("Number of Students")
    ax.legend(loc="upper right")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    if insight:
        add_caption(fig, insight)

    bottom_margin = 0.08 if insight else 0
    fig.tight_layout(rect=[0, bottom_margin, 1, 1])
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


def draw_pass_fail_bar(n_pass, n_fail, title, output_path, insight=""):
    # Draw a horizontal bar showing what percentage of students passed versus failed.
    # The green section shows pass, the red section shows fail.

    total = n_pass + n_fail
    if total == 0:
        return False

    percent_pass = 100.0 * n_pass / total
    percent_fail = 100.0 * n_fail / total

    fig, ax = plt.subplots(figsize=(10, 3))

    # Draw the green (pass) section
    ax.barh(["Result"], [percent_pass], color=COLOR_GREEN, edgecolor="white", linewidth=1,
            label=f"Pass (>=50%)  {percent_pass:.1f}%  (n={n_pass})")

    # Draw the red (fail) section, starting where the green one ends
    ax.barh(["Result"], [percent_fail], left=[percent_pass], color=COLOR_RED, edgecolor="white", linewidth=1,
            label=f"Fail  {percent_fail:.1f}%  (n={n_fail})")

    ax.set_xlim(0, 100)
    ax.set_xlabel("Percentage (%)")
    ax.set_title(wrap_long_title(title), fontsize=13, fontweight="bold")
    ax.legend(loc="lower right")
    ax.grid(False)

    # Add the count as text on each section, but only if the section is wide enough to fit
    if percent_pass > 10:
        ax.text(percent_pass / 2, 0, f"{n_pass}", ha="center", va="center",
                fontsize=12, fontweight="bold", color="white")
    if percent_fail > 10:
        ax.text(percent_pass + percent_fail / 2, 0, f"{n_fail}", ha="center", va="center",
                fontsize=12, fontweight="bold", color="white")

    if insight:
        add_caption(fig, insight)

    bottom_margin = 0.10 if insight else 0
    fig.tight_layout(rect=[0, bottom_margin, 1, 1])
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


def draw_scatter_with_trend(x_data, y_data, title, x_label, y_label, output_path, insight=""):
    # Draw a dot plot of two variables (one per axis) and a trend line.
    # The trend line shows whether higher values on the x-axis tend to match higher or lower y values.
    # The correlation value (r) in the legend measures how strong that relationship is.

    x_numeric = pd.to_numeric(x_data, errors="coerce")
    y_numeric = pd.to_numeric(y_data, errors="coerce")

    # Only keep rows where both x and y are valid numbers
    paired_df = pd.DataFrame({"x": x_numeric, "y": y_numeric}).dropna()

    if paired_df.empty or len(paired_df) < 3:
        return False

    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot each data point as a dot
    ax.scatter(paired_df["x"], paired_df["y"], color=COLOR_BLUE, alpha=0.75,
               edgecolors="white", linewidths=0.5, s=80, zorder=3)

    # Calculate the slope and intercept of the best-fit line
    coefficients = np.polyfit(paired_df["x"], paired_df["y"], 1)
    trend_line = np.poly1d(coefficients)

    # Generate evenly spaced x values to draw a smooth line
    x_range = np.linspace(paired_df["x"].min(), paired_df["x"].max(), 200)

    # Calculate the correlation coefficient (how closely x and y move together)
    correlation = float(paired_df["x"].corr(paired_df["y"]))

    # Draw the trend line
    ax.plot(x_range, trend_line(x_range), color=COLOR_GREEN, linewidth=2.5, linestyle="--",
            label=f"Trend (r = {correlation:+.2f})")
    ax.legend(fontsize=10)

    ax.set_title(wrap_long_title(title), fontsize=13, fontweight="bold")
    ax.set_xlabel(x_label, fontsize=11)
    ax.set_ylabel(y_label, fontsize=11)

    if insight:
        add_caption(fig, insight)

    bottom_margin = 0.08 if insight else 0
    fig.tight_layout(rect=[0, bottom_margin, 1, 1])
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True
