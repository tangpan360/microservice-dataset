# Prepare Pipelines

将 `export` 阶段导出的 raw JSON 继续整理成：

1. `canonical`
2. `tables`

这层的职责是：

- 合并重叠窗口
- 去重 Prom / Jaeger 原始数据
- 生成服务级分钟主表和调用边表

## 当前脚本

### 1. Canonicalize raw

- `canonicalize_prom_daily_json.py`
  - 输入：`<dataset-root>/exported/run_id=<run_id>/prom/...`
  - 输出：`dataset/processed/<dataset>/canonical/...`
  - 结果：每天每个指标一个 JSON，跨窗口去重后保留

- `canonicalize_jaeger_daily_json.py`
  - 输入：`<dataset-root>/exported/run_id=<run_id>/jaeger/...`
  - 输出：`dataset/processed/<dataset>/canonical/...`
  - 结果：每天每个服务一个 `traces.json`，按 `(trace_id, span_id)` 去重

### 2. Build intermediate tables

- `build_online_boutique_intermediate.py`
  - 输入：`canonical/prom/...` 和 `canonical/jaeger/...`
  - 输出：
    - `service_minute_features`
    - `service_call_edge_minute`
    - `service_metadata`
    - `run_metadata`

## 常用用法

### 处理某次 `run_id` 的数据

当前只支持这套数据布局：

- `dataset/processed/<dataset>/exported/run_id=<run_id>/...`

也就是说，这层脚本统一要求显式传：

- `--dataset-root`
- `--run-id`

例如：

```bash
cd pipelines/prepare

DATASET_ROOT="../../dataset/processed/online_boutique_clarknet"
RUN_ID="clarknet-20260427_111536"
```

### 生成 canonical raw

```bash
python canonicalize_prom_daily_json.py \
  --dataset-root "$DATASET_ROOT" \
  --run-id "$RUN_ID"

python canonicalize_jaeger_daily_json.py \
  --dataset-root "$DATASET_ROOT" \
  --run-id "$RUN_ID"
```

### 生成第 2 层 tables

默认输出 CSV：

- `service_minute_features`
- `service_call_edge_minute`
- `service_metadata`
- `run_metadata`

```bash
python build_online_boutique_intermediate.py \
  --dataset-root "$DATASET_ROOT" \
  --run-id "$RUN_ID"
```

### 核心特征体检 + 序列可视化

会输出：

- `report.md` / `report.json`
- 每个服务各特征组的时间序列图（PNG）

默认行为：

- 一次只检查并画 `1` 天
- 如果不传 `--day`，默认选择当前 `run_id` 下最新一天

```bash
cd pipelines/prepare
python inspect_and_plot_core_features.py \
  --dataset-root "$DATASET_ROOT" \
  --run-id "$RUN_ID" \
  --day 2026-04-27
```

常用参数（尽量只记这几个）：

- `--day`: 指定日期（如 `2026-04-22`）。不填则默认取最新一天
- `--services`: 只画指定服务（逗号分隔），例如：

```bash
python inspect_and_plot_core_features.py \
  --dataset-root "$DATASET_ROOT" \
  --run-id "$RUN_ID" \
  --day 2026-04-27 \
  --services frontend,checkoutservice
```

- `--max-points N`: 只画每个服务最后 N 个点（跑很久时避免图太密）
- `--out-dir`: 自定义输出目录
- `--dataset-root`: 指定数据集根目录（如 `dataset/processed/online_boutique_clarknet`），配合 `--run-id` 使用
- `--run-id`: 指定 run
