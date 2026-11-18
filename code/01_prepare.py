"""把 AIS 原始 CSV 落成 H3 网格，输出 parquet 供后续实验复用。

产物：
  data/ais_moving.parquet  SOG >= 3 kn 的航行船（主实验口径 B）
  data/ais_all.parquet     全量记录（对照口径 A）
"""
import time

import duckdb
import h3
import pandas as pd

CSV = "d:/trae/data/ais/AIS_2023_01_01.csv"
RES_LIST = range(4, 10)  # res 4..9


def load(con, moving_only: bool) -> pd.DataFrame:
    cond = ["LAT BETWEEN -85 AND 85"]
    if moving_only:
        cond.append("SOG >= 3")
    where = " AND ".join(cond)
    return con.execute(
        f"""
        SELECT MMSI, BaseDateTime AS ts, LAT AS lat, LON AS lon,
               SOG AS sog, VesselType AS vtype
        FROM read_csv_auto('{CSV}')
        WHERE {where}
        """
    ).df()


def add_h3(df: pd.DataFrame) -> pd.DataFrame:
    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()
    for res in RES_LIST:
        t0 = time.time()
        df[f"h3_{res}"] = [h3.latlng_to_cell(a, b, res) for a, b in zip(lat, lon)]
        print(f"  res {res}: {time.time() - t0:.1f}s")
    return df


def main():
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")

    for moving_only, out in [(True, "ais_moving"), (False, "ais_all")]:
        print(f"=== {out} ===")
        df = load(con, moving_only)
        print(f"  行数: {len(df):,}")
        df = add_h3(df)
        path = f"d:/trae/data/{out}.parquet"
        df.to_parquet(path, index=False)
        print(f"  已写出 {path}")


if __name__ == "__main__":
    main()
