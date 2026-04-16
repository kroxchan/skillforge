# SkillForge 能力预判引擎（Phase 1）
# 基于任务描述，通过 CoT 推理预测任务难度和 Agent 能力缺口

import uuid
import time
import json
from datetime import datetime
from typing import Literal, Optional

from skillforge.models import (
    GapAnalysis, Phase1Result, Phase2Result, Phase3Result, Phase4Result,
    Trajectory, Decision, Reflection, SkillForgeResult,
)
from skillforge.registry import SkillRegistry
from skillforge.decider import EnhancementDecider
from skillforge.evaluator import QualityEvaluator
from skillforge.executor import EnhancementExecutor
from skillforge.indexer import IndexManager
from skillforge.tracing import PhaseTiming, TimingLogger

# Stage 3（可选）
from skillforge.config import get_config
from skillforge.mar import MARCoordinator
from skillforge.vector_search import (
    HybridSkillMatcher,
    create_vector_search,
    VectorSearchProvider,
)

# Stage 4（可选）
from skillforge.reflexion import ReflectionLoader, format_as_context

# Forger
from skillforge.forger import count_successful_trajectories, generate_forger_draft


# Phase 1 分析 Prompt（供 Agent 直接使用）
PHASE1_PROMPT_TEMPLATE = """你是一个专业的能力评估专家。请分析以下任务，评估其难度和你的能力匹配度。

任务：{task_description}

请从以下 6 个维度分析（每个维度 0-100 分）：

1. 精确性（precision）：做好这个任务需要多精确？无幻觉？无错误？
   - 任务需求：__分（0-100）
   - 我的能力：__分（0-100）
   - 缺口：__分

2. 创意性（creativity）：需要多少创造性表达？
   - 任务需求：__分
   - 我的能力：__分
   - 缺口：__分

3. 领域知识（domain_knowledge）：需要多少专业领域知识？
   - 任务需求：__分
   - 我的能力：__分
   - 缺口：__分

4. 工具使用（tool_usage）：需要调用多少外部工具/API？
   - 任务需求：__分
   - 我的能力：__分
   - 缺口：__分

5. 推理能力（reasoning）：需要多复杂的逻辑推理？
   - 任务需求：__分
   - 我的能力：__分
   - 缺口：__分

6. 执行效率（speed）：需要在多短时间内完成？
   - 任务需求：__分
   - 我的能力：__分
   - 缺口：__分

请输出 JSON 格式：
{{
  "task_requirements": {{
    "precision": [0-100],
    "creativity": [0-100],
    "domain_knowledge": [0-100],
    "tool_usage": [0-100],
    "reasoning": [0-100],
    "speed": [0-100]
  }},
  "agent_capabilities": {{
    "precision": [0-100],
    "creativity": [0-100],
    "domain_knowledge": [0-100],
    "tool_usage": [0-100],
    "reasoning": [0-100],
    "speed": [0-100]
  }},
  "gaps": {{
    "precision": [task - agent],
    ...
  }},
  "total_gap": [最大缺口维度 或 加权和],
  "gap_level": "L1/L2/L3",
  "predicted_score": [100 - total_gap],
  "task_types": ["推断的任务类型列表"],
  "recommended_skill_types": ["建议的 skill 领域"]
}}
"""


