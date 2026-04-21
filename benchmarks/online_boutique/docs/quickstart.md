# 一步一步：部署 Online Boutique + Istio + Prometheus 并采集指标（最小闭环）

目标：跑通一次最小闭环（独立集群部署 -> 打流量 -> 查询 Prometheus -> 导出第一版指标）。

适用场景：
- 你要做微服务负载预测
- 你希望采集 `service_rps_1m`、CPU、内存、`replicas_ready`、延迟、错误率等指标
- 你希望这份文档能直接作为 `microservice-dataset` 中 `Online Boutique` 基准的操作手册

在执行本文命令前，请先进入 `microservice-dataset` 仓库根目录。

---

### 1) 本文采用的部署策略

`Online Boutique` 使用一个**独立的 kind 集群**进行部署与采集。

原因：
- 不和其他业务基准混跑，实验环境更干净
- 避免节点 `pods` 上限被已有工作负载占满
- `Online Boutique` 开启 sidecar 后会新增很多 Pod/容器
- 使用独立集群更干净，也更利于后续做数据采集

本文统一约定：
- kind 集群名：`ob`
- kubectl context：`kind-ob`
- 应用 namespace：`ob`
- 监控 namespace：`monitoring`
- kind 配置文件：`benchmarks/online_boutique/kind-config.yaml`

---

### 2) 前置条件

确保以下工具已经可用：

```bash
kubectl version --client
kind version
helm version
istioctl version --remote=false
docker version
```

本文默认使用 `benchmarks/online_boutique/kind-config.yaml` 创建 kind 集群，并给 kind 节点配置 `docker.io` 镜像站。

说明：
- 这会优先帮助 kind 节点拉取 `docker.io` 上的镜像，例如 `istio/*`、`busybox`、`grafana`
- 它**不会**自动解决 `quay.io`、`ghcr.io`、`registry.k8s.io`、`us-central1-docker.pkg.dev` 这些 registry 的拉取问题
- 因此本文仍然保留“宿主机预拉取 + kind load”的步骤，主要用于这些非 `docker.io` 镜像
- 如果你的宿主机访问外网也需要代理，请先确保宿主机代理可用；不要假设 kind 节点容器中的 `127.0.0.1` 能直接访问宿主机代理

### 3) 清理旧的 `ob` 集群或命名空间（如果存在）

如果你之前已经试过部署 `Online Boutique`，建议先清理旧环境，避免与本次实验冲突。

删除旧集群（如果存在）：

```bash
kind delete cluster --name ob || true
```

如果你不是删除整个集群，而是只清理旧命名空间，可以在对应 context 下执行：

```bash
kubectl delete ns ob --wait=true || true
```

这一步报 `NotFound` 也正常，可以继续。

---

### 4) 创建独立 kind 集群

推荐使用 3 节点 kind 集群：
- 1 个 control-plane
- 2 个 worker

本文直接使用仓库内的配置文件：

```bash
sed -n '1,120p' benchmarks/online_boutique/kind-config.yaml
```

由于 `kind-config.yaml` 使用了 `extraMounts` 将宿主机目录挂载到 kind 节点容器中，创建集群前请先确保宿主机目录存在：

```bash
mkdir -p .local/kind-ob-volumes
```

创建集群：

```bash
kind create cluster --config benchmarks/online_boutique/kind-config.yaml
```

切换 context 并确认节点：

```bash
kubectl config use-context kind-ob
kubectl config current-context
kubectl get nodes -o wide
kubectl get ns
```

你应该看到 3 个节点，当前 context 为 `kind-ob`。

---

### 5) 安装 Istio

本流程使用 `demo` profile，足够支持：
- sidecar 注入
- 服务级指标
- 入口网关

因为 kind 节点已经通过 `kind-config.yaml` 配置了 `docker.io` 镜像站，这里先直接安装 `Istio`。

```bash
istioctl install --set profile=demo -y
```

安装后确认状态：

```bash
kubectl -n istio-system get pods -o wide
kubectl -n istio-system get events --sort-by=.lastTimestamp | tail -n 30
```

安装完成后确认：

```bash
kubectl get ns
kubectl -n istio-system get pods
kubectl -n istio-system get svc
```

等待 `istio-system` 中核心 Pod 进入 `Running`，通常包括：
- `istiod`
- `istio-ingressgateway`

---

### 6) 安装 Prometheus 监控栈

使用 `kube-prometheus-stack` 安装监控组件：
- Prometheus
- Grafana
- kube-state-metrics
- node-exporter

