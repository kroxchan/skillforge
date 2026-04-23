---
name: SkillForge
description: |
  Agent Skill 增强系统。让 Agent 在执行任务前先"自我诊断"，
  识别能力缺口，并通过 skill 增强、回退坦白或自创建 skill 来保证任务质量。
  触发条件：任何需要评估任务难度、决定是否使用 skill、或需要反思改进的场景。
  通用设计，任何 LLM Agent 接入即可使用。

> **权威版本说明**：在 Cursor 对话场景下，`.cursor/rules/skillforge.mdc` 是权威执行版本。
> SKILL.md 保留用于独立 Python 引擎（批量脚本/API 场景），内容应与 mdc 规则保持一致。
---

# SkillForge: Agent Skill 增强系统

## 什么是 SkillForge

SkillForge 是一个让 Agent 主动管理"能力-任务匹配度"的框架。当前 Agent 的问题是"拿到任务就做"，不管自己擅不擅长。SkillForge 加了一个"诊-断-治"循环：

```
任务 → 分析难度 → 检测缺口 → 决策增强 → 执行 → 评估质量 → 自改进
```

## 核心概念

### 1. 双分数制

| 分数 | 含义 | 谁给出 |
|------|------|-------|
| **T**（Task Difficulty） | 任务本身的难度（做好需要多少分） | Agent 自评 |
| **S**（Predicted Score） | 预估自己能拿多少分 | Agent 自评 |
| **A**（Actual Score） | 执行后的实际质量分 | 用户评分 / 工具验证 / LLM 自评 |
| **Gap = T - S** | 能力缺口 | 计算得出 |

### 2. 五态缺分级

| 态 | Gap 范围 | Agent 行为 |
|------|---------|-----------|
| **独立** (independent) | Gap < 5 | 直接执行，不提示用户 |
| **轻提示** (light_hints) | 5 ≤ Gap < 15 | 执行，结束时轻描"有优化空间" |
| **建议增强** (suggest) | 15 ≤ Gap < 30 | 输出结果 + 告知"有优化空间，是否启用 X skill" |
| **强制增强** (force) | 30 ≤ Gap < 50 | 主动暂停，要求用户确认增强策略 |
| **超边界** (out_of_scope) | Gap ≥ 50 | 坦白能力边界，建议换方案，不执行 |

### 3. Skill Registry

SkillForge 维护一个 `skillforge-registry.yaml`，记录每个 skill 的：
- 覆盖领域（domain）
- 适用任务类型（task_types）
- 各能力维度的加分效果（capability_gains）
- 历史使用效果（avg_effectiveness）

当检测到缺口时，从 Registry 中找最匹配的 skill。

## 执行流程

### Phase 1: 任务分析 & 难度预判

拿到任务后，先不急着做，而是分析：

```
请评估这个任务的难度，并自评你的能力：

任务描述：{用户输入}

请从以下 3 个维度分析（每个维度 0-100 分）：

1. Precision（精确性）：数据必须准确吗？幻觉风险高吗？版本/API 细节容易出错吗？
   - 任务需求：__分
   - 我的能力：__分
   - 缺口：__分

2. Reasoning（推理）：需要多复杂的逻辑链？多步骤依赖？数学推导？
   - 任务需求：__分
   - 我的能力：__分
   - 缺口：__分

3. Tool+Knowledge（工具+知识）：需要调用外部工具吗？专业壁垒高吗？细分领域知识稀缺吗？
   - 任务需求：__分
   - 我的能力：__分
   - 缺口：__分

总缺口（取最大维度缺口 + 其余维度加权）：__分
五态 Gap 等级：independent / light-hint / suggest / force-enhance / out-of-scope
预估分数 S：100 - 总缺口 = __分
```

### Phase 2: Skill 缺口检测 & 增强决策

根据 Gap 等级行动：

**独立（Gap < 5）：直接执行，不提示用户**

**轻提示（5 ≤ Gap < 15）：执行，结束时轻描"有优化空间"**

**建议增强（15 ≤ Gap < 30）：**

```
Gap {gap}分（L3 建议增强）。
当前预估分数：{S}分
启用 [{skill_name}] 预计可提升到 {S'}分

候选 Skill：
1. [skill_name] — 能补 {covered_gap}分
2. ...

是否希望我启用 skill 增强执行？（回复"是"继续，或"直接做"跳过）
```

**强制增强（30 ≤ Gap < 50）：**

```
⚠️ 任务难度较高（Gap {gap}分，L4 强制增强）
当前能力可能不足以达到最优结果，建议选择增强方案：
1. 启用 [Best Skill Name]（预计 {S'}分）
2. 启用 [Second Best]（预计 {S''}分）
3. 我自己指定 skill
4. 继续用当前能力执行（高风险，不推荐）

请选择 1-4。
```

