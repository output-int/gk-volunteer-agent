# 数据导入管线

本项目把真实数据导入拆成两步：

1. 从官方 PDF/Excel/网页抽取并人工校验为 CSV。
2. 使用 `import_data.py` 校验 CSV 并写入 SQLite。

`import_data.py` 不负责 PDF/Excel 自动解析。原因是官方文件排版变化较多，直接自动抽取容易把院校代码、专业组、最低分、备注列错位。第一版把它设计成最终入库闸门，更可靠。

## 目录

```text
data/templates/admission_history_template.csv
data/templates/score_rank_table_template.csv
data/templates/subject_requirement_template.csv
data/templates/school_major_profile_template.csv
data/samples/admission_history_sample.csv
data/samples/score_rank_table_sample.csv
data/samples/subject_requirement_sample.csv
data/samples/school_major_profile_sample.csv
data/source_manifest.json
```

## 导入录取历史

先 dry-run 校验：

```powershell
python import_data.py --table admission_history --csv data/samples/admission_history_sample.csv --dry-run
```

写入数据库：

```powershell
python import_data.py --table admission_history --csv data/samples/admission_history_sample.csv
```

替换同一年、省份、科类、批次的已有数据：

```powershell
python import_data.py --table admission_history --csv data/samples/admission_history_sample.csv --replace-scope
```

`--replace-scope` 会删除 CSV 中涉及的：

```text
year + province + subject_type + batch
```

对应记录，再插入新数据。

## 导入一分一段表

先 dry-run 校验：

```powershell
python import_data.py --table score_rank_table --csv data/samples/score_rank_table_sample.csv --dry-run
```

写入数据库：

```powershell
python import_data.py --table score_rank_table --csv data/samples/score_rank_table_sample.csv
```

替换同一年、省份、科类的已有数据：

```powershell
python import_data.py --table score_rank_table --csv data/samples/score_rank_table_sample.csv --replace-scope
```

`--replace-scope` 会删除 CSV 中涉及的：

```text
year + province + subject_type
```

对应记录，再插入新数据。

## 导入 2026 选科要求

先 dry-run 校验：

```powershell
python import_data.py --table subject_requirement --csv data/samples/subject_requirement_sample.csv --dry-run
```

写入数据库：

```powershell
python import_data.py --table subject_requirement --csv data/samples/subject_requirement_sample.csv
```

替换同一学校、专业、要求年份的已有数据：

```powershell
python import_data.py --table subject_requirement --csv data/samples/subject_requirement_sample.csv --replace-scope
```

`--replace-scope` 会删除 CSV 中涉及的：

```text
school_name + major_name + requirement_year
```

对应记录，再插入新数据。

## 导入专业画像

先 dry-run 校验：

```powershell
python import_data.py --table school_major_profile --csv data/samples/school_major_profile_sample.csv --dry-run
```

写入数据库：

```powershell
python import_data.py --table school_major_profile --csv data/samples/school_major_profile_sample.csv
```

替换同一学校、专业的已有画像：

```powershell
python import_data.py --table school_major_profile --csv data/samples/school_major_profile_sample.csv --replace-scope
```

`--replace-scope` 会删除 CSV 中涉及的：

```text
school_name + major_name
```

对应记录，再插入新数据。

## 补数闭环

当 `validate_data.py` 提示缺专业画像或缺 2026 选科要求时，推荐按以下顺序处理：

1. 导出补数清单：

```powershell
python validate_data.py --export-gaps outputs/data_gaps
```

2. 参照模板补齐 CSV：

```text
data/templates/subject_requirement_template.csv
data/templates/school_major_profile_template.csv
```

3. dry-run 校验：

```powershell
python import_data.py --table subject_requirement --csv data/samples/subject_requirement_sample.csv --dry-run
python import_data.py --table school_major_profile --csv data/samples/school_major_profile_sample.csv --dry-run
```

4. 替换式导入：

```powershell
python import_data.py --table subject_requirement --csv data/samples/subject_requirement_sample.csv --replace-scope
python import_data.py --table school_major_profile --csv data/samples/school_major_profile_sample.csv --replace-scope
```

