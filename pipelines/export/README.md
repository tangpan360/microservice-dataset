# 导出 Online Boutique 运行数据

---

### 1) 这部分在整体流程中的位置

这部分负责把 `Online Boutique` 运行过程中的 Prometheus 指标和 Jaeger traces 导出为 `exported` 原始数据。

本文默认约定：

- 你已经按 `benchmarks/online_boutique/docs/quickstart.md` 完成部署
- 你已经按 `pipelines/traffic/README.md` 生成好 schedule
- 本阶段的输出目录为 `dataset/processed/<dataset>/exported/run_id=<run_id>/`

---

### 2) ClarkNet 正式采集

这一步对应 `ClarkNet` 流量回放。推荐使用两个终端：

- 终端 1：循环触发增量导出，持续写入 `exported`
- 终端 2：执行 `ClarkNet` schedule 注入

先进入 `microservice-dataset` 仓库根目录：

```bash
cd microservice-dataset
pwd
```

确认当前目录正确后，再生成这次采集的标识：

```bash
RUN_ID="clarknet-$(date +%Y%m%d_%H%M%S)"
SCENARIO_ID="clarknet-p99_1m-u2000-step10s"
RUN_DIR="dataset/processed/online_boutique_clarknet/exported/run_id=${RUN_ID}"
STATE_DIR="${RUN_DIR}/state"

echo "RUN_ID=$RUN_ID"
echo "SCENARIO_ID=$SCENARIO_ID"
echo "RUN_DIR=$RUN_DIR"
echo "STATE_DIR=$STATE_DIR"
```

先记下这里打印出来的 `RUN_ID` / `SCENARIO_ID`，后面终端 2 要原样使用。

这里几项的含义是：

- `RUN_DIR`：这次采集的根目录
- `STATE_DIR`：增量导出的进度目录，用于断点续跑
- `run_manifest.json`：这次实验的摘要信息
- `injection_events.jsonl`：注入开始/结束等事件时间日志

如果只是先检查这次会导出什么，可以先运行一次：

```bash
python pipelines/export/export_raw_incremental.py \
  --run-id "$RUN_ID" \
  --scenario-id "$SCENARIO_ID" \
  --out-base-dir "$RUN_DIR" \
  --state-dir "$STATE_DIR" \
  --dry-run
```

确认无误后，再启动持续增量导出。这里不预先写死结束时间，而是让它一直运行；等终端 2 的 14 天注入自然结束后，再回到这里手动停止。

```bash
while true; do
  date -u +"[%Y-%m-%dT%H:%M:%SZ] incremental export tick"
  python pipelines/export/export_raw_incremental.py \
    --run-id "$RUN_ID" \
    --scenario-id "$SCENARIO_ID" \
    --out-base-dir "$RUN_DIR" \
    --state-dir "$STATE_DIR"
  sleep 60
done
```

终端 2 自然结束后，再回到这里按 `Ctrl+C` 停止即可。

然后在终端 2 的 `microservice-dataset` 仓库根目录运行：

```bash
RUN_DIR="dataset/processed/online_boutique_clarknet/exported/run_id=<same RUN_ID as terminal 1>"
SCHED="dataset/processed/traffic/ClarkNet-HTTP/schedules/clarknet_users_10s_p99_1m_u2000.csv"
# 把终端 1 echo 出来的 RUN_ID 原样填到这里
export OB_RUN_ID="<paste RUN_ID from terminal 1>"
# 把终端 1 echo 出来的 SCENARIO_ID 原样填到这里
export OB_SCENARIO_ID="<paste SCENARIO_ID from terminal 1>"
export OB_RUN_ARTIFACT_DIR="$RUN_DIR"

bash benchmarks/online_boutique/loadgen-locust/run_traffic_schedule_10s.sh "$SCHED" 16 14d --web-port 0
```

这一步会在 `RUN_DIR` 下补充：

- `run_manifest.json`
- `injection_events.jsonl`

---

### 3) NASA 正式采集

这一步对应 `NASA` 流量回放。推荐同样使用两个终端：

- 终端 1：循环触发增量导出，持续写入 `exported`
- 终端 2：执行 `NASA` schedule 注入

