# SkillForge: Forger 模块测试

import sys, os, tempfile, shutil, json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skillforge.forger import count_successful_trajectories, generate_forger_draft

_ORIG_CWD = Path.cwd()


def new_helper():
    tmpdir = Path(tempfile.mkdtemp())
    root = tmpdir / "run"
    root.mkdir()
    os.chdir(root)
    return tmpdir, root


def cleanup(tmpdir):
    os.chdir(_ORIG_CWD)
    shutil.rmtree(tmpdir, ignore_errors=True)


def _write_trajectory(memory_dir: Path, task_type: str, task_id: str, outcome: str, score: float):
    """写一条假轨迹到 L1"""
    traj_dir = memory_dir / "trajectories" / task_type
    traj_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "task_id": task_id,
        "task_description": f"测试任务 {task_id}",
        "task_type": task_type,
        "timestamp": datetime.now().isoformat(),
        "phase3": {"tools_used": ["bash", "read"], "errors": []},
        "phase4": {"actual_score": score, "outcome": outcome, "user_rating": 4},
    }
    (traj_dir / f"{task_id}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ── 测试 ────────────────────────────────────────────────────────

def test_count_no_trajectories():
    """目录不存在时返回空列表"""
    tmpdir, root = new_helper()
    try:
        result = count_successful_trajectories(str(root / "memory"), "code_generation")
        assert result == []
        print("  [PASS] count_successful_trajectories: 目录不存在返回空列表")
    finally:
        cleanup(tmpdir)


def test_count_only_success():
    """只统计成功轨迹"""
    tmpdir, root = new_helper()
    try:
        mem = root / "memory"
        _write_trajectory(mem, "code_generation", "t1", "success", 80)
        _write_trajectory(mem, "code_generation", "t2", "success_within_tolerance", 72)
        _write_trajectory(mem, "code_generation", "t3", "patch_needed", 40)  # 失败，不计入

        result = count_successful_trajectories(str(mem), "code_generation")
        assert len(result) == 2
        ids = [r["task_id"] for r in result]
        assert "t1" in ids
        assert "t2" in ids
        assert "t3" not in ids
        print("  [PASS] count_successful_trajectories: 只统计成功轨迹")
    finally:
        cleanup(tmpdir)


def test_count_different_task_types():
    """不同 task_type 互不干扰"""
    tmpdir, root = new_helper()
    try:
        mem = root / "memory"
        _write_trajectory(mem, "code_generation", "c1", "success", 80)
        _write_trajectory(mem, "research", "r1", "success", 75)

        code = count_successful_trajectories(str(mem), "code_generation")
        research = count_successful_trajectories(str(mem), "research")

        assert len(code) == 1
        assert len(research) == 1
        print("  [PASS] count_successful_trajectories: task_type 隔离正确")
    finally:
        cleanup(tmpdir)


def test_generate_draft_creates_file():
    """触发后生成草稿文件"""
    tmpdir, root = new_helper()
    try:
        mem = root / "memory"
        trajectories = []
        for i in range(3):
            _write_trajectory(mem, "code_generation", f"t{i}", "success", 78 + i)
        trajectories = count_successful_trajectories(str(mem), "code_generation")

        draft_path = generate_forger_draft(
            task_type="code_generation",
            trajectories=trajectories,
            memory_dir=str(mem),
        )

        assert Path(draft_path).exists()
        content = Path(draft_path).read_text(encoding="utf-8")
        assert "skill_id:" in content
        assert "code_generation" in content
        assert "Forger" in content
        print(f"  [PASS] generate_forger_draft: 草稿生成 → {Path(draft_path).name}")
    finally:
        cleanup(tmpdir)


def test_generate_draft_no_duplicate():
    """同天同 task_type 不重复生成"""
    tmpdir, root = new_helper()
    try:
        mem = root / "memory"
        for i in range(3):
            _write_trajectory(mem, "code_generation", f"t{i}", "success", 80)
        trajectories = count_successful_trajectories(str(mem), "code_generation")

        path1 = generate_forger_draft("code_generation", trajectories, str(mem))
        path2 = generate_forger_draft("code_generation", trajectories, str(mem))

        # 同一天只生成一次，返回已有草稿路径
        assert path1 == path2
        drafts = list((mem / "self-made").glob("code_generation-draft-*.md"))
        assert len(drafts) == 1
        print("  [PASS] generate_forger_draft: 同天不重复生成")
    finally:
        cleanup(tmpdir)


def test_forger_trigger_via_orchestrator():
    """Orchestrator evaluate_and_close 触发 Forger"""
    tmpdir, root = new_helper()
    try:
        import json, shutil
        from skillforge.engine import SkillForgeOrchestrator

        REGISTRY_SRC = Path("/Users/vivx/cursor/digital-human/skills/SKILLFORGE/skillforge-registry.yaml")
        reg_file = root / "skillforge-registry.yaml"
        shutil.copy(str(REGISTRY_SRC), str(reg_file))

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
        )

        llm_response = json.dumps({
            "predicted_score": 75, "total_gap": 25,
            "gaps": {"precision": 20},
            "capability_dimensions": {"gaps": {"precision": 20}},
            "task_types": ["code_generation"], "task_difficulty": 80,
            "recommended_skill_types": ["code"],
        })

        # 写入 3 条已有成功轨迹，模拟触发条件
        mem = root / "memory"
        for i in range(3):
            _write_trajectory(mem, "code_generation", f"pre-{i}", "success", 78)

        # 第 4 次任务
        result = orch.run(
            task_description="写 Python 爬虫",
            llm_response=llm_response,
            user_decision="skip",
        )
        closed = orch.evaluate_and_close(result, actual_score=80)

        # Forger 触发，返回草稿路径
        assert closed.forger_draft_path is not None
        assert Path(closed.forger_draft_path).exists()
        print(f"  [PASS] Orchestrator Forger 触发 → {Path(closed.forger_draft_path).name}")
    finally:
        cleanup(tmpdir)


