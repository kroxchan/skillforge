# SkillForge Stage 3: 集成测试
# 测试 Orchestrator 与 MAR / 向量检索的串联调用链路

import sys, os, tempfile, shutil, json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skillforge.models import (
    Trajectory, Phase1Result, Phase2Result,
    Phase3Result, Phase4Result, Reflection,
)
from skillforge.mar import MARCoordinator
from skillforge.vector_search import (
    MockVectorSearchProvider,
    HybridSkillMatcher,
    create_vector_search,
)
from skillforge.evaluator import QualityEvaluator
from skillforge.engine import SkillForgeOrchestrator

_ORIG_CWD = Path.cwd()
_REGISTRY_SRC = Path("/Users/vivx/cursor/digital-human/skills/SKILLFORGE/skillforge-registry.yaml")


def new_helper():
    """每个测试用完全独立的临时目录"""
    tmpdir = Path(tempfile.mkdtemp())
    root = tmpdir / "run"
    root.mkdir()
    os.chdir(root)
    return tmpdir, root


def cleanup(tmpdir):
    os.chdir(_ORIG_CWD)
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── Fixtures ──────────────────────────────────────────────────

def _skills():
    from skillforge.models import Skill
    return [
        Skill(
            skill_id="code-expert", name="Code Expert Skill",
            description="专业代码编写与审查", domain=["programming"],
            task_types=["code_generation", "refactoring"],
            capability_gains={"precision": 10, "reasoning": 5},
            quality_tier="unknown", usage_count=5, avg_effectiveness=0.85,
            source="local", path="skills/code-expert",
            trigger_keywords=["写代码", "code", "python"],
        ),
        Skill(
            skill_id="seo-analysis", name="SEO Analysis Skill",
            description="搜索引擎优化分析", domain=["marketing"],
            task_types=["seo", "content_analysis"],
            capability_gains={"precision": 8},
            quality_tier="unknown", usage_count=3, avg_effectiveness=0.75,
            source="local", path="skills/seo-analysis",
            trigger_keywords=["seo", "关键词"],
        ),
    ]


def _trajectory(task_type="code_generation", predicted=80, actual=75):
    return Trajectory(
        task_id="it-001",
        task_description="写一个 Python 异步爬虫",
        task_type=task_type,
        timestamp=datetime.now(),
        phase1=Phase1Result(predicted_score=predicted, gap=20, gap_level="suggest"),
        phase2=Phase2Result(selected_skill=None, user_decision="skip"),
        phase3=Phase3Result(tools_used=["bash"], errors=[]),
        phase4=Phase4Result(actual_score=actual, outcome="success_within_tolerance"),
    )


# ── Stage 3-A: MAR 集成 ─────────────────────────────────────────

def test_evaluator_finalize_calls_mar():
    """MAR 已注入时，finalize() 调用 MAR 并填充 phase4.mar_result"""
    tmpdir, root = new_helper()
    try:
        index_file = root / "memory" / "capability-index.yaml"
        index_mgr = MagicMock()
        index_mgr.update = MagicMock()
        index_mgr.get_gap_adjustment = MagicMock(return_value=0.0)
        index_mgr.get_global_adjustment = MagicMock(return_value=0.0)
        index_mgr.get_entry = MagicMock(return_value=MagicMock(count=0, avg_delta=0.0))

        # 构造 mock MAR
        mock_mar = MARCoordinator(enabled=True)
        mock_response = json.dumps({
            "optimist": "代码结构清晰",
            "skeptic": "缺少错误处理",
            "domain_expert": "未处理反爬",
            "judge": {
                "final_score": 72,
                "delta_adjustment": -3,
                "lesson": "异步任务需完善错误处理",
                "trigger_improvement": "是",
                "improvement_note": "生成 SKILL.md",
            }
        })
        with patch.object(mock_mar._adapter, "_call_llm", return_value=mock_response):
            evaluator = QualityEvaluator(index_mgr=index_mgr, mar_coordinator=mock_mar)
            traj = _trajectory()
            phase4 = Phase4Result(actual_score=75, outcome="success_within_tolerance")

            result = evaluator.finalize(traj, phase4)

        assert result["trajectory_written"] is True
        assert phase4.mar_result is not None
        assert phase4.mar_result["optimist"] == "代码结构清晰"
        assert phase4.mar_result["judge"]["final_score"] == 72
        assert phase4.mar_result["judge"]["trigger_improvement"] is True
        print("  [PASS] Evaluator finalize(): 调用 MAR，填充 mar_result")
    finally:
        cleanup(tmpdir)


