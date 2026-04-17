# SkillForge 数据模型

from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal, Any
from dataclasses import dataclass, field

from pydantic import BaseModel, Field


# ── Core Enums ─────────────────────────────────────────

class GapStateEnum(str):
    INDEPENDENT = "independent"
    LIGHT_HINTS = "light_hints"
    SUGGEST = "suggest"
    FORCE = "force"
    OUT_OF_SCOPE = "out_of_scope"


class OutcomeEnum(str):
    SUCCESS = "success"
    SUCCESS_WITHIN_TOLERANCE = "success_within_tolerance"
    PATCH_NEEDED = "patch_needed"


# ── Skill Models ────────────────────────────────────────

class Skill(BaseModel):
    skill_id: str
    name: str
    domain: list[str] = Field(default_factory=list)
    task_types: list[str] = Field(default_factory=list)
    capability_gains: dict[str, float] = Field(default_factory=dict)
    quality_tier: Literal["unknown", "L1", "L2", "L3"] = "unknown"
    usage_count: int = 0
    avg_effectiveness: float = 0.7
    source: Literal["local", "community", "autoforge"] = "local"
    path: str = ""
    trigger_keywords: list[str] = Field(default_factory=list)
    description: str = ""


class SkillRecommendation(BaseModel):
    skill: Skill
    match_score: float = 0.0
    estimated_gain: float = 0.0
    reason: str = ""


# ── Phase Results ───────────────────────────────────────

class Phase1Result(BaseModel):
    predicted_score: float = 50.0
    task_difficulty: float = 70.0
    gap: float = 20.0
    gap_level: Literal["independent", "light-hint", "suggest", "force-enhance", "out-of-scope"] = "suggest"
    capability_dimensions: dict[str, Any] = Field(default_factory=dict)
    task_types: list[str] = Field(default_factory=list)
    recommended_skill_types: list[str] = Field(default_factory=list)


class Phase2Result(BaseModel):
    selected_skill: Optional[Skill] = None
    enhanced_estimate: float = 50.0
    alternatives: list[Skill] = Field(default_factory=list)
    user_decision: str = ""


class Phase3Result(BaseModel):
    execution_trace: list[dict[str, Any]] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    skill_content_used: str = ""


class Phase4Result(BaseModel):
    actual_score: float = 50.0
    outcome: Literal["success", "success_within_tolerance", "patch_needed"] = "success"
    delta: float = 0.0  # 用户感受与预估的偏差：(rating-3)*20，用于校准 gap_adjustment
    user_rating: Optional[int] = None
    reflection: Optional[str] = None
    # Stage 3: MAR 多角色辩论结果（由 MARCoordinator.evaluate() 填充）
    mar_result: Optional[dict] = None


# ── Trajectory ──────────────────────────────────────────

class Trajectory(BaseModel):
    task_id: str
    task_description: str
    task_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    phase1: Phase1Result = Field(default_factory=Phase1Result)
    phase2: Phase2Result = Field(default_factory=Phase2Result)
    phase3: Phase3Result = Field(default_factory=Phase3Result)
    phase4: Phase4Result = Field(default_factory=Phase4Result)


# ── Gap Analysis ────────────────────────────────────────

class GapAnalysis(BaseModel):
    dimensions: dict[str, float] = Field(default_factory=dict)
    total_gap: float = 0.0
    predicted_score: float = 50.0
    task_types: list[str] = Field(default_factory=list)
    recommended_skill_types: list[str] = Field(default_factory=list)


# ── Decision ────────────────────────────────────────────

class Decision(BaseModel):
    action: Literal[
        "execute_direct",
        "light_hints",
        "suggest_enhancement",
        "force_enhancement",
        "refuse",
    ] = "execute_direct"
    message: str = ""
    wait_for_confirm: bool = False
    options: list[SkillRecommendation] = Field(default_factory=list)
    allow_direct_execution: bool = False


# ── Reflection ──────────────────────────────────────────

class Reflection(BaseModel):
    task_id: str
    task_type: str = ""       # 任务类型（Stage 4 用于 L2 索引过滤）
    predicted: float = 0.0
    actual: float = 0.0
    delta: float = 0.0
    outcome: str = ""
    root_causes: list[str] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    related_trajectory_path: str = ""


# ── Engine Result ────────────────────────────────────────

class SkillForgeResult(BaseModel):
    """SkillForge 完整执行结果"""
    task_id: str
    task_description: str
    task_type: str
    trajectory: Trajectory
    phase4: Phase4Result
    index_updated: bool = False
    effectiveness_updated: bool = False
    decision: Decision = Field(default_factory=Decision)
    phase3_context: str = ""   # Phase 3 构建的增强 prompt（供外部执行）
    forger_draft_path: Optional[str] = None  # Forger 草稿路径（触发后非 None）
