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
import json
import yaml
from pathlib import Path
from datetime import date


def count_successful_trajectories(memory_dir: str, task_type: str) -> list[dict]:
    """
    读取 L1 轨迹目录，返回该 task_type 的所有成功轨迹。

    成功条件：phase4.outcome in ("success", "success_within_tolerance")
    """
    traj_dir = Path(memory_dir) / "trajectories" / task_type
    if not traj_dir.exists():
        return []

    successes = []
    for f in sorted(traj_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            outcome = data.get("phase4", {}).get("outcome", "")
            if outcome in ("success", "success_within_tolerance"):
                successes.append(data)
        except Exception:
            continue

    return successes


def generate_forger_draft(
    task_type: str,
    trajectories: list[dict],
    memory_dir: str = "memory",
) -> str:
    """
    根据成功轨迹生成 Forger 草稿 SKILL.md，写入 memory/self-made/。

    返回草稿文件路径。
    """
    draft_dir = Path(memory_dir) / "self-made"
    draft_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()

    # 防止重复生成（同一天同一 task_type）
    existing = list(draft_dir.glob(f"{task_type}-draft-*.md"))
    if existing:
        return str(existing[-1])

    # 摘要
    avg_score = sum(
        t.get("phase4", {}).get("actual_score", 0) for t in trajectories
    ) / len(trajectories)

    case_lines = []
    for i, t in enumerate(trajectories[:3], 1):
        desc = t.get("task_description", "")[:80]
        score = t.get("phase4", {}).get("actual_score", 0)
        case_lines.append(f"  {i}. [{t.get('task_id','?')}] {desc}  →  A={score:.0f}")

    # 提取常见工具调用（用于推断 Workflow）
    all_tools: list[str] = []
    for t in trajectories:
        all_tools.extend(t.get("phase3", {}).get("tools_used", []))
    common_tools = list(dict.fromkeys(all_tools))[:5]  # 去重保序

    draft = f"""---
# SkillForge Forger Auto-Generated Draft
# 请修改以下 metadata，然后运行 `skillforge push {draft_dir.name}/{task_type}-draft-{today}.md` 入库

skill_id: {task_type}-skill
name: {task_type.replace('_', ' ').title()} Skill
description: "自动生成草稿 — 请补充描述"
domain: []
task_types:
  - {task_type}
capability_gains:
  precision: 10
  tool_usage: 10
quality_tier: L2
trigger_keywords: []
---

# {task_type.replace('_', ' ').title()} Skill

> **⚠️ Forger 自动生成草稿**
> 基于 {len(trajectories)} 条成功轨迹（平均得分 {avg_score:.0f}），由 SkillForge Forger 提炼生成。
> 请审核内容后通过 `skillforge push` 入库，不要直接使用未审核草稿。

---

## Trigger Conditions

> 以下条件下应激活此 skill（请根据实际情况修改）：

- 任务类型为 `{task_type}`
- （补充更多触发条件）

---

## Workflow

> 从成功轨迹中提取的执行步骤（请补充细节）：

1. 分析任务需求，确定输入和预期输出
2. （补充步骤 2）
3. （补充步骤 3）

{f'工具调用记录：{", ".join(common_tools)}' if common_tools else ''}

---

## Successful Cases

{chr(10).join(case_lines)}

---

## Known Limitations

- （请补充已知限制）
- （请补充注意事项）

---

## 审核清单

- [ ] 补充 `domain` 字段
- [ ] 补充 `trigger_keywords`
- [ ] 完善 Workflow 步骤
- [ ] 补充 Known Limitations
- [ ] 运行 `skillforge push` 入库
"""

    draft_path = draft_dir / f"{task_type}-draft-{today}.md"
    draft_path.write_text(draft, encoding="utf-8")
    return str(draft_path)


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
