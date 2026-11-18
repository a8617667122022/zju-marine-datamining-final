"""生成报告用图（英文标注，避免缺字）。

输入：results/*.csv 与 data/ais_moving.parquet
输出：results/figures/*.png
"""
import os

import h3
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon

RES = "d:/trae/repo/results"
FIG = f"{RES}/figures"
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

MOVING = pd.read_parquet("d:/trae/data/ais_moving.parquet")


# ---------- 图 1：面积随纬度的畸变 ----------

def fig1_area_lat():
    e1 = pd.read_csv(f"{RES}/e1_area_by_lat.csv")
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))

    # 左：各分辨率在纬度带上的平均面积
    for res, sub in e1.groupby("res"):
        sub = sub.sort_values("lat_band")
        ax[0].plot(sub["lat_band"] + 5, sub["area_mean"], marker="o", label=f"res {res}")
    ax[0].set_yscale("log")
    ax[0].set_xlabel("Latitude band center (deg N)")
    ax[0].set_ylabel("Mean cell area (km$^2$, log)")
    ax[0].set_title("(a) H3 cell area vs latitude")
    ax[0].legend(fontsize=7, ncol=2)

    # 右：各分辨率在纬度带内的面积 CV
    for res, sub in e1.groupby("res"):
        sub = sub.sort_values("lat_band")
        ax[1].plot(sub["lat_band"] + 5, sub["area_cv"], marker="s", label=f"res {res}")
    ax[1].set_xlabel("Latitude band center (deg N)")
    ax[1].set_ylabel("Area CV within band")
    ax[1].set_title("(b) Within-band area dispersion")
    ax[1].legend(fontsize=7, ncol=2)

    fig.tight_layout()
    fig.savefig(f"{FIG}/fig1_area_vs_lat.png")
    plt.close(fig)
    print("fig1 done")


# ---------- 图 2：RSC 曲线（嵌套一致率 + 等质量 IoU） ----------

def fig2_rsc():
    mv = pd.read_csv(f"{RES}/e2_stability_moving.csv")
    al = pd.read_csv(f"{RES}/e2_stability_all.csv")

    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(mv["res"], mv["nested_hit_rate"], "o-", color="#1f77b4", label="B: moving (SOG>=3kn)")
    ax[0].plot(al["res"], al["nested_hit_rate"], "s--", color="#d62728", label="A: all records")
    ax[0].axhline(0.85, color="gray", ls=":", lw=1)
    ax[0].text(5.05, 0.855, "reference 0.85", color="gray", fontsize=8)
    ax[0].set_xlabel("H3 resolution")
    ax[0].set_ylabel("Nested hit rate")
    ax[0].set_title("(a) Hot-spot agreement with coarser level")
    ax[0].set_ylim(0.6, 1.0)
    ax[0].legend(fontsize=8)

    ax[1].plot(mv["res"], mv["iou50_prev"], "o-", color="#1f77b4", label="B: moving")
    ax[1].plot(al["res"], al["iou50_prev"], "s--", color="#d62728", label="A: all")
    ax[1].set_xlabel("H3 resolution")
    ax[1].set_ylabel("Equal-mass IoU vs previous level")
    ax[1].set_title("(b) No convergence to a plateau")
    ax[1].set_ylim(0.0, 0.6)
    ax[1].legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(f"{FIG}/fig2_rsc.png")
    plt.close(fig)
    print("fig2 done")


# ---------- 图 3：样本充分性 ----------

def fig3_sufficiency():
    e3 = pd.read_csv(f"{RES}/e3_sample.csv")
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(e3["res"], e3["mean_n"], "o-", label="Mean points per cell")
    ax.plot(e3["res"], e3["median_n"], "s--", label="Median points per cell")
    ax.axhline(30, color="#d62728", ls=":", lw=1)
    ax.text(4.05, 33, "n_min = 30", color="#d62728", fontsize=8)
    ax.set_yscale("log")
    ax.set_xlabel("H3 resolution")
    ax.set_ylabel("Points per occupied cell (log)")
    ax2 = ax.twinx()
    ax2.bar(e3["res"], e3["share_ge_nmin"], alpha=0.18, color="#2ca02c", label="Share >= 30")
    ax2.set_ylabel("Share of cells with n >= 30", color="#2ca02c")
    ax2.set_ylim(0, 1)
    ax2.grid(False)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("Sample dilution with finer resolution")
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig3_sufficiency.png")
    plt.close(fig)
    print("fig3 done")


