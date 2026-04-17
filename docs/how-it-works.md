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
│  · 3 个维度估算缺口（prec / reas / tool）                     │
│  · L0 历史数据校准预判分（读 gap_adjustment）                  │
│  · Stage 4: 自动加载 L2 同类历史反思（Python 引擎批量路径）    │
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
│  · sf show <skill_id> 输出 skill context（物理 SKILL.md 或     │
│    Registry inline fallback）                                 │
│  · 执行任务，记录工具调用和错误                                 │
│  · SandboxRunner: 代码类任务自动验证（Python 批量路径）         │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  Phase 4: 评估 + 记忆闭环（对用户透明）                         │
│  · 下一轮用户反馈识别 rating（默认 3，批评为 1，惊喜为 5）       │
│  · actual = predicted · delta = (rating - 3) × 20             │
│  · delta < 0 且 rating = 1 → 追加反思模板骨架到 L2              │
│  · sf update-l0 原子写入 L0（保留所有注释 + tmp→rename）        │
│  · count ≥ 5 时 Forger 自动触发，生成 self-made 草稿            │
└──────────────────────────────────────────────────────────────┘
```

---

## Phase 1：Gap 分析

### 三维度评估（v0.2.0 起从 6 维简化为 3 维）

| 维度 | 简写 | 什么情况下 Gap 高 |
|------|------|-----------------|
| Precision | `prec` | 幻觉风险高、数据必须准确、API/版本细节易错 |
| Reasoning | `reas` | 多步骤依赖、复杂逻辑链、数学推导 |
| Tool+Knowledge | `tool` | 需要调用真实工具、专业壁垒高、细分领域知识稀缺 |

**Gap 总分 = max(prec, reas, tool)**（取最大维度作为总 Gap，其余仅作参考，避免多维度加权失真）。

### L0 历史校准

L0 `capability-index.yaml` 记录每个 task_type 的历史执行统计：

```yaml
refactoring:
  count: 23
  avg_delta: -3.2          # EMA 指数移动平均（α=0.2）
  trend: improving
  gap_adjustment: -6       # Phase 1 预判修正值 = round(avg_delta * 2)
```

Phase 1 读取 `gap_adjustment`，自动叠加到原始 Gap 上：

- 如果历史上 `refactoring` 类任务总是被低估（`avg_delta < 0`），`gap_adjustment` 为负，下次 Gap 自动调低（预判调高）
- `avg_delta = 0.2 × current_delta + 0.8 × avg_delta`（EMA，α=0.2）
- `_meta.global_gap_adjustment` 作为系统级兜底校准（α=0.05）

### SF 诊断标签

每次明确任务在回复开头强制输出：

```
[SF | Gap≈{score} | {state}]
```

示例：

```
[SF | Gap≈3 | independent]       ← 直接执行
[SF | Gap≈35 | force-enhance]    ← 暂停，要求用户确认方案
```

**简化原因**：v0.1.x 曾列出所有非零缺口维度（如 `tool+30,know+20`），但真正影响行为的是**总 Gap 落在哪个区间**，维度细节信息量低且占标签字符。v0.2.0 起仅显示总 Gap。

---

## Phase 2：决策增强

### 五态行为

| 状态 | Gap 范围 | 行为 |
|------|---------|------|
| `independent` | < 5 | 直接进入 Phase 3，不打断用户 |
| `light-hint` | 5~15 | 直接执行，Phase 4 结束时轻提示"有优化空间" |
| `suggest` | 15~30 | 展示候选 skill 及预期提升分，询问用户是否启用 |
| `force-enhance` | 30~50 | 暂停，列出候选 skill 方案，等用户确认后才继续 |
| `out-of-scope` | ≥50 | 坦白能力边界，建议拆解任务或换专家，不执行 |

### Skill 匹配（Gap ≥ 15 时触发）

**情况 A（Registry 为空 — 当前默认状态）**：涌现式生长模型下 `skills:` 默认为空。仅提示一次"本地 Registry 为空"，不阻塞执行。Gap ≥ 30 时建议用户考虑找领域专家。

**情况 B（Registry 已有 skill）**：从 Registry 里找覆盖当前 Gap 维度的 skill：

```
综合得分 = 任务类型匹配权重(×20) + 缺口覆盖分 + 历史效果(×15)
```

Phase 3 调用 `sf show <skill_id>` 输出 skill context：
- `skill.path` 指向物理 SKILL.md → 输出完整文件（`source=skill_md`）
- 不存在 → 从 Registry 的 description / task_types / capability_gains 拼 inline context（`source=registry_inline`）

---

## Phase 4：评估与记忆闭环

### 评分约定（v0.2.3 默认基线版）

| 项 | 公式 |
|----|------|
| `actual` | `= predicted`（干活儿质量以预估为准） |
| `delta` | `= (user_rating - 3) × 20` |
| 默认 `rating` | **3**（任何非 1 的情况都默认 3） |

| rating | delta | 触发条件 |
|--------|-------|---------|
| 1 | -40 | 用户明确不满 / 要求重做 / 指出错误 |
| 3 | 0 | 默认基线：符合预期、灰色反馈、沉默、提下一任务 |
| 5 | +40 | 极罕见：用户明确惊喜（"太棒了"、"超出预期"） |

**关键约束**：
- **严禁主动询问用户打分**（不得在回复末尾出现"1/3/5 你选哪个"）
- **严禁主动暴露自评分数**（不得在回复末尾写"我给这次打 X 分"）
- Phase 4 由**下一轮用户消息**回溯触发，完全内化，对用户不可见

### 反思触发条件

- `rating = 1`：`sf update-l0` 自动追加反思模板骨架到 `memory/reflections.md`，Agent 填充内因归因
- 其他 rating：不写反思

### L2 反思格式（严格从内因视角归因）

```markdown
## [sf-{uuid}] refactoring @ 2026-04-17 14:30
**任务**: 修复 config.py 的路径绝对化逻辑
**S**: 80  **A**: 80  **delta**: -40

