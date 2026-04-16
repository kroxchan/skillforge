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
from skillforge.indexer import IndexManager
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
    task_type = task_types[0] if task_types else "other"

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
    task_type = task_types[0] if task_types else "other"
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
            closed = orch.evaluate_and_close(result, actual_score=rating / 5 * 100, user_rating=rating)
            delta = rating / 5 * 100 - result.trajectory.phase1.predicted_score
            console.print(f"[green]✓ 记忆闭环完成 | Delta: {delta:+.0f}分 | 索引已更新[/green]")
        except Exception as e:
            console.print(f"[red]Phase 4 执行失败: {e}[/red]")
    else:
        console.print("\n[dim]提示：使用 --rating 参数完成 Phase 4 评估[/dim]")


@app.command()
def search(
    keyword: str = typer.Argument(..., help="搜索关键词"),
    json_output: bool = typer.Option(False, "--json"),
):
    """
    在 Registry 中搜索 skill。
    """
    registry = _load_registry()
    results = registry.find_by_keyword(keyword)

    if not results:
        console.print(f"[yellow]未找到包含「{keyword}」的 skill[/yellow]")
        return

    if json_output:
        console.print_json(json.dumps([
            {
                "skill_id": s.skill_id,
                "name": s.name,
                "description": s.description,
                "task_types": s.task_types,
                "avg_effectiveness": s.avg_effectiveness,
                "usage_count": s.usage_count,
            }
            for s in results
        ], ensure_ascii=False))
        return

    table = Table(title=f"搜索结果: 「{keyword}」（{len(results)} 个）", show_header=True)
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


# ── 入口 ────────────────────────────────────────────────

def main():
    app()


if __name__ == "__main__":
    main()


# ── 内部辅助函数 ────────────────────────────────────────

def _infer_task_type(task: str) -> list[str]:
    """根据任务描述推断 task_type（简化版）"""
    task_lower = task.lower()

    patterns = [
        (["code", "python", "javascript", "typescript", "写代码", "函数", "class"], ["code_generation"]),
        (["review", "review", "pr", "代码审查", "review code"], ["code_review"]),
        (["research", "研究", "调研", "分析趋势", "find information"], ["research"]),
        (["seo", "搜索引擎优化", "关键词", "search engine"], ["seo"]),
        (["kol", "influencer", "dm", "outreach", "推广", "网红"], ["kol_outreach"]),
        (["data", "分析", "chart", "dashboard", "数据可视化"], ["data_analysis"]),
        (["design", "ui", "ux", "设计", "figma"], ["design"]),
        (["write", "写作", "文案", "content", "blog"], ["writing"]),
    ]

    result = []
    for keywords, task_type in patterns:
        if any(k in task_lower for k in keywords):
            result.extend(task_type)
            break

    if not result:
        result = ["other"]
    return result


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
