# SkillForge Stage 4: Reflexion Memory 重试闭环
#
# 功能：下次同类任务执行前，自动加载 L2 反思日志作为上下文。
#       让 Agent 在预判时知道"上次在这里踩过这个坑"。
#
# 设计原则：
#   1. 仅在 stage4.reflexion.enabled = true 时启用
#   2. 按 task_type 过滤，只加载同类型反思
#   3. Token 预算 <200/次，避免注入膨胀
#   4. 零新增依赖，纯 Python 实现

from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import re

from skillforge.models import Reflection


# ── 解析器 ──────────────────────────────────────────────────

def parse_reflections_file(file_path: Path) -> list[dict]:
    """
    解析 reflections.md 文件，提取每个反思条目为结构化 dict。

    支持格式：
        ## [task_id] task_type @ timestamp
        **任务**: ...
        **S**: ...  **A**: ...  **Delta**: ...
        **结果**: ...

        ### 根因
        - ...

        ### 教训
        - ...

        ### 改进
        - ...

        ---
    """
    if not file_path.exists():
        return []

    content = file_path.read_text(encoding="utf-8")
    entries = []

    # 按 "---" 分割条目
    raw_entries = re.split(r"\n---\n", content)

    for raw in raw_entries:
        entry = _parse_single_reflection(raw)
        if entry:
            entries.append(entry)

    return entries


def _parse_single_reflection(raw: str) -> Optional[dict]:
    """解析单个反思条目"""
    if not raw.strip():
        return None

    # 提取 task_id 和 task_type（标题行格式: ## [task_id] task_type @ timestamp）
    header_match = re.search(r"## \[([^\]]+)\] (\w+)\s+@ ", raw)
    if not header_match:
        return None

    task_id = header_match.group(1)
    task_type = header_match.group(2)

    # 提取 Delta
    delta_match = re.search(r"\*\*Delta\*\*:\s*([+-]?\d+(?:\.\d+)?)", raw)
    delta = float(delta_match.group(1)) if delta_match else 0.0

    # 提取 outcome
    outcome_match = re.search(r"\*\*结果\*\*:\s*(\S+)", raw)
    outcome = outcome_match.group(1) if outcome_match else ""

    # 提取 lesson（教训部分）
    lessons = re.findall(r"- (.+)$", raw.split("### 教训")[-1].split("### 改进")[0], re.MULTILINE)
    lesson = lessons[0] if lessons else ""

    # 提取根因
    root_causes = re.findall(r"- (.+)$", raw.split("### 根因")[-1].split("### 教训")[0], re.MULTILINE)

    return {
        "task_id": task_id,
        "task_type": task_type,
        "delta": delta,
        "outcome": outcome,
        "lesson": lesson,
        "root_causes": root_causes,
        "raw": raw,
    }


def format_as_context(reflections: list[dict], task_type: str, max_entries: int = 5) -> str:
    """
    将反思列表格式化为 Phase 1 的注入上下文。

    输出格式示例：
        [L2 反思 - code_generation]
        1. [task_id] Delta=-12 | 教训：异步任务需完善错误处理
        2. [task_id] Delta=-8  | 教训：边界条件处理不够细致
        (仅展示同类型反思，最多 max_entries 条)
    """
    if not reflections:
        return ""

    lines = [f"[L2 反思 - {task_type}]"]
    for i, entry in enumerate(reflections[:max_entries], 1):
        delta_str = f"{entry['delta']:+.1f}"
        lesson = entry.get("lesson", "")[:60]
        lines.append(f"  {i}. [{entry['task_id']}] Delta={delta_str} | {lesson}")

    return "\n".join(lines)


# ── 核心加载器 ──────────────────────────────────────────────