def test_evaluator_finalize_skips_mar_when_disabled():
    """MAR 未注入时，finalize() 不调用 MAR，phase4.mar_result 保持 None"""
    tmpdir, root = new_helper()
    try:
        index_file = root / "memory" / "capability-index.yaml"
        index_mgr = MagicMock()
        index_mgr.update = MagicMock()

        evaluator = QualityEvaluator(index_mgr=index_mgr)  # 无 mar_coordinator
        traj = _trajectory()
        phase4 = Phase4Result(actual_score=75, outcome="success_within_tolerance")

        result = evaluator.finalize(traj, phase4)

        assert result["trajectory_written"] is True
        assert phase4.mar_result is None
        print("  [PASS] Evaluator finalize(): MAR 未注入时不调用")
    finally:
        cleanup(tmpdir)


def test_mar_trigger_improvement_flag():
    """MAR Judge 触发改进时，trigger_improvement 为 True"""
    tmpdir, root = new_helper()
    try:
        mock_mar = MARCoordinator(enabled=True)
        mock_response = json.dumps({
            "optimist": "OK",
            "skeptic": "issues",
            "domain_expert": "blind spots",
            "judge": {
                "final_score": 70,
                "delta_adjustment": -5,
                "lesson": "需要改进错误处理",
                "trigger_improvement": "是",
                "improvement_note": "建议生成 error-handling skill",
            }
        })
        with patch.object(mock_mar._adapter, "_call_llm", return_value=mock_response):
            evaluator = QualityEvaluator(mar_coordinator=mock_mar)
            traj = _trajectory()
            phase4 = Phase4Result(actual_score=70)
            evaluator.finalize(traj, phase4)

        assert phase4.mar_result["judge"]["trigger_improvement"] is True
        assert phase4.mar_result["judge"]["improvement_note"] == "建议生成 error-handling skill"
        print("  [PASS] MAR trigger_improvement: 是 → 记录 improvement_note")
    finally:
        cleanup(tmpdir)


# ── Stage 3-B: 向量检索集成 ─────────────────────────────────────

def test_evaluator_with_hybrid_matcher():
    """Evaluator 可接受 hybrid_matcher（混合检索匹配器）"""
    tmpdir, root = new_helper()
    try:
        index_mgr = MagicMock()
        index_mgr.update = MagicMock()

        provider = MockVectorSearchProvider()
        provider.add_skills(_skills())
        matcher = HybridSkillMatcher(
            registry_skills=_skills(),
            vector_search=provider,
            keyword_weight=0.6,
            semantic_weight=0.4,
        )

        evaluator = QualityEvaluator(index_mgr=index_mgr, hybrid_matcher=matcher)
        assert evaluator.hybrid_matcher is matcher
        print("  [PASS] Evaluator: hybrid_matcher 注入成功")
    finally:
        cleanup(tmpdir)


def test_hybrid_matcher_keyword_priority():
    """HybridSkillMatcher: 关键词命中的 skill 排在最前"""
    provider = MockVectorSearchProvider()
    provider.add_skills(_skills())
    matcher = HybridSkillMatcher(
        registry_skills=_skills(),
        vector_search=provider,
        keyword_weight=0.6,
        semantic_weight=0.4,
    )

    results = matcher.search("seo analysis", task_type=None, top_k=5)
    ids = [r.skill.skill_id for r in results]
    assert ids[0] == "seo-analysis"
    print("  [PASS] HybridMatcher: 关键词命中优先排序")


def test_hybrid_matcher_no_vector_fallback():
    """HybridSkillMatcher: vector_search=None 时回退到纯关键词"""
    matcher = HybridSkillMatcher(registry_skills=_skills(), vector_search=None)
    results = matcher.search("python 代码", task_type=None, top_k=5)
    ids = [r.skill.skill_id for r in results]
    assert "code-expert" in ids
    print("  [PASS] HybridMatcher: 无向量时回退到关键词")


# ── Stage 3-C: Orchestrator 串联集成 ─────────────────────────────

