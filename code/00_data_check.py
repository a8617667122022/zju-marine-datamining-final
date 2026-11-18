"""数据体检：确认 AIS 单日数据的字段、规模、空间与时间覆盖是否满足实验需要。

用法：python 00_data_check.py
"""
import duckdb

CSV = "d:/trae/data/ais/AIS_2023_01_01.csv"

con = duckdb.connect()
con.execute("PRAGMA threads=4")

print("=== 1. 字段 ===")
cols = con.execute(
    f"DESCRIBE SELECT * FROM read_csv_auto('{CSV}', sample_size=200000)"
).fetchall()
for name, typ, *_ in cols:
    print(f"  {name:20s} {typ}")

print("\n=== 2. 规模与覆盖 ===")
row = con.execute(
    f"""
    SELECT COUNT(*)                         AS rows,
           COUNT(DISTINCT MMSI)             AS vessels,
           MIN(BaseDateTime)                AS t_min,
           MAX(BaseDateTime)                AS t_max,
           MIN(LAT) AS lat_min, MAX(LAT) AS lat_max,
           MIN(LON) AS lon_min, MAX(LON) AS lon_max
    FROM read_csv_auto('{CSV}')
    """
).fetchone()
keys = ["rows", "vessels", "t_min", "t_max",
        "lat_min", "lat_max", "lon_min", "lon_max"]
for k, v in zip(keys, row):
    print(f"  {k:10s} {v}")

print("\n=== 3. 纬度带分布（每 10 度）===")
for lat0, n in con.execute(
    f"""
    SELECT FLOOR(LAT/10)*10 AS lat_band, COUNT(*) AS n
    FROM read_csv_auto('{CSV}')
    GROUP BY 1 ORDER BY 1
    """
).fetchall():
    print(f"  {lat0:>5.0f}° ~ {lat0+10:>4.0f}°   {n:>12,}")

print("\n=== 4. 航速分布 ===")
for lo, cnt in con.execute(
    f"""
    SELECT CASE
             WHEN SOG IS NULL THEN 'null'
             WHEN SOG < 1  THEN '0-1'
             WHEN SOG < 5  THEN '1-5'
             WHEN SOG < 10 THEN '5-10'
             WHEN SOG < 20 THEN '10-20'
             ELSE '20+'
           END AS band, COUNT(*) AS n
    FROM read_csv_auto('{CSV}')
    GROUP BY 1 ORDER BY n DESC
    """
).fetchall():
    print(f"  {lo:>6s} kn   {cnt:>12,}")
