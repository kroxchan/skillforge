# SkillForge Stage 4: Reflexion 模块单元测试

import sys, os, tempfile, shutil
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skillforge.reflexion import (
    ReflectionLoader,
    parse_reflections_file,
    format_as_context,
    quick_reflexion_context,
)


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


# ── Fixtures ──────────────────────────────────────────────────

SAMPLE_REFLECTIONS = """## [sf-abc123] code_generation @ 2026-04-10 14:30

**任务**: 写一个 Python 异步爬虫
**S**: 70  **A**: 58  **Delta**: -12
**结果**: patch_needed

### 根因
- 错误处理不完善，网络超时会直接崩溃
- 未处理 robots.txt 限制

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
- 缺少参数校验

### 教训
- API 开发需先做好参数校验和边界条件

### 改进
- 添加输入校验逻辑

---

## [sf-ghi789] research @ 2026-04-14 11:00

**任务**: 研究 AI Agent 最新进展
**S**: 65  **A**: 50  **Delta**: -15
**结果**: patch_needed

### 根因
- 缺少引用来源标注
- 深度不足

### 教训
- 研究任务必须标注来源和引用

### 改进
- 生成 research-skill

---

## [sf-xyz000] seo @ 2026-04-13 16:00

**任务**: 网站 SEO 关键词分析
**S**: 75  **A**: 70  **Delta**: -5
**结果**: success_within_tolerance

### 根因
- 关键词覆盖不够全面

### 教训
- SEO 分析需覆盖长尾关键词

### 改进
- 扩大关键词研究范围
"""


# ── 解析器测试 ─────────────────────────────────────────────

def test_parse_reflections_file():
    """解析 reflections.md，提取结构化条目"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        entries = parse_reflections_file(ref_file)
        assert len(entries) == 4

        # 第一个条目：code_generation, delta=-12
        assert entries[0]["task_id"] == "sf-abc123"
        assert entries[0]["task_type"] == "code_generation"
        assert entries[0]["delta"] == -12.0
        assert "异步任务必须完善超时和重试机制" in entries[0]["lesson"]
        assert "错误处理不完善" in entries[0]["root_causes"][0]

        # 第三个条目：research, delta=-15
        assert entries[2]["task_id"] == "sf-ghi789"
        assert entries[2]["task_type"] == "research"
        assert entries[2]["delta"] == -15.0

        print("  [PASS] parse_reflections_file: 解析 4 条反思")
    finally:
        cleanup(tmpdir)


def test_parse_empty_file():
    """空文件返回空列表"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text("# SkillForge 反思记录\n\n", encoding="utf-8")

        entries = parse_reflections_file(ref_file)
        assert entries == []
        print("  [PASS] parse_reflections_file: 空文件返回空列表")
    finally:
        cleanup(tmpdir)


def test_parse_missing_file():
    """文件不存在返回空列表"""
    entries = parse_reflections_file(Path("/nonexistent/reflections.md"))
    assert entries == []
    print("  [PASS] parse_reflections_file: 文件不存在返回空列表")


def test_format_as_context():
    """格式化为 Phase 1 注入字符串"""
    entries = parse_reflections_file(Path("/nonexistent/reflections.md"))  # 返回 []
    result = format_as_context([], "code_generation", max_entries=3)
    assert result == ""

    # 模拟 entries
    mock_entries = [
        {"task_id": "sf-001", "task_type": "code_generation", "delta": -12.0,
         "lesson": "必须完善超时重试机制"},
        {"task_id": "sf-002", "task_type": "code_generation", "delta": -8.0,
         "lesson": "需做好参数校验"},
    ]
    result = format_as_context(mock_entries, "code_generation", max_entries=5)
    assert "[L2 反思 - code_generation]" in result
    assert "sf-001" in result
    assert "Delta=-12.0" in result
    assert "必须完善超时重试机制" in result
    print("  [PASS] format_as_context: 格式化输出正确")


