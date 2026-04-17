"""
sf show <skill_id> 契约测试。

覆盖：
1. path 指向真实 SKILL.md → 输出文件内容，source=skill_md
2. path 缺失 → 输出 Registry inline context，source=registry_inline，path_missing=True
3. skill_id 不存在 → 退出码 1
4. inline context 包含所有关键字段（description / task_types / capability_gains / trigger_keywords）
5. JSON 模式下的字段完整性
6. 绝对路径 / 相对路径 / 相对 Registry 目录都能解析
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from skillforge.cli import app, _build_inline_skill_context
from skillforge.models import Skill


runner = CliRunner()


@pytest.fixture
def tmp_workspace(monkeypatch):
    """
    创建临时工作区并切过去（Config 默认用相对路径寻找 registry/memory）：
    - 写 skillforge-registry.yaml（3 个 skill：1 个 path 有效、1 个 path 无效、1 个空 path）
    - 真实创建一个 SKILL.md
    """
    tmp = Path(tempfile.mkdtemp(prefix="skillforge-test-show-"))

    skill_md = tmp / ".cursor/skills/real-skill/SKILL.md"
    skill_md.parent.mkdir(parents=True, exist_ok=True)
    skill_md.write_text(
        "# Real Skill\n\n这是真实存在的 SKILL.md，Phase 3 应直接读到这段文字。",
        encoding="utf-8",
    )

    registry_data = {
        "version": "1.0",
        "skills": [
            {
                "skill_id": "real-skill",
                "name": "Real Skill",
                "description": "真实存在的 skill",
                "domain": ["test"],
                "task_types": ["code_generation"],
                "capability_gains": {"precision": 10, "reasoning": 5, "tool_knowledge": 15},
                "quality_tier": "L2",
                "source": "local",
                "path": ".cursor/skills/real-skill/SKILL.md",
                "trigger_keywords": ["实验", "test"],
            },
            {
                "skill_id": "phantom-skill",
                "name": "Phantom Skill",
                "description": "占位 skill，SKILL.md 不存在",
                "domain": ["placeholder"],
                "task_types": ["refactoring"],
                "capability_gains": {"precision": 20, "reasoning": 0, "tool_knowledge": 10},
                "quality_tier": "L2",
                "source": "local",
                "path": ".cursor/skills/nonexistent/SKILL.md",
                "trigger_keywords": ["幽灵"],
            },
            {
                "skill_id": "no-path-skill",
                "name": "Skill Without Path",
                "description": "完全没填 path",
                "task_types": ["debugging"],
                "capability_gains": {},
                "quality_tier": "unknown",
                "source": "local",
                "path": "",
                "trigger_keywords": [],
            },
        ],
    }
    (tmp / "skillforge-registry.yaml").write_text(
        yaml.dump(registry_data, allow_unicode=True), encoding="utf-8"
    )

    (tmp / "memory").mkdir(exist_ok=True)
    (tmp / "memory/capability-index.yaml").write_text(
        yaml.dump({
            "version": "1.0",
            "task_type_index": {},
            "_meta": {"total_executed": 0, "global_gap_adjustment": 0},
        }, allow_unicode=True),
        encoding="utf-8",
    )

    # Config 走模块级单例 + 相对路径解析；切换 cwd 到 tmp + 重置单例
    import skillforge.config as sf_config
    original_cwd = os.getcwd()
    os.chdir(tmp)
    sf_config._config = None

    yield tmp

    os.chdir(original_cwd)
    sf_config._config = None
    shutil.rmtree(tmp, ignore_errors=True)


def test_show_skill_with_existing_skill_md(tmp_workspace):
    """path 指向真实存在的 SKILL.md → 输出其内容"""
    result = runner.invoke(app, ["show", "real-skill", "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert data["skill_id"] == "real-skill"
    assert data["source"] == "skill_md"
    assert data["path_missing"] is False
    assert "真实存在的 SKILL.md" in data["content"]


def test_show_skill_with_missing_path(tmp_workspace):
    """path 指向不存在的文件 → 降级到 inline context"""
    result = runner.invoke(app, ["show", "phantom-skill", "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert data["skill_id"] == "phantom-skill"
    assert data["source"] == "registry_inline"
    assert data["path_missing"] is True

    content = data["content"]
    assert "Phantom Skill" in content
    assert "占位 skill" in content
    assert "refactoring" in content
    assert "precision" in content and "+20" in content
    assert "幽灵" in content
    assert "L2" in content


def test_show_skill_with_empty_path(tmp_workspace):
    """path 为空字符串 → 也应 inline 降级，不应崩溃"""
    result = runner.invoke(app, ["show", "no-path-skill", "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert data["source"] == "registry_inline"
    assert data["path_missing"] is True
    assert "Skill Without Path" in data["content"]
    assert "debugging" in data["content"]


def test_show_unknown_skill_id(tmp_workspace):
    """不存在的 skill_id → exit_code=1"""
    result = runner.invoke(app, ["show", "nonexistent-skill-xxx"])
    assert result.exit_code == 1
    assert "未找到" in result.stdout or "未找到" in (result.stderr or "")


def test_show_text_mode_prints_warning_for_missing(tmp_workspace):
    """非 JSON 模式下，path_missing 应显式标注 ⚠ 警告"""
    result = runner.invoke(app, ["show", "phantom-skill"])
    assert result.exit_code == 0
    assert "SKILL.md" in result.stdout
    assert "path_missing" in result.stdout or "缺失" in result.stdout


def test_show_text_mode_no_warning_for_existing(tmp_workspace):
    """path 有效时，文本模式不应出现"缺失"告警"""
    result = runner.invoke(app, ["show", "real-skill"])
    assert result.exit_code == 0
    assert "缺失" not in result.stdout
    assert "真实存在的 SKILL.md" in result.stdout


def test_inline_context_contains_required_sections():
    """_build_inline_skill_context 输出必须包含 Phase 3 所需的所有核心章节"""
    skill = Skill(
        skill_id="test-skill",
        name="Test Skill",
        description="A test skill",
        domain=["dev"],
        task_types=["code_generation", "refactoring"],
        capability_gains={"precision": 15, "reasoning": 10},
        quality_tier="L2",
        source="local",
        path=".cursor/skills/test/SKILL.md",
        trigger_keywords=["test", "demo"],
    )
    ctx = _build_inline_skill_context(skill)

    for section in ["描述", "领域", "适用任务类型", "能力提升估算", "触发关键词", "质量等级", "使用指引"]:
        assert section in ctx, f"Missing section: {section}"

    assert "test-skill" in ctx
    assert "Test Skill" in ctx
    assert "code_generation" in ctx and "refactoring" in ctx
    assert "+15" in ctx and "+10" in ctx
    assert "test" in ctx and "demo" in ctx


def test_inline_context_handles_empty_fields():
    """空字段必须有合理降级文案，不能输出空行或崩溃"""
    skill = Skill(
        skill_id="minimal",
        name="Minimal",
        description="",
        task_types=[],
        capability_gains={},
        trigger_keywords=[],
        domain=[],
    )
    ctx = _build_inline_skill_context(skill)

    assert "未填写" in ctx or "未指定" in ctx
    assert "Minimal" in ctx


def test_absolute_path_in_registry(tmp_workspace):
    """Registry path 为绝对路径时也应正确解析"""
    skill_md = tmp_workspace / "abs-skill" / "SKILL.md"
    skill_md.parent.mkdir(parents=True, exist_ok=True)
    skill_md.write_text("# Abs Skill\nabsolute path content", encoding="utf-8")

    registry_path = tmp_workspace / "skillforge-registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    data["skills"].append({
        "skill_id": "abs-skill",
        "name": "Abs Skill",
        "description": "uses absolute path",
        "task_types": ["code_generation"],
        "capability_gains": {},
        "quality_tier": "L2",
        "source": "local",
        "path": str(skill_md.resolve()),
        "trigger_keywords": [],
    })
    registry_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")

    result = runner.invoke(app, ["show", "abs-skill", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["source"] == "skill_md"
    assert "absolute path content" in parsed["content"]