先添加 Helm 仓库：

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

`kind-config.yaml` 只帮 kind 节点解决了 `docker.io` 镜像站；`kube-prometheus-stack` 里还有大量 `quay.io`、`ghcr.io`、`registry.k8s.io` 镜像，所以这里仍然使用“宿主机预拉取 + kind load”的稳妥方式。

先下载固定版本 chart 到本地目录：

```bash
PROM_CHART_VERSION="82.17.0"
PROM_CHART_ROOT="/tmp/ob-kube-prometheus-stack-chart"

rm -rf "$PROM_CHART_ROOT"
mkdir -p "$PROM_CHART_ROOT"

helm pull prometheus-community/kube-prometheus-stack \
  --version "$PROM_CHART_VERSION" \
  --untar \
  --untardir "$PROM_CHART_ROOT"
```

再基于本地 chart 渲染 manifest：

```bash
PROM_CHART_ROOT="/tmp/ob-kube-prometheus-stack-chart"
PROM_CHART="$PROM_CHART_ROOT/kube-prometheus-stack"
PROM_TMP="/tmp/ob-kube-prometheus-stack-rendered.yaml"

helm template monitoring "$PROM_CHART" -n monitoring > "$PROM_TMP"
```

再在宿主机准备 `kube-prometheus-stack` 镜像，并生成待导入列表：

```bash
PROM_CHART_ROOT="/tmp/ob-kube-prometheus-stack-chart"
PROM_CHART="$PROM_CHART_ROOT/kube-prometheus-stack"
PROM_TMP="/tmp/ob-kube-prometheus-stack-rendered.yaml"
PROM_LOAD_LIST="/tmp/ob-kube-prometheus-stack-images.txt"

IMGS="$(awk '/^[[:space:]]*image:[[:space:]]*/{print $2}' "$PROM_TMP" | sed "s/[\"']//g" | sort -u)"
: > "$PROM_LOAD_LIST"

for IMG in $IMGS; do
  [ -z "$IMG" ] && continue

  CANON="$IMG"
  if [[ "$IMG" == */* ]]; then
    first="${IMG%%/*}"
    if [[ "$first" != *.* && "$first" != *:* && "$first" != "localhost" ]]; then
      CANON="docker.io/$IMG"
    fi
  else
    CANON="docker.io/library/$IMG"
  fi

  if ! docker image inspect "$CANON" >/dev/null 2>&1 && ! docker image inspect "$IMG" >/dev/null 2>&1; then
    if [[ "$CANON" == localhost/* ]]; then
      echo "ERROR: local image missing, please build it first: $CANON" >&2
      exit 1
    fi
    if [[ "$CANON" == docker.io/* ]]; then
      SRC="docker.m.daocloud.io/${CANON#docker.io/}"
    elif [[ "$CANON" == quay.io/* ]]; then
      SRC="quay.m.daocloud.io/${CANON#quay.io/}"
    else
      SRC="docker.gh-proxy.com/$CANON"
    fi
    docker pull "$SRC" || docker pull "$CANON" || docker pull "$IMG" || {
      echo "ERROR: pull failed: $CANON" >&2
      exit 1
    }
    docker tag "$SRC" "$CANON" 2>/dev/null || true
    docker tag "$SRC" "$IMG" 2>/dev/null || true
  fi

  docker tag "$IMG" "$CANON" 2>/dev/null || true
  printf '%s\n' "$CANON" >> "$PROM_LOAD_LIST"
done

sort -u "$PROM_LOAD_LIST" -o "$PROM_LOAD_LIST"
```

再把 `kube-prometheus-stack` 镜像统一导入 `kind-ob`：

```bash
PROM_LOAD_LIST="/tmp/ob-kube-prometheus-stack-images.txt"

while IFS= read -r IMG; do
  [ -z "$IMG" ] && continue
  kind load docker-image "$IMG" --name ob
done < "$PROM_LOAD_LIST"
```

执行安装并等待返回：

```bash
PROM_CHART_ROOT="/tmp/ob-kube-prometheus-stack-chart"
PROM_CHART="$PROM_CHART_ROOT/kube-prometheus-stack"

helm upgrade --install monitoring "$PROM_CHART" -n monitoring --create-namespace \
  -f benchmarks/online_boutique/manifests/monitoring/kube-prometheus-stack-values.yaml \
  --wait
```

确认监控组件状态：

```bash
kubectl -n monitoring get pods
kubectl -n monitoring get pods -w
```

