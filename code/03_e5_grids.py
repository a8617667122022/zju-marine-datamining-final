"""E5：不同空间网格方案对照（H3 / Geohash / 等经纬网格）。

三个系统各取若干档，尽量覆盖相近的单元面积范围，比较三件事：
  1) 面积均匀性：被占用单元的面积变异系数 CV（H3 是等积面，理论最稳）
  2) 嵌套一致率：细档 Top100 热点格的父格是否落进上一档 Top100
  3) 样本充分性：每格点数 >= n_min 的比例

产物：results/e5_grids.csv
"""
import math

import numpy as np
import pandas as pd
import pygeohash as pgh

MOVING = "d:/trae/data/ais_moving.parquet"
OUT = "d:/trae/repo/results/e5_grids.csv"
N_MIN = 30
TOPK = 100
R_EARTH = 6371.0088
BASE_STEP = 0.001953125  # 等经纬网格的最小档，其余档都是它的整数倍

# 等经纬网格的纬度步长（度），每档是上一档的 1/4，保证严格嵌套
LATLON_STEPS = [0.5, 0.125, 0.03125, 0.0078125, BASE_STEP]
# Geohash 精度（p3..p7）
GH_PRECISIONS = [3, 4, 5, 6, 7]


def rect_area(lat_min, lat_span, lon_span_deg):
    """经纬矩形面积（km²）。"""
    return (R_EARTH ** 2) * math.radians(lon_span_deg) * (
        math.sin(math.radians(lat_min + lat_span)) - math.sin(math.radians(lat_min))
    )


# ---------- 各系统：生成单元 id 与单元面积 ----------

def assign_h3(df):
    """H3 直接用 01_prepare 落好的列。"""
    out = {}
    for res in range(4, 10):
        col = f"h3_{res}"
        out[f"h3_r{res}"] = (df[col].to_numpy(), None, res)  # 面积单独算
    return out


def geohash_bits(precision):
    total = 5 * precision
    lon_bits = (total + 1) // 2
    lat_bits = total // 2
    return lat_bits, lon_bits


def assign_geohash(df):
    """先统一编码到最高精度，再按前缀截断——Geohash 天然前缀嵌套。"""
    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()
    maxp = max(GH_PRECISIONS)
    codes = np.array([pgh.encode(a, b, maxp) for a, b in zip(lat, lon)])
    res = {}
    for p in GH_PRECISIONS:
        cells = np.array([c[:p] for c in codes])
        # 单元面积：由该精度的经纬跨度 + 单元所在纬度决定
        lat_bits, lon_bits = geohash_bits(p)
        lat_span = 180.0 / (2 ** lat_bits)
        lon_span = 360.0 / (2 ** lon_bits)
        lat_min = np.floor((lat + 90.0) / lat_span) * lat_span - 90.0
        area = (R_EARTH ** 2) * np.radians(lon_span) * (
            np.sin(np.radians(lat_min + lat_span)) - np.sin(np.radians(lat_min))
        )
        res[f"gh_p{p}"] = (cells, area, p)
    return res


def assign_latlon(df):
    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()
    res = {}
    for step in LATLON_STEPS:
        ilat = np.floor((lat + 90.0) / step).astype(np.int64)
        ilon = np.floor((lon + 180.0) / step).astype(np.int64)
        cells = np.array([f"{a}_{b}" for a, b in zip(ilat, ilon)])
        lat_min = ilat * step - 90.0
        area = (R_EARTH ** 2) * np.radians(step) * (
            np.sin(np.radians(lat_min + step)) - np.sin(np.radians(lat_min))
        )
        ratio = int(round(step / BASE_STEP))  # 用于求父格
        res[f"ll_{step}"] = (cells, area, ratio)
    return res


# ---------- 通用：单档统计 ----------

def level_stats(cells, area_per_point, kind):
    """返回该档：按单元聚合后的 n / area / density / 中位面积 / CV 等。"""
    df = pd.DataFrame({"cell": cells, "area": area_per_point})
    g = df.groupby("cell", observed=True).agg(n=("area", "size"), area=("area", "first"))
    g = g.reset_index()
    g["density"] = g["n"] / g["area"]
    g = g.sort_values("density", ascending=False).reset_index(drop=True)
    top = g.head(TOPK)
    return {
        "n_occupied": int(len(g)),
        "median_area_km2": float(g["area"].median()),
        "mean_area_km2": float(g["area"].mean()),
        "area_cv": float(g["area"].std() / g["area"].mean()),
        "share_ge_nmin": float((g["n"] >= N_MIN).mean()),
        "capture_top100_pct": float(top["n"].sum() / g["n"].sum() * 100),
        "_g": g,
        "_top_cells": set(top["cell"]),
    }


def parent_ids(cells, kind, meta):
    """把一组单元映射到上一档的父单元 id（各系统各自定义）。"""
    if kind == "h3":
        import h3
        res = meta
        return [h3.cell_to_parent(c, res - 1) for c in cells]
    if kind == "geohash":
        p = meta
        return [c[: p - 1] for c in cells]
    if kind == "latlon":
        ratio = meta
        out = []
        for c in cells:
            a, b = c.split("_")
            out.append(f"{int(a) // 4}_{int(b) // 4}")
        return out
    raise ValueError(kind)