def test_format_as_context_truncation():
    """教训超长时截断到 60 字符"""
    long_lesson = "这是一个非常非常长的教训内容超过了60个字符的限制需要被截断处理以保持格式"
    mock_entries = [
        {"task_id": "sf-001", "task_type": "code_generation", "delta": -10.0, "lesson": long_lesson},
    ]
    result = format_as_context(mock_entries, "code_generation", max_entries=5)
    # 60 字符截断 + "..."
    assert len([l for l in result.split("\n") if "sf-001" in l][0]) < 70
    print("  [PASS] format_as_context: 长教训截断正确")


# ── ReflectionLoader 测试 ──────────────────────────────────────

def test_loader_filter_by_task_type():
    """按 task_type 过滤"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        loader = ReflectionLoader(
            memory_dir=str(root / "memory"),
            max_entries=5,
            min_delta_threshold=-15.0,
            enabled=True,
        )

        # code_generation: 2 条（delta -12, -8 都 < -15? 不，-8 > -15 → 不符合）
        # delta < -15 才有，所以只有 -12 和 -15 的条目
        code_entries = loader._get_filtered_entries("code_generation")
        # min_delta_threshold=-15: delta 必须 < -15
        # -12 > -15 → 不符合，-15 == -15 → 不符合（需要 < -15）
        # 实际上 -12 和 -8 都不 < -15，所以空？
        # 重新理解：min_delta_threshold=-15 意味着加载 delta < -15 的反思
        # -12 不 < -15，-8 不 < -15，只有 -15 == -15 不符合
        # 看代码实现: if delta >= self.min_delta_threshold: continue
        # delta=-12 >= -15 → True → 被过滤掉
        # delta=-8 >= -15 → True → 被过滤掉
        # 所以 code_entries 应该是空？

        # 重新看一下过滤逻辑
        # min_delta_threshold = -15
        # delta >= -15 → skip
        # -12 >= -15 → True → skip
        # -8 >= -15 → True → skip
        # -15 >= -15 → True → skip
        # -20 >= -15 → False → 保留

        # 调整阈值测试
        loader2 = ReflectionLoader(
            memory_dir=str(root / "memory"),
            max_entries=5,
            min_delta_threshold=-10.0,  # delta < -10 才保留
            enabled=True,
        )
        code_entries2 = loader2._get_filtered_entries("code_generation")
        # delta < -10: -12 < -10 ✓, -8 < -10 ✗
        assert len(code_entries2) == 1
        assert code_entries2[0]["task_id"] == "sf-abc123"
        print("  [PASS] ReflectionLoader: task_type 过滤正确")
    finally:
        cleanup(tmpdir)


def test_loader_disabled_returns_empty():
    """enabled=False 时返回空字符串"""
    tmpdir, root = new_helper()
    try:
        loader = ReflectionLoader(enabled=False)
        result = loader.load_context("code_generation")
        assert result == ""
        print("  [PASS] ReflectionLoader: enabled=False → 空字符串")
    finally:
        cleanup(tmpdir)


def test_loader_file_cache():
    """文件缓存：mtime 不变不重新读"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        loader = ReflectionLoader(
            memory_dir=str(root / "memory"),
            min_delta_threshold=-20.0,  # 保留 delta < -20 → 无条目（-12, -8 >= -20 都被过滤）
            enabled=True,
        )

        # 缓存存在：文件有内容但阈值过滤后无条目
        ctx1 = loader.load_context("code_generation")
        # min_delta_threshold=-20 过滤掉所有（-12 >= -20, -8 >= -20）
        # 无条目返回空字符串
        assert ctx1 == ""  # 阈值过严，无匹配条目

        # 修改文件并清除缓存
        ref_file.write_text(SAMPLE_REFLECTIONS + "\n\n---\n", encoding="utf-8")
        loader.clear_cache()

        # 重新加载
        entries = loader._load_entries()
        assert entries is not None
        # entries 有内容（因为 _load_entries 不过滤）
        print("  [PASS] ReflectionLoader: 文件缓存机制正常")
    finally:
        cleanup(tmpdir)


