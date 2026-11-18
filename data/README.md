# 数据说明

原始数据体积较大，**不纳入版本库**（见根目录 `.gitignore`）。本文件记录数据来源与获取方式，
保证任何人可以按此复现。

## 主数据集：NOAA AIS（船舶自动识别系统）

| 项目 | 内容 |
|---|---|
| 来源 | NOAA / BOEM MarineCadastre，AccessAIS 服务 |
| 地址 | `https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2023/AIS_2023_01_01.zip` |
| 版本 | 2023-01-01 单日全量 |
| 体积 | 约 304 MB（压缩包） |
| 许可 | 美国政府作品，公有领域（Public Domain），可自由使用 |
| 覆盖范围 | 美国近海，约 24°N–49°N，含阿拉斯加、夏威夷周边部分海域 |
| 关键字段 | `MMSI`、`BaseDateTime`、`LAT`、`LON`、`SOG`（对地航速）、`VesselType` |

选它的原因：点密度在港口—航道—外海之间存在三个数量级的差异，正好能暴露
"换一个分辨率，热点就搬家"的问题；而网格分辨率的争议只在密度变化剧烈时才会显现。

## 辅助数据集：Argo 全球剖面

| 项目 | 内容 |
|---|---|
| 来源 | International Argo Program / Ifremer GDAC |
| 地址 | `https://data-argo.ifremer.fr/ar_index_global_prof.txt.gz` |
| 体积 | 约 56 MB |
| 许可 | 开放获取（Argo data policy） |

用途：AIS 只覆盖中纬度一隅，做不了"面积随纬度畸变"的跨纬度实验。Argo 剖面位置
覆盖约 80°S–80°N，用来补充 E1（面积畸变）的纬度切片。

## 获取方式

```bash
# 需要走本机代理 127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
curl -O https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2023/AIS_2023_01_01.zip
curl -O https://data-argo.ifremer.fr/ar_index_global_prof.txt.gz
```
