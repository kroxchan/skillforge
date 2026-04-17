# SkillForge: Agent Skill 增强系统 PRD

> **权威版本说明**：在 Cursor 对话场景下，`.cursor/rules/skillforge.mdc` 是权威执行版本。PRD 描述的是设计意图，PRD 与 mdc 规则不一致时，以 mdc 规则为准。

> 让 Agent 在执行任务前先"自我诊断"，主动识别能力缺口，并通过 skill 增强、回退坦白或自创建 skill 来保证任务质量。通用设计，谁拿来都能用。

---

## 一、问题陈述

当前 Agent 的执行模式是"快进快出"：

1. 收到任务 → 立即执行（用已有能力） → 输出结果

这个模式有三个根本缺陷：

| 缺陷 | 说明 | 学术依据 |
|------|------|---------|
| **质量天花板** | Agent 用的是"碰巧有的"能力，而非"最适合的"能力 | KnowSelf (ACL 2025): Agent 采用"漫灌"策略，不先判断自己缺什么 |
| **Skill 闲置** | 本地或社区有更优 skill，但 Agent 不会主动检索和使用 | — |
| **用户无感知** | 用户不知道结果是否还有提升空间，只能"接受现状" | — |

进一步的核心问题：Agent 倾向于"凑合完成"，该用的 skill 没派上用场，遇到任务就直接执行"最快路径"，而非"最优路径"。

### 学术支撑

- **KnowSelf (ACL 2025)**: 当前 Agent 采用"漫灌"(flood irrigation)策略——把所有知识一股脑注入，遇到任务就直接执行，没有"先判断自己缺什么"这个环节
- **CapBound (清华 & 蚂蚁, 2025)**: LLM 其实**知道自己什么做不出来**。推理轨迹中，confident vs uncertain expressions 的密度曲线形态完全不同——可解问题呈"凹曲线"（越来越确定），不可解问题呈"凸曲线"（越来越卡住）。模型 hidden states 中，可解 vs 不可解问题在 98%+ 准确率下线性可分，甚至在推理开始前就能预判
- **Reflexion (Shinn et al.)**: 失败后用自然语言写反思，存到 episodic memory，下次复用。HumanEval pass@1 从 76.4 提升到 82.6
- **MAR - Multi-Agent Reflexion (Ozer et al.)**: 单一 agent 自评容易"确认偏误"，自己犯错还合理化。MAR 让多个不同 persona 的 critic 打辩论，最终由 judge 综合。解决了"思维退化"(degeneration-of-thought) 的问题
- **Hermes Agent**: 失败了自动生成 reusable skill 文件（SKILL.md），持续自改进

---

## 二、核心设计原则

| 原则 | 说明 |
|------|------|
| **先诊后治** | 任务执行前必须经过分析阶段，类似 KnowSelf 的"情境判断" |
| **双分数制** | 预测分数（执行前）+ 实际分数（执行后），Gap 驱动增强行为 |
| **透明告��** | 主动告诉用户"我预估能做几分"、"我建议用什么 skill" |
| **保守增强** | skill 增强需要用户授权，或限定在低风险场景自动执行 |
| **通用可迁移** | 不绑定特定 Agent 框架，任何 LLM Agent 接入即可使用 |

---

## 三、系统架构

### 整体流程

