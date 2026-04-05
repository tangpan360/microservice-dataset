### 一步一步：部署 Train‑Ticket 0.0.4 + Istio + Prometheus 并采集指标（10 分钟快速验证）

目标：跑通一次最小闭环（部署 → 打点流量 → 导出指标 → 落盘到 `runs/<run_id>/`）。

---

### 0) 代码位置

Train‑Ticket 0.0.4 的业务清单在：`benchmarks/trainticket/train-ticket/deployment/quickstart-k8s-deployment/`。

本文的业务部署以这套 `0.0.4` 清单和对应预构建镜像为准。

---

### 1) 前置条件

- **OS**：Ubuntu 20.04/22.04（其他 Linux 也可以）
- **网络**：能直接拉取 Docker 镜像
- **权限**：有 sudo
- **本地源码构建（可选）**：如果你后续要本地重编 Java 服务做 canary，请额外准备 `OpenJDK 8`、`javac`、`Maven 3.6+`

```bash
java -version
javac -version
mvn -version
```

如果只是按本文部署现成镜像，这三项不是必须。

#### 1.1 一个很重要的版本说明

本次部署以 `quickstart-k8s-deployment` 和对应的 `0.0.4` 预构建镜像作为可运行基线，不混入仓库后续版本中的新服务、新接口或新配置。

本流程默认使用以下修正版镜像：
- `tangpan360/ts-ui-dashboard:0.0.4`
- `tangpan360/ts-food-service:0.0.4`

其余服务仍按 `quickstart-k8s-deployment` 中的镜像配置拉取并部署。

---

### 2) 安装基础工具

这一节安装的不是“Train‑Ticket 业务代码”，而是搭建实验环境的工具链。你可以把它理解为：
- Docker：提供容器运行时（kind 会把 K8s 节点跑成 Docker 容器）
- kind：在本机用 Docker 快速创建一个临时 Kubernetes 集群（实验结束可整集群删除）
- kubectl：Kubernetes 的命令行客户端（用来 apply 清单、看 pod、端口转发等）
- Helm：Kubernetes 的“包管理器”（用来安装 kube-prometheus-stack）
- istioctl：Istio 的安装/卸载/诊断工具（用来装 service mesh，从而获得服务级指标）

```bash
sudo apt update
sudo apt install -y curl ca-certificates gnupg jq git
```

#### 2.1 安装 Docker

在这个项目里，Docker 的定位是“底座”：它负责运行 kind 的节点容器，也负责你后续拉取/缓存镜像。

先创建一个目录，用来保存 apt 源的签名密钥文件。

```bash
sudo install -m 0755 -d /etc/apt/keyrings
```

然后导入 Docker 官方源的签名密钥，并设置成所有用户可读。

```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
```

接着把 Docker 官方 apt 源写入 sources list，并刷新 apt 索引。

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo ${VERSION_CODENAME}) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
```

安装 Docker Engine 与 compose 插件。

```bash
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

启动 Docker 的 socket（Docker 默认使用 systemd socket activation），再启动 Docker 服务。

```bash
sudo systemctl start docker.socket
sudo systemctl start docker
```

把当前用户加入 `docker` 用户组，然后刷新当前 shell 的组权限（这样后面运行 `docker` 不需要 `sudo`）。

```bash
sudo usermod -aG docker $USER
newgrp docker
```

最后验证 Docker 与 compose 是否可用。

```bash
docker version
docker compose version
```

#### 2.2 安装 kind / kubectl / helm

接下来安装 3 个和 Kubernetes 直接相关的工具：
- kind：创建本机 K8s 集群
- kubectl：操作集群（部署、查看状态、端口转发）
- helm：安装监控栈（Prometheus/Grafana 等）

下载 kind 二进制并安装到 `/usr/local/bin`。

```bash
curl -L -o kind https://kind.sigs.k8s.io/dl/v0.23.0/kind-linux-amd64
chmod +x kind
sudo mv kind /usr/local/bin/kind
kind version
```

下载 kubectl 并安装到 `/usr/local/bin`。

```bash
curl -L -o kubectl "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/kubectl
kubectl version --client=true
```

下载 Helm 并安装到 `/usr/local/bin`。

