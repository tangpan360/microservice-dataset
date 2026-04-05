# Train-Ticket 负载注入方案

这个目录提供一套独立、简洁、可开源的 Train-Ticket 负载注入实现。

它的目标不是堆积一批可执行脚本，而是提供一套清晰的分层结构：

- 用动作层表达最小业务动作
- 用场景层表达业务顺序和参数策略
- 用 `Locust` 负责强度、时间线和场景混合比例

这样做更适合：

- 复现实验
- 做混合业务场景注入
- 与 Prometheus 指标采集配合
- 为后续的负载预测与容量分析提供稳定输入

## 当前实现范围

当前版本已经包含：

- 核心运行上下文、HTTP 客户端、登录认证
- 查询、订单、售后、管理观察等最小动作层
- 场景注册表与标准场景集合
- YAML 混合配置解析
- `Locust` 适配层
- 单场景本地 dry-run 入口

当前场景目录采用中等规模定稿方式，按四类组织：

- 浏览类：稳定背景流量
- 支撑类：订单刷新、联系人、餐食浏览等常用轻操作
- 交易类：下单、支付、取消、改签、托运等状态变更链路
- 观察类：少量后台只读流量

当前不包含：

- 图形化控制台
- 面向多 benchmark 的通用抽象
- 自动生成全量服务覆盖矩阵

## 目录说明

- `src/tt_injector/core/`：HTTP、认证、上下文、基础模型
- `src/tt_injector/actions/`：动作层，直接描述最小业务调用
- `src/tt_injector/scenarios/`：场景层，组合动作形成业务流程
- `src/tt_injector/registry/`：场景注册表，统一维护场景 ID 与入口
- `src/tt_injector/config/`：混合配置模型与 YAML 解析
- `src/tt_injector/adapters/locust/`：Locust task 与负载 shape
- `src/tt_injector/cli/`：本地调试入口
- `configs/mix/`：混合注入配置示例
- `docs/`：中文方案文档

## 最小环境变量

- `TT_BASE_URL`：Train-Ticket 入口地址，默认 `http://127.0.0.1:8080`
- `TT_USERNAME` / `TT_PASSWORD`：普通用户账号
- `TT_ADMIN_USERNAME` / `TT_ADMIN_PASSWORD`：管理员账号
- `TT_TIMEOUT`：单请求超时秒数
- `TT_MIX_CONFIG`：混合配置文件路径

## 最小运行方式

安装：

```bash
cd benchmarks/trainticket/load_injector
python -m pip install -e ".[locust]"
```

单场景 dry-run：

```bash
TT_BASE_URL="http://localhost:8080" \
python -m tt_injector.cli.dryrun browseBasic
```

`Locust` 运行：

```bash
TT_BASE_URL="http://localhost:8080" \
TT_MIX_CONFIG="configs/mix/steady.yaml" \
locust -f "src/tt_injector/adapters/locust/locustfile.py" --headless
```

## 推荐阅读顺序

- `docs/方案设计.md`
- `docs/场景说明.md`
- `docs/配置说明.md`
- `docs/运行与采集.md`