5. 严格复查：

```powershell
python validate_data.py --strict-warnings
```

`verify_data_quality.py` 会在临时库中验证“导入补充 CSV 后，对应补数缺口减少”，用于防止补数流程失效。

## 字段要求

CSV 字段必须和模板完全一致，包括顺序。

录取历史模板：

```text
data/templates/admission_history_template.csv
```

一分一段模板：

```text
data/templates/score_rank_table_template.csv
```

2026 选科要求模板：

```text
data/templates/subject_requirement_template.csv
```

专业画像模板：

```text
data/templates/school_major_profile_template.csv
```

## 校验规则

导入器会校验：

- 年份必须是 2021-2026。
- 科类必须是 `物理` 或 `历史`。
- 批次必须是 `本科批`、`专科批`、`提前批`。
- 招生类型必须是 `普通类`、`中外合作`、`民族班`、`预科`、`专项`。
- 分数必须在 0-750。
- 位次必须为正数。
- `rank_max >= rank_min`。
- `cumulative_count >= rank_max`。
- `above_batch_line_count` 用于等效位次折算，必须来自同年同科类一分一段或官方批次线统计口径。
- `source_type` 必须是 `official`、`third_party`、`manual_verified`。
- `confidence` 必须是 `high`、`medium`、`low`。
- `first_subject_required` 必须是 `物理`、`历史`、`物理或历史均可`。
- `effective_from` 必须是 2021-2026，`effective_to` 可空或不晚于 2030。
- `school_major_profile.source_url` 必填，画像类文字字段可空但建议补全。

## 官方来源策略

真实导入时优先使用：

- 重庆市教育考试院
- 重庆招考信息网
- 阳光高考
- 高校本科招生网或招生章程

第三方整理数据只能用于交叉校验。除非已核验其原始来源，否则不得标记为 `official`。

## 真实数据替换建议

建议按年份和科类逐步替换：

1. 2025 物理本科批录取历史
2. 2025 历史本科批录取历史
3. 2025 物理/历史一分一段表
4. 2024 数据
5. 2021-2023 数据

每导入一个范围后运行：

```powershell
python verify_recommender.py
python verify_api.py
python validate_data.py --strict-warnings
```

## 重庆 2025 真实数据导入

已提供可复现脚本：

```powershell
python scripts/import_cq_2025_real_data.py
```

该脚本会：

- 下载或复用本地 `data/raw/cq/2025/` 下的原始 PDF/HTML。
- 抽取并生成：
  - `data/cleaned/cq/2025/score_rank_table_2025_chongqing.csv`
  - `data/cleaned/cq/2025/admission_history_2025_chongqing_benke.csv`
- 调用 `import_data.py` 的同一套校验逻辑写入 `gaokao_agent.db`。
- 使用 `--replace-scope` 替换 2025 重庆物理/历史一分一段表，以及 2025 重庆物理/历史本科批投档表。

只抽取 CSV、不写数据库：

```powershell
python scripts/import_cq_2025_real_data.py --extract-only
```

只校验 CSV、不写数据库：

```powershell
python scripts/import_cq_2025_real_data.py --dry-run
```

导入后验证：

```powershell
python verify_cq_2025_real_data.py
python validate_data.py
```

当前 2025 数据口径：

- 一分一段表：物理 502 行，历史 473 行。
- 本科批投档表：物理 11464 行，历史 3786 行。
- 物理本科线 425，本科线上人数 103219。
- 历史本科线 438，本科线上人数 35253。
- 招生信息 PDF 不直接给出最低位次；`admission_history.min_rank` 按同年同科类一分一段表中投档最低分对应的累计人数折算。
- 因存在上述折算，投档表行 `source_type` 使用 `manual_verified`，`confidence` 使用 `medium`。

`data/raw/` 是原始下载文件目录，已加入 `.gitignore`。清洗 CSV 保留在 `data/cleaned/`，便于复查和重复导入。