```bash
curl -L -o helm.tgz https://get.helm.sh/helm-v3.15.4-linux-amd64.tar.gz
tar -xzf helm.tgz
sudo mv linux-amd64/helm /usr/local/bin/helm
rm -rf linux-amd64 helm.tgz
helm version
```

#### 2.3 安装 istioctl

Istio 的定位是“可观测层”：它在服务之间注入 sidecar，从而让你能在 Prometheus 里稳定拿到服务级的 RPS、延迟分位数、错误率等指标（这类指标对做负载预测/扩缩容非常关键）。

下载并解压 Istio（包含 `istioctl`）。

```bash
ISTIO_VERSION="1.23.0"
curl -L https://istio.io/downloadIstio | ISTIO_VERSION="$ISTIO_VERSION" sh -
```

把 `istioctl` 安装到 `/usr/local/bin`，然后验证版本信息。

```bash
sudo install -m 0755 "istio-$ISTIO_VERSION/bin/istioctl" /usr/local/bin/istioctl
istioctl version --remote=false
```

如果你希望目录保持干净，现在就可以删除解压出来的 `istio-$ISTIO_VERSION/`（不影响后续使用 `/usr/local/bin/istioctl`）。

```bash
rm -rf "istio-$ISTIO_VERSION"
```

---

### 3) clone 本仓库

```bash
# 在本仓库根目录执行后续命令
pwd
```

---

### 4) 创建本次实验目录（run_id）

```bash
mkdir -p runs
run_id="$(date +%Y%m%d_%H%M%S)_quick10m"
mkdir -p "runs/$run_id"/{meta,loadgen,prom}
echo "run_id=$run_id"
```

---

### 5) 记录本次操作

```bash
script -af "runs/$run_id/terminal.log"
```

全部完成后输入 `exit` 结束录制。

---

### 6) 部署：kind + Istio + Prometheus + Train‑Ticket

从这一节开始你在做的事情是：先把“实验环境”搭起来（K8s + service mesh + 监控），再把业务系统 Train‑Ticket 部署进去。这样后面你打流量时，Prometheus 才能持续采集并导出数据集。

#### 6.1 创建 kind 集群

kind 的集群是临时的、可删除的。它的价值是“复现成本低”：你不需要准备真实的多节点 K8s。

```bash
kind create cluster --name tt
```

```bash
kubectl cluster-info
```

稍等 30–90 秒，等节点就绪后再查看（刚创建完出现 `NotReady` 是正常的）。

```bash
kubectl get nodes -o wide
```

如果你看到 `error: current-context is not set`，用 kind 自动创建的 context 再试一次。

```bash
kubectl cluster-info --context kind-tt
```

#### 6.2 安装 Istio

Istio 安装完成后，后续部署到开启注入的 namespace（例如 `trainticket`）时，Pod 会多一个 `istio-proxy` sidecar，从而产出 `istio_requests_total`、`istio_request_duration_*` 等指标。

先准备并导入 `Istio` 镜像，再安装。建议用两个终端同时进行：
- 终端 A：执行预加载和安装
- 终端 B：观察 Pod 与 events

终端 A，先在宿主机准备 `Istio` 镜像：

```bash
ISTIO_VERSION="1.23.0"

docker pull "docker.m.daocloud.io/istio/pilot:${ISTIO_VERSION}"
docker pull "docker.m.daocloud.io/istio/proxyv2:${ISTIO_VERSION}"

docker tag "docker.m.daocloud.io/istio/pilot:${ISTIO_VERSION}" "docker.io/istio/pilot:${ISTIO_VERSION}"
docker tag "docker.m.daocloud.io/istio/proxyv2:${ISTIO_VERSION}" "docker.io/istio/proxyv2:${ISTIO_VERSION}"
```

终端 A，再把 `Istio` 镜像导入 kind（`tt`）：

```bash
ISTIO_VERSION="1.23.0"

kind load docker-image "docker.io/istio/pilot:${ISTIO_VERSION}" --name tt
kind load docker-image "docker.io/istio/proxyv2:${ISTIO_VERSION}" --name tt
```

终端 A：安装 Istio，等待返回。

