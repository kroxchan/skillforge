# Skill Registry 指南

> 如何管理、扩展和审核 SkillForge 的 skill 库

---

## v0.2.6 重大变化：Registry 改为涌现式生长

Registry 已从"预设 5 个种子 skill"转向**涌现式生长**：

- `skillforge-registry.yaml` 的 `skills:` 字段**默认为空**
- 由 Forger 在同类任务累计 `count ≥ 5` 时**自动生成**草稿到 `memory/self-made/`
- 用户审核草稿后显式用 `sf push` 入库

**为什么这么设计**：不同用户的工作类型不同（写代码 / 做内容 / 运营 / 设计），强行预置"种子 skill"反而污染 Registry 且跟实际需求对不上。让 Agent 在真实使用中"长出"skill 更符合个性化场景。

---

## Registry 文件格式

`skillforge-registry.yaml` 完整格式（示例，当前实际为空）：

```yaml
version: '2.0'
updated_at: '2026-04-17'
skills:
  - skill_id: refactoring-skill         # 唯一 ID（snake_case + -skill 后缀）
    name: Refactoring Skill             # 展示名称
    description: 代码重构与一致性扫荡的专项 skill
    domain:
      - programming
    task_types:                          # 适用的 task_type（Phase 2 匹配时用）
      - refactoring
    capability_gains:                    # 各维度能补多少分（0-100 量纲，v0.2.0+ 仅 3 维）
      precision: 10.0
      reasoning: 5.0
      tool_knowledge: 5.0
    quality_tier: L2                     # L1（轻量）/ L2（标准）/ L3（专业）
    usage_count: 0                       # 使用次数（自动更新）
    avg_effectiveness: 0.70              # 新 skill 默认 0.70，使用后自动校准
    source: autoforge                    # local / community / autoforge
    path: memory/self-made/refactoring-draft-2026-04-17.md
    trigger_keywords:
      - 重构
      - 一致性
      - refactor
```

**字段变化提醒**（v0.2.0 起）：
- 旧字段 `creativity` / `speed` 已废弃
- 旧字段 `domain_knowledge` + `tool_usage` 合并为 `tool_knowledge`
- `capability_gains` 只保留三个核心字段：`precision` / `reasoning` / `tool_knowledge`

---

## 涌现式工作流程

### 1. 查看当前 task_type 积累进度

```bash
sf demand-queue
```

输出：

```
╭─ Forger 需求队列（阈值 count ≥ 5）────────────────────────╮
│ Task Type              count  进度                          │
│ refactoring            2      ▓▓░░░  40%（还差 3 次）       │
│ architecture_review    1      ▓░░░░  20%（还差 4 次）       │
╰─────────────────────────────────────────────────────────────╯
```

### 2. 达到阈值时 Forger 自动触发

当某 task_type 累计 `count ≥ 5` 且没有对应 skill 时，`sf update-l0` 会自动调用 Forger 生成草稿。Agent 会在下次回复中提示：

```
🔨 Forger 已生成 refactoring 的 skill 草稿
路径: memory/self-made/refactoring-draft-2026-04-17.md
请审核后用 sf push 入库
```

### 3. 草稿内容（轻量骨架）

Forger 生成的草稿只列**事实**（count / rating 分布 / 最近审计摘要），**不替用户总结"最佳实践"**：

```markdown
---
skill_id: refactoring-skill
name: Refactoring Skill
description: "自动生成草稿 — 请补充描述"
domain: []
task_types:
  - refactoring
capability_gains:
  precision: 10
  reasoning: 10
  tool_knowledge: 10
quality_tier: L2
trigger_keywords: []
---

# Refactoring Skill

> ⚠️ Forger 自动生成草稿（v0.2.6 轻量骨架版）
> 基于 5 条执行记录（avg_delta=+2.0, trend=stable），由 SkillForge Forger 提炼生成。

## 任务类型统计

- 总执行次数：5
- 平均 delta：+2.0
- 最近 5 次 rating 分布：3/3/3/3/3
- 最后执行：2026-04-17

## Trigger Conditions
- 任务类型为 `refactoring`
- （请补充更多触发条件，如代码库范围 / 工具约束等）

## Workflow
1. （请补充：第一步做什么）
2. （请补充：第二步）
3. （请补充：第三步）

## Recent Audit Notes
- [sf-abc] 2026-04-17 修复 config.py 的路径绝对化逻辑 | S=80 | rating=3
- [sf-def] 2026-04-17 mdc Phase 4 重写触发时机契约 | S=85 | rating=3
- ...

## Known Limitations
- （请补充：这个 skill 不适用于哪些场景）
```

**为什么"轻量骨架"而不是"完整草稿"**：Forger 不懂用户的工作上下文，让它生成 Workflow 容易产生幻觉（"一步步重构"之类的空话）。交给用户在真实经验基础上填写，质量更高。

### 4. 审核并入库

手动编辑草稿，填充 Trigger Conditions / Workflow / Known Limitations，然后：

