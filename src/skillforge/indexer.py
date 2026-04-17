# SkillForge L0 Capability Index 管理器
# 三层 Progressive Disclosure 的第一层
# 设计依据：SkillReducer (2025) tiered architecture + Meta-Policy Reflexion (2025) MPM

import re
import uuid
import yaml
from pathlib import Path
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


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

    model_config = ConfigDict(arbitrary_types_allowed=True)


DEFAULT_TASK_TYPE: str = "default"
"""所有模块统一引用此常量作为兜底 task_type，禁止在代码中散落 "default" 字符串。"""

DEFAULT_TASK_TYPES = [
    # v0.2.7 起 Registry 默认空，_load_default_task_types_from_registry() 总返回 ["default"]
    # Registry 累积 skill 后此函数将恢复动态加载，作为 IndexManager 初始化的 task_type 种子
    DEFAULT_TASK_TYPE,
]


def _find_registry_path() -> Optional[Path]:
    """向上查找 skillforge-registry.yaml。

    策略一：从 CWD 向上找；策略二：从 __file__ 向上找（CWD 非项目根时的 fallback）。
    """
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        candidate = p / "skillforge-registry.yaml"
        if candidate.exists():
            return candidate

    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        candidate = p / "skillforge-registry.yaml"
        if candidate.exists():
            return candidate

    return None


def _load_default_task_types_from_registry() -> list[str]:
    """
    从 Registry 提取全部 task_types，作为 L0 索引的默认 task_type 集合。

    这是 task_type 的**单一权威数据源**：新增 skill 到 Registry 时会自动扩展
    L0 索引默认条目，不再需要同步维护 indexer 的硬编码列表。

    降级策略：
    - 找不到 Registry / import 失败 → 返回 ["default"]
    """
    try:
        from skillforge.registry import SkillRegistry  # 延迟导入避免循环依赖
        reg_path = _find_registry_path()
        if reg_path is None:
            return list(DEFAULT_TASK_TYPES)
        reg = SkillRegistry(registry_path=str(reg_path))
        task_types = {"default"}
        for skill in reg.list_skills():
            task_types.update(skill.task_types)
        return sorted(task_types)
    except Exception:
        return list(DEFAULT_TASK_TYPES)


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
        self.load()

    def _find_project_root(self) -> "Path":
        """向上查找 skillforge 项目根目录"""
        from pathlib import Path as _Path
        cwd = _Path.cwd()
        for p in [cwd, *cwd.parents]:
            if (p / "skillforge-registry.yaml").exists():
                return p
        return cwd

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
        """初始化默认 task_type 条目（从 Registry 动态加载，单一数据源）"""
        self._index.meta = CapabilityIndexMeta(
            version="1.0",
            updated_at=date.today().isoformat(),
            total_executed=0,
            global_gap_adjustment=0,
        )
        for tt in _load_default_task_types_from_registry():
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
        delta: float,
        timestamp: Optional[str] = None,
    ):
        """
        Phase 4 评估后调用：更新 L0 索引

        Args:
            task_type: 任务类型
            predicted_score: Phase 1 预估分 S
            actual_score: Phase 4 实际分 A（= predicted_score，评分约定）
            delta: 用户感受与预估的偏差（=(rating-3)*20），用于校准 gap_adjustment
            timestamp: ISO 格式时间戳
        """
        if timestamp is None:
            timestamp = date.today().isoformat()

        entry = self.get_entry(task_type)

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


# ── Phase 4 Helper：text-level patch，保留 yaml 注释 + 审计注释 ──────────
#
# 用途：mdc 规则通过 `sf update-l0` 命令调用本函数，完成 Phase 4 闭环
# 优势：
#   1. 保留 yaml 原文所有注释（含历史审计记录）
#   2. 每次调用追加一条审计注释到对应条目末尾
#   3. 原子写入（tmp → rename），防止写中断损坏文件
#   4. 单点维护：Agent 不再需要理解 yaml 结构，一行命令搞定

_L0_BLOCK_PATTERN = re.compile(
    r"(^  )({key}):\s*\n",
    re.MULTILINE,
)


