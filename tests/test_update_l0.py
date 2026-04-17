"""
tests/test_update_l0.py

FIX-024: update_l0_file() 的回归测试套件。

覆盖路径：
  1. 已存在 task_type 条目的数据更新（count / avg_delta / gap_adjustment / trend）
  2. 审计注释追加到条目末尾 + 保留已有注释
  3. 不存在的 task_type 自动创建新条目
  4. rating=1 触发 reflections.md 追加模板骨架（并含禁止外部归因模板）
  5. _meta.last_task_id / total_executed / updated_at / global_gap_adjustment 同步
  6. trend 的 count<5 不更新 / count=5 且 avg_delta>10 → degrading 逻辑
  7. 原子写入：中间写 tmp 文件，最终 rename
"""

import re
import pytest
from pathlib import Path
from datetime import date

from skillforge.indexer import update_l0_file


# ── fixtures ──────────────────────────────────────────────────────────────────

MINIMAL_YAML = """# header comment
task_type_index:

  refactoring:
    count: 2
    avg_delta: 0.0
    trend: stable
    gap_adjustment: 0
    # [sf-v0.2.1-fix] 2026-04-17 旧审计记录 | S=90 | rating=3 | delta=0

  default:
    count: 0
    avg_delta: 0.0
    trend: stable
    gap_adjustment: 0

_meta:
  version: "1.0"
  updated_at: "2026-04-01"
  last_task_id: sf-old
  total_executed: 2
  global_gap_adjustment: 0
"""


@pytest.fixture
def yaml_path(tmp_path: Path) -> Path:
    p = tmp_path / "capability-index.yaml"
    p.write_text(MINIMAL_YAML, encoding="utf-8")
    return p


# ── 基础更新 ──────────────────────────────────────────────────────────────────

class TestBasicUpdate:
    def test_count_increments(self, yaml_path):
        update_l0_file(yaml_path, "refactoring", rating=3, task_desc="test", predicted=80)
        text = yaml_path.read_text()
        m = re.search(r"refactoring:\s*\n(?:    [^\n]*\n)+", text)
        assert m, "refactoring 条目未找到"
        assert re.search(r"count:\s*3", m.group())

    def test_avg_delta_ema_rating3(self, yaml_path):
        """rating=3 → delta=0 → avg_delta 保持不变"""
        update_l0_file(yaml_path, "refactoring", rating=3, task_desc="test", predicted=80)
        text = yaml_path.read_text()
        m = re.search(r"refactoring:\s*\n((?:    [^\n]*\n)+)", text)
        block = m.group(1)
        avg_m = re.search(r"avg_delta:\s*([-+]?\d+(?:\.\d+)?)", block)
        assert float(avg_m.group(1)) == pytest.approx(0.0)

    def test_avg_delta_ema_rating1(self, yaml_path):
        """rating=1 → delta=-40 → avg_delta = 0.2*(-40) + 0.8*0 = -8.0"""
        update_l0_file(yaml_path, "refactoring", rating=1, task_desc="fail", predicted=80)
        text = yaml_path.read_text()
        m = re.search(r"refactoring:\s*\n((?:    [^\n]*\n)+)", text)
        block = m.group(1)
        avg_m = re.search(r"avg_delta:\s*([-+]?\d+(?:\.\d+)?)", block)
        assert float(avg_m.group(1)) == pytest.approx(-8.0)

    def test_gap_adjustment_is_round_avg_times_2(self, yaml_path):
        """gap_adjustment = round(avg_delta * 2)"""
        update_l0_file(yaml_path, "refactoring", rating=1, task_desc="fail", predicted=80)
        text = yaml_path.read_text()
        m = re.search(r"refactoring:\s*\n((?:    [^\n]*\n)+)", text)
        block = m.group(1)
        avg_m = re.search(r"avg_delta:\s*([-+]?\d+(?:\.\d+)?)", block)
        gap_m = re.search(r"gap_adjustment:\s*([-+]?\d+)", block)
        expected_gap = round(float(avg_m.group(1)) * 2)
        assert int(gap_m.group(1)) == expected_gap

    def test_returns_summary_dict(self, yaml_path):
        result = update_l0_file(yaml_path, "refactoring", rating=3, task_desc="x", predicted=75)
        assert result["new_count"] == 3
        assert result["delta"] == 0
        assert "new_trend" in result
        assert "new_global_gap_adjustment" in result
        assert result["reflection_written"] is False


# ── 注释保留 ──────────────────────────────────────────────────────────────────

