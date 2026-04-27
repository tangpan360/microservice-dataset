# Traffic Pipelines

整理流量数据集的下载、解压与秒级提取方式。

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

默认提取 `NASA_access_log_Aug95` 中 `1995-08-07` 到 `1995-08-20` 这 `14` 天的秒级数据：

```bash
cd pipelines/traffic
python extract_nasa_requests.py
```

默认输出文件：

- `dataset/processed/traffic/NASA-HTTP/NASA_access_log_Aug95_19950807_19950820_requests_per_second.csv`

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

默认提取整个目录并合并成一个两周的秒级 CSV：

```bash
cd pipelines/traffic
python extract_clarknet_requests.py
```

默认输出文件：

- `dataset/processed/traffic/ClarkNet-HTTP/clarknet_access_log_aug28_sep10_requests_per_second.csv`

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

## 生成 Locust 10s 注入 schedule

把已经提取好的**秒级**流量 CSV（`timestamp,request_count`）转换成 Locust 可直接使用的 **10s 注入 schedule**。

### 运行

前置条件：你已经跑完上面的提取步骤，得到两份秒级 CSV：

- `dataset/processed/traffic/ClarkNet-HTTP/clarknet_access_log_aug28_sep10_requests_per_second.csv`
- `dataset/processed/traffic/NASA-HTTP/NASA_access_log_Aug95_19950807_19950820_requests_per_second.csv`

生成 schedule：

```bash
cd pipelines/traffic

# 默认生成 clarknet + nasa 两份 schedule
python build_users_schedule_10s.py

# 或者只生成一个数据集
python build_users_schedule_10s.py --data clarknet
python build_users_schedule_10s.py --data nasa
```

当前默认策略是：

- 直接用全局最高的 `10s avg RPS` 对齐到 `1000 users`
- 其余所有时间点按比例整体缩放
- 最终 schedule 的实际峰值就是 `1000 users`

### 输出

默认输出到各自数据集目录下的 `schedules/`：

- `dataset/processed/traffic/ClarkNet-HTTP/schedules/clarknet_users_10s_peak_u1000.csv`
- `dataset/processed/traffic/NASA-HTTP/schedules/nasa_users_10s_peak_u1000.csv`

默认文件名里的 `peak` 表示它是按全局最高 `10s avg RPS` 对齐生成的。

输出的 `*_users_10s_*.csv` 是 Online Boutique 分布式 Locust 的动态注入输入文件。

对应的 `*_meta_*.json` 里会额外记录：

- `peak_rps`
- `peak_users`
