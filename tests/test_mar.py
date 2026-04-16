# SkillForge Stage 3: MAR 模块测试

import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skillforge.mar import (
    MARCoordinator, build_mar_prompt, parse_mar_response,
    MAR_PROMPT_TEMPLATE,
)
from skillforge.models import (
    Trajectory, Phase1Result, Phase2Result,
    Phase3Result, Phase4Result,
)


# ── Fixture ────────────────────────────────────────────────

def _make_trajectory(
    task_id="test-001",
    task_type="code_generation",
    predicted=80,
    actual=75,
    skill_name="Code Expert Skill",
):
    return Trajectory(
        task_id=task_id,
        task_description="写一个 Python 异步爬虫，抓取多个网站数据",
        task_type=task_type,
        timestamp=datetime.now(),
        phase1=Phase1Result(predicted_score=predicted, gap=20, gap_level="L2"),
        phase2=Phase2Result(selected_skill=None, user_decision="skip"),
        phase3=Phase3Result(tools_used=["bash", "read"], errors=[]),
        phase4=Phase4Result(actual_score=actual),
    )


def _make_phase4(actual=75, outcome="success_within_tolerance"):
    return Phase4Result(actual_score=actual, outcome=outcome)


# ── 测试 ────────────────────────────────────────────────────

def test_build_mar_prompt_contains_roles():
    """MAR prompt 包含三个 Critic 角色"""
    traj = _make_trajectory()
    phase4 = _make_phase4()
    prompt = build_mar_prompt(traj, phase4)

    assert "优点发现者" in prompt or "Optimist" in prompt
    assert "漏洞发现者" in prompt or "Skeptic" in prompt
    assert "盲点检查员" in prompt or "Domain Expert" in prompt
    assert "裁判" in prompt or "Judge" in prompt
    assert "code_generation" in prompt
    assert "80" in prompt          # predicted
    assert "75" in prompt          # actual
    print("  [PASS] MAR prompt 包含三角色 + Judge")


def test_parse_json_with_code_fence():
    """解析带 markdown code fence 的 JSON"""
    raw = '''
Here's my analysis:

```json
{
  "optimist": "代码结构清晰，异步并发设计合理",
  "skeptic": "错误处理不完善，网络超时会直接崩溃",
  "domain_expert": "未处理 robots.txt 限制，存在合规风险",
  "judge": {
    "final_score": 73,
    "delta_adjustment": -2,
    "lesson": "异步爬虫必须完善错误处理和超时机制",
    "trigger_improvement": "是",
    "improvement_note": "建议生成爬虫错误处理 SKILL.md"
  }
}
```
'''
    result = parse_mar_response(raw)

    assert result["optimist"] == "代码结构清晰，异步并发设计合理"
    assert result["skeptic"] == "错误处理不完善，网络超时会直接崩溃"
    assert result["judge"]["final_score"] == 73
    assert result["judge"]["trigger_improvement"] == "是"
    print("  [PASS] JSON 解析：code fence + 正常 JSON")


def test_parse_bare_json():
    """解析裸 JSON（无 code fence）"""
    raw = '{"optimist":"OK","skeptic":"issues","domain_expert":"blind","judge":{"final_score":80,"delta_adjustment":0,"lesson":"fine","trigger_improvement":"否","improvement_note":""}}'
    result = parse_mar_response(raw)

    assert result["optimist"] == "OK"
    assert result["judge"]["final_score"] == 80
    assert result["judge"]["trigger_improvement"] == "否"
    print("  [PASS] JSON 解析：裸 JSON")


def test_parse_invalid_json_fallback():
    """非法 JSON 兜底：返回空 dict，不崩溃"""
    raw = "This is not JSON at all"
    result = parse_mar_response(raw)
    assert result == {}
    print("  [PASS] JSON 解析：非法 JSON 兜底不崩溃")


def test_mar_disabled_returns_dummy():
    """MAR 未启用时返回兜底结果"""
    coordinator = MARCoordinator(enabled=False)
    traj = _make_trajectory(predicted=80, actual=75)
    phase4 = _make_phase4(actual=75)

    result = coordinator.evaluate(traj, phase4)

    assert result["judge"]["final_score"] == 75
    assert result["judge"]["trigger_improvement"] is False
    assert result["optimist"] == "(MAR 未启用)"
    assert result["raw"] == ""
    print("  [PASS] MAR disabled → 兜底结果")


