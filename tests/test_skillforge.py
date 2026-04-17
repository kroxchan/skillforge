# SkillForge 端到端测试

import sys, os, tempfile, shutil, json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skillforge.indexer import IndexManager
from skillforge.evaluator import QualityEvaluator
from skillforge.engine import SkillForgeEngine
from skillforge.decider import EnhancementDecider
from skillforge.registry import SkillRegistry
from skillforge.models import (
    Trajectory, Phase1Result, Phase2Result,
    Phase3Result, Phase4Result, Reflection,
)

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


# ── 测试 ────────────────────────────────────────────────

def test_index_manager_write_and_read():
    """L0: 移动平均 -> 持久化 -> 重加载"""
    tmpdir, root = new_helper()
    try:
        index_file = root / "memory" / "capability-index.yaml"
        index = IndexManager(index_path=str(index_file))

        # 新设计：delta 由用户评分独立传入（= (rating-3)*20），actual = predicted
        # delta1=-16（rating=3 → 符合预期，delta=0；这里用 -16 模拟 rating=2 偏悲观）
        # avg_delta = 0.2*(-16) + 0.8*0 = -3.2
        index.update("code_generation", 80, 80, delta=-16, timestamp="2026-04-15")
        e = index.index.task_type_index["code_generation"]
        assert e.count == 1
        assert abs(e.avg_delta - (-3.2)) < 0.01

        # delta2=+24（rating=4 → delta=(4-3)*20=+20；这里用+24 模拟超预期）
        # avg_delta = 0.2*(+24) + 0.8*(-3.2) = +2.24
        index.update("code_generation", 80, 80, delta=+24, timestamp="2026-04-16")
        e = index.index.task_type_index["code_generation"]
        assert e.count == 2
        assert abs(e.avg_delta - (+2.24)) < 0.01

        # 重加载验证
        index2 = IndexManager(index_path=str(index_file))
        assert index2.index.task_type_index["code_generation"].count == 2

        print("  [PASS] L0 Index: 移动平均 -> 持久化 -> 重加载")
    finally:
        cleanup(tmpdir)


def test_decider_five_states():
    """五态决策"""
    decider = EnhancementDecider()
    cases = [
        (3.0,  "independent"),
        (10.0, "light_hints"),
        (22.0, "suggest"),
        (40.0, "force"),
        (60.0, "out_of_scope"),
    ]
    for gap, expected in cases:
        assert decider.classify_state(gap) == expected
    print("  [PASS] Decider: 五态分类正确")


