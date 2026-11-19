"""E9：半格平移扰动（教材实验步骤 ⑦ 要求的「半格偏移/换系」之一）。

做法：
  把全部报文的经纬度整体平移半格边长（纬度方向固定，经度方向按 cos(lat)
  折算），等价于把网格相对船位挪了半格、格子结构本身不动；然后在各档
  重算密度 Top-K，量化平移前后热点集合的交集比例（|A∩B|/K，另记 Jaccard）。

产物：results/e9_halfcell.csv、results/e9_summary.json
"""
import json

import h3
import numpy as np
import pandas as pd

MOVING = "d:/trae/data/ais_moving.parquet"
OUT_CSV = "d:/trae/repo/results/e9_halfcell.csv"
OUT_JSON = "d:/trae/repo/results/e9_summary.json"
RES_LIST = list(range(4, 10))
TOPKS = (100, 10)
KM_PER_DEG_LAT = 111.32


def topk_density(cells: np.ndarray, areas: dict, k: int) -> set:
    s = pd.Series(cells).value_counts()
    d = s / pd.Series(areas).reindex(s.index)
    return set(d.nlargest(k).index)


def main():
    df = pd.read_parquet(MOVING, columns=["lat", "lon"] + [f"h3_{r}" for r in RES_LIST])
    n = len(df)
    print(f"moving = {n:,}")

    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()

    # 半格平移后的经纬度（经度按 cos(lat) 折算，并回卷到 [-180, 180]）
    rows = []
    for res in RES_LIST:
        edge = h3.average_hexagon_edge_length(res, unit="km")
        dlat = (edge / 2) / KM_PER_DEG_LAT
        dlon = (edge / 2) / (KM_PER_DEG_LAT * np.cos(np.radians(lat)))
        lon2 = ((lon + dlon + 180) % 360) - 180
        lat2 = lat + dlat

        # 平移后的落格（逐点标量调用，h3-py 无向量化接口）
        shifted = np.array(
            [h3.latlng_to_cell(a, b, res) for a, b in zip(lat2, lon2)],
            dtype=object,
        )
        orig = df[f"h3_{res}"].to_numpy()

        # 面积表：占用单元的并集（同一档内同面积，缓存一次）
        cells_all = pd.unique(np.concatenate([pd.unique(orig), pd.unique(shifted)]))
        areas = {c: h3.cell_area(c, unit="km^2") for c in cells_all}
        print(f"res {res}: edge={edge:.2f} km, 占用单元 {len(areas):,}")

        rec = {"res": res, "edge_km": round(edge, 2)}
        for k in TOPKS:
            t_o = topk_density(orig, areas, k)
            t_s = topk_density(shifted, areas, k)
            inter = len(t_o & t_s)
            rec[f"overlap{k}"] = round(inter / k, 4)
            rec[f"jaccard{k}"] = round(inter / len(t_o | t_s), 4)
        rows.append(rec)
        print(rec)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    summary = {
        "shift": "half cell edge; dlat fixed, dlon scaled by cos(lat)",
        "metric": "overlap = |A∩B|/K（交集比例，另记 Jaccard）",
        "rows": rows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n已写出 {OUT_CSV} / {OUT_JSON}")


if __name__ == "__main__":
    main()
