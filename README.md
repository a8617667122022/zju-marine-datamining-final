# 分辨率如何改变“船舶热区”的结论

**基于 AIS 数据的 H3 选档实验与口径合同**

课程：海洋数据挖掘技术（研）· 浙江大学　　专业：海洋技术

对应第 3 讲“空间数据的编码与落格”。课件给出了 H3 各分辨率的面积量级，
但选档原则只有“按业务尺度、数据质量和样本量选档”一句定性描述。
本课题把它变成一条可计算、可复现的判据，并用公开 AIS 数据做实证。

---

## 一句话结论

稳定性不是“收敛—平台”，而是**缓慢衰减 + 断崖**；而断崖约八成来自**同尺度可靠性天花板 O_r 的坍塌**，
不是尺度效应。判据因此改为“**取最细的 r，使 O_r ≥ ρ**”，不再拍一个一致性阈值。
H3 的等积优势只在全球尺度成立。

## 仓库结构

```
.
├── README.md
├── ai-log/                  与 AI 的协作记录（逐字主证据 + 阶段摘要，当时记录与事后复盘分开标注）
│   ├── 00-用户逐字输入与AI行动轨迹.md   主证据：41 轮用户逐字输入 + AI 回复正文 + 每轮文件轨迹
│   ├── 01-选题与方案确定.md             阶段摘要（叙述第 1–8 轮）
│   ├── 02-实验推进与主线改写.md         阶段摘要（叙述第 9–12 轮）
│   ├── 03-原创点深化与自我纠错.md       阶段摘要（叙述第 13–16 轮）
│   └── 04-三判据交叉验证.md             阶段摘要（叙述第 17–21 轮）
├── report/
│   ├── report.md            实验报告正文
│   └── design.md            方案设计备忘
├── code/
│   ├── 00_data_check.py     数据体检
│   ├── 01_prepare.py        CSV → parquet + H3 落格
│   ├── 02_experiments.py    E1–E4
│   ├── 03_e5_grids.py       E5：H3 / Geohash / 等经纬网格对照
│   ├── 04_figures.py        出图
│   ├── 05_reliability.py    E6：split-half 可靠性天花板与 SSI（原创点 A）
│   ├── 06_persistence.py    E7：层级持久热点（原创点 B）
│   ├── 07_crosscheck.py     E8：局部方差 / 支撑度 / 可靠性三判据（原创点 C）
│   ├── 08_halfcell_shift.py E9：半格平移扰动（MAUP 划区效应）
│   ├── 09_summary_assets.py 图 10–13 与汇总产物
│   ├── 09b_or_seeds_fix.py  O_r 逐种子图修正
│   ├── 10_stat_ci.py        O_r 置信区间与相邻档配对检验（含 Cohen's d_z）
│   └── h3_advisor.py        选档判据工具（输出口径合同 JSON）
├── results/
│   ├── *.csv                实验产物
│   └── figures/*.png        报告用图
└── data/README.md           数据来源与获取方式（原始数据不入库）
```

## 实验一览

| 编号 | 内容 | 产物 |
|---|---|---|
| E1 | 面积随纬度的畸变；count 口径 vs 密度口径的排序差异 | `results/e1_area_by_lat.csv` |
| E2 | res 4–9 的层次一致率与等质量 IoU（B 主 / A 对照） | `results/e2_stability_*.csv` |
| E3 | 每格样本量随分辨率的变化 | `results/e3_sample.csv` |
| E4 | 切成 4 个 6 小时时段的稳健性 | `results/e4_temporal.csv` |
| E5 | H3 vs Geohash vs 等经纬网格（局部 + 全球面积） | `results/e5_grids.csv`, `e5_area_global.csv` |
| E6 | split-half 可靠性天花板与归一化尺度稳定指数 SSI | `results/e6_reliability.csv` |
| E7 | 层级持久热点：寿命、持久核心、等质量对照 | `results/e7_summary.json`, `e7_birth_profile.csv` |
| E8 | 局部方差比 / 支撑度 / 质量效率三判据 | `results/e8_crosscheck.csv` |
| E9 | 半格平移扰动：划区效应（MAUP）的固定税 | `results/e9_halfcell.csv`, `e9_summary.json` |
| E10 | O_r 的 95% 置信区间、相邻档配对 t 检验与 Cohen's d_z | `results/e10_cr_ci.csv`, `e10_pairwise_tests.csv`, `e10_ci_significance.csv` |