# ---------- 图 4：热点地图（4 档） ----------

def fig4_hotspots():
    res_list = [6, 7, 8, 9]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, res in zip(axes.ravel(), res_list):
        sub = MOVING[["h3_%d" % res, "lat", "lon"]].copy()
        sub.columns = ["cell", "lat", "lon"]
        g = sub.groupby("cell", observed=True).agg(n=("lat", "size"),
                                                   lat=("lat", "mean"),
                                                   lon=("lon", "mean")).reset_index()
        g = g.sort_values("n", ascending=False)
        # 背景：全部被占格（抽样，避免过密）
        bg = g.sample(min(len(g), 40000), random_state=0)
        ax.scatter(bg["lon"], bg["lat"], s=0.6, c="#c7c7c7", linewidths=0, alpha=0.5)
        top = g.head(300)
        v = np.log10(top["n"].to_numpy())
        vmin, vmax = np.percentile(v, 5), np.percentile(v, 95)
        sc = ax.scatter(top["lon"], top["lat"], s=np.log1p(top["n"]) * 10,
                        c=v, cmap="inferno", vmin=vmin, vmax=vmax, alpha=0.9, linewidths=0)
        ax.set_title(f"res {res}: top 300 hot cells")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_xlim(-130, -60)
        ax.set_ylim(22, 52)
        fig.colorbar(sc, ax=ax, shrink=0.75, label="log10(n)")
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig4_hotspots.png")
    plt.close(fig)
    print("fig4 done")


# ---------- 图 5：三系统面积均匀性（局部 vs 全球） ----------

def fig5_grids():
    loc = pd.read_csv(f"{RES}/e5_grids.csv")
    glo = pd.read_csv(f"{RES}/e5_area_global.csv")

    fig, ax = plt.subplots(1, 2, figsize=(10, 4))

    for sysname, color, mk in [("h3", "#1f77b4", "o"),
                               ("geohash", "#ff7f0e", "s"),
                               ("latlon", "#2ca02c", "^")]:
        s = loc[loc["system"] == sysname]
        ax[0].plot(s["median_area_km2"], s["area_cv"], marker=mk, color=color, label=sysname)
    ax[0].set_xscale("log")
    ax[0].set_xlabel("Median cell area (km$^2$, log)")
    ax[0].set_ylabel("Area CV (occupied cells)")
    ax[0].set_title("(a) Local footprint (25-49 N)")
    ax[0].legend(fontsize=8)

    systems = ["h3", "geohash", "latlon"]
    cols = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    g_tmp = glo.copy()
    g_tmp["ratio"] = g_tmp["area_max_min_ratio"]
    vals = [g_tmp[g_tmp["system"] == s]["ratio"].mean() for s in systems]
    ax[1].bar(systems, vals, color=cols, alpha=0.85)
    for i, v in enumerate(vals):
        ax[1].text(i, v + 0.05, f"{v:.2f}x", ha="center", fontsize=9)
    ax[1].set_ylabel("Max / min cell area (global)")
    ax[1].set_title("(b) Global latitude sweep")
    ax[1].set_ylim(0, max(vals) * 1.2)

    fig.tight_layout()
    fig.savefig(f"{FIG}/fig5_grids.png")
    plt.close(fig)
    print("fig5 done")


# ---------- 图 6：时段稳健性 ----------

def fig6_temporal():
    e4 = pd.read_csv(f"{RES}/e4_temporal.csv")
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for b, sub in e4.groupby("block"):
        sub = sub.sort_values("res")
        ax.plot(sub["res"], sub["nested_hit_rate"], "o-", label=f"block {b} (6h)")
    ax.set_xlabel("H3 resolution")
    ax.set_ylabel("Nested hit rate")
    ax.set_ylim(0.6, 1.0)
    ax.set_title("Cliff position is stable across 6-hour blocks")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig6_temporal.png")
    plt.close(fig)
    print("fig6 done")


if __name__ == "__main__":
    fig1_area_lat()
    fig2_rsc()
    fig3_sufficiency()
    fig4_hotspots()
    fig5_grids()
    fig6_temporal()
    print(f"\n全部图已写入 {FIG}")
