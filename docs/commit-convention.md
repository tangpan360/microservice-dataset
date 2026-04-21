# Commit 规范

## 目标
为当前仓库建立一套长期可执行、便于回溯、适合数据集构建与部署演进的提交规范。

## 核心原则
- 一次 `commit` 只表达一类变化。
- 形成阶段性结果后再提交，不要攒成超大提交。
- 文档、部署配置、脚本修复、数据处理，尽量分开提交。
- 提交信息优先说明“为什么做”，不要只写“update”或“fix bugs”。
- 提交应当能被后续自己快速看懂，而不依赖聊天记录。

## 推荐粒度
- 完成一个清晰里程碑时提交一次。
- 小范围连续修改同一目标时，可合并为一次提交。
- 还在探索、没有稳定结论时，先不要提交。

## 提交格式
统一使用：

```text
<type>: <简短主题>
```

## type 定义
- `docs`: 文档、说明、流程、规范
- `feat`: 新增功能或新增能力
- `fix`: 修复错误、兼容性问题、部署问题
- `refactor`: 重构，不改变外部行为
- `chore`: 基础整理、目录调整、非功能性维护
- `test`: 测试、验证脚本、测试说明
- `data`: 数据集结构、采集流程、样本处理、元数据更新

## 主题写法
- 用小写英文短句。
- 控制在一句话内。
- 尽量具体，不要空泛。
- 推荐使用动词开头，如 `add`、`fix`、`document`、`initialize`、`align`。

## 不推荐写法
- `update`
- `misc`
- `tmp`
- `fix bugs`
- `change files`

## 适用于本仓库的常见场景
- `docs: add v1 migration notes`
- `docs: add v1 minimal deployment checklist`
- `chore: initialize trainticket v1 workspace`
- `fix: align auto-query scripts with v1 endpoints`
- `fix: correct nacos and mysql startup flow`
- `test: add first-round deployment verification steps`
- `data: define run directory layout and metadata fields`

## 建议提交节奏
1. 目录骨架和迁移基线，提交一次。
2. 最小闭环部署文档完成，提交一次。
3. 基础依赖与核心服务可启动，提交一次。
4. 第一版链路跑通，提交一次。
5. 脚本验证与测试说明稳定后，再提交一次。

## 当前仓库的执行建议
- 现在适合先做一次文档初始化提交。
- 后续等最小闭环真正跑通后，再做下一次提交。
