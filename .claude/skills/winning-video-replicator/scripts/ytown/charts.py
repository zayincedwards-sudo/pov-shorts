"""Retention charts (PNG, matplotlib). Colours and marks follow the dataviz reference palette.

chart_video: the retention curve over the episode's own timeline, section bands behind it, the
beat kinds as a strip under the axis (fixed hue per kind, never cycled), dips marked and the
three biggest labelled with the sentence being spoken.
chart_channel: every video's curve against the share of runtime, hits in blue, the rest muted.
"""
from __future__ import annotations

from pathlib import Path

SURFACE, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BAND = "#f0efec"
SERIES = "#2a78d6"
DIP = "#e34948"
# fixed categorical order from the reference palette, one slot per beat kind
KIND_COLOURS = {"clip": "#2a78d6", "still": "#eb6834", "card": "#1baf7a", "hero": "#eda100", "grid": "#e87ba4",
                "recording": "#008300", "host": "#4a3aa7", "text": "#e34948", "montage": "#2a78d6", "flat": "#eb6834", "beat": "#c3c2b7"}
SPAN_COLOURS = {"recording": "#008300", "price_flash": "#eda100", "card": "#1baf7a", "music": "#9085e9", "narration": "#2a78d6", "tag": "#898781"}


def _mmss(t, _=None):
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"


def chart_video(res: dict, join: dict, out: Path, title: str) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.ticker import FuncFormatter

    curve = res["curve"]
    dur = res["duration"]
    fig = plt.figure(figsize=(13, 6), dpi=140, facecolor=SURFACE)
    gs = fig.add_gridspec(3, 1, height_ratios=[10, 1.1, 1.1], hspace=0.08)
    ax = fig.add_subplot(gs[0])
    ax.set_facecolor(SURFACE)
    for i, s in enumerate(join.get("sections", [])):
        if i % 2 == 0:
            ax.axvspan(s["t0"], s["t1"], color=BAND, lw=0, zorder=0)
        ax.text((s["t0"] + s["t1"]) / 2, 1.02, s["name"][:14], ha="center", va="bottom", fontsize=7, color=MUTED, transform=ax.get_xaxis_transform(), clip_on=False)
    ax.plot(range(len(curve)), curve, color=SERIES, lw=2, zorder=3)
    for d in res["dips"][:12]:
        ax.plot([d["t"]], [curve[min(len(curve) - 1, d["t"])]], "o", ms=7, color=DIP, mec=SURFACE, mew=1.5, zorder=4)
    for d in res["dips"][:3]:
        y = curve[min(len(curve) - 1, d["t"])]
        txt = (d.get("sentence") or "")[:52] + ("…" if d.get("sentence") and len(d["sentence"]) > 52 else "")
        ax.annotate(f"{d['at']}  −{d['loss_points']:.0f} pts\n{txt}", (d["t"], y), xytext=(8, 12), textcoords="offset points",
                    fontsize=7.5, color=INK2, arrowprops=dict(arrowstyle="-", color=BASE, lw=1))
    s = res["survival"]
    ax.text(0.01, 0.04, f"30 s: {s['30s']:.0%} still watching · midpoint {s['mid']:.0%} · end {s['end']:.0%} · "
            f"baseline loss {res['baseline_pct_per_min']:.1f}%/min", transform=ax.transAxes, fontsize=8.5, color=INK2)
    ax.set_xlim(0, dur)
    ax.set_ylim(0, max(1.05, max(curve) * 1.05))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.xaxis.set_major_formatter(FuncFormatter(_mmss))
    ax.grid(axis="y", color=GRID, lw=0.8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(BASE)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.set_ylabel("share of viewers still watching", color=INK2, fontsize=9)
    ax.set_title(f"{title[:70]}  ·  audience retention over the build timeline", loc="left", color=INK, fontsize=11, pad=22)
    ax.tick_params(axis="x", labelbottom=False)

    strip = fig.add_subplot(gs[1], sharex=ax)
    strip.set_facecolor(SURFACE)
    kinds = []
    for b in join.get("beats", []):
        c = KIND_COLOURS.get(b["kind"], BASE)
        strip.axvspan(b["t0"], max(b["t1"], b["t0"] + 0.3), color=c, lw=0)
        if b["kind"] not in kinds:
            kinds.append(b["kind"])
    strip.set_yticks([])
    strip.set_ylabel("shots", color=INK2, fontsize=8, rotation=0, ha="right", va="center")
    strip.tick_params(axis="x", labelbottom=False)
    for sp in strip.spines.values():
        sp.set_visible(False)

    spans_ax = fig.add_subplot(gs[2], sharex=ax)
    spans_ax.set_facecolor(SURFACE)
    types = []
    for sp_ in sorted(join.get("spans", []), key=lambda s: -(s["t1"] - s["t0"])):   # long spans first, short ones on top
        if sp_["type"] == "take":                                                      # a take is a boundary, not a fill
            spans_ax.axvline(sp_["t0"], color=INK2, lw=1.2, ymin=0.0, ymax=1.0)
            continue
        c = SPAN_COLOURS.get(sp_["type"], BASE)
        spans_ax.axvspan(sp_["t0"], max(sp_["t1"], sp_["t0"] + 0.3), color=c, lw=0, alpha=0.9)
        if sp_["type"] not in types:
            types.append(sp_["type"])
    if any(s["type"] == "take" for s in join.get("spans", [])):
        types.append("take (tick = a new voice take)")
    spans_ax.set_yticks([])
    spans_ax.set_ylabel("on top", color=INK2, fontsize=8, rotation=0, ha="right", va="center")
    spans_ax.xaxis.set_major_formatter(FuncFormatter(_mmss))
    spans_ax.tick_params(colors=MUTED, labelsize=8)
    for sp in spans_ax.spines.values():
        sp.set_visible(False)
    handles = [Patch(color=KIND_COLOURS.get(k, BASE), label=k) for k in kinds] + \
              [Patch(color=(INK2 if t.startswith("take") else SPAN_COLOURS.get(t, BASE)), label=t) for t in types]
    if handles:
        fig.legend(handles=handles, loc="lower center", ncol=min(8, len(handles)), frameon=False, fontsize=8, labelcolor=INK2, bbox_to_anchor=(0.5, -0.01))
    fig.savefig(out, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return out


def chart_channel(recs: list[dict], curves: dict[str, list[float]], out: Path, name: str) -> Path | None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    if not curves:
        return None
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=140, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for r in recs:
        c = curves.get(r["id"])
        if not c:
            continue
        xs = [100.0 * i / max(1, len(c) - 1) for i in range(len(c))]
        hit = bool(r.get("hit"))
        ax.plot(xs, c, color=SERIES if hit else BASE, lw=2.2 if hit else 1.4, zorder=3 if hit else 2, alpha=1 if hit else 0.9)
        if hit:
            ax.text(100.5, c[-1], (r.get("title") or r["id"])[:28], fontsize=7.5, color=INK2, va="center")
    ax.plot([], [], color=SERIES, lw=2.2, label="hits (views/day at least 2x the neighbours)")
    ax.plot([], [], color=BASE, lw=1.4, label="the rest")
    ax.legend(frameon=False, fontsize=8, loc="upper right", labelcolor=INK2)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1.05)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.grid(axis="y", color=GRID, lw=0.8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.set_xlabel("share of the runtime", color=INK2, fontsize=9)
    ax.set_ylabel("share of viewers still watching", color=INK2, fontsize=9)
    ax.set_title(f"{name}: retention of every video, hits against the rest", loc="left", color=INK, fontsize=11)
    fig.savefig(out, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return out
