"""生成报告用图（统一视觉规范，英文标注）。

输入：results/*.csv 与 data/ais_moving.parquet
输出：results/figures/*.png
"""
import json
import os

import h3
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection, PolyCollection

RES = "d:/trae/repo/results"
FIG = f"{RES}/figures"
COAST = "d:/trae/data/geo/ne_110m_coastline.geojson"
os.makedirs(FIG, exist_ok=True)

NAVY, TEAL, ORANGE = "#12355B", "#0FA3B1", "#F28C28"
RED, GRAY, GREEN = "#C1272D", "#8896A6", "#2E8B57"

plt.rcParams.update({
    "figure.dpi": 160,
    "savefig.dpi": 220,
    "font.size": 10,
    "font.family": "DejaVu Sans",
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.edgecolor": "#4a4a4a",
    "axes.linewidth": 0.8,
    "axes.grid": True,
    "grid.color": "#d9dde3",
    "grid.linewidth": 0.6,
    "legend.frameon": False,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})


def despine(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def load_coast():
    with open(COAST, encoding="utf-8") as f:
        gj = json.load(f)
    segs = []
    for feat in gj["features"]:
        geom = feat["geometry"]
        if geom["type"] == "LineString":
            segs.append(np.array(geom["coordinates"]))
        elif geom["type"] == "MultiLineString":
            segs.extend(np.array(c) for c in geom["coordinates"])
    return segs


COAST_SEGS = load_coast()


def add_coast(ax, lw=0.6, color="#5f6b7a"):
    ax.add_collection(LineCollection(COAST_SEGS, colors=color, linewidths=lw, zorder=1))


# ---------- 图 1：面积随纬度的畸变 ----------

def fig1_area_lat():
    e1 = pd.read_csv(f"{RES}/e1_area_by_lat.csv")
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.2))

    cmap = plt.get_cmap("viridis")
    for i, (res, sub) in enumerate(e1.groupby("res")):
        sub = sub.sort_values("lat_band")
        c = cmap(i / 6)
        ax[0].plot(sub["lat_band"] + 5, sub["area_mean"], marker="o", ms=4,
                   color=c, label=f"res {res}")
        ax[1].plot(sub["lat_band"] + 5, sub["area_cv"], marker="o", ms=4, color=c)
    ax[0].set_yscale("log")
    ax[0].set_xlabel("Latitude band center (°N)")
    ax[0].set_ylabel("Mean cell area (km², log)")
    ax[0].set_title("(a) H3 area is nearly latitude-invariant")
    ax[0].legend(fontsize=7, ncol=2, loc="lower right")
    ax[0].annotate("flat curves = no latitude trend\n(not strictly equal-area)", xy=(35, 5),
                   xytext=(18, 0.9), fontsize=7.5, color=NAVY,
                   arrowprops=dict(arrowstyle="->", color=NAVY, lw=0.8))

    ax[1].set_xlabel("Latitude band center (°N)")
    ax[1].set_ylabel("Area CV within band")
    ax[1].set_title("(b) Within-band dispersion shrinks toward mid-latitudes")
    for a in ax:
        despine(a)
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig1_area_vs_lat.png")
    plt.close(fig)
    print("fig1 done")


# ---------- 图 2：RSC 曲线 ----------

