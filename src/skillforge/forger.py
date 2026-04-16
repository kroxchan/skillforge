# SkillForge 自创建 Skill 生成器
# 当同一类任务出现 ≥3 次成功执行时，自动生成 SKILL.md 草稿

from typing import Optional
from dataclasses import dataclass
from skillforge.models import Trajectory


FORGE_PROMPT = """你是一个 Skill 生成专家。请根据以下执行轨迹，生成一个标准 SKILL.md 文件。

## 任务概述
{overview}

## 轨迹数量
- 总计：{total_count} 条
- 成功：{success_count} 条
- 平均质量提升：+{avg_improvement:.1f} 分

## 成功案例（共 N 条，展示典型 3 条）

{success_cases}

## 失败案例（共 M 条，仅供参考）

{failure_cases}

## 共同模式

{common_patterns}

---

请生成标准 SKILL.md 文件：

```markdown
---
name: [auto_generated_name]
description: [一句话描述这个 skill 是做什么的，什么时候触发]
---

# [Skill 标题]

## Trigger Conditions
什么情况下应该使用这个 skill？（列表形式，至少 3 条）

## Workflow
步骤化的执行流程（numbered list，简洁清晰）

## Example
[一个使用这个 skill 的示例，演示输入和期望输出]

## Known Limitations
已知的限制和注意事项（至少 2 条）

## Quality Guidelines
质量标准或最佳实践（至少 2 条）
```

---
"""

import re
import yaml
from pathlib import Path


def parse_skill_frontmatter(skill_md_path: str) -> dict:
    """
    解析 SKILL.md 的 YAML frontmatter，返回 metadata 字典。

    Args:
        skill_md_path: SKILL.md 文件路径

    Returns:
        dict，含 skill_id / name / description / domain / task_types 等字段
    """
    path = Path(skill_md_path)
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8")

    match = re.match(r"^---\n(.*?)\n---", raw, re.DOTALL)
    if not match:
        return {
            "skill_id": path.parent.name,
            "name": path.parent.name,
            "description": "",
            "domain": [],
            "task_types": [],
            "capability_gains": {},
            "quality_tier": "L2",
        }

    metadata = yaml.safe_load(match.group(1)) or {}

    return {
        "skill_id": metadata.get("skill_id", path.parent.name),
        "name": metadata.get("name", path.parent.name),
        "description": metadata.get("description", ""),
        "domain": metadata.get("domain", []),
        "task_types": metadata.get("task_types", []),
        "capability_gains": metadata.get("capability_gains", {}),
        "quality_tier": metadata.get("quality_tier", "L2"),
        "trigger_keywords": metadata.get("trigger_keywords", []),
    }
