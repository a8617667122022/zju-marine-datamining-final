"""E6：可靠性天花板与归一化尺度稳定指数（SSI）。

核心问题：
  跨分辨率的一致率 C_r 下降，到底是因为"尺度效应"，还是因为"样本不够"？
  如果同一分辨率下、只换一半样本，热点集合也会同样程度地变化，
  那么跨尺度的变化就没有超出采样噪声。

做法：
  1) 把点按 6 小时时段分层，随机分成两半；
  2) 在每个 res 上，两半各自取密度 Top-100，计算重合率 O_r（同尺度噪声天花板）；
  3) 在同一半内，比较 res r 与 r-1 的 Top-100（父格命中率）C_r；
  4) 定义 SSI_r = C_r / O_r。
     SSI ≈ 1：细化带来的变化与"换个样本"相当，没有额外尺度效应；
     SSI < 1：细化额外损失了稳定性。

产物：results/e6_reliability.csv、results/e6_summary.json
"""
import json

import h3
import numpy as np
import pandas as pd

MOVING = "d:/trae/data/ais_moving.parquet"
OUT_CSV = "d:/trae/repo/results/e6_reliability.csv"
OUT_JSON = "d:/trae/repo/results/e6_summary.json"
RES_LIST = list(range(4, 10))
TOPK = 100
SEEDS = 12


def area_lookup(df: pd.DataFrame, res: int) -> pd.Series:
    """每个被占用单元的面积（km²），并对同一档做缓存。"""
    cells = pd.unique(df[f"h3_{res}"].to_numpy())
    areas = {c: h3.cell_area(c, unit="km^2") for c in cells}
    return pd.Series(areas)


def topk_density(cells: np.ndarray, area: pd.Series) -> set:
    s = pd.Series(cells).value_counts()
    d = s / area.reindex(s.index)
    return set(d.nlargest(TOPK).index)


def nested_hit(fine_cells: set, coarse_cells: set, res: int) -> float:
    parents = {h3.cell_to_parent(c, res - 1) for c in fine_cells}
    hit = sum(1 for p in parents if p in coarse_cells)
    return hit / max(len(parents), 1)


def main():
    df = pd.read_parquet(MOVING, columns=["ts"] + [f"h3_{r}" for r in RES_LIST])
    n = len(df)
    print(f"moving = {n:,}")

    areas = {r: area_lookup(df, r) for r in RES_LIST}
    print("面积表已就绪")

    ts = pd.to_datetime(df["ts"])
    blocks = (ts.dt.hour // 6).to_numpy()

    rows = []
    for res in RES_LIST:
        cells = df[f"h3_{res}"].to_numpy()
        ovs, jacs, cross = [], [], []
        for seed in range(SEEDS):
            rng = np.random.default_rng(seed)
            # 分时段随机对半
            half = np.empty(n, dtype=bool)
            for b in np.unique(blocks):
                idx = np.where(blocks == b)[0]
                rng.shuffle(idx)
                half[idx[: len(idx) // 2]] = True
                half[idx[len(idx) // 2:]] = False

            top1 = topk_density(cells[half], areas[res])
            top2 = topk_density(cells[~half], areas[res])
            ovs.append(len(top1 & top2) / TOPK)
            jacs.append(len(top1 & top2) / len(top1 | top2))

            if res > RES_LIST[0]:
                # 在同一半内做跨尺度比较，样本量与 split-half 对齐
                c1 = nested_hit(top1, topk_density(df[f"h3_{res-1}"].to_numpy()[half],
                                                  areas[res - 1]), res)
                c2 = nested_hit(top2, topk_density(df[f"h3_{res-1}"].to_numpy()[~half],
                                                  areas[res - 1]), res)
                cross.append((c1 + c2) / 2)

        rec = {
            "res": res,
            "overlap_mean": round(float(np.mean(ovs)), 4),
            "overlap_std": round(float(np.std(ovs)), 4),
            "jaccard_mean": round(float(np.mean(jacs)), 4),
            "cross_mean": round(float(np.mean(cross)), 4) if cross else None,
            "cross_std": round(float(np.std(cross)), 4) if cross else None,
        }
        if cross:
            rec["ssi"] = round(float(np.mean(cross) / np.mean(ovs)), 3)
        else:
            rec["ssi"] = None
        rows.append(rec)
        print(rec)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)

    summary = {
        "top_k": TOPK,
        "seeds": SEEDS,
        "split": "random within 6-hour blocks",
        "metric": "overlap = |A∩B|/K",
        "rows": rows,
        "reading": ("O_r 是同分辨率、换一半样本时的热点重合率，可视为该档的一致性上限；"
                    "SSI=C_r/O_r 接近 1 表示细化带来的变化没有超出采样噪声。"),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n已写出 {OUT_CSV} / {OUT_JSON}")


if __name__ == "__main__":
    main()
