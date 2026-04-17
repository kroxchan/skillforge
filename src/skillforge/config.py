# SkillForge 配置加载器
# 统一管理 config.yaml，所有模块通过 Config.get() 获取配置

import os
import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


def _find_project_root() -> Path:
    """向上查找 skillforge 项目根目录。

    策略一（优先）：从当前工作目录向上找 config.yaml / skillforge-registry.yaml。
    策略二（关键 fallback）：从本文件（__file__）向上找。
        pip install -e 保留源文件原位，__file__ 指向
        .../SKILLFORGE/src/skillforge/config.py，向上即为项目根。
        这保证了 sf 命令在任意 CWD（如 /tmp、用户工作仓库）下都能找到数据目录。
    """
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        if (p / "config.yaml").exists() or (p / "skillforge-registry.yaml").exists():
            return p

    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if (p / "skillforge-registry.yaml").exists():
            return p
        if (p / "config.yaml").exists():
            return p

    return cwd


@dataclass
class GapThresholds:
    independent_max: float = 5.0
    light_hints_max: float = 15.0
    suggest_max: float = 30.0
    force_max: float = 50.0


@dataclass
class PredictionConfig:
    model: str = "gpt-4o-mini"
    prompt_template: str = "detailed"


@dataclass
class EvaluationConfig:
    patch_threshold: float = 5.0
    forger_trigger: int = 5  # v0.2: 从 3 改为 5，降低自创建门槛


@dataclass
class StorageConfig:
    registry_path: str = "skillforge-registry.yaml"
    memory_dir: str = "memory"
    trajectory_retention_days: int = 90


@dataclass
class MARConfig:
    enabled: bool = False
    provider: str = "llm-only"  # "cursor" | "claude-code" | "codex" | "llm-only"
    llm_endpoint: str = ""
    llm_model: str = "gpt-4o-mini"
    single_pass: bool = True


@dataclass
class ChromaConfig:
    persist_dir: str = ".chroma"
    model: str = "all-MiniLM-L6-v2"
    distance_metric: str = "cosine"


@dataclass
class VectorSearchConfig:
    enabled: bool = False
    provider: str = "mock"  # "chroma" | "mock"
    chroma: ChromaConfig = field(default_factory=ChromaConfig)
    keyword_weight: float = 0.6
    semantic_weight: float = 0.4
    max_candidates: int = 5


@dataclass
class SharedIndexConfig:
    enabled: bool = False
    source: str = "local"  # "local" | "gist" | "http"
    gist_url: str = ""
    http_endpoint: str = ""
    share_level: str = "index"  # "none" | "index" | "trajectory"
    auto_pull: bool = True
    auto_push: bool = False


@dataclass
class Stage3Config:
    enabled: bool = False
    mar: MARConfig = field(default_factory=MARConfig)
    vector_search: VectorSearchConfig = field(default_factory=VectorSearchConfig)
    shared_index: SharedIndexConfig = field(default_factory=SharedIndexConfig)


@dataclass
class ReflexionConfig:
    enabled: bool = False
    max_entries: int = 5       # Phase 1 每次最多注入多少条反思
    max_age_days: int = 90     # 超过多少天的反思不加载
    min_delta_threshold: float = -5.0  # delta < 此值才加载（过滤轻微失误）
    inject_in_phase1: bool = True   # Phase 1 前是否注入反思上下文


@dataclass
class Stage4Config:
    enabled: bool = False
    reflexion: ReflexionConfig = field(default_factory=ReflexionConfig)