重点确认这些 Pod 最终为 `Running`：
- `monitoring-kube-prometheus-operator`
- `monitoring-kube-state-metrics`
- `prometheus-monitoring-kube-prometheus-prometheus-0`
- `monitoring-grafana`

正常情况下，经过预拉取和导入后，这一步应该一次成功。

如果有 Pod 没有进入 `Running`，再检查最近事件：

```bash
kubectl -n monitoring get events --sort-by=.lastTimestamp | tail -n 30
```

让 Prometheus 抓取 Istio sidecar 指标：

```bash
kubectl apply -f benchmarks/online_boutique/manifests/monitoring/istio-proxy-podmonitor.yaml
```

确认 `PodMonitor` 已创建：

```bash
kubectl -n monitoring get podmonitor
```

---

### 7) 部署 Online Boutique

`Online Boutique` 业务清单中除了 `docker.io` 镜像，还包含 `us-central1-docker.pkg.dev` 上的镜像，所以这里同样保留“宿主机预拉取 + kind load”的方式，再部署业务。

先创建业务命名空间并开启 sidecar 注入：

```bash
kubectl create namespace ob || true
kubectl label namespace ob istio-injection=enabled --overwrite
```

先在宿主机准备清单里引用到的镜像，并生成待导入列表。如果宿主机里还没有，下面这段脚本会自动拉取并统一导入 kind：

```bash
OB_LOAD_LIST="/tmp/ob-online-boutique-images.txt"
FILES="benchmarks/online_boutique/microservices-demo/release/kubernetes-manifests.yaml"

IMGS="$(awk '/^[[:space:]]*image:[[:space:]]*/{print $2}' "$FILES" | sed "s/[\"']//g" | sort -u)"
: > "$OB_LOAD_LIST"

for IMG in $IMGS; do
  [ -z "$IMG" ] && continue

  CANON="$IMG"
  if [[ "$IMG" == */* ]]; then
    first="${IMG%%/*}"
    if [[ "$first" != *.* && "$first" != *:* ]]; then
      CANON="docker.io/$IMG"
    fi
  else
    CANON="docker.io/library/$IMG"
  fi

  if ! docker image inspect "$CANON" >/dev/null 2>&1 && ! docker image inspect "$IMG" >/dev/null 2>&1; then
    if [[ "$CANON" == docker.io/* ]]; then
      SRC="docker.m.daocloud.io/${CANON#docker.io/}"
    elif [[ "$CANON" == quay.io/* ]]; then
      SRC="quay.m.daocloud.io/${CANON#quay.io/}"
    else
      SRC="docker.gh-proxy.com/$CANON"
    fi
    docker pull "$SRC" || docker pull "$CANON" || docker pull "$IMG" || {
      echo "WARN: pull failed, skip: $CANON" >&2
      continue
    }
    docker tag "$SRC" "$CANON" 2>/dev/null || true
    docker tag "$SRC" "$IMG" 2>/dev/null || true
  fi

  docker tag "$IMG" "$CANON" 2>/dev/null || true
  printf '%s\n' "$CANON" >> "$OB_LOAD_LIST"
done

sort -u "$OB_LOAD_LIST" -o "$OB_LOAD_LIST"
```

再把这组业务镜像统一导入 `kind-ob`：

```bash
OB_LOAD_LIST="/tmp/ob-online-boutique-images.txt"

while IFS= read -r IMG; do
  [ -z "$IMG" ] && continue
  kind load docker-image "$IMG" --name ob
done < "$OB_LOAD_LIST"
```

镜像导入完成后，直接部署业务清单，然后观察启动进度：

```bash
kubectl -n ob apply -f benchmarks/online_boutique/microservices-demo/release/kubernetes-manifests.yaml
```

查看 Pod：

```bash
kubectl -n ob get pods
kubectl -n ob get pods -w
```

正常情况下，大多数 Pod 会显示为 `2/2`，表示：
- 业务容器
- `istio-proxy` sidecar

重点确认：
- `frontend`
- `loadgenerator`
- `checkoutservice`
- `productcatalogservice`
- `cartservice`
- `redis-cart`

如果有 Pod 没有进入 `Running`，再检查最近事件：

```bash
kubectl -n ob get events --sort-by=.lastTimestamp | tail -n 30
```

---

### 8) 验证应用是否跑通

查看 Service：

```bash
kubectl -n ob get svc
```

查看内置负载发生器日志：

```bash
kubectl -n ob logs deploy/loadgenerator --tail=80
```