```
任务输入
  │
  ▼
┌──────────────────────────────────────────────┐
│  Phase 1: 任务分析 & 难度预判                  │
│  · 分析任务类型、所需能力集                    │
│  · 评估当前 Agent 的能力边界                  │
│  · 输出：任务难度分 (T) 和 预估得分 (S)        │
│  · 若 S < 阈值，提示用户                      │
└──────────────────┬───────────────────────────┘
                   ▼ Gap = T - S
┌──────────────────────────────────────────────┐
│  Phase 2: Skill 缺口检测 & 增强决策           │
│  · 本地 Skill Registry 查询                  │
│  · 评估每个 skill 能补多少分                 │
│  · 决策分支：                                │
│    - Gap 小 → 直接执行                       │
│    - Gap 中 → 建议用户启用 skill             │
│    - Gap 大 → 联网搜索 / 自创建 skill        │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│  Phase 3: 任务执行（增强态）                  │
│  · 使用增强后的 skill 执行                    │
│  · 记录完整执行轨迹（工具调用、中间结果）     │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│  Phase 4: 质量评估 & 自改进                  │
│  · 实际质量分数 (A) 与 预估分数 (S) 对比     │
│  · 若 A < S - δ：触发 patch 流程             │
│  · 若发现新 workflow（≥3次重复模式）：        │
│    生��� SKILL.md 草稿，提示用户确认保存       │
│  · 更新 MEMORY.md 反思记录                   │
└──────────────────────────────────────────────┘
```

---

## 四、关键模块设计

### 4.1 能力预判引擎（SkillForge-Engine）

基于任务描述，通过 CoT 推理预测：

- 任务类型（代码 / 分析 / 搜索 / 设计 / 写作 / 对话...）
- 所需能力维度（精确性、创意性、领域知识、工具使用、多步推理...）
- 当前 Agent 在各维度的能力置信度

**输出示例：**

```
任务类型: 前端代码生成
所需能力分: 85分（复杂UI、多状态管理）
当前预估分: 62分（推理模型，非专用代码模型）
缺口: 23分 → 建议使用 code-expert-skill
```

**技术实现方向：**

- 参照 CapBound 的 hidden state 线性可分性，用小模型做轻量预判
- 或者直接用 CoT prompt 让当前 Agent 自评能力缺口
- 预判结果存下，用于 Phase 4 校准

### 4.2 Skill 缺口雷达（SkillForge-Radar）

维护一个 **Skill Registry**，记录：

| 字段 | 说明 |
|------|------|
| `skill_id` | 唯一标识 |
| `name` | skill 名称 |
| `domain` | 覆盖领域 |
| `task_types` | 适用任务类型列表 |
| `capability_gains` | 各能力维度的加分效果（如 +15 精确性） |
| `quality_tier` | 质量等级（L1/L2/L3） |
| `usage_count` | 累计使用次数 |
| `avg_effectiveness` | 平均效果评分（Phase 4 反馈持续校准） |
| `source` | 来源（本地/社区/自创建） |

当 Phase 1 检测到缺口时，自动从 Registry 中找最匹配的 skill，并说明"为什么这个 skill 能补这 23 分"。

**通用 Skill Registry 格式：**

```yaml
# skillforge-registry.yaml
skills:
  - skill_id: code-expert
    name: Code Expert Skill
    domain: programming
    task_types: [code_generation, refactoring, debugging]
    capability_gains:
      precision: +20
      tool_usage: +15
    quality_tier: 3
    usage_count: 47
    avg_effectiveness: 0.82
    source: local
    path: .cursor/skills/code-expert/SKILL.md
```

### 4.3 增强决策器（SkillForge-Decider）

借鉴 KnowSelf (ACL 2025) 的情境判断研究，将原来的 L1/L2/L3 三档扩展为五态，更细粒度地刻画"能力-任务匹配度"：

| 态 | Gap 范围 | Agent 行为 | 用户感知 |
|----|---------|-----------|---------|
| **独立** | Gap < 5 | 直接执行，不提示 | 无感知，快速完成 |
| **轻提示** | 5 ≤ Gap < 15 | 执行，结束时轻描"有优化空间" | 结束时一条提示 |
| **建议增强** | 15 ≤ Gap < 30 | 输出结果 + 询问"是否启用 skill" | 结果 + 增强建议 |
| **强制增强** | 30 ≤ Gap < 50 | 主动建议 skill，用户确认后才执行 | 主动暂停，要求确认 |
| **超边界** | Gap ≥ 50 | 坦白能力边界，建议用户找专业人士/换模型 | 明确告知做不到 |