def test_registry_effectiveness():
    """Registry: capability_gains 动态校准（不依赖预置 skill，v0.2.6 起 Registry 默认空）"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        # v0.2.6：Registry 默认空，测试注入一个临时 skill
        reg_file.write_text(
            "version: '1.0'\n"
            "updated_at: '2026-04-17'\n"
            "skills:\n"
            "  - skill_id: test-skill\n"
            "    name: Test Skill\n"
            "    description: 测试专用\n"
            "    domain: [testing]\n"
            "    task_types: [test]\n"
            "    capability_gains:\n"
            "      precision: 20\n"
            "    quality_tier: L2\n"
            "    trigger_keywords: [test]\n"
            "    avg_effectiveness: 0.5\n"
            "    usage_count: 0\n",
            encoding="utf-8",
        )

        registry = SkillRegistry(registry_path=str(reg_file))
        before = registry.find_by_id("test-skill")
        assert before is not None, "注入的临时 skill 应可被 Registry 找到"
        assert before.usage_count == 0
        assert abs(before.avg_effectiveness - 0.5) < 0.01

        # ratio = 25/20 = 1.25; new = 0.5 * 0.7 + 1.25 * 0.3 = 0.725
        registry.update_effectiveness("test-skill", actual_gain=25, estimated_gain=20)
        after = registry.find_by_id("test-skill")
        assert after.usage_count == 1
        assert abs(after.avg_effectiveness - 0.725) < 0.01

        print("  [PASS] Registry: effectiveness 移动平均更新正确")
    finally:
        cleanup(tmpdir)


def test_l1_trajectory_write():
    """L1: Phase 4 后写入轨迹 JSON"""
    tmpdir, root = new_helper()
    try:
        index_file = root / "memory" / "capability-index.yaml"
        traj_dir = root / "memory" / "trajectories"

        eval = QualityEvaluator(index_mgr=IndexManager(index_path=str(index_file)))
        trajectory = Trajectory(
            task_id="traj-001",
            task_description="Python 爬虫开发",
            task_type="code_generation",
            timestamp=datetime.now(),
            phase1=Phase1Result(predicted_score=80, gap=20, gap_level="suggest"),
            phase2=Phase2Result(selected_skill=None, user_decision="skip"),
            phase3=Phase3Result(tools_used=["bash"], errors=[]),
            phase4=Phase4Result(),
        )
        phase4 = Phase4Result(actual_score=75, outcome="success_within_tolerance")
        result = eval.finalize(trajectory, phase4)

        assert result["trajectory_written"] is True
        traj_file = traj_dir / "code_generation" / "traj-001.json"
        assert traj_file.exists()
        with open(traj_file) as f:
            data = json.load(f)
        assert data["phase4"]["actual_score"] == 75

        print("  [PASS] L1 Trajectory: 写入 JSON")
    finally:
        cleanup(tmpdir)


def test_reflection_append():
    """L2: 反思日志追加"""
    tmpdir, root = new_helper()
    try:
        index_file = root / "memory" / "capability-index.yaml"
        ref_file = root / "memory" / "reflections.md"

        eval = QualityEvaluator(index_mgr=IndexManager(index_path=str(index_file)))
        trajectory = Trajectory(
            task_id="refl-001",
            task_description="复杂多步骤任务",
            task_type="research",
            timestamp=datetime.now(),
            phase1=Phase1Result(predicted_score=70, gap=30, gap_level="force-enhance"),
            phase2=Phase2Result(),
            phase3=Phase3Result(),
            phase4=Phase4Result(),
        )
        phase4 = Phase4Result(actual_score=55, outcome="patch_needed")
        reflection = Reflection(
            task_id="refl-001",
            predicted=70, actual=55, delta=-15,
            outcome="patch_needed",
            root_causes=["领域知识不足"],
            lessons=["下次预估分下调 15 分"],
            improvement_suggestions=["建议启用 research-skill"],
        )
        eval.finalize(trajectory, phase4, reflection=reflection)

        assert ref_file.exists()
        assert "refl-001" in ref_file.read_text()

        print("  [PASS] L2 Reflection: 追加 markdown 反思日志")
    finally:
        cleanup(tmpdir)


def test_end_to_end():
    """端到端: 预判 -> 决策 -> 评估 -> 索引更新"""
    tmpdir, root = new_helper()
    try:
        index_file = root / "memory" / "capability-index.yaml"

        # Phase 1
        engine = SkillForgeEngine()
        result = engine.parse_analysis(
            '{"predicted_score": 80, "gap": 20, "task_types": ["code_generation"]}'
        )
        assert result.predicted_score == 80

        # Phase 2
        decider = EnhancementDecider()
        decision = decider.decide(
            gap=20, predicted_score=80,
            recommendations=[], task_types=["code_generation"],
        )
        assert decision.action in ("suggest_enhancement", "execute_direct")

        # Phase 4
        eval = QualityEvaluator(index_mgr=IndexManager(index_path=str(index_file)))
        trajectory = Trajectory(
            task_id="e2e-001",
            task_description="端到端测试",
            task_type="code_generation",
            timestamp=datetime.now(),
            phase1=Phase1Result(predicted_score=80, gap=20, gap_level="suggest"),
            phase2=Phase2Result(),
            phase3=Phase3Result(),
            phase4=Phase4Result(),
        )
        phase4 = Phase4Result(actual_score=75, outcome="success", delta=0.0)
        eval.finalize(trajectory, phase4)

        # L0 验证（EMA：alpha=0.2，delta=0 → avg_delta = 0.2*0 + 0.8*0 = 0）
        index = IndexManager(index_path=str(index_file))
        entry = index.get_entry("code_generation")
        assert entry.count == 1
        assert abs(entry.avg_delta - 0.0) < 0.1

        print("  [PASS] End-to-end: 预判 -> 决策 -> 评估 -> 索引更新")
    finally:
        cleanup(tmpdir)


def test_orchestrator_run_and_close():
    """Orchestrator: run() → evaluate_and_close() 完整闭环"""
    tmpdir, root = new_helper()
    try:
        from skillforge.engine import SkillForgeOrchestrator

        # 模拟 Phase 1 LLM 返回的 JSON
        # parse_analysis 读取 total_gap 字段，否则从 gaps dict 取 max
        llm_response = json.dumps({
            "predicted_score": 75,
            "total_gap": 25,
            "gaps": {"precision": 20, "creativity": 30},
            "capability_dimensions": {"gaps": {"precision": 20, "creativity": 30}},
            "task_types": ["code_generation"],
            "task_difficulty": 85,
            "recommended_skill_types": ["code"],
        })

        orch = SkillForgeOrchestrator(
            registry_path=str(root / "skillforge-registry.yaml"),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
        )

        # Phase 1-3
        result = orch.run(
            task_description="写一个 Python 爬虫",
            llm_response=llm_response,
            user_decision="skip",
        )

        assert result.task_id.startswith("sf-")
        assert result.phase3_context != ""
        assert result.trajectory.task_type in ("code_generation", "default")
        assert result.trajectory.phase1.predicted_score == 75

        # Phase 4 闭环（user_rating=3 → delta=0）
        closed = orch.evaluate_and_close(result, user_rating=3)
        assert closed.index_updated is True
        assert closed.phase4.outcome in ("success", "success_within_tolerance")

        # L0 索引已写入
        from skillforge.indexer import IndexManager
        idx = IndexManager(index_path=str(root / "memory" / "capability-index.yaml"))
        entry = idx.get_entry("code_generation")
        assert entry.count == 1

        print("  [PASS] Orchestrator: run() + evaluate_and_close() 完整闭环")
    finally:
        cleanup(tmpdir)


def test_timing_logger():
    """TimingLogger: 写入 + 读取 + 摘要统计"""
    tmpdir, root = new_helper()
    try:
        from skillforge.tracing import TimingLogger, PhaseTiming

        timings_path = root / "memory" / "timings.yaml"
        logger = TimingLogger(timings_path=str(timings_path))

        t1 = PhaseTiming(
            task_id="t1", task_type="code_generation", gap_state="force",
            phase1_ms=10, phase2_ms=5, phase3_ms=8, phase4_ms=15,
            total_ms=38, predicted_score=75, actual_score=80,
            delta=5, outcome="success", timestamp="2026-04-15T10:00:00",
        )
        t2 = PhaseTiming(
            task_id="t2", task_type="code_generation", gap_state="suggest",
            phase1_ms=12, phase2_ms=6, phase3_ms=10, phase4_ms=20,
            total_ms=48, predicted_score=70, actual_score=65,
            delta=-5, outcome="success_within_tolerance", timestamp="2026-04-15T10:01:00",
        )
        logger.write(t1)
        logger.write(t2)

        summary = logger.summary()
        assert summary["count"] == 2
        assert summary["avg_total_ms"] > 0
        assert "phase1_ms" in summary["avg_phase_ms"]

        print("  [PASS] TimingLogger: 写入 + 读取 + 摘要")
    finally:
        cleanup(tmpdir)


# ── 运行 ────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== SkillForge 端到端测试 ===\n")
    test_index_manager_write_and_read()
    test_decider_five_states()
    test_registry_effectiveness()
    test_l1_trajectory_write()
    test_reflection_append()
    test_end_to_end()
    test_orchestrator_run_and_close()
    test_timing_logger()
    print("\n[ALL PASS] 8/8 测试全部通过\n")
