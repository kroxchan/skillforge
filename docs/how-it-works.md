# 工作原理

> SkillForge 的完整执行循环：Phase 1 → 2 → 3 → 4 → 记忆

---

## 整体架构

```
用户任务
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 1: Gap 分析                                            │
│  · 6 个维度估算缺口（prec/crea/know/tool/reas/spd）           │
│  · L0 历史数据校准预判分                                       │
│  · Stage 4: 自动加载 L2 同类历史反思                           │
│  · 输出 SF 诊断标签                                           │
└───────────────────────────┬──────────────────────────────────┘
                            │ Gap 五态
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 2: 决策增强                                            │
│  · independent → 直接进 Phase 3                               │
│  · light-hint  → 直接进 Phase 3，结束时提示                    │
│  · suggest     → 推荐 skill，询问用户                          │
│  · force-enhance → 暂停，要求用户确认                          │
│  · out-of-scope → 拒绝，建议拆解任务                          │
│  · Stage 3: HybridSkillMatcher（关键词 + 向量双路召回）        │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 3: 增强执行                                            │
│  · 读取 skill SKILL.md 内容注入 context                       │
│  · 执行任务，记录工具调用和错误                                 │
│  · SandboxRunner: 代码类任务自动验证                           │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 4: 评估 + 记忆闭环                                     │
│  · 加权计算实际分 A（用户评分 60% / LLM 自评 30% / 工具 10%）  │
│  · Delta = A - S                                              │
│  · Delta < -5 → 生成反思，写入 L2                             │
│  · Stage 3: MAR 多角色辩论（可选）                             │
│  · L1 轨迹写入 · L0 索引移动平均更新                           │
└──────────────────────────────────────────────────────────────┘
```

---

## Phase 1：Gap 分析

### 六维度评估

| 维度 | 简写 | 什么情况下 Gap 高 |
|------|------|-----------------|
| Precision | `prec` | 幻觉风险高、数据必须准确、API/版本细节易错 |
| Creativity | `crea` | 需要原创内容、独特方案 |
| Domain Knowledge | `know` | 专业壁垒高、细分领域、要求最新信息 |
| Tool Usage | `tool` | 需要调用真实工具、读写文件、访问外部 API |
| Reasoning | `reas` | 多步骤依赖、复杂逻辑链、数学推导 |
| Speed | `spd` | 有严格时间/资源限制 |

**Gap 总分**：取各维度缺口的加权最大值（最大缺口维度权重 60%，其余均分 40%），避免单维度极端值失真。

### L0 历史校准

L0 `capability-index.yaml` 记录每个 task_type 的历史执行统计：

```yaml
task_type_index:
  code_generation:
    count: 23
    avg_delta: -3.2      # 实际分 - 预估分，移动平均
    trend: improving
    gap_adjustment: +5   # Phase 1 预判修正值
```

Phase 1 读取 `gap_adjustment`，自动修正预判：
- 如果历史上 code_generation 类任务总是低估（avg_delta 为负），下次自动调高预判分
- `avg_delta = 0.2 × current_delta + 0.8 × avg_delta`（指数移动平均，α=0.2）

### SF 诊断标签

每次任务开头强制输出：

```
[SF | {non-zero dims} → Gap≈{score} | {state} | {action}]
```

例：
```
[SF | no gap → Gap≈3 | independent | direct execution]
[SF | tool+30,know+20 → Gap≈35 | force-enhance | recommend code-expert, need confirm]
```

---

## Phase 2：决策增强

### 五态行为

| 状态 | 行为 |
|------|------|
| `independent` | 直接进入 Phase 3，不打断用户 |
| `light-hint` | 直接执行，Phase 4 结束时轻提示"有优化空间" |
| `suggest` | 展示候选 skill 及预期提升分，询问用户是否启用 |
| `force-enhance` | 暂停，列出 Top-3 skill 方案，等用户确认后才继续 |
| `out-of-scope` | 坦白能力边界，建议拆解任务或换模型，不执行 |

### Skill 匹配

从 Registry 里找覆盖当前 Gap 维度的 skill：

```
综合得分 = 任务类型匹配权重(×20) + 缺口覆盖分 + 历史效果(×15)
```

---

## Phase 4：评估与记忆闭环

### 加权实际分

