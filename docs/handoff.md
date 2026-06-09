# Handoff: 高考志愿填报 Agent

## 1. 当前任务目标

搭建一个本地纯 Python 运行的“高考志愿填报 Agent”原型。核心原则是：

- 历史分数、位次、选科要求等事实数据走 SQLite 结构化库。
- 推荐、过滤、冲稳保分档走确定性 Python 规则。
- Markdown 报告只做解释、归纳和人工核验提示。
- 不再考虑 Coze、Coze 插件、OpenAPI 对接或平台部署。

## 2. 已完成内容

- SQLite 初始化：
  - `db/init.sql`
  - `init_db.py`
  - Mock 数据覆盖重庆普通类本科批、物理/历史、中外合作、民族班、计算机、临床医学、师范、电子信息等场景。
- 推荐核心：
  - `gaokao_recommender.py`
  - 支持选科硬过滤、等效位次、冲稳保分档、波动风险、特殊招生类型偏好。
- 本地 API 与网页：
  - `api_server.py`
  - `GET /`
  - `POST /recommend`
  - `POST /report`
  - `GET /web/report`
  - `GET /web/report.md`
  - `GET /data-quality`
  - `GET /web/data-quality`
  - `GET /web/data-gaps.csv`
  - `GET /web/data-gaps.md`
- 本地终端 Agent：
  - `local_agent.py`
  - 支持交互式输入、非交互参数、JSON/Markdown 输出、运行快照保存。
  - 运行快照包含 `official_checks.json`，用于人工核验任务流转。
- 官方核验清单：
  - `report_renderer.py` 提供 `build_official_checks()`。
  - `/report` 返回 `recommendation`、`official_checks` 和 `markdown_report`。
  - Markdown 报告会列出 2026 招生章程、选科、专业组、计划数、校区、学费等人工核验事项。
- 数据导入与补数闭环：
  - `import_data.py`
  - 支持导入 `admission_history`、`score_rank_table`、`subject_requirement`、`school_major_profile`。
  - 支持 `--dry-run` 和 `--replace-scope`。
  - `validate_data.py` 可导出补数清单。
- 测试和 CI：
  - `run_checks.py`
  - `verify_recommender.py`
  - `verify_api.py`
  - `verify_local_agent.py`
  - `verify_importer.py`
  - `verify_data_quality.py`
  - GitHub Actions CI 已配置并持续通过。
- Git 状态：
  - 以当前工作树和 `git log -1` 为准。
  - 之前已确认提交包括数据质量、补数清单、导入器、网页数据质量页、特殊招生类型控制等。

## 3. 关键文件和位置

- 数据库 schema 和 Mock 数据：`db/init.sql`
- 初始化数据库：`init_db.py`
- 推荐规则：`gaokao_recommender.py`
- Markdown 报告渲染：`report_renderer.py`
- FastAPI 服务和本地网页：`api_server.py`
- 终端 Agent：`local_agent.py`
- CSV 导入：`import_data.py`
- 数据质量校验和补数清单：`validate_data.py`
- 批量案例评测：`evaluate_cases.py`
- 统一检查入口：`run_checks.py`
- 数据导入文档：`docs/data_import.md`
- 报告模板说明：`docs/report_template.md`
- 当前交接文档：`docs/handoff.md`
- CSV 模板：
  - `data/templates/admission_history_template.csv`
  - `data/templates/score_rank_table_template.csv`
  - `data/templates/subject_requirement_template.csv`
  - `data/templates/school_major_profile_template.csv`
- CSV 样例：
  - `data/samples/admission_history_sample.csv`
  - `data/samples/score_rank_table_sample.csv`
  - `data/samples/subject_requirement_sample.csv`
  - `data/samples/school_major_profile_sample.csv`

## 4. 重要规则和限制

- 项目路线限定为本地纯 Python，不继续开发 Coze、OpenAPI、Coze 文档或平台部署。
- Mock 数据只用于开发测试，不代表真实录取数据。
- 正式使用前必须核验重庆市教育考试院、重庆招考信息网、阳光高考和高校招生章程。
- LLM 不应负责数字计算、位次判断、选科硬过滤或事实性结论。
- 默认推荐池保守：
  - 普通类默认可进入推荐。
  - 中外合作需要 `accept_sino_foreign=true` 或显式加入 `accepted_admission_types`。
  - 民族班、预科、专项需要显式加入 `accepted_admission_types`。
- 2026 选科要求必须优先于 2021-2023 历史选科信息。
- 不要把 `openapi/`、`docs/coze_workflow.md`、`docs/openapi_integration.md` 作为后续开发依据。
- 生成文件和运行输出应放在 `outputs/`，该目录已被 `.gitignore` 忽略。

## 5. 已确认结论

- `python run_checks.py` 在当前功能集下通过。
- GitHub Actions CI 已配置；提交后以 GitHub Actions 最新运行结果为准。
- 本地 API 可用启动命令：

```powershell
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload
```

- 当前本地浏览器页面为：

```text
http://127.0.0.1:8000/web/data-quality
```

- 数据质量页可以显示当前 SQLite 质量状态、WARN/ERROR、表记录数和补数清单预览。
- 补数闭环已经验证：
  - 导出缺口。
  - 填写 `subject_requirement` / `school_major_profile` CSV。
  - 导入。
  - 缺口数量减少。
- 特殊招生类型偏好已经验证：
  - 默认过滤民族班等特殊类型。
  - 显式接受后可以进入推荐和搜索结果。

## 6. 待确认事项

- 待确认：真实重庆近 5 年录取数据来源、字段结构、授权和清洗流程。
- 待确认：2026 年各高校招生章程、专业组代码、选科要求、校区、学费、体检限制。
- 待确认：一分一段表中“本科线上人数”的真实口径和年份覆盖。
- 待确认：是否需要把 `examples/recommend_response.json` 中早期乱码占位示例替换为真实中文示例。

## 7. 不要重复做的事情

- 不要重新设计 Coze 工作流、OpenAPI 规格或 Coze 插件。
- 不要重写现有 SQLite schema，除非真实数据字段证明必须变更。
- 不要把推荐逻辑改成 LLM 直接判断分数、位次或录取概率。
- 不要移除硬规则过滤：选科、招生类型、特殊资格限制必须在推荐前处理。
- 不要重复搭建 Docker/部署路线；当前重点是本地运行和真实数据导入。
- 不要重复实现 CSV 导入器已有能力；应基于 `import_data.py` 扩展。

## 8. 建议下一步

建议下一步操作：

1. 继续保持每轮变更后运行：

```powershell
python run_checks.py
```

2. 查看当前工作树：

```powershell
git status -sb
git diff --stat
```

3. 下一轮功能建议：
   - 优先替换/扩展真实数据导入样例。
   - 增加 `official_checks` 的 CSV/Markdown 下载。
   - 增加“真实数据导入后推荐结果对比”的回归评测。
   - 待确认是否需要修复 `examples/recommend_response.json` 里的早期乱码占位。
