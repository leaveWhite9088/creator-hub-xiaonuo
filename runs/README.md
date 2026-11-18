# runs/ — 选手运行沙盒与评测留档目录

本目录按运行批次（`runs/<模型标识>/`）存放全生命周期产物（过程与实测数据不入 Git 版本库，本地完整留档备查）：

| 路径 | 产生阶段 | 说明 |
| --- | --- | --- |
| `runs/<名>/workspace/` | 开局（`start_run.py`）与选手开发期 | 选手专属前端沙盒目录（含 `TASK.md`、`CONTRACT.md`、`DECISIONS.md`、`smoke_public.py` 及选手交付的离线网页文件） |
| `runs/<名>/protocol.json` | 开局创建、打包冻结 | 记录起点时间 `t0`、结束时间 `t1`、端到端秒数、环境哈希 `env_commit` 及代码冻结承诺 `code_sha256` |
| `runs/<名>/token_usage.json` | 选手收尾自报 | 词元消耗统计留档（仅作成本诊断，不参与算分） |
| `runs/<名>/result.json` | 出榜（`finalize.py` 调 `score_run.py`） | 三波无头浏览器实测原始物理指标、逐项检查结果与外网拦截明细 |
| `runs/<名>/评分.json` | 出榜（`finalize.py` 调 `score_run.py`） | 连续插值定稿后的 A/B/C 客观得分明细（满分 70 分） |
| `runs/<名>/audit_report.md` | 出榜（`finalize.py` 调 `score_run.py`） | 人类可读的物理测量与缺陷定位审计报告 |
| `runs/<名>/wave_trace.jsonl` | 出榜（`finalize.py` 调 `score_run.py`） | 三波浏览器剧本每一步动作与断言的时间线日志 |
