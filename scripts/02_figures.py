#!/usr/bin/env python3
"""Figures for a BAER run. All values read from the stats JSON.

Usage: python scripts/02_figures.py [--stats data/processed/baer_stats_2026.09.json]
"""
from __future__ import annotations

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

GREEN, BLUE, GREY, RED = "#2a6f4e", "#2a5f8f", "#d9d9d9", "#a33d3d"


def fig_types(s, out, final):
    a = dict(s["adulteration_types"])
    a.pop("substitution", None)
    names = list(a) + ["substitution"]
    vals = [a[n] for n in list(a)] + [0]
    total = s["n_events"]
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    colors = [BLUE] * len(a) + [RED]
    bars = ax.barh(names[::-1], vals[::-1], color=colors[::-1])
    for b, v in zip(bars, vals[::-1]):
        label = f"{v:,} ({100*v/total:.1f}%)" if v else "0  \u2190 none"
        ax.text(v + total * 0.012, b.get_y() + b.get_height()/2, label,
                va="center", fontsize=9,
                color=RED if not v else "black",
                fontweight="bold" if not v else "normal")
    ax.set_xlim(0, max(vals) * 1.35)
    ax.set_xlabel(f"BAER events (n = {total:,})")
    ax.set_title("The US regulatory record never states botanical substitution",
                 pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.5, 0.02, s["provenance"], ha="center", fontsize=6.5,
             color="dimgray")
    if not final:
        fig.text(0.5, 0.5, "DRAFT", fontsize=56, color="gray", alpha=0.15,
                 ha="center", va="center", rotation=28)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    p = os.path.join(out, "adulteration_types.png")
    fig.savefig(p, dpi=150); plt.close(fig); return p


def fig_botanicals(s, out, final):
    top = s["top_botanicals"]
    names, vals = list(top)[::-1], list(top.values())[::-1]
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    colors = [RED if n == "Mitragyna speciosa" else BLUE for n in names]
    bars = ax.barh(names, vals, color=colors)
    for b, v in zip(bars, vals):
        ax.text(v + max(vals) * 0.015, b.get_y() + b.get_height()/2,
                f"{v:,}", va="center", fontsize=9)
    ax.set_xlim(0, max(vals) * 1.15)
    ax.set_xlabel(f"BAER events (of {s['n_events']:,} total)")
    ax.set_title("Kratom leads the US botanical regulatory record", pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.5, 0.02, "Counts track trade volume as well as risk; no public "
             "denominator of products per botanical exists.",
             ha="center", fontsize=6.5, color="dimgray")
    if not final:
        fig.text(0.5, 0.5, "DRAFT", fontsize=56, color="gray", alpha=0.15,
                 ha="center", va="center", rotation=28)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    p = os.path.join(out, "top_botanicals.png")
    fig.savefig(p, dpi=150); plt.close(fig); return p


def fig_evidence(s, out, final):
    rt = s["record_types"]
    order = ["adverse_event", "notice", "recall"]
    labels = ["Adverse event\n(CAERS)\nno causality assessment",
              "60-day notice\n(Prop 65)\nprivate assertion",
              "Recall\nagency determination"]
    vals = [rt[k] for k in order]
    total = sum(vals)
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    bars = ax.bar(labels, vals, color=[RED, "#c98b3a", GREEN], width=0.55)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + total * 0.02,
                f"{v:,}\n({100*v/total:.1f}%)", ha="center", fontsize=10)
    ax.set_ylim(0, max(vals) * 1.25)
    ax.set_ylabel("BAER events")
    ax.set_title("Seven in ten events come from the weakest evidence class",
                 pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", labelsize=8)
    if not final:
        fig.text(0.5, 0.5, "DRAFT", fontsize=56, color="gray", alpha=0.15,
                 ha="center", va="center", rotation=28)
    fig.tight_layout()
    p = os.path.join(out, "evidence_classes.png")
    fig.savefig(p, dpi=150); plt.close(fig); return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", default="data/processed/baer_stats_2026.09.json")
    ap.add_argument("--out", default="docs/figures")
    ap.add_argument("--final", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    s = json.load(open(a.stats, encoding="utf-8"))
    for p in (fig_types(s, a.out, a.final), fig_botanicals(s, a.out, a.final),
              fig_evidence(s, a.out, a.final)):
        print("wrote", p)


if __name__ == "__main__":
    main()
