"""统计显著性核查：给 O_r 加 95% 置信区间，并对相邻档做配对 t 检验。

依据报告 4.2：12 个随机种子的 split-half 重合率 (results/e6_per_seed.csv)
当作 12 次独立重采样，用 t 分布 (df=11) 算 O_r 的 95% CI；相邻档共用同一批
种子，所以用配对 t 检验 (paired t-test) 与 Wilcoxon 符号秩检验。

这是报告里所有"缓慢下滑不显著、断崖高度显著"数字的来源，可重算核验。

运行：
    python code/10_stat_ci.py
依赖：pandas、numpy、scipy
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PER_SEED = ROOT / "results" / "e6_per_seed.csv"
RELIAB = ROOT / "results" / "e6_reliability.csv"
OUT = ROOT / "results" / "e10_ci_significance.csv"

N = 12  # seeds
TC = stats.t.ppf(0.975, N - 1)  # 2.201 for df=11


def main() -> None:
    df = pd.read_csv(PER_SEED)
    rel = pd.read_csv(RELIAB)

    rows = []
    res_stats = {}
    for r, s in df.groupby("res")["overlap"]:
        s = s.astype(float).values
        m = s.mean()
        sd = s.std(ddof=1)
        half = TC * sd / np.sqrt(N)
        res_stats[int(r)] = s
        rows.append({
            "res": int(r), "n": N, "O_r_mean": round(m, 4),
            "O_r_std": round(sd, 4),
            "O_r_ci_lo": round(m - half, 4), "O_r_ci_hi": round(m + half, 4),
        })

    # 相邻档配对检验
    rs = sorted(res_stats)
    sig_rows = []
    for a, b in zip(rs, rs[1:]):
        diff = res_stats[a] - res_stats[b]
        t, p = stats.ttest_rel(res_stats[a], res_stats[b])
        try:
            _, pw = stats.wilcoxon(res_stats[a], res_stats[b])
        except ValueError:
            pw = np.nan
        sig_rows.append({
            "pair": f"{a}->{b}", "mean_diff": round(float(diff.mean()), 4),
            "t": round(float(t), 2), "p_two_sided": float(p),
            "wilcoxon_p": float(pw) if not np.isnan(pw) else None,
        })

    # C_r 的 CI（来自 e6_reliability 的 cross_mean / cross_std）
    cr_rows = []
    for _, r in rel.iterrows():
        m = r["cross_mean"]
        sd = r["cross_std"]
        if pd.notna(m) and pd.notna(sd):
            half = TC * sd / np.sqrt(N)
            cr_rows.append({
                "res": int(r["res"]),
                "C_r_mean": round(float(m), 4),
                "C_r_ci_lo": round(float(m - half), 4),
                "C_r_ci_hi": round(float(m + half), 4),
            })

    # 打印报告用的关键数字
    print("O_r 95% CI (df=11, n=12):")
    for row in rows:
        print(f"  res {row['res']}: {row['O_r_mean']} [{row['O_r_ci_lo']}, {row['O_r_ci_hi']}]")
    print("\n相邻档配对 t 检验:")
    for row in sig_rows:
        print(f"  {row['pair']}: diff={row['mean_diff']:+.3f} t={row['t']} "
              f"p={row['p_two_sided']:.2e}")

    # 落盘，留痕
    pd.DataFrame(rows).to_csv(OUT, index=False)
    pd.DataFrame(sig_rows).to_csv(
        ROOT / "results" / "e10_pairwise_tests.csv", index=False)
    pd.DataFrame(cr_rows).to_csv(
        ROOT / "results" / "e10_cr_ci.csv", index=False)
    print(f"\nwritten: {OUT.name}, e10_pairwise_tests.csv, e10_cr_ci.csv")


if __name__ == "__main__":
    main()
