# SkillForge Agent Skill 增强系统
# https://github.com/your-org/skillforge

__version__ = "0.1.0"
__license__ = "Apache-2.0"

from skillforge.models import (
    Skill, SkillRecommendation, Trajectory,
    Phase1Result, Phase2Result, Phase3Result, Phase4Result,
    GapAnalysis, Decision, Reflection, SkillForgeResult
)
from skillforge.registry import SkillRegistry
from skillforge.engine import SkillForgeEngine, SkillForgeOrchestrator, PHASE1_PROMPT_TEMPLATE
from skillforge.decider import EnhancementDecider, GapState, decide_enhancement
from skillforge.evaluator import QualityEvaluator, quick_evaluate
from skillforge.forger import FORGE_PROMPT
from skillforge.executor import EnhancementExecutor, execute_with_skill
from skillforge.config import Config, get_config
from skillforge.indexer import IndexManager

# Stage 3 模块（可选，默认关闭）
from skillforge import mar as mar_module
from skillforge import vector_search as vector_search_module

MARCoordinator = mar_module.MARCoordinator
build_mar_prompt = mar_module.build_mar_prompt
parse_mar_response = mar_module.parse_mar_response
MAR_PROMPT_TEMPLATE = mar_module.MAR_PROMPT_TEMPLATE

VectorSearchProvider = vector_search_module.VectorSearchProvider
HybridSkillMatcher = vector_search_module.HybridSkillMatcher
create_vector_search = vector_search_module.create_vector_search
MockVectorSearchProvider = vector_search_module.MockVectorSearchProvider

# Stage 4 模块（可选，默认关闭）
from skillforge.reflexion import (
    ReflectionLoader,
    format_as_context,
    quick_reflexion_context,
)

__all__ = [
    # Version
    "__version__",
    # Models
    "Skill", "SkillRecommendation", "Trajectory",
    "Phase1Result", "Phase2Result", "Phase3Result", "Phase4Result",
    "GapAnalysis", "Decision", "Reflection",
    # Core modules
    "SkillRegistry",     "SkillForgeEngine", "SkillForgeOrchestrator",
    "EnhancementDecider", "QualityEvaluator",
    "EnhancementExecutor", "GapState",
    "Config", "get_config", "IndexManager",
    # Prompts
    "PHASE1_PROMPT_TEMPLATE", "FORGE_PROMPT",
    # Shortcut functions
    "decide_enhancement", "quick_evaluate", "execute_with_skill",
    # Stage 3 - MAR
    "MARCoordinator", "build_mar_prompt", "parse_mar_response", "MAR_PROMPT_TEMPLATE",
    # Stage 3 - Vector Search
    "VectorSearchProvider", "HybridSkillMatcher", "create_vector_search",
    "MockVectorSearchProvider",
    # Stage 4 - Reflexion
    "ReflectionLoader", "format_as_context", "quick_reflexion_context",
]