## 复现方式

```bash
pip install duckdb h3 pandas numpy matplotlib pyarrow pygeohash scipy

# 1) 数据体检
python code/00_data_check.py
# 2) 落格，生成 parquet（需要先按 data/README.md 下载原始 CSV）
python code/01_prepare.py
# 3) 跑实验
python code/02_experiments.py
python code/03_e5_grids.py
python code/05_reliability.py
python code/06_persistence.py
python code/07_crosscheck.py
python code/08_halfcell_shift.py
# 4) 出图与汇总
python code/04_figures.py
python code/09_summary_assets.py
python code/09b_or_seeds_fix.py
# 5) 统计显著性核查（O_r 的 95% CI、相邻档配对 t 检验与 Cohen's d_z）
python code/10_stat_ci.py
# 6) 选档工具（可靠性模式）
python code/h3_advisor.py --input data/ais_moving.parquet --lat lat --lon lon --min-overlap 0.90
```

数据来源与许可见 [`data/README.md`](data/README.md)。原始 CSV 体积较大，未纳入版本库。

## 关键结果

- 层次一致性（航行船）：res 5 = 0.899 → res 7 = 0.877 → res 8 = 0.862 → **res 9 = 0.747**
- **同尺度可靠性天花板 O_r 自己在坍塌**：0.978 → 0.939 → 0.893 → **0.813**；
  跨尺度一致率 C_r 只是它的等比例缩放，**SSI = C_r / O_r 稳定在 0.93–0.96**
- 因此断崖约八成来自可靠性天花板，而非尺度效应；判据改为
  “取最细的 r，使 O_r ≥ ρ”，本数据在 ρ = 0.90 下推荐 **res 7**
- **持久性验证（B）**：0.31% 的持久核心承载 **6.74%** 的点，中位样本量 25（瞬态仅 1）；
  res 7 Top-100 的 89.3%、res 9 Top-100 的 84.0% 落在核心内——细档热点是“位置对、排序抖”
- **口径敏感性**：固定 K=100 时 res 4 的 Top-100 覆盖 44.2% 的点、中位样本仅 1；
  换成等质量口径后，跨档嵌套率从 0.85–0.90 降到 **0.33–0.60**，SSI 不可当普适常数
- **特征尺度验证（C）**：局部方差比 LV 在 **res 7 触底（0.434）** 后回升，
  与 split-half 独立吻合；三条判据（可靠性 / 支撑度 / LV）无一条支持 res 8 或 9
- res 9 要覆盖 10% 的点需 **1,769** 个格（res 7 只需 174 个），且 99.4% 的格子样本不足 30
- 全量口径在 res 8 已跌到 0.747（静止船占 80%，稀释更严重）
- res 9 每格中位数 **1 个点**，仅 **0.6%** 的格子样本 ≥ 30
- 三种网格的层次一致性量级相同（0.74–0.88）；面积均匀性在全球尺度上 H3 为 1.97× 极差
  （与 H3 官方 restable 一致，属复现），经纬网格为 5.71×

## AI 协作

协作记录分两层，逐字证据与摘要各司其职：

- **逐字主证据 [`ai-log/00`](ai-log/00-用户逐字输入与AI行动轨迹.md)**：41 轮用户输入的逐字原文（附 15 个源日志文件的 SHA256，可自行复算），外加每轮 AI 回复正文与本轮文件行动轨迹。41 轮中有 40 轮收录了 AI 回复正文（28 轮来自公开分享 API 逐字导出，12 轮来自聊天截图/录屏转录，1 轮因输出被手动终止而无正文），来源逐轮标注，未做美化。
- **阶段摘要 [`ai-log/01`](ai-log/01-选题与方案确定.md)–[`04`](ai-log/04-三判据交叉验证.md)**：把 41 轮归纳为 21 轮叙述，“我的输入”保留原话或原意，“AI 输出”为关键结论摘要（非全文照抄），“本轮我确认了什么”为事后补写；整理时无法逐字还原的内容标注“（复盘）”，标注规则见报告第 7 章。