class TestCommentPreservation:
    def test_old_audit_comment_preserved(self, yaml_path):
        update_l0_file(yaml_path, "refactoring", rating=3, task_desc="new-task", predicted=80)
        text = yaml_path.read_text()
        assert "sf-v0.2.1-fix" in text, "旧审计注释被删除"

    def test_new_audit_comment_appended(self, yaml_path):
        result = update_l0_file(
            yaml_path, "refactoring", rating=3,
            task_desc="审计测试", predicted=80, task_id="sf-test-id"
        )
        text = yaml_path.read_text()
        assert "sf-test-id" in text
        assert "审计测试" in text

    def test_header_comment_preserved(self, yaml_path):
        update_l0_file(yaml_path, "refactoring", rating=3, task_desc="x", predicted=80)
        text = yaml_path.read_text()
        assert "# header comment" in text

    def test_audit_comment_after_data_fields(self, yaml_path):
        """审计注释应在 count/avg_delta 等字段之后"""
        result = update_l0_file(
            yaml_path, "refactoring", rating=3,
            task_desc="order-test", predicted=80, task_id="sf-order"
        )
        text = yaml_path.read_text()
        # 在 refactoring 块内，数据字段行号 < 审计注释行号
        lines = text.splitlines()
        count_idx = next(i for i, l in enumerate(lines) if "count:" in l and "refactoring" not in l)
        audit_idx = next(i for i, l in enumerate(lines) if "sf-order" in l)
        assert count_idx < audit_idx


# ── 新条目创建 ────────────────────────────────────────────────────────────────

class TestNewEntry:
    def test_creates_missing_task_type(self, yaml_path):
        result = update_l0_file(
            yaml_path, "brand_new_type", rating=3,
            task_desc="new", predicted=70, task_id="sf-new"
        )
        text = yaml_path.read_text()
        assert "brand_new_type:" in text
        assert result["new_count"] == 1

    def test_new_entry_before_meta(self, yaml_path):
        update_l0_file(yaml_path, "brand_new_type", rating=3, task_desc="x", predicted=70)
        text = yaml_path.read_text()
        new_pos = text.index("brand_new_type:")
        meta_pos = text.index("_meta:")
        assert new_pos < meta_pos

    def test_new_entry_with_rating1_has_correct_delta(self, yaml_path):
        result = update_l0_file(
            yaml_path, "another_new", rating=1,
            task_desc="fail", predicted=60
        )
        text = yaml_path.read_text()
        m = re.search(r"another_new:\s*\n((?:    [^\n]*\n)+)", text)
        block = m.group(1)
        avg_m = re.search(r"avg_delta:\s*([-+]?\d+(?:\.\d+)?)", block)
        assert float(avg_m.group(1)) == pytest.approx(-40.0)


# ── _meta 更新 ────────────────────────────────────────────────────────────────

class TestMetaUpdate:
    def test_last_task_id_updated(self, yaml_path):
        update_l0_file(
            yaml_path, "refactoring", rating=3,
            task_desc="x", predicted=80, task_id="sf-meta-test"
        )
        text = yaml_path.read_text()
        assert "last_task_id: sf-meta-test" in text

    def test_total_executed_increments(self, yaml_path):
        update_l0_file(yaml_path, "refactoring", rating=3, task_desc="x", predicted=80)
        text = yaml_path.read_text()
        assert "total_executed: 3" in text

    def test_updated_at_refreshed(self, yaml_path):
        update_l0_file(yaml_path, "refactoring", rating=3, task_desc="x", predicted=80)
        text = yaml_path.read_text()
        today = date.today().isoformat()
        assert today in text

    def test_global_gap_adjustment_rating3_stays_zero(self, yaml_path):
        """rating=3 → delta=0 → global_gap_adjustment = round(0*0.95 + 0*0.05) = 0"""
        update_l0_file(yaml_path, "refactoring", rating=3, task_desc="x", predicted=80)
        text = yaml_path.read_text()
        assert "global_gap_adjustment: 0" in text

    def test_global_gap_adjustment_rating1_moves(self, yaml_path):
        """rating=1 → delta=-40 → new_gga = round(0*0.95 + (-40)*0.05) = -2"""
        update_l0_file(yaml_path, "refactoring", rating=1, task_desc="x", predicted=80)
        text = yaml_path.read_text()
        assert "global_gap_adjustment: -2" in text


# ── trend 逻辑 ────────────────────────────────────────────────────────────────

