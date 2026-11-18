"""h3_advisor：给定一份点数据，推荐一个 H3 分辨率，并输出"口径合同"。

用法：
    python h3_advisor.py --input points.parquet --lat lat --lon lon
    python h3_advisor.py --input points.csv --lat LAT --lon LON --threshold 0.85

判据（与报告第三节一致）：
  1) 层次一致性：从 r-1 细化到 r 时，细档 Top100 热点格的父格仍落在
     粗档 Top100 的比例（nested_hit_rate）不低于 threshold；
  2) 样本充分性：在 r 档，点数 >= n_min 的单元占比不低于 min_share。
  推荐的 r 取"同时满足两条的最大档位"；并额外报告 r+1 是否跌破阈值，
  因为这正是"再细一格结论会不会变"的答案。

输出：JSON（同时打印到标准输出），可直接粘进分析文档当口径合同。
"""
import argparse
import json
import sys

import h3
import numpy as np
import pandas as pd

TOPK = 100


def load_points(path, lat_col, lon_col):
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    if lat_col not in df.columns or lon_col not in df.columns:
        raise SystemExit(f"找不到列 {lat_col}/{lon_col}，现有列：{list(df.columns)[:20]}")
    return df[lat_col].to_numpy(), df[lon_col].to_numpy(), len(df)


def cells_for(lat, lon, res, precomputed):
    col = f"h3_{res}"
    if precomputed is not None and col in precomputed.columns:
        return precomputed[col].to_numpy()
    return np.array([h3.latlng_to_cell(a, b, res) for a, b in zip(lat, lon)])


def level_curve(lat, lon, precomputed, res_min, res_max, n_min, topk=TOPK):
    curve = []
    prev_top = None
    for res in range(res_min, res_max + 1):
        cells = cells_for(lat, lon, res, precomputed)
        g = pd.DataFrame({"cell": cells}).groupby("cell", observed=True).size().rename("n").reset_index()
        total = int(g["n"].sum())
        g = g.sort_values("n", ascending=False).reset_index(drop=True)
        top = g.head(topk)
        rec = {
            "res": res,
            "n_occupied": int(len(g)),
            "median_n": float(g["n"].median()),
            "mean_n": round(float(g["n"].mean()), 2),
            "share_ge_nmin": round(float((g["n"] >= n_min).mean()), 4),
            "capture_top100_pct": round(float(top["n"].sum() / total * 100), 2),
        }
        if prev_top is not None:
            parents = {h3.cell_to_parent(c, res - 1) for c in top["cell"]}
            hit = sum(1 for p in parents if p in prev_top)
            rec["nested_hit_rate"] = round(hit / max(len(parents), 1), 4)
        else:
            rec["nested_hit_rate"] = None
        curve.append(rec)
        prev_top = set(top["cell"])
    return curve


def recommend(curve, threshold, min_share):
    """取同时满足一致性 + 样本充分性的最大档位。"""
    ok = [r for r in curve
          if r["nested_hit_rate"] is not None
          and r["nested_hit_rate"] >= threshold
          and r["share_ge_nmin"] >= min_share]
    if not ok:
        return None, None, False
    best = max(r["res"] for r in ok)
    nxt = next((r for r in curve if r["res"] == best + 1), None)
    breaks = bool(nxt and nxt["nested_hit_rate"] is not None
                  and nxt["nested_hit_rate"] < threshold)
    return best, nxt, breaks


def main():
    ap = argparse.ArgumentParser(description="H3 分辨率推荐与口径合同生成")
    ap.add_argument("--input", required=True, help="点数据路径（parquet/csv）")
    ap.add_argument("--lat", default="lat")
    ap.add_argument("--lon", default="lon")
    ap.add_argument("--res-min", type=int, default=4)
    ap.add_argument("--res-max", type=int, default=9)
    ap.add_argument("--n-min", type=int, default=30, help="每格最少样本数")
    ap.add_argument("--min-share", type=float, default=0.10,
                    help="样本充分单元的占比下限")
    ap.add_argument("--threshold", type=float, default=0.85,
                    help="层次一致性阈值")
    ap.add_argument("--out", default=None, help="可选：把 JSON 写到文件")
    args = ap.parse_args()

    precomputed = pd.read_parquet(args.input) if args.input.endswith(".parquet") else None
    lat, lon, n = load_points(args.input, args.lat, args.lon)

    curve = level_curve(lat, lon, precomputed, args.res_min, args.res_max,
                        args.n_min)
    best, nxt, breaks = recommend(curve, args.threshold, args.min_share)

    result = {
        "input": args.input,
        "n_points": n,
        "rule": {
            "nested_threshold": args.threshold,
            "min_share_ge_nmin": args.min_share,
            "n_min": args.n_min,
            "top_k": TOPK,
        },
        "curve": curve,
        "recommended_res": best,
        "next_res": nxt["res"] if nxt else None,
        "next_res_breaks_threshold": breaks,
        "contract": {
            "cell_unit": "H3",
            "resolution": best,
            "typical_area_km2": round(h3.average_hexagon_area(best, unit="km^2"), 4)
            if best is not None else None,
            "density_definition": "count / cell_area_km2",
            "hotspot_definition": f"top {TOPK} cells by density",
            "note": ("推荐档位为满足层次一致性与样本充分性的最细档；"
                     "再细一格若跌破阈值，说明结论已被采样噪声主导。"),
        },
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\n已写出 {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
