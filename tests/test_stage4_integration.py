# SkillForge Stage 4: 集成测试
# 测试 Orchestrator 与 ReflexionLoader 的串联调用链路

import sys, os, tempfile, shutil, json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skillforge.models import (
    Trajectory, Phase1Result, Phase2Result,
    Phase3Result, Phase4Result,
)
from skillforge.reflexion import ReflectionLoader
from skillforge.engine import SkillForgeOrchestrator

_ORIG_CWD = Path.cwd()
_REGISTRY_SRC = Path("/Users/vivx/cursor/digital-human/skills/SKILLFORGE/skillforge-registry.yaml")


def new_helper():
    tmpdir = Path(tempfile.mkdtemp())
    root = tmpdir / "run"
    root.mkdir()
    os.chdir(root)
    return tmpdir, root


def cleanup(tmpdir):
    os.chdir(_ORIG_CWD)
    shutil.rmtree(tmpdir, ignore_errors=True)


SAMPLE_REFLECTIONS = """## [sf-abc123] code_generation @ 2026-04-10 14:30

**任务**: 写一个 Python 异步爬虫
**S**: 70  **A**: 58  **Delta**: -12
**结果**: patch_needed

### 根因
- 错误处理不完善，网络超时会直接崩溃

### 教训
- 异步任务必须完善超时和重试机制

### 改进
- 生成 error-handling-skill

---

## [sf-def456] code_generation @ 2026-04-12 09:00

**任务**: 优化 REST API 接口
**S**: 80  **A**: 72  **Delta**: -8
**结果**: success_within_tolerance

### 根因
- 边界条件处理不够细致

### 教训
- API 开发需先做好参数校验

### 改进
- 添加输入校验逻辑

---
"""


# ── Stage 4-A: ReflexionLoader 独立测试 ─────────────────────────

def test_reflexion_loader_standalone():
    """ReflexionLoader 独立加载 L2 上下文"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        loader = ReflectionLoader(
            memory_dir=str(root / "memory"),
            max_entries=5,
            min_delta_threshold=-5.0,
            enabled=True,
        )

        ctx = loader.load_context("code_generation")
        assert "[L2 反思 - code_generation]" in ctx
        assert "sf-abc123" in ctx
        print("  [PASS] ReflexionLoader 独立加载 code_generation 反思")
    finally:
        cleanup(tmpdir)


def test_reflexion_loader_no_type_match():
    """task_type 无匹配时返回空"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        loader = ReflectionLoader(
            memory_dir=str(root / "memory"),
            max_entries=5,
            min_delta_threshold=-5.0,
            enabled=True,
        )

        ctx = loader.load_context("design")  # 无 matching 类型
        assert ctx == ""
        print("  [PASS] ReflexionLoader: 无匹配 task_type → 空字符串")
    finally:
        cleanup(tmpdir)


def test_reflexion_loader_get_recent_lessons():
    """get_recent_lessons 返回教训列表"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        loader = ReflectionLoader(
            memory_dir=str(root / "memory"),
            max_entries=5,
            min_delta_threshold=-5.0,
            enabled=True,
        )

        lessons = loader.get_recent_lessons("code_generation", limit=3)
        assert len(lessons) >= 1
        assert "超时" in lessons[0] or "校验" in lessons[0]
        print(f"  [PASS] get_recent_lessons: {len(lessons)} 条教训")
    finally:
        cleanup(tmpdir)


def test_reflexion_loader_get_root_causes():
    """get_failure_root_causes 返回历史根因"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        loader = ReflectionLoader(
            memory_dir=str(root / "memory"),
            min_delta_threshold=-5.0,
            enabled=True,
        )

        causes = loader.get_failure_root_causes("code_generation", limit=10)
        assert len(causes) >= 1
        print(f"  [PASS] get_failure_root_causes: {len(causes)} 条根因")
    finally:
        cleanup(tmpdir)


# ── Stage 4-B: Orchestrator + ReflexionLoader 串联 ───────────────

def test_orchestrator_reflexion_enabled():
    """Orchestrator reflexion_enabled=True → ReflexionLoader 初始化"""
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
            reflexion_enabled=True,
        )

        assert orch._reflexion_loader is not None
        assert isinstance(orch._reflexion_loader, ReflectionLoader)
        print("  [PASS] Orchestrator: reflexion_enabled=True → ReflexionLoader 初始化")
    finally:
        cleanup(tmpdir)


def test_orchestrator_reflexion_disabled():
    """Orchestrator reflexion_enabled=False → _reflexion_loader=None"""
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
            reflexion_enabled=False,
        )

        assert orch._reflexion_loader is None
        print("  [PASS] Orchestrator: reflexion_enabled=False → _reflexion_loader=None")
    finally:
        cleanup(tmpdir)


