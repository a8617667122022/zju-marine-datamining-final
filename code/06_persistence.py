"""E7：层级持久热点（原创点 B 的验证）。

把 H3 的父子层级当成一棵树：对每个 res 9 叶子单元，检查它在 r=4..9 的祖先
是否落在该档的 Top-100 热点集合中。连续处于热点的层数即"寿命"。

定义：
  lifetime = r=4..9 中祖先为热点的层数；
  longest_run = 最长连续为热点的层数；
  birth/death = 首次/最后一次为热点的档位。
  持久热点：longest_run >= 4（共 6 档）。

产物：
  results/e7_persistence_cells.parquet   每个 res9 叶子的寿命
  results/e7_persistent_res7.csv         聚合到 res7 的持久热点（用于地图）
  results/e7_summary.json                寿命分布与点数占比
  results/e7_equal_mass_sets.csv         等质量口径的集合规模与覆盖率
  results/e7_equal_mass_nesting.csv      等质量口径的跨档嵌套率
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
TOPK = 100
PERSIST_L = 4
os.makedirs(CACHE, exist_ok=True)


def area_map(res: int) -> pd.Series:
    path = f"{CACHE}/h3_{res}.parquet"
    if os.path.exists(path):
        d = pd.read_parquet(path)
        return d.set_index("cell")["area"]
    df = pd.read_parquet(MOVING, columns=[f"h3_{res}"])
    cells = pd.unique(df[f"h3_{res}"].to_numpy())
    areas = [h3.cell_area(c, unit="km^2") for c in cells]
    s = pd.Series(areas, index=pd.Index(cells, name="cell"), name="area")
    s.reset_index().to_parquet(path, index=False)
    return s


def hot_set(cells: np.ndarray, area: pd.Series, k: int = TOPK) -> set:
    s = pd.Series(cells).value_counts()
    d = s / area.reindex(s.index)
    return set(d.nlargest(k).index)


def hot_set_mass(cells: np.ndarray, area: pd.Series, q: float) -> set:
    """等质量热点：取累计覆盖 q 比例点数的最少单元集合，消除 Top-K 面积不等。"""
    s = pd.Series(cells).value_counts()
    d = (s / area.reindex(s.index)).sort_values(ascending=False)
    cum = (s.reindex(d.index).cumsum() / s.sum()).to_numpy()
    k = int(np.searchsorted(cum, q)) + 1
    return set(d.index[:k])


def lifetime_table(anc: np.ndarray, hots: dict):
    """给定每档热点集合，返回 (flags, lifetime, longest_run, birth, death)。"""
    n, L = anc.shape
    flags = np.zeros((n, L), dtype=bool)
    for j, r in enumerate(RES_LIST):
        flags[:, j] = np.isin(anc[:, j], list(hots[r]))
    run = np.zeros(n, dtype=int)
    longest = np.zeros(n, dtype=int)
    for j in range(L):
        run = (run + 1) * flags[:, j]
        longest = np.maximum(longest, run)
    birth = np.where(flags.any(axis=1), RES_LIST[0] + np.argmax(flags, axis=1), -1)
    death = np.where(flags.any(axis=1),
                     RES_LIST[0] + (L - 1 - np.argmax(flags[:, ::-1], axis=1)), -1)
    return flags, flags.sum(axis=1), longest, birth, death


def main():
    df = pd.read_parquet(MOVING, columns=[f"h3_{r}" for r in RES_LIST])
    areas = {r: area_map(r) for r in RES_LIST}
    print("面积表就绪")

    hots = {r: hot_set(df[f"h3_{r}"].to_numpy(), areas[r]) for r in RES_LIST}
    for r in RES_LIST:
        print(f"  res {r}: 热点 {len(hots[r])} 个")

    leaves, counts = np.unique(df["h3_9"].to_numpy(), return_counts=True)
    n = len(leaves)
    print(f"res9 叶子 {n:,} 个")

    # 祖先矩阵只算一次，两种热点口径共用
    anc = np.empty((n, len(RES_LIST)), dtype=object)
    for j, r in enumerate(RES_LIST):
        anc[:, j] = leaves if r == 9 else np.array([h3.cell_to_parent(c, r) for c in leaves])

    flags, lifetime, longest, first, last = lifetime_table(anc, hots)
    for j, r in enumerate(RES_LIST):
        print(f"  res {r}: 命中叶子 {int(flags[:, j].sum()):,}")

    lat = np.empty(n)
    lon = np.empty(n)
    for i, c in enumerate(leaves):
        la, lo = h3.cell_to_latlng(c)
        lat[i], lon[i] = la, lo

    out = pd.DataFrame({
        "h3_9": leaves, "n": counts, "lat": lat, "lon": lon,
        "lifetime": lifetime, "longest_run": longest,
        "birth": first, "death": last,
        **{f"hot_{r}": flags[:, j] for j, r in enumerate(RES_LIST)},
    })
    out.to_parquet(f"{OUT}/e7_persistence_cells.parquet", index=False)

    # 聚合到 res7 画地图
    p7 = np.array([h3.cell_to_parent(c, 7) for c in leaves])
    agg = out.assign(h3_7=p7).groupby("h3_7", observed=True).agg(
        n=("n", "sum"), max_run=("longest_run", "max"),
        mean_lifetime=("lifetime", "mean")).reset_index()
    cent = [h3.cell_to_latlng(c) for c in agg["h3_7"]]
    agg["lat"] = [p[0] for p in cent]
    agg["lon"] = [p[1] for p in cent]
    agg.to_csv(f"{OUT}/e7_persistent_res7.csv", index=False)

    # 出生剖面：越晚出生的热点，样本是否越薄？
    # 这是对"固定 K 导致 Top-K 面积不等"这一偏置的自检：
    # 若迟出生的热点都是低计数格，则"细档新生儿"更可能是采样噪声而非新结构。
    born = out.loc[out["birth"] >= 0]
    prof = born.groupby("birth").agg(
        n_cells=("h3_9", "size"),
        n_points=("n", "sum"),
        median_n=("n", "median"),
        mean_n=("n", "mean"),
        p90_n=("n", lambda s: float(np.percentile(s, 90))),
    ).reset_index()
    prof["points_pct"] = prof["n_points"] / out["n"].sum() * 100
    prof.to_csv(f"{OUT}/e7_birth_profile.csv", index=False)

    core = out["longest_run"] >= PERSIST_L
    hot9 = out["hot_9"].to_numpy()
    hot7 = out["hot_7"].to_numpy()

    dist_cells = out["longest_run"].value_counts().sort_index()
    dist_points = out.groupby("longest_run")["n"].sum().sort_index()
    summary = {
        "top_k": TOPK,
        "levels": RES_LIST,
        "persist_threshold": PERSIST_L,
        "n_leaves": int(n),
        "cells_by_longest_run": {int(k): int(v) for k, v in dist_cells.items()},
        "points_by_longest_run_pct": {
            int(k): round(float(v / out["n"].sum() * 100), 2)
            for k, v in dist_points.items()},
        "persistent_cells": int((out["longest_run"] >= PERSIST_L).sum()),
        "persistent_points_pct": round(
            float(out.loc[out["longest_run"] >= PERSIST_L, "n"].sum()
                  / out["n"].sum() * 100), 2),
        "persistent_res7_cells": int((agg["max_run"] >= PERSIST_L).sum()),
        "share_leaves_never_hot_pct": round(
            float((out["longest_run"] == 0).mean() * 100), 2),
        "res9_top100_persistent_pct": round(float(core[hot9].mean() * 100), 2),
        "res7_top100_persistent_pct": round(float(core[hot7].mean() * 100), 2),
        "median_n_persistent": float(out.loc[core, "n"].median()),
        "median_n_transient": float(out.loc[(out["longest_run"] > 0) & ~core, "n"].median()),
        "median_n_never": float(out.loc[out["longest_run"] == 0, "n"].median()),
    }
    with open(f"{OUT}/e7_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # ---- 等质量对照：固定 K 会让粗档"以大欺小"，这里把各档热点质量对齐到 1% ----
    Q = 0.01
    hots_em = {r: hot_set_mass(df[f"h3_{r}"].to_numpy(), areas[r], Q) for r in RES_LIST}
    _, lt_em, lr_em, _, _ = lifetime_table(anc, hots_em)
    core_em = lr_em >= PERSIST_L
    set_rows = []
    for r in RES_LIST:
        s = df[f"h3_{r}"].value_counts()
        cov = float(s.reindex(list(hots_em[r])).sum() / s.sum() * 100)
        set_rows.append({"res": r, "k_cells": len(hots_em[r]),
                         "point_coverage_pct": round(cov, 3)})
    pd.DataFrame(set_rows).to_csv(f"{OUT}/e7_equal_mass_sets.csv", index=False)
    nest_rows = []
    for r in RES_LIST[1:]:
        hit = sum(1 for c in hots_em[r]
                  if h3.cell_to_parent(c, r - 1) in hots_em[r - 1])
        nest_rows.append({"res": r, "prev_res": r - 1,
                          "k_cells": len(hots_em[r]), "nested_cells": hit,
                          "nesting_rate": round(hit / len(hots_em[r]), 4)})
    pd.DataFrame(nest_rows).to_csv(f"{OUT}/e7_equal_mass_nesting.csv", index=False)
    em = {
        "rule": f"equal-mass: 累计覆盖 {Q:.0%} 点数的最少单元集合",
        "sets": set_rows,
        "nesting": nest_rows,
        "persistent_cells": int(core_em.sum()),
        "persistent_points_pct": round(
            float(out.loc[core_em, "n"].sum() / out["n"].sum() * 100), 2),
        "median_n_persistent": float(out.loc[core_em, "n"].median()),
        "share_leaves_never_hot_pct": round(float((lr_em == 0).mean() * 100), 2),
        "res9_set_persistent_pct": round(
            float(core_em[np.isin(anc[:, -1], list(hots_em[9]))].mean() * 100), 2),
    }
    with open(f"{OUT}/e7_summary_em.json", "w", encoding="utf-8") as f:
        json.dump(em, f, ensure_ascii=False, indent=2)
    print(json.dumps(em, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