```bash
istioctl install --set profile=default -y
```

终端 B：观察直到 `istiod` 和 `istio-ingressgateway` 都 `Running 1/1`。

```bash
kubectl -n istio-system get pods -o wide
kubectl -n istio-system get events --sort-by=.lastTimestamp | tail -n 30
```

#### 6.3 安装 Prometheus（kube-prometheus-stack）

Prometheus 的定位是“指标数据库”。我们后续用它的 `query_range` API 把一段时间窗内的指标导出到 `runs/<run_id>/prom/`，形成数据集原始材料。

建议用两个终端同时进行。

先准备并导入 `kube-prometheus-stack` 镜像，再安装。

终端 A，先添加 Helm 仓库并更新索引：

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

终端 A，下载本次固定使用的 chart 到本地目录：

```bash
PROM_CHART_VERSION="82.17.0"
PROM_CHART_ROOT="/tmp/tt-kube-prometheus-stack-chart"

rm -rf "$PROM_CHART_ROOT"
mkdir -p "$PROM_CHART_ROOT"

helm pull prometheus-community/kube-prometheus-stack \
  --version "$PROM_CHART_VERSION" \
  --untar \
  --untardir "$PROM_CHART_ROOT"
```

终端 A，再基于本地 chart 渲染 manifest：

```bash
PROM_CHART_ROOT="/tmp/tt-kube-prometheus-stack-chart"
PROM_CHART="$PROM_CHART_ROOT/kube-prometheus-stack"
PROM_TMP="/tmp/tt-kube-prometheus-stack-rendered.yaml"

helm template monitoring "$PROM_CHART" -n monitoring > "$PROM_TMP"
```

终端 A，再在宿主机准备 `kube-prometheus-stack` 镜像，并生成待导入列表：

```bash
PROM_CHART_ROOT="/tmp/tt-kube-prometheus-stack-chart"
PROM_CHART="$PROM_CHART_ROOT/kube-prometheus-stack"
PROM_TMP="/tmp/tt-kube-prometheus-stack-rendered.yaml"
PROM_LOAD_LIST="/tmp/tt-kube-prometheus-stack-images.txt"

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

终端 A，再把 `kube-prometheus-stack` 镜像导入 kind（`tt`）：

```bash
PROM_LOAD_LIST="/tmp/tt-kube-prometheus-stack-images.txt"

while IFS= read -r IMG; do
  [ -z "$IMG" ] && continue
  kind load docker-image "$IMG" --name tt
done < "$PROM_LOAD_LIST"
```

终端 A，执行安装命令并等待返回（不要 `Ctrl+C`）：

```bash
PROM_CHART_ROOT="/tmp/tt-kube-prometheus-stack-chart"
PROM_CHART="$PROM_CHART_ROOT/kube-prometheus-stack"

helm upgrade --install monitoring "$PROM_CHART" -n monitoring --create-namespace --wait
```

终端 B，检查是否正常就绪：

```bash
kubectl -n monitoring get pods -o wide
kubectl -n monitoring get pods | grep -E 'ErrImagePull|ImagePullBackOff|Init:' || true
kubectl -n monitoring get events --sort-by=.lastTimestamp | tail -n 30
```

如果这里看到 `prometheus-monitoring-kube-prometheus-prometheus-0` 或 `alertmanager-monitoring-kube-prometheus-alertmanager-0` 卡在 `ErrImagePull` / `ImagePullBackOff`，并且事件里出现类似下面的报错：

```text
Failed to pull image "quay.io/prometheus-operator/prometheus-config-reloader:v0.89.0"
```

可以手工预拉并导入这个镜像，然后再让 Pod 重建：

```bash
docker pull quay.m.daocloud.io/prometheus-operator/prometheus-config-reloader:v0.89.0
docker tag quay.m.daocloud.io/prometheus-operator/prometheus-config-reloader:v0.89.0 quay.io/prometheus-operator/prometheus-config-reloader:v0.89.0
kind load docker-image quay.io/prometheus-operator/prometheus-config-reloader:v0.89.0 --name tt

