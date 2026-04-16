# SkillForge

> **Agent Skill 增强系统** — 让 Agent 在执行每个任务前先自我诊断能力缺口，再决定是否增强、回退或自创建 skill。

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Tests: 51/51](https://img.shields.io/badge/tests-51%2F51%20passing-brightgreen.svg)]()

---

## 为什么需要 SkillForge？

当前 Agent 的默认模式是"拿到任务就做"——不管自己擅不擅长。

SkillForge 在任务执行前插入一个**诊断-决策-闭环**循环：

```
任务 → [Phase 1] Gap 分析 → [Phase 2] 决策增强 → [Phase 3] 执行 → [Phase 4] 评估 + 记忆
```

学术依据：KnowSelf (ACL 2025) · CapBound (清华&蚂蚁) · Reflexion (NeurIPS 2023) · MAR (Ozer et al.)

---

## 快速开始（5 分钟）

### 方式 A：Cursor Rule（推荐，零代码）

复制 `cursor-rule/skillforge.mdc` 到你的项目 `.cursor/rules/`，Cursor Agent 重启后自动生效。

每次任务开头会显示诊断标签：

```
[SF | tool+30,know+20 → Gap≈35 | force-enhance | recommend code-expert, need confirm]
```

### 方式 B：Python 包

```bash
pip install pyyaml pydantic typer rich httpx
pip install -e .
```

```python
from skillforge import SkillForgeOrchestrator

orch = SkillForgeOrchestrator(
    registry_path="skillforge-registry.yaml",
    memory_dir="memory",
    reflexion_enabled=True,   # Stage 4: 自动加载历史反思
)

# Phase 1-3: 预判 + 决策 + 增强 prompt 构建
result = orch.run(
    task_description="帮我写一个异步爬虫",
    llm_response=llm_analysis_json,  # Phase 1 LLM 分析结果
    user_decision="auto",
)

print(result.phase3_context)  # 增强后的 prompt，交给 LLM 执行

# Phase 4: 执行完成后评估 + 记忆闭环
closed = orch.evaluate_and_close(result, actual_score=75)
```

### 方式 C：CLI 工具

```bash
# 任务预判
skillforge analyze "帮我实现用户权限系统"

# 完整循环（含 Phase 4 评分）
skillforge run "优化这段 SQL 查询" --rating 4

# 查看 Skill Registry
skillforge list-skills

# 查看记忆索引 Dashboard
skillforge dashboard
```

---

## 核心机制

### Gap 五态判断

每个任务从 6 个维度估算 Agent 能力缺口（`prec` / `crea` / `know` / `tool` / `reas` / `spd`），取加权最大值得出总 Gap：

| Gap 范围 | 状态 | Agent 行为 |
|----------|------|-----------|
| Gap < 5 | `independent` | 直接执行，无提示 |
| 5 ≤ Gap < 15 | `light-hint` | 执行，结束时提示优化空间 |
| 15 ≤ Gap < 30 | `suggest` | 询问是否启用 skill 增强 |
| 30 ≤ Gap < 50 | `force-enhance` | 暂停，要求用户确认增强方案 |
| Gap ≥ 50 | `out-of-scope` | 坦白能力边界，不执行 |

### 三层记忆索引（Progressive Disclosure）

| 层 | 文件 | Token 开销 | 读取时机 |
|----|------|-----------|---------|
| L0 | `capability-index.yaml` | < 500 tokens | Phase 1 前，自动校准预判 |
| L1 | `trajectories/{type}/` | < 1K tokens | Phase 2 决策前 |
| L2 | `reflections.md` | < 2K tokens | Phase 4 后，Reflexion 闭环 |

### Stage 3 可选增强

- **MAR**（多角色辩论评估）：三个 Critic + Judge，解决自评确认偏误，单次 LLM 调用完成
- **向量语义检索**：ChromaDB + Mock 双实现，Phase 2 混合召回（关键词 + 语义）

---

## 文件结构

```
SKILLFORGE/
├── cursor-rule/
│   └── skillforge.mdc          # Cursor Rule 接入文件（直接复制到 .cursor/rules/）
├── src/skillforge/
│   ├── engine.py               # SkillForgeOrchestrator（Phase 1-4 串联）
│   ├── evaluator.py            # Phase 4 质量评估 + L2 反思写入
│   ├── reflexion.py            # Stage 4: L2 反思加载器（ReflectionLoader）
│   ├── mar.py                  # Stage 3: MAR 多角色辩论（MARCoordinator）
│   ├── vector_search.py        # Stage 3: 混合语义检索（HybridSkillMatcher）
│   ├── decider.py              # 五态 Gap 决策器
│   ├── indexer.py              # L0 Capability Index 管理
│   ├── registry.py             # Skill Registry 读写
│   ├── executor.py             # Phase 3 增强执行（含 SandboxRunner）
│   ├── tracing.py              # Phase Timing 观测
│   ├── models.py               # Pydantic 数据模型
│   ├── config.py               # 配置加载（含 Stage3Config / Stage4Config）
│   ├── forger.py               # 自创建 Skill 生成器
│   └── cli.py                  # CLI 工具
├── tests/
│   ├── test_skillforge.py      # 核心端到端测试（8 个）
│   ├── test_mar.py             # MAR 模块（9 个）
│   ├── test_vector_search.py   # 向量检索（10 个）
│   ├── test_reflexion.py       # Reflexion（13 个）
│   └── test_stage4_integration.py  # Stage 4 集成（11 个）
├── memory/
│   ├── reflections.md          # L2 反思日志（append-only）
│   ├── trajectories/           # L1 执行轨迹
│   └── self-made/              # 自创建 skill 草稿
├── skillforge-registry.yaml    # Skill 注册表（5 个种子 skill）
├── config.yaml                 # 全局配置（含 Stage 3/4 可选开关）
└── pyproject.toml              # 包配置（pip install -e .）
```

---

## 配置

```yaml
# config.yaml

# 五态 Gap 阈值
gap_thresholds:
  independent_max: 5
  light_hints_max: 15
  suggest_max: 30
  force_max: 50

# Stage 3: MAR 多角色辩论（可选，默认关闭）
stage3:
  mar:
    enabled: false
    provider: "llm-only"   # "cursor" | "claude-code" | "codex" | "llm-only"

  # Stage 3: 向量语义检索（可选，默认关闭）
  vector_search:
    enabled: false
    provider: "mock"       # "chroma" | "mock"

# Stage 4: Reflexion 记忆闭环（可选，默认关闭）
stage4:
  reflexion:
    enabled: false
    max_entries: 5          # Phase 1 最多注入多少条历史反思
    min_delta_threshold: -5.0  # 只加载大于此幅度的失败反思
```

---

## 测试

```bash
# 安装依赖
pip install pyyaml pydantic

# 运行全部测试（51 个）
python3 tests/test_skillforge.py
python3 tests/test_mar.py
python3 tests/test_vector_search.py
python3 tests/test_reflexion.py
python3 tests/test_stage4_integration.py
```

---

## Skill Registry 扩展

在 `skillforge-registry.yaml` 中添加 entry：

```yaml
skills:
  - skill_id: my-skill
    name: My Custom Skill
    domain: [programming]
    task_types: [code_generation]
    capability_gains:
      precision: 15
      tool_usage: 10
    quality_tier: L2
    trigger_keywords: [写代码, implement, build]
    description: 专业代码生成 skill
    path: skills/my-skill/SKILL.md
```

---

## 开发进度

| Stage | 内容 | 状态 |
|-------|------|------|
| Stage 0 | pyproject.toml · CLI · 包结构 | ✅ |
| Stage 1 | Phase 1-4 串联 · L0/L1/L2 记忆 · capability 校准 | ✅ |
| Stage 2 | observability tracing · sandbox 执行 · CONTRIBUTING | ✅ |
| Stage 3 | MAR 多角色辩论 · 向量语义检索 · 混合召回 | ✅ |
| Stage 4 | Reflexion Memory 重试闭环 · 历史反思注入 | ✅ |
| Stage 5 | CapBound 白盒预判（hidden state 分类） | 规划中 |

---

## 许可证

[Apache 2.0](LICENSE)