# ---------- 主流程 ----------

def run_system(name, levels, kind):
    """levels: [(label, cells, area_per_point, meta)]，由粗到细。"""
    rows = []
    prev_top = None
    for label, cells, area, meta in levels:
        s = level_stats(cells, area, kind)
        rec = {
            "system": name,
            "level": label,
            "n_occupied": s["n_occupied"],
            "median_area_km2": round(s["median_area_km2"], 4),
            "mean_area_km2": round(s["mean_area_km2"], 4),
            "area_cv": round(s["area_cv"], 4),
            "share_ge_nmin": round(s["share_ge_nmin"], 4),
            "capture_top100_pct": round(s["capture_top100_pct"], 2),
        }
        if prev_top is not None:
            parents = set(parent_ids(sorted(s["_top_cells"]), kind, meta))
            hit = sum(1 for c in parents if c in prev_top)
            rec["nested_hit_rate"] = round(hit / max(len(parents), 1), 4)
        else:
            rec["nested_hit_rate"] = np.nan
        rows.append(rec)
        prev_top = s["_top_cells"]
        print(f"  {name:8s} {label:10s} 单元={s['n_occupied']:>7d} "
              f"中位面积={s['median_area_km2']:9.4f}km² CV={s['area_cv']:.3f} "
              f"充分率={s['share_ge_nmin']:.3f} "
              f"嵌套={rec['nested_hit_rate']}")
    return rows


def global_area_cv():
    """全球尺度的面积均匀性：三种网格各自扫一遍全球纬度。

    本数据只覆盖 25–49°N 的窄带，局部 CV 说明不了问题；这一节回答
    "把同一套网格铺到全球，面积会差多少倍"。按 1° 纬度采样。
    """
    import h3 as h3lib

    rows = []
    lats = np.arange(-80.0, 80.0, 1.0)

    # H3：按 5° 经纬网格取代表性单元，去重后算面积
    for res in range(4, 10):
        seen = set()
        for la in np.arange(-80.0, 80.0, 5.0):
            for lo in np.arange(-180.0, 180.0, 5.0):
                seen.add(h3lib.latlng_to_cell(la, lo, res))
        areas = np.array([h3lib.cell_area(c, unit="km^2") for c in seen])
        rows.append({
            "system": "h3", "level": f"h3_r{res}",
            "n_sampled": len(areas),
            "area_cv": round(areas.std() / areas.mean(), 4),
            "area_max_min_ratio": round(areas.max() / areas.min(), 3),
        })

    for pr in GH_PRECISIONS:
        lat_bits, lon_bits = geohash_bits(pr)
        lat_span = 180.0 / (2 ** lat_bits)
        areas = []
        for la in lats:
            lat_min = np.floor((la + 90.0) / lat_span) * lat_span - 90.0
            areas.append(rect_area(lat_min, lat_span, 360.0 / (2 ** lon_bits)))
        areas = np.array(areas)
        rows.append({
            "system": "geohash", "level": f"gh_p{pr}",
            "n_sampled": len(areas),
            "area_cv": round(areas.std() / areas.mean(), 4),
            "area_max_min_ratio": round(areas.max() / areas.min(), 3),
        })

    for step in LATLON_STEPS:
        areas = []
        for la in lats:
            lat_min = np.floor((la + 90.0) / step) * step - 90.0
            areas.append(rect_area(lat_min, step, step))
        areas = np.array(areas)
        rows.append({
            "system": "latlon", "level": f"ll_{step}",
            "n_sampled": len(areas),
            "area_cv": round(areas.std() / areas.mean(), 4),
            "area_max_min_ratio": round(areas.max() / areas.min(), 3),
        })

    out = pd.DataFrame(rows)
    out.to_csv("d:/trae/repo/results/e5_area_global.csv", index=False)
    print("\n=== E5 全球面积均匀性 ===")
    print(out.to_string(index=False))
    return out


def main():
    df = pd.read_parquet(MOVING)
    print(f"moving = {len(df):,}")

    import h3 as h3lib

    print("\n=== E5 三系统对照 ===")

    # H3：面积按单元单价算
    h3_levels = []
    for res in range(4, 10):
        cells = df[f"h3_{res}"].to_numpy()
        area = np.array([h3lib.cell_area(c, unit="km^2") for c in cells])
        h3_levels.append((f"h3_r{res}", cells, area, res))

    gh = assign_geohash(df)
    gh_levels = [(k, v[0], v[1], v[2]) for k, v in sorted(gh.items())]

    ll = assign_latlon(df)
    ll_levels = [(k, v[0], v[1], v[2]) for k, v in ll.items()]

    rows = []
    rows += run_system("h3", h3_levels, "h3")
    rows += run_system("geohash", gh_levels, "geohash")
    rows += run_system("latlon", ll_levels, "latlon")

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(f"\n已写出 {OUT}")
    print(out.to_string(index=False))

    global_area_cv()


if __name__ == "__main__":
    main()