def fig2_rsc():
    mv = pd.read_csv(f"{RES}/e2_stability_moving.csv")
    al = pd.read_csv(f"{RES}/e2_stability_all.csv")

    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.2))
    ax[0].plot(mv["res"], mv["nested_hit_rate"], "o-", color=NAVY, lw=2,
               label="B: moving (SOG ≥ 3 kn)")
    ax[0].plot(al["res"], al["nested_hit_rate"], "s--", color=RED, lw=1.8,
               label="A: all records")
    ax[0].axvspan(8.6, 9.25, color=RED, alpha=0.06)
    ax[0].annotate("cliff at res 9", xy=(9, 0.747), xytext=(7.6, 0.70),
                   fontsize=9, color=RED,
                   arrowprops=dict(arrowstyle="->", color=RED, lw=1))
    ax[0].set_xlabel("H3 resolution")
    ax[0].set_ylabel("Nested hit rate")
    ax[0].set_title("(a) Slow decay, then a cliff")
    ax[0].set_ylim(0.65, 1.0)
    ax[0].legend(fontsize=8, loc="lower left")

    ax[1].plot(mv["res"], mv["iou50_prev"], "o-", color=NAVY, lw=2, label="B: moving")
    ax[1].plot(al["res"], al["iou50_prev"], "s--", color=RED, lw=1.8, label="A: all")
    ax[1].set_xlabel("H3 resolution")
    ax[1].set_ylabel("Equal-mass IoU vs previous level")
    ax[1].set_title("(b) No convergence to a plateau")
    ax[1].set_ylim(0.0, 0.5)
    ax[1].legend(fontsize=8, loc="upper right")
    for a in ax:
        despine(a)
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig2_rsc.png")
    plt.close(fig)
    print("fig2 done")


# ---------- 图 3：可靠性天花板与 SSI（原创点） ----------

def fig3_reliability():
    e6 = pd.read_csv(f"{RES}/e6_reliability.csv")
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2),
                           gridspec_kw={"width_ratios": [1.65, 1]})

    ax[0].plot(e6["res"], e6["overlap_mean"], "o-", color=TEAL, lw=2.4,
               label="O$_r$: split-half reproducibility (ceiling)")
    ax[0].fill_between(e6["res"], e6["overlap_mean"] - e6["overlap_std"],
                       e6["overlap_mean"] + e6["overlap_std"], color=TEAL, alpha=0.15)
    sub = e6.dropna(subset=["cross_mean"])
    ax[0].plot(sub["res"], sub["cross_mean"], "s--", color=ORANGE, lw=2.2,
               label="C$_r$: cross-scale agreement")
    ax[0].fill_between(sub["res"], sub["cross_mean"] - sub["cross_std"],
                       sub["cross_mean"] + sub["cross_std"], color=ORANGE, alpha=0.15)
    for _, r in e6.iterrows():
        ax[0].annotate(f"{r['overlap_mean']:.2f}", (r["res"], r["overlap_mean"]),
                       textcoords="offset points", xytext=(0, 8), ha="center",
                       fontsize=7.5, color=TEAL)
    ax[0].set_xlabel("H3 resolution")
    ax[0].set_ylabel("Top-100 agreement")
    ax[0].set_title("(a) Cross-scale agreement tracks its own reliability ceiling")
    ax[0].set_ylim(0.7, 1.02)
    ax[0].legend(fontsize=8, loc="lower left")
    ax[0].annotate("ceiling itself collapses\n(≈1 point per cell)",
                   xy=(9, 0.813), xytext=(7.2, 0.74), fontsize=8, color=TEAL,
                   arrowprops=dict(arrowstyle="->", color=TEAL, lw=0.9))

    ax[1].plot(e6["res"], e6["ssi"], "D-", color=NAVY, lw=2, ms=6)
    ax[1].axhline(1.0, color=GRAY, ls=":", lw=1.2)
    ax[1].axhspan(0.9, 1.0, color=NAVY, alpha=0.05)
    for _, r in e6.dropna(subset=["ssi"]).iterrows():
        ax[1].annotate(f"{r['ssi']:.2f}", (r["res"], r["ssi"]),
                       textcoords="offset points", xytext=(0, -14), ha="center",
                       fontsize=8, color=NAVY)
    ax[1].set_xlabel("H3 resolution")
    ax[1].set_ylabel("SSI = C$_r$ / O$_r$")
    ax[1].set_title("(b) Scale penalty is constant")
    ax[1].set_ylim(0.85, 1.03)
    ax[1].annotate("≈ 6% fixed scale penalty", xy=(5.15, 0.905), fontsize=8.5,
                   color=NAVY)
    for a in ax:
        despine(a)
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig7_reliability.png")
    plt.close(fig)
    print("fig3 done")


