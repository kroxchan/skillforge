# SkillForge 质量评估器（Phase 4）
# 执行后评估质量，记录反思，触发自改进

from typing import Optional
from datetime import datetime
from pathlib import Path
import json

from skillforge.models import (
    Trajectory, Phase4Result, Reflection,
    SkillRecommendation
)
from skillforge.indexer import IndexManager
from skillforge.mar import MARCoordinator
from skillforge.vector_search import HybridSkillMatcher, VectorSearchProvider


class QualityEvaluator:
    """
    Phase 4: 质量评估与反思

    流程：
    1. 收集评估（用户评分 / LLM 自评 / 工具验证）
    2. 计算实际分 A
    3. 与预估分 S 对比
    4. 若 A < S - δ，触发 patch 和反思
    5. 更新 Skill Registry 中的 effectiveness（L1 轨迹写入）
    6. 更新 L0 Capability Index（索引更新）
    Stage 3（可选）：MAR 多角色辩论评估 + 混合语义检索
    """

    def __init__(
        self,
        user_weight: float = 0.6,
        llm_self_weight: float = 0.3,
        tool_weight: float = 0.1,
        patch_threshold: float = 5.0,
        index_mgr: Optional[IndexManager] = None,
        mar_coordinator: Optional[MARCoordinator] = None,
        hybrid_matcher: Optional[HybridSkillMatcher] = None,
        memory_dir: str = "memory",
    ):
        """
        Args:
            user_weight: 用户评分权重
            llm_self_weight: LLM 自评权重
            tool_weight: 工具验证权重
            patch_threshold: delta 容忍阈值
            index_mgr: L0 索引管理器（共享实例避免多实例覆盖）
            mar_coordinator: MAR 多角色辩论协调器（Stage 3，可选）
            hybrid_matcher: 混合检索匹配器（Stage 3，可选）
            memory_dir: 记忆目录（用于 L2 反思写入路径）
        """
        self.user_weight = user_weight
        self.llm_self_weight = llm_self_weight
        self.tool_weight = tool_weight
        self.patch_threshold = patch_threshold
        if index_mgr is not None:
            self.index_mgr = index_mgr
        else:
            self.index_mgr = IndexManager()

        # Stage 3 可选组件
        self.mar = mar_coordinator
        self.hybrid_matcher = hybrid_matcher
        # Stage 4: L2 反思写入路径（使用绝对路径避免 cwd 漂移）
        self._memory_dir = Path(memory_dir).resolve()

    def evaluate(
        self,
        trajectory: Trajectory,
        user_rating: Optional[int] = None,      # 1-5 星
        llm_self_rating: Optional[dict] = None,  # {"accuracy": 4, ...}
        tool_verification: Optional[dict] = None  # {"passed": True, "test_count": 5}
    ) -> Phase4Result:
        """
        执行质量评估。

        Args:
            trajectory: 完整执行轨迹
            user_rating: 用户评分（1-5）
            llm_self_rating: LLM 自评分（各维度 1-5）
            tool_verification: 工具验证结果（如代码测试通过数）

        Returns:
            Phase4Result，包含实际分、结果判定、反思等
        """
        actual_score = self._compute_score(
            user_rating, llm_self_rating, tool_verification
        )

        predicted = trajectory.phase1.predicted_score
        delta = actual_score - predicted

        # 判定结果
        if delta >= -self.patch_threshold:
            outcome = "success"
        elif delta >= -self.patch_threshold * 2:
            outcome = "success_within_tolerance"
        else:
            outcome = "patch_needed"

        return Phase4Result(
            actual_score=actual_score,
            outcome=outcome,
            user_rating=user_rating,
            reflection=None,  # 后面生成
            mar_result=None,  # 后面由 finalize() 填充（MAR 启用时）
        )

    def finalize(
        self,
        trajectory: Trajectory,
        phase4: Phase4Result,
        reflection: Optional[Reflection] = None,
    ) -> dict:
        """
        Phase 4 完成后写盘：L1 轨迹 + L0 索引更新。

        调用时机：Phase 4 评估完成后。
        Stage 3 MAR: 若 mar_coordinator 已注入，在写盘前执行多角色辩论评估，
        并将结果写入 phase4.mar_result。
        """
        task_type = trajectory.task_type or "other"

        # Stage 3: MAR 多角色辩论评估（若启用）
        if self.mar is not None:
            mar_result = self.mar.evaluate(trajectory, phase4)
            phase4.mar_result = mar_result
            # 若 Judge 触发改进，记录 lesson 到 L2
            if mar_result.get("judge", {}).get("trigger_improvement"):
                lesson = mar_result["judge"].get("lesson", "")
                if lesson and reflection is None:
                    # 用 MAR lesson 生成轻量反思
                    pass  # 轻量化处理，不触发完整反思生成

        # 1. 写入 L1 轨迹（memory/trajectories/{task_type}/{task_id}.json）
        self._write_trajectory(trajectory, phase4)

        # 2. 更新 L0 Capability Index
        self.index_mgr.update(
            task_type=task_type,
            predicted_score=trajectory.phase1.predicted_score,
            actual_score=phase4.actual_score,
            timestamp=datetime.now().isoformat(),
        )

        # 3. 追加反思到 L2（可选）
        if reflection:
            self._append_reflection(reflection, trajectory)

        return {
            "trajectory_written": True,
            "index_updated": True,
            "reflection_appended": reflection is not None,
        }

    def _write_trajectory(
        self,
        trajectory: Trajectory,
        phase4: Phase4Result,
    ):
        """写入 L1 轨迹 JSON"""
        task_type = trajectory.task_type or "other"
        traj_dir = Path("memory") / "trajectories" / task_type
        traj_dir.mkdir(parents=True, exist_ok=True)

        traj_file = traj_dir / f"{trajectory.task_id}.json"
        data = {
            "task_id": trajectory.task_id,
            "task_description": trajectory.task_description,
            "task_type": task_type,
            "timestamp": trajectory.timestamp.isoformat(),
            "phase1": {
                "predicted_score": trajectory.phase1.predicted_score,
                "gap": trajectory.phase1.gap,
                "gap_level": trajectory.phase1.gap_level,
                "task_types": trajectory.phase1.task_types,
            },
            "phase2": {
                "selected_skill": (
                    trajectory.phase2.selected_skill.name
                    if trajectory.phase2.selected_skill else None
                ),
                "user_decision": trajectory.phase2.user_decision,
            },
            "phase3": {
                "tools_used": trajectory.phase3.tools_used,
                "errors": trajectory.phase3.errors,
            },
            "phase4": {
                "actual_score": phase4.actual_score,
                "outcome": phase4.outcome,
                "user_rating": phase4.user_rating,
                "delta": phase4.actual_score - trajectory.phase1.predicted_score,
            },
        }

        with open(traj_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _append_reflection(
        self,
        reflection: Reflection,
        trajectory: Trajectory,
    ):
        """追加反思到 L2 日志（reflections.md）"""
        ref_file = self._memory_dir / "reflections.md"
        ref_file.parent.mkdir(parents=True, exist_ok=True)

        delta_icon = "+" if reflection.delta > 0 else ("-" if reflection.delta < -5 else "~")
        ts = datetime.now().strftime('%Y-%m-%d %H:%M')
        # Stage 4: task_type 用于 L2 索引过滤
        rc_lines = ''.join(f'- {c}\n' for c in reflection.root_causes)
        ls_lines = ''.join(f'- {l}\n' for l in reflection.lessons)
        ig_lines = ''.join(f'- {s}\n' for s in reflection.improvement_suggestions)

        entry = f"""## [{reflection.task_id}] {reflection.task_type}  @ {ts}

**任务**: {trajectory.task_description[:80]}
**S**: {reflection.predicted:.0f}  **A**: {reflection.actual:.0f}  **Delta**: {delta_icon} {reflection.delta:+.1f}
**结果**: {reflection.outcome}

### 根因
{rc_lines}

### 教训
{ls_lines}

### 改进
{ig_lines}

---
"""
        with open(ref_file, "a", encoding="utf-8") as f:
            f.write(entry)

    def generate_reflection(
        self,
        trajectory: Trajectory,
        phase4: Phase4Result
    ) -> Reflection:
        """
        生成反思记录。

        触发条件：
        - outcome == "patch_needed"
        - 或 delta < -5
        - 或用户要求反思
        """
        predicted = trajectory.phase1.predicted_score
        actual = phase4.actual_score
        delta = actual - predicted

        # 分析根因
        root_causes = self._analyze_root_cause(trajectory, delta)

        # 教训
        lessons = self._extract_lessons(root_causes)

        # 改进建议
        suggestions = self._generate_suggestions(trajectory, delta, root_causes)

        return Reflection(
            task_id=trajectory.task_id,
            task_type=trajectory.task_type,
            predicted=predicted,
            actual=actual,
            delta=delta,
            outcome=phase4.outcome,
            root_causes=root_causes,
            lessons=lessons,
            improvement_suggestions=suggestions,
            related_trajectory_path=f"memory/trajectories/{trajectory.task_id}.md"
        )

    def format_reflection_markdown(
        self,
        reflection: Reflection,
        trajectory: Trajectory
    ) -> str:
        """生成 Markdown 格式的反思记录（用于写入文件）"""
        delta_icon = "+" if reflection.delta > 0 else ("-" if reflection.delta < -5 else "~")
        rc_lines = "".join(f"- {cause}\n" for cause in reflection.root_causes)
        ls_lines = "".join(f"- {lesson}\n" for lesson in reflection.lessons)
        ig_lines = "".join(f"- {s}\n" for s in reflection.improvement_suggestions)
        ts = datetime.now().strftime('%Y-%m-%d %H:%M')
        desc = trajectory.task_description[:80]
        suffix = '...' if len(trajectory.task_description) > 80 else ''
        traj_path = reflection.related_trajectory_path

        return f"""## 反思记录 [{ts}]

**任务**：{desc}{suffix}
**类型**：{trajectory.task_type}
**预估分**：{reflection.predicted:.0f} **实际分**：{reflection.actual:.0f} **Delta**：{delta_icon} {reflection.delta:.1f}
**结果**：{reflection.outcome}

### 失败根因

{rc_lines}

### 教训

{ls_lines}

### 改进建议

{ig_lines}

### 相关轨迹
`{traj_path}`

---
"""

    def _compute_score(
        self,
        user_rating: Optional[int],
        llm_self_rating: Optional[dict],
        tool_verification: Optional[dict]
    ) -> float:
        """计算加权实际分（0-100）"""
        scores = []
        weights = []

        if user_rating is not None:
            scores.append(user_rating / 5 * 100)  # 1-5 → 0-100
            weights.append(self.user_weight)

        if llm_self_rating:
            avg = sum(llm_self_rating.values()) / len(llm_self_rating)
            scores.append(avg / 5 * 100)
            weights.append(self.llm_self_weight)

        if tool_verification:
            if tool_verification.get("passed"):
                scores.append(100)
            else:
                passed = tool_verification.get("passed_count", 0)
                total = tool_verification.get("test_count", 1)
                scores.append(passed / total * 100)
            weights.append(self.tool_weight)

        if not scores:
            return 50  # 默认中分

        total_weight = sum(weights)
        return sum(s * w for s, w in zip(scores, weights)) / total_weight

    def _analyze_root_cause(
        self,
        trajectory: Trajectory,
        delta: float
    ) -> list[str]:
        """分析失败根因"""
        causes = []

        # 检查 Phase 3 执行轨迹中的错误
        if trajectory.phase3.errors:
            for error in trajectory.phase3.errors:
                causes.append(f"执行错误：{error}")

        # 检查工具调用
        if trajectory.phase3.tools_used:
            # 常见问题模式
            missing_tools = [t for t in ["github", "bash", "file"] 
                           if any(t in t_used.lower() for t_used in trajectory.phase3.tools_used) is False]
            # 这里可以扩展更多模式检测

        # 检查 phase1 预判偏差
        if delta < -10:
            causes.append(f"预判偏差较大：预估 {trajectory.phase1.predicted_score:.0f}，实际 {trajectory.phase1.predicted_score + delta:.0f}")

        # 检查 skill 效果
        if trajectory.phase2.selected_skill and delta < -5:
            causes.append(f"启用的 skill 效果未达预期，可能是场景不匹配")

        if not causes:
            causes.append("未知根因，需进一步分析执行轨迹")

        return causes

    def _extract_lessons(self, root_causes: list[str]) -> list[str]:
        """从根因提取教训"""
        lessons = []
        for cause in root_causes:
            if "工具" in cause:
                lessons.append("下次遇到类似任务，先确认是否有合适的工具可用")
            if "预判" in cause:
                lessons.append("需要校准预判模型，或在 L2/L3 场景下更保守")
            if "skill" in cause:
                lessons.append("skill 选择需要更精确地匹配任务类型")
        if not lessons:
            lessons.append("需要记录更多上下文以便后续分析")
        return lessons

    def _generate_suggestions(
        self,
        trajectory: Trajectory,
        delta: float,
        root_causes: list[str]
    ) -> list[str]:
        """生成改进建议"""
        suggestions = []

        if delta < -10:
            suggestions.append(
                f"下次同类任务，预估分应调整为 {trajectory.phase1.predicted_score + delta:.0f} 分"
            )

        # 根据任务类型建议
        task_type = trajectory.task_type
        if task_type in ["code_generation", "refactoring"]:
            suggestions.append("建议启用 code-expert-skill 以提升编程质量")
        elif task_type in ["content_analysis", "keyword_research"]:
            suggestions.append("建议启用 seo-analysis-skill 以提升分析深度")

        # 根据 phase2 选择建议
        if trajectory.phase2.selected_skill:
            suggestions.append(
                f"当前启用的 {trajectory.phase2.selected_skill.name} 效果需观察，"
                "考虑替换为其他候选"
            )

        return suggestions


# 快捷函数
def quick_evaluate(
    trajectory: Trajectory,
    user_rating: int
) -> Phase4Result:
    """快速评估（只需用户评分）"""
    evaluator = QualityEvaluator()
    return evaluator.evaluate(trajectory, user_rating=user_rating)