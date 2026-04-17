# SkillForge CLI
# 命令行接口：analyze / search / list / push / dashboard

import sys
import json
import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from skillforge.config import get_config
from skillforge.registry import SkillRegistry
from skillforge.indexer import IndexManager, DEFAULT_TASK_TYPE
from skillforge.engine import SkillForgeEngine
from skillforge.decider import EnhancementDecider
from skillforge.models import Skill
from skillforge.tracing import TimingLogger

app = typer.Typer(
    name="skillforge",
    help="SkillForge — Agent Skill 增强系统",
    add_completion=False,
)
console = Console()


# ── 辅助 ────────────────────────────────────────────────

def _load_registry() -> SkillRegistry:
    cfg = get_config()
    return SkillRegistry(registry_path=cfg.storage.registry_path)


def _load_index() -> IndexManager:
    cfg = get_config()
    index_path = Path(cfg.storage.memory_dir) / "capability-index.yaml"
    return IndexManager(index_path=str(index_path))


def _state_badge(state: str) -> str:
    badges = {
        "independent": "[green]独立[/green]",
        "light_hints": "[yellow]轻提示[/yellow]",
        "suggest": "[cyan]建议增强[/cyan]",
        "force": "[bold red]强制增强[/bold red]",
        "out_of_scope": "[bold magenta]超边界[/bold magenta]",
    }
    return badges.get(state, state)


def _trend_badge(trend: str) -> str:
    badges = {
        "improving": "[green]↑ improving[/green]",
        "stable": "[yellow]→ stable[/yellow]",
        "degrading": "[red]↓ degrading[/red]",
    }
    return badges.get(trend, trend)


# ── 命令 ────────────────────────────────────────────────

