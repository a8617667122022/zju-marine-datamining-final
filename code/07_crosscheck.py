"""E8：三条独立判据的交叉验证（原创点 C）。

不依赖 Top-K 口径的三个"尺度诊断量"：

1. 局部方差比 LV_r（Woodcock & Strahler 1987）
   LV = Σ w_i (x_i - m_i)^2 / Σ w_i (x_i - x̄)^2
   x_i 为格 i 的密度，m_i 为其 1 环邻域的面积加权密度。
   LV 峰值对应的档位即"数据自身的特征尺度"：比它更细，局部差异开始由噪声主导。

2. 支撑度 support_pct：占用单元中 n >= NMIN 的占比。

3. 质量效率 cells_for_10pct：覆盖 10% 点数所需的最少单元数。
   这个量直接回答"要看清 10% 的流量，得画多少个格子"。

三者与 E6 的可靠性天花板 O_r 并列，看它们是否指向同一个档位。

产物：
  results/e8_crosscheck.csv
  results/e8_summary.json
"""
import json
import os

import h3
import numpy as np
import pandas as pd

MOVING = "d:/trae/data/ais_moving.parquet"
CACHE = "d:/trae/repo/results/areas"
OUT = "d:/trae/repo/results"
RES_LIST = list(range(4, 10))
NMIN = 30
Q_COVER = 0.10
Q_LV = 0.50


def area_map(res: int) -> pd.Series:
    d = pd.read_parquet(f"{CACHE}/h3_{res}.parquet")
    return d.set_index("cell")["area"]


def local_variance(cells, n, area, k_half):
    """在覆盖 50% 点数的子集上计算局部方差比。"""
    nmap = dict(zip(cells, n))
    amap = dict(zip(cells, area))
    a_bar = float(np.mean(area))
    x = n / area
    x_bar = float((n * x).sum() / n.sum())
    num = den = 0.0
    for i in k_half:
        c = cells[i]
        s_n = s_a = 0.0
        for d in h3.grid_disk(c, 1):
            s_n += nmap.get(d, 0.0)
            s_a += amap.get(d, a_bar)
        m_i = s_n / s_a
        w = n[i]
        num += w * (x[i] - m_i) ** 2
        den += w * (x[i] - x_bar) ** 2
    return num / den


def main():
    df = pd.read_parquet(MOVING, columns=[f"h3_{r}" for r in RES_LIST])
    areas = {r: area_map(r) for r in RES_LIST}
    rows = []

    for r in RES_LIST:
        vc = df[f"h3_{r}"].value_counts()
        cells = vc.index.to_numpy()
        n = vc.to_numpy().astype(float)
        area = areas[r].reindex(cells).to_numpy()
        order = np.argsort(-n)
        cum = np.cumsum(n[order]) / n.sum()
        k10 = int(np.searchsorted(cum, Q_COVER)) + 1
        k50 = int(np.searchsorted(cum, Q_LV)) + 1
        lv = local_variance(cells, n, area, order[:k50])
        rows.append({
            "res": r,
            "n_occupied": int(len(cells)),
            "support_pct": round(float((n >= NMIN).mean() * 100), 2),
            "cells_for_10pct": k10,
            "cells_for_50pct": k50,
            "lv": round(float(lv), 4),
            "density_cv": round(float(np.std(area) / np.mean(area)), 4),
        })
        print(f"res {r}: occupied={len(cells):,} support={rows[-1]['support_pct']}% "
              f"k10={k10} k50={k50} LV={lv:.4f}")

    tab = pd.DataFrame(rows)
    tab.to_csv(f"{OUT}/e8_crosscheck.csv", index=False)

    # 三条判据各自推荐哪一档
    rel = pd.read_csv(f"{OUT}/e6_reliability.csv")
    j_rel = int(rel.loc[rel["overlap_mean"] >= 0.90, "res"].max())
    # 支撑度判据对阈值敏感，这里同时给出 10% / 25% / 50% 三种口径
    sensitivity = {
        f"{th}%": int(tab.loc[tab["support_pct"] >= th, "res"].max())
        for th in (10, 25, 50)
    }
    j_sup = sensitivity["50%"]
    # LV 的谷底（而非峰值）才是特征尺度：再细下去局部方差由噪声而非结构驱动
    j_lv = int(tab.loc[tab["lv"].idxmin(), "res"])
    summary = {
        "criteria": {
            "J1_reliability": {"rule": "最细 r 使 O_r >= 0.90", "recommend": j_rel},
            "J2_support": {"rule": f"最细 r 使 n>={NMIN} 的单元占比 >= 50%",
                           "recommend": j_sup, "threshold_sensitivity": sensitivity},
            "J3_local_variance": {"rule": "局部方差比 LV 的谷底档位", "recommend": j_lv},
        },
        "lv_curve": {int(r): float(v) for r, v in zip(tab["res"], tab["lv"])},
        "cells_for_10pct": {int(r): int(v) for r, v in zip(tab["res"], tab["cells_for_10pct"])},
        "agreement_span": [min(j_rel, j_sup, j_lv), max(j_rel, j_sup, j_lv)],
    }
    with open(f"{OUT}/e8_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    main()