```
A = (用户评分 × 0.6 + LLM 自评 × 0.3 + 工具验证 × 0.1)
                / (实际参与的权重之和)
```

### 反思触发条件

- `Delta = A - S < -5`：触发反思，写入 L2
- `outcome == "patch_needed"`：触发完整分析

### L2 反思格式

```markdown
## [task_id] code_generation  @ 2026-04-16 14:30
**任务**: 写一个 Python 异步爬虫
**S**: 70  **A**: 55  **Delta**: - -15.0
**结果**: patch_needed

### root cause
- 未处理网络超时，崩溃时没有重试机制

### lessons
- 异步任务必须加超时和 backoff 重试

### next time
- 预估分应调整为 55；建议启用 code-expert skill
```

### Stage 4：Reflexion 注入

下次执行同类型任务时，Phase 1 前自动加载历史反思：

```python
# 过滤条件
# 1. task_type 匹配
# 2. delta < min_delta_threshold（默认 -5，只加载重大失败）
# 3. 最近 max_age_days 天内

context = loader.load_context("code_generation")
# "[L2 Reflexion - code_generation]
#   1. [sf-xxx] Delta=-15 | 异步任务必须加超时和重试"
```

---

## 三层记忆索引：Token 预算设计

| 层 | 文件 | 每次开销 | 设计原则 |
|----|------|---------|---------|
| L0 | `capability-index.yaml` | ≈ 400 tokens | 每次对话注入一次，结构紧凑 |
| L1 | `trajectories/{type}/*.json` | ≈ 800 tokens | 按 task_type 按需加载，不全量 |
| L2 | `reflections.md` | ≈ 300 tokens | 只注入 top-5 重大失败，截断 60 字/条 |
| **合计** | | **≈ 1,500 tokens** | 远低于 SkillReducer 报告的 10K+ 平均水位 |

参考：SkillReducer (2025) 发现 skill body 60% 是非行动内容，压缩 39% 后质量反而提升 2.8%（less-is-more）。

---

## 可观测性：Dashboard 示例

运行 `skillforge dashboard` 的输出效果：

```
╭─ SkillForge 记忆索引 Dashboard ──────────────────────────────────────╮
│ 总执行次数: 12    全局修正值: -3分    最后更新: 2026-04-16             │
╰──────────────────────────────────────────────────────────────────────╯

                按 Task Type 分组统计（L0 Capability Index）
 Task Type         执行次数   Avg Delta   趋势           Gap 修正值   最后执行
 code_generation   7          -3.2分      ↑ improving    -3           2026-04-16
 research          3          +1.5分      → stable       +1           2026-04-15
 seo               2          -8.0分      ↓ degrading    -8           2026-04-13

Delta = 实际分 - 预估分（负值=低估，正值=高估）。Gap 修正值用于 Phase 1 校准。

╭─ Phase Timing 统计 ────────────────────────────────────────────────────╮
│ 最近 12 条记录平均耗时                                                  │
│ Phase 1: 1ms  Phase 2: 0ms  Phase 3: 0ms  Phase 4: 2ms  总计: 4ms     │
╰────────────────────────────────────────────────────────────────────────╯
```

### `memory/timings.yaml` 结构

每次 `run()` 和 `evaluate_and_close()` 都会自动写入：

```yaml
version: '1.0'
updated_at: '2026-04-16'
total_records: 12
timings:
- task_id: sf-a1b2c3d4
  task_type: code_generation
  gap_state: suggest
  phase1_ms: 0.8
  phase2_ms: 0.3
  phase3_ms: 0.1
  phase4_ms: 1.2
  total_ms: 3.4
  predicted_score: 75.0
  actual_score: 80.0
  delta: 5.0
  outcome: success
  timestamp: '2026-04-16T14:23:10'
```

### 通过 Python 获取 Timing 摘要

```python
from skillforge.tracing import TimingLogger

logger = TimingLogger("memory/timings.yaml")
summary = logger.summary()

print(f"记录条数: {summary['count']}")
print(f"平均总耗时: {summary['avg_total_ms']:.0f}ms")
print(f"各 Phase 平均: {summary['avg_phase_ms']}")
# {'phase1_ms': 0.8, 'phase2_ms': 0.3, 'phase3_ms': 0.1, 'phase4_ms': 1.4}
```
