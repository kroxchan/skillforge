"""
SkillForge Forger — 涌现式 Skill 生成器（v0.2.6 重写）

核心理念：Registry 不预设种子 skill，而是由 Agent 在真实工作中发现。
当 Phase 4 记录到某 task_type 累计 count ≥ 5 时，Forger 扫描该 task_type
的 L0 索引 + audit comment 历史，生成 SKILL.md 轻量骨架草稿供用户审阅。

数据源（按优先级）：
1. memory/capability-index.yaml — 统计量（count / avg_delta / trend）
2. capability-index.yaml 中的 audit 注释 — 每次任务的 task_desc / rating / delta
3. memory/reflections.md — rating=1 时的内因反思（可选）

不读取 L1 trajectory — 因为 Cursor 对话路径下不会产生 trajectory。

API:
- should_forge(task_type, index_path, registry_path) -> bool
    判断某 task_type 是否满足生成条件（count ≥ 5 且未存在同名 skill 草稿）
- forge_draft(task_type, index_path, memory_dir, ...) -> Path | None
    执行生成，返回草稿路径（若已存在则复用）
"""

from __future__ import annotations

import re
import json
import yaml
from pathlib import Path
from datetime import date
from typing import Optional


# ── 阈值配置 ────────────────────────────────────────────
FORGE_COUNT_THRESHOLD = 5  # Q1=A：同 task_type 累计 ≥5 次触发


# ── 向后兼容：保留 v0.2.5 前的 FORGE_PROMPT 常量（供 __init__.py 导入）──
FORGE_PROMPT = """你是一个 Skill 生成专家。请根据以下执行轨迹，生成一个标准 SKILL.md 文件。

[此 prompt 为 v0.2.5 及之前的 LLM-based Forger 路径使用，v0.2.6 起主通路改用
轻量骨架生成（forge_draft()），不再依赖 LLM 调用。保留本常量仅为向后兼容。]
"""


# ── 触发条件 ────────────────────────────────────────────

def should_forge(
    task_type: str,
    index_path: str | Path,
    registry_path: str | Path,
    memory_dir: str | Path = "memory",
) -> bool:
    """
    判断某 task_type 是否应该触发 Forger 生成草稿。

    触发条件（v0.2.6 Q1=A）：
    1. L0 索引中该 task_type count >= FORGE_COUNT_THRESHOLD
    2. Registry 中还没有任何 skill 以该 task_type 作为 task_types 之一
    3. memory/self-made/ 下还没有该 task_type 的草稿（避免重复生成）

    之前是否触发过（user 审核/废弃状态）**不重新触发**——
    若用户废弃草稿，需手动删除 self-made/<task_type>-draft-*.md 才会再次生成。
    """
    index_path = Path(index_path)
    registry_path = Path(registry_path)
    memory_dir = Path(memory_dir)

    # 条件 1: count ≥ 阈值
    count = _read_task_type_count(index_path, task_type)
    if count < FORGE_COUNT_THRESHOLD:
        return False

    # 条件 2: Registry 中不存在已覆盖此 task_type 的 skill
    if _registry_covers_task_type(registry_path, task_type):
        return False

    # 条件 3: 草稿目录下不存在该 task_type 的草稿
    draft_dir = memory_dir / "self-made"
    if draft_dir.exists():
        if list(draft_dir.glob(f"{task_type}-draft-*.md")):
            return False

    return True


# ── 生成草稿 ────────────────────────────────────────────

def forge_draft(
    task_type: str,
    index_path: str | Path,
    memory_dir: str | Path = "memory",
    force: bool = False,
) -> Optional[Path]:
    """
    基于 L0 索引 + audit comment 为指定 task_type 生成轻量骨架 SKILL.md。

    Q2=A（轻量骨架）：
    - 不尝试替用户总结最佳实践（因为数据不够）
    - 只如实列出"这类任务反复出现什么模式 + 历次 rating/delta 分布"
    - 留白让用户自己补 Workflow / Known Limitations / Trigger Conditions

    返回：草稿路径；若 force=False 且已存在则返回已有路径；生成失败返回 None。
    """
    index_path = Path(index_path)
    memory_dir = Path(memory_dir)
    draft_dir = memory_dir / "self-made"
    draft_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()

    existing = sorted(draft_dir.glob(f"{task_type}-draft-*.md"))
    if existing and not force:
        return existing[-1]

    # 提取统计数据
    stats = _read_task_type_stats(index_path, task_type)
    if stats is None or stats.get("count", 0) == 0:
        return None

    # 提取 audit comment 历史（task_desc / rating / delta）
    history = _read_audit_comments(index_path, task_type)

    draft_path = draft_dir / f"{task_type}-draft-{today}.md"
    draft_path.write_text(
        _render_lightweight_draft(task_type, stats, history),
        encoding="utf-8",
    )
    return draft_path


# ── 内部辅助 ────────────────────────────────────────────