**超边界（Gap ≥ 50）：坦白能力边界，建议换方案，当前不执行**

### Phase 3: 任务执行（增强态）

使用选定的 skill 内容辅助执行：

1. 读取目标 skill 的 `SKILL.md` 内容
2. 将 skill 指导注入当前 context
3. 执行任务，同时记录执行轨迹
4. 如果遇到 skill 未覆盖的情况，主动坦白："skill 中没有处理这种情况，我选择..."

### Phase 4: 质量评估 & 自改进

评分约定（v0.2.3 默认基线版）：
- `actual = predicted`（干活儿的质量以预估为准，不改变 A）
- `delta = (user_rating - 3) × 20`
- **默认 `rating=3`**（绝大多数任务都是符合预期的）

| 用户评分 | 触发条件 | delta | 含义 |
|---------|---------|-------|------|
| 1 | 用户明确表达不满、指出错误、要求重做 | -40 | 低于预期 |
| 3 | **默认**——任何非 1 的情况（含满意、沉默、灰色反馈、提下一任务） | 0 | 符合预期 |
| 5 | **极罕见**——用户明确惊喜（"太棒了"、"超出预期"），普通"很好"不算 | +40 | 超预期 |

**关键约束（v0.2.3）**：

- **严禁主动询问用户打分**（不得在回复末尾出现"1/3/5 你选哪个"）
- **严禁主动暴露自评分数**（不得在回复末尾写"我给这次打 X 分"）
- Phase 4 由**下一轮用户消息**回溯触发，完全内化，对用户不可见
- **灰色反馈兜底**：歧义/混合反馈（"嗯"、"那就这样"、"改一下 X"）一律 rating=3

**评分步骤**：

1. 当用户下一轮消息进来时，扫描其反馈判断 rating（默认 3，批评为 1，明确惊喜为 5）
2. 调用 `sf update-l0` CLI 完成 L0 索引更新（自动保留注释 + 原子写入）：
   ```bash
   sf update-l0 \
       --task-type {task_type} \
       --rating {1|3|5} \
       --task-desc "{任务摘要}" \
       --predicted {S}
   ```
   helper 内部完成：
   - `count += 1`
   - `avg_delta = EMA(delta, α=0.2)`
   - `gap_adjustment = round(avg_delta * 2)`
   - `trend` 更新（count ≥ 5 后：avg>10→degrading, avg<5→improving, else stable）
   - `_meta.global_gap_adjustment = round(old*0.95 + delta*0.05)`
3. 若 rating=1，`sf update-l0` 自动追加反思模板骨架到 `memory/reflections.md`

**自创建 Skill 触发（≥5 次同类成功）**：

```
检测到同一类任务已成功执行 5 次。
已生成 SKILL.md 草稿，建议审核后保存以便复用。
草稿位置：memory/self-made/{auto_name}.md
```

## Reflexion 反思机制

当 rating=1（delta=-40）时，`sf update-l0` 自动追加反思模板骨架到 `memory/reflections.md`。
Agent 应填充以下格式，**严格从内因视角归因**：

```
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

## 数据存储位置

```
skillforge/
├── skillforge-registry.yaml    # Skill Registry（task_type 单一数据源）
├── memory/
│   ├── capability-index.yaml   # L0 索引（sf update-l0 原子更新 + 保留注释）
│   ├── reflections.md          # 反思记录（rating=1 时自动追加骨架）
│   ├── trajectories/           # L1 执行轨迹（Python API 批量场景）
│   └── self-made/              # Forger 生成的 skill 草稿
└── config.yaml                 # 全局配置
```

> `cursor-timings.md` 已废弃（v0.2.2），不再产出。
> `sf ingest` 命令已标注 deprecated，存量文件迁移用。

## 行为准则

1. **先诊后治**：不审查任务就执行，是最大的质量隐患
2. **透明告知**：用户有权知道 Agent 的能力边界在哪里
3. **保守增强**：高风险决策必须用户授权
4. **如实承认**：如果某个任务超出能力边界，坦白说，不要硬做
5. **持续学习**：每次失败都是改进的机会，把教训写进反思

## 与其他 Skill 的关系

SkillForge 是一个**元 skill**：它不直接完成任务，而是管理其他 skill 的使用。

```
SkillForge（调度层）
  ├── Registry 涌现式生长（v0.2.6+）  # skills: 默认为空
  ├── Forger 生成草稿（生成层）        # 同类任务 count ≥ 5 时触发
  ├── 用户审核 → sf push 入库         # 草稿进入 Registry
  └── 被入库的 skill（执行层）         # skill_id 由用户在 frontmatter 定义