@app.command()
def analyze(
    task: str = typer.Argument(..., help="任务描述"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
    verbose: bool = typer.Option(False, "-v", help="显示详细信息"),
):
    """
    Phase 1 预判：分析任务，返回 Gap 五态 + 候选 skill。
    """
    # 加载组件
    registry = _load_registry()
    index_mgr = _load_index()
    cfg = get_config()

    engine = SkillForgeEngine()
    decider = EnhancementDecider(
        independent_max=cfg.gap_thresholds.independent_max,
        light_hints_max=cfg.gap_thresholds.light_hints_max,
        suggest_max=cfg.gap_thresholds.suggest_max,
        force_max=cfg.gap_thresholds.force_max,
    )

    # Phase 1: 构建分析 prompt（CLI 模式：直接输出 prompt 让用户感知）
    # 实际使用时由 Agent 调用 LLM，CLI 这里是简化版：模拟 Phase 1 结果
    task_types = _infer_task_type(task)
    task_type = task_types[0] if task_types else "default"

    # 读取 L0 索引中的校准值
    gap_adj = index_mgr.get_gap_adjustment(task_type)
    global_adj = index_mgr.get_global_adjustment()

    # 模拟 Phase 1 预判（CLI 原型阶段不做真实 LLM 调用）
    # TODO: Stage 1 中接入真实 LLM
    raw_gap = _estimate_gap(task)
    adjusted_gap = max(0, raw_gap + gap_adj + global_adj)
    predicted = max(0, min(100, 100 - adjusted_gap))

    state = decider.classify_state(adjusted_gap)

    # Phase 2: 匹配 skill
    from .models import GapAnalysis
    gap_analysis = GapAnalysis(
        dimensions={"estimated": adjusted_gap},
        total_gap=adjusted_gap,
        predicted_score=predicted,
        task_types=[task_type],
        recommended_skill_types=[],
    )
    recommendations = registry.match(
        task_types=[task_type],
        capability_gaps={"estimated": adjusted_gap},
        top_k=5,
    )
    decision = decider.decide(
        gap=adjusted_gap,
        predicted_score=predicted,
        recommendations=recommendations,
        task_types=[task_type],
    )

    # 输出
    if json_output:
        result = {
            "task": task,
            "task_type": task_type,
            "predicted_score": predicted,
            "gap": round(adjusted_gap, 1),
            "gap_state": state,
            "gap_adjustment_used": gap_adj + global_adj,
            "skill_recommendations": [
                {
                    "skill_id": r.skill.skill_id,
                    "name": r.skill.name,
                    "estimated_gain": r.estimated_gain,
                    "avg_effectiveness": r.skill.avg_effectiveness,
                }
                for r in recommendations
            ],
            "decision": {
                "action": decision.action,
                "message": decision.message,
                "wait_for_confirm": decision.wait_for_confirm,
            },
        }
        console.print_json(json.dumps(result, ensure_ascii=False))
        return

    # 富文本输出
    title = f"Phase 1 预判结果  [{_state_badge(state)}]"
    content = (
        f"[bold]任务[/bold]: {task[:60]}{'...' if len(task) > 60 else ''}\n"
        f"[bold]任务类型[/bold]: {task_type}\n"
        f"[bold]预估分数[/bold]: {predicted:.0f} / 100\n"
        f"[bold]Gap[/bold]: {adjusted_gap:.1f} 分\n"
    )
    if gap_adj or global_adj:
        content += f"[dim]校准值: task_type={gap_adj}, global={global_adj} (来源: L0 索引)[/dim]\n"

    console.print(Panel(content, title=title, border_style="blue"))

    # Skill 推荐
    if recommendations:
        table = Table(title="候选 Skill（Phase 2 匹配结果）", show_header=True)
        table.add_column("Skill", style="cyan")
        table.add_column("覆盖缺口", justify="right")
        table.add_column("历史效果", justify="right")
        table.add_column("来源")

        for rec in recommendations[:5]:
            table.add_row(
                f"[bold]{rec.skill.name}[/bold]",
                f"+{rec.estimated_gain:.0f}分",
                f"{rec.skill.avg_effectiveness:.0%}",
                rec.skill.source,
            )
        console.print(table)

    console.print(f"\n{decision.message}")


@app.command()
def run(
    task: str = typer.Argument(..., help="任务描述"),
    skip_skill: bool = typer.Option(False, "--skip-skill", help="跳过 skill，直接执行"),
    rating: int = typer.Option(None, "--rating", help="Phase 4 用户评分（1-5）"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
):
    """
    完整 Phase 1-4 循环：预判 → 决策 → 增强 prompt → 评估 → 记忆闭环。

    该命令完整跑通 SkillForgeOrchestrator，适合在独立环境中验证整个流程。
    Phase 1 需要外部 LLM 分析；CLI 模式下使用简化估算逻辑。
    """
    from skillforge.engine import SkillForgeOrchestrator

    cfg = get_config()
    registry_path = cfg.storage.registry_path
    memory_dir = cfg.storage.memory_dir

    orch = SkillForgeOrchestrator(
        registry_path=registry_path,
        memory_dir=memory_dir,
    )

    # CLI 模式下用简化 Phase 1（不调 LLM）
    # 构建模拟 LLM 响应
    task_types = _infer_task_type(task)
    task_type = task_types[0] if task_types else "default"
    raw_gap = _estimate_gap(task)

    import json
    llm_response = json.dumps({
        "predicted_score": max(0, 100 - raw_gap),
        "total_gap": raw_gap,
        "gaps": {"estimated": raw_gap},
        "capability_dimensions": {"gaps": {"estimated": raw_gap}},
        "task_types": [task_type],
        "task_difficulty": min(100, 100 - raw_gap + 20),
        "recommended_skill_types": [],
    })

    user_decision = "skip" if skip_skill else "auto"

    try:
        result = orch.run(
            task_description=task,
            llm_response=llm_response,
            user_decision=user_decision,
        )
    except Exception as e:
        console.print(f"[red]Phase 1-3 执行失败: {e}[/red]")
        raise typer.Exit(1)

    if json_output:
        console.print_json(json.dumps({
            "task_id": result.task_id,
            "task_type": result.task_type,
            "gap_state": result.decision.action,
            "phase3_context_length": len(result.phase3_context),
            "message": result.decision.message,
        }, ensure_ascii=False))
        return

    console.print(Panel(
        f"[bold]Task ID[/bold]: {result.task_id}\n"
        f"[bold]Gap 状态[/bold]: {result.decision.action}\n"
        f"[bold]候选 Skill[/bold]: "
        f"{', '.join(r.skill.name for r in result.decision.options) or '无'}\n\n"
        f"{result.decision.message}",
        title=f"Phase 1-3 完成  [{_state_badge(result.decision.action)}]",
        border_style="blue",
    ))

    if rating is not None:
        console.print(f"\n[cyan]Phase 4 评估中（评分: {rating}/5）...[/cyan]")
        try:
            closed = orch.evaluate_and_close(result, user_rating=rating)
            delta = (rating - 3) * 20
            console.print(f"[green]✓ 记忆闭环完成 | Delta: {delta:+.0f}分 | 索引已更新[/green]")
        except Exception as e:
            console.print(f"[red]Phase 4 执行失败: {e}[/red]")
    else:
        console.print("\n[dim]提示：使用 --rating 参数完成 Phase 4 评估[/dim]")


@app.command()
def eval(
    task_id: str = typer.Option(..., "--task-id", help="任务 ID（由 SkillForge 自动生成）"),
    rating: int = typer.Option(..., "--rating", help="用户评分（1-5）"),
    task_type: str = typer.Option(DEFAULT_TASK_TYPE, "--task-type", help="任务类型（需与 skillforge-registry.yaml 登记的 task_types 一致；未知任务用 default）"),
    predicted: float = typer.Option(50.0, "--predicted", help="Phase 1 预估分 S（0-100）"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
):
    """
    Phase 4 评估结果写入 Python 引擎（Bridge 主路径）。

    用途：Cursor 规则在 Phase 4 末尾调用此命令，将对话态的自评结果写回 Python 引擎，
    完成 L0 索引更新 + L1 轨迹写入 + L2 反思追加。

    评分约定：
    - 用户评分（rating）：1（不满意）/ 3（一般）/ 5（满意）
    - actual = predicted（干活儿的质量以预估为准，用户打分不改变实际分数）
    - delta = (rating - 3) × 20（用户感受与预估的偏差，用于校准 gap_adjustment）
      - rating=5 → delta=+40（超预期）
      - rating=3 → delta=0（符合预期）
      - rating=1 → delta=-40（低于预期）

    示例：
        sf eval --task-id abc123 --rating 5 --task-type code_generation --predicted 70
        # actual=70, delta=+40
    """
    from skillforge.evaluator import QualityEvaluator
    from datetime import datetime

    actual_score = predicted
    delta = (rating - 3) * 20

    # 写入 L0 索引
    index_mgr = _load_index()
    index_mgr.update(
        task_type=task_type,
        predicted_score=predicted,
        actual_score=actual_score,
        delta=delta,
        timestamp=datetime.now().isoformat(),
    )

    result = {
        "task_id": task_id,
        "task_type": task_type,
        "rating": rating,
        "predicted": predicted,
        "actual": actual_score,
        "delta": round(delta, 1),
        "l0_index_updated": True,
        "outcome": "success" if delta >= -5 else "patch_needed",
    }

    if json_output:
        console.print_json(json.dumps(result, ensure_ascii=False))
        return

    delta_str = f"{delta:+.1f}"
    delta_style = "green" if delta >= -5 else "red"
    console.print(Panel(
        f"[bold]Task ID[/bold]: {task_id}\n"
        f"[bold]Task Type[/bold]: {task_type}\n"
        f"[bold]评分[/bold]: {rating}/5 → {actual_score:.0f}分\n"
        f"[bold]预估分[/bold]: {predicted:.0f}  [bold]{delta_str}[/bold]\n"
        f"[bold]结果[/bold]: {result['outcome']}",
        title=f"Phase 4 评估完成  [/{delta_style}]{delta_str}[/{delta_style}]",
        border_style="green" if delta >= -5 else "red",
    ))

    # 若 delta < -5，提示生成反思
    if delta < -5:
        console.print("\n[yellow]⚠ Delta < -5，建议生成反思记录写入 memory/reflections.md[/yellow]")


@app.command("update-l0")
def update_l0(
    task_type: str = typer.Option(..., "--task-type", help="任务类型（从 Registry 中选最贴近的一项，兜底用 'default'）"),
    rating: int = typer.Option(..., "--rating", help="用户评分：1 / 3 / 5"),
    task_desc: str = typer.Option(..., "--task-desc", help="任务摘要（建议 ≤50 字符）"),
    predicted: float = typer.Option(..., "--predicted", help="Phase 1 预估分 S（0-100）"),
    task_id: str = typer.Option(None, "--task-id", help="可选，默认自动生成 sf-{hex}"),
    json_output: bool = typer.Option(False, "--json", help="JSON 输出"),
):
    """
    Phase 4 闭环 helper（供 Cursor mdc 规则调用）。

    读取 memory/capability-index.yaml，针对目标 task_type 条目：
    - count += 1
    - avg_delta = EMA(delta, α=0.2)
    - gap_adjustment = round(avg_delta * 2)
    - 在条目尾部追加一条审计注释（保留已有所有注释）
    - 同步更新 _meta 的 last_task_id / total_executed / updated_at
    - 若 rating=1，在 reflections.md 追加反思模板骨架

    其中 delta = (rating - 3) × 20。

    示例:
        sf update-l0 --task-type refactoring --rating 3 \\
            --task-desc "修 8 个 FIX + 实现 sf update-l0 helper" \\
            --predicted 88

    评分约定：
      rating=1 → delta=-40（用户明确不满 / 要求重做）
      rating=3 → delta=0 （默认基线：符合预期 / 灰色反馈 / 无反馈）
      rating=5 → delta=+40（用户明确惊喜，非常罕见）
    """
    if rating not in (1, 3, 5):
        console.print(f"[red]rating 必须是 1 / 3 / 5 之一，收到: {rating}[/red]")
        raise typer.Exit(1)

    from skillforge.indexer import update_l0_file

    cfg = get_config()
    index_path = Path(cfg.storage.memory_dir) / "capability-index.yaml"

    try:
        summary = update_l0_file(
            index_path=index_path,
            task_type=task_type,
            rating=rating,
            task_desc=task_desc,
            predicted=predicted,
            task_id=task_id,
        )
    except Exception as e:
        console.print(f"[red]update-l0 失败: {e}[/red]")
        raise typer.Exit(1)

    if json_output:
        console.print_json(json.dumps(summary, ensure_ascii=False))
        return

    delta = summary["delta"]
    delta_style = "green" if delta == 0 else ("red" if delta < 0 else "magenta")
    console.print(Panel(
        f"[bold]Task ID[/bold]:    {summary['task_id']}\n"
        f"[bold]Task Type[/bold]:  {summary['task_type']}\n"
        f"[bold]Rating[/bold]:     {rating} / 5  →  [{delta_style}]delta = {delta:+d}[/{delta_style}]\n"
        f"[bold]新计数[/bold]:     count = {summary['new_count']}\n"
        f"[bold]EMA delta[/bold]:  avg_delta = {summary['new_avg_delta']:+.2f}\n"
        f"[bold]Trend[/bold]:      {summary['new_trend']}\n"
        f"[bold]Gap 修正[/bold]:   gap_adjustment = {summary['new_gap_adjustment']:+d}\n"
        f"[bold]全局修正[/bold]:   global_gap_adjustment = {summary['new_global_gap_adjustment']:+d}",
        title="Phase 4 闭环完成",
        border_style=delta_style,
    ))
    if summary["reflection_written"]:
        console.print("[yellow]⚠ rating=1，已追加反思模板骨架到 memory/reflections.md，请填充内因分析[/yellow]")


def _find_self_made_drafts(keyword: str) -> list[dict]:
    """扫描 memory/self-made/ 中未入库的 SKILL.md 草稿，返回包含关键词的条目。"""
    cfg = get_config()
    draft_dir = Path(cfg.storage.memory_dir) / "self-made"
    if not draft_dir.exists():
        return []

    kw_lower = keyword.lower()
    matched = []
    for md_file in sorted(draft_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8", errors="ignore")
        # 简单关键词匹配（文件名 + 内容）
        if kw_lower in md_file.name.lower() or kw_lower in text.lower():
            matched.append({
                "path": str(md_file),
                "name": md_file.stem,
                "status": "draft (未入库)",
            })
    return matched


@app.command()
def search(
    keyword: str = typer.Argument(..., help="搜索关键词"),
    json_output: bool = typer.Option(False, "--json"),
):
    """
    在 Registry 中搜索 skill，同时扫描 memory/self-made/ 本地草稿。
    """
    registry = _load_registry()
    results = registry.find_by_keyword(keyword)
    drafts = _find_self_made_drafts(keyword)

    if not results and not drafts:
        console.print(f"[yellow]未找到包含「{keyword}」的 skill 或本地草稿[/yellow]")
        return

    if json_output:
        console.print_json(json.dumps({
            "registry": [
                {
                    "skill_id": s.skill_id,
                    "name": s.name,
                    "description": s.description,
                    "task_types": s.task_types,
                    "avg_effectiveness": s.avg_effectiveness,
                    "usage_count": s.usage_count,
                }
                for s in results
            ],
            "local_drafts": drafts,
        }, ensure_ascii=False))
        return

    if results:
        table = Table(title=f"Registry 搜索结果: 「{keyword}」（{len(results)} 个）", show_header=True)
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="dim")
        table.add_column("Task Types", style="green")
        table.add_column("效果", justify="right")
        table.add_column("使用次数", justify="right")
        for s in results:
            table.add_row(
                f"[bold]{s.name}[/bold]",
                s.skill_id,
                ", ".join(s.task_types[:3]),
                f"{s.avg_effectiveness:.0%}",
                str(s.usage_count),
            )
        console.print(table)
    else:
        console.print(f"[dim]Registry 无「{keyword}」匹配项[/dim]")

    if drafts:
        console.print()
        console.print(f"[yellow]⚠ 发现 {len(drafts)} 个本地未入库草稿（`memory/self-made/`）：[/yellow]")
        for d in drafts:
            console.print(f"  [cyan]{d['name']}[/cyan]  {d['path']}")
        console.print("[dim]  审核后可用 `sf push <path>` 入库[/dim]")


@app.command()
def list_skills(
    json_output: bool = typer.Option(False, "--json"),
    domain: str = typer.Option(None, "--domain", help="按领域过滤"),
):
    """
    列出所有已注册的 skill。
    """
    registry = _load_registry()

    skills = registry.skills
    if domain:
        skills = [s for s in skills if domain in s.domain]

    if not skills:
        console.print("[yellow]Registry 为空，请先使用 push 添加 skill[/yellow]")
        return

    if json_output:
        console.print_json(json.dumps([
            {
                "skill_id": s.skill_id,
                "name": s.name,
                "description": s.description[:80],
                "domain": s.domain,
                "task_types": s.task_types,
                "avg_effectiveness": s.avg_effectiveness,
                "usage_count": s.usage_count,
                "quality_tier": s.quality_tier,
            }
            for s in skills
        ], ensure_ascii=False))
        return

    table = Table(title=f"Skill Registry（共 {len(skills)} 个）", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Domain", style="green")
    table.add_column("Task Types")
    table.add_column("效果", justify="right")
    table.add_column("使用", justify="right")
    table.add_column("Tier")

    for s in skills:
        domain_str = ", ".join(s.domain[:2])
        tt_str = ", ".join(s.task_types[:2])
        table.add_row(
            f"[bold]{s.name}[/bold]",
            domain_str,
            f"[dim]{tt_str}[/dim]",
            f"{s.avg_effectiveness:.0%}",
            str(s.usage_count),
            s.quality_tier,
        )
    console.print(table)


@app.command()
def show(
    skill_id: str = typer.Argument(..., help="skill_id（来自 sf search / sf list-skills）"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
):
    """
    输出指定 skill 的完整上下文（供 Phase 3 注入 Agent context 使用）。

    行为：
    1. 若 Registry 中该 skill 的 path 指向真实存在的 SKILL.md → 输出文件内容
    2. 否则 → 用 Registry 的 description / task_types / capability_gains /
       trigger_keywords 拼装最小 inline context（标注 path_missing=True）

    设计保证：Phase 3 必然拿到某种 context，不会因 SKILL.md 缺失而阻塞。
    """
    registry = _load_registry()
    skill = next((s for s in registry.skills if s.skill_id == skill_id), None)

    if skill is None:
        console.print(f"[red]未找到 skill_id: {skill_id}[/red]")
        console.print("[dim]用 `sf list-skills` 查看全部已注册 skill[/dim]")
        raise typer.Exit(1)

    # 路径解析：相对路径以 Registry yaml 所在目录为基准
    skill_path = None
    path_missing = True
    if skill.path:
        p = Path(skill.path)
        if not p.is_absolute():
            p = registry.registry_path.parent / p
        if p.exists() and p.is_file():
            skill_path = p
            path_missing = False

    if skill_path is not None:
        content = skill_path.read_text(encoding="utf-8")
        source = "skill_md"
    else:
        content = _build_inline_skill_context(skill)
        source = "registry_inline"

    if json_output:
        console.print_json(json.dumps({
            "skill_id": skill.skill_id,
            "name": skill.name,
            "source": source,
            "path_missing": path_missing,
            "resolved_path": str(skill_path) if skill_path else skill.path,
            "content": content,
            "capability_gains": skill.capability_gains,
            "task_types": skill.task_types,
            "quality_tier": skill.quality_tier,
        }, ensure_ascii=False))
        return

    # 纯文本输出（供 Phase 3 直接 pipe / 复制进 context）
    if path_missing:
        console.print(
            f"[yellow]⚠ SKILL.md 物理文件缺失[/yellow]：{skill.path}\n"
            f"[dim]已降级到 Registry inline context（path_missing=True）[/dim]\n"
        )
    console.print(content)


def _build_inline_skill_context(skill) -> str:
    """
    当 SKILL.md 物理文件不存在时，用 Registry 元数据拼装最小可用上下文。
    此函数输出供 Phase 3 注入 Agent context 使用。
    """
    gains = skill.capability_gains or {}
    gains_lines = "\n".join(
        f"- **{k}**: +{v:.0f}" for k, v in gains.items()
    ) or "- （未填写）"

    task_types_line = ", ".join(skill.task_types) or "（未指定）"
    keywords_line = ", ".join(skill.trigger_keywords) or "（未指定）"
    domain_line = ", ".join(skill.domain) or "（未指定）"

    return (
        f"# Skill: {skill.name} (`{skill.skill_id}`)\n"
        f"\n"
        f"> **注意**：此 skill 的完整 SKILL.md 尚未创建（`{skill.path}` 不存在）。\n"
        f"> 以下是 Registry 提供的轻量 inline context，作为 Phase 3 的临时注入上下文。\n"
        f"\n"
        f"## 描述\n"
        f"{skill.description or '（未填写）'}\n"
        f"\n"
        f"## 领域\n"
        f"{domain_line}\n"
        f"\n"
        f"## 适用任务类型\n"
        f"{task_types_line}\n"
        f"\n"
        f"## 能力提升估算 (capability_gains)\n"
        f"{gains_lines}\n"
        f"\n"
        f"## 触发关键词\n"
        f"{keywords_line}\n"
        f"\n"
        f"## 质量等级\n"
        f"{skill.quality_tier}（L2=设计意图估算；L1=验证；L3=实验；unknown=无数据）\n"
        f"\n"
        f"## 使用指引（Agent）\n"
        f"- 处理 `{task_types_line}` 类任务时，优先按上述能力维度自检\n"
        f"- 若发现问题落在 trigger_keywords 范围内，启用该 skill 的专长视角\n"
        f"- 执行完成后主动坦白：此轮使用的 skill 为 inline context（非完整 SKILL.md）\n"
    )


@app.command()
def forge(
    task_type: str = typer.Option(None, "--task-type", help="只对此 task_type 触发（不指定则扫描所有达到阈值的）"),
    force: bool = typer.Option(False, "--force", help="忽略重复抑制，强制重新生成草稿"),
    json_output: bool = typer.Option(False, "--json"),
):
    """
    手动触发 Forger：扫描 L0 索引，为达到阈值 (count ≥ 5 且 Registry 无覆盖) 的
    task_type 生成 SKILL.md 轻量骨架草稿到 memory/self-made/。

    正常情况 Forger 由 `sf update-l0` 自动触发；此命令用于：
    - 手动检视当前有多少 task_type 满足生成条件
    - 用户删除了已有草稿后想重新生成（配合 --force）
    - 对特定 task_type 强制生成（--task-type 且 --force）
    """
    from skillforge.forger import should_forge, forge_draft, FORGE_COUNT_THRESHOLD
    import yaml as _yaml

    cfg = get_config()
    memory_dir = Path(cfg.storage.memory_dir)
    index_path = memory_dir / "capability-index.yaml"
    registry_path = Path(cfg.storage.registry_path)

    if not index_path.exists():
        console.print(f"[red]L0 索引不存在: {index_path}[/red]")
        raise typer.Exit(1)

    data = _yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
    idx = data.get("task_type_index", {}) or {}

    targets = [task_type] if task_type else list(idx.keys())
    results = []

    for tt in targets:
        if tt == "default":
            continue
        entry = idx.get(tt, {})
        count = entry.get("count", 0)
        eligible = count >= FORGE_COUNT_THRESHOLD

        should = False
        if force and task_type == tt:
            should = True
        elif eligible:
            should = should_forge(tt, index_path, registry_path, memory_dir)

        if not should:
            results.append({
                "task_type": tt,
                "count": count,
                "status": "skipped",
                "reason": (
                    f"count={count} < {FORGE_COUNT_THRESHOLD}"
                    if count < FORGE_COUNT_THRESHOLD
                    else "已有对应 Registry skill 或 self-made 草稿"
                ),
                "draft_path": None,
            })
            continue

        draft = forge_draft(tt, index_path, memory_dir, force=force)
        results.append({
            "task_type": tt,
            "count": count,
            "status": "forged" if draft else "failed",
            "draft_path": str(draft) if draft else None,
        })

    if json_output:
        console.print_json(json.dumps(results, ensure_ascii=False))
        return

    # 默认只展示 count>0 的行；--verbose 时展示全部
    visible = [r for r in results if r["count"] > 0] if not force else results
    if not visible:
        console.print("[dim]当前 L0 中暂无 count > 0 的 task_type。[/dim]")
        console.print(
            "继续积累：每次 Phase 4 调用 `sf update-l0` 后，"
            "达到 count ≥ 5 的 task_type 会自动生成草稿。\n"
            "运行 `sf demand-queue` 查看所有进度。"
        )
        return

    table = Table(title=f"Forger 扫描结果（共 {len(visible)} 项，count=0 已过滤）", show_header=True)
    table.add_column("task_type", style="cyan")
    table.add_column("count", justify="right")
    table.add_column("状态")
    table.add_column("草稿路径 / 跳过原因")

    for r in visible:
        status_txt = (
            "[green]已生成[/green]" if r["status"] == "forged"
            else "[yellow]跳过[/yellow]" if r["status"] == "skipped"
            else "[red]失败[/red]"
        )
        extra = r.get("draft_path") or r.get("reason", "")
        table.add_row(r["task_type"], str(r["count"]), status_txt, extra)
    console.print(table)

    forged_count = sum(1 for r in visible if r["status"] == "forged")
    if forged_count > 0:
        console.print(
            f"\n[bold green]✓ 已生成 {forged_count} 份草稿[/bold green]，请审核 "
            f"`memory/self-made/` 后用 `sf push <path>` 入库。"
        )
    elif all(r["status"] == "skipped" for r in visible):
        console.print(
            "\n[dim]以上 task_type 均未达到阈值或已有覆盖，暂无草稿生成。[/dim]\n"
            "运行 `sf demand-queue` 查看距阈值的剩余进度。"
        )


@app.command(name="demand-queue")
def demand_queue(
    json_output: bool = typer.Option(False, "--json"),
):
    """
    查看 L0 索引中每个 task_type 距离 Forger 阈值 (count ≥ 5) 还差多少。

    这是涌现式 Registry 的"需求面板"：
    - ▲ 已达阈值但未生成 → 运行 `sf forge` 即可生成草稿
    - ◎ 已有草稿 / Registry 覆盖 → 不会重复生成
    - ○ 进展中 → 继续积累
    """
    from skillforge.forger import FORGE_COUNT_THRESHOLD
    import yaml as _yaml

    cfg = get_config()
    memory_dir = Path(cfg.storage.memory_dir)
    index_path = memory_dir / "capability-index.yaml"
    registry_path = Path(cfg.storage.registry_path)
    draft_dir = memory_dir / "self-made"

    if not index_path.exists():
        console.print(f"[red]L0 索引不存在: {index_path}[/red]")
        raise typer.Exit(1)

    data = _yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
    idx = data.get("task_type_index", {}) or {}

    # 已覆盖的 task_type（Registry 或 self-made）
    covered = set()
    if registry_path.exists():
        reg_data = _yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        for s in reg_data.get("skills", []) or []:
            covered.update(s.get("task_types") or [])
    drafted = set()
    if draft_dir.exists():
        for f in draft_dir.glob("*-draft-*.md"):
            tt = f.name.rsplit("-draft-", 1)[0]
            drafted.add(tt)

    rows = []
    for tt, entry in sorted(idx.items()):
        if tt == "default":
            continue
        count = entry.get("count", 0)
        avg_delta = entry.get("avg_delta", 0.0)
        # 过滤 v0.2.1 预置但从未有真实数据的空条目（count=0 且 avg=0）
        # 这些条目会在真实使用后自然变成 count>0，届时再重新出现
        if count == 0 and avg_delta == 0:
            continue
        remaining = max(0, FORGE_COUNT_THRESHOLD - count)
        if tt in covered:
            status = "◎ 已入 Registry"
        elif tt in drafted:
            status = "◎ 已有草稿"
        elif count >= FORGE_COUNT_THRESHOLD:
            status = "▲ 达阈值待生成"
        else:
            status = f"○ 进展中（还差 {remaining}）"
        rows.append({
            "task_type": tt,
            "count": count,
            "avg_delta": round(avg_delta, 2),
            "remaining": remaining,
            "status": status,
        })

    if json_output:
        console.print_json(json.dumps(rows, ensure_ascii=False))
        return

    if not rows:
        console.print("[dim]L0 索引尚无非 default task_type 记录。[/dim]")
        return

    table = Table(title="SkillForge 需求面板（涌现式 Registry）", show_header=True)
    table.add_column("task_type", style="cyan")
    table.add_column("count", justify="right")
    table.add_column("avg_delta", justify="right")
    table.add_column("距阈值", justify="right")
    table.add_column("状态")
    for r in rows:
        table.add_row(
            r["task_type"],
            str(r["count"]),
            f"{r['avg_delta']:+.1f}",
            str(r["remaining"]) if r["remaining"] > 0 else "✓",
            r["status"],
        )
    console.print(table)


@app.command()
def push(
    skill_path: str = typer.Argument(..., help="skill 目录或 SKILL.md 路径"),
    force: bool = typer.Option(False, "--force", help="覆盖已存在的 skill"),
):
    """
    将一个 skill 推入 Registry。

    skill_path 可以是：
    - SKILL.md 文件路径（自动读取 metadata）
    - skill 目录路径（读取目录下的 SKILL.md）
    """
    skill_path = Path(skill_path)
    if not skill_path.exists():
        console.print(f"[red]路径不存在: {skill_path}[/red]")
        raise typer.Exit(1)

    # 找到 SKILL.md
    if skill_path.is_dir():
        md_path = skill_path / "SKILL.md"
    else:
        md_path = skill_path
        skill_path = skill_path.parent

    if not md_path.exists():
        console.print(f"[red]未找到 SKILL.md: {md_path}[/red]")
        raise typer.Exit(1)

    # 解析 metadata frontmatter
    from .forger import parse_skill_frontmatter
    metadata = parse_skill_frontmatter(str(md_path))

    registry = _load_registry()

    # 检查是否已存在
    existing = registry.find_by_id(metadata.get("skill_id", ""))
    if existing and not force:
        console.print(f"[yellow]Skill {metadata['skill_id']} 已存在，使用 --force 覆盖[/yellow]")
        raise typer.Exit(1)

    # 构建 Skill 对象
    skill = Skill(
        skill_id=metadata.get("skill_id", md_path.parent.name),
        name=metadata.get("name", md_path.parent.name),
        domain=metadata.get("domain", []),
        task_types=metadata.get("task_types", []),
        capability_gains=metadata.get("capability_gains", {}),
        quality_tier=metadata.get("quality_tier", "L2"),
        usage_count=0,
        avg_effectiveness=0.7,  # 新 skill 默认 0.7
        source="local",
        path=str(md_path),
        trigger_keywords=metadata.get("trigger_keywords", []),
        description=metadata.get("description", ""),
    )

    registry.add(skill)
    console.print(f"[green]已添加 skill: {skill.name} ({skill.skill_id})[/green]")


@app.command()
def dashboard(
    json_output: bool = typer.Option(False, "--json"),
):
    """
    显示 L0 索引统计：各 task_type 的执行次数、avg_delta、trend。
    """
    index_mgr = _load_index()
    summary = index_mgr.summary()

    if json_output:
        console.print_json(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    console.print(Panel(
        f"[bold]总执行次数[/bold]: {summary['total_executed']}    "
        f"[bold]全局修正值[/bold]: {summary['global_gap_adjustment']}分    "
        f"[bold]最后更新[/bold]: {summary['updated_at'] or 'N/A'}",
        title="SkillForge 记忆索引 Dashboard",
        border_style="green",
    ))

    if not summary["task_types"]:
        console.print("[dim]暂无执行记录（Phase 4 评估后会自动更新）[/dim]")
        return

    table = Table(title="按 Task Type 分组统计（L0 Capability Index）", show_header=True)
    table.add_column("Task Type", style="cyan")
    table.add_column("执行次数", justify="right")
    table.add_column("Avg Delta", justify="right", style="yellow")
    table.add_column("趋势", style="yellow")
    table.add_column("Gap 修正值", justify="right")
    table.add_column("最后执行")

    for entry in summary["task_types"]:
        delta_str = f"{entry['avg_delta']:+.1f}分"
        delta_style = "green" if entry["avg_delta"] <= 0 else "red"
        table.add_row(
            f"[bold]{entry['task_type']}[/bold]",
            str(entry["count"]),
            f"[{delta_style}]{delta_str}[/{delta_style}]",
            _trend_badge(entry["trend"]),
            f"[{'green' if entry['gap_adjustment'] <= 0 else 'red'}]{entry['gap_adjustment']:+d}[/]",
            entry["last_timestamp"] or "N/A",
        )

    console.print(table)
    console.print("\n[dim]Delta = 实际分 - 预估分（负值=低估，正值=高估）。Gap 修正值用于 Phase 1 校准。[/dim]")

    # Timing 摘要
    cfg = get_config()
    timing_path = Path(cfg.storage.memory_dir) / "timings.yaml"
    timing_summary = TimingLogger(timings_path=str(timing_path)).summary()

    if timing_summary["count"] > 0:
        avg = timing_summary["avg_phase_ms"]
        console.print(Panel(
            f"[bold]最近 {timing_summary['count']} 条记录平均耗时[/bold]\n"
            f"Phase 1: {avg.get('phase1_ms', 0):.0f}ms  "
            f"Phase 2: {avg.get('phase2_ms', 0):.0f}ms  "
            f"Phase 3: {avg.get('phase3_ms', 0):.0f}ms  "
            f"Phase 4: {avg.get('phase4_ms', 0):.0f}ms  "
            f"[bold]总计: {timing_summary['avg_total_ms']:.0f}ms[/bold]",
            title="Phase Timing 统计",
            border_style="cyan",
        ))


@app.command()
def ingest(
    timings_file: str = typer.Argument(..., help="cursor-timings.md 文件路径"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只打印解析结果，不写入"),
):
    """
    [已废弃] 批量导入 cursor-timings.md 记录到 L0 索引。

    cursor-timings.md 自 v0.2.2 起不再产出，此命令仅用于存量历史文件的一次性迁移。
    新场景请使用 `sf update-l0` 完成单次 Phase 4 闭环。
    """
    console.print(
        "[yellow]⚠ 警告：sf ingest 已废弃（v0.2.2+）[/yellow]\n"
        "cursor-timings.md 自 v0.2.2 起不再产出。\n"
        "如需写入 Phase 4 数据，请改用：\n"
        "  [bold]sf update-l0 --task-type <type> --rating <1|3|5> "
        "--task-desc '<摘要>' --predicted <S>[/bold]\n"
    )

    from skillforge.models import Trajectory, Phase4Result, Phase1Result
    from datetime import datetime

    file_path = Path(timings_file)
    if not file_path.exists():
        console.print(f"[red]文件不存在: {timings_file}[/red]")
        raise typer.Exit(1)

    index_mgr = _load_index()
    registry = _load_registry()

    content = file_path.read_text(encoding="utf-8")
    entries = _parse_cursor_timings(content)

    if not entries:
        console.print("[yellow]未解析到任何记录[/yellow]")
        return

    console.print(f"[cyan]解析到 {len(entries)} 条记录：[/cyan]")
    for entry in entries:
        console.print(
            f"  [{entry['task_id']}] {entry['task_type']} "
            f"S={entry['s']} A={entry['a']} Δ={entry['delta']:+.1f}"
        )

    if dry_run:
        console.print("\n[dim]--dry-run: 未写入任何数据[/dim]")
        return

    written = 0
    for entry in entries:
        index_mgr.update(
            task_type=entry["task_type"],
            predicted_score=entry["s"],
            actual_score=entry["a"],
            delta=entry.get("delta", 0),
            timestamp=entry.get("timestamp"),
        )
        written += 1

    console.print(f"\n[green]✓ 写入完成：{written} 条 L0 索引更新[/green]")


def _parse_cursor_timings(content: str) -> list[dict]:
    """从 cursor-timings.md 解析出评估记录（支持表格格式）"""
    import re
    records = []
    # ## [sf-{uuid}] task_type @ YYYY-MM-DD HH:MM
    # | 字段 | 值 |
    # | S | X |
    # | A | X |
    # | delta | +Y |
    # | rating | N |
    blocks = re.split(r"(?=^## \[sf-)", content, flags=re.MULTILINE)
    for block in blocks:
        if not block.strip():
            continue
        m_id = re.search(r"## \[([^\]]+)\] (\w+)", block)
        ts_m = re.search(r"@ ([\d\-T: ]+)", block)
        s_m = re.search(r"\|\s*S\s*\|\s*(\d+(?:\.\d+)?)", block)
        a_m = re.search(r"\|\s*A\s*\|\s*(\d+(?:\.\d+)?)", block)
        d_m = re.search(r"\|\s*delta\s*\|\s*([+-]?\d+(?:\.\d+)?)", block)
        r_m = re.search(r"\|\s*rating\s*\|\s*(\d)", block)
        if m_id and s_m:
            records.append({
                "task_id": m_id.group(1),
                "task_type": m_id.group(2),
                "timestamp": ts_m.group(1).strip() if ts_m else "",
                "s": float(s_m.group(1)),
                "a": float(a_m.group(1)) if a_m else float(s_m.group(1)),
                "delta": float(d_m.group(1)) if d_m else 0.0,
                "rating": int(r_m.group(1)) if r_m else 3,
            })
    return records


# ── 入口 ────────────────────────────────────────────────

def main():
    app()


if __name__ == "__main__":
    main()


# ── 内部辅助函数 ────────────────────────────────────────

def _infer_task_type(task: str) -> list[str]:
    """
    根据任务描述推断 task_type。

    ⚠️ 仅用于 Python 引擎批量路径（`sf analyze` / `sf run`）。
    Cursor 对话路径下，Agent 应按 mdc Phase 4 规则**自主命名** snake_case task_type，
    并在 `sf update-l0 --task-type <tt>` 时直接传入，不经过此函数。

    此函数基于预设关键词映射，不能覆盖涌现式 Registry 下的所有情况，
    命中不准确时兜底返回 ["default"]。
    """
    task_lower = task.lower()

    # 映射表 key: 关键词列表，value: Registry 中已登记的 task_type
    patterns = [
        # code-expert
        (["code", "python", "javascript", "typescript", "写代码", "函数", "class", "function"], "code_generation"),
        (["refactor", "重构", "重写", "重组"], "refactoring"),
        (["debug", "调试", "报错", "error", "exception", "traceback"], "debugging"),
        (["review", "pr", "代码审查", "code review"], "code_review"),
        (["algorithm", "算法", "排序", "搜索", "数据结构"], "algorithm_design"),
        # seo-analysis
        (["seo", "搜索引擎优化", "search engine", "网站排名"], "content_analysis"),
        (["keyword", "关键词", "kw research"], "keyword_research"),
        (["competitor", "竞品", "竞争对手"], "competitor_analysis"),
        (["backlink", "外链", "链接建设"], "backlink_analysis"),
        # data-analysis
        (["数据清洗", "clean data", "data clean"], "data_cleaning"),
        (["统计", "statistical", "regression", "分布"], "statistical_analysis"),
        (["visualiz", "可视化", "chart", "图表", "dashboard"], "visualization"),
        (["report", "报表", "报告"], "report_generation"),
        # research
        (["research", "调研", "研究", "find information", "文献", "论文"], "research"),
        (["事实核查", "fact check", "verify"], "fact_checking"),
        # video-production
        (["video", "视频", "ffmpeg", "mp4", "剪辑"], "video_editing"),
        (["convert", "转码", "format", "格式转换"], "format_conversion"),
        (["audio", "音频", "音声"], "audio_processing"),
        (["thumbnail", "封面", "缩略图"], "thumbnail_design"),
        (["script", "脚本", "旁白", "剧本"], "script_writing"),
    ]

    # 打分匹配：统计每个 task_type 命中的关键词数，取最高分
    # 相比首匹配，顺序无关、结果可解释、多关键词描述更准确
    scores: dict[str, int] = {}
    for keywords, task_type in patterns:
        hits = sum(1 for k in keywords if k in task_lower)
        if hits > 0:
            scores[task_type] = scores.get(task_type, 0) + hits

    if not scores:
        return ["default"]

    max_score = max(scores.values())
    # 平局时按 patterns 声明顺序取第一个（稳定排序）
    for keywords, task_type in patterns:
        if scores.get(task_type, 0) == max_score:
            return [task_type]

    return ["default"]


def _estimate_gap(task: str) -> float:
    """
    简化版 Gap 估算（CLI 原型用）。
    真实 Phase 1 由 LLM 调用 PHASE1_PROMPT_TEMPLATE 完成。
    TODO: Stage 1 中接入真实 LLM。
    """
    # 基于关键词估计难度
    complex_keywords = [
        "复杂", "多步骤", "multi-step", "高并发", "分布式",
        "微服务", "机器学习", "ml ", "ai ", "大模型",
        "安全", "加密", "性能优化", "架构设计",
    ]
    moderate_keywords = [
        "实现", "写一个", "功能", "api", "rest",
        "前端", "后端", "数据库", "query",
    ]
    simple_keywords = [
        "简单", "小", "改一下", "fix", "bug",
    ]

    if any(k in task.lower() for k in complex_keywords):
        return 40.0
    elif any(k in task.lower() for k in moderate_keywords):
        return 20.0
    elif any(k in task.lower() for k in simple_keywords):
        return 8.0
    return 15.0
