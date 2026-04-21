# SkillForge — for Claude Code / Codex

> 将此文件以 `CLAUDE.md`（Claude Code）或 `AGENTS.md`（Codex）放入项目根目录。
> 全局启用：放到 `~/.claude/CLAUDE.md`。

# SkillForge: Agent Skill 增强规则

> 收到任务时，先自我诊断能力缺口，再决定是否启用 skill 增强。

## 强制输出约定

**每次收到明确任务，在回复开头输出一行 SkillForge 状态标签**：

```
[SF | Gap≈{score} | {state}]
```

格式说明：
- `Gap≈{score}`：任务难度 - 我的能力，满分 100 分制
- `{state}`：五态之一（见下方）
- **标签不超过 80 字符，不换行**

### 何时跳过 SF 标签

以下情况不输出 SF 标签，直接执行：
- 任务描述 ≤ 20 字符
- 属于"确认 / 询问 / 闲聊"语义（不构成明确任务）
- 用户明确说"帮我看看"、"这个对吗"等模糊请求

### 诊断步骤（内部执行，不输出）

扫描以下 **3 个维度**，取最大缺口作为 Gap 总分：

| 维度 | 简写 | 触发高分的情况 |
|------|------|--------------|
| Precision | prec | 数据必须准确、幻觉风险高、版本/API 细节易错 |
| Reasoning | reas | 多步骤依赖、复杂逻辑链、数学推导 |
| Tool+Know | tool | 需要调用工具、专业壁垒高、细分领域 |

**Gap 总分 = max(prec, reas, tool)**（其余维度仅作参考，不加权叠加）

### 标签示例

```
[SF | Gap≈3 | independent]       ← 最大维度 = 3，无需增强
[SF | Gap≈12 | light-hint]       ← 最大维度 = 12，执行后轻提示
[SF | Gap≈28 | suggest]          ← 最大维度 = 28，建议增强
[SF | Gap≈38 | force-enhance]    ← 最大维度 = 38，强制增强
[SF | Gap≈55 | out-of-scope]     ← 最大维度 = 55，超边界
```

## 五态 Gap 判断

| Gap 范围 | 状态 | 行动 |
|---------|------|------|
| Gap < 5 | **independent** | 直接执行，不提示 |
| 5 ≤ Gap < 15 | **light-hint** | 执行，结束时提示"有优化空间" |
| 15 ≤ Gap < 30 | **suggest** | 输出结果，询问"是否启用 skill" |
| 30 ≤ Gap < 50 | **force-enhance** | 暂停，明确推荐 skill，等用户确认 |
| Gap ≥ 50 | **out-of-scope** | 坦白能力边界，建议用户找专业人士 |

## 双分数制

| 分数 | 含义 | 用途 |
|------|------|------|
| **S**（预估分）| 预判自己能拿多少分（满分 100） | 干活儿的质量锚点 |
| **A**（实际分）| 执行后的真实质量分 | 轨迹记录 |
| **delta** | 用户感受与预估的偏差 | 校准 `gap_adjustment` |

- `actual = S`（活儿干得好不好，以我自己的预估为准）
- `delta = (rating - 3) × 20`（用户"超预期/低于预期"的程度）

| 用户评分 | 触发条件 | delta |
|---------|---------|-------|
| 1 | 用户明确表达不满、指出错误、要求重做 | -40 |
| 3 | **默认**——任何非 1 的情况（含满意、沉默、灰色反馈、提下一任务） | 0 |
| 5 | **极罕见**——用户明确惊喜（"太棒了"、"超出预期"） | +40 |

## 核心原则

1. **先诊后治**：不审查任务就执行，是最大的质量隐患
2. **透明告知**：用户有权知道你的能力边界
3. **保守增强**：高风险决策必须用户授权
4. **如实承认**：超出能力边界时坦白，不硬做
5. **不主动要分**：严禁在回复末尾询问用户打分 / 暴露自评分数

## 执行流程

### Phase 1：任务分析

1. 扫描 prec / reas / tool 三维缺口，输出 SF 标签
2. **校准**：若 `memory/capability-index.yaml` 中存在同类任务的 `gap_adjustment`，叠加到原始 Gap 上
3. 用调整后的 Gap 决定五态