kubectl -n monitoring delete pod alertmanager-monitoring-kube-prometheus-alertmanager-0
kubectl -n monitoring delete pod prometheus-monitoring-kube-prometheus-prometheus-0
kubectl -n monitoring get pods -o wide
```

#### 6.4 让 Prometheus 抓取 Istio sidecar 指标

这一步决定你后续是否能在 Prometheus 里查到 `istio_requests_total`、`istio_request_duration_*` 等 Istio 指标。

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: istio-proxy
  namespace: monitoring
  labels:
    release: monitoring
spec:
  namespaceSelector:
    any: true
  selector:
    matchExpressions:
    - key: security.istio.io/tlsMode
      operator: Exists
  podMetricsEndpoints:
  - port: http-envoy-prom
    path: /stats/prometheus
    interval: 30s
EOF
```

可选：确认 `PodMonitor` 已创建。

```bash
kubectl -n monitoring get podmonitor
```

注意：这一步只是让 Prometheus “知道要抓哪些 sidecar”。真正验证 `istio_requests_total` 等指标是否有数据，一般要等你完成 `6.5` 部署业务并在第 7 节产生流量后，再在第 8 节转发 Prometheus 并查询。

#### 6.5 部署 Train‑Ticket

先按清单把 `Train‑Ticket` 镜像准备好并导入 kind，再部署业务。

```bash
kubectl create ns trainticket || true
kubectl label ns trainticket istio-injection=enabled --overwrite
```

`quickstart-k8s-deployment/` 目录中的 YAML 可直接用于本文流程。其中 `ts-ui-dashboard` 和 `ts-food-service` 使用 Docker Hub 上的修正版镜像 `tangpan360/ts-ui-dashboard:0.0.4` 与 `tangpan360/ts-food-service:0.0.4`。

先在宿主机准备清单里引用到的镜像，并生成待导入列表。如果宿主机里还没有，下面这段脚本会自动拉取并统一导入 kind：

```bash
TT_LOAD_LIST="/tmp/tt-train-ticket-images.txt"
DIR="benchmarks/trainticket/train-ticket/deployment/quickstart-k8s-deployment"
FILES="$DIR/quickstart-ts-deployment-part1.yml $DIR/quickstart-ts-deployment-part2.yml $DIR/quickstart-ts-deployment-part3.yml"

IMGS="$(awk '/^[[:space:]]*image:[[:space:]]*/{print $2}' $FILES | sed "s/[\"']//g" | sort -u)"
: > "$TT_LOAD_LIST"

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
  printf '%s\n' "$CANON" >> "$TT_LOAD_LIST"
done

sort -u "$TT_LOAD_LIST" -o "$TT_LOAD_LIST"
```

再把这组业务镜像统一导入 kind（`tt`）：

```bash
TT_LOAD_LIST="/tmp/tt-train-ticket-images.txt"

while IFS= read -r IMG; do
  [ -z "$IMG" ] && continue
  kind load docker-image "$IMG" --name tt
done < "$TT_LOAD_LIST"

rm -f "$TT_LOAD_LIST"
```

说明：
- `tangpan360/ts-ui-dashboard:0.0.4` 和 `tangpan360/ts-food-service:0.0.4` 会像其他业务镜像一样被拉取并导入 kind
- 这段预加载脚本会先把镜像准备到宿主机，再由第二段循环统一导入 `kind`

镜像导入完成后，直接 apply 当前目录中的业务清单，然后观察启动进度。

```bash
DIR="benchmarks/trainticket/train-ticket/deployment/quickstart-k8s-deployment"

kubectl -n trainticket apply -f "$DIR/quickstart-ts-deployment-part1.yml"
kubectl -n trainticket apply -f "$DIR/quickstart-ts-deployment-part2.yml"
kubectl -n trainticket apply -f "$DIR/quickstart-ts-deployment-part3.yml"

kubectl -n trainticket get pods -o wide
kubectl -n trainticket get deploy
```

#### 6.5 部署后立即验证动作链路

部署完成后，建议立刻做一次动作级回归验证：

```bash
cd "benchmarks/trainticket/load_injector"

NODE_IP="$(docker inspect tt-control-plane --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')"
TT_BASE_URL="http://$NODE_IP:32677" python -m tt_injector.cli.check_actions
```

