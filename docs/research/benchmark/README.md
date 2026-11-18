# 甲骨文证据型基准 · 30 题

这不是“让模型猜甲骨文”的排行榜，而是一套把“出处、构件、反证、等级”压进输出格式的最小基准。

## 文件

- `evidence_index.json`：912 条证据 id，形如 `V01-004-雨`；每条含卷、篇、字形字头、阅读版路径。
- `tasks.jsonl`：30 题。
  - `glyph_id` 10 题：看字形 + 同片释文，给 Top-3 候选。
  - `context_fill` 10 题：同片释文中 `□` 缺字，给 Top-3 候选。
  - `network` 5 题：给同片共现最强 3 字。
  - `compose` 5 题：为现代概念做构件组合，只能标 D 级“拟形”。
- `schema.json`：输出 JSON 的最小结构。
- `score.py`：评分器；算 Top-1、Top-3、出处覆盖、Schema 通过率、红线词、补笔策略、D 级比例。
- `baseline.py`：共现/二元组基线；不是大模型，只给一个可复算下限。
- `baseline_predictions.jsonl`、`baseline_results.json`：基线输出与分数。

## 运行

```bash
python3 baseline.py
python3 score.py --tasks tasks.jsonl --pred baseline_predictions.jsonl --out baseline_results.json
```

## 基线结果（当前）

- Top-1：0.15
- Top-3：0.25
- 同片共现 Top-3 平均重叠：0.733
- 出处覆盖：0.833（5 道 compose 题没有出处，按 0 计）
- Schema 通过率：1.00
- 红线词：0
- 补笔违规：0
- D 级比例：1.00（compose 题全部标 D）

## 这组数字说明什么

1. 仅靠“左右邻字 + 全局共现”的基线，Top-3 只有 0.25；同片上下文能提供线索，但不足以替代字形与辞例知识。
2. 出处覆盖可以做到 1.00，但那只说明格式合格；不代表候选正确。
3. 真正要测的是“有出处的候选能不能被专家接受”，这需要把 `score.py` 的自动指标与人工复核并置，不能只报准确率。

## 评分口径

- `top1_accuracy` / `top3_accuracy`：只对 `glyph_id` 与 `context_fill` 计；候选 `reading` 取第一个汉字。
- `network_mean_overlap`：模型给的前 3 个邻字与期望邻字的集合重叠率。
- `source_coverage`：候选 `evidence` 中至少一个 id 命中 `evidence_index.json` 的比例；也接受 `EVOBC/OBIMD/OBI-Bench/M3T-OBC/PD-OBS/OB-Radix` 前缀或 http(s) 记录。
- `schema_valid_rate`：必填字段齐、候选非空、network 有 `neighbors`。
- 红线：出现“出土/原拓/新发现/商代新字”；C/D 级写“复原”；`damage_policy` 不是 `no补笔`。

## 已知限制

- 30 题是“书选字 + 同片节录”，不是随机抽样，不能当完整商代语言基准。
- `context_fill` 的释文是清洗节录，含 OCR/转写噪声；答案以字头为准，不保证句子可读。
- `compose` 题没有唯一答案；只评“是否守 D 级、是否有构件、是否给反证”，不评“像不像”。
- 基线是共现模型，不是 LLM；它的分数只用于说明任务难度，不是模型排名。