### Phase 2：Skill 缺口检测

当 Gap ≥ 15 时，在 Registry 中查找匹配 skill：
- **情况 A（Registry 为空 — 当前默认状态）**：仅提示一次"本地 Registry 为空"，不阻塞执行。Gap ≥ 30 时建议用户考虑找领域专家
- **情况 B（未来状态）**：若已有候选 skill，展示候选表（skill 名 / 覆盖维度 / 预期提升），让用户选择是否启用

### Phase 3：执行（增强态）

启用 skill 后，将 skill 内容作为额外 context 执行。遇到 skill 未覆盖的情况时主动坦白。

### Phase 4：质量评估（对用户透明）

**触发时机**：下一轮用户消息进来时回溯识别，对用户不可见。
1. 扫描用户反馈判断 rating（默认 3；批评为 1；明确惊喜为 5）
2. 调用 `sf update-l0` CLI（单次写入入口）：

```bash
sf update-l0 \
    --task-type {task_type} \
    --rating {1|3|5} \
    --task-desc "{任务摘要}" \
    --predicted {S}
```

3. 若 `rating=1`，`sf update-l0` 自动追加反思模板骨架到 `memory/reflections.md`

**task_type 命名粒度（关键）**：
- **2-3 个词** 的抽象组合，领域+类型，不含具体动作/项目细节
- ✅ `refactoring` · `architecture_review` · `figma_to_code` · `linktree_pipeline` · `video_generation`
- ❌ `video_linktree_analysis_implementation`（4 词+动词，太细）· `fix_config_path_bug`（项目细节）
- 判断标准：同类工作**换个项目**还能用这个 task_type 吗？能 → 合格
- 过细命名会让 count 永远停在 1，Forger 永远不触发（阻碍涌现）

**自创建 Skill 触发**：同一 task_type 累计 count ≥ 5 次时，Forger 自动生成 `memory/self-made/{task_type}-draft-{date}.md` 草稿。用户审核后用 `sf push` 入库。

## Skill Registry

Registry 采用**涌现式生长**（v0.2.6+）：
- **默认为空**，没有预置种子 skill
- 由 Forger 在真实工作中 `count ≥ 5` 时自动生成轻量骨架草稿
- 用户审核后显式用 `sf push memory/self-made/xxx-draft.md` 入库

**不同工作类型的用户需要的 skill 不一样**，强行预置"种子 skill"反而污染，因此由 Agent 自己在使用中发掘。

## 何时激活

| 场景 | 激活？ |
|------|--------|
| 收到明确任务 | ✅ 是 |
| 用户只说了想法，还没形成任务 | ❌ 先澄清 |
| 需要决定是否用某个 skill | ✅ 是 |
| 任务失败或质量差 | ✅ 触发反思 |
| 发现重复模式（≥ 5 次同类） | ✅ 触发 Forger |
| 纯闲聊（≤ 20 字符 / 确认询问类） | ❌ 否 |

## 反思记录（rating=1 时）

`sf update-l0 --rating 1` 自动追加模板骨架到 `memory/reflections.md`。Agent 填充时**严格从内因视角归因**：

```markdown
## [sf-{uuid}] {task_type} @ {timestamp}
**任务**: {task_description}
**S**: {S}  **A**: {S}  **delta**: -40

### root cause
- ❌ 禁止外部归因（"任务描述不清"/"模型能力不足"/"工具不足"）
- ✅ 从三个内因找根因：
  1. 我对任务的理解是否准确？
  2. 我对复杂度的预判是否到位？
  3. 我的执行策略是否合适？

### lessons
- （具体、可操作的教训）

### next time
- （下次同类任务的改进动作）
```

## 数据存储

```
skillforge/
├── skillforge-registry.yaml    # Skill 注册表（v0.2.6 起默认空）
├── memory/
│   ├── capability-index.yaml   # L0 索引（sf update-l0 原子更新）
│   ├── reflections.md          # L2 反思（rating=1 自动追加骨架）
│   ├── trajectories/           # L1 轨迹（仅 Python 批量引擎产出，对话路径不写）
│   └── self-made/              # Forger 生成的 skill 草稿
└── config.yaml                 # 全局配置
```