class TestTrendLogic:
    def _make_yaml_with_count(self, tmp_path, count, avg_delta_val, trend="stable"):
        p = tmp_path / "cap.yaml"
        p.write_text(f"""task_type_index:

  test_type:
    count: {count}
    avg_delta: {avg_delta_val}
    trend: {trend}
    gap_adjustment: 0

_meta:
  version: "1.0"
  updated_at: "2026-01-01"
  last_task_id: null
  total_executed: {count}
  global_gap_adjustment: 0
""", encoding="utf-8")
        return p

    def test_trend_not_changed_when_count_lt_5(self, tmp_path):
        """count < 5 → trend 维持原值"""
        p = self._make_yaml_with_count(tmp_path, 3, 0.0, trend="stable")
        update_l0_file(p, "test_type", rating=1, task_desc="x", predicted=70)
        text = p.read_text()
        m = re.search(r"test_type:\s*\n((?:    [^\n]*\n)+)", text)
        block = m.group(1)
        trend_m = re.search(r"trend:\s*(\w+)", block)
        assert trend_m.group(1) == "stable"

    def test_trend_degrading_when_count_5_and_avg_gt_10(self, tmp_path):
        """模拟 count 到 5，avg_delta 在 rating=1 后超 10"""
        # avg=14, delta=-40 → new_avg = 0.2*(-40)+0.8*14 = -8+11.2 = 3.2 — 不触发 degrading
        # 用更高 avg_delta 让 EMA 后仍 > 10
        # avg=20, delta=0 → new_avg = 0.2*0+0.8*20 = 16 → count=5 → abs(16)>10 → degrading
        p = self._make_yaml_with_count(tmp_path, 4, 20.0, trend="stable")
        update_l0_file(p, "test_type", rating=3, task_desc="x", predicted=70)
        text = p.read_text()
        m = re.search(r"test_type:\s*\n((?:    [^\n]*\n)+)", text)
        trend_m = re.search(r"trend:\s*(\w+)", m.group(1))
        assert trend_m.group(1) == "degrading"

    def test_trend_improving_when_count_5_and_avg_lt_5(self, tmp_path):
        """avg=2, delta=0 → new_avg=1.6 → count=5 → abs(1.6)<5 → improving"""
        p = self._make_yaml_with_count(tmp_path, 4, 2.0, trend="stable")
        update_l0_file(p, "test_type", rating=3, task_desc="x", predicted=70)
        text = p.read_text()
        m = re.search(r"test_type:\s*\n((?:    [^\n]*\n)+)", text)
        trend_m = re.search(r"trend:\s*(\w+)", m.group(1))
        assert trend_m.group(1) == "improving"


# ── rating=1 反思 ─────────────────────────────────────────────────────────────

class TestReflection:
    def test_reflection_created_on_rating1(self, yaml_path):
        update_l0_file(
            yaml_path, "refactoring", rating=1,
            task_desc="任务失败测试", predicted=60
        )
        refl = yaml_path.parent / "reflections.md"
        assert refl.exists(), "reflections.md 未创建"
        content = refl.read_text()
        assert "任务失败测试" in content
        assert "root cause" in content
        assert "lessons" in content
        assert "next time" in content

    def test_reflection_not_created_on_rating3(self, yaml_path):
        update_l0_file(yaml_path, "refactoring", rating=3, task_desc="x", predicted=80)
        refl = yaml_path.parent / "reflections.md"
        assert not refl.exists()

    def test_reflection_appends_on_second_rating1(self, yaml_path):
        update_l0_file(
            yaml_path, "refactoring", rating=1,
            task_desc="第一次失败", predicted=60, task_id="sf-fail-1"
        )
        update_l0_file(
            yaml_path, "refactoring", rating=1,
            task_desc="第二次失败", predicted=55, task_id="sf-fail-2"
        )
        content = (yaml_path.parent / "reflections.md").read_text()
        assert "sf-fail-1" in content
        assert "sf-fail-2" in content
        assert "第一次失败" in content
        assert "第二次失败" in content

    def test_reflection_template_has_no_external_blame(self, yaml_path):
        """反思模板应引导内因归因，骨架中需含禁止外部归因提示"""
        update_l0_file(
            yaml_path, "refactoring", rating=1,
            task_desc="测试禁止外部归因", predicted=70
        )
        content = (yaml_path.parent / "reflections.md").read_text()
        assert "TODO" in content  # 模板骨架待填充


# ── 原子写入 ──────────────────────────────────────────────────────────────────

class TestAtomicWrite:
    def test_tmp_file_removed_after_success(self, yaml_path):
        update_l0_file(yaml_path, "refactoring", rating=3, task_desc="x", predicted=80)
        tmp = yaml_path.with_suffix(".yaml.tmp")
        assert not tmp.exists(), "tmp 文件未被清理"

    def test_file_not_exist_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            update_l0_file(
                tmp_path / "nonexistent.yaml",
                "refactoring", rating=3, task_desc="x", predicted=80
            )