**决策流程：**

```
读取 Gap 值
  │
  ├─ Gap < 5   → 【独立】直接执行，Phase 1 结果存档
  │
  ├─ 5 ≤ Gap < 15  → 【轻提示】执行，结束时轻描"有优化空间"
  │
  ├─ 15 ≤ Gap < 30 → 【建议增强】
  │    ├─ 从 Registry 找最佳匹配 skill
  │    ├─ 计算增强后预估分 S'
  │    ├─ 展示: "当前预估 62分，启用 [X] 可提升到 77分"
  │    └─ 等待用户确认或跳过
  │
  ├─ 30 ≤ Gap < 50 → 【强制增强】
  │    ├─ 列出 Top-3 候选 skill 及各自预估分
  │    ├─ 明确告知"强制建议启用增强"
  │    └─ 用户确认后才执行，记录为"高风险"
  │
  └─ Gap ≥ 50      → 【超边界】
       ├─ 坦白告知："任务难度超出当前能力范围"
       ├─ 提供建议：换模型 / 人工介入 / 拆解任务
       └─ 不执行，记录为"拒绝执行"

### 4.4 自创建 Skill 流程（SkillForge-Forger）

当同一类任务出现 **≥3 次成功执行**时：

1. 从执行轨迹中提取标准化 workflow
2. 生成 SKILL.md 草稿（含 trigger conditions、steps、examples）
3. 提示用户审核、修改、确认保存
4. 保存后通知 Skill Registry 更新索引

**生成草稿格式示例：**

```markdown
---
name: user-github-pr-review
description: 自动审查用户 GitHub PR 的 workflow。从 URL 抓取 diff，分析代码质量，输出审查报告。触发条件：用户提供 GitHub PR URL。
---

# User GitHub PR Review Skill

## Trigger Conditions
- 用户提供 GitHub PR URL（形式为 github.com/{owner}/{repo}/pull/{number}）

## Workflow
1. 构造 GitHub API URL 获取 PR 信息和 diff
2. 调用 `curl` 或 `gh` CLI 获取 PR 详情
3. 提取 changed files 列表
4. 对每个文件生成代码审查要点
5. 综合输出结构化审查报告

## Example
用户输入: "帮我 review 这个 PR: https://github.com/owner/repo/pull/123"
Agent 输出: [结构化审查报告]

## Known Limitations
- 不支持需要 auth 的 private repo（除非配置 GITHUB_TOKEN）
- 不处理 >50 个文件的大型 PR（建议拆分成多次）
```

---

## 五、Phase 4: 质量评估与自改进闭环

### 5.1 评分约定

```
actual = predicted（干活儿的质量以预估为准）
delta  = (user_rating - 3) * 20

| 用户评分 | delta | 含义 |
|---------|-------|------|
| 5 | +40 | 超预期 |
| 3 | 0 | 符合预期 |
| 1 | -40 | 低于预期 |