```

> skill_id 以 `skillforge-registry.yaml` 为准，不预置种子条目。
> 不同用户工作类型不同，强行预置种子 skill 反而污染——让 Agent 在真实工作中"长出"skill 更符合个性化场景。

SkillForge 的优先级高于具体 skill：先分析缺口，再决定用哪个具体 skill。

## 快速参考

| 场景 | 激活 SkillForge？ |
|------|-----------------|
| 收到明确任务（> 20 字符） | ✅ 是 |
| 用户只说了想法，还没形成任务 | ❌ 否（先澄清） |
| 需要决定是否用某个 skill | ✅ 是 |
| 任务失败或质量差 | ✅ 是（触发反思） |
| 发现重复模式（同 task_type ≥ 5 次） | ✅ 是（触发 Forger 生成草稿） |
| 纯闲聊 / 短确认（≤ 20 字符） | ❌ 否 |

---

## 更新日志

- **2026-04-23 v0.2.10**: 同会话纠错体系（Layer 1 + Layer 3）——纯使用模式第二次真实反馈暴露设计空白：reflections.md 自建档起完全空白，L0 九条记录全 rating=3，"同会话多轮纠错"这个最常见场景从未触发过任何学习机制。新增 **会话约束栈**（Active Constraints 清单，用户强调的硬性约束在工作记忆维护，输出前强制自检）；**Phase 4 同会话补触发**（rating=1 条件扩展到"又错了/还是错/我刚说过/第 N 次"等重复犯错信号）；反思 root cause 新增第 4 维"约束自检是否跑了"。零代码，只改 mdc + 文档。Layer 2（跨会话 reflections 注入）作为 Round 2 待办
- **2026-04-17 v0.2.9-patch**: 纯使用模式下首次真实数据驱动的规则修复——L0 出现两条过细 task_type（`video_linktree_analysis_implementation` / `linktree_page_pipeline`，同义却不合并）；mdc Phase 4 `task_type 选择规则` 新增粒度约束（2-3 词 / 领域+类型 / 不含项目细节），附真实错误示例；三份文档同步（AGENTS.md / cursor-integration.md / skill-registry.md）；历史过细条目作为"教训化石"保留不改
- **2026-04-17 v0.2.9-review**: 第七轮复审首次 P0/P1 归零，综合分 82（项目最高）；建议进入"纯使用模式"收集真实数据后再 review
- **2026-04-17 v0.2.8**: 修复 Cursor 路径 Phase 4 从未真正工作的根因 bug——`_find_project_root()` 添加 `__file__` fallback，`Config.load()` 绝对化 storage 路径，确保 `sf` 命令在任意 CWD 下可用；mdc 补充"先 Phase 4 再 Phase 1"触发时机契约；新增 `sf search` 扫描 `memory/self-made/` 草稿；新增 `DEFAULT_TASK_TYPE` 常量；新增 `tests/test_cwd_independence.py`（8 项集成测试）；全量 **159 测试通过**（FIX-058~067）
- **2026-04-17 v0.2.7**: 涌现一致性扫荡——清理 L0 索引 legacy 条目；mdc Phase 4 task_type 选择规则重写（允许 Agent 自行命名 snake_case）；删除 StrReplace 降级路径；`_infer_task_type` 从 first-match 改为 score-based；新增 `tests/test_infer_task_type.py`（32 测试，FIX-049~057 + FIX-042）
- **2026-04-17 v0.2.6**: 范式转变——Registry 从"预设 5 个种子 skill"改为"涌现式生长"，由 Forger 在 `count ≥ 5` 时自动生成轻量骨架草稿；新增 `sf forge` / `sf demand-queue` CLI；`update_l0_file` 集成 Forger 自动触发（FIX-043~048）
- **2026-04-17 v0.2.5**: Phase 2/3 强制契约实现——新增 `sf show <skill_id>` CLI（带 Registry inline fallback）；mdc 升级为"必须展示候选表 / 必须等用户指令"（FIX-039）
- **2026-04-17 v0.2.4**: 第三轮深度复审；修复 `task_type="other"` 硬编码污染 L0 索引（FIX-037）；`sf run --rating` delta 公式统一（FIX-036）
- **2026-04-17 v0.2.3**: 引入 `sf update-l0` CLI helper（保留注释 + 原子写入）；indexer 改为从 Registry 动态加载 task_types；补 trend + global_gap_adjustment 更新（FIX-023）；新增 26 项回归测试（FIX-024）
- **2026-04-17 v0.2.2**: Phase 4 默认基线化（rating=3 为默认）；禁止主动询问打分；废弃 `cursor-timings.md`
- **2026-04-17 v0.2.1**: 全面审查修复；mdc 3 维统一；Phase 4 直接写 yaml；archive 旧 6 维文件
- **2026-04-17 v0.2.0**: 全面审查修复；mdc 权威化；Registry capability_gains 填充
- **2026-04-15 v0.1.0**: 初始版本，基于 CapBound、KnowSelf、Reflexion、MAR 研究