# ---------- 图 4：热点地图（真实六边形 + 海岸线） ----------

def _cells_with_density(res):
    df = pd.read_parquet("d:/trae/data/ais_moving.parquet",
                         columns=[f"h3_{res}", "lat", "lon"])
    col = f"h3_{res}"
    g = df.groupby(col, observed=True).agg(
        n=("lat", "size"), lat=("lat", "mean"), lon=("lon", "mean")).reset_index()
    g["area"] = [h3.cell_area(c, unit="km^2") for c in g[col]]
    g["density"] = g["n"] / g["area"]
    return g


def fig4_hotspots():
    """同一港口范围（Houston/Galveston）在四个分辨率下的热点结构。"""
    from matplotlib.patches import Rectangle

    PORT = (-95.45, -94.55, 29.15, 30.05)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    sc = None
    for ax, res in zip(axes.ravel(), [6, 7, 8, 9]):
        g = _cells_with_density(res).rename(columns={f"h3_{res}": "h3_cell"})
        sub = g[(g["lon"].between(PORT[0], PORT[1]))
                & (g["lat"].between(PORT[2], PORT[3]))]
        sub = sub.nlargest(30000, "density")
        vals = sub["density"].rank(pct=True)
        sc = ax.scatter(sub["lon"], sub["lat"], s=12, c=vals, cmap="YlOrRd",
                        vmin=0, vmax=1, linewidths=0, alpha=0.95)
        add_coast(ax, lw=0.5)
        ax.set_xlim(PORT[0], PORT[1])
        ax.set_ylim(PORT[2], PORT[3])
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(f"res {res} — {len(sub):,} occupied cells")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        despine(ax)

    # 全国定位小图
    axin = axes[0, 0].inset_axes([0.02, 0.60, 0.36, 0.36])
    add_coast(axin, lw=0.4)
    axin.add_patch(Rectangle((PORT[0], PORT[2]), PORT[1] - PORT[0],
                             PORT[3] - PORT[2], fill=False, ec=RED, lw=1.2))
    axin.set_xlim(-128, -62)
    axin.set_ylim(22, 51)
    axin.set_xticks([])
    axin.set_yticks([])
    axin.set_facecolor("#f7f9fb")
    axin.set_title("study area", fontsize=7)
    for s in axin.spines.values():
        s.set_visible(True)
        s.set_linewidth(0.6)

    fig.subplots_adjust(right=0.88, hspace=0.30, wspace=0.20, top=0.92)
    cax = fig.add_axes([0.905, 0.15, 0.018, 0.68])
    cb = fig.colorbar(sc, cax=cax)
    cb.set_label("Density percentile within panel")
    fig.suptitle("Same harbour, four resolutions: hotspots dissolve into AIS tracks",
                 fontsize=12, fontweight="bold", y=0.975)
    fig.savefig(f"{FIG}/fig3_hotspots.png")
    plt.close(fig)
    print("fig4 done")


# ---------- 图 5：样本充分性 ----------

def fig5_sufficiency():
    e3 = pd.read_csv(f"{RES}/e3_sample.csv")
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.plot(e3["res"], e3["mean_n"], "o-", color=NAVY, lw=2, label="Mean points per cell")
    ax.plot(e3["res"], e3["median_n"], "s--", color=ORANGE, lw=1.8,
            label="Median points per cell")
    ax.axhline(30, color=RED, ls=":", lw=1.2)
    ax.text(4.05, 33, "n_min = 30", color=RED, fontsize=8)
    ax.set_yscale("log")
    ax.set_xlabel("H3 resolution")
    ax.set_ylabel("Points per occupied cell (log)")
    ax2 = ax.twinx()
    ax2.bar(e3["res"], e3["share_ge_nmin"], width=0.45, alpha=0.22,
            color=GREEN, label="Share of cells with n ≥ 30")
    ax2.set_ylabel("Share of cells with n ≥ 30", color=GREEN)
    ax2.set_ylim(0, 1)
    ax2.grid(False)
    despine(ax)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("Sample dilution: median drops to 1 point at res 9")
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig4_sufficiency.png")
    plt.close(fig)
    print("fig5 done")