delta < -5 → 触发反思（写入 memory/reflections.md）
```

### 5.2 评分机制（v0.2.2 默认基线版）

**核心原则**：默认 `rating=3`，评分是 Agent 的内部静默行为，**禁止主动询问用户打分**。

| 用户评分 | 触发条件 | delta |
|---------|---------|-------|
| 1 | 用户明确表达不满、指出错误、要求重做 | -40 |
| 3 | **默认**——任何非 1 的情况（含满意、沉默、提下一任务） | 0 |
| 5 | **罕见**——用户明确表达惊喜（如"太棒了"、"超出预期"） | +40 |

**执行步骤**：

1. 当下一轮用户消息进来时，扫描反馈判断 rating（默认 3）
2. **直接更新** `memory/capability-index.yaml` 对应 task_type：
   - `count += 1`
   - `avg_delta = 0.2 × current_delta + 0.8 × old_avg_delta`（EMA，α=0.2）
   - `gap_adjustment += current_delta`
3. 若 rating=1，追加反思到 `memory/reflections.md`

**关键约束**：

- Phase 4 由**下一轮用户消息**回溯触发，对用户完全透明
- Agent **不得**在回复末尾询问打分，**不得**主动暴露自评分数
- 由于默认 rating=3 → delta=0，大部分任务仅 `count += 1`，不会扰动 gap_adjustment。只有 rating=1/5 才真正移动校准值

> **v0.2.2 变更**：评分从"主动询问 1/3/5"改为"默认 3 + 识别偏离"，移除了打扰用户的主动打分环节。
> **v0.2.1 遗产**：L0 索引仍在对话内直接原子更新，不依赖外部命令。

### 5.3 自改进触发

当同一 task_type 成功执行 ≥5 次时，生成 SKILL.md 草稿（需用户审核确认）。

---

## 六、数据结构

### 6.1 执行轨迹（Trajectory Log）

```json
{
  "task_id": "uuid",
  "task_description": "帮我 review PR #123",
  "task_type": "code_review",
  "timestamp": "2026-04-15T10:30:00Z",
  "phase1": {
    "predicted_score": 62,
    "task_difficulty": 85,
    "detected_gap": 23,
    "gap_level": "suggest",
    "capability_dimensions": {
      "precision": 20,
      "reasoning": 15,
      "tool_knowledge": 23
    },
    "matched_skills": ["github-api-skill", "code-review-skill"]
  },
  "phase2": {
    "selected_skill": "github-api-skill",
    "enhanced_score_estimate": 74
  },
  "phase3": {
    "execution_trace": [...],
    "tools_used": ["shell:gh", "read"],
    "errors": []
  },
  "phase4": {
    "actual_score": 71,
    "quality_delta": -3,
    "outcome": "success_within_tolerance",
    "reflection": "..."
  }
}
```

### 6.2 Skill Registry Schema

```json
{
  "version": "1.0",
  "updated_at": "2026-04-15",
  "skills": [
    {
      "skill_id": "string",
      "name": "string",
      "domain": "string[]",
      "task_types": "string[]",
      "capability_gains": {
        "precision": "number",
        "reasoning": "number",
        "tool_knowledge": "number"
      },
      "quality_tier": "L1|L2|L3",
      "effectiveness_history": ["number[]"],
      "trigger_conditions": "string[]",
      "source": "local|community|autoforge",
      "path": "string"
    }
  ]
}

