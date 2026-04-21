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

### 输出

默认输出到 `microservice-dataset/runs/traffic_schedules/`（相对于 `microservice-dataset/` 根目录为 `runs/traffic_schedules/`）：

- `clarknet_users_10s_p99_1m_u2000.csv`
- `nasa_users_10s_p99_1m_u2000.csv`

输出的 `*_users_10s_*.csv` 是 Online Boutique 分布式 Locust 的动态注入输入文件。

使用示例：

```bash
# 在 microservice-dataset 根目录运行
SCHED="runs/traffic_schedules/clarknet_users_10s_p99_1m_u2000.csv"
export OB_RUN_ID="clarknet-$(date +%Y%m%d_%H%M%S)"
export OB_PROFILE="day_normal"
export OB_SCENARIO_ID="clarknet-p99_1m-u2000-step10s"

bash benchmarks/online_boutique/loadgen-locust/run_traffic_schedule_10s.sh "$SCHED" 16 30m --web-port 0
```