def test_orchestrator_mar_enabled():
    """Orchestrator mar_enabled=True → MAR 组件初始化"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
            mar_enabled=True,
        )

        assert orch.mar is not None
        assert isinstance(orch.mar, MARCoordinator)
        assert orch.mar.enabled is True
        print("  [PASS] Orchestrator: mar_enabled=True → MAR 初始化")
    finally:
        cleanup(tmpdir)


def test_orchestrator_vector_search_enabled():
    """Orchestrator vector_search_enabled=True → HybridSkillMatcher 初始化"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
            vector_search_enabled=True,
        )

        assert orch._hybrid_matcher is not None
        assert isinstance(orch._hybrid_matcher, HybridSkillMatcher)
        # 向量提供器也应有
        assert orch._vector_provider is not None
        print("  [PASS] Orchestrator: vector_search_enabled=True → HybridMatcher 初始化")
    finally:
        cleanup(tmpdir)


def test_orchestrator_run_with_mar_evaluates():
    """Orchestrator.run() + evaluate_and_close() + MAR → phase4.mar_result 被填充"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
            mar_enabled=True,
        )

        llm_response = json.dumps({
            "predicted_score": 75,
            "total_gap": 25,
            "gaps": {"precision": 20},
            "capability_dimensions": {"gaps": {"precision": 20}},
            "task_types": ["code_generation"],
            "task_difficulty": 85,
            "recommended_skill_types": ["code"],
        })

        result = orch.run(
            task_description="写一个 Python 爬虫",
            llm_response=llm_response,
            user_decision="skip",
        )

        # Mock MAR LLM 响应
        mock_mar_response = json.dumps({
            "optimist": "异步设计合理",
            "skeptic": "缺少超时机制",
            "domain_expert": "未考虑反爬",
            "judge": {
                "final_score": 70,
                "delta_adjustment": -5,
                "lesson": "网络 IO 需超时机制",
                "trigger_improvement": "是",
                "improvement_note": "生成网络任务 SKILL.md",
            }
        })

        with patch.object(orch.mar._adapter, "_call_llm", return_value=mock_mar_response):
            closed = orch.evaluate_and_close(result, user_rating=5)

        assert closed.phase4.mar_result is not None
        assert closed.phase4.mar_result["judge"]["trigger_improvement"] is True
        assert closed.phase4.mar_result["judge"]["lesson"] == "网络 IO 需超时机制"
        print("  [PASS] Orchestrator run+close+MAR: mar_result 完整填充")
    finally:
        cleanup(tmpdir)


def test_orchestrator_run_with_vector_search_uses_hybrid():
    """Orchestrator vector_search_enabled=True → Phase 2 使用 HybridSkillMatcher"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
            vector_search_enabled=True,
        )

        # Mock HybridSkillMatcher.search 返回特定结果
        from skillforge.models import Skill, SkillRecommendation

        mock_rec = SkillRecommendation(
            skill=Skill(
                skill_id="seo-analysis",
                name="SEO Analysis Skill",
                description="SEO analysis",
                domain=["marketing"],
                task_types=["seo"],
                capability_gains={"precision": 8},
                quality_tier="unknown",
                usage_count=3,
                avg_effectiveness=0.75,
                source="local",
                path="skills/seo-analysis",
                trigger_keywords=["seo", "关键词"],
            ),
            match_score=0.9,
            estimated_gain=8.0,
            reason="keyword",
        )

        from skillforge.models import Skill, SkillRecommendation

        fake_rec = SkillRecommendation(
            skill=Skill(
                skill_id="seo-analysis", name="SEO Analysis Skill",
                description="SEO analysis", domain=["marketing"],
                task_types=["seo"], capability_gains={"precision": 8},
                quality_tier="unknown", usage_count=3, avg_effectiveness=0.75,
                source="local", path="skills/seo-analysis",
                trigger_keywords=["seo", "关键词"],
            ),
            match_score=0.9,
            estimated_gain=8.0,
            reason="keyword",
        )

        call_log = {"count": 0, "task_type": None}

        def tracking_search(query, task_type, top_k):
            call_log["count"] += 1
            call_log["task_type"] = task_type
            return [fake_rec]

        # 替换 search 方法为跟踪版本
        original_search = orch._hybrid_matcher.search
        orch._hybrid_matcher.search = tracking_search

        llm_response = json.dumps({
            "predicted_score": 70,
            "total_gap": 30,
            "gaps": {"precision": 15},
            "capability_dimensions": {"gaps": {"precision": 15}},
            "task_types": ["seo"],
            "task_difficulty": 80,
            "recommended_skill_types": ["marketing"],
        })
        result = orch.run(
            task_description="分析网站 SEO 关键词",
            llm_response=llm_response,
            user_decision="auto",
        )

        assert call_log["count"] == 1
        assert call_log["task_type"] == "seo"
        print("  [PASS] Orchestrator run(): Phase 2 使用 HybridSkillMatcher.search")
    finally:
        cleanup(tmpdir)