> **capability_gains 维度说明**（v0.2 简化版）：
> - `precision`: 数据准确性提升（幻觉风险高的任务此项更重要）
> - `reasoning`: 复杂逻辑推理能力提升
> - `tool_knowledge`: 工具调用和细分领域知识提升
```

---

## 七、文件结构

```
skillforge/
├── SKILL.md                    # 核心技能文件（Agent 直接读取）
├── skillforge-registry.yaml    # 全局 Skill Registry
├── memory/
│   ├── trajectories/           # 执行轨迹日志
│   ├── reflections.md          # Reflexion 反思记录
│   └── self-made/              # 自创建 skill 草稿
├── src/
│   ├── engine.py               # 能力预判引擎（Phase 1）
│   ├── radar.py                # Skill 缺口雷达（Phase 2）
│   ├── decider.py              # 增强决策器
│   ├── executor.py             # 增强执行（Phase 3）
│   ├── evaluator.py            # 质量评估（Phase 4）
│   ├── forger.py               # 自创建 Skill 生成器
│   └── registry.py             # Skill Registry 读写
└── config.yaml                 # 全局配置
```

---

## 八、接入方式

### 方式 A：作为 Cursor Rules 接入

在 `.cursor/rules/skillforge.mdc` 中写入 SKILL.md 的核心逻辑，任何 Cursor Agent 启动时自动具备能力预判和 Skill 增强意识。

**启动方式**：SKILL.md 在 Agent 初始化时注入一次，之后由 Agent 自觉执行四 Phase 循环，不需要每次任务都重新注入。Agent 收到的是"行为模式引导"而非"重复指令集"。

### 方式 B：作为独立 Skill 接入

把整个 `skillforge/` 目录复制到项目的 `.cursor/skills/skillforge/`，Agent 通过 skill trigger 词自动激活。

### 方式 C：作为 API 服务

```
POST /api/skillforge/analyze
Body: { "task": "帮我写一个 Python 爬虫", "agent_profile": {...} }
Response: {
  "predicted_score": 68,
  "gap": 22,
  "gap_level": "L2",
  "recommended_skills": [...]
}
```

---

## 九、核心创新点

1. **双分数驱动的增强机制**：不是盲目 retry，而是用 Gap 量化"离目标还差多少"，再决定用哪种增强手段
2. **Skill 缺口透明化**：让用户看见 Agent 的能力边界，而不是把一个 60 分的输出当成最优解
3. **渐进式自改进**：Skill 的创建和优化来自真实执行数据，而非人工维护
4. **保守增强设计**：关键决策（自动联网下载 skill、自动创建 skill）需要用户授权，避免 Agent 失控
5. **通用可迁移**：不绑定特定框架，任何 LLM Agent 接入即可使用

---

## 十三、记忆索引设计

> 基于 SkillReducer (2025) tiered architecture + Meta-Policy Reflexion (2025) MPM 思路。

### 问题

每条执行轨迹全量写入 memory 会导致：
1. Token 膨胀（每次加载大量历史）
2. 检索效率低（无索引结构）
3. 噪声累积（重复模式淹没有效 pattern）

### 方案：三层 Progressive Disclosure

| 层 | 文件 | Token/次 | 何时读取 |
|----|------|---------|---------|
| **L0 索引** | `capability-index.yaml` | <500 | Agent 启动时注入一次 |
| **L1 记录** | `trajectories/{task_type}/` | <1K | Phase 2 决策前，按 task_type 加载 |
| **L2 反思** | `reflections.md` | <2K | Phase 4 评估前读取，不注入 prompt |

**L0 索引结构**（核心设计）：

```yaml
task_type_index:
  code_generation:
    count: 23
    avg_delta: -3.2      # 实际分 - 预估分，移动平均
    trend: improving    # improving | stable | degrading
    gap_adjustment: +5  # 预判分数偏差修正值
```

**Delta 移动平均算法**：
- `avg_delta = α * current_delta + (1-α) * avg_delta`（α=0.2）
- `gap_adjustment` = 累计 Delta，用于修正 Phase 1 的预判偏差
- `trend` = 最近 5 次 Delta 趋势（上坡/下坡/平稳）

**L1 按 task_type 分目录**：`trajectories/code_generation/`、`trajectories/research/` 等，每次只加载当前类型的记录。

**L2 反思日志**：`reflections.md`，append-only，Phase 4 后追加反思，不注入 prompt。

### 效果

- 单次 Agent 调用：L0 + 当前任务 <3.5K tokens overhead
- 对比：SkillReducer 报告平均 skill body 10K+ tokens
- 参考：SkillReducer 压缩 39% 后质量提升 2.8%，less-is-more 效应

---

## 十四、风险与对策

| 风险 | 对策 |
|------|------|
| Agent 过度自评导致执行变慢 | L1 缺口直接过，Phase 1 本身轻量化 |
| 自创建 skill 质量不稳定 | 必须用户审核确认后才能入库 |
| 预测分数和实际分数偏差大 | 用 Phase 4 的反馈持续校准预判模型 |
| 确认偏误（Agent 给自己打高分） | 参考 MAR 的 multi-critic 机制，引入外部评估 |
| Skill Registry 过于庞大难维护 | 按 domain 分片存储，支持动态加载 |
