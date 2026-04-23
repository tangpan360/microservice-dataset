# microservice-dataset

这个仓库用于**可复现地部署微服务应用，并使用真实应用流量曲线注入负载，采集 Prometheus 指标与 Jaeger traces，最终整理成可用于负载预测的结构化数据集**。

当前主维护的基准应用是 **Online Boutique**。

## 整体处理思路（从真实流量到数据表）

1. **真实流量作为负载注入**：从公开 Web 访问日志（如 ClarkNet / NASA）提取秒级请求数序列，并将其映射为 Locust 的动态注入曲线（例如每 10s 的 users 目标），通过 `frontend` 入口持续驱动 Online Boutique 产生真实风格的微服务负载。
2. **系统观测数据导出（exported）**：在 Online Boutique 运行期间导出 Prometheus 指标与 Jaeger traces 的 JSON 窗口切片（允许重叠与重复，便于溯源复现）。
3. **去重合并（canonical）**：把 exported 的重叠窗口按天合并并去重，得到可消费的 canonical JSON。
4. **结构化表（tables）**：从 canonical JSON 构建分钟级主表/边表（Parquet），用于后续特征裁剪与样本构造。

## 仓库结构

- `benchmarks/online_boutique/`
  - `docs/quickstart.md`：从 0 部署到采集的操作手册
  - `manifests/`：监控/可观测相关部署资源（Prom/Jaeger/Otel 等）
- `pipelines/traffic/`
  - 真实流量曲线（NASA/ClarkNet）下载/提取 → 生成 Locust 动态注入 schedule
- `pipelines/export/`
  - 导出 Prom / Jaeger 原始数据（含 `run_id`、`scenario_id` 元信息）
- `pipelines/prepare/`
  - `canonicalize_*`：raw 去重合并（Prom/Jaeger）
  - `build_online_boutique_intermediate.py`：生成分钟级 `tables` 表
- `docs/`
  - 数据字段与整理方案（面向论文/数据集设计）
- `dataset/`
  - `raw/`：原始/公开数据集（如 Alibaba2022 等，按项目实际情况）
  - `processed/<dataset>/`：你采集并整理后的数据输出位置（如 `online_boutique_clarknet`）

## 处理步骤

1. **部署与验证应用可用**
   - 按 `benchmarks/online_boutique/docs/quickstart.md` 部署 kind + Istio + Prom + Jaeger + Online Boutique
2. **准备注入流量（可选：真实流量）**
   - `pipelines/traffic/README.md`：下载 NASA/ClarkNet → 提取秒级请求数 → 生成 `10s` Locust schedule
3. **注入流量并采集 exported**
   - 使用 schedule 驱动 Locust 动态注入
   - 用 `pipelines/export/` 导出 Prom 指标与 Jaeger traces（exported）
4. **canonicalize（合并去重，得到 canonical JSON）**
   - `pipelines/prepare/canonicalize_prom_daily_json.py`
   - `pipelines/prepare/canonicalize_jaeger_daily_json.py`
5. **构建 tables（分钟级主表/边表）**
   - `pipelines/prepare/build_online_boutique_intermediate.py`（输出到 `tables/`）
