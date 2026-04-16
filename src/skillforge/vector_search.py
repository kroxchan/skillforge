# SkillForge Stage 3: 向量语义检索
#
# 功能：当 Skill Registry 的关键词匹配找不到合适 skill 时，
#       用向量相似度搜索找到语义相近的候选。
#
# 设计原则：
#   1. 可选配置：config.stage3.vector_search.enabled = false 时完全不加载
#   2. 实现分离：
#      - VectorSearchProvider（接口抽象）
#      - ChromaDBProvider（真实实现）
#      - MockProvider（本地测试用，无需外部依赖）
#   3. ChromaDB 首次启动时自动从 Registry 构建向量索引
#   4. Registry 更新时自动重建索引（只增不减）

import hashlib
from pathlib import Path
from typing import Optional

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False

from skillforge.models import Skill, SkillRecommendation


# ── 接口定义 ──────────────────────────────────────────────────

class VectorSearchProvider:
    """
    向量检索接口。
    所有实现（ChromaDB / Mock）都实现这个接口。
    """

    def add_skills(self, skills: list[Skill]) -> None:
        """将 skill 列表加入向量索引"""
        raise NotImplementedError

    def rebuild_index(self, skills: list[Skill]) -> None:
        """重建整个索引（全量替换）"""
        raise NotImplementedError

    def search(
        self,
        query: str,
        task_type: Optional[str] = None,
        top_k: int = 5,
    ) -> list[tuple[Skill, float]]:
        """
        语义相似度搜索。

        Args:
            query: 自然语言任务描述
            task_type: 可选，按任务类型过滤
            top_k: 返回前 K 个最相似结果

        Returns:
            [(skill, similarity_score)] 按相似度从高到低排列
        """
        raise NotImplementedError

    def close(self) -> None:
        """关闭资源"""
        raise NotImplementedError


# ── Mock 实现（测试 / 无依赖环境） ──────────────────────────────

