# SkillForge 增强执行器（Phase 3）
# 使用 skill 内容增强执行，同时记录完整轨迹

import subprocess
import tempfile
from typing import Optional, Callable
from pathlib import Path
from skillforge.models import Trajectory, Phase3Result, Skill


class EnhancementExecutor:
    """
    Phase 3: 增强执行器

    职责：
    1. 读取 skill 内容并注入 context
    2. 执行任务，记录完整轨迹
    3. 捕获错误，追踪工具调用
    """

    def __init__(
        self,
        base_system_prompt: str = "",
        memory_dir: str = "memory/trajectories"
    ):
        self.base_system_prompt = base_system_prompt
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def build_enhanced_prompt(
        self,
        skill: Optional[Skill],
        task_context: str,
        task_description: str
    ) -> str:
        """
        构建增强后的 system prompt。

        Args:
            skill: 要注入的 skill（None = 无 skill）
            task_context: Phase 1 分析结果
            task_description: 原始任务描述

        Returns:
            拼接后的完整 system prompt
        """
        sections = [self.base_system_prompt]

        # Skill 内容注入
        if skill:
            skill_path = Path(skill.path)
            if skill_path.exists():
                skill_content = skill_path.read_text(encoding="utf-8")
                sections.append(f"\n\n## 启用 Skill: {skill.name}\n\n{skill_content}")
            else:
                sections.append(f"\n\n## 启用 Skill: {skill.name}\n\n[Skill 文件不存在：{skill.path}]")

        # 任务上下文
        if task_context:
            sections.append(f"\n\n## 当前任务\n\n{task_description}\n\n## 任务分析\n\n{task_context}")

        return "\n\n---\n\n".join(sections)

    def save_trajectory(
        self,
        trajectory: Trajectory,
        output_dir: Optional[Path] = None
    ) -> Path:
        """保存执行轨迹到文件"""
        if output_dir is None:
            output_dir = self.memory_dir

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filepath = output_dir / f"{trajectory.task_id}.md"

        content = self._format_trajectory_markdown(trajectory)
        filepath.write_text(content, encoding="utf-8")

        return filepath

    def _format_trajectory_markdown(self, trajectory: Trajectory) -> str:
        """将轨迹格式化为 Markdown"""
        from datetime import datetime

        lines = [
            f"# 执行轨迹",
            "",
            f"**任务ID**：{trajectory.task_id}",
            f"**时间**：{trajectory.timestamp or datetime.now().isoformat()}",
            f"**任务类型**：{trajectory.task_type}",
            "",
            "---",
            "",
            "## Phase 1: 预判",
            "",
            f"- 预估分 S：{trajectory.phase1.predicted_score}",
            f"- 任务难度 T：{trajectory.phase1.task_difficulty}",
            f"- 缺口 Gap：{trajectory.phase1.gap}",
            f"- 缺口等级：{trajectory.phase1.gap_level}",
            "",
            "## Phase 2: Skill 匹配",
            "",
        ]

        if trajectory.phase2.selected_skill:
            lines.append(f"- 选中 Skill：{trajectory.phase2.selected_skill.name}")
            lines.append(f"- 增强后预估：{trajectory.phase2.enhanced_estimate}")
        else:
            lines.append("- 未启用 Skill")
        lines.append(f"- 用户决策：{trajectory.phase2.user_decision}")
        lines.append("")

        lines.extend([
            "## Phase 3: 执行",
            "",
            f"- 工具调用：{', '.join(trajectory.phase3.tools_used) or '（无）'}",
            f"- 执行错误：{len(trajectory.phase3.errors)} 个",
        ])

        if trajectory.phase3.errors:
            for err in trajectory.phase3.errors:
                lines.append(f"  - `{err}`")
        lines.append("")

        if trajectory.phase3.execution_trace:
            lines.append("### 执行轨迹详情")
            for i, step in enumerate(trajectory.phase3.execution_trace, 1):
                lines.append(f"{i}. {step.get('action', 'unknown')}")
                if step.get("input"):
                    lines.append(f"   输入：{step['input']}")
                if step.get("output"):
                    output = str(step["output"])
                    lines.append(f"   输出：{output[:200]}{'...' if len(output) > 200 else ''}")
            lines.append("")

        if trajectory.phase4:
            lines.extend([
                "## Phase 4: 评估",
                "",
                f"- 实际分 A：{trajectory.phase4.actual_score}",
                f"- 结果：{trajectory.phase4.outcome}",
                f"- Delta（S-A）：{trajectory.phase1.predicted_score - trajectory.phase4.actual_score:.1f}",
            ])

        lines.append("")
        lines.append("---")
        lines.append(f"*轨迹文件由 SkillForge 自动生成*")

        return "\n".join(lines)


