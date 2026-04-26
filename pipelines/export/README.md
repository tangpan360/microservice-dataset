# 导出 Online Boutique 运行数据

---

### 1) 这部分在整体流程中的位置

这部分负责把 `Online Boutique` 运行过程中的 Prometheus 指标和 Jaeger traces 导出为 `exported` 原始数据。

本文默认约定：

- 你已经按 `benchmarks/online_boutique/docs/quickstart.md` 完成部署
- 你已经按 `pipelines/traffic/README.md` 生成好 schedule
- 本阶段的输出目录为 `dataset/processed/<dataset>/exported/run_id=<run_id>/`

当前正式版默认访问方式：

- 默认走宿主机本地地址：
  - `Prometheus`: `http://127.0.0.1:19090`
  - `Jaeger`: `http://127.0.0.1:16686`
- 也可以显式覆盖：
  - 单次命令行参数 `--prom` / `--jaeger`
  - 环境变量 `EXPORT_PROM_URL` / `EXPORT_JAEGER_URL`

---

### 2) ClarkNet 正式采集

这一步对应 `ClarkNet` 流量回放。推荐改成两阶段：

- 阶段 A：只执行 `ClarkNet` schedule 注入，不做在线增量导出
- 阶段 B：注入自然结束后，再按 `run_manifest.json` 记录的时间窗补导 `Prometheus` / `Jaeger`

先进入 `microservice-dataset` 仓库根目录：

```bash
cd microservice-dataset
pwd
```

确认当前目录正确后，再生成这次采集的标识：

```bash
RUN_ID="clarknet-$(date +%Y%m%d_%H%M%S)"
SCENARIO_ID="clarknet-peak-u2000-step10s"
RUN_DIR="dataset/processed/online_boutique_clarknet/exported/run_id=${RUN_ID}"

echo "RUN_ID=$RUN_ID"
echo "SCENARIO_ID=$SCENARIO_ID"
echo "RUN_DIR=$RUN_DIR"
```

先记下这里打印出来的 `RUN_ID` / `SCENARIO_ID`。

这里几项的含义是：

- `RUN_DIR`：这次采集和后续补导的根目录
- `run_manifest.json`：这次实验的摘要信息
- `injection_events.jsonl`：注入开始/结束等事件时间日志

然后在同一个终端的 `microservice-dataset` 仓库根目录运行：

```bash
RUN_DIR="dataset/processed/online_boutique_clarknet/exported/run_id=<same RUN_ID as terminal 1>"
SCHED="dataset/processed/traffic/ClarkNet-HTTP/schedules/clarknet_users_10s_peak_u2000.csv"
# 把上面 echo 出来的 RUN_ID 原样填到这里
export OB_RUN_ID="<paste RUN_ID from terminal 1>"
# 把上面 echo 出来的 SCENARIO_ID 原样填到这里
export OB_SCENARIO_ID="<paste SCENARIO_ID from terminal 1>"
export OB_RUN_ARTIFACT_DIR="$RUN_DIR"

bash benchmarks/online_boutique/loadgen-locust/run_traffic_schedule_10s.sh "$SCHED" 16 14d --web-port 0
```

注入结束后，这一步会在 `RUN_DIR` 下补充：

- `run_manifest.json`
- `injection_events.jsonl`

然后再执行离线补导：

```bash
python pipelines/export/export_raw_postrun.py \
  --run-dir "$RUN_DIR"
```

默认会：

- 从 `run_manifest.json` 读取 `inject_start_utc` / `inject_end_utc`
- 在注入前后各补 `5` 分钟缓冲
- `Prometheus` 按 `60` 分钟块导出
- `Jaeger` 按 `10` 分钟外层块、`1` 分钟 slice 导出

如果只想先补导 `Prometheus` 或 `Jaeger`，可以加：

```bash
python pipelines/export/export_raw_postrun.py --run-dir "$RUN_DIR" --only prom
python pipelines/export/export_raw_postrun.py --run-dir "$RUN_DIR" --only jaeger
```

---

### 3) NASA 正式采集

这一步对应 `NASA` 流量回放。流程与 `ClarkNet` 相同，也是：

- 阶段 A：只执行 `NASA` schedule 注入
- 阶段 B：注入结束后再离线补导 `Prometheus` / `Jaeger`

先进入 `microservice-dataset` 仓库根目录：

```bash
cd microservice-dataset
pwd
```

确认当前目录正确后，再生成这次采集的标识：

```bash
RUN_ID="nasa-$(date +%Y%m%d_%H%M%S)"
SCENARIO_ID="nasa-peak-u2000-step10s"
RUN_DIR="dataset/processed/online_boutique_nasa/exported/run_id=${RUN_ID}"

echo "RUN_ID=$RUN_ID"
echo "SCENARIO_ID=$SCENARIO_ID"
echo "RUN_DIR=$RUN_DIR"
```

先记下这里打印出来的 `RUN_ID` / `SCENARIO_ID`。