如果日志里没有持续报 `frontend` 不可达，说明负载发生器基本正常。

如果你只是想快速确认页面能打开，可以在**单独终端**里启动前端直连端口转发，并保持这个命令不要退出。本文默认使用 `18080`，避免和本机常见服务端口冲突：

```bash
kubectl -n ob port-forward svc/frontend 18080:80
```

浏览器访问：

```text
http://localhost:18080
```

如果页面能打开，说明应用部署成功。

如果你后面要做 **Locust 压测**、并且 `frontend` 可能扩成多个副本，不要继续压 `svc/frontend`。  
`kubectl port-forward svc/frontend ...` 往往只会固定连到某一个后端 Pod，无法真实利用多个 `frontend` 副本。

建议改成下面这组 **Istio 入口**：

```bash
kubectl -n ob apply -f benchmarks/online_boutique/microservices-demo/istio-manifests/frontend-gateway.yaml
kubectl -n istio-system port-forward svc/istio-ingressgateway 18081:80
```

然后把浏览器或 Locust 的入口改成：

```text
http://localhost:18081
```

这个链路是：

```text
Locust / 浏览器 -> istio-ingressgateway -> frontend Service -> 多个 frontend Pod
```

这样即使本地还是 `port-forward`，流量也会先进入 Istio 网关，再由网关转给 `frontend` Service，能够真正分发到多个副本。

---

### 9) 访问 Prometheus 并验证指标

在**另一个单独终端**里把 Prometheus 端口转发出来，并保持这个命令不要退出。本文默认使用 `19090`，避免和本机代理常用端口冲突：

```bash
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 19090:9090
```

浏览器访问：

```text
http://localhost:19090
```

下面的内容是 **PromQL 查询**，要在 Prometheus 网页中的 `Expression` 输入框里执行，不要在终端里直接输入。

#### 9.1 先查基础资源指标

Pod CPU：

```promql
sum(rate(container_cpu_usage_seconds_total{namespace="ob", container!="", image!=""}[1m])) by (pod)
```

Pod 内存：

```promql
sum(container_memory_working_set_bytes{namespace="ob", container!="", image!=""}) by (pod)
```

Deployment ready replicas：

```promql
kube_deployment_status_replicas_available{namespace="ob"}
```

Deployment desired replicas：

```promql
kube_deployment_spec_replicas{namespace="ob"}
```

#### 9.2 再查 Istio 服务级指标

服务级 RPS：

```promql
sum(rate(istio_requests_total{reporter="destination", destination_workload_namespace="ob"}[1m]))
  by (destination_workload)
```

服务级 5xx RPS：

```promql
sum(rate(istio_requests_total{reporter="destination", destination_workload_namespace="ob", response_code=~"5.."}[1m]))
  by (destination_workload)
```

服务级平均延迟（秒）：

```promql
(
  sum(rate(istio_request_duration_milliseconds_sum{reporter="destination", destination_workload_namespace="ob"}[1m]))
    by (destination_workload)
)
/
(
  sum(rate(istio_request_duration_milliseconds_count{reporter="destination", destination_workload_namespace="ob"}[1m]))
    by (destination_workload)
)
/ 1000
```

边级 RPS：

```promql
sum(rate(istio_requests_total{reporter="destination", destination_workload_namespace="ob"}[1m]))
  by (source_workload, destination_workload)
```

如果这些查询都能返回数据，说明你的主采集链路已经打通。

---

#### 9.3 安装并开启 tracing（必做）

目标：让 Istio sidecar 产出的 trace 通过 OTLP 上报到集群内的 `OpenTelemetry Collector`，并在 `Jaeger` 中可查询（用于后续构造 `service_call_edge_minute` 等依赖传播数据）。

说明：为了让 `run_id / scenario_id` 写入 span tag，你后续的压测/注入请求必须携带 `x-run-id / x-scenario-id`（本仓库的 `loadgen-locust` 已自动注入）。

安装 `observability` 组件（Jaeger + OTel Collector）：

```bash
kubectl create ns observability || true

kubectl -n observability apply -f benchmarks/online_boutique/manifests/observability/jaeger-pvc.yaml
kubectl -n observability apply -f benchmarks/online_boutique/manifests/observability/jaeger.yaml
kubectl -n observability apply -f benchmarks/online_boutique/manifests/observability/otel-collector.yaml
```

开启 Istio tracing（采样率 1%，并把 `x-run-id / x-scenario-id` 写入 span tag）：

