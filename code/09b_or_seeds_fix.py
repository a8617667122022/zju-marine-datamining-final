# -*- coding: utf-8 -*-
"""修正版逐种子 O_r：与正文同口径（同一半样本内部两半互相重合）。
只重跑 per-seed O_r 与 fig12，其余资产不动。
"""
import h3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

MOVING = "d:/trae/data/ais_moving.parquet"
RES_LIST = list(range(4, 10))
SEEDS = 12

plt.rcParams["font.family"] = ["Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

df = pd.read_parquet(MOVING, columns=["ts"] + [f"h3_{r}" for r in RES_LIST])
blocks = (pd.to_datetime(df["ts"]).dt.hour // 6).to_numpy()
n = len(df)
rows = []
for res in RES_LIST:
    cells = df[f"h3_{res}"].to_numpy()
    areas = {c: h3.cell_area(c, unit="km^2") for c in pd.unique(cells)}
    for seed in range(SEEDS):
        rng = np.random.default_rng(seed)
        half = np.empty(n, dtype=bool)
        for b in np.unique(blocks):
            idx = np.where(blocks == b)[0]
            rng.shuffle(idx)
            half[idx[: len(idx) // 2]] = True
        tops = {}
        for tag, msk in (("S1", half), ("S2", ~half)):
            sub = pd.Series(cells[msk]).value_counts()
            d = sub / pd.Series(areas).reindex(sub.index)
            tops[tag] = set(d.nlargest(100).index)
        rows.append({"res": res, "seed": seed,
                     "overlap": len(tops["S1"] & tops["S2"]) / 100})
    print(f"res {res} done")

per = pd.DataFrame(rows)
per.to_csv("d:/trae/repo/results/e6_per_seed.csv", index=False)
print(per.groupby("res")["overlap"].agg(["mean", "std"]).round(4).to_string())

data = [g["overlap"].to_numpy() for _, g in per.groupby("res")]
fig, ax = plt.subplots(figsize=(7.6, 4.4))
ax.boxplot(data, positions=RES_LIST, widths=0.55, patch_artist=True,
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
ax.set_ylim(0.75, 1.0)
ax.set_xlabel("H3 分辨率")
ax.set_ylabel("O_r（12 种子 × 两半重合）")
ax.set_title("同尺度可靠性天花板 O_r 的种子间分布")
ax.legend(loc="lower left")
ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig("d:/trae/repo/results/figures/fig12_or_seeds.png", dpi=200)
plt.close(fig)
print("fig12 regenerated")