# 快捷函数
def execute_with_skill(
    task_description: str,
    skill: Optional[Skill] = None,
    task_context: str = ""
) -> str:
    """
    快速构建增强后的执行 prompt。

    使用方法：
    enhanced_prompt = execute_with_skill(
        task_description="帮我写一个 Python 爬虫",
        skill=my_skill,
        task_context=phase1_result
    )
    # 将 enhanced_prompt 发给 LLM 执行
    """
    executor = EnhancementExecutor()
    return executor.build_enhanced_prompt(
        skill=skill,
        task_context=task_context,
        task_description=task_description
    )


# ── Sandbox Runner ──────────────────────────────────────

class SandboxRunner:
    """
    代码类任务的自动沙盒验证。

    支持：
    - Python: 运行 pytest / 直接执行，捕获输出和错误
    - 未来可扩展：JavaScript (Node.js)、Shell 等

    用法：
        runner = SandboxRunner(timeout_seconds=30)
        result = runner.run("print('hello')")
        # result = {"passed": True/False, "stdout": "...", "stderr": "...", "exit_code": 0}
    """

    SUPPORTED = {"python", "javascript", "shell"}

    def __init__(
        self,
        timeout_seconds: int = 30,
        runner_dir: Optional[str] = None,
    ):
        self.timeout = timeout_seconds
        self.runner_dir = Path(runner_dir) if runner_dir else Path(tempfile.mkdtemp(prefix="skillforge_sandbox_"))

    def run(self, code: str, language: str = "python") -> dict:
        """
        在沙盒中运行代码。

        Args:
            code: 要执行的代码
            language: 语言类型（python/javascript/shell）

        Returns:
            {"passed": bool, "stdout": str, "stderr": str, "exit_code": int}
        """
        if language not in self.SUPPORTED:
            return {
                "passed": False,
                "stdout": "",
                "stderr": f"Unsupported language: {language}",
                "exit_code": 1,
            }

        self.runner_dir.mkdir(parents=True, exist_ok=True)
        suffix = {".py": "python", ".js": "javascript", ".sh": "shell"}.get(
            Path(code).suffix, ""
        )
        ext = {".py": ".py", "python": ".py", ".js": ".js", "javascript": ".js", ".sh": ".sh", "shell": ".sh"}.get(
            language, ".txt"
        )
        code_file = self.runner_dir / f"sandbox_script{ext}"

        # 处理多行代码
        code_file.write_text(code, encoding="utf-8")

        try:
            if language in ("python", ".py") or ext == ".py":
                result = subprocess.run(
                    ["python3", str(code_file)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
            elif language in ("javascript", ".js") or ext == ".js":
                result = subprocess.run(
                    ["node", str(code_file)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
            else:
                result = subprocess.run(
                    ["bash", str(code_file)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "stdout": "",
                "stderr": f"Timeout after {self.timeout}s",
                "exit_code": 124,
            }
        except FileNotFoundError as e:
            return {
                "passed": False,
                "stdout": "",
                "stderr": f"Runtime not found: {e}",
                "exit_code": 127,
            }

        return {
            "passed": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }

    def cleanup(self):
        """清理临时目录"""
        import shutil
        if self.runner_dir.exists():
            shutil.rmtree(self.runner_dir, ignore_errors=True)