```bash
sf push memory/self-made/refactoring-draft-2026-04-17.md
```

`sf push` 会：
1. 校验 yaml frontmatter 字段完整性
2. 将 skill 条目追加到 `skillforge-registry.yaml`（保留注释）
3. 把 SKILL.md 移动到标准位置（或保留在 `memory/self-made/`）
4. 设置 `source: local`（审核后不再是 `autoforge`）

---

## 手动添加 Skill（Registry 非涌现路径）

如果你已经有了现成的 skill 文档，想跳过 Forger 直接入库：

### 1. 创建 SKILL.md

```markdown
---
name: My Custom Skill
skill_id: my-custom-skill
version: 1.0.0
description: 专业代码生成与优化 skill
domain: [programming]
task_types: [code_generation, refactoring]
capability_gains:
  precision: 15
  reasoning: 5
  tool_knowledge: 10
trigger_keywords: [写代码, implement, build]
---

# My Custom Skill

## Trigger Conditions
- 任务类型为 `code_generation` / `refactoring`
- 用户明确说"用 Python" / "写代码"

## Workflow

1. 第一步...
2. 第二步...

## Known Limitations
- 不适用于 ...
```

### 2. 用 CLI 注册

```bash
sf push path/to/my-custom-skill/SKILL.md
```

---

## Python API 管理

```python
from skillforge import SkillRegistry
from skillforge.models import Skill

registry = SkillRegistry(registry_path="skillforge-registry.yaml")

for skill in registry.list_skills():
    print(f"{skill.skill_id}: {skill.name} (效果 {skill.avg_effectiveness:.0%})")

results = registry.find_by_keyword("refactor")

recommendations = registry.match(
    task_types=["refactoring"],
    capability_gaps={"precision": 20, "reasoning": 10},
    top_k=3,
)
for rec in recommendations:
    print(f"{rec.skill.name}: 预期提升 {rec.estimated_gain:.0f}分")

new_skill = Skill(
    skill_id="my-skill",
    name="My Skill",
    domain=["programming"],
    task_types=["code_generation"],
    capability_gains={"precision": 15, "reasoning": 5, "tool_knowledge": 10},
    quality_tier="L2",
    trigger_keywords=["python"],
    description="专业 Python 代码生成",
)
registry.add(new_skill)
```

---

## Skill Effectiveness 自动校准

Phase 4 评估完成后，`skill.avg_effectiveness` 按 EMA 更新：

```
新效果 = 旧效果 × 0.7 + (实际增益/预期增益) × 0.3
```

含义：
- 一个 skill 表现超预期 → `avg_effectiveness` 上升
- 表现低于预期 → 下降
- 最终趋向真实效果的均衡值

在 `sf dashboard` 中可看到每个 skill 的使用次数和历史效果变化趋势。

---

## Forger 触发规则（v0.2.6）

| 条件 | 阈值 |
|------|------|
| task_type `count` | ≥ 5 |
| task_type 是否已有对应 skill | 否（没有入库过） |
| 今天是否已生成过该 task_type 的草稿 | 否（同日不重复） |

调整阈值：编辑 `config.yaml` 的 `evaluation.forger_trigger`（默认 5）。

---

## 常见问题

**Q：task_types 写什么值？**

由 Agent 在 Phase 4 基于语义自行命名（snake_case），不限枚举。常见值：`refactoring` · `architecture_review` · `writing` · `research` · `code_generation` · `debugging` · `design` · `seo_analysis` · `linktree_pipeline` · `video_generation` 等。

**命名粒度约束（v0.2.9-patch+）**：

- **2-3 个词**，领域+类型的抽象组合，**不含具体动作或项目细节**
- ✅ 正确：`refactoring` · `figma_to_code` · `linktree_pipeline`
- ❌ 错误：`video_linktree_analysis_implementation`（太细，count 永远停 1）· `fix_config_path_bug`（项目细节，不可复用）
- 判断标准：**同类工作换个项目，这个标签还能用吗？** 能 → 合格
- 过细命名是 Forger 不触发的头号原因（每次名字都不一样，count 永远在 1）

**Q：capability_gains 的数值代表什么？**

代表这个 skill 在该维度能补多少缺口分（0-100 的量纲）。一般来说：
- **专业 skill**（L3）：核心维度补 15~25 分
- **标准 skill**（L2）：核心维度补 8~15 分
- **轻量 skill**（L1）：核心维度补 3~8 分

**Q：quality_tier 有什么用？**

L1 = 轻量（light-hint 场景），L2 = 标准（suggest 场景），L3 = 专业（force-enhance 场景优先推荐）。Phase 2 匹配时 L3 权重略高。

**Q：`sf list-skills` 返回空怎么办？**

这是 v0.2.6+ 的**预期行为**——Registry 默认为空。你可以：
1. 继续正常用 Cursor Agent，等 Forger 自动触发
2. 手动写 SKILL.md 并 `sf push` 入库