class MockVectorSearchProvider(VectorSearchProvider):
    """
    内存 mock 实现，用于：
    1. 开发调试（不装 ChromaDB）
    2. CI 测试
    3. 用户不想装 ChromaDB 时的降级方案
    """

    def __init__(self):
        self._skills: list[Skill] = []
        self._query_log: list[dict] = []  # 记录查询历史，便于调试

    def add_skills(self, skills: list[Skill]) -> None:
        self._skills.extend(skills)

    def rebuild_index(self, skills: list[Skill]) -> None:
        self._skills = list(skills)

    def search(
        self,
        query: str,
        task_type: Optional[str] = None,
        top_k: int = 5,
    ) -> list[tuple[Skill, float]]:
        """
        Mock 检索：基于关键词重叠 + task_type 匹配打分量分数。
        不是真正的向量检索，但能跑通整个流程。
        """
        query_lower = query.lower()
        tokens = set(query_lower.split())

        scored = []
        for skill in self._skills:
            if task_type and task_type not in skill.task_types:
                continue

            score = 0.0

            # 名称重叠
            name_tokens = set(skill.name.lower().split())
            score += len(tokens & name_tokens) * 0.5

            # 描述重叠
            desc_tokens = set(skill.description.lower().split())
            score += len(tokens & desc_tokens) * 0.3

            # 触发词重叠
            for kw in skill.trigger_keywords:
                if kw.lower() in query_lower:
                    score += 0.8

            # domain 加权
            for domain in skill.domain:
                if domain.lower() in query_lower:
                    score += 0.4

            if score > 0:
                scored.append((skill, min(score, 1.0)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def close(self) -> None:
        pass

    def debug_stats(self) -> dict:
        """返回 mock 索引统计（调试用）"""
        return {
            "total_skills": len(self._skills),
            "query_log_count": len(self._query_log),
        }


# ── ChromaDB 实现 ─────────────────────────────────────────────

class ChromaDBProvider(VectorSearchProvider):
    """
    ChromaDB 向量检索实现。

    特性：
    - 自动从 SkillRegistry 同步向量索引
    - task_type 作为 filter metadata，支持条件过滤
    - 只增索引（不删），Registry 删除 skill 时重建全量索引
    - 持久化到本地 .chroma/ 目录
    """

    COLLECTION_NAME = "skillforge_skills"

    def __init__(
        self,
        persist_dir: str = ".chroma",
        model_name: str = "all-MiniLM-L6-v2",
        distance_metric: str = "cosine",
    ):
        if not _CHROMA_AVAILABLE:
            raise ImportError(
                "ChromaDB 未安装。请运行：pip install chromadb\n"
                "或者在 config.yaml 中设置 stage3.vector_search.provider: mock"
            )

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(exist_ok=True)
        self.model_name = model_name
        self.distance_metric = distance_metric
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "SkillForge Skill Vector Index"},
        )
        self._initialized = self._collection.count() > 0

    def add_skills(self, skills: list[Skill]) -> None:
        """增量添加 skill 到向量索引"""
        if not skills:
            return

        ids, embeddings, documents, metadatas = self._skills_to_vectors(skills)

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def rebuild_index(self, skills: list[Skill]) -> None:
        """重建全量索引（清空后重建）"""
        self._client.delete_collection(name=self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "SkillForge Skill Vector Index"},
        )
        self.add_skills(skills)

    def search(
        self,
        query: str,
        task_type: Optional[str] = None,
        top_k: int = 5,
    ) -> list[tuple[Skill, float]]:
        """
        ChromaDB 语义检索。

        使用 sentence-transformers/all-MiniLM-L6-v2 编码查询向量，
        在 ChromaDB 中做余弦相似度搜索。
        """
        from sentence_transformers import SentenceTransformer

        # 编码查询
        model = SentenceTransformer(self.model_name)
        query_embedding = model.encode(query).tolist()

        # 搜索
        where_filter = {"task_type": task_type} if task_type else None
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["metadatas", "distances"],
        )

        skill_map = {s.skill_id: s for s in self._get_all_skills()}
        matches = []
        for i in range(len(results["ids"][0])):
            skill_id = results["ids"][0][i]
            distance = results["distances"][0][i]
            if skill_id in skill_map:
                # ChromaDB distance 越小越相似，转换为相似度分数
                similarity = 1.0 - distance
                matches.append((skill_map[skill_id], similarity))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:top_k]

    def _skills_to_vectors(
        self, skills: list[Skill]
    ) -> tuple[list[str], list[list[float]], list[str], list[dict]]:
        """
        将 Skill 列表转换为向量数据。
        文本 = name + description + trigger_keywords 拼接，
        确保每个 skill 的语义有足够信息量。
        """
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(self.model_name)

        texts = []
        ids = []
        metadatas = []

        for skill in skills:
            text_parts = [
                skill.name,
                skill.description,
                " ".join(skill.trigger_keywords),
                " ".join(skill.domain),
            ]
            text = " | ".join(filter(None, text_parts))
            texts.append(text)
            ids.append(skill.skill_id)
            metadatas.append({
                "task_type": ",".join(skill.task_types),
                "domain": ",".join(skill.domain),
            })

        embeddings = model.encode(texts).tolist()
        return ids, embeddings, texts, metadatas

    def _get_all_skills(self) -> list[Skill]:
        """从 collection metadata 重建 skill 列表（仅含基本信息）"""
        # 实际使用时由 Registry 传入完整 Skill 对象，这里只用于 search 结果查找
        return []


# ── 工厂函数 ──────────────────────────────────────────────────

