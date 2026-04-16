# SkillForge Observability Tracing
# 记录 Phase 1-4 各阶段耗时，写入 memory/timings.yaml

import yaml
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, date
from typing import Optional


@dataclass
class PhaseTiming:
    """单次任务的各阶段耗时记录"""
    task_id: str
    task_type: str
    gap_state: str
    phase1_ms: float = 0.0
    phase2_ms: float = 0.0
    phase3_ms: float = 0.0
    phase4_ms: float = 0.0
    total_ms: float = 0.0
    predicted_score: float = 0.0
    actual_score: float = 0.0
    delta: float = 0.0
    outcome: str = ""
    timestamp: str = ""


class TimingLogger:
    """
    Phase 1-4 各阶段耗时记录器。

    用法：
        logger = TimingLogger()
        timing = logger.start_phase1(task_id, task_type, gap_state)
        # ... 各阶段执行 ...
        timing = logger.end_phase4(timing, actual_score, outcome)
        logger.write(timing)
    """

    def __init__(self, timings_path: str = "memory/timings.yaml"):
        self.path = Path(timings_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._timings: list[dict] = []
        self._load()

    def _load(self):
        """加载已有记录"""
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        self._timings = raw.get("timings", [])

    def write(self, timing: PhaseTiming):
        """追加单条记录并持久化"""
        self._timings.append(asdict(timing))
        self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "updated_at": date.today().isoformat(),
            "total_records": len(self._timings),
            "timings": self._timings[-100:],  # 保留最近 100 条
        }
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    def summary(self) -> dict:
        """生成 dashboard 用的耗时统计"""
        if not self._timings:
            return {"avg_total_ms": 0, "avg_phase_ms": {}, "count": 0}

        records = self._timings[-50:]  # 最近 50 条
        n = len(records)

        phase_sums = {
            "phase1_ms": sum(r["phase1_ms"] for r in records),
            "phase2_ms": sum(r["phase2_ms"] for r in records),
            "phase3_ms": sum(r["phase3_ms"] for r in records),
            "phase4_ms": sum(r["phase4_ms"] for r in records),
        }
        total_sums = sum(r["total_ms"] for r in records)

        avg_phase_ms = {k: round(v / n, 1) for k, v in phase_sums.items()}

        return {
            "count": n,
            "avg_total_ms": round(total_sums / n, 1),
            "avg_phase_ms": avg_phase_ms,
            "latest_timing": records[-1] if records else None,
        }