先进入 `microservice-dataset` 仓库根目录：

```bash
cd microservice-dataset
pwd
```

确认当前目录正确后，再生成这次采集的标识：

```bash
RUN_ID="nasa-$(date +%Y%m%d_%H%M%S)"
SCENARIO_ID="nasa-p99_1m-u2000-step10s"
RUN_DIR="dataset/processed/online_boutique_nasa/exported/run_id=${RUN_ID}"
STATE_DIR="${RUN_DIR}/state"

echo "RUN_ID=$RUN_ID"
echo "SCENARIO_ID=$SCENARIO_ID"
echo "RUN_DIR=$RUN_DIR"
echo "STATE_DIR=$STATE_DIR"
```

先记下这里打印出来的 `RUN_ID` / `SCENARIO_ID`，后面终端 2 要原样使用。

这里几项的含义是：

- `RUN_DIR`：这次采集的根目录
- `STATE_DIR`：增量导出的进度目录，用于断点续跑
- `run_manifest.json`：这次实验的摘要信息
- `injection_events.jsonl`：注入开始/结束等事件时间日志

如果只是先检查这次会导出什么，可以先运行一次：

```bash
python pipelines/export/export_raw_incremental.py \
  --run-id "$RUN_ID" \
  --scenario-id "$SCENARIO_ID" \
  --out-base-dir "$RUN_DIR" \
  --state-dir "$STATE_DIR" \
  --dry-run
```

确认无误后，再启动持续增量导出。这里不预先写死结束时间，而是让它一直运行；等终端 2 的 14 天注入自然结束后，再回到这里手动停止。

```bash
while true; do
  date -u +"[%Y-%m-%dT%H:%M:%SZ] incremental export tick"
  python pipelines/export/export_raw_incremental.py \
    --run-id "$RUN_ID" \
    --scenario-id "$SCENARIO_ID" \
    --out-base-dir "$RUN_DIR" \
    --state-dir "$STATE_DIR"
  sleep 60
done
```

终端 2 自然结束后，再回到这里按 `Ctrl+C` 停止即可。

然后在终端 2 的 `microservice-dataset` 仓库根目录运行：

```bash
RUN_DIR="dataset/processed/online_boutique_nasa/exported/run_id=<same RUN_ID as terminal 1>"
SCHED="dataset/processed/traffic/NASA-HTTP/schedules/nasa_users_10s_p99_1m_u2000.csv"
# 把终端 1 echo 出来的 RUN_ID 原样填到这里
export OB_RUN_ID="<paste RUN_ID from terminal 1>"
# 把终端 1 echo 出来的 SCENARIO_ID 原样填到这里
export OB_SCENARIO_ID="<paste SCENARIO_ID from terminal 1>"
export OB_RUN_ARTIFACT_DIR="$RUN_DIR"

bash benchmarks/online_boutique/loadgen-locust/run_traffic_schedule_10s.sh "$SCHED" 16 14d --web-port 0
```

这一步会在 `RUN_DIR` 下补充：

- `run_manifest.json`
- `injection_events.jsonl`

---

### 4) 采集完成后会得到什么

推荐把 `exported` 放到：

- `dataset/processed/<dataset>/exported/run_id=<run_id>/`

例如：

- `dataset/processed/online_boutique_clarknet/exported/run_id=<run_id>/`
- `dataset/processed/online_boutique_nasa/exported/run_id=<run_id>/`

导出的 `meta.json` 会保存：

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
- `--out-base-dir`：增量导出的输出根目录
- `--only prom`：只导出 Prometheus
- `--only jaeger`：只导出 Jaeger
- `--dry-run`：只看本次会导什么，不实际执行

单次导出脚本还支持时间窗参数：

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

默认状态文件：

- `runs/export_raw/state/prom_last_end.json`
- `runs/export_raw/state/jaeger_last_end.json`

当前默认策略：

- Prom：每次补最近未导出的 `10min`，`lag=2min`，`overlap=1min`
- Jaeger：每次补最近未导出的 `5min`，内部按 `1min` 小窗切片，`service=frontend.ob`