```bash
kubectl -n istio-system apply -f benchmarks/online_boutique/manifests/istio/telemetry-tracing.yaml
```

验证 Jaeger UI（保持命令不退出）：

```bash
kubectl -n observability port-forward svc/jaeger-query 16686:16686
```

浏览器打开：

```text
http://127.0.0.1:16686
```

---

### 10) 创建本次实验目录（run_id）

先确认你当前已经回到 `microservice-dataset` 仓库根目录，再执行下面命令。

例如，你的终端当前目录应为项目根目录：

```text
microservice-dataset
```

然后执行：

```bash
mkdir -p runs
run_id="$(date +%Y%m%d_%H%M%S)_ob"
mkdir -p "runs/$run_id"/{meta,prom,locust}
echo "run_id=$run_id"
```

记录环境快照：

```bash
{
  echo "## time"; date -Is
  echo; echo "## context"; kubectl config current-context
  echo; echo "## nodes"; kubectl get nodes -o wide
  echo; echo "## namespaces"; kubectl get ns
  echo; echo "## ob pods"; kubectl -n ob get pods -o wide
  echo; echo "## ob deploy"; kubectl -n ob get deploy
  echo; echo "## monitoring pods"; kubectl -n monitoring get pods -o wide
} > "runs/$run_id/meta/env.txt"
```

---

### 11) 准备第一版 PromQL 清单

先在本次实验目录下生成 PromQL 文件：