如果你只想单独验证 `query_food`，重点看输出里是否出现：
- `"action": "query_food"`
- `"ok": true`
- `"msg":"Get All Food Success"`

---

### 7) 产生一点流量（10 分钟）

终端 A：先直接使用 `ts-ui-dashboard` 的 `NodePort 32677`。如果你的宿主机不能直接访问 kind 节点 NodePort，再退回到 `port-forward`。

```bash
kubectl -n trainticket get svc ts-ui-dashboard
```

很多 Linux 主机上的 kind `NodePort` 并不会直接绑定到 `127.0.0.1`。更稳妥的做法是先拿到 kind 节点容器 IP，再用 `http://<NODE_IP>:32677` 访问：

```bash
NODE_IP="$(docker inspect tt-control-plane --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')"
echo "$NODE_IP"
```

然后在浏览器中打开：

```bash
echo "http://$NODE_IP:32677"
```

如果你的宿主机仍然不能直接访问 kind 节点 NodePort，再退回到 `port-forward`：

```bash
kubectl -n trainticket port-forward svc/ts-ui-dashboard 8080:8080
```

终端 B：循环调用一个接口（不登录）

```bash
BASE_URL="http://$NODE_IP:32677"
# 如果你用了 port-forward，就把上面这一行改成：BASE_URL="http://127.0.0.1:8080"

END=$((SECONDS+600))
while [ $SECONDS -lt $END ]; do
  curl -sS "$BASE_URL/api/v1/travelservice/trips/left" \
    -H "Content-Type: application/json" \
    -d '{"departureTime":"2026-03-29","startingPlace":"Shang Hai","endPlace":"Su Zhou"}' >/dev/null || true
  sleep 0.2
done
```

快速自检：如果首页能打开，直接抓一段 HTML 看是否出现 `TrainTicket Admin`。

```bash
curl -sS "$BASE_URL/" | sed -n '1,20p'
```

---

### 8) 导出 Prometheus 指标（10 分钟窗口）

终端 C：转发 Prometheus 到本机。默认建议优先使用 `:19090`，避免和本机已有代理/开发服务冲突；如果你确认 `:9090` 空闲，也可以继续使用 `:9090`。

```bash
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 19090:9090
```

终端 D：用 `query_range` 导出一个指标（示例：服务级 RPS）

```bash
END="$(date +%s)"
START="$((END-10*60))"
STEP=60

curl -sG 'http://localhost:19090/api/v1/query_range' \
  --data-urlencode 'query=sum(rate(container_cpu_usage_seconds_total{namespace="trainticket",container!="",image!=""}[1m])) by (pod)' \
  --data-urlencode "start=$START" \
  --data-urlencode "end=$END" \
  --data-urlencode "step=$STEP" \
  > "runs/$run_id/prom/pod_cpu_usage_cores_1m.json"
```

快速自检：

```bash
curl -sS http://127.0.0.1:19090/-/healthy
curl -sS 'http://127.0.0.1:19090/api/v1/targets' | jq '.data.activeTargets | length'
```

如果你在 `127.0.0.1:9090` 上看到了类似 `{"hello":"mihomo"}` 这类与 Prometheus 无关的返回，说明本机 `9090` 已经被其他程序占用；这种情况下继续使用 `19090`，不要再用 `9090`。

---

### 9) 验收：这轮 run_id 是否跑通

你至少应该看到：
- `runs/<run_id>/terminal.log`：有
- `runs/<run_id>/prom/*.json`：有（至少 1 个指标）
- `kubectl -n trainticket get pods`：业务 Pod 为 `2/2 Running`
- `kubectl -n trainticket get deploy`：业务 Deployment 为 `1/1 Available`
- `curl -sS "$BASE_URL/" | sed -n '1,20p'`：返回的首页 HTML 中可见 `TrainTicket Admin`
- `curl -sS http://127.0.0.1:19090/-/healthy`：返回 `Prometheus Server is Healthy.`

结束 `script`：

```bash
exit
```

---

### 10) 完整卸载与清理（恢复到“未部署/未采集”之前）

#### 10.1 删除 kind 集群（会删除集群内所有内容）

删除 kind 集群（会删除集群内所有资源）。

