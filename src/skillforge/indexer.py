# SkillForge L0 Capability Index 管理器
# 三层 Progressive Disclosure 的第一层
# 设计依据：SkillReducer (2025) tiered architecture + Meta-Policy Reflexion (2025) MPM

import yaml
from pathlib import Path
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class TaskTypeEntry(BaseModel):
    count: int = 0
    avg_delta: float = 0.0       # 移动平均：实际分 - 预估分
    trend: str = "stable"         # improving | stable | degrading
    gap_adjustment: int = 0      # 累计修正值（分）
    last_timestamp: Optional[str] = None


class CapabilityIndexMeta(BaseModel):
    version: str = "1.0"
    updated_at: str = ""
    total_executed: int = 0
    global_gap_adjustment: int = 0


class CapabilityIndex(BaseModel):
    task_type_index: dict[str, TaskTypeEntry] = Field(default_factory=dict)
    meta: CapabilityIndexMeta = Field(default_factory=CapabilityIndexMeta)

    class Config:
        arbitrary_types_allowed = True


DEFAULT_TASK_TYPES = [
    "code_generation",
    "code_review",
    "research",
    "seo",
    "kol_outreach",
    "data_analysis",
    "design",
    "writing",
    "conversation",
    "other",
]


class IndexManager:
    """
    L0 Capability Index 管理器

    负责：
    1. 加载 / 持久化 capability-index.yaml
    2. Phase 4 后更新 delta 和 trend
    3. Phase 1 前读取 gap_adjustment，用于预判校准
    """

    ALPHA = 0.2  # 移动平均权重

    def __init__(self, index_path: Optional[str] = None):
        if index_path is None:
            root = self._find_project_root()
            index_path = str(root / "memory" / "capability-index.yaml")
        self.path = Path(index_path)
        # Pydantic 2 BaseModel 会替换 self._index，所以先创建再初始化
        self._index = CapabilityIndex()
        self._init_defaults()
        self.load()

    def _find_project_root(self) -> "Path":
        """向上查找 skillforge 项目根目录"""
        from pathlib import Path as _Path
        cwd = _Path.cwd()
        for p in [cwd, *cwd.parents]:
            if (p / "skillforge-registry.yaml").exists():
                return p
        return cwd

    def _init_defaults(self):
        """初始化默认结构和空条目（只调用一次）"""
        self._index = CapabilityIndex()
        self._index.meta = CapabilityIndexMeta(
            version="1.0",
            updated_at="",
            total_executed=0,
            global_gap_adjustment=0,
        )
        for tt in DEFAULT_TASK_TYPES:
            self._index.task_type_index[tt] = TaskTypeEntry()

    # ── 持久化 ────────────────────────────────────────────

    def load(self):
        """从 YAML 加载索引（覆盖内存中同名条目；不存在的条目保持默认值）"""
        if not self.path.exists():
            return

        with open(self.path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        # 只更新元信息（不清空已有条目的累积数据）
        meta_raw = raw.get("_meta", {})
        self._index.meta.version = meta_raw.get("version", "1.0")
        self._index.meta.updated_at = meta_raw.get("updated_at", "")
        self._index.meta.total_executed = meta_raw.get("total_executed", 0)
        self._index.meta.global_gap_adjustment = meta_raw.get("global_gap_adjustment", 0)

        raw_tti = raw.get("task_type_index", {})
        for tt_name, entry_raw in raw_tti.items():
            self._index.task_type_index[tt_name] = TaskTypeEntry(
                count=entry_raw.get("count", 0),
                avg_delta=float(entry_raw.get("avg_delta", 0.0)),
                trend=entry_raw.get("trend", "stable"),
                gap_adjustment=int(entry_raw.get("gap_adjustment", 0)),
                last_timestamp=entry_raw.get("last_timestamp"),
            )

    def save(self):
        """持久化到 YAML"""
        self._ensure_memory_dir()
        self._index.meta.updated_at = date.today().isoformat()

        raw_tti = {}
        for name, entry in self._index.task_type_index.items():
            raw_tti[name] = {
                "count": entry.count,
                "avg_delta": entry.avg_delta,
                "trend": entry.trend,
                "gap_adjustment": entry.gap_adjustment,
                "last_timestamp": entry.last_timestamp,
            }

        data = {
            "task_type_index": raw_tti,
            "_meta": {
                "version": self._index.meta.version,
                "updated_at": self._index.meta.updated_at,
                "total_executed": self._index.meta.total_executed,
                "global_gap_adjustment": self._index.meta.global_gap_adjustment,
            },
        }

        with open(self.path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    def _init_defaults(self):
        """初始化默认 task_type 条目"""
        self._index.meta = CapabilityIndexMeta(
            version="1.0",
            updated_at=date.today().isoformat(),
            total_executed=0,
            global_gap_adjustment=0,
        )
        for tt in DEFAULT_TASK_TYPES:
            self._index.task_type_index[tt] = TaskTypeEntry()

    def _ensure_memory_dir(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ── 查询 ──────────────────────────────────────────────

    @property
    def index(self) -> CapabilityIndex:
        return self._index

    def get_entry(self, task_type: str) -> TaskTypeEntry:
        """获取指定 task_type 的索引条目（不存在则创建空条目）"""
        if task_type not in self._index.task_type_index:
            self._index.task_type_index[task_type] = TaskTypeEntry()
        return self._index.task_type_index[task_type]

    def get_gap_adjustment(self, task_type: str) -> int:
        """Phase 1 校准用：返回该 task_type 的 gap_adjustment"""
        return self.get_entry(task_type).gap_adjustment

    def get_global_adjustment(self) -> int:
        """全局修正值"""
        return self._index.meta.global_gap_adjustment

    # ── 更新 ──────────────────────────────────────────────

    def update(
        self,
        task_type: str,
        predicted_score: float,
        actual_score: float,
        timestamp: Optional[str] = None,
    ):
        """
        Phase 4 评估后调用：更新 L0 索引

        Args:
            task_type: 任务类型
            predicted_score: Phase 1 预估分 S
            actual_score: Phase 4 实际分 A
            timestamp: ISO 格式时间戳
        """
        if timestamp is None:
            timestamp = date.today().isoformat()

        entry = self.get_entry(task_type)
        delta = actual_score - predicted_score

        # 移动平均更新 avg_delta
        entry.avg_delta = (
            self.ALPHA * delta + (1 - self.ALPHA) * entry.avg_delta
        )

        # 累计计数
        entry.count += 1
        entry.last_timestamp = timestamp

        # 更新 trend
        if entry.count >= 5:
            if abs(entry.avg_delta) > 10:
                entry.trend = "degrading"
            elif abs(entry.avg_delta) < 5 and entry.count >= 3:
                entry.trend = "improving"
            else:
                entry.trend = "stable"

        # 更新 gap_adjustment（累计修正值）
        entry.gap_adjustment = int(round(entry.avg_delta * 2))

        # 全局修正值（指数移动平均）
        self._index.meta.total_executed += 1
        self._index.meta.global_gap_adjustment = int(
            round(self._index.meta.global_gap_adjustment * 0.95 + delta * 0.05)
        )

        self.save()

    # ── 统计摘要 ──────────────────────────────────────────

    def summary(self) -> dict:
        """生成 dashboard 用的统计摘要"""
        entries = []
        for name, entry in self._index.task_type_index.items():
            if entry.count > 0:
                entries.append({
                    "task_type": name,
                    "count": entry.count,
                    "avg_delta": round(entry.avg_delta, 1),
                    "trend": entry.trend,
                    "gap_adjustment": entry.gap_adjustment,
                    "last_timestamp": entry.last_timestamp,
                })

        entries.sort(key=lambda x: x["count"], reverse=True)

        return {
            "total_executed": self._index.meta.total_executed,
            "global_gap_adjustment": self._index.meta.global_gap_adjustment,
            "updated_at": self._index.meta.updated_at,
            "task_types": entries,
        }
