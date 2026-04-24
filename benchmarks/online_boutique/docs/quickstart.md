# 一步一步：部署 Online Boutique + Istio + Prometheus（部署与可观测验证）

---

### 1) 本文采用的部署策略

`Online Boutique` 使用一个**独立的 kind 集群**进行部署与可观测验证。

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

本文使用 3 节点 kind 集群：
- 1 个 control-plane
- 2 个 worker

本文直接使用仓库内的配置文件：

```bash
sed -n '1,120p' benchmarks/online_boutique/kind-config.yaml
```

`kind-config.yaml` 是 kind 集群的配置文件，用于声明节点数量/角色、挂载目录（`extraMounts`）、宿主机端口映射（`extraPortMappings`）以及镜像站等创建参数，保证环境可复现。

由于 `kind-config.yaml` 使用了 `extraMounts` 将宿主机目录“映射/挂载”到 kind 的节点容器内部（节点在 kind 里其实是 Docker 容器），创建集群前请先确保宿主机目录存在。这里的 `.local/kind-ob-volumes` 主要用于提供 kind 集群里的本地持久化卷目录（例如 local-path-provisioner 使用的 PV 数据）。

在 `microservice-dataset` 仓库根目录执行：

```bash
mkdir -p .local/kind-ob-volumes
```

创建集群（集群名为 `ob`，对应 kubectl context 为 `kind-ob`）：

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

---

### 5) 安装 Istio

用 Istio 的 `demo` 安装配置把控制面与入口网关等组件装进集群（用于 sidecar 注入与服务级观测）。

```bash
istioctl install --set profile=demo -y
```

安装完成后确认：

```bash
kubectl get ns
kubectl -n istio-system get pods
kubectl -n istio-system get svc
```

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

让 Prometheus 抓取 Istio sidecar 和 Jaeger 指标：

```bash
kubectl apply -f benchmarks/online_boutique/manifests/monitoring/istio-proxy-podmonitor.yaml
kubectl apply -f benchmarks/online_boutique/manifests/monitoring/jaeger-podmonitor.yaml
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

（可选）查看内置负载发生器日志：

```bash
kubectl -n ob logs deploy/loadgenerator --tail=80
```

说明：部署清单里 `loadgenerator` 默认是 `0`，因此这里可能没有日志/没有持续请求是正常的。若你想用它做一次短暂冒烟验证，可先在第 9 节按提示临时 scale 到 `1`，再回来看日志。

如果你只是想快速确认页面能打开，可以在**单独终端**里启动前端直连端口转发，并保持这个命令不要退出。本文默认使用 `18080`，避免和本机常见服务端口冲突：

```bash
kubectl -n ob port-forward svc/frontend 18080:80
```

浏览器访问：

```text
http://localhost:18080
```

如果页面能打开，说明应用部署成功。

为后续的 **Locust 注入** 准备入口，本文采用固定的 **Istio 入口**（宿主机 `18081`）。`18080` 仅用于验证页面可用。

```bash
kubectl -n ob apply -f benchmarks/online_boutique/microservices-demo/istio-manifests/frontend-gateway.yaml
```

把 `istio-ingressgateway` 的 HTTP nodePort 固定成 `30081`：

```bash
kubectl -n istio-system patch svc istio-ingressgateway --type='json' \
  -p='[{"op":"replace","path":"/spec/ports/1/nodePort","value":30081}]'
```

由于 `kind-config.yaml` 已把宿主机 `18081` 映射到 kind 节点的 `30081`，这里不再需要 `kubectl port-forward`。然后把浏览器或 Locust 的入口改成：

```text
http://localhost:18081
```

这个链路是：

```text
Locust / 浏览器 -> localhost:18081 -> kind:30081 -> istio-ingressgateway -> frontend Service -> 多个 frontend Pod
```

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

#### 9.1 最小验证（第一次部署建议先跑这 3 条）

由于部署清单里 `loadgenerator` 默认是 `0`，此时没有流量，服务级 RPS 会是 `0`，平均延迟会是 `NaN`（0/0）。第一次验证先临时打一点流量：

```bash
kubectl -n ob scale deploy/loadgenerator --replicas=1
```

1) Deployment ready replicas（确认 kube-state-metrics 正常）：

```promql
kube_deployment_status_replicas_available{namespace="ob"}
```

2) 服务级 RPS（确认 Istio 请求指标正常）：

```promql
sum(rate(istio_requests_total{reporter="destination", destination_workload_namespace="ob"}[1m]))
  by (destination_workload)
```

3) 服务级平均延迟（秒）（确认 duration 指标正常）：

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
/
1000
```

如果以上 3 条都能返回数据，说明 Prometheus+Istio 的主采集链路已经打通，可以继续后续步骤。

验证完成后建议缩回 `0`，避免污染后续正式注入数据：

```bash
kubectl -n ob scale deploy/loadgenerator --replicas=0
```

#### 9.2 可选查询（排障/深入检查时再用）

Pod CPU：

```promql
sum(rate(container_cpu_usage_seconds_total{namespace="ob", container!="", image!=""}[1m])) by (pod)
```

Pod 内存：

```promql
sum(container_memory_working_set_bytes{namespace="ob", container!="", image!=""}) by (pod)
```

Deployment desired replicas：

```promql
kube_deployment_spec_replicas{namespace="ob"}
```

服务级 5xx RPS：

```promql
sum(rate(istio_requests_total{reporter="destination", destination_workload_namespace="ob", response_code=~"5.."}[1m]))
  by (destination_workload)
```

边级 RPS：

```promql
sum(rate(istio_requests_total{reporter="destination", destination_workload_namespace="ob"}[1m]))
  by (source_workload, destination_workload)
```

---

#### 9.3 安装并开启 tracing

目标：让 Istio sidecar 产出的 trace 通过 OTLP 上报到集群内的 `OpenTelemetry Collector`，并在 `Jaeger` 中可查询。

安装 `observability` 组件（Jaeger + OTel Collector）：

```bash
kubectl create ns observability || true

kubectl -n observability apply -f benchmarks/online_boutique/manifests/observability/jaeger-pvc.yaml
kubectl -n observability apply -f benchmarks/online_boutique/manifests/observability/jaeger.yaml
kubectl -n observability apply -f benchmarks/online_boutique/manifests/observability/otel-collector.yaml
```

开启 Istio tracing（采样率 1%）：

```bash
kubectl -n istio-system apply -f benchmarks/online_boutique/manifests/istio/telemetry-tracing.yaml
```

验证 Jaeger UI（在单独的终端保持命令不退出）：

```bash
kubectl -n observability port-forward svc/jaeger-query 16686:16686
```

浏览器打开：

```text
http://127.0.0.1:16686
```
