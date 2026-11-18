"""E1–E4：H3 分辨率的定量实验。

产物写到 results/*.csv，控制台打印摘要。
"""
import json
import os

import h3
import numpy as np
import pandas as pd

MOVING = "d:/trae/data/ais_moving.parquet"
ALL = "d:/trae/data/ais_all.parquet"
OUT = "d:/trae/repo/results"
RES_LIST = list(range(4, 10))
os.makedirs(OUT, exist_ok=True)


# ---------- 工具函数 ----------

def cell_area_km2(cell: str) -> float:
    return h3.cell_area(cell, unit="km^2")


def load(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


RES9_AREA = float(np.mean([cell_area_km2(h3.latlng_to_cell(la, lo, 9))
                           for la in (-60, -30, 0, 30, 60)
                           for lo in (-120, 0, 120)]))


def cell_stats(df: pd.DataFrame, res: int) -> pd.DataFrame:
    """按 H3 单元聚合：点数、面积、密度、质心。"""
    col = f"h3_{res}"
    g = df.groupby(col, observed=True).size().rename("n").reset_index()
    cells = g[col].tolist()
    g["area_km2"] = [cell_area_km2(c) for c in cells]
    g["density"] = g["n"] / g["area_km2"]
    ll = [h3.cell_to_latlng(c) for c in cells]
    g["lat"] = [p[0] for p in ll]
    g["lon"] = [p[1] for p in ll]
    return g


def mask_at_res9(cells: list[str]) -> set[str]:
    """把一组不同层级的单元统一展开到 res 9，便于跨分辨率求交并。"""
    out = set()
    for c in cells:
        r = h3.get_resolution(c)
        if r == 9:
            out.add(c)
        else:
            out.update(h3.cell_to_children(c, 9))
    return out


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


# ---------- E1 面积畸变 ----------

def e1_area_distortion(df: pd.DataFrame) -> pd.DataFrame:
    print("\n=== E1 面积畸变 ===")
    rows = []
    for res in RES_LIST:
        st = cell_stats(df, res)
        # 纬度带内的面积变异系数
        st["lat_band"] = (np.floor(st["lat"] / 10) * 10).astype(int)
        for band, sub in st.groupby("lat_band"):
            if len(sub) < 20:
                continue
            rows.append({
                "res": res,
                "lat_band": band,
                "n_cells": len(sub),
                "area_mean": round(sub["area_km2"].mean(), 4),
                "area_cv": round(sub["area_km2"].std() / sub["area_km2"].mean(), 4),
                "area_min": round(sub["area_km2"].min(), 4),
                "area_max": round(sub["area_km2"].max(), 4),
            })
    out = pd.DataFrame(rows)
    out.to_csv(f"{OUT}/e1_area_by_lat.csv", index=False)

    # count 口径 vs 密度口径的热点排序差异（res 7）
    res = 7
    st = cell_stats(df, res).sort_values("n", ascending=False)
    k = 100
    top_count = set(st.head(k)[f"h3_{res}"])
    st2 = st.sort_values("density", ascending=False)
    top_density = set(st2.head(k)[f"h3_{res}"])
    iou = len(top_count & top_density) / len(top_count | top_density)
    print(f"  res7 Top100：count 口径 vs 密度口径 IoU = {iou:.3f}")
    print(f"  面积 CV（全局）：{st['area_km2'].std() / st['area_km2'].mean():.3f}")
    return out


# ---------- E2 分辨率稳定性 ----------

def e2_stability(df: pd.DataFrame, tag: str) -> pd.DataFrame:
    """分辨率稳定性。

    两个指标：
      1) 等质量 IoU：每档取"累计覆盖 50% 点数"的区域，质量对齐后比较面积重叠。
      2) 嵌套一致率：细档热点格里，有多大比例落进了粗档热点格。
    另附 Top-K 的点捕获率与质心漂移。
    """
    print(f"\n=== E2 分辨率稳定性（{tag}）===")
    total = len(df)
    rows = []
    prev_mask = None
    prev_top = None
    for res in RES_LIST:
        st = cell_stats(df, res).sort_values("density", ascending=False)
        cum = st["n"].cumsum() / total
        # 等质量区域：累计到 50% 点数
        n50 = int((cum < 0.5).sum()) + 1
        mask50 = mask_at_res9(st.head(n50)[f"h3_{res}"].tolist())

        top100 = st.head(100)
        rec = {
            "res": res,
            "n_occupied": len(st),
            "cells_for_50pct": n50,
            "area_for_50pct_km2": round(len(mask50) * RES9_AREA, 1),
            "capture_top100_pct": round(top100["n"].sum() / total * 100, 2),
        }
        if prev_mask is not None:
            inter = len(mask50 & prev_mask)
            union = len(mask50 | prev_mask)
            rec["iou50_prev"] = round(inter / union, 4)
            # 嵌套：细档热点格的父格是否在上一档的热点集合中
            parents = {h3.cell_to_parent(c, res - 1) for c in top100[f"h3_{res}"]}
            hit = sum(1 for p in parents if p in prev_top)
            rec["nested_hit_rate"] = round(hit / max(len(parents), 1), 4)
            d = [haversine_km(la, lo, prev_top_df["lat"].to_numpy(),
                              prev_top_df["lon"].to_numpy()).min()
                 for la, lo in zip(top100["lat"], top100["lon"])]
            rec["drift_km_median"] = round(float(np.median(d)), 2)
        rows.append(rec)
        prev_mask, prev_top, prev_top_df = mask50, set(st.head(100)[f"h3_{res}"]), top100
    out = pd.DataFrame(rows)
    out.to_csv(f"{OUT}/e2_stability_{tag}.csv", index=False)
    print(out.to_string(index=False))
    return out


# ---------- E3 样本充分性 ----------

def e3_sample_sufficiency(df: pd.DataFrame) -> pd.DataFrame:
    print("\n=== E3 样本充分性 ===")
    rows = []
    for res in RES_LIST:
        st = cell_stats(df, res)
        n_min = 30
        rows.append({
            "res": res,
            "n_occupied": len(st),
            "mean_n": round(st["n"].mean(), 2),
            "median_n": float(st["n"].median()),
            "share_ge_nmin": round((st["n"] >= n_min).mean(), 4),
            "mean_cell_area_km2": round(st["area_km2"].mean(), 4),
        })
    out = pd.DataFrame(rows)
    out.to_csv(f"{OUT}/e3_sample.csv", index=False)
    print(out.to_string(index=False))
    return out


# ---------- E4 时段稳健性 ----------

def e4_temporal(df: pd.DataFrame) -> pd.DataFrame:
    print("\n=== E4 时段稳健性（4 个 6 小时切片）===")
    ts = pd.to_datetime(df["ts"])
    df = df.assign(block=(ts.dt.hour // 6).astype(int))
    all_rows = []
    for b in sorted(df["block"].unique()):
        sub = df[df["block"] == b]
        print(f"  -- block {b}: {len(sub):,} 点")
        r = e2_stability(sub, f"block{b}")
        r["block"] = b
        all_rows.append(r)
    out = pd.concat(all_rows, ignore_index=True)
    out.to_csv(f"{OUT}/e4_temporal.csv", index=False)
    return out


if __name__ == "__main__":
    moving = load(MOVING)
    allrec = load(ALL)
    print(f"moving={len(moving):,}  all={len(allrec):,}")

    e1_area_distortion(moving)
    e2_stability(moving, "moving")
    e2_stability(allrec, "all")
    e3_sample_sufficiency(moving)
    e4_temporal(moving)
    print("\n全部实验完成。")