class SkillForgeEngine:
    """
    Phase 1: 任务分析 & 难度预判引擎
    
    使用方法（供 Agent 直接调用）：
    
    1. 收集任务描述
    2. 调用 analyze(task_description)
    3. 根据返回的 gap_level 决定后续行为
    """

    def __init__(self, gap_thresholds=(10, 25)):
        self.l1_max = gap_thresholds[0]
        self.l2_max = gap_thresholds[1]

    def build_prompt(self, task_description: str) -> str:
        """构建 Phase 1 分析 Prompt"""
        return PHASE1_PROMPT_TEMPLATE.format(
            task_description=task_description
        )

    def parse_analysis(self, llm_response: str) -> Phase1Result:
        """
        解析 LLM 返回的分析结果。
        实际使用时由 LLM 直接输出 JSON，这里做结构化解析。
        """
        import json
        import re

        # 尝试提取 JSON 块（支持多层嵌套）
        stripped = llm_response.strip()

        # 尝试直接解析（最快路径）
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            # 去掉可能的 markdown code fence
            fenced = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.MULTILINE)
            fenced = re.sub(r"\s*```$", "", fenced, flags=re.MULTILINE)
            try:
                data = json.loads(fenced.strip())
            except json.JSONDecodeError:
                # 兜底：找第一对 {} 包裹的完整 JSON
                data = self._extract_json_fallback(stripped)

        gaps = data.get("gaps", {})
        total_gap = data.get("total_gap", max(gaps.values()) if gaps else 10)

        return Phase1Result(
            predicted_score=data.get("predicted_score", 100 - total_gap),
            task_difficulty=data.get("task_difficulty", 100 - total_gap + 20),
            gap=total_gap,
            gap_level=self._classify_gap(total_gap),
            capability_dimensions=data,
            task_types=data.get("task_types", []),
            recommended_skill_types=data.get("recommended_skill_types", []),
        )

    def _classify_gap(
        self,
        gap: float
    ) -> Literal["L1", "L2", "L3"]:
        """根据缺口值分类"""
        if gap < self.l1_max:
            return "L1"
        elif gap < self.l2_max:
            return "L2"
        else:
            return "L3"

    def summarize_for_user(self, result: Phase1Result) -> str:
        """生成用户可见的预判摘要"""
        level_descriptions = {
            "L1": "任务与你的能力高度匹配，直接执行即可。",
            "L2": "任务有一定挑战，建议考虑启用专业 skill 增强。",
            "L3": "任务难度较高，当前能力可能有明显缺口，建议优先选择增强方案。"
        }

        return (
            f"任务分析结果：\n"
            f"- 预估分数：{result.predicted_score} 分\n"
            f"- 缺口等级：{result.gap_level}（{level_descriptions.get(result.gap_level, '')}）\n"
            f"- 缺口分：{result.gap} 分"
        )

    @staticmethod
    def _extract_json_fallback(text: str) -> dict:
        """兜底：找第一对最外层 {} 包裹的完整 JSON"""
        import re
        # 找第一个 { 和最后一个 } 作为 JSON 边界
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace >= 0 and last_brace > first_brace:
            candidate = text[first_brace : last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        return {}


# ── Full-Phase Orchestrator ──────────────────────────────

class SkillForgeOrchestrator:
    """
    完整四 Phase 串联执行器。

    流程：
        Phase 1 → Phase 2 → [用户确认?] → Phase 3 → Phase 4 → 记忆闭环
        Stage 3（可选）：MAR 辩论评估 + 混合语义检索

    适用于：
    - CLI `run` 命令
    - Agent 端到端执行
    """

    def __init__(
        self,
        registry_path: str = "skillforge-registry.yaml",
        index_path: Optional[str] = None,
        memory_dir: str = "memory",
        timings_path: Optional[str] = None,
        mar_enabled: bool = False,
        vector_search_enabled: bool = False,
        reflexion_enabled: bool = False,
    ):
        self.registry = SkillRegistry(registry_path=registry_path)
        self.index_mgr = IndexManager(index_path=index_path or f"{memory_dir}/capability-index.yaml")
        self.memory_dir = memory_dir
        self._timing_logger = TimingLogger(timings_path or f"{memory_dir}/timings.yaml")

        # ── Stage 3 初始化 ────────────────────────────────────────
        self._stage3_enabled = mar_enabled or vector_search_enabled
        self._config = get_config()

        # MAR 多角色辩论（默认关闭）
        self.mar: Optional[MARCoordinator] = None
        if mar_enabled:
            s3_cfg = self._config.stage3
            self.mar = MARCoordinator(
                enabled=True,
                provider=s3_cfg.mar.provider,
                llm_endpoint=s3_cfg.mar.llm_endpoint,
                model=s3_cfg.mar.llm_model,
            )

        # 混合语义检索（默认关闭）
        self._vector_provider: Optional[VectorSearchProvider] = None
        self._hybrid_matcher: Optional[HybridSkillMatcher] = None
        if vector_search_enabled:
            vs_cfg = self._config.stage3.vector_search
            self._vector_provider = create_vector_search(
                provider=vs_cfg.provider,
                persist_dir=vs_cfg.chroma.persist_dir,
                model_name=vs_cfg.chroma.model,
                distance_metric=vs_cfg.chroma.distance_metric,
            )
            all_skills = self.registry.list_skills()
            self._hybrid_matcher = HybridSkillMatcher(
                registry_skills=all_skills,
                vector_search=self._vector_provider,
                keyword_weight=vs_cfg.keyword_weight,
                semantic_weight=vs_cfg.semantic_weight,
            )

        # QualityEvaluator 注入 Stage 3 组件
        self.evaluator = QualityEvaluator(
            index_mgr=self.index_mgr,
            mar_coordinator=self.mar,
            hybrid_matcher=self._hybrid_matcher,
            memory_dir=memory_dir,  # Stage 4: L2 反思写入路径
        )
        self.executor = EnhancementExecutor(memory_dir=f"{memory_dir}/trajectories")

        # ── Stage 4 初始化 ────────────────────────────────────────
        self._reflexion_loader: Optional[ReflectionLoader] = None
        if reflexion_enabled:
            s4_cfg = self._config.stage4.reflexion
            self._reflexion_loader = ReflectionLoader(
                memory_dir=memory_dir,
                max_entries=s4_cfg.max_entries,
                max_age_days=s4_cfg.max_age_days,
                min_delta_threshold=s4_cfg.min_delta_threshold,
                enabled=True,  # 构造函数参数优先，不读 config
            )

    def _load_l2_context(self, task_type: str) -> str:
        """加载 L2 反思上下文（Stage 4）"""
        if self._reflexion_loader is None:
            return ""
        return self._reflexion_loader.load_context(task_type)

    def run(
        self,
        task_description: str,
        llm_response: str,
        user_rating: Optional[int] = None,
        user_decision: str = "auto",
    ) -> SkillForgeResult:
        """
        串联 Phase 1-4，执行完整循环。

        Args:
            task_description: 原始任务描述
            llm_response: Phase 1 LLM 分析结果的原始文本（JSON 格式）
            user_rating: Phase 4 用户评分（1-5）
            user_decision: Phase 2 用户决策（auto/skip/enhance/number）
                           auto=根据 gap 自动选择；skip=强制跳过 skill；enhance=强制启用；number=数字选对应 option

        Returns:
            SkillForgeResult，包含完整轨迹、L0 更新状态、skill effectiveness 更新状态
        """
        task_id = f"sf-{uuid.uuid4().hex[:8]}"
        t0 = time.monotonic()

        # ── Phase 1: 预判 ────────────────────────────────────
        engine = SkillForgeEngine()
        phase1 = engine.parse_analysis(llm_response)

        task_type = phase1.task_types[0] if phase1.task_types else "other"

        # Stage 4: 加载 L2 反思上下文（供外部注入或诊断）
        l2_context = self._load_l2_context(task_type)
        if l2_context:
            # 将 L2 反思记录到 phase1 的 capability_dimensions 中，供后续使用
            phase1.capability_dimensions["_l2_reflection_context"] = l2_context

        # 读取 L0 索引中的校准值
        gap_adj = self.index_mgr.get_gap_adjustment(task_type)
        global_adj = self.index_mgr.get_global_adjustment()
        adjusted_gap = max(0.0, phase1.gap + gap_adj + global_adj)
        adjusted_score = max(0.0, min(100.0, 100 - adjusted_gap))

        p1_ms = (time.monotonic() - t0) * 1000

        # ── Phase 2: 决策 ────────────────────────────────────
        decider = EnhancementDecider()
        capability_gaps = phase1.capability_dimensions.get("gaps", {})
        if not capability_gaps:
            capability_gaps = {"estimated": adjusted_gap}

        # Stage 3 混合检索（keyword + 向量语义双路召回）
        if self._hybrid_matcher is not None:
            recommendations = self._hybrid_matcher.search(
                query=task_description,
                task_type=task_type,
                top_k=5,
            )
        else:
            recommendations = self.registry.match(
                task_types=[task_type],
                capability_gaps=capability_gaps,
                top_k=5,
            )
        decision = decider.decide(
            gap=adjusted_gap,
            predicted_score=adjusted_score,
            recommendations=recommendations,
            task_types=[task_type],
        )

        # 用户决策覆盖
        if user_decision != "auto":
            parsed = decider.parse_user_response(user_decision, decision)
            action, selected = parsed
            if action == "execute_direct":
                decision = Decision(action="execute_direct", message="用户选择跳过 skill")
            elif action == "enhance" and selected:
                decision = Decision(action="suggest_enhancement", options=[selected])

        # selected_skill
        selected_skill = None
        user_decision_str = decision.action
        if decision.options and decision.action in ("suggest_enhancement", "force_enhancement"):
            selected_skill = decision.options[0].skill

        p2_ms = (time.monotonic() - t0) * 1000 - p1_ms

        # ── Phase 3: 增强 prompt 构建 ────────────────────────
        phase3_context = self.executor.build_enhanced_prompt(
            skill=selected_skill,
            task_context=engine.summarize_for_user(phase1),
            task_description=task_description,
        )
        p3_ms = (time.monotonic() - t0) * 1000 - p1_ms - p2_ms

        # 构建轨迹（Phase 3 的执行由外部完成，这里只记录 context）
        phase3_result = Phase3Result(
            tools_used=[],
            errors=[],
            skill_content_used=selected_skill.name if selected_skill else "",
        )

        phase2_result = Phase2Result(
            selected_skill=selected_skill,
            enhanced_estimate=(
                adjusted_score + decision.options[0].estimated_gain
                if (decision.options and selected_skill)
                else adjusted_score
            ),
            user_decision=user_decision_str,
        )

        trajectory = Trajectory(
            task_id=task_id,
            task_description=task_description,
            task_type=task_type,
            timestamp=datetime.now(),
            phase1=Phase1Result(
                predicted_score=adjusted_score,
                task_difficulty=phase1.task_difficulty,
                gap=adjusted_gap,
                gap_level=phase1.gap_level,
                capability_dimensions=phase1.capability_dimensions,
                task_types=[task_type],
                recommended_skill_types=phase1.recommended_skill_types,
            ),
            phase2=phase2_result,
            phase3=phase3_result,
            phase4=Phase4Result(),  # 空占位，由 evaluate_and_close 填充
        )

        phase4 = Phase4Result(actual_score=50.0, outcome="success")
        if user_rating is not None:
            phase4 = self.evaluator.evaluate(trajectory, user_rating=user_rating)
            trajectory.phase4 = phase4  # 写回引用

        p4_ms = (time.monotonic() - t0) * 1000 - p1_ms - p2_ms - p3_ms

        total_ms = (time.monotonic() - t0) * 1000

        # 记录 timing
        timing = PhaseTiming(
            task_id=task_id,
            task_type=task_type,
            gap_state=decision.action,
            phase1_ms=round(p1_ms, 1),
            phase2_ms=round(p2_ms, 1),
            phase3_ms=round(p3_ms, 1),
            phase4_ms=round(p4_ms, 1),
            total_ms=round(total_ms, 1),
            predicted_score=adjusted_score,
            actual_score=phase4.actual_score,
            delta=phase4.actual_score - adjusted_score,
            outcome=phase4.outcome,
            timestamp=datetime.now().isoformat(),
        )
        self._timing_logger.write(timing)

        return SkillForgeResult(
            task_id=task_id,
            task_description=task_description,
            task_type=task_type,
            trajectory=trajectory,
            phase4=phase4,
            index_updated=False,
            effectiveness_updated=False,
            decision=decision,
            phase3_context=phase3_context,
        )

    def evaluate_and_close(
        self,
        result: SkillForgeResult,
        actual_score: float,
        user_rating: Optional[int] = None,
        llm_self_rating: Optional[dict] = None,
    ) -> SkillForgeResult:
        """
        Phase 4 评估 + 记忆闭环。

        在外部执行完任务后调用，完成：
        1. Phase 4 评估
        2. L1 轨迹写入
        3. L0 索引更新
        4. skill effectiveness 校准
        """
        t_close = time.monotonic()
        # 评估
        phase4 = self.evaluator.evaluate(
            result.trajectory,
            user_rating=user_rating,
            llm_self_rating=llm_self_rating,
            tool_verification={"passed": actual_score >= 60, "test_count": 1}
            if result.task_type == "code_generation"
            else None,
        )
        result.trajectory.phase4 = phase4  # 写回引用

        # 用真实的 actual_score 更新 Phase4Result（保持 outcome 来自 evaluator）
        phase4.actual_score = actual_score
        result.phase4 = phase4

        # 反思（delta < -5 才生成）
        delta = actual_score - result.trajectory.phase1.predicted_score
        reflection = None
        if delta < -5:
            reflection = self.evaluator.generate_reflection(
                result.trajectory, phase4
            )

        # 记忆闭环：L1 轨迹写入 + L0 索引更新
        closed = self.evaluator.finalize(
            result.trajectory,
            phase4,
            reflection=reflection,
        )

        # skill effectiveness 校准
        if result.trajectory.phase2.selected_skill:
            est_gain = (
                result.trajectory.phase2.enhanced_estimate
                - result.trajectory.phase1.predicted_score
            )
            self.registry.update_effectiveness(
                skill_id=result.trajectory.phase2.selected_skill.skill_id,
                actual_gain=max(0, delta + est_gain),
                estimated_gain=max(0, est_gain),
            )
            self.registry.save()

        # 记录耗时
        close_ms = (time.monotonic() - t_close) * 1000
        timing = PhaseTiming(
            task_id=result.task_id,
            task_type=result.task_type,
            gap_state=result.decision.action,
            phase4_ms=round(close_ms, 1),
            total_ms=round(close_ms, 1),
            predicted_score=result.trajectory.phase1.predicted_score,
            actual_score=actual_score,
            delta=delta,
            outcome=phase4.outcome,
            timestamp=datetime.now().isoformat(),
        )
        self._timing_logger.write(timing)

        # 更新返回结果
        result.phase4 = phase4
        result.index_updated = closed["index_updated"]
        result.effectiveness_updated = (
            result.trajectory.phase2.selected_skill is not None
        )

        # ── Forger 触发检测 ────────────────────────────────────
        # 同类任务成功次数 >= forger_trigger（默认 3）时，生成 SKILL.md 草稿
        forger_cfg = self._config.evaluation
        successes = count_successful_trajectories(self.memory_dir, result.task_type)
        if len(successes) >= forger_cfg.forger_trigger:
            draft_path = generate_forger_draft(
                task_type=result.task_type,
                trajectories=successes,
                memory_dir=self.memory_dir,
            )
            result.forger_draft_path = draft_path

        return result


# 快捷函数（供 Agent 直接调用）
def quick_analyze(task_description: str) -> Phase1Result:
    """
    快速分析任务难度。
    
    实际由 Agent 调用 LLM 填写 PHASE1_PROMPT_TEMPLATE，
    然后用 SkillForgeEngine().parse_analysis() 解析结果。
    """
    engine = SkillForgeEngine()
    prompt = engine.build_prompt(task_description)
    # Agent 需要将 prompt 发送给 LLM，然后将结果传入 parse_analysis
    return prompt  # 返回 prompt，供 Agent 使用
