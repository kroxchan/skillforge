# Skill Registry 指南

> 如何添加、管理和扩展 SkillForge 的 skill 库

---

## 内置种子 Skill

`skillforge-registry.yaml` 自带 5 个种子 skill：

| Skill ID | 名称 | 适用任务 | 覆盖维度 |
|---------|------|---------|---------|
| `code-expert` | Code Expert Skill | 代码生成、重构、debug | prec +20, tool +15 |
| `research-skill` | Research Assistant | 信息检索、调研 | know +15, reas +10 |
| `seo-analysis-skill` | SEO Analysis Skill | SEO 分析、关键词 | know +12, prec +8 |
| `ffmpeg-skill` | FFmpeg Video Skill | 音视频处理 | tool +25, know +20 |
| `data-analysis-skill` | Data Analysis Skill | 数据分析、可视化 | reas +15, tool +10 |

---

## Registry 文件格式

`skillforge-registry.yaml` 的完整格式（实际文件片段）：

```yaml
version: '1.0'
updated_at: '2026-04-16'
skills:
- skill_id: code-expert          # 唯一 ID，在 Python API 中用于查找
  name: Code Expert Skill        # 展示名称
  description: 编程开发专家，处理代码生成、调试、重构等任务
  domain:
  - programming
  - development
  task_types:                    # 适用的任务类型（Phase 2 匹配时用）
  - code_generation
  - refactoring
  - debugging
  capability_gains:              # 各维度能补多少分（0-100 量纲）
    precision: 20.0
    tool_usage: 15.0
    reasoning: 10.0
    creativity: 5.0
    domain_knowledge: 5.0
    speed: -5.0                  # 负值表示该维度会变慢（可接受的代价）
  quality_tier: L3               # L1（基础）/ L2（标准）/ L3（专业）
  usage_count: 3                 # 使用次数（自动更新）
  avg_effectiveness: 0.93        # 历史平均效果（Phase 4 自动校准）
  source: local                  # local / community / autoforge
  path: .cursor/skills/code-expert/SKILL.md
  trigger_keywords:
  - 写代码
  - Python
  - debug
```

## 添加新 Skill

### 1. 在 Registry 中添加 entry

编辑 `skillforge-registry.yaml`，在 `skills:` 列表末尾追加：

```yaml
- skill_id: my-custom-skill
  name: My Custom Skill
  description: 一句话描述这个 skill 能做什么
  domain:
  - programming
  task_types:
  - code_generation
  - refactoring
  capability_gains:
    precision: 15.0
    tool_usage: 10.0
  quality_tier: L2
  usage_count: 0
  avg_effectiveness: 0.70        # 新 skill 默认 0.70，使用后自动校准
  source: local
  path: skills/my-custom-skill/SKILL.md
  trigger_keywords:
  - 写代码
  - implement
  - build
```

### 2. 创建对应的 SKILL.md

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
  tool_usage: 10
trigger_keywords: [写代码, implement, build]
---

# My Custom Skill

## 适用场景

描述这个 skill 在什么情况下被激活。

## 执行步骤

1. 第一步...
2. 第二步...

## 注意事项

- 注意点 1
- 注意点 2
```

### 3. 用 CLI 注册

```bash
skillforge push skills/my-custom-skill/
# 或直接指定 SKILL.md
skillforge push skills/my-custom-skill/SKILL.md
```

---

## 通过 Python API 管理

```python
from skillforge import SkillRegistry
from skillforge.models import Skill

registry = SkillRegistry(registry_path="skillforge-registry.yaml")

# 列出所有 skill
for skill in registry.list_skills():
    print(f"{skill.skill_id}: {skill.name} (效果 {skill.avg_effectiveness:.0%})")

# 搜索 skill
results = registry.find_by_keyword("python")

# 按任务类型和缺口匹配
recommendations = registry.match(
    task_types=["code_generation"],
    capability_gaps={"precision": 20, "tool_usage": 15},
    top_k=3,
)
for rec in recommendations:
    print(f"{rec.skill.name}: 预期提升 {rec.estimated_gain:.0f}分")

# 添加新 skill
new_skill = Skill(
    skill_id="my-skill",
    name="My Skill",
    domain=["programming"],
    task_types=["code_generation"],
    capability_gains={"precision": 15},
    quality_tier="L2",
    trigger_keywords=["python"],
    description="专业 Python 代码生成",
)
registry.add(new_skill)  # 自动保存到 YAML
```

---

## Skill effectiveness 自动校准

Phase 4 评估完成后，SkillForge 自动更新 skill 的历史效果：

```
新效果 = 旧效果 × 0.7 + (实际增益/预期增益) × 0.3
```

这意味着：
- 一个 skill 表现超预期 → `avg_effectiveness` 上升
- 表现低于预期 → 下降
- 最终趋向真实效果的均衡值

你可以在 `skillforge dashboard` 里看到每个 skill 的使用次数和历史效果变化趋势。

---

## Skill 自创建（Forger）

当同一 task_type 的成功轨迹达到 `forger_trigger`（默认 3 次）后，`evaluate_and_close()` 会自动触发 Forger，从成功轨迹中提炼生成 `SKILL.md` 草稿。

### 触发条件

1. `evaluate_and_close()` 被调用
2. 当前 task_type 的 L1 轨迹中，成功条目 ≥ `forger_trigger`（默认 3）
3. 今天尚未生成过同 task_type 的草稿

### 草稿格式示例

```markdown
---
skill_id: code_generation-skill
name: Code Generation Skill
description: "自动生成草稿 — 请补充描述"
domain: []
task_types:
  - code_generation
capability_gains:
  precision: 10
  tool_usage: 10
quality_tier: L2
trigger_keywords: []
---

# Code Generation Skill

> ⚠️ Forger 自动生成草稿
> 基于 3 条成功轨迹（平均得分 78），由 SkillForge Forger 提炼生成。

## Trigger Conditions
- 任务类型为 `code_generation`
- （补充更多触发条件）

## Workflow
1. 分析任务需求，确定输入和预期输出
2. （补充步骤）

## Successful Cases
  1. [sf-xxx] 写 Python 异步爬虫  →  A=80
  2. [sf-yyy] 实现 REST API       →  A=75

## Known Limitations
- （请补充）
```

### 在代码中检测草稿

```python
result = orch.evaluate_and_close(result, actual_score=80)

if result.forger_draft_path:
    print(f"🔨 Forger 触发！草稿位于: {result.forger_draft_path}")
    print("请审核草稿后运行 `skillforge push` 入库")
```

草稿需要你手动审核确认后才会入库，避免低质量 skill 污染 Registry：

```bash
skillforge push memory/self-made/code_generation-draft-2026-04-16.md
```

---

## 常见问题

**Q：task_types 写什么值？**

常用值：`code_generation` · `refactoring` · `research` · `seo` · `data_analysis` · `writing` · `design` · `code_review` · `other`。你也可以自定义新的 task_type，Phase 1 会自动识别。

**Q：capability_gains 的数值代表什么？**

代表这个 skill 在该维度能补多少缺口分（0-100 的量纲）。一般来说，专业 skill 在核心维度补 15-25 分，通用 skill 补 8-15 分。

**Q：quality_tier 有什么用？**

L1 = 基础 skill（轻提示场景推荐），L2 = 标准 skill（建议增强场景），L3 = 专业 skill（强制增强场景优先推荐）。目前 Phase 2 匹配时 L3 skill 权重略高。
