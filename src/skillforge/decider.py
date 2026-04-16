# SkillForge 增强决策器（Phase 2）
# 根据缺口等级，决定下一步行动
#
# 五态设计借鉴 KnowSelf (ACL 2025) 情境判断研究：
#   - independent: Gap < 5   — 独立执行
#   - light_hints: 5-15    — 执行后轻提示
#   - suggest: 15-30        — 建议增强
#   - force: 30-50         — 强制增强
#   - out_of_scope: ≥ 50   — 超边界

from typing import Optional
from skillforge.models import SkillRecommendation, Decision


# 五态常量（参考 KnowSelf 三态扩展）
class GapState:
    INDEPENDENT = "independent"     # Gap < 5
    LIGHT_HINTS = "light_hints"     # 5 ≤ Gap < 15
    SUGGEST = "suggest"             # 15 ≤ Gap < 30
    FORCE = "force"                 # 30 ≤ Gap < 50
    OUT_OF_SCOPE = "out_of_scope"   # Gap ≥ 50


class EnhancementDecider:
    """
    Phase 2: 增强决策器

    根据 Phase 1 的 Gap 分析结果，决定五态行为之一：
    - independent: 直接执行，不提示用户
    - light_hints: 执行，结束时轻描"有优化空间"
    - suggest: 输出结果 + 询问"是否启用 skill"
    - force: 主动暂停，要求用户确认增强方案
    - out_of_scope: 坦白能力边界，建议换方案
    """

    def __init__(
        self,
        independent_max: float = 5.0,
        light_hints_max: float = 15.0,
        suggest_max: float = 30.0,
        force_max: float = 50.0,
        show_predictions: bool = True,
        show_recommendations: bool = True,
    ):
        self.independent_max = independent_max
        self.light_hints_max = light_hints_max
        self.suggest_max = suggest_max
        self.force_max = force_max
        self.show_predictions = show_predictions
        self.show_recommendations = show_recommendations

    def classify_state(self, gap: float) -> str:
        """根据 Gap 值分类到五态之一"""
        if gap < self.independent_max:
            return GapState.INDEPENDENT
        elif gap < self.light_hints_max:
            return GapState.LIGHT_HINTS
        elif gap < self.suggest_max:
            return GapState.SUGGEST
        elif gap < self.force_max:
            return GapState.FORCE
        else:
            return GapState.OUT_OF_SCOPE

    def decide(
        self,
        gap: float,
        predicted_score: float,
        recommendations: list[SkillRecommendation],
        task_types: list[str] = None,
    ) -> Decision:
        """
        根据 Gap 值做出决策。

        Args:
            gap: 能力缺口值（0-100）
            predicted_score: Phase 1 预估分 S
            recommendations: 候选 skill 列表（已按匹配度排序）
            task_types: 任务类型列表

        Returns:
            Decision 对象
        """
        state = self.classify_state(gap)

        if state == GapState.INDEPENDENT:
            return self._decide_independent(gap, predicted_score)

        if state == GapState.LIGHT_HINTS:
            return self._decide_light_hints(gap, predicted_score)

        if state == GapState.SUGGEST:
            return self._decide_suggest(gap, predicted_score, recommendations)

        if state == GapState.FORCE:
            return self._decide_force(gap, predicted_score, recommendations)

        # OUT_OF_SCOPE
        return self._decide_out_of_scope(gap, predicted_score, task_types)

    # ── 五态决策 ────────────────────────────────────────────

    def _decide_independent(self, gap: float, score: float) -> Decision:
        """独立：直接执行"""
        return Decision(
            action="execute_direct",
            message=f"任务与当前能力高度匹配（Gap {gap:.0f}分），直接执行。",
            wait_for_confirm=False,
            options=[],
            allow_direct_execution=True,
        )

    def _decide_light_hints(
        self, gap: float, score: float
    ) -> Decision:
        """轻提示：执行，结束时轻描"""
        return Decision(
            action="light_hints",
            message=(
                f"任务有一定挑战（Gap {gap:.0f}分，L2），"
                "执行过程中已尽力处理。\n"
                f"完成后轻提示：有优化空间可记录。"
            ),
            wait_for_confirm=False,
            options=[],
            allow_direct_execution=True,
        )

    def _decide_suggest(
        self,
        gap: float,
        score: float,
        recommendations: list[SkillRecommendation],
    ) -> Decision:
        """建议增强：等用户确认"""
        if not recommendations:
            return Decision(
                action="execute_direct",
                message=f"Gap {gap:.0f}分（L3），但未找到匹配 skill，直接执行。",
                wait_for_confirm=False,
                options=[],
                allow_direct_execution=True,
            )

        best = recommendations[0]
        enhanced = score + best.estimated_gain

        rec_lines = ""
        if self.show_recommendations:
            rec_lines = "\n候选 skill：\n" + "\n".join(
                f"  {i + 1}. {r.skill.name} "
                f"(覆盖缺口 {r.estimated_gain:.1f}分，"
                f"历史效果 {r.skill.avg_effectiveness:.0%})"
                for i, r in enumerate(recommendations[:3])
            )

        return Decision(
            action="suggest_enhancement",
            message=(
                f"任务评估：Gap {gap:.0f}分（L3）\n"
                f"当前预估 {score:.0f} 分 | "
                f"启用 [{best.skill.name}] 预计 {enhanced:.0f} 分\n"
                f"{rec_lines}\n\n"
                f'是否启用 skill 增强？（回复"是"继续，"直接做"跳过，"查看详情"看完整列表）'
            ),
            wait_for_confirm=True,
            options=recommendations[:3],
            allow_direct_execution=True,
        )

    def _decide_force(
        self,
        gap: float,
        score: float,
        recommendations: list[SkillRecommendation],
    ) -> Decision:
        """强制增强：要求用户明确确认"""
        options_text = ""
        if recommendations:
            for i, rec in enumerate(recommendations[:3], 1):
                enhanced = score + rec.estimated_gain
                options_text += (
                    f"  {i}. {rec.skill.name} "
                    f"(预计 {enhanced:.0f}分，{rec.skill.avg_effectiveness:.0%}历史效果)\n"
                )

        return Decision(
            action="force_enhancement",
            message=(
                f"⚠️ 任务难度较高（Gap {gap:.0f}分，L4 强制增强）\n"
                f"当前能力可能不足以达到最优结果，建议选择增强方案：\n\n"
                f"{options_text or '  （暂无匹配 skill）'}\n"
                f"  4. 我自己指定 skill\n"
                f"  5. 继续用当前能力执行（高风险）\n\n"
                f"请选择 1-5。"
            ),
            wait_for_confirm=True,
            options=recommendations[:3],
            allow_direct_execution=True,
        )

    def _decide_out_of_scope(
        self,
        gap: float,
        score: float,
        task_types: list[str] = None,
    ) -> Decision:
        """超边界：坦白拒绝"""
        suggestions = []
        if task_types:
            suggestions.append(f"任务类型：{', '.join(task_types)}")
        suggestions.extend([
            "建议：1) 换用更强大的模型  2) 拆解为多个子任务  3) 人工介入",
            "如果任务可以简化，请提供更具体的描述，我来重新评估。",
        ])

        return Decision(
            action="refuse",
            message=(
                f"⚠️ 任务难度超出当前能力范围（Gap {gap:.0f}分，L5 超边界）\n"
                f"预估分仅 {score:.0f}，强行执行质量难以保证。\n\n"
                + "\n".join(f"- {s}" for s in suggestions)
            ),
            wait_for_confirm=False,
            options=[],
            allow_direct_execution=False,
        )

    # ── 用户回复解析 ────────────────────────────────────────

    def parse_user_response(
        self,
        user_response: str,
        decision: Decision,
    ) -> tuple[str, Optional[SkillRecommendation]]:
        """
        解析用户回复，返回 (action, selected_skill)。

        支持：
        - "是"/"好"/"ok"/"y" → 启用最佳推荐
        - "直接做"/"跳过"/"不需要" → 直接执行
        - "1"/"2"/"3"/"4" → 选择对应选项
        - "查看详情" → 展开推荐详情
        """
        r = user_response.strip().lower()

        confirm_kw = {"是", "好", "ok", "oui", "y", "启用", "用", "确认"}
        skip_kw = {"直接做", "跳过", "不需要", "不用", "算了", "no", "skip"}

        if any(kw in r for kw in confirm_kw):
            return (
                "enhance",
                decision.options[0] if decision.options else None,
            )

        if any(kw in r for kw in skip_kw):
            return ("execute_direct", None)

        if r in {"1", "2", "3", "4"}:
            idx = int(r) - 1
            if idx < len(decision.options):
                return ("enhance", decision.options[idx])
            if idx == 3:
                return ("specify_skill", None)
            if idx == 4:
                return ("execute_anyway", None)

        if "详情" in r or "详细" in r:
            return ("show_details", None)

        return ("execute_direct", None)


# 快捷函数
def decide_enhancement(
    gap: float,
    predicted_score: float,
    recommendations: list[SkillRecommendation] = None,
) -> Decision:
    """
    快速决策（gap 值输入 → 自动分态 → 返回 Decision）。

    等价于：EnhancementDecider().decide(gap, score, recommendations)
    """
    decider = EnhancementDecider()
    return decider.decide(
        gap=gap,
        predicted_score=predicted_score,
        recommendations=recommendations or [],
    )
