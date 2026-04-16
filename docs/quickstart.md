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
skillforge list-skills
# 应输出 5 个种子 skill 的表格
```

---

## CLI 使用

### 任务预判（Phase 1）

```bash
skillforge analyze "帮我实现一个用户权限系统"
```

输出示例：
```
╭─ Phase 1 预判结果  [suggest] ──────────────────────────────╮
│ 任务: 帮我实现一个用户权限系统                               │
│ 任务类型: code_generation                                    │
│ 预估分数: 78 / 100                                          │
│ Gap: 22 分                                                  │
╰─────────────────────────────────────────────────────────────╯

候选 Skill：
  code-expert-skill   +15分   效果 82%   local
  research-skill      +8分    效果 75%   local
```

### 完整循环（Phase 1-4）

```bash
# 自动决策
skillforge run "写一个 Python 异步爬虫"

# 跳过 skill 增强直接执行
skillforge run "写一个 Python 异步爬虫" --skip-skill

# 执行后评分（触发 Phase 4 记忆闭环）
skillforge run "写一个 Python 异步爬虫" --rating 4
```

### 查看记忆 Dashboard

```bash
skillforge dashboard
```

输出 L0 索引统计（各 task_type 的执行次数、avg_delta、趋势）和 Phase Timing 统计。

### 搜索 Skill

```bash
skillforge search "python"
skillforge list-skills --domain programming
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

# Phase 1 LLM 分析结果（由你的 LLM 调用 PHASE1_PROMPT_TEMPLATE 后得到）
llm_analysis = json.dumps({
    "predicted_score": 72,
    "total_gap": 28,
    "gaps": {"precision": 20, "tool_usage": 15},
    "capability_dimensions": {"gaps": {"precision": 20, "tool_usage": 15}},
    "task_types": ["code_generation"],
    "task_difficulty": 85,
    "recommended_skill_types": ["code"],
})

# Phase 1-3
result = orch.run(
    task_description="帮我写一个 Python 异步爬虫，带错误处理和重试",
    llm_response=llm_analysis,
    user_decision="auto",  # "auto" | "skip" | "enhance"
)

# Phase 3 输出的增强 prompt — 交给你的 LLM 执行
print(result.phase3_context)
print(f"Gap 状态: {result.decision.action}")
print(f"推荐 Skill: {[r.skill.name for r in result.decision.options]}")

# (执行完任务后) Phase 4 评估 + 记忆闭环
closed = orch.evaluate_and_close(
    result,
    actual_score=75,        # 实际执行分（0-100）
    user_rating=4,          # 用户评分（1-5）
)
print(f"Delta: {closed.phase4.actual_score - result.trajectory.phase1.predicted_score:+.0f}")
print(f"L0 索引已更新: {closed.index_updated}")
```

### 启用 Stage 4 Reflexion

```python
orch = SkillForgeOrchestrator(
    registry_path="skillforge-registry.yaml",
    memory_dir="memory",
    reflexion_enabled=True,   # 自动加载 L2 历史反思注入 Phase 1
)
```

### 启用 Stage 3 MAR + 向量检索

```python
orch = SkillForgeOrchestrator(
    registry_path="skillforge-registry.yaml",
    memory_dir="memory",
    mar_enabled=True,             # MAR 多角色辩论评估
    vector_search_enabled=True,   # 混合语义检索（需要 pip install chromadb）
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
├── skillforge-registry.yaml   # Skill 注册表，可自由添加
├── config.yaml                # 全局配置（阈值、Stage 3/4 开关）
└── memory/
    ├── capability-index.yaml  # L0 索引，自动更新
    ├── reflections.md         # L2 反思日志
    └── trajectories/          # L1 执行轨迹（按 task_type 分目录）
```

`memory/` 目录下的文件由 SkillForge 自动维护，不需要手动编辑。
