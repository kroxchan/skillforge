"""
FIX-067: 非 SKILLFORGE CWD 下的 sf 命令集成测试。

验证 config._find_project_root() 的 __file__ fallback 能在任意 CWD
（如 /tmp）下正确定位 SKILLFORGE 项目根，使 sf 命令全部可用。
"""
import os
import json
import tempfile
import subprocess
import sys
from pathlib import Path

import pytest

# SKILLFORGE 项目根（通过 __file__ 相对定位，不依赖 CWD）
_SKILL_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def foreign_cwd(tmp_path):
    """切到与 SKILLFORGE 完全无关的临时目录，模拟 Cursor 对话时 CWD = 用户仓库。"""
    original = Path.cwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original)


def _run_sf(*args, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "skillforge.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestCwdIndependence:
    """
    所有测试都在 foreign_cwd（/tmp/xxx）下运行，
    SKILLFORGE 项目根不在 CWD 及任何父目录中。
    """

    def test_find_project_root_uses_file_fallback(self, foreign_cwd):
        """_find_project_root() 的 __file__ fallback 必须返回真实项目根。"""
        from skillforge.config import _find_project_root
        root = _find_project_root()
        assert (root / "skillforge-registry.yaml").exists(), (
            f"__file__ fallback 返回了错误的根: {root}"
        )

    def test_config_memory_dir_is_absolute(self, foreign_cwd):
        """Config.storage.memory_dir 在任意 CWD 下必须是绝对路径且存在于项目根下。"""
        # 清除单例，强制重新加载
        import skillforge.config as sf_config
        sf_config._config = None

        from skillforge.config import get_config
        cfg = get_config()

        mem = Path(cfg.storage.memory_dir)
        assert mem.is_absolute(), f"memory_dir 不是绝对路径: {mem}"
        assert mem == _SKILL_ROOT / "memory", (
            f"memory_dir 路径错误: {mem}（期望 {_SKILL_ROOT / 'memory'}）"
        )

        sf_config._config = None  # 还原单例，不影响其他测试

    def test_config_registry_path_is_absolute(self, foreign_cwd):
        """Config.storage.registry_path 在任意 CWD 下必须是绝对路径。"""
        import skillforge.config as sf_config
        sf_config._config = None

        from skillforge.config import get_config
        cfg = get_config()

        reg = Path(cfg.storage.registry_path)
        assert reg.is_absolute(), f"registry_path 不是绝对路径: {reg}"
        assert reg == _SKILL_ROOT / "skillforge-registry.yaml"

        sf_config._config = None

    def test_sf_update_l0_from_foreign_cwd(self, foreign_cwd):
        """sf update-l0 在非 SKILLFORGE CWD 下必须成功执行（不报 capability-index.yaml 不存在）。"""
        result = _run_sf(
            "update-l0",
            "--task-type", "cwd_integration_test",
            "--rating", "3",
            "--task-desc", "CWD 独立性集成测试",
            "--predicted", "80",
        )
        assert result.returncode == 0, (
            f"sf update-l0 在外部 CWD 下失败:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "Phase 4 闭环完成" in result.stdout or "task_type" in result.stdout.lower()

    def test_sf_demand_queue_from_foreign_cwd(self, foreign_cwd):
        """sf demand-queue 在非 SKILLFORGE CWD 下必须成功（不报 L0 索引不存在）。"""
        result = _run_sf("demand-queue")
        assert result.returncode == 0, (
            f"sf demand-queue 在外部 CWD 下失败:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # 不应出现之前的错误信息
        assert "L0 索引不存在" not in result.stdout
        assert "L0 索引不存在" not in result.stderr

    def test_sf_search_from_foreign_cwd(self, foreign_cwd):
        """sf search 在非 SKILLFORGE CWD 下必须不崩溃（Registry 空时输出"未找到"而非 IOError）。"""
        result = _run_sf("search", "test_keyword")
        assert result.returncode == 0, (
            f"sf search 在外部 CWD 下失败:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_sf_forge_from_foreign_cwd(self, foreign_cwd):
        """sf forge 在非 SKILLFORGE CWD 下必须不报 L0 不存在的错误。"""
        result = _run_sf("forge")
        assert result.returncode == 0, (
            f"sf forge 在外部 CWD 下失败:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "L0 索引不存在" not in result.stdout
        assert "L0 索引不存在" not in result.stderr

    def test_sf_list_skills_from_foreign_cwd(self, foreign_cwd):
        """sf list-skills 在非 SKILLFORGE CWD 下必须不崩溃。"""
        result = _run_sf("list-skills")
        assert result.returncode == 0, (
            f"sf list-skills 在外部 CWD 下失败:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