# ---------- 图 6：时段稳健性 ----------

def fig6_temporal():
    e4 = pd.read_csv(f"{RES}/e4_temporal.csv")
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    colors = ["#12355B", "#0FA3B1", "#F28C28", "#C1272D"]
    for (b, sub), c in zip(e4.groupby("block"), colors):
        sub = sub.sort_values("res")
        ax.plot(sub["res"], sub["nested_hit_rate"], "o-", color=c, lw=1.6,
                label=f"block {b} ({b*6:02d}:00–{b*6+6:02d}:00)")
    ax.set_xlabel("H3 resolution")
    ax.set_ylabel("Nested hit rate")
    ax.set_ylim(0.7, 1.0)
    ax.set_title("Cliff position moves with the time window")
    ax.legend(fontsize=8, loc="lower left")
    ax.annotate("res 9: 0.867 → 0.747", xy=(9, 0.747), xytext=(6.6, 0.73),
                fontsize=8, color=RED,
                arrowprops=dict(arrowstyle="->", color=RED, lw=0.9))
    despine(ax)
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig5_temporal.png")
    plt.close(fig)
    print("fig6 done")


# ---------- 图 7：三系统对照 ----------

def fig7_grids():
    loc = pd.read_csv(f"{RES}/e5_grids.csv")
    glo = pd.read_csv(f"{RES}/e5_area_global.csv")
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.2))

    for sysname, color, mk in [("h3", NAVY, "o"), ("geohash", ORANGE, "s"),
                               ("latlon", GREEN, "^")]:
        s = loc[loc["system"] == sysname]
        ax[0].plot(s["median_area_km2"], s["area_cv"], marker=mk, color=color,
                   lw=1.6, label=sysname)
    ax[0].set_xscale("log")
    ax[0].set_xlabel("Median cell area (km², log)")
    ax[0].set_ylabel("Area CV (occupied cells)")
    ax[0].set_title("(a) Local footprint (25–49°N): H3 is not the most uniform")
    ax[0].legend(fontsize=8)

    systems = ["h3", "geohash", "latlon"]
    cols = [NAVY, ORANGE, GREEN]
    vals = [glo[glo["system"] == s]["area_max_min_ratio"].mean() for s in systems]
    bars = ax[1].bar(systems, vals, color=cols, width=0.55, alpha=0.9)
    for b, v in zip(bars, vals):
        ax[1].text(b.get_x() + b.get_width() / 2, v + 0.08, f"{v:.2f}×",
                   ha="center", fontsize=9)
    ax[1].set_ylabel("Max / min cell area (global)")
    ax[1].set_title("(b) Global sweep: H3 is ~3× more uniform")
    ax[1].set_ylim(0, max(vals) * 1.18)
    for a in ax:
        despine(a)
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig6_grids.png")
    plt.close(fig)
    print("fig7 done")


# ---------- 图 8：层级持久热点（原创点 B） ----------