```bash
cat > "runs/$run_id/meta/promql-onlineboutique.json" <<'EOF'
{
  "service_rps_1m": "sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (destination_workload)",
  "service_out_rps_1m": "sum(rate(istio_requests_total{reporter=\"source\", source_workload_namespace=\"ob\"}[1m])) by (source_workload)",
  "service_5xx_rps_1m": "sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\", response_code=~\"5..\"}[1m])) by (destination_workload)",
  "service_error_ratio_1m": "((sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\", response_code=~\"5..\"}[1m])) by (destination_workload)) / (sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (destination_workload)))",
  "service_timeout_flag_rps_1m": "sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\", response_flags=~\"UT|UO|UF|UC|DC\"}[1m])) by (destination_workload)",
  "service_timeout_flag_ratio_1m": "((sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\", response_flags=~\"UT|UO|UF|UC|DC\"}[1m])) by (destination_workload)) / (sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (destination_workload)))",
  "service_latency_avg_1m": "((sum(rate(istio_request_duration_milliseconds_sum{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (destination_workload)) / (sum(rate(istio_request_duration_milliseconds_count{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (destination_workload))) / 1000",
  "service_latency_p95_1m": "histogram_quantile(0.95, sum(rate(istio_request_duration_milliseconds_bucket{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (destination_workload, le)) / 1000",
  "service_latency_p99_1m": "histogram_quantile(0.99, sum(rate(istio_request_duration_milliseconds_bucket{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (destination_workload, le)) / 1000",
  "edge_rps_1m": "sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (source_workload, destination_workload)",
  "edge_5xx_rps_1m": "sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\", response_code=~\"5..\"}[1m])) by (source_workload, destination_workload)",
  "edge_error_ratio_1m": "((sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\", response_code=~\"5..\"}[1m])) by (source_workload, destination_workload)) / (sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (source_workload, destination_workload)))",
  "edge_latency_avg_1m": "((sum(rate(istio_request_duration_milliseconds_sum{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (source_workload, destination_workload)) / (sum(rate(istio_request_duration_milliseconds_count{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (source_workload, destination_workload))) / 1000",
  "edge_latency_p95_1m": "histogram_quantile(0.95, sum(rate(istio_request_duration_milliseconds_bucket{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (source_workload, destination_workload, le)) / 1000",
  "edge_latency_p99_1m": "histogram_quantile(0.99, sum(rate(istio_request_duration_milliseconds_bucket{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (source_workload, destination_workload, le)) / 1000",
  "service_retry_rps_1m": "sum by (destination_workload) (label_replace(rate(envoy_cluster_upstream_rq_retry{namespace=\"ob\", cluster_name=~\"outbound\\\\\\\\|[0-9]+\\\\\\\\|\\\\\\\\|.*\\\\\\\\.ob\\\\\\\\.svc\\\\\\\\.cluster\\\\\\\\.local\"}[1m]), \"destination_workload\", \"$1\", \"cluster_name\", \"outbound\\\\\\\\|[0-9]+\\\\\\\\|\\\\\\\\|([^\\\\\\\\.]+)\\\\\\\\..*\"))",
  "service_cpu_usage_cores_1m": "sum by (destination_workload) (rate(container_cpu_usage_seconds_total{namespace=\"ob\", container!=\"\", image!=\"\"}[1m]) * on(namespace, pod) group_left(replicaset) label_replace(kube_pod_owner{namespace=\"ob\", owner_kind=\"ReplicaSet\"}, \"replicaset\", \"$1\", \"owner_name\", \"(.*)\") * on(namespace, replicaset) group_left(destination_workload) label_replace(kube_replicaset_owner{namespace=\"ob\", owner_kind=\"Deployment\"}, \"destination_workload\", \"$1\", \"owner_name\", \"(.*)\"))",
  "service_cpu_limit_cores": "sum by (destination_workload) (kube_pod_container_resource_limits{namespace=\"ob\", resource=\"cpu\", unit=\"core\"} * on(namespace, pod) group_left(replicaset) label_replace(kube_pod_owner{namespace=\"ob\", owner_kind=\"ReplicaSet\"}, \"replicaset\", \"$1\", \"owner_name\", \"(.*)\") * on(namespace, replicaset) group_left(destination_workload) label_replace(kube_replicaset_owner{namespace=\"ob\", owner_kind=\"Deployment\"}, \"destination_workload\", \"$1\", \"owner_name\", \"(.*)\"))",
  "service_cpu_request_cores": "sum by (destination_workload) (kube_pod_container_resource_requests{namespace=\"ob\", resource=\"cpu\", unit=\"core\"} * on(namespace, pod) group_left(replicaset) label_replace(kube_pod_owner{namespace=\"ob\", owner_kind=\"ReplicaSet\"}, \"replicaset\", \"$1\", \"owner_name\", \"(.*)\") * on(namespace, replicaset) group_left(destination_workload) label_replace(kube_replicaset_owner{namespace=\"ob\", owner_kind=\"Deployment\"}, \"destination_workload\", \"$1\", \"owner_name\", \"(.*)\"))",
  "service_mem_working_set_bytes": "sum by (destination_workload) (container_memory_working_set_bytes{namespace=\"ob\", container!=\"\", image!=\"\"} * on(namespace, pod) group_left(replicaset) label_replace(kube_pod_owner{namespace=\"ob\", owner_kind=\"ReplicaSet\"}, \"replicaset\", \"$1\", \"owner_name\", \"(.*)\") * on(namespace, replicaset) group_left(destination_workload) label_replace(kube_replicaset_owner{namespace=\"ob\", owner_kind=\"Deployment\"}, \"destination_workload\", \"$1\", \"owner_name\", \"(.*)\"))",
  "service_mem_limit_bytes": "sum by (destination_workload) (kube_pod_container_resource_limits{namespace=\"ob\", resource=\"memory\", unit=\"byte\"} * on(namespace, pod) group_left(replicaset) label_replace(kube_pod_owner{namespace=\"ob\", owner_kind=\"ReplicaSet\"}, \"replicaset\", \"$1\", \"owner_name\", \"(.*)\") * on(namespace, replicaset) group_left(destination_workload) label_replace(kube_replicaset_owner{namespace=\"ob\", owner_kind=\"Deployment\"}, \"destination_workload\", \"$1\", \"owner_name\", \"(.*)\"))",
  "service_mem_request_bytes": "sum by (destination_workload) (kube_pod_container_resource_requests{namespace=\"ob\", resource=\"memory\", unit=\"byte\"} * on(namespace, pod) group_left(replicaset) label_replace(kube_pod_owner{namespace=\"ob\", owner_kind=\"ReplicaSet\"}, \"replicaset\", \"$1\", \"owner_name\", \"(.*)\") * on(namespace, replicaset) group_left(destination_workload) label_replace(kube_replicaset_owner{namespace=\"ob\", owner_kind=\"Deployment\"}, \"destination_workload\", \"$1\", \"owner_name\", \"(.*)\"))",
  "service_cpu_util_vs_request_1m": "(sum by (destination_workload) (rate(container_cpu_usage_seconds_total{namespace=\"ob\", container!=\"\", image!=\"\"}[1m]) * on(namespace, pod) group_left(replicaset) label_replace(kube_pod_owner{namespace=\"ob\", owner_kind=\"ReplicaSet\"}, \"replicaset\", \"$1\", \"owner_name\", \"(.*)\") * on(namespace, replicaset) group_left(destination_workload) label_replace(kube_replicaset_owner{namespace=\"ob\", owner_kind=\"Deployment\"}, \"destination_workload\", \"$1\", \"owner_name\", \"(.*)\"))) / (sum by (destination_workload) (kube_pod_container_resource_requests{namespace=\"ob\", resource=\"cpu\", unit=\"core\"} * on(namespace, pod) group_left(replicaset) label_replace(kube_pod_owner{namespace=\"ob\", owner_kind=\"ReplicaSet\"}, \"replicaset\", \"$1\", \"owner_name\", \"(.*)\") * on(namespace, replicaset) group_left(destination_workload) label_replace(kube_replicaset_owner{namespace=\"ob\", owner_kind=\"Deployment\"}, \"destination_workload\", \"$1\", \"owner_name\", \"(.*)\")))",
  "pod_cpu_1m": "sum(rate(container_cpu_usage_seconds_total{namespace=\"ob\", container!=\"\", image!=\"\"}[1m])) by (pod)",
  "pod_cpu_limit_cores": "sum(kube_pod_container_resource_limits{namespace=\"ob\", resource=\"cpu\", unit=\"core\"}) by (pod)",
  "pod_cpu_request_cores": "sum(kube_pod_container_resource_requests{namespace=\"ob\", resource=\"cpu\", unit=\"core\"}) by (pod)",
  "pod_cpu_throttling_ratio_1m": "(sum(rate(container_cpu_cfs_throttled_seconds_total{namespace=\"ob\", container!=\"\", image!=\"\"}[1m])) by (pod)) / (sum(rate(container_cpu_usage_seconds_total{namespace=\"ob\", container!=\"\", image!=\"\"}[1m])) by (pod))",
  "pod_mem_working_set_bytes": "sum(container_memory_working_set_bytes{namespace=\"ob\", container!=\"\", image!=\"\"}) by (pod)",
  "pod_mem_limit_bytes": "sum(kube_pod_container_resource_limits{namespace=\"ob\", resource=\"memory\", unit=\"byte\"}) by (pod)",
  "pod_mem_request_bytes": "sum(kube_pod_container_resource_requests{namespace=\"ob\", resource=\"memory\", unit=\"byte\"}) by (pod)",
  "replicas_ready_1m": "kube_deployment_status_replicas_available{namespace=\"ob\"}",
  "replicas_desired_1m": "kube_deployment_spec_replicas{namespace=\"ob\"}",
  "service_rps_per_ready_replica_1m": "(sum(rate(istio_requests_total{reporter=\"destination\", destination_workload_namespace=\"ob\"}[1m])) by (destination_workload)) / on(destination_workload) label_replace(kube_deployment_status_replicas_available{namespace=\"ob\"}, \"destination_workload\", \"$1\", \"deployment\", \"(.*)\")",
  "service_cpu_per_ready_replica_1m": "(sum by (destination_workload) (rate(container_cpu_usage_seconds_total{namespace=\"ob\", container!=\"\", image!=\"\"}[1m]) * on(namespace, pod) group_left(replicaset) label_replace(kube_pod_owner{namespace=\"ob\", owner_kind=\"ReplicaSet\"}, \"replicaset\", \"$1\", \"owner_name\", \"(.*)\") * on(namespace, replicaset) group_left(destination_workload) label_replace(kube_replicaset_owner{namespace=\"ob\", owner_kind=\"Deployment\"}, \"destination_workload\", \"$1\", \"owner_name\", \"(.*)\"))) / on(destination_workload) label_replace(kube_deployment_status_replicas_available{namespace=\"ob\"}, \"destination_workload\", \"$1\", \"deployment\", \"(.*)\")",
  "pod_restarts_1m": "sum(increase(kube_pod_container_status_restarts_total{namespace=\"ob\"}[1m])) by (pod)",
  "hpa_current_replicas": "kube_horizontalpodautoscaler_status_current_replicas{namespace=\"ob\"}",
  "hpa_desired_replicas": "kube_horizontalpodautoscaler_status_desired_replicas{namespace=\"ob\"}",
  "hpa_spec_min_replicas": "kube_horizontalpodautoscaler_spec_min_replicas{namespace=\"ob\"}",
  "hpa_spec_max_replicas": "kube_horizontalpodautoscaler_spec_max_replicas{namespace=\"ob\"}",
  "node_cpu_util_1m": "1 - avg(rate(node_cpu_seconds_total{mode=\"idle\"}[1m])) by (instance)",
  "node_load1": "avg(node_load1) by (instance)",
  "node_mem_available_ratio": "avg(node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) by (instance)"
}
EOF
```