def _read_task_type_stats(index_path: Path, task_type: str) -> Optional[dict]:
    """从 capability-index.yaml 读取某 task_type 的统计信息。"""
    if not index_path.exists():
        return None
    try:
        data = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None

    idx = data.get("task_type_index", {}) or {}
    entry = idx.get(task_type)
    if entry is None:
        return None
    return {
        "count": entry.get("count", 0),
        "avg_delta": entry.get("avg_delta", 0.0),
        "gap_adjustment": entry.get("gap_adjustment", 0),
        "trend": entry.get("trend", "stable"),
    }


def _read_task_type_count(index_path: Path, task_type: str) -> int:
    stats = _read_task_type_stats(index_path, task_type)
    return int(stats.get("count", 0)) if stats else 0


def _registry_covers_task_type(registry_path: Path, task_type: str) -> bool:
    """Registry 中是否已有 skill 覆盖此 task_type。"""
    if not registry_path.exists():
        return False
    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return False
    for skill in data.get("skills", []) or []:
        if task_type in (skill.get("task_types") or []):
            return True
    return False


_AUDIT_PATTERN = re.compile(
    r"#\s*\[(?P<task_id>sf-[\w-]+)\]\s+"
    r"(?P<timestamp>[\d\-T:\.]+)\s+"
    r"(?P<task_desc>.+?)\s*\|\s*"
    r"rating=(?P<rating>\d+)\s*\|\s*"
    r"delta=(?P<delta>[-+]?\d+(?:\.\d+)?)"
)


def _read_audit_comments(index_path: Path, task_type: str) -> list[dict]:
    """
    从 capability-index.yaml 的原始文本中提取某 task_type 节点尾部的 audit 注释。
    （update_l0_file 在每个条目后追加的 `# [sf-...] ... rating=x delta=y` 行）
    """
    if not index_path.exists():
        return []
    text = index_path.read_text(encoding="utf-8")

    # 定位该 task_type 块：从 "  <task_type>:" 开始，到下一个同层 task_type 或 _meta / EOF
    task_block_pattern = re.compile(
        rf"^\s{{2}}{re.escape(task_type)}:\s*$"
        r"(?P<body>(?:\n(?:\s{4,}.*|\s*#.*|\s*))+?)"
        r"(?=\n\s{2}\w|\n_meta:|\nskill_coverage:|\Z)",
        re.MULTILINE,
    )
    m = task_block_pattern.search(text)
    if not m:
        return []

    body = m.group("body")
    records = []
    for line in body.splitlines():
        hit = _AUDIT_PATTERN.search(line.strip())
        if hit:
            records.append({
                "task_id": hit.group("task_id"),
                "timestamp": hit.group("timestamp"),
                "task_desc": hit.group("task_desc"),
                "rating": int(hit.group("rating")),
                "delta": float(hit.group("delta")),
            })
    return records


