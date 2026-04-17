"""
FIX-042：_infer_task_type 单元测试（打分匹配重构后）

覆盖要求：
- 每个 task_type 至少 1 条正向 case
- 至少 3 条负向 case（确保不误归类）
- 多关键词冲突时打分匹配的优先级行为
- 打分结果与 pattern 顺序无关的稳定性

注意：_infer_task_type 属于 Python 引擎路径（sf analyze / sf run）专用；
      Cursor 对话路径中 Agent 应自主命名 snake_case task_type，不经过此函数。
"""

import pytest
from skillforge.cli import _infer_task_type


# ── 正向 case：明确命中单一 task_type ──────────────────────────────────────

@pytest.mark.parametrize("task,expected", [
    # code-expert group
    ("帮我写一个 Python 函数来解析 JSON", "code_generation"),
    ("把这个模块重写重构，去掉重复逻辑", "refactoring"),
    ("运行报错 AttributeError: NoneType，帮我 debug", "debugging"),
    ("请 review 这个 PR 的代码质量", "code_review"),
    ("设计一个快速排序算法", "algorithm_design"),
    # seo group
    ("分析这个网站的 SEO 问题", "content_analysis"),
    ("帮我做关键词研究", "keyword_research"),
    ("分析竞品网站的策略", "competitor_analysis"),
    ("如何建设外链？", "backlink_analysis"),
    # data group
    ("帮我数据清洗这份 CSV，去掉空值和重复行", "data_cleaning"),
    ("计算样本的统计分布和回归", "statistical_analysis"),
    ("用 chart 展示这组数据的可视化", "visualization"),
    ("生成月度报表", "report_generation"),
    # research group
    ("帮我调研这个领域的主流方案", "research"),
    ("这个数据准确吗？帮我 fact check 一下", "fact_checking"),
    # video group
    ("用 ffmpeg 把 mp4 剪辑成 30 秒片段", "video_editing"),
    ("将这个 mp4 转码为 webm format，格式转换", "format_conversion"),
    ("处理这段音频，降噪", "audio_processing"),
    ("给这个视频做个封面缩略图", "thumbnail_design"),
    ("帮我写一段旁白脚本，大约 30 秒", "script_writing"),
])
def test_single_keyword_positive(task, expected):
    result = _infer_task_type(task)
    assert result == [expected], (
        f"任务 {task!r} 期望 [{expected}]，实际 {result}"
    )


# ── 负向 case：确保常见描述不误归类 ──────────────────────────────────────

def test_no_keywords_returns_default():
    result = _infer_task_type("帮我想想下一步怎么办")
    assert result == ["default"]


def test_unrelated_business_task_returns_default():
    result = _infer_task_type("帮我起草一封邮件给客户")
    assert result == ["default"]


def test_generic_question_returns_default():
    result = _infer_task_type("这两个方案哪个更好？")
    assert result == ["default"]


def test_report_not_confused_with_research():
    # "报告" → report_generation；不应归为 research
    result = _infer_task_type("帮我生成一份项目报告")
    assert result == ["report_generation"]


def test_review_not_confused_with_research():
    # "review" 在 patterns 里属于 code_review；不应归为 research
    result = _infer_task_type("code review this PR")
    assert result == ["code_review"]


# ── 多关键词冲突 → 打分匹配选最高分 ────────────────────────────────────────

def test_multi_keyword_code_wins():
    # 3 个代码关键词 vs 1 个 SEO 关键词 → code_generation 得分更高
    task = "写一个 Python 函数来分析 SEO 关键词"
    result = _infer_task_type(task)
    # "python"+"函数"+"写代码" 各 1 分 → code_generation 至少 2 分
    # "SEO"+"关键词" → content_analysis(1) + keyword_research(1)
    # code_generation 得分最高
    assert result == ["code_generation"]


def test_multi_keyword_video_over_audio():
    # "video"+"mp4" → video_editing(2) > audio(1) → video_editing
    task = "把这个 mp4 视频里的音频提取出来"
    result = _infer_task_type(task)
    assert result == ["video_editing"]


def test_refactoring_over_code_generation():
    # "重构" → refactoring；"code" 不在描述中
    task = "这段代码需要重构，帮我重写一下"
    result = _infer_task_type(task)
    # "重构"+"重写" → refactoring(2) > code_generation 的隐含 code(0)
    assert result == ["refactoring"]


# ── 顺序无关稳定性 ──────────────────────────────────────────────────────────

def test_same_score_uses_pattern_order():
    """
    同分时，按 patterns 声明顺序取第一个。
    测试重复调用结果稳定（不因字典顺序变化）。
    """
    task = "帮我做一些 code review"
    r1 = _infer_task_type(task)
    r2 = _infer_task_type(task)
    assert r1 == r2, "相同输入应返回相同结果"


# ── 边界 ────────────────────────────────────────────────────────────────────

def test_empty_string_returns_default():
    assert _infer_task_type("") == ["default"]


def test_only_spaces_returns_default():
    assert _infer_task_type("   ") == ["default"]


def test_mixed_case_insensitive():
    # 关键词匹配应大小写不敏感
    assert _infer_task_type("REFACTOR this module") == ["refactoring"]
    assert _infer_task_type("Debug the Error") == ["debugging"]
