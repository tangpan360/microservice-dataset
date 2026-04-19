# Traffic Pipelines

当前整理这些流量数据集的下载、解压与分钟级提取方式。

## NASA-HTTP

### 下载

官方来源：

- [NASA-HTTP - Internet Traffic Archive](https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html)

下载方式：

```bash
mkdir -p dataset/raw/NASA-HTTP
cd dataset/raw/NASA-HTTP

wget ftp://ita.ee.lbl.gov/traces/NASA_access_log_Jul95.gz
wget ftp://ita.ee.lbl.gov/traces/NASA_access_log_Aug95.gz
```

解压：

```bash
gunzip NASA_access_log_Jul95.gz
gunzip NASA_access_log_Aug95.gz
```

### 提取

提取整个目录：

```bash
python pipelines/traffic/extract_nasa_requests_per_minute.py \
  --input dataset/raw/NASA-HTTP \
  --output dataset/processed/traffic/NASA-HTTP
```

提取单个文件：

```bash
python pipelines/traffic/extract_nasa_requests_per_minute.py \
  --input dataset/raw/NASA-HTTP/NASA_access_log_Jul95 \
  --output dataset/processed/traffic/NASA-HTTP/NASA_access_log_Jul95_requests_per_minute.csv
```

### 可视化

可视化整个目录：

```bash
python pipelines/traffic/plot_daily_minute_curves.py \
  --input dataset/processed/traffic/NASA-HTTP \
  --output analysis/NASA-HTTP
```

可视化单个文件：

```bash
python pipelines/traffic/plot_daily_minute_curves.py \
  --input dataset/processed/traffic/NASA-HTTP/NASA_access_log_Jul95_requests_per_minute.csv \
  --output analysis/NASA-HTTP/NASA_access_log_Jul95_daily_minute_curves.png
```

说明：

- 脚本默认最多只可视化前 `31` 天。
- 如果某个数据文件超过 `1` 个月，默认只画前 `1` 个月。
- 如果想取消这个限制，可以额外加 `--max-days 0`。

## ClarkNet-HTTP

### 下载

官方来源：

