# 配置参考

> `config.yaml` 完整字段说明

---

## 完整配置文件

```yaml
# ────────────────────────────────────────────────────────
# 五态 Gap 阈值
# ────────────────────────────────────────────────────────
gap_thresholds:
  independent_max: 5      # Gap < 5  → independent，直接执行
  light_hints_max: 15     # 5-15    → light-hint，结束时轻提示
  suggest_max: 30          # 15-30   → suggest，询问用户
  force_max: 50           # 30-50   → force-enhance，暂停等确认
  # Gap ≥ 50 → out-of-scope，拒绝执行

# ────────────────────────────────────────────────────────
# Phase 1 预判引擎
# ────────────────────────────────────────────────────────
prediction:
  model: "gpt-4o-mini"           # Phase 1 分析使用的模型（轻量即可）
  prompt_template: "detailed"    # "detailed" | "quick"
  calibration_enabled: true      # 是否启用 L0 历史数据校准

# ────────────────────────────────────────────────────────
# Phase 4 评估权重
# ────────────────────────────────────────────────────────
evaluation:
  default_weight:
    user: 0.6        # 用户评分权重（1-5 星）
    llm_self: 0.3    # LLM 自评权重
    tool: 0.1        # 工具验证权重（代码测试通过率等）
  patch_threshold: 5   # A < S - 5 → 触发 patch 和反思
  forger_trigger: 3    # 同类任务成功 3 次 → 触发自创建 skill

# ────────────────────────────────────────────────────────
# 存储路径
# ────────────────────────────────────────────────────────
storage:
  registry_path: "skillforge-registry.yaml"
  memory_dir: "memory"
  trajectory_retention_days: 90   # L1 轨迹保留天数

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

### 场景 2：只用用户评分，不用 LLM 自评

```yaml
evaluation:
  default_weight:
    user: 1.0
    llm_self: 0.0
    tool: 0.0
```

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
# 或
cfg = get_config("/path/to/config.yaml")

print(cfg.gap_thresholds.suggest_max)  # 30
print(cfg.stage4.reflexion.enabled)    # False
print(cfg.stage3.mar.provider)         # "llm-only"
```
