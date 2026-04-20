# Traffic Pipelines

整理流量数据集的下载、解压与分钟级提取方式。

## NASA-HTTP

### 下载

官方来源：

- [NASA-HTTP - Internet Traffic Archive](https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html)

下载方式：

```bash
mkdir -p dataset/raw/NASA-HTTP
cd dataset/raw/NASA-HTTP

wget ftp://ita.ee.lbl.gov/traces/NASA_access_log_Aug95.gz
```

解压：

```bash
gunzip NASA_access_log_Aug95.gz
```

### 提取

默认提取 `NASA_access_log_Aug95` 中 `1995-08-07` 到 `1995-08-20` 这 `14` 天的数据：

```bash
cd pipelines/traffic
python extract_nasa_requests_per_minute.py
```

默认输出文件：

- `dataset/processed/traffic/NASA-HTTP/NASA_access_log_Aug95_19950807_19950820_requests_per_minute.csv`

### 可视化

默认只传数据集名字：

```bash
cd pipelines/traffic
python plot_daily_minute_curves.py --data nasa
```

这会默认读取：

- `dataset/processed/traffic/NASA-HTTP`

并把图片输出到同一个目录：

- `dataset/processed/traffic/NASA-HTTP`

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

默认提取整个目录并合并成一个两周的 CSV：

```bash
cd pipelines/traffic
python extract_clarknet_requests_per_minute.py
```

默认输出文件：

- `dataset/processed/traffic/ClarkNet-HTTP/clarknet_access_log_aug28_sep10_requests_per_minute.csv`

### 可视化

默认只传数据集名字：

```bash
cd pipelines/traffic
python plot_daily_minute_curves.py --data clarknet
```

这会默认读取：

- `dataset/processed/traffic/ClarkNet-HTTP`

并把图片输出到同一个目录：

- `dataset/processed/traffic/ClarkNet-HTTP`