### root cause
- ❌ 禁止外部归因（"任务描述不清"/"模型能力不足"/"工具不足"）
- ✅ 从三个内因找根因：
  1. 我对任务的理解是否准确？（没理解 CWD 独立性要求）
  2. 我对复杂度的预判是否到位？（低估了运行时 / 测试环境差异）
  3. 我的执行策略是否合适？（应先在 /tmp 下冒烟测试）

### lessons
- 复审必须至少包含一次"在陌生 CWD 执行"的冒烟测试

### next time
- 预估分调整为 70；在测试套中加 foreign_cwd fixture
```

### Forger 触发（同类任务 count ≥ 5）

```
检测到 refactoring 类任务已执行 5 次。
已生成 SKILL.md 草稿：memory/self-made/refactoring-draft-2026-04-17.md
请审核草稿，用 sf push 入库到 Registry。
```

草稿是**轻量骨架**（只列事实 + 统计，不替用户总结最佳实践），避免 AI 幻觉污染。

---

## 三层记忆索引：Token 预算设计

| 层 | 文件 | 每次开销 | 设计原则 |
|----|------|---------|---------|
| L0 | `capability-index.yaml` | ≈ 400 tokens | 每次对话注入一次，结构紧凑 |
| L1 | `trajectories/{type}/*.json` | ≈ 800 tokens | 按 task_type 按需加载，**仅 Python 批量引擎产出，Cursor 对话路径不写** |
| L2 | `reflections.md` | ≈ 300 tokens | 只注入 top-5 重大失败，截断 60 字/条 |
| **合计** | | **≈ 1,500 tokens** | 远低于 SkillReducer 报告的 10K+ 平均水位 |

参考：**SkillReducer (2025)** 发现 skill body 60% 是非行动内容，压缩 39% 后质量反而提升 2.8%（less-is-more）。

---

## Stage 3 & 4 可观测性

### Dashboard 示例

运行 `sf dashboard` 的输出效果：

```
╭─ SkillForge 记忆索引 Dashboard ──────────────────────────────────────╮
│ 总执行次数: 4    全局修正值: 0分    最后更新: 2026-04-17              │
╰──────────────────────────────────────────────────────────────────────╯

                按 Task Type 分组统计（L0 Capability Index）
 Task Type              执行次数  Avg Delta   趋势       Gap 修正值  最后执行
 default                0         0.0分       → stable    0          -
 refactoring            2         0.0分       → stable    0          2026-04-17
 architecture_review    1         0.0分       → stable    0          2026-04-17
 cwd_integration_test   1         0.0分       → stable    0          2026-04-17

Delta = 实际分 - 预估分（负值=低估，正值=高估）。Gap 修正值用于 Phase 1 校准。

╭─ Phase Timing 统计 ────────────────────────────────────────────────────╮
│ 最近 4 条记录平均耗时                                                   │
│ Phase 1: 1ms  Phase 2: 0ms  Phase 3: 0ms  Phase 4: 2ms  总计: 4ms     │
╰────────────────────────────────────────────────────────────────────────╯
```

### `sf demand-queue` 示例

查看距 Forger 阈值（5）还差多远：

```
╭─ Forger 需求队列（阈值 count ≥ 5）────────────────────────╮
│ Task Type              count  进度                          │
│ refactoring            2      ▓▓░░░  40%（还差 3 次）       │
│ architecture_review    1      ▓░░░░  20%（还差 4 次）       │
│ cwd_integration_test   1      ▓░░░░  20%（还差 4 次）       │
╰─────────────────────────────────────────────────────────────╯
```

### `memory/timings.yaml` 结构（Python 批量引擎产出）

每次 `orch.run()` 和 `orch.evaluate_and_close()` 都会自动写入：

```yaml
version: '1.0'
updated_at: '2026-04-17'
total_records: 4
timings:
- task_id: sf-a1b2c3d4
  task_type: refactoring
  gap_state: suggest
  phase1_ms: 0.8
  phase2_ms: 0.3
  phase3_ms: 0.1
  phase4_ms: 1.2
  total_ms: 3.4
  predicted_score: 80.0
  actual_score: 80.0
  delta: 0.0
  outcome: success
  timestamp: '2026-04-17T14:23:10'
```

---

## 架构哲学：为什么做这么多简化

| 演化 | 动机 |
|------|------|
| 6 维 → 3 维（v0.2.0） | LLM 自评 6 个维度无锚定、无校验，容易造假。3 维足以区分 Gap 类型 |
| 加权 A → `actual=predicted`（v0.1.2） | 跨任务 delta 必须可比；delta 由 rating 独立编码（rating=1 → -40） |
| 主动询问打分 → 默认 3（v0.2.2） | 5 分超预期极罕见；沉默应视为默认合格，而非跳过记录 |
| 种子 skill → 涌现式（v0.2.6） | 不同用户的 skill 需求不同；强行预置反而污染 Registry |

每一步简化都来自真实使用反馈或审计发现，不是纸面设计的产物。