说明：

- `service_*` 资源指标通过 `pod -> ReplicaSet -> Deployment` 关系把 Pod 指标聚合回 `destination_workload`，更适合做 `service` 级 CPU 预测。
- `service_cpu_util_vs_request_1m` 更接近 HPA 常用的 CPU 利用率视角，后续做 HPA 学习时很有用。
- `hpa_*` 指标在你没有创建 HPA 时会返回空结果，这是正常现象；等你后面增加 HPA run 后再一起导出即可。

---

### 12) 导出第一版指标

先确定时间窗：

```bash
END="$(date +%s)"
START="$((END-30*60))"
STEP=60

echo "START=$START"
echo "END=$END"
echo "STEP=$STEP"
```

先在本次实验目录下生成一个简单的导出脚本：

```bash
cat > "runs/$run_id/meta/export_prometheus_range.py" <<'EOF'
#!/usr/bin/env python3
import argparse
import json
import os
import time
import requests


def load_queries(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prom", required=True)
    parser.add_argument("--queries", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    queries = load_queries(args.queries)
    manifest = {
        "prom": args.prom,
        "queries_file": os.path.abspath(args.queries),
        "start": args.start,
        "end": args.end,
        "step": args.step,
        "exported_at": int(time.time()),
        "queries": queries,
        "results": {},
    }

    session = requests.Session()
    session.trust_env = False

    for name, query in queries.items():
        response = session.get(
            args.prom.rstrip("/") + "/api/v1/query_range",
            params={
                "query": query,
                "start": args.start,
                "end": args.end,
                "step": args.step,
            },
            timeout=args.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        target = os.path.join(args.out, f"{name}.json")
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        manifest["results"][name] = {
            "file": os.path.abspath(target),
            "series_count": len(payload.get("data", {}).get("result", [])),
            "status": payload.get("status", "unknown"),
        }

    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
EOF

chmod +x "runs/$run_id/meta/export_prometheus_range.py"
```

