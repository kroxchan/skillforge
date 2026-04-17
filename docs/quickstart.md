# 快速开始

---

## 环境要求

- Python 3.9+
- 依赖：`pyyaml` · `pydantic` · `typer` · `rich` · `httpx`

---

## 安装

```bash
git clone https://github.com/kroxchan/skillforge.git
cd skillforge
pip install -e .
```

验证安装：

```bash
sf --help           # 显示所有 CLI 命令
sf demand-queue     # 显示当前 L0 索引各 task_type 的累积进度
```

> v0.2.6 起 Registry **默认为空**（涌现式生长），skill 由 Forger 在真实工作中 `count ≥ 5` 时自动生成草稿。`sf list-skills` 返回空是**正常行为**。

---

## CLI 使用

SkillForge CLI 支持两种入口：`sf`（简写）和 `skillforge`（完整名），功能完全等价。

### 任务预判（Phase 1）

```bash
sf analyze "帮我实现一个用户权限系统"
```

输出示例：
```
╭─ Phase 1 预判结果  [suggest] ──────────────────────────────╮
│ 任务: 帮我实现一个用户权限系统                               │
│ 任务类型: code_generation                                   │
│ 预估分数: 78 / 100                                          │
│ Gap: 22 分                                                  │
╰─────────────────────────────────────────────────────────────╯
```

> Registry 空时（当前默认状态），Phase 2 不会显示候选 skill。Forger 会在同类任务累积 ≥ 5 次时自动生成草稿到 `memory/self-made/`。

### 完整循环（Phase 1-4）

```bash
# Phase 1-3 自动决策
sf run "写一个 Python 异步爬虫"

# 跳过 skill 增强直接执行
sf run "写一个 Python 异步爬虫" --skip-skill
```

### Phase 4 闭环：`sf update-l0`（推荐入口）

Cursor mdc 规则在 Phase 4 会自动调用此命令；Python API 批量场景也可以直接调用：

```bash
sf update-l0 \
    --task-type refactoring \
    --rating 3 \
    --task-desc "修复 mdc 规则 + evaluator 死代码分支" \
    --predicted 88
```

命令内部完成：
- `count += 1`, EMA 更新 `avg_delta`, 重算 `gap_adjustment`
- 在目标 task_type 条目尾部**追加审计注释**（保留所有已有注释）
- 更新 `_meta` 的 last_task_id / total_executed / updated_at
- 原子写回（tmp → rename）
- 若 `rating=1`，追加反思模板骨架到 `reflections.md`

**评分约定**（与 mdc 规则一致）：

| rating | delta | 触发条件 |
|--------|-------|---------|
| 1 | -40 | 用户明确不满 / 要求重做 / 指出错误 |
| 3 | 0 | 默认基线：符合预期、灰色反馈、无反馈 |
| 5 | +40 | 用户明确惊喜（极罕见） |

### 旧版评估入口：`sf eval`（兼容保留）

```bash
sf eval --task-id abc123 --rating 3 --task-type code_generation --predicted 70
```

与 `update-l0` 的区别：`eval` 使用 `IndexManager.save()` 做全量重写（会丢失 yaml 中的注释），适合独立 Python 环境中的批量评估；**Cursor 对话场景优先用 `update-l0`**。

### 查看记忆 Dashboard

```bash
sf dashboard
```

### 搜索 Skill

```bash
sf search "python"                     # 同时扫描 Registry + memory/self-made/ 草稿
sf list-skills --domain programming    # 列出已入库 skill
```

### 涌现式 Skill 生长（v0.2.6+）

```bash
sf demand-queue                         # 查看各 task_type 距 Forger 阈值多远
sf forge                                # 查看哪些 task_type 可触发
sf forge --task-type my_type --force    # 强制生成草稿（调试用）
sf push memory/self-made/xxx-draft.md   # 审核草稿后入库到 Registry
```

---

## Python API

### 最简用法

```python
import json
from skillforge import SkillForgeOrchestrator

orch = SkillForgeOrchestrator(
    registry_path="skillforge-registry.yaml",
    memory_dir="memory",
)

llm_analysis = json.dumps({
    "predicted_score": 72,
    "total_gap": 28,
    "gaps": {"precision": 20, "reasoning": 8},
    "capability_dimensions": {"gaps": {"precision": 20, "reasoning": 8}},
    "task_types": ["code_generation"],
    "task_difficulty": 85,
    "recommended_skill_types": ["code"],
})

result = orch.run(
    task_description="帮我写一个 Python 异步爬虫",
    llm_response=llm_analysis,
    user_decision="auto",
)

print(result.phase3_context)
print(f"Gap 状态: {result.decision.action}")

closed = orch.evaluate_and_close(
    result,
    actual_score=72,
    user_rating=3,
)
print(f"Delta: {(3-3)*20:+d}")
print(f"L0 索引已更新: {closed.index_updated}")
```

### 直接调用 update_l0_file helper

```python
from pathlib import Path
from skillforge.indexer import update_l0_file

summary = update_l0_file(
    index_path=Path("memory/capability-index.yaml"),
    task_type="refactoring",
    rating=3,
    task_desc="修复若干一致性问题",
    predicted=90,
)
print(summary)
```

### 启用 Stage 4 Reflexion

```python
orch = SkillForgeOrchestrator(
    registry_path="skillforge-registry.yaml",
    memory_dir="memory",
    reflexion_enabled=True,
)
```

### 启用 Stage 3 MAR + 向量检索

```python
orch = SkillForgeOrchestrator(
    registry_path="skillforge-registry.yaml",
    memory_dir="memory",
    mar_enabled=True,
    vector_search_enabled=True,
)
```

详见 → [高级功能](advanced.md)

### 获取 Phase 1 Prompt

```python
from skillforge import SkillForgeEngine, PHASE1_PROMPT_TEMPLATE

engine = SkillForgeEngine()
prompt = engine.build_prompt("帮我写一个 Python 异步爬虫")
# 把 prompt 发给你的 LLM，得到 JSON 格式的分析结果
# 再用 engine.parse_analysis(llm_response) 解析
```

---

## 文件结构说明

```
skillforge/
├── skillforge-registry.yaml    # Skill 注册表（v0.2.6 起默认空，涌现式生长）
├── config.yaml                 # 全局配置（阈值、Stage 3/4 开关）
└── memory/
    ├── capability-index.yaml   # L0 索引，sf update-l0 自动更新（保留注释）
    ├── reflections.md          # L2 反思日志（rating=1 时自动追加模板）
    ├── self-made/              # Forger 自动生成的 SKILL.md 草稿（v0.2.6+）
    └── trajectories/           # L1 执行轨迹（仅 Python 引擎批量场景产出）
```

`memory/` 目录由 SkillForge 自动维护，不建议手动编辑 `capability-index.yaml`。
如需手工标注，放在对应 task_type 条目下方即可——`sf update-l0` 会保留所有注释。