```bash
kind delete cluster --name tt
```

#### 10.2 卸载本机安装的二进制（kind/kubectl/helm/istioctl）

删除本流程安装到 `/usr/local/bin` 的工具。

```bash
sudo rm -f /usr/local/bin/kind
sudo rm -f /usr/local/bin/kubectl
sudo rm -f /usr/local/bin/helm
sudo rm -f /usr/local/bin/istioctl
```

如果你还保留了解压目录，也可以删掉它（版本号以你实际为准）。

```bash
rm -rf istio-1.23.0
```

#### 10.3 清理本次任务相关镜像（推荐）

如果你希望验证“镜像是否能够重新拉取 / 文档是否能在无缓存条件下重跑”，建议在保留 Docker 的前提下，先清掉本次任务相关镜像，再重新执行本文流程。

先查看当前本机还保留了哪些相关镜像：

```bash
docker images --format '{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}' | \
  grep -E 'codewisdom|ts-ui-dashboard|ts-food-service|jaegertracing|istio/|prometheus|grafana|mongo|mysql' || true
```

删除本次任务相关镜像：

```bash
docker rmi tangpan360/ts-ui-dashboard:0.0.4 2>/dev/null || true
docker rmi tangpan360/ts-food-service:0.0.4 2>/dev/null || true
docker rmi jaegertracing/all-in-one:1.76.0 2>/dev/null || true
docker rmi jaegertracing/all-in-one:latest 2>/dev/null || true
docker rmi docker.m.daocloud.io/jaegertracing/all-in-one:latest 2>/dev/null || true
docker rmi mongo:4.4 2>/dev/null || true
docker rmi docker.m.daocloud.io/library/mongo:4.4 2>/dev/null || true
docker rmi mongo:latest 2>/dev/null || true
docker rmi mysql:5.6.35 2>/dev/null || true
docker rmi istio/pilot:1.23.0 2>/dev/null || true
docker rmi docker.m.daocloud.io/istio/pilot:1.23.0 2>/dev/null || true
docker rmi istio/proxyv2:1.23.0 2>/dev/null || true
docker rmi docker.m.daocloud.io/istio/proxyv2:1.23.0 2>/dev/null || true

docker images --format '{{.Repository}}:{{.Tag}}' | \
  grep -E '^(codewisdom|docker\.io/codewisdom)/ts-.*:0\.0\.4$' | \
  xargs -r docker rmi

docker images --format '{{.Repository}}:{{.Tag}}' | \
  grep -E 'prometheus|alertmanager|grafana|prometheus-operator|k8s-sidecar|node-exporter|kube-state-metrics' | \
  xargs -r docker rmi
```

清理完成后，再次检查：

```bash
docker images --format '{{.Repository}}:{{.Tag}}' | \
  grep -E 'codewisdom|ts-ui-dashboard|ts-food-service|jaegertracing|istio/|prometheus|grafana|mongo|mysql' || true
```

如果你还想单独验证几个关键镜像能否重新获取，可以先手工执行：

```bash
docker pull openresty/openresty:trusty
docker pull docker.m.daocloud.io/istio/pilot:1.23.0
docker pull docker.m.daocloud.io/istio/proxyv2:1.23.0
docker pull docker.io/codewisdom/ts-travel-service:0.0.4
docker pull jaegertracing/all-in-one:1.76.0
docker pull mongo:4.4
docker pull mysql:5.6.35
```

#### 10.4 卸载 Docker（docker-ce）

卸载 docker-ce 相关软件包。

```bash
sudo apt remove -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo apt autoremove -y
```

如果你想把镜像/容器/卷也一并清空，可以删除数据目录。

```bash
sudo rm -rf /var/lib/docker
sudo rm -rf /var/lib/containerd
```

#### 10.5 移除 Docker 官方 apt 源（可选）

删除 Docker apt 源配置与密钥文件，然后刷新 apt 索引。

```bash
sudo rm -f /etc/apt/sources.list.d/docker.list
sudo rm -f /etc/apt/keyrings/docker.gpg
sudo apt update
```

#### 10.6 清理本仓库的实验产物（runs）

删除本地实验产物目录。

```bash
rm -rf runs/
```