def fig8_persistence():
    cells = pd.read_parquet(f"{RES}/e7_persistence_cells.parquet")
    prof = pd.read_csv(f"{RES}/e7_birth_profile.csv")
    agg = pd.read_csv(f"{RES}/e7_persistent_res7.csv")
    with open(f"{RES}/e7_summary.json", encoding="utf-8") as f:
        s7 = json.load(f)

    fig = plt.figure(figsize=(11, 8.8))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.12], hspace=0.30, wspace=0.42,
                          left=0.07, right=0.965, top=0.93, bottom=0.06)

    # (a) 寿命分布
    ax = fig.add_subplot(gs[0, 0])
    ks = sorted(int(k) for k in s7["cells_by_longest_run"])
    cnt = [s7["cells_by_longest_run"][str(k)] for k in ks]
    pct = [s7["points_by_longest_run_pct"][str(k)] for k in ks]
    ax.bar(ks, cnt, color=GRAY, alpha=0.55, width=0.62, label="res-9 cells")
    ax.set_yscale("log")
    ax.set_xlabel("Longest consecutive run as hotspot (levels)")
    ax.set_ylabel("Number of res-9 cells (log)")
    ax2 = ax.twinx()
    ax2.plot(ks, pct, "o-", color=RED, lw=1.8, ms=5, label="share of points")
    ax2.set_ylabel("Share of points (%)", color=RED)
    ax2.set_ylim(0, 62)
    ax2.grid(False)
    ax.axvline(3.5, color=NAVY, ls="--", lw=1.1)
    ax.text(3.62, 2.0e4, "core\n(run ≥ 4)", fontsize=8, color=NAVY)
    ax.set_title("(a) Only 0.3% of cells are persistent")
    ax.set_xticks(ks)
    despine(ax)

    # (b) 持久核心地图
    ax = fig.add_subplot(gs[1, :])
    bg = agg[agg["max_run"] == 0]
    fg = agg[agg["max_run"] > 0]
    ax.scatter(bg["lon"], bg["lat"], s=1.4, c="#e3e7ec", linewidths=0,
               label="never persistent")
    sc = ax.scatter(fg["lon"], fg["lat"], s=np.clip(fg["n"] / 350, 4, 70),
                    c=fg["max_run"], cmap="YlOrRd", vmin=0, vmax=6,
                    linewidths=0.25, edgecolors="#7a4a10", alpha=0.9)
    add_coast(ax, lw=0.55)
    ax.set_xlim(-128, -72)
    ax.set_ylim(23, 50)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("(b) The persistent core (aggregated to res 7); marker area ∝ points")
    cb = fig.colorbar(sc, ax=ax, fraction=0.022, pad=0.012, aspect=28)
    cb.set_label("max run (levels)", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    ax.legend(fontsize=7.5, loc="lower left", markerscale=3)
    despine(ax)

    # (c) 出生剖面：粗档 Top-100 几乎囊括一切
    ax = fig.add_subplot(gs[0, 1])
    b = prof["birth"].to_numpy()
    ax.bar(b, prof["points_pct"], color=TEAL, alpha=0.75, width=0.6)
    ax.set_xlabel("Birth level (first entering Top-100)")
    ax.set_ylabel("Share of AIS points (%)", color=TEAL)
    ax.set_ylim(0, 56)
    ax.set_xticks(range(4, 10))
    ax2 = ax.twinx()
    ax2.plot(b, prof["median_n"], "D--", color=NAVY, lw=1.4, ms=5)
    ax2.set_ylabel("Median points per cell", color=NAVY)
    ax2.grid(False)
    ax.set_title("(c) Coarse 'hotspots' swallow 44% of points")
    ax.annotate("res 4 Top-100:\n44% of points,\nmedian n = 1",
                xy=(4.05, 40), xytext=(5.05, 30), fontsize=7.8, color=NAVY,
                arrowprops=dict(arrowstyle="->", color=NAVY, lw=0.8))
    despine(ax)

    fig.suptitle("Persistence of hotspots across the H3 hierarchy", fontsize=12,
                 fontweight="bold", y=0.985)
    fig.savefig(f"{FIG}/fig8_persistence.png")
    plt.close(fig)
    print("fig8 done")


# ---------- 图 9：三判据交叉验证（原创点 C） ----------

def fig9_crosscheck():
    e8 = pd.read_csv(f"{RES}/e8_crosscheck.csv")
    with open(f"{RES}/e8_summary.json", encoding="utf-8") as f:
        s8 = json.load(f)

    fig, ax = plt.subplots(1, 3, figsize=(13.4, 4.9),
                           gridspec_kw={"width_ratios": [1.1, 1.1, 1.15]})
    fig.subplots_adjust(left=0.055, right=0.955, top=0.90, bottom=0.14, wspace=0.42)

    # (a) 局部方差比
    ax[0].plot(e8["res"], e8["lv"], "o-", color=NAVY, lw=2.2, ms=6)
    j_lv = s8["criteria"]["J3_local_variance"]["recommend"]
    ax[0].scatter([j_lv], [e8.loc[e8["res"] == j_lv, "lv"].iat[0]], s=150,
                  facecolors="none", edgecolors=RED, lw=2, zorder=5)
    ax[0].axvspan(j_lv - 0.18, j_lv + 0.18, color=RED, alpha=0.07)
    ax[0].annotate(f"trough at res {j_lv}", xy=(j_lv, 0.44), xytext=(4.3, 0.47),
                   fontsize=8.5, color=RED,
                   arrowprops=dict(arrowstyle="->", color=RED, lw=0.9))
    ax[0].set_xlabel("H3 resolution")
    ax[0].set_ylabel("Local variance ratio LV")
    ax[0].set_title("(a) Feature scale: LV trough")
    ax[0].set_ylim(0.38, 1.0)
    ax[0].text(4.05, 0.96, "LV → 1: local ≈ global\n(noise dominates)",
               fontsize=7.5, color=GRAY)

    # (b) 支撑度与质量效率
    ax[1].bar(e8["res"], e8["support_pct"], color=GREEN, alpha=0.6, width=0.55,
              label="cells with n ≥ 30 (%)")
    ax[1].axhline(50, color=GREEN, ls=":", lw=1.1)
    ax[1].text(4.05, 52, "50%", fontsize=7.5, color=GREEN)
    ax[1].set_xlabel("H3 resolution")
    ax[1].set_ylabel("Share of cells with n ≥ 30 (%)", color=GREEN)
    ax[1].set_ylim(0, 85)
    ax2 = ax[1].twinx()
    ax2.plot(e8["res"], e8["cells_for_10pct"], "s--", color=ORANGE, lw=1.8, ms=5)
    ax2.set_yscale("log")
    ax2.set_ylabel("Cells needed for 10% of points (log)", color=ORANGE)
    ax2.grid(False)
    ax[1].set_title("(b) Support collapses, cost explodes")
    despine(ax[1])

    # (c) 三条判据的推荐档
    rows = [("J1 reliability\n(O$_r$ ≥ 0.90)", s8["criteria"]["J1_reliability"]["recommend"]),
            ("J2 support\n(n ≥ 30 in ≥ 50%)", s8["criteria"]["J2_support"]["recommend"]),
            ("J3 local variance\n(LV trough)", s8["criteria"]["J3_local_variance"]["recommend"])]
    ax[2].axvspan(4.6, 7.4, color=NAVY, alpha=0.07)
    for i, (name, rec) in enumerate(rows):
        y = len(rows) - 1 - i
        ax[2].hlines(y, 3.3, 9.5, color="#cfd6df", lw=1.2, zorder=0)
        ax[2].scatter([rec], [y], s=210, color=TEAL, zorder=3, edgecolors="white")
        ax[2].text(3.22, y + 0.18, name, fontsize=8, va="bottom", color="#2b3a4a")
        ax[2].text(rec, y - 0.32, f"res {rec}", fontsize=8.5, ha="center", color=TEAL)
    ax[2].set_xlim(3.15, 9.6)
    ax[2].set_ylim(-0.75, 2.95)
    ax[2].set_yticks([])
    ax[2].set_xticks(range(4, 10))
    ax[2].set_xlabel("H3 resolution")
    ax[2].set_title("(c) Three independent criteria agree on 5–7")
    ax[2].grid(False)
    despine(ax[2])
    ax[2].text(6.4, -0.62, "no criterion supports res 8 or 9", fontsize=8,
               ha="center", color=RED)

    fig.savefig(f"{FIG}/fig9_crosscheck.png")
    plt.close(fig)
    print("fig9 done")


if __name__ == "__main__":
    fig1_area_lat()
    fig2_rsc()
    fig3_reliability()
    fig4_hotspots()
    fig5_sufficiency()
    fig6_temporal()
    fig7_grids()
    fig8_persistence()
    fig9_crosscheck()
    print(f"\n全部图已写入 {FIG}")
