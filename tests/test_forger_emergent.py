"""
测试 v0.2.6 涌现式 Forger 通路

覆盖：
1. should_forge: count 阈值 / Registry 覆盖 / 重复抑制
2. forge_draft: 基于 L0 + audit comment 生成轻量骨架
3. update_l0_file 自动触发 Forger
4. sf forge / sf demand-queue CLI
"""

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from skillforge import config as sf_config
from skillforge.forger import (
    FORGE_COUNT_THRESHOLD,
    should_forge,
    forge_draft,
    _read_audit_comments,
)
from skillforge.indexer import update_l0_file
from skillforge.cli import app


runner = CliRunner()


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    """隔离的临时工作目录，含空 Registry + 种子 L0 索引。"""
    registry = tmp_path / "skillforge-registry.yaml"
    registry.write_text("version: '1.0'\nskills: []\n", encoding="utf-8")

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    index_path = memory_dir / "capability-index.yaml"
    index_path.write_text(
        "version: '1.0'\n"
        "updated_at: '2026-04-17'\n"
        "\n"
        "task_type_index:\n"
        "  default:\n"
        "    count: 0\n"
        "    avg_delta: 0.0\n"
        "    trend: stable\n"
        "    gap_adjustment: 0\n"
        "\n"
        "_meta:\n"
        "  total_executed: 0\n"
        "  global_gap_adjustment: 0\n"
        "  last_task_id: null\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    sf_config._config = None
    yield {
        "root": tmp_path,
        "registry": registry,
        "memory": memory_dir,
        "index": index_path,
    }
    sf_config._config = None


def _inject_task_count(index_path: Path, task_type: str, count: int):
    """直接在 L0 索引插入某 task_type 条目，用于测试阈值触发。"""
    text = index_path.read_text(encoding="utf-8")
    audit = "\n".join(
        f"    # [sf-{i:08x}] 2026-04-17T10:{i:02d} 测试任务-{i} "
        f"| S=50 | rating=3 | delta=+0"
        for i in range(count)
    )
    block = (
        f"\n  {task_type}:\n"
        f"    count: {count}\n"
        f"    avg_delta: 0.0\n"
        f"    trend: stable\n"
        f"    gap_adjustment: 0\n"
        f"{audit}\n"
    )
    new_text = text.replace("\n_meta:", block + "\n_meta:")
    index_path.write_text(new_text, encoding="utf-8")


# ────────────────────────────────────────────────────
# should_forge
# ────────────────────────────────────────────────────

def test_should_forge_below_threshold(tmp_workspace):
    _inject_task_count(tmp_workspace["index"], "refactoring", FORGE_COUNT_THRESHOLD - 1)
    assert not should_forge(
        "refactoring",
        tmp_workspace["index"],
        tmp_workspace["registry"],
        tmp_workspace["memory"],
    )


def test_should_forge_at_threshold(tmp_workspace):
    _inject_task_count(tmp_workspace["index"], "refactoring", FORGE_COUNT_THRESHOLD)
    assert should_forge(
        "refactoring",
        tmp_workspace["index"],
        tmp_workspace["registry"],
        tmp_workspace["memory"],
    )


def test_should_forge_suppresses_when_registry_covered(tmp_workspace):
    _inject_task_count(tmp_workspace["index"], "refactoring", FORGE_COUNT_THRESHOLD + 5)
    # 注入 Registry 覆盖
    tmp_workspace["registry"].write_text(
        "version: '1.0'\n"
        "skills:\n"
        "  - skill_id: refactor-skill\n"
        "    name: Refactor\n"
        "    description: x\n"
        "    domain: [code]\n"
        "    task_types: [refactoring]\n"
        "    capability_gains: {precision: 10}\n"
        "    quality_tier: L2\n"
        "    trigger_keywords: [refactor]\n",
        encoding="utf-8",
    )
    assert not should_forge(
        "refactoring",
        tmp_workspace["index"],
        tmp_workspace["registry"],
        tmp_workspace["memory"],
    )


def test_should_forge_suppresses_when_draft_exists(tmp_workspace):
    _inject_task_count(tmp_workspace["index"], "refactoring", FORGE_COUNT_THRESHOLD)
    draft_dir = tmp_workspace["memory"] / "self-made"
    draft_dir.mkdir()
    (draft_dir / "refactoring-draft-2026-04-17.md").write_text("existing", encoding="utf-8")

    assert not should_forge(
        "refactoring",
        tmp_workspace["index"],
        tmp_workspace["registry"],
        tmp_workspace["memory"],
    )


# ────────────────────────────────────────────────────
# forge_draft
# ────────────────────────────────────────────────────

def test_forge_draft_generates_lightweight(tmp_workspace):
    _inject_task_count(tmp_workspace["index"], "refactoring", 5)
    draft = forge_draft(
        "refactoring",
        tmp_workspace["index"],
        tmp_workspace["memory"],
    )
    assert draft is not None and draft.exists()
    content = draft.read_text(encoding="utf-8")
    # 验证骨架关键字段
    assert "skill_id: refactoring-skill" in content
    assert "task_types:\n  - refactoring" in content
    assert "Forger 轻量骨架草稿" in content
    assert "审核清单" in content
    # 验证留白（让用户补 Workflow 而非 Forger 自己总结）
    assert "（待补充" in content


def test_forge_draft_reuses_existing(tmp_workspace):
    _inject_task_count(tmp_workspace["index"], "refactoring", 5)
    first = forge_draft("refactoring", tmp_workspace["index"], tmp_workspace["memory"])
    second = forge_draft("refactoring", tmp_workspace["index"], tmp_workspace["memory"])
    assert first == second, "同 task_type 不应重复生成（除非 force=True）"


def test_forge_draft_reads_audit_comments(tmp_workspace):
    _inject_task_count(tmp_workspace["index"], "refactoring", 5)
    records = _read_audit_comments(tmp_workspace["index"], "refactoring")
    assert len(records) == 5
    assert records[0]["rating"] == 3
    assert records[0]["task_desc"].startswith("测试任务")


# ────────────────────────────────────────────────────
# update_l0_file 自动触发
# ────────────────────────────────────────────────────

def test_update_l0_triggers_forger_at_threshold(tmp_workspace):
    index = tmp_workspace["index"]
    result = None
    # 模拟连续 5 次任务写入
    for i in range(FORGE_COUNT_THRESHOLD):
        result = update_l0_file(
            index_path=index,
            task_type="refactoring",
            rating=3,
            task_desc=f"任务 {i}",
            predicted=50.0,
        )

    # 第 5 次调用应已触发 Forger
    assert result["new_count"] == FORGE_COUNT_THRESHOLD
    assert result.get("forger_draft_path") is not None
    assert Path(result["forger_draft_path"]).exists()


def test_update_l0_does_not_retrigger_forger(tmp_workspace):
    index = tmp_workspace["index"]
    # 5 次到阈值
    for i in range(FORGE_COUNT_THRESHOLD):
        r = update_l0_file(index, "refactoring", 3, f"t{i}", 50.0)
    assert r["forger_draft_path"] is not None
    first_draft = r["forger_draft_path"]

    # 第 6 次应复用已有草稿，不重新生成
    r2 = update_l0_file(index, "refactoring", 3, "t5", 50.0)
    # 已有草稿 → should_forge 返回 False → forger_draft_path 为 None
    assert r2["forger_draft_path"] is None


# ────────────────────────────────────────────────────
# CLI: sf forge / sf demand-queue
# ────────────────────────────────────────────────────

def test_cli_demand_queue_empty_index(tmp_workspace):
    result = runner.invoke(app, ["demand-queue"])
    assert result.exit_code == 0
    # default 条目被过滤（count=0 且 avg=0）
    assert "尚无非 default task_type" in result.stdout


def test_cli_demand_queue_shows_progress(tmp_workspace):
    _inject_task_count(tmp_workspace["index"], "refactoring", 2)
    result = runner.invoke(app, ["demand-queue"])
    assert result.exit_code == 0
    assert "refactoring" in result.stdout
    assert "进展中" in result.stdout


def test_cli_forge_no_eligible(tmp_workspace):
    result = runner.invoke(app, ["forge"])
    assert result.exit_code == 0


def test_cli_forge_forced_generates_draft(tmp_workspace):
    _inject_task_count(tmp_workspace["index"], "refactoring", 5)
    result = runner.invoke(app, ["forge", "--task-type", "refactoring"])
    assert result.exit_code == 0
    assert "已生成" in result.stdout or "refactoring" in result.stdout

    draft_dir = tmp_workspace["memory"] / "self-made"
    drafts = list(draft_dir.glob("refactoring-draft-*.md"))
    assert len(drafts) == 1