- [ClarkNet-HTTP - Internet Traffic Archive](https://ita.ee.lbl.gov/html/contrib/ClarkNet-HTTP.html)

下载方式：

```bash
mkdir -p dataset/raw/ClarkNet-HTTP
cd dataset/raw/ClarkNet-HTTP

wget ftp://ita.ee.lbl.gov/traces/clarknet_access_log_Aug28.gz
wget ftp://ita.ee.lbl.gov/traces/clarknet_access_log_Sep4.gz
```

解压：

```bash
gunzip clarknet_access_log_Aug28.gz
gunzip clarknet_access_log_Sep4.gz
```

### 提取

提取整个目录：

```bash
python pipelines/traffic/extract_clarknet_requests_per_minute.py \
  --input dataset/raw/ClarkNet-HTTP \
  --output dataset/processed/traffic/ClarkNet-HTTP
```

提取单个文件：

```bash
python pipelines/traffic/extract_clarknet_requests_per_minute.py \
  --input dataset/raw/ClarkNet-HTTP/clarknet_access_log_Aug28 \
  --output dataset/processed/traffic/ClarkNet-HTTP/clarknet_access_log_Aug28_requests_per_minute.csv
```

### 可视化

可视化整个目录：

```bash
python pipelines/traffic/plot_daily_minute_curves.py \
  --input dataset/processed/traffic/ClarkNet-HTTP \
  --output analysis/ClarkNet-HTTP
```

可视化单个文件：

```bash
python pipelines/traffic/plot_daily_minute_curves.py \
  --input dataset/processed/traffic/ClarkNet-HTTP/clarknet_access_log_Aug28_requests_per_minute.csv \
  --output analysis/ClarkNet-HTTP/clarknet_access_log_Aug28_daily_minute_curves.png
```

## Calgary-HTTP

### 下载

官方来源：

- [Calgary-HTTP - Internet Traffic Archive](https://ita.ee.lbl.gov/html/contrib/Calgary-HTTP.html)

下载方式：

```bash
mkdir -p dataset/raw/Calgary-HTTP
cd dataset/raw/Calgary-HTTP

wget ftp://ita.ee.lbl.gov/traces/calgary_access_log.gz
```

解压：

```bash
gunzip calgary_access_log.gz
```

### 提取

```bash
python pipelines/traffic/extract_calgary_requests_per_minute.py \
  --input dataset/raw/Calgary-HTTP/calgary_access_log \
  --output dataset/processed/traffic/Calgary-HTTP/calgary_access_log_requests_per_minute.csv
```

### 可视化

```bash
python pipelines/traffic/plot_daily_minute_curves.py \
  --input dataset/processed/traffic/Calgary-HTTP/calgary_access_log_requests_per_minute.csv \
  --output analysis/Calgary-HTTP/calgary_access_log_daily_minute_curves.png
```

说明：

- `Calgary-HTTP` 的时间跨度超过 `1` 个月，默认只可视化前 `31` 天。

## Wikimedia-pageviews_2026_03

### 下载

当前已验证的是按月份目录下载 `2026-03` 的小时级 pageviews 文件。

官方来源：

- [Wikimedia Downloads: Analytics](https://dumps.wikimedia.org/other/analytics/)
- [Pageviews readme](https://dumps.wikimedia.org/other/pageviews/readme.html)

下载方式：

```bash
mkdir -p dataset/raw/Wikimedia-pageviews_2026_03
cd dataset/raw/Wikimedia-pageviews_2026_03

wget -r -np -nH --cut-dirs=4 -A "*.gz" \
  https://dumps.wikimedia.org/other/pageviews/2026/2026-03/
```

解压单个文件：

```bash
gunzip pageviews-20260301-000000.gz
```

批量并行解压当前目录所有文件（10 个进程）：

```bash
find . -maxdepth 1 -name "*.gz" -print0 | xargs -0 -n 1 -P 10 gunzip
```

### 提取

当前未提供 `Wikimedia-pageviews_2026_03` 的分钟级提取脚本；该数据集原始文件本身就是小时级统计。

## worldcup98_may_1998

### 下载

当前已验证两部分：

1. `WorldCup_tools.tar.gz`
2. `wc_day6_1.gz` 到 `wc_day36_1.gz`

官方来源：

- [WorldCup98 - Internet Traffic Archive](https://ita.ee.lbl.gov/html/contrib/WorldCup.html)

下载方式：

```bash
mkdir -p dataset/raw/worldcup98_may_1998
cd dataset/raw/worldcup98_may_1998

wget ftp://ita.ee.lbl.gov/software/WorldCup_tools.tar.gz
```

解压 tools：

```bash
tar -xzf WorldCup_tools.tar.gz
```

下载 `day6_1` 到 `day36_1`：

```bash
for d in $(seq 6 36); do
  wget "ftp://ita.ee.lbl.gov/traces/WorldCup/wc_day${d}_1.gz"
done
```

解压 `day6_1` 到 `day36_1`：

```bash
gunzip wc_day*_1.gz
```

### 提取

提取整个目录：

```bash
python pipelines/traffic/extract_worldcup_requests_per_minute.py \
  --input dataset/raw/worldcup98_may_1998 \
  --output dataset/processed/traffic/worldcup98_may_1998
```

提取单个文件：

```bash
python pipelines/traffic/extract_worldcup_requests_per_minute.py \
  --input dataset/raw/worldcup98_may_1998/wc_day6_1 \
  --output dataset/processed/traffic/worldcup98_may_1998/wc_day6_1_requests_per_minute.csv
```

### 可视化

可视化整个目录：

```bash
python pipelines/traffic/plot_daily_minute_curves.py \
  --input dataset/processed/traffic/worldcup98_may_1998 \
  --output analysis/worldcup98_may_1998
```

可视化单个文件：

```bash
python pipelines/traffic/plot_daily_minute_curves.py \
  --input dataset/processed/traffic/worldcup98_may_1998/wc_day6_1_requests_per_minute.csv \
  --output analysis/worldcup98_may_1998/wc_day6_1_daily_minute_curves.png
```