def update_l0_file(
    index_path: Path,
    task_type: str,
    rating: int,
    task_desc: str,
    predicted: float,
    task_id: Optional[str] = None,
    alpha: float = 0.2,
) -> dict:
    """
    Phase 4 helper：原子更新 capability-index.yaml，保留注释 + 追加审计条目。

    参数:
        index_path:  capability-index.yaml 绝对路径
        task_type:   任务类型（从 Registry 中选最贴近的一项，兜底用 "default"）
        rating:      用户评分 1 / 3 / 5
        task_desc:   任务摘要（建议 ≤50 字符，用于审计追溯）
        predicted:   Phase 1 预估分 S（0-100）
        task_id:     可选，默认自动生成 sf-{8位hex}
        alpha:       EMA 权重，默认 0.2

    返回:
        dict 格式的更新摘要（供 CLI 展示 / JSON 输出）

    副作用:
        - 修改 index_path 对应的 yaml 文件
        - 若 rating=1，在 index_path 同目录的 reflections.md 追加反思模板骨架
    """
    if task_id is None:
        task_id = f"sf-{uuid.uuid4().hex[:8]}"
    delta = (rating - 3) * 20
    timestamp = datetime.now().isoformat(timespec="minutes")

    if not index_path.exists():
        raise FileNotFoundError(f"capability-index.yaml 不存在: {index_path}")

    text = index_path.read_text(encoding="utf-8")

    # 定位目标 task_type 条目块（key 行 + 缩进 4 空格的 body）
    pattern = re.compile(
        r"(^  " + re.escape(task_type) + r":\n)"       # key 行
        r"((?:    [^\n]*\n|\n)*?)"                     # body（4 空格缩进 / 空行）
        r"(?=^  [A-Za-z_]|^_meta:|\Z)",                # 前看：下一个 key 或 _meta 或 EOF
        re.MULTILINE,
    )
    m = pattern.search(text)

    audit_line = (
        f"    # [{task_id}] {timestamp} {task_desc} "
        f"| S={predicted:.0f} | rating={rating} | delta={delta:+d}\n"
    )

    if m is None:
        # 条目不存在：在 _meta 之前插入一个新条目
        new_trend = "stable"  # 新条目 count=1，不满足门槛，直接 stable
        new_block = (
            f"\n  {task_type}:\n"
            f"    count: 1\n"
            f"    avg_delta: {float(delta):.2f}\n"
            f"    trend: {new_trend}\n"
            f"    gap_adjustment: {delta}\n"
            + audit_line
        )
        text = re.sub(r"^_meta:", new_block + "\n_meta:", text, count=1, flags=re.MULTILINE)
        new_count, new_avg, new_gap = 1, float(delta), delta
    else:
        key_line, body = m.group(1), m.group(2)

        cnt_m = re.search(r"count:\s*(\d+)", body)
        avg_m = re.search(r"avg_delta:\s*([-+]?\d+(?:\.\d+)?)", body)
        gap_m = re.search(r"gap_adjustment:\s*([-+]?\d+)", body)

        old_count = int(cnt_m.group(1)) if cnt_m else 0
        old_avg = float(avg_m.group(1)) if avg_m else 0.0

        new_count = old_count + 1
        new_avg = alpha * delta + (1 - alpha) * old_avg
        new_gap = int(round(new_avg * 2))

        new_body = body
        new_body = re.sub(r"(count:\s*)\d+",
                          f"count: {new_count}", new_body, count=1)
        new_body = re.sub(r"(avg_delta:\s*)[-+]?\d+(?:\.\d+)?",
                          f"avg_delta: {new_avg:.2f}", new_body, count=1)
        new_body = re.sub(r"(gap_adjustment:\s*)[-+]?\d+",
                          f"gap_adjustment: {new_gap}", new_body, count=1)

        # trend 更新（与 IndexManager.update() 保持一致）
        # 门槛：count ≥ 5 后才开始判定，避免早期噪声
        if new_count >= 5:
            if abs(new_avg) > 10:
                new_trend = "degrading"
            elif abs(new_avg) < 5:
                new_trend = "improving"
            else:
                new_trend = "stable"
        else:
            # count < 5：读取原始 trend，不做改动
            trend_m = re.search(r"trend:\s*(\w+)", body)
            new_trend = trend_m.group(1) if trend_m else "stable"
        new_body = re.sub(r"(trend:\s*)\w+", f"trend: {new_trend}", new_body, count=1)

        # 追加审计注释行到 body 尾部（保留已有注释）
        new_body = new_body.rstrip("\n") + "\n" + audit_line + "\n"

        text = text[: m.start()] + key_line + new_body + text[m.end():]

    # 更新 _meta 块
    if re.search(r"last_task_id:\s*\S+", text):
        text = re.sub(r"(last_task_id:\s*)\S+",
                      f"last_task_id: {task_id}", text, count=1)
    else:
        text = re.sub(r"(total_executed:\s*\d+)",
                      rf"last_task_id: {task_id}\n  \1", text, count=1)

    te_m = re.search(r"total_executed:\s*(\d+)", text)
    if te_m:
        new_te = int(te_m.group(1)) + 1
        text = re.sub(r"(total_executed:\s*)\d+",
                      f"total_executed: {new_te}", text, count=1)

    # global_gap_adjustment：EMA（与 IndexManager.update() 保持一致）
    # 公式：new = round(old * 0.95 + delta * 0.05)
    gga_m = re.search(r"global_gap_adjustment:\s*([-+]?\d+)", text)
    old_gga = int(gga_m.group(1)) if gga_m else 0
    new_gga = int(round(old_gga * 0.95 + delta * 0.05))
    text = re.sub(
        r"(global_gap_adjustment:\s*)[-+]?\d+",
        f"global_gap_adjustment: {new_gga}",
        text, count=1,
    )

    text = re.sub(
        r'(updated_at:\s*)["\']?[\d\-]+["\']?',
        f'updated_at: "{date.today().isoformat()}"', text, count=1
    )

    # 原子写回
    tmp_path = index_path.with_suffix(".yaml.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(index_path)

    # 若 rating=1，追加反思模板骨架到 reflections.md
    reflection_written = False
    if rating == 1:
        refl_path = index_path.parent / "reflections.md"
        tmpl = (
            f"\n## [{task_id}] {task_type} @ {timestamp}\n"
            f"**任务**: {task_desc}\n"
            f"**S**: {predicted:.0f}  **A**: {predicted:.0f}  **delta**: {delta:+d}\n\n"
            f"### root cause\n"
            f"- TODO: 从三个内因维度分析（禁止外部归因）\n"
            f"  1. 我对任务的理解\n"
            f"  2. 我对复杂度的预判\n"
            f"  3. 我的执行策略\n\n"
            f"### lessons\n- TODO\n\n"
            f"### next time\n- TODO\n"
        )
        if refl_path.exists():
            with open(refl_path, "a", encoding="utf-8") as f:
                f.write(tmpl)
        else:
            refl_path.write_text(
                "# SkillForge 反思记录\n\n> 由 Phase 4 在 rating=1 时自动追加模板骨架\n"
                + tmpl,
                encoding="utf-8",
            )
        reflection_written = True

    # ── Forger 涌现触发检查（v0.2.6）────────────────────────
    # 当某 task_type 累计 count ≥ 5 且 Registry 无对应 skill 时，
    # 自动生成轻量骨架草稿到 memory/self-made/。不阻塞主流程。
    forger_draft_path: Optional[str] = None
    try:
        from skillforge.forger import should_forge, forge_draft
        registry_path = _find_registry_path()
        if registry_path is not None and should_forge(
            task_type=task_type,
            index_path=index_path,
            registry_path=registry_path,
            memory_dir=index_path.parent,
        ):
            draft = forge_draft(
                task_type=task_type,
                index_path=index_path,
                memory_dir=index_path.parent,
            )
            if draft is not None:
                forger_draft_path = str(draft)
    except Exception:
        # Forger 失败不得影响 L0 写入（主流程已经完成）
        forger_draft_path = None

    return {
        "task_id": task_id,
        "task_type": task_type,
        "rating": rating,
        "delta": delta,
        "predicted": predicted,
        "new_count": new_count,
        "new_avg_delta": round(new_avg, 2),
        "new_gap_adjustment": new_gap,
        "new_trend": new_trend if m else "stable",
        "new_global_gap_adjustment": new_gga,
        "reflection_written": reflection_written,
        "forger_draft_path": forger_draft_path,
    }
