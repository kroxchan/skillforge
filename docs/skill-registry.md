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

## 添加新 Skill

### 1. 在 Registry 中添加 entry

编辑 `skillforge-registry.yaml`：

```yaml
skills:
  - skill_id: my-custom-skill         # 唯一 ID，用于 Python API 引用
    name: My Custom Skill
    description: 一句话描述这个 skill 能做什么
    domain:
      - programming                   # 领域标签（可多个）
    task_types:
      - code_generation               # 适用的任务类型
      - refactoring
    capability_gains:                 # 各维度的加分效果
      precision: 15
      tool_usage: 10
    quality_tier: L2                  # L1（基础）/ L2（标准）/ L3（专业）
    trigger_keywords:
      - 写代码
      - implement
      - build
    path: skills/my-custom-skill/SKILL.md   # SKILL.md 文件路径
    source: local                           # local / community / autoforge
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

当同一类任务成功执行 3 次及以上时，SkillForge 会自动生成 SKILL.md 草稿：

```
检测到 code_generation 类任务已成功执行 3 次。
已生成 SKILL.md 草稿，建议审核后保存：
  → memory/self-made/code-gen-pattern-2026-04-16.md
```

草稿需要你手动审核确认后才会入库（`skillforge push memory/self-made/xxx.md`），避免低质量 skill 污染 Registry。

---

## 常见问题

**Q：task_types 写什么值？**

常用值：`code_generation` · `refactoring` · `research` · `seo` · `data_analysis` · `writing` · `design` · `code_review` · `other`。你也可以自定义新的 task_type，Phase 1 会自动识别。

**Q：capability_gains 的数值代表什么？**

代表这个 skill 在该维度能补多少缺口分（0-100 的量纲）。一般来说，专业 skill 在核心维度补 15-25 分，通用 skill 补 8-15 分。

**Q：quality_tier 有什么用？**

L1 = 基础 skill（轻提示场景推荐），L2 = 标准 skill（建议增强场景），L3 = 专业 skill（强制增强场景优先推荐）。目前 Phase 2 匹配时 L3 skill 权重略高。