def test_mar_enabled_with_mock_llm():
    """MAR 启用 + mock LLM 响应"""
    mock_response = '''
{
  "optimist": "异步并发设计合理",
  "skeptic": "缺少超时和重试机制",
  "domain_expert": "未考虑反爬策略",
  "judge": {
    "final_score": 72,
    "delta_adjustment": -3,
    "lesson": "网络 IO 任务必须加入超时和重试",
    "trigger_improvement": "是",
    "improvement_note": "生成网络任务 SKILL.md"
  }
}
'''
    coordinator = MARCoordinator(enabled=True)

    # Mock httpx 调用（llm-only 路径）
    with patch.object(coordinator._adapter, "_call_llm", return_value=mock_response):
        traj = _make_trajectory(predicted=80, actual=75)
        phase4 = _make_phase4(actual=75)
        result = coordinator.evaluate(traj, phase4)

    assert result["optimist"] == "异步并发设计合理"
    assert result["skeptic"] == "缺少超时和重试机制"
    assert result["judge"]["final_score"] == 72
    assert result["judge"]["delta_adjustment"] == -3
    assert result["judge"]["trigger_improvement"] is True
    assert result["judge"]["lesson"] == "网络 IO 任务必须加入超时和重试"
    assert "raw" in result
    print("  [PASS] MAR enabled + mock LLM → 完整结果")


def test_mar_cursor_provider_falls_back():
    """provider=cursor 时，evaluate() 捕获 NotImplementedError 并回退到 dummy"""
    coordinator = MARCoordinator(enabled=True, provider="cursor")
    traj = _make_trajectory()
    phase4 = _make_phase4()

    # NotImplementedError 由 evaluate() 内部捕获，回退到 dummy 结果
    # 不会上抛，这是正确行为
    result = coordinator.evaluate(traj, phase4)

    # 回退结果：final_score = 原始 actual_score
    assert result["judge"]["final_score"] == 75
    assert result["optimist"] == "(MAR 未启用)"
    assert result["raw"] == ""
    print("  [PASS] provider=cursor → 回退到 dummy（预期行为）")


def test_build_cursor_prompt():
    """build_cursor_prompt 生成可直接在 Cursor 中粘贴的 prompt"""
    coordinator = MARCoordinator(enabled=True, provider="cursor")
    traj = _make_trajectory()
    phase4 = _make_phase4()

    prompt = coordinator.build_cursor_prompt(traj, phase4)

    assert "code_generation" in prompt
    assert "80" in prompt
    assert "75" in prompt
    assert "JSON" in prompt
    print("  [PASS] Cursor prompt 可直接粘贴到 Cursor session")


def test_mar_single_pass_token_efficiency():
    """验证 MAR 设计满足 token 效率要求：单次调用"""
    # 单次调用的判断：prompt 模板同时包含所有角色，不做多次往返
    assert "优点发现者" in MAR_PROMPT_TEMPLATE or "Optimist" in MAR_PROMPT_TEMPLATE
    assert "漏洞发现者" in MAR_PROMPT_TEMPLATE or "Skeptic" in MAR_PROMPT_TEMPLATE
    assert "裁判" in MAR_PROMPT_TEMPLATE or "Judge" in MAR_PROMPT_TEMPLATE

    # 所有角色在同一个 prompt 里，一次 LLM 调用完成
    prompt = build_mar_prompt(_make_trajectory(), _make_phase4())
    assert prompt.count("角色") >= 3 or prompt.count("role") >= 3
    print("  [PASS] Token 效率：单次调用完成所有 Critic 评估")


# ── 运行 ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== SkillForge Stage 3 MAR 测试 ===\n")
    test_build_mar_prompt_contains_roles()
    test_parse_json_with_code_fence()
    test_parse_bare_json()
    test_parse_invalid_json_fallback()
    test_mar_disabled_returns_dummy()
    test_mar_enabled_with_mock_llm()
    test_mar_cursor_provider_falls_back()
    test_build_cursor_prompt()
    test_mar_single_pass_token_efficiency()
    print("\n[ALL PASS] 9/9 MAR 测试通过\n")