class ReflectionLoader:
    """
    L2 反思加载器。

    使用方式：
        loader = ReflectionLoader(memory_dir="memory")
        context = loader.load_context(task_type="code_generation")
        # context = "[L2 反思 - code_generation]\n  1. [sf-xxx] Delta=-12 ..."

        # 注入 Phase 1 prompt（由 engine.py 拼接）
    """

    def __init__(
        self,
        memory_dir: str = "memory",
        reflections_file: Optional[str] = None,
        max_entries: int = 5,
        max_age_days: int = 90,
        min_delta_threshold: float = -15.0,  # 只加载 delta < -15 的反思（重大失败）
        enabled: bool = True,
    ):
        self.memory_dir = Path(memory_dir)
        self.reflections_file = Path(reflections_file) if reflections_file else self.memory_dir / "reflections.md"
        self.max_entries = max_entries
        self.max_age_days = max_age_days
        self.min_delta_threshold = min_delta_threshold
        self.enabled = enabled

        # 缓存：避免同一次运行中重复解析文件
        self._cache: Optional[list[dict]] = None
        self._cache_mtime: Optional[float] = None

    def load_context(
        self,
        task_type: str,
        limit: Optional[int] = None,
    ) -> str:
        """
        按 task_type 加载同类型反思，格式化为注入字符串。

        Args:
            task_type: 任务类型（如 "code_generation"）
            limit: 可选，覆盖默认 max_entries

        Returns:
            格式化的反思上下文字符串，供 Phase 1 注入
        """
        if not self.enabled:
            return ""

        entries = self._get_filtered_entries(task_type)
        max_k = limit or self.max_entries

        return format_as_context(entries, task_type, max_k)

    def get_recent_lessons(self, task_type: str, limit: int = 3) -> list[str]:
        """
        仅返回教训字符串列表（供决策参考）。

        用于 Phase 2 决策时，告知 Decider "上次同类任务踩过这些坑"。
        """
        if not self.enabled:
            return []

        entries = self._get_filtered_entries(task_type)
        return [e.get("lesson", "") for e in entries[:limit] if e.get("lesson")]

    def get_failure_root_causes(self, task_type: str, limit: int = 5) -> list[str]:
        """
        返回同类任务的历史失败根因列表。

        用于 Phase 3 执行时，提示 Executor "这些坑要绕开"。
        """
        if not self.enabled:
            return []

        all_entries = self._get_filtered_entries(task_type)
        causes = []
        for entry in all_entries:
            for cause in entry.get("root_causes", []):
                if cause not in causes:
                    causes.append(cause)
                if len(causes) >= limit:
                    break
        return causes

    def _get_filtered_entries(self, task_type: str) -> list[dict]:
        """
        获取同类型反思条目，经过滤和排序。

        过滤规则（全部满足才算有效反思）：
          1. task_type 匹配
          2. delta < min_delta_threshold（重大失败）
          3. 尚未过期
        """
        all_entries = self._load_entries()

        cutoff_date = datetime.now() - timedelta(days=self.max_age_days)
        filtered = []

        for entry in all_entries:
            # task_type 匹配
            if entry.get("task_type") != task_type:
                continue

            # delta 过滤（仅重大失败）
            delta = entry.get("delta", 0.0)
            if delta >= self.min_delta_threshold:  # -15 threshold: delta 必须 < -15
                continue

            filtered.append(entry)

        # 按 delta 升序（最惨的排前面）
        filtered.sort(key=lambda x: x.get("delta", 0))
        return filtered

    def _load_entries(self) -> list[dict]:
        """懒加载 + 文件缓存（mtime 变化才重新读）"""
        if not self.reflections_file.exists():
            return []

        # 始终 resolve 路径，避免 symlink 导致缓存失效
        resolved = self.reflections_file.resolve()
        mtime = resolved.stat().st_mtime
        if self._cache is None or self._cache_mtime != mtime:
            self._cache = parse_reflections_file(self.reflections_file)
            self._cache_mtime = mtime

        return self._cache

    def get_stats(self) -> dict:
        """返回 L2 反思统计（调试用）"""
        entries = self._load_entries()
        if not entries:
            return {"total": 0, "by_task_type": {}, "avg_delta": 0.0}

        by_type: dict[str, int] = {}
        for e in entries:
            t = e.get("task_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        deltas = [e.get("delta", 0.0) for e in entries]
        return {
            "total": len(entries),
            "by_task_type": by_type,
            "avg_delta": sum(deltas) / len(deltas) if deltas else 0.0,
        }

    def clear_cache(self) -> None:
        """手动清除缓存（测试用）"""
        self._cache = None
        self._cache_mtime = None


# ── 快捷函数 ──────────────────────────────────────────────

def quick_reflexion_context(
    memory_dir: str = "memory",
    task_type: str = "default",
    max_entries: int = 5,
) -> str:
    """快速加载 L2 反思上下文（单次调用）"""
    loader = ReflectionLoader(memory_dir=memory_dir, max_entries=max_entries)
    return loader.load_context(task_type)