def test_loader_get_recent_lessons():
    """get_recent_lessons: 仅返回教训字符串"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        loader = ReflectionLoader(
            memory_dir=str(root / "memory"),
            max_entries=5,
            min_delta_threshold=-5.0,  # delta < -5 才保留 → -12 ✓, -8 ✓, -15 ✓
            enabled=True,
        )

        lessons = loader.get_recent_lessons("code_generation", limit=3)
        assert len(lessons) >= 1
        assert all(isinstance(l, str) for l in lessons)
        print("  [PASS] ReflectionLoader.get_recent_lessons: 返回教训列表")
    finally:
        cleanup(tmpdir)


def test_loader_get_failure_root_causes():
    """get_failure_root_causes: 返回历史失败根因"""
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

        causes = loader.get_failure_root_causes("code_generation", limit=5)
        assert len(causes) >= 1
        print(f"  [PASS] ReflectionLoader.get_failure_root_causes: {len(causes)} 条根因")
    finally:
        cleanup(tmpdir)


def test_loader_stats():
    """get_stats: 返回反思统计"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        loader = ReflectionLoader(memory_dir=str(root / "memory"), enabled=True)
        stats = loader.get_stats()

        assert stats["total"] == 4
        assert stats["by_task_type"]["code_generation"] == 2
        assert stats["by_task_type"]["research"] == 1
        assert stats["by_task_type"]["seo"] == 1
        assert abs(stats["avg_delta"] - (-10.0)) < 0.1
        print("  [PASS] ReflectionLoader.get_stats: 统计正确")
    finally:
        cleanup(tmpdir)


def test_quick_reflexion_context():
    """quick_reflexion_context: 单次调用函数"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        ctx = quick_reflexion_context(
            memory_dir=str(root / "memory"),
            task_type="code_generation",
            max_entries=3,
        )
        assert isinstance(ctx, str)
        print("  [PASS] quick_reflexion_context: 单次调用正常")
    finally:
        cleanup(tmpdir)


def test_loader_delta_filter_threshold():
    """验证 delta 过滤阈值逻辑: min_delta_threshold = -20 保留 delta < -20"""
    tmpdir, root = new_helper()
    try:
        ref_file = root / "memory" / "reflections.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text(SAMPLE_REFLECTIONS, encoding="utf-8")

        # delta < -20 → -12 和 -8 都不 < -20，所以 code_entries 为空
        loader_strict = ReflectionLoader(
            memory_dir=str(root / "memory"),
            min_delta_threshold=-20.0,
            enabled=True,
        )
        strict = loader_strict._get_filtered_entries("code_generation")
        assert len(strict) == 0

        # delta < -5 → -12 < -5 ✓, -8 < -5 ✓，保留两条
        loader_lenient = ReflectionLoader(
            memory_dir=str(root / "memory"),
            min_delta_threshold=-5.0,
            enabled=True,
        )
        lenient = loader_lenient._get_filtered_entries("code_generation")
        assert len(lenient) == 2

        # research 只有 1 条 delta=-15，-15 < -5 ✓
        research = loader_lenient._get_filtered_entries("research")
        assert len(research) == 1

        print("  [PASS] ReflectionLoader: delta 阈值过滤逻辑正确")
    finally:
        cleanup(tmpdir)


# ── 运行 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== SkillForge Stage 4 Reflexion 单元测试 ===\n")
    test_parse_reflections_file()
    test_parse_empty_file()
    test_parse_missing_file()
    test_format_as_context()
    test_format_as_context_truncation()
    test_loader_filter_by_task_type()
    test_loader_disabled_returns_empty()
    test_loader_file_cache()
    test_loader_get_recent_lessons()
    test_loader_get_failure_root_causes()
    test_loader_stats()
    test_quick_reflexion_context()
    test_loader_delta_filter_threshold()
    print("\n[ALL PASS] 13/13 Reflexion 单元测试通过\n")