def test_forger_no_trigger_below_threshold():
    """成功次数不足时不触发 Forger"""
    tmpdir, root = new_helper()
    try:
        import json, shutil
        from skillforge.engine import SkillForgeOrchestrator

        REGISTRY_SRC = Path("/Users/vivx/cursor/digital-human/skills/SKILLFORGE/skillforge-registry.yaml")
        reg_file = root / "skillforge-registry.yaml"
        shutil.copy(str(REGISTRY_SRC), str(reg_file))

        orch = SkillForgeOrchestrator(
            registry_path=str(reg_file),
            index_path=str(root / "memory" / "capability-index.yaml"),
            memory_dir=str(root / "memory"),
        )

        llm_response = json.dumps({
            "predicted_score": 75, "total_gap": 25, "gaps": {"precision": 20},
            "capability_dimensions": {"gaps": {"precision": 20}},
            "task_types": ["code_generation"], "task_difficulty": 80,
            "recommended_skill_types": [],
        })

        # 只有 1 条已有轨迹（不够 3 次）
        _write_trajectory(root / "memory", "code_generation", "pre-0", "success", 78)

        result = orch.run(
            task_description="写 Python 爬虫",
            llm_response=llm_response,
            user_decision="skip",
        )
        closed = orch.evaluate_and_close(result, actual_score=80)

        assert closed.forger_draft_path is None
        print("  [PASS] 成功次数不足时不触发 Forger")
    finally:
        cleanup(tmpdir)


# ── 运行 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== SkillForge Forger 模块测试 ===\n")
    test_count_no_trajectories()
    test_count_only_success()
    test_count_different_task_types()
    test_generate_draft_creates_file()
    test_generate_draft_no_duplicate()
    test_forger_trigger_via_orchestrator()
    test_forger_no_trigger_below_threshold()
    print("\n[ALL PASS] 7/7 Forger 测试通过\n")
