# SkillForge Stage 3: 向量检索模块测试

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skillforge.models import Skill, SkillRecommendation
from skillforge.vector_search import (
    MockVectorSearchProvider,
    HybridSkillMatcher,
    create_vector_search,
)


# ── Fixtures ────────────────────────────────────────────────

def _skills() -> list[Skill]:
    return [
        Skill(
            skill_id="code-expert",
            name="Code Expert Skill",
            description="专业代码编写与审查，提升编程质量和效率",
            domain=["programming", "code"],
            task_types=["code_generation", "refactoring"],
            capability_gains={"precision": 10, "reasoning": 5},
            quality_tier="L2",
            usage_count=5,
            avg_effectiveness=0.85,
            source="local",
            path="skills/code-expert",
            trigger_keywords=["写代码", "code", "python", "function"],
        ),
        Skill(
            skill_id="seo-analysis",
            name="SEO Analysis Skill",
            description="搜索引擎优化分析，关键词研究与内容策略",
            domain=["marketing", "seo"],
            task_types=["seo", "content_analysis"],
            capability_gains={"precision": 8, "domain_knowledge": 6},
            quality_tier="L2",
            usage_count=3,
            avg_effectiveness=0.75,
            source="local",
            path="skills/seo-analysis",
            trigger_keywords=["seo", "关键词", "search engine"],
        ),
        Skill(
            skill_id="research-assistant",
            name="Research Assistant",
            description="深度信息检索与研究辅助，文献调研",
            domain=["research", "information"],
            task_types=["research"],
            capability_gains={"domain_knowledge": 10, "reasoning": 5},
            quality_tier="L1",
            usage_count=2,
            avg_effectiveness=0.90,
            source="local",
            path="skills/research-assistant",
            trigger_keywords=["研究", "research", "调研", "find information"],
        ),
    ]


# ── Mock 向量检索测试 ─────────────────────────────────────────

def test_mock_add_and_search():
    """MockProvider: 添加 skill 后可以检索"""
    provider = MockVectorSearchProvider()
    provider.add_skills(_skills())

    results = provider.search("python 爬虫 代码", task_type="code_generation", top_k=3)

    assert len(results) >= 1
    assert results[0][0].skill_id == "code-expert"
    assert 0 < results[0][1] <= 1.0
    print("  [PASS] MockProvider: 添加 → 检索 → 命中 code-expert")


def test_mock_task_type_filter():
    """MockProvider: task_type 过滤"""
    provider = MockVectorSearchProvider()
    provider.add_skills(_skills())

    results = provider.search("关键词分析", task_type="seo", top_k=5)

    for skill, score in results:
        assert "seo" in skill.task_types, f"意外命中: {skill.skill_id}"
    print("  [PASS] MockProvider: task_type 过滤正确")


def test_mock_rebuild_index():
    """MockProvider: rebuild_index 全量替换"""
    provider = MockVectorSearchProvider()
    provider.add_skills(_skills())
    # rebuild 后只剩 SEO skill
    provider.rebuild_index([_skills()[1]])

    # SEO skill 搜 SEO 关键词可以找到
    results = provider.search("seo 关键词", top_k=5)
    ids = [s.skill_id for s, _ in results]

    assert "seo-analysis" in ids
    assert "code-expert" not in ids   # 被清掉了
    assert "research-assistant" not in ids
    print("  [PASS] MockProvider: rebuild_index 全量替换")


def test_mock_no_match():
    """MockProvider: 无匹配时返回空"""
    provider = MockVectorSearchProvider()
    provider.add_skills(_skills())

    results = provider.search("完全不相关的查询 xyz123", top_k=5)
    assert results == []
    print("  [PASS] MockProvider: 无匹配返回空列表")


def test_mock_debug_stats():
    """MockProvider: debug_stats 正常"""
    provider = MockVectorSearchProvider()
    provider.add_skills(_skills())

    stats = provider.debug_stats()
    assert stats["total_skills"] == 3
    print("  [PASS] MockProvider: debug_stats 正常")


# ── 混合检索测试 ──────────────────────────────────────────────

def test_hybrid_keyword_priority():
    """HybridSkillMatcher: 关键词命中的 skill 排在最前"""
    provider = MockVectorSearchProvider()
    provider.add_skills(_skills())

    matcher = HybridSkillMatcher(
        registry_skills=_skills(),
        vector_search=provider,
        keyword_weight=0.6,
        semantic_weight=0.4,
    )

    # "seo" 精确命中 seo-analysis 的 trigger_keywords
    results = matcher.search("seo analysis", task_type=None, top_k=5)

    assert len(results) > 0
    # 关键词命中排第一
    ids = [r.skill.skill_id for r in results]
    assert ids[0] == "seo-analysis"
    print("  [PASS] HybridSkillMatcher: 关键词命中优先")


def test_hybrid_no_vector_fallback():
    """HybridSkillMatcher: 向量检索未启用时只用关键词"""
    matcher = HybridSkillMatcher(
        registry_skills=_skills(),
        vector_search=None,
    )

    results = matcher.search("写代码 python", task_type=None, top_k=5)
    ids = [r.skill.skill_id for r in results]

    assert "code-expert" in ids
    print("  [PASS] HybridSkillMatcher: 无向量时回退到关键词")


def test_hybrid_task_type_filter():
    """HybridSkillMatcher: task_type 过滤"""
    provider = MockVectorSearchProvider()
    provider.add_skills(_skills())

    matcher = HybridSkillMatcher(_skills(), vector_search=provider)

    results = matcher.search("关键词", task_type="research", top_k=5)
    for r in results:
        assert "research" in r.skill.task_types
    print("  [PASS] HybridSkillMatcher: task_type 过滤正确")


# ── 工厂函数测试 ──────────────────────────────────────────────

def test_create_mock_provider():
    """create_vector_search: mock 模式"""
    provider = create_vector_search(provider="mock")
    assert isinstance(provider, MockVectorSearchProvider)
    print("  [PASS] create_vector_search(provider='mock')")


def test_create_unknown_provider_raises():
    """create_vector_search: 未知 provider 抛出错误"""
    try:
        create_vector_search(provider="unknown")
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "unknown" in str(e)
    print("  [PASS] create_vector_search: 未知 provider 报错")


# ── 运行 ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== SkillForge Stage 3 向量检索测试 ===\n")
    test_mock_add_and_search()
    test_mock_task_type_filter()
    test_mock_rebuild_index()
    test_mock_no_match()
    test_mock_debug_stats()
    test_hybrid_keyword_priority()
    test_hybrid_no_vector_fallback()
    test_hybrid_task_type_filter()
    test_create_mock_provider()
    test_create_unknown_provider_raises()
    print("\n[ALL PASS] 10/10 向量检索测试通过\n")
