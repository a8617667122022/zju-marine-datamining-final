# -*- coding: utf-8 -*-
"""补充资产：4 张新图 + H3 参数表数据。

fig10_studyarea : 图1.1 研究区与数据覆盖（B 口径 hexbin）
fig11_halfcell  : 图4.7 半格平移扰动的重合率曲线（E9）
fig12_or_seeds  : 图4.9 各档 12 个种子的 O_r 分布箱线图
fig13_pareto    : 图4.11 Top-k 热点格覆盖点数占比曲线
另产出 results/e6_per_seed.csv、results/h3_params.csv、results/pareto.csv
"""
import json

import h3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

MOVING = "d:/trae/data/ais_moving.parquet"
FIGDIR = "d:/trae/repo/results/figures"
RES_LIST = list(range(4, 10))
SEEDS = 12
KM_PER_DEG_LAT = 111.32

plt.rcParams["font.family"] = ["Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

df = pd.read_parquet(MOVING, columns=["lat", "lon", "ts"] + [f"h3_{r}" for r in RES_LIST])
print(f"rows={len(df):,}")

# ---------- 图1.1 研究区 hexbin ----------
fig, ax = plt.subplots(figsize=(10.5, 5.2))
hb = ax.hexbin(df["lon"], df["lat"], gridsize=280, bins="log", cmap="viridis",
               mincnt=1, linewidths=0)
cb = fig.colorbar(hb, ax=ax, pad=0.01)
cb.set_label("每格报文数（对数）")
ports = {"西雅图": (-122.33, 47.60), "旧金山": (-122.42, 37.75),
         "洛杉矶/长滩": (-118.20, 33.72), "休斯敦": (-95.00, 29.30),
         "纽约/新泽西": (-74.05, 40.60)}
for name, (x, y) in ports.items():
    ax.scatter([x], [y], marker="*", s=120, c="crimson", zorder=5)
    ax.annotate(name, (x, y), textcoords="offset points", xytext=(6, 5),
                fontsize=10, color="crimson")
ax.set_xlim(-128, -66)
ax.set_ylim(24, 50)
ax.set_xlabel("经度（°E）")
ax.set_ylabel("纬度（°N）")
ax.set_title("NOAA AIS 2023-01-01，B 口径（SOG≥3 kn）1,415,790 条报文的空间覆盖")
ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(f"{FIGDIR}/fig10_studyarea.png", dpi=600)
plt.close(fig)
print("fig10 done")

# ---------- 图4.7 半格平移曲线 ----------
e9 = pd.read_csv("d:/trae/repo/results/e9_halfcell.csv")
fig, ax = plt.subplots(figsize=(7.6, 4.4))
ax.plot(e9["res"], e9["overlap100"], "o-", label="Top-100 交集比例", lw=2)
ax.plot(e9["res"], e9["jaccard100"], "s--", label="Top-100 Jaccard", lw=1.6, alpha=0.8)
ax.plot(e9["res"], e9["overlap10"], "^--", label="Top-10 交集比例", lw=1.6, alpha=0.8)
ax.axhspan(0.57, 0.64, color="tab:blue", alpha=0.10)
ax.annotate("Top-100 平移税恒定在 0.57–0.64", xy=(6.5, 0.605), fontsize=10,
            color="tab:blue", ha="center")
ax.annotate("res 9 的 Top-10 仅 0.30", xy=(9, 0.30), xytext=(7.6, 0.22),
            fontsize=10, arrowprops=dict(arrowstyle="->", lw=1))
ax.set_xticks(RES_LIST)
ax.set_ylim(0, 0.75)
ax.set_xlabel("H3 分辨率")
ax.set_ylabel("重合率")
ax.set_title("半格平移前后热点集合的重合率（E9）")
ax.legend()
ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(f"{FIGDIR}/fig11_halfcell.png", dpi=600)
plt.close(fig)
print("fig11 done")

# ---------- O_r 逐种子 + 图4.9 箱线图 ----------
ts = pd.to_datetime(df["ts"])
blocks = (ts.dt.hour // 6).to_numpy()
n = len(df)
rows = []
for res in RES_LIST:
    cells = df[f"h3_{res}"].to_numpy()
    uniq = pd.unique(cells)
    areas = {c: h3.cell_area(c, unit="km^2") for c in uniq}
    s_all = pd.Series(cells).value_counts()
    d_all = s_all / pd.Series(areas).reindex(s_all.index)
    for seed in range(SEEDS):
        rng = np.random.default_rng(seed)
        half = np.empty(n, dtype=bool)
        for b in np.unique(blocks):
            idx = np.where(blocks == b)[0]
            rng.shuffle(idx)
            half[idx[: len(idx) // 2]] = True
        for tag, msk in (("S1", half), ("S2", ~half)):
            sub = pd.Series(cells[msk]).value_counts()
            d = sub / pd.Series(areas).reindex(sub.index)
            top = set(d.nlargest(100).index)
            rows.append({"res": res, "seed": seed, "half": tag,
                         "overlap": len(top & set(d_all.nlargest(100).index)) / 100})
per_seed = pd.DataFrame(rows)
per_seed.to_csv("d:/trae/repo/results/e6_per_seed.csv", index=False)
print("per-seed O_r done")

data = [g["overlap"].to_numpy() for _, g in per_seed.groupby("res")]
fig, ax = plt.subplots(figsize=(7.6, 4.4))
bp = ax.boxplot(data, positions=RES_LIST, widths=0.55, patch_artist=True,
                medianprops=dict(color="crimson", lw=1.6),
                boxprops=dict(facecolor="#aec7e8", alpha=0.7),
                whiskerprops=dict(lw=1.2), capprops=dict(lw=1.2))
means = [np.mean(v) for v in data]
ax.plot(RES_LIST, means, "D-", color="tab:orange", lw=1.6, ms=5, label="均值")
for r, v in zip(RES_LIST, data):
    ax.annotate(f"{np.mean(v):.3f}", (r, np.mean(v)), textcoords="offset points",
                xytext=(10, -12), fontsize=9, color="tab:orange")
ax.axhline(0.90, color="gray", ls=":", lw=1.2)
ax.annotate("ρ = 0.90", xy=(4.15, 0.905), fontsize=10, color="gray")
ax.set_xticks(RES_LIST)
ax.set_ylim(0.70, 1.0)
ax.set_xlabel("H3 分辨率")
ax.set_ylabel("O_r（12 种子 × 2 半样本）")
ax.set_title("同尺度可靠性天花板 O_r 的种子间分布")
ax.legend(loc="lower left")
ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(f"{FIGDIR}/fig12_or_seeds.png", dpi=600)
plt.close(fig)
print("fig12 done")

# ---------- Pareto 覆盖曲线 + 图4.11 ----------
pareto_ks = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000]
prows = []
for res in RES_LIST:
    cells = df[f"h3_{res}"].to_numpy()
    uniq = pd.unique(cells)
    areas = {c: h3.cell_area(c, unit="km^2") for c in uniq}
    s = pd.Series(cells).value_counts()
    d = (s / pd.Series(areas).reindex(s.index)).sort_values(ascending=False)
    cum = d.cumsum() / d.sum()
    for k in pareto_ks:
        if k <= len(cum):
            share = float(cum.iloc[k - 1])
        else:
            share = float(cum.iloc[-1])
        prows.append({"res": res, "k": k, "point_share": round(share, 4),
                      "occupied": len(d)})
pareto = pd.DataFrame(prows)
pareto.to_csv("d:/trae/repo/results/pareto.csv", index=False)
print("pareto done")

fig, ax = plt.subplots(figsize=(7.8, 4.6))
colors = plt.cm.viridis(np.linspace(0.05, 0.9, len(RES_LIST)))
for c, (res, g) in zip(colors, pareto.groupby("res")):
    ax.plot(g["k"], g["point_share"], "o-", color=c, lw=1.8, ms=4,
            label=f"res {res}")
    g100 = g[g["k"] == 100]["point_share"]
    if len(g100):
        ax.scatter([100], g100, color=c, s=46, zorder=5,
                   edgecolors="white", linewidths=1.2)
ax.set_xscale("log")
ax.set_xlabel("Top-k 热点格数量（对数轴）")
ax.set_ylabel("覆盖点数占比")
ax.set_title("各分辨率下 Top-k 热点格的点数覆盖率")
ax.legend(ncol=3, fontsize=9)
ax.grid(alpha=0.25, which="both")
fig.tight_layout()
fig.savefig(f"{FIGDIR}/fig13_pareto.png", dpi=600)
plt.close(fig)
print("fig13 done")

# ---------- H3 参数表 ----------
hrows = []
for res in RES_LIST:
    hrows.append({
        "res": res,
        "area_km2": round(h3.average_hexagon_area(res, unit="km^2"), 3),
        "edge_km": round(h3.average_hexagon_edge_length(res, unit="km"), 3),
        "global_cells": h3.get_num_cells(res),
    })
hp = pd.DataFrame(hrows)
occ = {res: int(pd.Series(df[f"h3_{res}"]).nunique()) for res in RES_LIST}
hp["occupied_B"] = [occ[r] for r in hp["res"]]
hp.to_csv("d:/trae/repo/results/h3_params.csv", index=False)
print(hp)

# Top-100 覆盖率快照（供正文引用）
snap = pareto[pareto["k"] == 100][["res", "point_share"]]
print(snap.to_string(index=False))