def test_orchestrator_run_injects_l2_context():
    """Orchestrator.run() → Phase 1 注入 L2 反思上下文到 capability_dimensions"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
            reflexion_enabled=True,
        )

        llm_response = json.dumps({
            "predicted_score": 70,
            "total_gap": 30,
            "gaps": {"precision": 20},
            "capability_dimensions": {"gaps": {"precision": 20}},
            "task_types": ["code_generation"],
            "task_difficulty": 85,
            "recommended_skill_types": ["code"],
        })

        result = orch.run(
            task_description="写一个 Python 异步爬虫",
            llm_response=llm_response,
            user_decision="skip",
        )

        # L2 反思上下文已注入 phase1.capability_dimensions["_l2_reflection_context"]
        l2_ctx = result.trajectory.phase1.capability_dimensions.get("_l2_reflection_context", "")
        assert l2_ctx != ""
        assert "[L2 反思 - code_generation]" in l2_ctx
        assert "sf-abc123" in l2_ctx
        print("  [PASS] Orchestrator.run(): Phase 1 注入 L2 反思上下文")
    finally:
        cleanup(tmpdir)


def test_orchestrator_run_no_reflexion_no_context():
    """Orchestrator.reflexion_enabled=False → 不注入 L2 上下文"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
            reflexion_enabled=False,
        )

        llm_response = json.dumps({
            "predicted_score": 70,
            "total_gap": 30,
            "gaps": {"precision": 20},
            "capability_dimensions": {"gaps": {"precision": 20}},
            "task_types": ["code_generation"],
            "task_difficulty": 85,
            "recommended_skill_types": ["code"],
        })

        result = orch.run(
            task_description="写一个 Python 异步爬虫",
            llm_response=llm_response,
            user_decision="skip",
        )

        # L2 上下文不应存在（未启用）
        l2_ctx = result.trajectory.phase1.capability_dimensions.get("_l2_reflection_context", "")
        assert l2_ctx == ""
        print("  [PASS] Orchestrator.run(): reflexion=False → 无 L2 上下文")
    finally:
        cleanup(tmpdir)


def test_orchestrator_run_empty_reflections_file():
    """reflections.md 为空 → L2 上下文为空字符串（不报错）"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text("# 空反思文件\n", encoding="utf-8")

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
            reflexion_enabled=True,
        )

        llm_response = json.dumps({
            "predicted_score": 75,
            "total_gap": 25,
            "gaps": {},
            "capability_dimensions": {"gaps": {}},
            "task_types": ["code_generation"],
            "task_difficulty": 80,
            "recommended_skill_types": [],
        })

        result = orch.run(
            task_description="写代码",
            llm_response=llm_response,
            user_decision="auto",
        )

        l2_ctx = result.trajectory.phase1.capability_dimensions.get("_l2_reflection_context", "")
        assert l2_ctx == ""  # 无反思条目时为空
        print("  [PASS] Orchestrator.run(): 空 reflections.md 不报错")
    finally:
        cleanup(tmpdir)


def test_orchestrator_all_stage4_features():
    """Orchestrator 同时启用 MAR + 向量检索 + Reflexion"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
            mar_enabled=True,
            vector_search_enabled=True,
            reflexion_enabled=True,
        )

        assert orch.mar is not None
        assert orch._hybrid_matcher is not None
        assert orch._reflexion_loader is not None
        print("  [PASS] Orchestrator: MAR + 向量检索 + Reflexion 三组件全初始化")
    finally:
        cleanup(tmpdir)


def test_orchestrator_reflexion_and_close():
    """Reflexion + evaluate_and_close 完整闭环"""
    tmpdir, root = new_helper()
    try:
        reg_file = root / "skillforge-registry.yaml"
        with open(_REGISTRY_SRC) as f:
            content = f.read()
        with open(reg_file, "w") as f:
            f.write(content)

        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
            reflexion_enabled=True,
        )

        llm_response = json.dumps({
            "predicted_score": 70,
            "total_gap": 30,
            "gaps": {"reasoning": 25},
            "capability_dimensions": {"gaps": {"reasoning": 25}},
            "task_types": ["code_generation"],
            "task_difficulty": 80,
            "recommended_skill_types": ["code"],
        })

        result = orch.run(
            task_description="写一个 Python 异步爬虫",
            llm_response=llm_response,
            user_decision="skip",
        )

        assert "[L2 反思" in result.trajectory.phase1.capability_dimensions.get("_l2_reflection_context", "")

        # Phase 4 闭环（失败 → 生成反思）
        # MAR 未启用，所以不 patch MAR
        closed = orch.evaluate_and_close(result, actual_score=55)

        assert closed.index_updated is True
        # 反思已写入 reflections.md（evaluator 使用 Path("memory")）
        # 确认文件路径
        ref_path = root / "memory" / "reflections.md"
        assert ref_path.exists(), f"reflections.md not found at {ref_path}"
        # 清除 loader 缓存并重新读
        orch._reflexion_loader.clear_cache()
        ref_loaded = orch._reflexion_loader._load_entries()
        # 原有 2 条 + 新增 1 条反思 = 3 条
        assert len(ref_loaded) >= 3, f"只有 {len(ref_loaded)} 条（期望 >=3）"

        print("  [PASS] Reflexion 完整闭环: run + close + 反思写入")
    finally:
        cleanup(tmpdir)


# ── 运行 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== SkillForge Stage 4 集成测试 ===\n")
    print("-- ReflexionLoader 独立 --")
    test_reflexion_loader_standalone()
    test_reflexion_loader_no_type_match()
    test_reflexion_loader_get_recent_lessons()
    test_reflexion_loader_get_root_causes()
    print("-- Orchestrator + Reflexion 串联 --")
    test_orchestrator_reflexion_enabled()
    test_orchestrator_reflexion_disabled()
    test_orchestrator_run_injects_l2_context()
    test_orchestrator_run_no_reflexion_no_context()
    test_orchestrator_run_empty_reflections_file()
    test_orchestrator_all_stage4_features()
    test_orchestrator_reflexion_and_close()
    print("\n[ALL PASS] 11/11 Stage 4 集成测试通过\n")