@dataclass
class Config:
    gap_thresholds: GapThresholds = field(default_factory=GapThresholds)
    prediction: PredictionConfig = field(default_factory=PredictionConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    stage3: Stage3Config = field(default_factory=Stage3Config)
    stage4: Stage4Config = field(default_factory=Stage4Config)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        root = _find_project_root()
        if config_path is None:
            config_path = root / "config.yaml"
        else:
            config_path = Path(config_path)
            if config_path.is_absolute():
                root = config_path.parent

        if not config_path.exists():
            return cls._with_absolute_storage(root)

        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        gt = raw.get("gap_thresholds", {})
        ev = raw.get("evaluation", {})
        st = raw.get("storage", {})
        pred = raw.get("prediction", {})
        s3_raw = raw.get("stage3", {})

        mar_raw = s3_raw.get("mar", {})
        vs_raw = s3_raw.get("vector_search", {})
        si_raw = s3_raw.get("shared_index", {})
        chroma_raw = vs_raw.get("chroma", {})

        def _abs(p: str) -> str:
            """将相对路径绝对化到项目根，绝对路径不变。"""
            pp = Path(p)
            return str(pp if pp.is_absolute() else root / pp)

        return cls(
            gap_thresholds=GapThresholds(
                independent_max=float(gt.get("independent_max", 5.0)),
                light_hints_max=float(gt.get("light_hints_max", 15.0)),
                suggest_max=float(gt.get("suggest_max", 30.0)),
                force_max=float(gt.get("force_max", 50.0)),
            ),
            prediction=PredictionConfig(
                model=pred.get("model", "gpt-4o-mini"),
                prompt_template=pred.get("prompt_template", "detailed"),
            ),
            evaluation=EvaluationConfig(
                patch_threshold=float(ev.get("patch_threshold", 5.0)),
                forger_trigger=int(ev.get("forger_trigger", 5)),
            ),
            storage=StorageConfig(
                registry_path=_abs(st.get("registry_path", "skillforge-registry.yaml")),
                memory_dir=_abs(st.get("memory_dir", "memory")),
                trajectory_retention_days=int(st.get("trajectory_retention_days", 90)),
            ),
            stage3=Stage3Config(
                enabled=s3_raw.get("enabled", False),
                mar=MARConfig(
                    enabled=mar_raw.get("enabled", False),
                    provider=mar_raw.get("provider", "llm-only"),
                    llm_endpoint=mar_raw.get("llm_endpoint", ""),
                    llm_model=mar_raw.get("llm_model", "gpt-4o-mini"),
                    single_pass=mar_raw.get("single_pass", True),
                ),
                vector_search=VectorSearchConfig(
                    enabled=vs_raw.get("enabled", False),
                    provider=vs_raw.get("provider", "mock"),
                    chroma=ChromaConfig(
                        persist_dir=chroma_raw.get("persist_dir", ".chroma"),
                        model=chroma_raw.get("model", "all-MiniLM-L6-v2"),
                        distance_metric=chroma_raw.get("distance_metric", "cosine"),
                    ),
                    keyword_weight=float(vs_raw.get("keyword_weight", 0.6)),
                    semantic_weight=float(vs_raw.get("semantic_weight", 0.4)),
                    max_candidates=int(vs_raw.get("max_candidates", 5)),
                ),
                shared_index=SharedIndexConfig(
                    enabled=si_raw.get("enabled", False),
                    source=si_raw.get("source", "local"),
                    gist_url=si_raw.get("gist_url", ""),
                    http_endpoint=si_raw.get("http_endpoint", ""),
                    share_level=si_raw.get("share_level", "index"),
                    auto_pull=si_raw.get("auto_pull", True),
                    auto_push=si_raw.get("auto_push", False),
                ),
            ),
            stage4=Stage4Config(
                enabled=raw.get("stage4", {}).get("enabled", False),
                reflexion=ReflexionConfig(
                    enabled=raw.get("stage4", {}).get("reflexion", {}).get("enabled", False),
                    max_entries=int(raw.get("stage4", {}).get("reflexion", {}).get("max_entries", 5)),
                    max_age_days=int(raw.get("stage4", {}).get("reflexion", {}).get("max_age_days", 90)),
                    min_delta_threshold=float(
                        raw.get("stage4", {}).get("reflexion", {}).get("min_delta_threshold", -5.0)
                    ),
                    inject_in_phase1=raw.get("stage4", {}).get("reflexion", {}).get("inject_in_phase1", True),
                ),
            ),
        )

    @classmethod
    def _with_absolute_storage(cls, root: Path) -> "Config":
        """构造默认 Config，storage 路径绝对化到给定 root（无 config.yaml 时使用）。"""
        return cls(
            storage=StorageConfig(
                registry_path=str(root / "skillforge-registry.yaml"),
                memory_dir=str(root / "memory"),
            )
        )


# 全局单例
_config: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    global _config
    if _config is None:
        _config = Config.load(config_path)
    return _config