导出前，确认 Prometheus 的 `port-forward` 仍然在运行，并且本地访问地址仍是 `http://localhost:19090`。

然后导出：

```bash
python "runs/$run_id/meta/export_prometheus_range.py" \
  --prom "http://127.0.0.1:19090" \
  --queries "runs/$run_id/meta/promql-onlineboutique.json" \
  --start "$START" --end "$END" --step "$STEP" \
  --out "runs/$run_id/prom"
```

导出完成后查看结果：

```bash
ls "runs/$run_id/prom"
```

你应该看到类似这些文件：
- `service_rps_1m.json`
- `service_5xx_rps_1m.json`
- `service_latency_avg_1m.json`
- `edge_rps_1m.json`
- `pod_cpu_1m.json`
- `pod_mem_working_set_bytes.json`
- `replicas_ready_1m.json`
- `manifest.json`

---

### 13) 当前阶段先不要做什么

在最小闭环跑通前，先不要着急做下面这些事情：
- 不要先引入 HPA
- 不要马上改 `loadgenerator` 逻辑
- 不要先追求周期负载、burst、正弦负载
- 不要一开始把 tracing 采样率开得很高（先用 1% 验证流程与口径）

推荐顺序是：
- 先跑通 `fixed_replicas`
- 先把 `service_rps / cpu / mem / replicas / latency` 采出来
- 再进入更复杂的负载形状和自动扩容实验

---

### 14) 下一步建议

当这篇文档的最小闭环跑通后，下一步建议是：

1. 先继续使用 `fixed_replicas`，不要急着上 HPA
2. 先把低 / 中 / 高三档恒定负载跑出来
3. 再增加阶梯负载 / 周期负载 / burst 负载
4. 给每一轮实验增加 `scenario_id`
5. 把导出的 JSON 整理成统一的表格式数据集
6. 最后再增加 `with_hpa` 扩展实验组

如果你准备进入“正式采集/可复现”的阶段，建议你把真实流量（NASA/ClarkNet）转换为 Locust schedule 后再长跑：

- 生成 10s schedule：`pipelines/traffic/README.md`（末尾有最短命令）
- 运行 schedule：`benchmarks/online_boutique/loadgen-locust/run_traffic_schedule_10s.sh`

数据落盘的“字段口径与中间层表结构”请以主文档为准：

- `docs/微服务负载预测数据整理方案.md`