def create_vector_search(
    provider: str = "mock",
    **kwargs,
) -> VectorSearchProvider:
    """
    根据配置创建对应的向量检索实现。

    Args:
        provider: "chroma" | "mock"
        **kwargs: 传给具体实现的参数

    Returns:
        VectorSearchProvider 实例
    """
    if provider == "chroma":
        return ChromaDBProvider(**kwargs)
    elif provider == "mock":
        return MockVectorSearchProvider()
    else:
        raise ValueError(f"未知的 vector_search provider: {provider}，支持: chroma, mock")


# ── 增强版 Registry 检索 ────────────────────────────────────────

class HybridSkillMatcher:
    """
    混合检索：关键词 + 向量语义双路召回。

    流程：
    1. 关键词匹配（快速精确）
    2. 向量检索（语义扩展）
    3. 合并去重，按加权分数排序

    这样既能找到精确命中的 skill，也能找到语义相近但名称不匹配的 skill。
    """

    def __init__(
        self,
        registry_skills: list[Skill],
        vector_search: Optional[VectorSearchProvider] = None,
        keyword_weight: float = 0.6,
        semantic_weight: float = 0.4,
    ):
        self._skills = registry_skills
        self._vector = vector_search
        self.keyword_weight = keyword_weight
        self.semantic_weight = semantic_weight

    def search(
        self,
        query: str,
        task_type: Optional[str] = None,
        top_k: int = 5,
    ) -> list[SkillRecommendation]:
        """
        混合搜索，返回 SkillRecommendation 列表。
        """
        from skillforge.models import SkillRecommendation

        # 1. 关键词匹配（用 Registry 已有逻辑）
        keyword_hits = self._keyword_search(query, task_type)
        keyword_scores = {r.skill.skill_id: r.match_score for r in keyword_hits}

        # 2. 向量检索（如果启用）
        semantic_hits: list[tuple[Skill, float]] = []
        if self._vector is not None:
            semantic_hits = self._vector.search(query=query, task_type=task_type, top_k=top_k * 2)
        semantic_scores = {s.skill_id: score for s, score in semantic_hits}

        # 3. 合并去重，加权排序
        all_ids = set(keyword_scores) | set(semantic_scores)
        combined = []
        max_kw = max(keyword_scores.values()) if keyword_scores else 1.0
        max_sem = max(semantic_scores.values()) if semantic_scores else 1.0

        for skill_id in all_ids:
            kw = keyword_scores.get(skill_id, 0.0) / max_kw
            sem = semantic_scores.get(skill_id, 0.0) / max_sem
            combined_score = self.keyword_weight * kw + self.semantic_weight * sem

            skill = next((s for s in self._skills if s.skill_id == skill_id), None)
            if skill:
                combined.append(SkillRecommendation(
                    skill=skill,
                    match_score=combined_score,
                    estimated_gain=sum(skill.capability_gains.values()) / max(len(skill.capability_gains), 1),
                    reason="keyword" if skill_id in keyword_scores else "semantic",
                ))

        combined.sort(key=lambda x: x.match_score, reverse=True)
        return combined[:top_k]

    def _keyword_search(
        self, query: str, task_type: Optional[str] = None
    ) -> list[SkillRecommendation]:
        """内部：关键词匹配（复用 Registry 逻辑）"""
        query_lower = query.lower()
        tokens = set(query_lower.split())
        hits: list[SkillRecommendation] = []

        for skill in self._skills:
            if task_type and task_type not in skill.task_types:
                continue

            score = 0.0
            if any(t in skill.name.lower() for t in tokens):
                score += 2.0
            if any(t in skill.description.lower() for t in tokens):
                score += 1.0
            if any(tk.lower() in query_lower for tk in skill.trigger_keywords):
                score += 3.0
            if any(d.lower() in query_lower for d in skill.domain):
                score += 0.5

            if score > 0:
                hits.append(SkillRecommendation(
                    skill=skill,
                    match_score=score,
                    estimated_gain=sum(skill.capability_gains.values()) / max(len(skill.capability_gains), 1),
                    reason="keyword",
                ))

        hits.sort(key=lambda x: x.match_score, reverse=True)
        return hits
