# SkillForge Registry Manager
# 负责 Skill Registry 的读写、查询、匹配

import yaml
from pathlib import Path
from typing import Optional
from skillforge.models import Skill, SkillRecommendation


class SkillRegistry:
    """Skill Registry 管理器"""

    def __init__(self, registry_path: str = "skillforge-registry.yaml"):
        self.registry_path = Path(registry_path)
        self.skills: list[Skill] = []
        self.load()

    def load(self):
        """从 YAML 文件加载 Registry"""
        if not self.registry_path.exists():
            return
        
        with open(self.registry_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        self.skills = []
        for entry in data.get("skills", []):
            # 规范化 quality_tier（YAML 中可能写 1/2/3 而非 L1/L2/L3）
            entry = dict(entry)
            if "quality_tier" in entry:
                raw_tier = str(entry["quality_tier"]).strip()
                tier_map = {"1": "L1", "2": "L2", "3": "L3"}
                entry["quality_tier"] = tier_map.get(raw_tier, raw_tier)
            self.skills.append(Skill(**entry))

    def save(self):
        """保存 Registry 到 YAML 文件（保持字段顺序，浮点数保留 2 位小数）"""
        def _clean_skill(skill: Skill) -> dict:
            d = skill.model_dump()
            # 保持可读顺序
            ordered = {
                "skill_id": d["skill_id"],
                "name": d["name"],
                "description": d.get("description", ""),
                "domain": d.get("domain", []),
                "task_types": d.get("task_types", []),
                "capability_gains": {
                    k: round(float(v), 2)
                    for k, v in d.get("capability_gains", {}).items()
                },
                "quality_tier": d.get("quality_tier", "L2"),
                "usage_count": d.get("usage_count", 0),
                "avg_effectiveness": round(float(d.get("avg_effectiveness", 0.7)), 2),
                "source": d.get("source", "local"),
                "path": d.get("path", ""),
                "trigger_keywords": d.get("trigger_keywords", []),
            }
            return ordered

        data = {
            "version": "1.0",
            "updated_at": self._today(),
            "skills": [_clean_skill(skill) for skill in self.skills],
        }

        with open(self.registry_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False,
                      sort_keys=False)

    def add(self, skill: Skill):
        """添加新 Skill"""
        existing = self.find_by_id(skill.skill_id)
        if existing:
            raise ValueError(f"Skill {skill.skill_id} 已存在")
        self.skills.append(skill)
        self.save()

    def remove(self, skill_id: str):
        """移除 Skill"""
        self.skills = [s for s in self.skills if s.skill_id != skill_id]
        self.save()

    def find_by_id(self, skill_id: str) -> Optional[Skill]:
        """按 ID 查找 Skill"""
        for skill in self.skills:
            if skill.skill_id == skill_id:
                return skill
        return None

    def list_skills(self) -> list[Skill]:
        """返回所有 Skill 列表（用于 HybridSkillMatcher 构建向量索引）"""
        return list(self.skills)

    def find_by_keyword(self, keyword: str) -> list[Skill]:
        """按关键词搜索 Skill"""
        keyword_lower = keyword.lower()
        results = []
        for skill in self.skills:
            if keyword_lower in skill.name.lower():
                results.append(skill)
            elif any(keyword_lower in k.lower() for k in skill.trigger_keywords):
                results.append(skill)
            elif keyword_lower in skill.description.lower():
                results.append(skill)
        return results

    def match(
        self,
        task_types: list[str],
        capability_gaps: dict[str, float],
        top_k: int = 5
    ) -> list[SkillRecommendation]:
        """
        根据任务类型和能力缺口，匹配最合适的 Skill。

        Args:
            task_types: 任务类型列表
            capability_gaps: 各维度的能力缺口 {dimension: gap_value}
            top_k: 最多返回多少个候选

        Returns:
            按匹配度排序的 Skill 推荐列表
        """
        candidates = []

        for skill in self.skills:
            # 1. 任务类型匹配
            type_match = len(set(task_types) & set(skill.task_types))

            # 2. 计算能力缺口覆盖度
            covered = 0.0
            for dim, gap in capability_gaps.items():
                if gap > 0 and dim in skill.capability_gains:
                    covered += min(skill.capability_gains[dim], gap)

            # 3. 综合得分
            score = type_match * 20 + covered + skill.avg_effectiveness * 15

            if score > 0:
                candidates.append(SkillRecommendation(
                    skill=skill,
                    match_score=score,
                    estimated_gain=covered,
                    reason=f"类型匹配 {type_match} 项，缺口覆盖 {covered:.1f} 分"
                ))

        # 按得分排序
        candidates.sort(key=lambda x: x.match_score, reverse=True)
        return candidates[:top_k]

    def update_effectiveness(
        self,
        skill_id: str,
        actual_gain: float,
        estimated_gain: float
    ):
        """
        更新 Skill 的有效性评分。

        Args:
            skill_id: Skill ID
            actual_gain: 实际加分（Phase 4 评估得出）
            estimated_gain: 预估加分
        """
        skill = self.find_by_id(skill_id)
        if not skill:
            return

        # 移动平均更新
        n = skill.usage_count
        old_avg = skill.avg_effectiveness
        # actual_gain / estimated_gain = 效果比率（1.0 = 完全符合预估）
        ratio = actual_gain / estimated_gain if estimated_gain > 0 else 1.0

        # 用 ratio 调整有效性分数
        new_effectiveness = old_avg * 0.7 + ratio * 0.3
        new_effectiveness = max(0.1, min(1.0, new_effectiveness))

        skill.avg_effectiveness = new_effectiveness
        skill.usage_count += 1
        self.save()

    def _today(self) -> str:
        from datetime import date
        return date.today().isoformat()