def _render_lightweight_draft(
    task_type: str,
    stats: dict,
    history: list[dict],
) -> str:
    """生成轻量骨架 SKILL.md（Q2=A：只列事实，不替用户总结）。"""
    today = date.today().isoformat()
    name = task_type.replace("_", " ").replace("-", " ").title()

    # rating 分布
    ratings = [h["rating"] for h in history]
    r5 = ratings.count(5)
    r3 = ratings.count(3)
    r1 = ratings.count(1)

    # 近 5 条任务摘要
    recent = history[-5:] if history else []
    history_lines = "\n".join(
        f"  - `{h['task_id']}` {h['timestamp'][:10]} | rating={h['rating']} | delta={h['delta']:+.0f} | {h['task_desc']}"
        for h in recent
    ) or "  _（无 audit 历史，可能在 v0.2.6 之前写入）_"

    trend_hint = {
        "improving": "✓ 趋势向好",
        "stable": "→ 稳定",
        "degrading": "⚠ 趋势下滑（这正是 Forger 建议你补 skill 的核心理由）",
    }.get(stats.get("trend", "stable"), "")

    return f"""---
# SkillForge Forger 轻量骨架草稿（v0.2.6）
#
# 这是由 Forger 基于 L0 索引自动生成的"起点文档"，不是最终 skill。
# 它只列出【事实】（你反复在做什么 + 结果如何），不替你总结最佳实践。
# 请在此基础上填充 Workflow / Trigger Conditions / Known Limitations。
#
# 完成后：
#   sf push memory/self-made/{task_type}-draft-{today}.md
#
# 若不想保留：
#   rm memory/self-made/{task_type}-draft-{today}.md
#   （删除后，下次触发阈值时 Forger 会重新生成）

skill_id: {task_type}-skill
name: {name} Skill
description: "（待补充 — 一句话说明这个 skill 什么时候被激活）"
domain: []
task_types:
  - {task_type}
capability_gains:
  precision: 10       # 保守正估计；使用 ≥10 次后由 Phase 4 EMA 校准至真实值
  reasoning: 10
  tool_knowledge: 10
quality_tier: L2      # 草稿默认 L2（未校准）；真实验证后手动升 L1
trigger_keywords: []
---

# {name} Skill（草稿）

> **Forger 轻量骨架草稿** · 生成于 {today}
> 基于 L0 索引中 `{task_type}` 累计 **{stats['count']} 次**执行记录自动提取。

---

## 为什么生成这个草稿

在你的工作中，`{task_type}` 类任务已经反复出现 **{stats['count']} 次**。这类任务多次被 Phase 1 诊断为 Gap ≥ 15，说明它对你的工作负荷产生了持续影响，值得沉淀一份专属 skill。

**当前校准状态**：
- 平均 delta = `{stats['avg_delta']:+.1f}`（>0 = 你做得比自己预估好；<0 = 相反）
- gap_adjustment = `{stats['gap_adjustment']:+d}`（下次 Phase 1 会据此调整估分）
- 趋势 = `{stats['trend']}` {trend_hint}

**rating 分布**（来自最近 audit 历史）：
- rating=5 (明确超预期): {r5} 次
- rating=3 (符合预期): {r3} 次
- rating=1 (明确不满意): {r1} 次

---

## 历次执行记录（最近 5 条）

{history_lines}

---

## ⬇ 以下章节由你手工补充 ⬇

### Trigger Conditions（什么情况下应该启用此 skill）

> 看上面的历次任务描述，找出共同的触发信号。例如：
> - 当用户提到 X 时
> - 当涉及 Y 领域时
> - ...

- （待补充，至少 3 条）

### Workflow（处理此类任务的标准流程）

> 回顾 rating=5 的任务，提炼你当时的做法。
> 回顾 rating=1 的任务，提炼你要避开的做法。

1. （待补充）
2. （待补充）
3. （待补充）

### Known Limitations（已知的边界和陷阱）

- （从 rating=1 的案例中提炼）
- （从 reflections.md 中提炼）

### Quality Guidelines（质量门槛）

- （至少 2 条可检查的标准）

---

## 审核清单

- [ ] `description` 补完
- [ ] `domain` 至少填 1 个（e.g. programming / design / research）
- [ ] `trigger_keywords` 至少 5 个
- [ ] Trigger Conditions 至少 3 条
- [ ] Workflow 至少 3 步
- [ ] Known Limitations 至少 2 条
- [ ] Quality Guidelines 至少 2 条
- [ ] 运行 `sf push memory/self-made/{task_type}-draft-{today}.md` 入库
"""


# ── 兼容旧 API（保留原 count_successful_trajectories / generate_forger_draft）─────

def count_successful_trajectories(memory_dir: str, task_type: str) -> list[dict]:
    """
    [v0.2.5 及之前] 读取 L1 轨迹目录，返回该 task_type 的所有成功轨迹。

    注：Cursor 对话路径不产生 trajectory；此函数仅用于 Python 引擎批量场景。
    新的涌现式 Forger 通路请用 `should_forge` + `forge_draft`。
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
    [v0.2.5 及之前] 根据 L1 成功轨迹生成 Forger 草稿 SKILL.md。

    新的涌现式 Forger 通路请用 `forge_draft(task_type, index_path)`。
    此函数保留供 Python 引擎批量场景和 test_forger.py 向后兼容。
    """
    draft_dir = Path(memory_dir) / "self-made"
    draft_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()

    existing = list(draft_dir.glob(f"{task_type}-draft-*.md"))
    if existing:
        return str(existing[-1])

    avg_score = sum(
        t.get("phase4", {}).get("actual_score", 0) for t in trajectories
    ) / len(trajectories) if trajectories else 0.0

    case_lines = []
    for i, t in enumerate(trajectories[:3], 1):
        desc = t.get("task_description", "")[:80]
        score = t.get("phase4", {}).get("actual_score", 0)
        case_lines.append(f"  {i}. [{t.get('task_id','?')}] {desc}  →  A={score:.0f}")

    all_tools: list[str] = []
    for t in trajectories:
        all_tools.extend(t.get("phase3", {}).get("tools_used", []))
    common_tools = list(dict.fromkeys(all_tools))[:5]

    draft = f"""---
# SkillForge Forger Auto-Generated Draft (legacy L1 path)

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

> **⚠️ Forger 自动生成草稿（legacy L1 path）**
> 基于 {len(trajectories)} 条成功轨迹（平均得分 {avg_score:.0f}）生成。

## Successful Cases

{chr(10).join(case_lines)}

## Workflow

1. （补充步骤）

{f'常用工具：{", ".join(common_tools)}' if common_tools else ''}
"""

    draft_path = draft_dir / f"{task_type}-draft-{today}.md"
    draft_path.write_text(draft, encoding="utf-8")
    return str(draft_path)


def parse_skill_frontmatter(skill_md_path: str) -> dict:
    """解析 SKILL.md 的 YAML frontmatter，返回 metadata 字典。"""
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