这里几项的含义是：

- `RUN_DIR`：这次采集和后续补导的根目录
- `run_manifest.json`：这次实验的摘要信息
- `injection_events.jsonl`：注入开始/结束等事件时间日志

然后在同一个终端的 `microservice-dataset` 仓库根目录运行：

```bash
RUN_DIR="dataset/processed/online_boutique_nasa/exported/run_id=<same RUN_ID as terminal 1>"
SCHED="dataset/processed/traffic/NASA-HTTP/schedules/nasa_users_10s_peak_u2000.csv"
# 把上面 echo 出来的 RUN_ID 原样填到这里
export OB_RUN_ID="<paste RUN_ID from terminal 1>"
# 把上面 echo 出来的 SCENARIO_ID 原样填到这里
export OB_SCENARIO_ID="<paste SCENARIO_ID from terminal 1>"
export OB_RUN_ARTIFACT_DIR="$RUN_DIR"

bash benchmarks/online_boutique/loadgen-locust/run_traffic_schedule_10s.sh "$SCHED" 16 14d --web-port 0
```

这一步会在 `RUN_DIR` 下补充：

- `run_manifest.json`
- `injection_events.jsonl`

然后再执行离线补导：

```bash
python pipelines/export/export_raw_postrun.py \
  --run-dir "$RUN_DIR"
```

---

### 4) 采集完成后会得到什么

推荐把 `exported` 放到：

- `dataset/processed/<dataset>/exported/run_id=<run_id>/`

例如：

- `dataset/processed/online_boutique_clarknet/exported/run_id=<run_id>/`
- `dataset/processed/online_boutique_nasa/exported/run_id=<run_id>/`

离线补导后，导出的 `meta.json` 会保存：

- 时间窗信息
- `run_id`
- `scenario_id`
- Jaeger `hit_limit`

注入脚本额外会保存：

- `run_manifest.json`：本次实验的摘要信息
- `injection_events.jsonl`：注入开始/结束等事件时间

---

### 5) 只想单独测试 Prometheus / Jaeger 导出

如果你还不想开始正式采集，只想先验证单个导出脚本能否工作，可以在 `microservice-dataset/pipelines/export` 下运行：

```bash
cd pipelines/export

# 最近 30 分钟 Prometheus 指标
python export_prom_metrics.py

# 最近 30 分钟 Jaeger traces
python export_jaeger_traces.py --service frontend.ob
```

默认输出到：

- `runs/export_prom_metrics/<timestamp>/`
- `runs/export_jaeger_traces/<timestamp>/`

---

### 6) 常用参数

最常用的是这些：

- `--run-id`：一次完整采集的统一 ID
- `--scenario-id`：场景标签
- `--out-base-dir`：导出输出根目录
- `--only prom`：只导出 Prometheus
- `--only jaeger`：只导出 Jaeger
- `--dry-run`：只看本次会导什么，不实际执行
- `--run-dir`：`export_raw_postrun.py` 使用的采集目录
- `--pad-before-minutes` / `--pad-after-minutes`：离线补导在注入前后额外补的分钟数
- `--prom-chunk-minutes`：Prometheus 离线补导块大小
- `--jaeger-chunk-minutes`：Jaeger 离线补导外层块大小

单次导出脚本和离线补导脚本都围绕时间窗工作，其中单次导出脚本还支持这些显式时间参数：

- `--minutes`
- `--hours`
- `--days`
- `--start`
- `--end`

---

### 7) 一些补充说明

`export_prom_metrics.py` 默认导出这些服务级指标：

- service in/out RPS
- service mean / p95 / p99 latency
- 5xx RPS
- error rate / timeout rate
- CPU
- memory
- CPU throttling ratio
- replicas spec / available
- active node count

其中 `error_rate` / `timeout_rate` / `latency_*` 查询会对零流量边界做兜底：

- 没有错误/超时时，按服务返回 `0`，而不是缺失整条 series
- 请求分母为 `0` 时，返回 `0`，避免导出 `NaN`

`export_jaeger_traces.py` 默认按 `frontend.ob` 过滤 traces。  
如果你想先查看当前环境里的 Jaeger 服务名，可以运行：

```bash
kubectl -n observability port-forward svc/jaeger-query 16686:16686
curl "http://127.0.0.1:16686/api/services"
```

---

### 8) 增量导出的默认行为

默认配置文件：

- `pipelines/export/export_raw_config.json`

其中 `url=""` 表示自动选择默认访问地址：

- 默认走本地 `localhost` 地址

默认状态文件：

- `runs/export_raw/state/prom_last_end.json`
- `runs/export_raw/state/jaeger_last_end.json`

当前默认策略：

- Prom：每次补最近未导出的 `10min`，`lag=2min`，`overlap=1min`
- Jaeger：每次补最近未导出的 `5min`，内部按 `1min` 小窗切片，`service=frontend.ob`
