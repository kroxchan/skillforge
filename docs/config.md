# 配置参考

> `config.yaml` 完整字段说明

---

## 完整配置文件

```yaml
# ────────────────────────────────────────────────────────
# 五态 Gap 阈值
# ────────────────────────────────────────────────────────
gap_thresholds:
  independent_max: 5      # Gap < 5   → independent，直接执行
  light_hints_max: 15     # 5-15     → light-hint，结束时轻提示
  suggest_max: 30          # 15-30    → suggest，询问用户
  force_max: 50           # 30-50    → force-enhance，暂停等确认
  # Gap ≥ 50 → out-of-scope，拒绝执行

# ────────────────────────────────────────────────────────
# Phase 1 预判引擎
# ────────────────────────────────────────────────────────
prediction:
  model: "gpt-4o-mini"           # Phase 1 分析使用的模型（轻量即可）
  prompt_template: "detailed"    # "detailed" | "quick"
  # calibration_enabled 已废弃：L0 历史校准默认开启，无法关闭

# ────────────────────────────────────────────────────────
# Phase 4 评估
# ────────────────────────────────────────────────────────
evaluation:
  # v0.1.2 起评分公式简化：actual = predicted，delta = (rating - 3) × 20
  # 旧字段 default_weight / patch_threshold 已废弃
  forger_trigger: 5    # 同类任务累计 count ≥ 5 次 → 触发自创建 skill（Forger）

# ────────────────────────────────────────────────────────
# 存储路径
# ────────────────────────────────────────────────────────
storage:
  registry_path: "skillforge-registry.yaml"
  memory_dir: "memory"
  trajectory_retention_days: 90   # L1 轨迹保留天数（仅 Python 批量引擎产出）

# ────────────────────────────────────────────────────────
# Stage 3: 多 Agent 协作（可选，默认全部关闭）
# ────────────────────────────────────────────────────────
stage3:
  enabled: false

  # MAR 多角色辩论评估
  mar:
    enabled: false
    # provider: 执行环境
    #   "cursor"       — Cursor IDE（Task tool），无需额外 API key
    #   "claude-code"  — Claude Code，无需额外 API key
    #   "codex"        — Codex（Agents SDK），需要 OPENAI_API_KEY
    #   "llm-only"     — 直接调 LLM（无多 agent 环境时的降级）
    provider: "llm-only"
    llm_endpoint: ""           # llm-only 模式下的端点
    llm_model: "gpt-4o-mini"
    single_pass: true          # 三 Critic + Judge 合并为单次调用（节省 token）

  # 向量语义检索
  vector_search:
    enabled: false
    provider: "mock"           # "chroma"（需要 pip install chromadb）| "mock"
    chroma:
      persist_dir: ".chroma/"
      model: "all-MiniLM-L6-v2"   # sentence-transformers 模型
      distance_metric: "cosine"
    keyword_weight: 0.6        # 关键词匹配权重
    semantic_weight: 0.4       # 语义向量权重
    max_candidates: 5

  # 共享索引（社区贡献，可选）
  shared_index:
    enabled: false
    source: "local"            # "local" | "gist" | "http"
    gist_url: ""
    http_endpoint: ""
    share_level: "index"       # "none" | "index"（仅统计数据）| "trajectory"
    auto_pull: true
    auto_push: false           # 每次推送都需手动确认

# ────────────────────────────────────────────────────────
# Stage 4: Reflexion Memory 重试闭环（可选，默认关闭）
# ────────────────────────────────────────────────────────
stage4:
  enabled: false
  reflexion:
    enabled: false
    max_entries: 5             # Phase 1 最多注入多少条历史反思
    max_age_days: 90           # 超过多少天的反思不加载
    min_delta_threshold: -5.0  # 只加载 delta < -5 的失败反思（过滤轻微失误）
    inject_in_phase1: true     # Phase 1 前是否注入反思上下文
```

---

## 常用配置场景

### 场景 1：更激进的 skill 触发

如果你希望 Agent 更频繁地建议 skill：

```yaml
gap_thresholds:
  independent_max: 3     # 原来 5，降低独立执行门槛
  light_hints_max: 10    # 原来 15
  suggest_max: 20        # 原来 30
  force_max: 40          # 原来 50
```

### 场景 2：Forger 更快触发（新用户积累期）

```yaml
evaluation:
  forger_trigger: 3      # 原来 5，前期快速积累 skill 草稿
```

⚠ 降低阈值的副作用：草稿可能基于样本不足的统计数据，需要你在审核时更谨慎地补充 Trigger Conditions。

### 场景 3：启用 Reflexion，宽松过滤条件

```yaml
stage4:
  reflexion:
    enabled: true
    max_entries: 8
    min_delta_threshold: -3.0   # 连轻微失败也会被注入提醒
    max_age_days: 30            # 只参考最近一个月
```

### 场景 4：Cursor 环境下启用 MAR

```yaml
stage3:
  mar:
    enabled: true
    provider: "cursor"          # 使用 Cursor Task tool，零额外 API 费用
```

---

## Python 中读取配置

```python
from skillforge.config import get_config

cfg = get_config()  # 自动查找最近的 config.yaml
cfg = get_config("/path/to/config.yaml")

print(cfg.gap_thresholds.suggest_max)     # 30
print(cfg.evaluation.forger_trigger)      # 5
print(cfg.stage4.reflexion.enabled)       # False
print(cfg.stage3.mar.provider)            # "llm-only"
print(cfg.storage.memory_dir)             # 绝对路径（v0.2.8 起自动绝对化）
```

**关于路径处理**（v0.2.8 起）：

`storage.registry_path` 和 `storage.memory_dir` 即使写的是相对路径（`"memory"`），`Config.load()` 会自动绝对化到项目根目录。这保证 `sf` 命令在任意 CWD（如 `/tmp` / 用户工作区）下都能找到正确的数据文件。

---

## 已废弃字段说明

以下字段在老版本 config.yaml 中存在，v0.2.x 已删除，出现时会被忽略：

| 字段 | 废弃版本 | 原因 |
|------|---------|------|
| `prediction.calibration_enabled` | v0.2.0 | L0 历史校准始终开启，开关无意义 |
| `evaluation.default_weight.user/llm_self/tool` | v0.1.2 | 评分公式简化为 `actual = predicted`，不再加权 |
| `evaluation.patch_threshold` | v0.1.2 | 用 rating=1 直接触发反思，不再用 delta 阈值 |
| `output.*`（整个 section） | v0.2.0 | rich 输出格式交给 CLI 本身控制 |