def test_orchestrator_both_stage3_features():
    """Orchestrator 同时启用 MAR + 向量检索 → 两个组件都初始化"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
            mar_enabled=True,
            vector_search_enabled=True,
        )

        assert orch.mar is not None
        assert orch._hybrid_matcher is not None
        assert orch._vector_provider is not None
        # Evaluator 注入验证
        assert orch.evaluator.mar is orch.mar
        assert orch.evaluator.hybrid_matcher is orch._hybrid_matcher
        print("  [PASS] Orchestrator: MAR + 向量检索双组件初始化正确")
    finally:
        cleanup(tmpdir)


def test_orchestrator_both_stage3_and_close():
    """Orchestrator 双 Stage 3 → 端到端 run + close，MAR 结果写入 phase4"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
            mar_enabled=True,
            vector_search_enabled=True,
        )

        llm_response = json.dumps({
            "predicted_score": 72,
            "total_gap": 28,
            "gaps": {"reasoning": 25},
            "capability_dimensions": {"gaps": {"reasoning": 25}},
            "task_types": ["research"],
            "task_difficulty": 80,
            "recommended_skill_types": ["research"],
        })

        with patch.object(orch._hybrid_matcher, "search", return_value=[]):
            result = orch.run(
                task_description="深度研究 AI Agent 最新进展",
                llm_response=llm_response,
                user_decision="skip",
            )

        mock_mar_response = json.dumps({
            "optimist": "结构清晰",
            "skeptic": "深度不足",
            "domain_expert": "缺少引用来源",
            "judge": {
                "final_score": 68,
                "delta_adjustment": -4,
                "lesson": "研究任务需引用和来源标注",
                "trigger_improvement": "是",
                "improvement_note": "建议生成 research-skill",
            }
        })

        with patch.object(orch.mar._adapter, "_call_llm", return_value=mock_mar_response):
            closed = orch.evaluate_and_close(result, user_rating=3)

        # 双闭环验证
        assert closed.index_updated is True
        assert closed.phase4.mar_result is not None
        assert closed.phase4.mar_result["judge"]["trigger_improvement"] is True
        assert closed.phase4.mar_result["judge"]["lesson"] == "研究任务需引用和来源标注"

        # L1 轨迹已写入
        traj_dir = root / "memory" / "trajectories"
        traj_file = list(traj_dir.rglob("*.json"))
        assert len(traj_file) >= 1

        print("  [PASS] 双 Stage 3 端到端: run + close + MAR + L1 写盘")
    finally:
        cleanup(tmpdir)


# ── Stage 3-D: 零依赖降级 ─────────────────────────────────────────

def test_stage3_disabled_by_default():
    """Stage 3 默认关闭时，Orchestrator 不加载任何 Stage 3 组件"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
        )

        assert orch.mar is None
        assert orch._hybrid_matcher is None
        assert orch._vector_provider is None
        print("  [PASS] Stage 3 默认关闭，零额外组件开销")
    finally:
        cleanup(tmpdir)


# ── 运行 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== SkillForge Stage 3 集成测试 ===\n")
    print("-- MAR 集成 --")
    test_evaluator_finalize_calls_mar()
    test_evaluator_finalize_skips_mar_when_disabled()
    test_mar_trigger_improvement_flag()
    print("-- 向量检索集成 --")
    test_evaluator_with_hybrid_matcher()
    test_hybrid_matcher_keyword_priority()
    test_hybrid_matcher_no_vector_fallback()
    print("-- Orchestrator 串联 --")
    test_orchestrator_mar_enabled()
    test_orchestrator_vector_search_enabled()
    test_orchestrator_run_with_mar_evaluates()
    test_orchestrator_run_with_vector_search_uses_hybrid()
    test_orchestrator_both_stage3_features()
    test_orchestrator_both_stage3_and_close()
    print("-- 零依赖降级 --")
    test_stage3_disabled_by_default()
    print("\n[ALL PASS] 13/13 集成测试通过\n")
