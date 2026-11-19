# 赛制与全流程协议 · creator-hub-xiaonuo v4.0

> 本文件面向基准维护者、独立评委与出榜操作者说明完整运行协议；被测试者（选手）仅允许阅读 `AGENTS.md` 的 `§0–§1` 及各自沙盒目录内的 `TASK.md` 与 `CONTRACT.md`。

---

## 1. 两角色信任域与隔离承诺

1. **被测试者（选手域）**：
   - 执行 `python tools/start_run.py --model <名>` 启动计时 `t0`，释放沙盒模板（含官方只读 `mock_backend.js`），同时将核心评测文件与官方后端联合哈希写入 `runs/<名>/protocol.json` 的 `env_commit`；
   - 仅在 `runs/<名>/workspace/`（及收尾前必须清空的 `draft/`）内读写，**严禁修改或替换 `mock_backend.js`**；
   - 收尾执行 `python src/scoring/judge_pack.py --model <名>`，自动核验 `mock_backend.js` 原件完整性、冻结结束时钟 `t1`、写入沙盒代码哈希 `code_sha256`，生成脱敏盲评包 `leaderboard/blind/<pack_id>/` 与私有映射 `leaderboard/blind-maps/<model_id>.<pack_id>.blind-map.json`。
2. **独立评委与收官汇总域**：
   - **盲评阶段**：仅读取 `leaderboard/blind/<pack_id>/`，严禁接触模型身份与客观分，严禁使用全屏桌面 Computer Use 随机点击；通过 `judge_submit.py` 将 D1/D2/D3 原子追加至 `leaderboard/reviews.jsonl`；
   - **汇总阶段**：盲评收齐后，先执行 `isolation_audit.py --strict` 与 `timing_audit.py runs --strict`，再执行 `leaderboard/finalize.py`。

---

## 2. 匿名盲评包结构与靶向补测规范

每个匿名包 `leaderboard/blind/<pack_id>/` 包含：
- `README.md`：三步取证盲评指引与隔离红线；
- `RUBRIC.md`：D1（10分）、D2（10分）、D3（10分）详细锚点、视觉审美定档与硬伤重扣铁律；
- `SUBMIT.md`：当前盲评包专属提交命令模板；
- `pack.json`：包清单元数据（`schema_version: 2`）；
- `case-XX/OVERVIEW.md`：脱敏代码文件清单与行数统计；
- `case-XX/STORYBOARD.md` + `case-XX/storyboard/S01..S12.png`：替身体验官自动抓拍的 **12 张《交互状态连环画》**（覆盖首屏质感、列表滚动恢复、SVG 多维对比面板、空搜索恢复、桌面/窄屏表格代码长文、顾问排期冲突告警、去剧透冲突顺延、耦合非破坏带入、异步提交 `503` 恢复与 `INQ-2026-` 回执 + 100ms 复制反馈、深色模式与窄屏悬浮对比条）及纯物理事实批注；
- `case-XX/code/*`：脱敏后的完整离线网页文件与官方原件 `mock_backend.js`。

**靶向补测规约**：
当评委在 `code/` 中发现选手实现了静态 12 张连环画未触发的特色交互设计时，允许调用 `tools/judge_probe.py` 指定 `--case-dir`、`--viewport`、`--click`、`--fill`、`--press`、`--scroll-y`、`--eval` 在断网无头浏览器（已自动等待异步引导完成）中定向验证并输出截图至 `draft/`，并在提交评分前清空 `draft/`。

---

## 3. 防篡改、版本归档与作废判定条件

在 `finalize.py`、`judge_pack.py` 或 `isolation_audit.py --strict` 中，出现以下任一情形将阻断出榜或判该批次无效：
1. `protocol.json` 的 `env_commit` 与当前仓库 `configs/benchmark.json`、`src/sandbox_template/mock_backend.js`、`tools/start_run.py` 及 `src/scoring/*.py` 哈希不一致（比赛期间篡改了评测尺子或混入了旧版本运行目录）；
2. 沙盒或盲评包内的 `mock_backend.js` 缺失或与官方模板归一化 SHA-256 不一致（选手私自篡改了模拟后端数据或延迟/故障规则）；
3. `protocol.json` 的 `code_sha256` 与当前 `runs/<名>/workspace/` 哈希不一致（选手在 `t1` 冻结停表后补改了沙盒代码）；
4. `draft/` 目录残留未清理的草稿文件；
5. 盲评包内缺失 12 张连环画截图，或检出模型名、运行目录名、客观分字段泄露；
6. 同一模型多批次运行出现墙钟时间重叠（`timing_audit.py --strict` 告警 B2 被并发排队污染）。
