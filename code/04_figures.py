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
    "savefig.dpi": 600,
    "font.size": 10,
    "font.family": ["Microsoft YaHei", "DejaVu Sans"],
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
    ax[0].set_xlabel("纬度带中心（°N）")
    ax[0].set_ylabel("单元面积均值（km²，对数）")
    ax[0].set_title("（a）H3 面积几乎没有纬度趋势")
    ax[0].legend(fontsize=7, ncol=2, loc="lower right")
    ax[0].annotate("曲线平直 = 无纬度趋势\n（但不等于严格等积）", xy=(35, 5),
                   xytext=(18, 0.9), fontsize=7.5, color=NAVY,
                   arrowprops=dict(arrowstyle="->", color=NAVY, lw=0.8))

    ax[1].set_xlabel("纬度带中心（°N）")
    ax[1].set_ylabel("带内面积变异系数")
    ax[1].set_title("（b）中纬度带内离散度更小")
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
               label="B：航行船（SOG ≥ 3 kn）")
    ax[0].plot(al["res"], al["nested_hit_rate"], "s--", color=RED, lw=1.8,
               label="A：全量记录")
    ax[0].axvspan(8.6, 9.25, color=RED, alpha=0.06)
    ax[0].annotate("res 9 断崖", xy=(9, 0.747), xytext=(7.6, 0.70),
                   fontsize=9, color=RED,
                   arrowprops=dict(arrowstyle="->", color=RED, lw=1))
    ax[0].set_xlabel("H3 分辨率")
    ax[0].set_ylabel("嵌套一致率")
    ax[0].set_title("（a）缓慢衰减后突然崩塌")
    ax[0].set_ylim(0.65, 1.0)
    ax[0].legend(fontsize=8, loc="lower left")

    ax[1].plot(mv["res"], mv["iou50_prev"], "o-", color=NAVY, lw=2, label="B：航行船")
    ax[1].plot(al["res"], al["iou50_prev"], "s--", color=RED, lw=1.8, label="A：全量")
    ax[1].set_xlabel("H3 分辨率")
    ax[1].set_ylabel("等质量 IoU（对上一档）")
    ax[1].set_title("（b）不存在收敛平台")
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
               label="O$_r$：同尺度可靠性天花板")
    ax[0].fill_between(e6["res"], e6["overlap_mean"] - e6["overlap_std"],
                       e6["overlap_mean"] + e6["overlap_std"], color=TEAL, alpha=0.15)
    sub = e6.dropna(subset=["cross_mean"])
    ax[0].plot(sub["res"], sub["cross_mean"], "s--", color=ORANGE, lw=2.2,
               label="C$_r$：跨尺度一致率")
    ax[0].fill_between(sub["res"], sub["cross_mean"] - sub["cross_std"],
                       sub["cross_mean"] + sub["cross_std"], color=ORANGE, alpha=0.15)
    for _, r in e6.iterrows():
        ax[0].annotate(f"{r['overlap_mean']:.2f}", (r["res"], r["overlap_mean"]),
                       textcoords="offset points", xytext=(0, 8), ha="center",
                       fontsize=7.5, color=TEAL)
    ax[0].set_xlabel("H3 分辨率")
    ax[0].set_ylabel("Top-100 重合率")
    ax[0].set_title("（a）跨尺度一致率紧跟自身天花板")
    ax[0].set_ylim(0.7, 1.02)
    ax[0].legend(fontsize=8, loc="lower left")
    ax[0].annotate("天花板自身坍塌\n（每格约 1 点）",
                   xy=(9, 0.813), xytext=(7.2, 0.74), fontsize=8, color=TEAL,
                   arrowprops=dict(arrowstyle="->", color=TEAL, lw=0.9))

    ax[1].plot(e6["res"], e6["ssi"], "D-", color=NAVY, lw=2, ms=6)
    ax[1].axhline(1.0, color=GRAY, ls=":", lw=1.2)
    ax[1].axhspan(0.9, 1.0, color=NAVY, alpha=0.05)
    for _, r in e6.dropna(subset=["ssi"]).iterrows():
        ax[1].annotate(f"{r['ssi']:.2f}", (r["res"], r["ssi"]),
                       textcoords="offset points", xytext=(0, -14), ha="center",
                       fontsize=8, color=NAVY)
    ax[1].set_xlabel("H3 分辨率")
    ax[1].set_ylabel("SSI = C$_r$ / O$_r$")
    ax[1].set_title("（b）尺度惩罚基本恒定")
    ax[1].set_ylim(0.85, 1.03)
    ax[1].annotate("约 6% 的固定尺度惩罚", xy=(5.15, 0.905), fontsize=8.5,
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
        ax.set_title(f"res {res} —— {len(sub):,} 个占用单元")
        ax.set_xlabel("经度")
        ax.set_ylabel("纬度")
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
    axin.set_title("研究区", fontsize=7)
    for s in axin.spines.values():
        s.set_visible(True)
        s.set_linewidth(0.6)

    fig.subplots_adjust(right=0.88, hspace=0.30, wspace=0.20, top=0.92)
    cax = fig.add_axes([0.905, 0.15, 0.018, 0.68])
    cb = fig.colorbar(sc, cax=cax)
    cb.set_label("面板内密度分位")
    fig.suptitle("同一港口、四种分辨率：热点逐渐碎成 AIS 航迹",
                 fontsize=12, fontweight="bold", y=0.975)
    fig.savefig(f"{FIG}/fig3_hotspots.png")
    plt.close(fig)
    print("fig4 done")


# ---------- 图 5：样本充分性 ----------

def fig5_sufficiency():
    e3 = pd.read_csv(f"{RES}/e3_sample.csv")
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.plot(e3["res"], e3["mean_n"], "o-", color=NAVY, lw=2, label="每格点数均值")
    ax.plot(e3["res"], e3["median_n"], "s--", color=ORANGE, lw=1.8,
            label="每格点数中位数")
    ax.axhline(30, color=RED, ls=":", lw=1.2)
    ax.text(4.05, 33, "n_min = 30", color=RED, fontsize=8)
    ax.set_yscale("log")
    ax.set_xlabel("H3 分辨率")
    ax.set_ylabel("每格点数（对数）")
    ax2 = ax.twinx()
    ax2.bar(e3["res"], e3["share_ge_nmin"], width=0.45, alpha=0.22,
            color=GREEN, label="样本充足（n ≥ 30）单元占比")
    ax2.set_ylabel("样本充足（n ≥ 30）单元占比", color=GREEN)
    ax2.set_ylim(0, 1)
    ax2.grid(False)
    despine(ax)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("样本稀释：res 9 每格中位数降至 1 点")
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
                label=f"时段 {b}（{b*6:02d}:00–{b*6+6:02d}:00）")
    ax.set_xlabel("H3 分辨率")
    ax.set_ylabel("嵌套一致率")
    ax.set_ylim(0.7, 1.0)
    ax.set_title("断崖位置随时段移动")
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
    ax[0].set_xlabel("单元面积中位数（km²，对数）")
    ax[0].set_ylabel("面积变异系数（占用单元）")
    ax[0].set_title("（a）局部范围（25–49°N）：H3 并非最均匀")
    ax[0].legend(fontsize=8)

    systems = ["h3", "geohash", "latlon"]
    cols = [NAVY, ORANGE, GREEN]
    vals = [glo[glo["system"] == s]["area_max_min_ratio"].mean() for s in systems]
    bars = ax[1].bar(systems, vals, color=cols, width=0.55, alpha=0.9)
    for b, v in zip(bars, vals):
        ax[1].text(b.get_x() + b.get_width() / 2, v + 0.08, f"{v:.2f}×",
                   ha="center", fontsize=9)
    ax[1].set_ylabel("全球单元面积最大/最小比")
    ax[1].set_title("（b）全球扫描：H3 均匀性约为经纬网格的 3 倍")
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
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.12], hspace=0.32, wspace=0.62,
                          left=0.075, right=0.955, top=0.93, bottom=0.06)

    # (a) 寿命分布
    ax = fig.add_subplot(gs[0, 0])
    ks = sorted(int(k) for k in s7["cells_by_longest_run"])
    cnt = [s7["cells_by_longest_run"][str(k)] for k in ks]
    pct = [s7["points_by_longest_run_pct"][str(k)] for k in ks]
    ax.bar(ks, cnt, color=GRAY, alpha=0.55, width=0.62, label="res 9 单元")
    ax.set_yscale("log")
    ax.set_xlabel("连续成为热点的最长层数")
    ax.set_ylabel("res 9 单元数（对数）")
    ax2 = ax.twinx()
    ax2.plot(ks, pct, "o-", color=RED, lw=1.8, ms=5, label="点数占比")
    ax2.set_ylabel("点数占比（%）", color=RED)
    ax2.set_ylim(0, 62)
    ax2.grid(False)
    ax.axvline(3.5, color=NAVY, ls="--", lw=1.1)
    ax.text(3.62, 2.0e4, "持久核心\n（连续 ≥ 4 层）", fontsize=8, color=NAVY)
    ax.set_title("（a）仅 0.3% 的单元是持久的")
    ax.set_xticks(ks)
    despine(ax)

    # (b) 持久核心地图
    ax = fig.add_subplot(gs[1, :])
    bg = agg[agg["max_run"] == 0]
    fg = agg[agg["max_run"] > 0]
    ax.scatter(bg["lon"], bg["lat"], s=1.4, c="#e3e7ec", linewidths=0,
               label="从未持久")
    sc = ax.scatter(fg["lon"], fg["lat"], s=np.clip(fg["n"] / 350, 4, 70),
                    c=fg["max_run"], cmap="YlOrRd", vmin=0, vmax=6,
                    linewidths=0.25, edgecolors="#7a4a10", alpha=0.9)
    add_coast(ax, lw=0.55)
    ax.set_xlim(-128, -72)
    ax.set_ylim(23, 50)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    ax.set_title("（b）持久核心（聚合至 res 7），点面积与点数成正比")
    cb = fig.colorbar(sc, ax=ax, fraction=0.022, pad=0.012, aspect=28)
    cb.set_label("最长连续层数", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    ax.legend(fontsize=7.5, loc="lower left", markerscale=3)
    despine(ax)

    # (c) 出生剖面：粗档 Top-100 几乎囊括一切
    ax = fig.add_subplot(gs[0, 1])
    b = prof["birth"].to_numpy()
    ax.bar(b, prof["points_pct"], color=TEAL, alpha=0.75, width=0.6)
    ax.set_xlabel("出生档位（首次进入 Top-100）")
    ax.set_ylabel("AIS 点数占比（%）", color=TEAL)
    ax.set_ylim(0, 56)
    ax.set_xticks(range(4, 10))
    ax2 = ax.twinx()
    ax2.plot(b, prof["median_n"], "D--", color=NAVY, lw=1.4, ms=5)
    ax2.set_ylabel("每格点数中位数", color=NAVY)
    ax2.grid(False)
    ax.set_title("（c）粗档“热点”吞掉 44% 的点")
    ax.annotate("res 4 Top-100：\n44% 的点，\n每格中位数 1",
                xy=(4.05, 40), xytext=(5.05, 30), fontsize=7.8, color=NAVY,
                arrowprops=dict(arrowstyle="->", color=NAVY, lw=0.8))
    despine(ax)

    fig.suptitle("热点在 H3 层级中的持久性", fontsize=12,
                 fontweight="bold", y=0.985)
    fig.savefig(f"{FIG}/fig8_persistence.png")
    plt.close(fig)
    print("fig8 done")


# ---------- 图 9：三判据交叉验证（原创点 C） ----------

def fig9_crosscheck():
    e8 = pd.read_csv(f"{RES}/e8_crosscheck.csv")
    with open(f"{RES}/e8_summary.json", encoding="utf-8") as f:
        s8 = json.load(f)

    fig, ax = plt.subplots(1, 3, figsize=(14.2, 4.9),
                           gridspec_kw={"width_ratios": [1.05, 1.05, 1.2]})
    fig.subplots_adjust(left=0.062, right=0.94, top=0.90, bottom=0.14, wspace=0.55)

    # (a) 局部方差比
    ax[0].plot(e8["res"], e8["lv"], "o-", color=NAVY, lw=2.2, ms=6)
    j_lv = s8["criteria"]["J3_local_variance"]["recommend"]
    ax[0].scatter([j_lv], [e8.loc[e8["res"] == j_lv, "lv"].iat[0]], s=150,
                  facecolors="none", edgecolors=RED, lw=2, zorder=5)
    ax[0].axvspan(j_lv - 0.18, j_lv + 0.18, color=RED, alpha=0.07)
    ax[0].annotate(f"res {j_lv} 处触底", xy=(j_lv, 0.44), xytext=(4.3, 0.47),
                   fontsize=8.5, color=RED,
                   arrowprops=dict(arrowstyle="->", color=RED, lw=0.9))
    ax[0].set_xlabel("H3 分辨率")
    ax[0].set_ylabel("局部方差比 LV")
    ax[0].set_title("（a）特征尺度：LV 谷底")
    ax[0].set_ylim(0.38, 1.0)
    ax[0].text(4.05, 0.96, "LV → 1：局部≈全局\n（噪声主导）",
               fontsize=7.5, color=GRAY)

    # (b) 支撑度与质量效率
    ax[1].bar(e8["res"], e8["support_pct"], color=GREEN, alpha=0.6, width=0.55,
              label="n ≥ 30 的单元占比（%）")
    ax[1].axhline(50, color=GREEN, ls=":", lw=1.1)
    ax[1].text(4.05, 52, "50%", fontsize=7.5, color=GREEN)
    ax[1].set_xlabel("H3 分辨率")
    ax[1].set_ylabel("n ≥ 30 单元占比（%）", color=GREEN, fontsize=8.5)
    ax[1].set_ylim(0, 85)
    ax2 = ax[1].twinx()
    ax2.plot(e8["res"], e8["cells_for_10pct"], "s--", color=ORANGE, lw=1.8, ms=5)
    ax2.set_yscale("log")
    ax2.set_ylabel("覆盖 10% 点数所需格数（对数）", color=ORANGE, fontsize=8.5)
    ax2.grid(False)
    ax[1].set_title("（b）支撑度坍塌，代价飙升")
    despine(ax[1])

    # (c) 三条判据的推荐档
    rows = [("J1 可靠性\n（O$_r$ ≥ 0.90）", s8["criteria"]["J1_reliability"]["recommend"]),
            ("J2 支撑度\n（n ≥ 30 占比 ≥ 50%）", s8["criteria"]["J2_support"]["recommend"]),
            ("J3 局部方差\n（LV 谷底）", s8["criteria"]["J3_local_variance"]["recommend"])]
    ax[2].axvspan(4.6, 7.4, color=NAVY, alpha=0.07)
    for i, (name, rec) in enumerate(rows):
        y = len(rows) - 1 - i
        ax[2].hlines(y, 3.9, 9.4, color="#cfd6df", lw=1.2, zorder=0)
        ax[2].scatter([rec], [y], s=210, color=TEAL, zorder=3, edgecolors="white")
        ax[2].text(3.98, y + 0.12, name, fontsize=7.8, va="bottom", color="#2b3a4a")
        ax[2].text(rec, y - 0.30, f"res {rec}", fontsize=8.5, ha="center", color=TEAL)
    ax[2].set_xlim(3.8, 9.55)
    ax[2].set_ylim(-0.75, 2.95)
    ax[2].set_yticks([])
    ax[2].set_xticks(range(4, 10))
    ax[2].set_xlabel("H3 分辨率")
    ax[2].set_title("（c）三条独立判据都落在 5–7")
    ax[2].grid(False)
    despine(ax[2])
    ax[2].text(6.6, -0.60, "无判据支持 res 8 / 9", fontsize=7.8,
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
