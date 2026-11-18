# Creator Hub · xiaonuo（创作者选型与顾问排期工作台 · 真实异步前端工程与交互体验基准）

> **一句话定位**：围绕独立 AI 研究者“林澈”的真实顾问咨询与技术选型场景，官方提供**带真实波动延迟、乱序竞态、参数/档期校验与瞬时繁忙故障的只读本地异步后端（`mock_backend.js`）**，并在任务书中**彻底剥离交互答案剧透**——由**无头浏览器三波连环组合压测物理测量 70 分异步工程与可用性底线**，配合**替身体验官自动抓拍 12 张《交互状态连环画》盲评 30 分视觉美学、产品直觉与架构上限**。

当前赛制版本为 `xiaonuo-v4.0`（历史归档见 [`leaderboard/archive/xiaonuo-v3.0/scores.md`](leaderboard/archive/xiaonuo-v3.0/scores.md)、[`leaderboard/archive/xiaonuo-v2.0/scores.md`](leaderboard/archive/xiaonuo-v2.0/scores.md) 与 [`leaderboard/archive/xiaonuo-v1.0/scores.md`](leaderboard/archive/xiaonuo-v1.0/scores.md)）。进入本仓库请先阅读 [`AGENTS.md`](AGENTS.md) 第 0 节认领身份（被测试者或独立评委）；最新成绩榜单见 [`leaderboard/scores.md`](leaderboard/scores.md)。

---

## 核心设计：真实感异步后端 + 去答案化需求 + 连环组合压测过关制

在传统前端基准中，选手往往耗费大量词元编造静态假文案，而提示词又把交互答案喂得一清二楚，导致顶尖旗舰模型扎堆天花板而无法拉开上限区分度。

`xiaonuo-v4.0` 在不增加题目规模的前提下，从四个维度拉开旗舰模型真实工程上限（详见 [`docs/design.md`](docs/design.md)）：

| 核心机制 | 解决什么问题 |
| --- | --- |
| **1. 官方只读异步模拟后端（`mock_backend.js`）** | 卸掉约 400 行静态假文案编造负担，由 SHA-256 锁定的 `window.LincheMockAPI` 提供 4 项目、4 富长文、14 周忙闲日历、排期测算与咨询提交服务；内置 `35ms`–`230ms` 确定性波动延迟（触发**先慢后快乱序倒灌竞态**）、`AbortSignal` 取消、并发双提拦截（`DUPLICATE_SUBMIT`）及首次提交 `503 SERVICE_BUSY` 瞬时故障。 |
| **2. 彻底去答案化的业务需求（零交互剧透）** | `TASK.md` 只讲述林澈的业务诉求与四类真实糟糕体验，删光一切具体交互处方（不教怎么防竞态、不教怎么顺延撞期、不教怎么保草稿重试）；`CONTRACT.md` 同步移除 `est-conflict` / `est-resolve-conflict` 等剧透钩子，真正考察模型的产品直觉与工程防御本能。 |
| **3. 砍保底 + 异步业务不变量 + 连环过关门控** | `A1` 静态保底压至 `2.0` 分；`A2`（`9.5`）、`A3`（`12.0`）、`A4`（`6.5`）实测慢请求乱序防倒灌、零重叠动态 `<svg>` 多维对比图、2 周与 5–6 周跨度连续空闲排期消解、跨模块 Undo/Redo 焦点隔离、15ms 连点防重提与 `503` 故障保底恢复，上游 `< 55%` 则下游统一乘 `×0.20` 连坐。 |
| **4. 严苛几何/无障碍探针 + 12 图连环画反端水盲评** | 客观层重仓模态弹层双向焦点锁（`5.5` 分）、陡峭 WCAG AA 9 角色木桶对比度（`4.8` 分）、反 `overflow:hidden` 偷裁与 320 卡片高压检索；盲评层基于 `S01`–`S12` 实拍截图与脱敏源码按硬伤直接降档规则打分。 |

---

## 四维计分结构（满分 100 分）

总分 = **A 异步状态韧性与耦合工作台（30） + B 高压性能与开发效率（15） + C 严苛物理可用性底线（25） + D 视觉美学、交互直觉与工程架构（30）**。详细公式见 [`docs/scoring.md`](docs/scoring.md)。

| 维度 | 满分 | 评判主体与核心子项 |
| --- | --- | --- |
| **A 异步韧性与耦合工作台** | **30** | **无头浏览器第一波剧本 + 连环过关门控自动算分**：<br>• `A1` 零外网离线连通、`mock_backend.js` SHA-256 完整性、异步接口真实调用与四项目/四富长文渲染（2.0）<br>• `A2 连环链` 异步多词交集检索与慢快请求乱序防倒灌 → 筛选/排序/详情取消收藏同步 → 双项对比与零重叠原生 `<svg>` 多维图 → 增至 3 项动态重绘与上限拦截（9.5）<br>• `A3 连环链` 异步测算单调重算与快速重置防旧报价倒灌 → 去剧透忙闲冲突识别与短/长跨度（含 6 周方案）排期消解 → 跨模块 Undo/Redo 栈及输入框防劫持 → 耦合非破坏带入、15ms 防并发连点锁与 `503` 瞬时故障恢复生成真实回执（12.0）<br>• `A4 连环链` 双异步深链接刷新与新窗口直达 → 快速切篇防旧详情倒灌与五步连续历史栈 → 长文目录真实滚动防遮挡定位（6.5） |
| **B 高压性能与开发效率** | **15** | **脚本自动算分（以 A 层得分率作为上限乘数封顶）**：<br>• `B1` 离线首屏耗时、320 卡片高压注入搜索 `P95`、长文滚动帧间隔与空闲无限 `rAF` 惩罚 `-40%`（5）<br>• `B2` 开局 `t0` 至打包冻结 `t1` 端到端真实墙钟耗时（免去编造文案负担后：18 分钟内满分，此后每 24 分钟减半）（10） |
| **C 严苛物理可用性底线** | **25** | **无头浏览器第二、三波剧本物理测量算分**：<br>• `C1` 四档视口（首页/表格长文/SVG 对比面板）反 `overflow:hidden` 截断、320px 超长串抗撑破、动态对比条防遮挡与热区留白（9）<br>• `C2` 六区键盘可达、定制 `:focus-visible` 焦点环、**对比弹层双向焦点锁（`Tab`+`Shift+Tab`）与 `Escape` 归位**（8）<br>• `C3` 多态脏 JSON/`SecurityError`/`QuotaExceededError`/剪贴板降级与**深浅 9 角色陡峭 WCAG AA 木桶对比度**（8） |
| **D 视觉美学与工程思想** | **30** | **独立评委审阅《12 张连环画 + 脱敏源码》盲评（追加写入中心日志）**：<br>• `D1` 视觉排版质感、零重叠 SVG 图表层次与长文阅读心流（11）<br>• `D2` 异步过渡体验、自发排期冲突消解、跨模块撤销重做与 `503` 容错体贴度（10）<br>• `D3` 异步竞态控制架构、模块解耦可维护性与 `DECISIONS.md` 五条声明逐行核验（9） |

---

## 标准同仓闭环流程

```sh
# 阶段一：被测试者（选手）开局、对接只读 mock_backend.js 开发、冒烟自检与匿名连环画打包
python tools/start_run.py --model Demo
# -> 在 runs/Demo/workspace/ 内阅读 TASK.md 与 CONTRACT.md 完成前端开发（严禁修改 mock_backend.js）并填写 DECISIONS.md
python runs/Demo/workspace/smoke_public.py
python src/scoring/judge_pack.py --model Demo
# -> 校验 mock_backend.js 原件哈希，冻结 t1 与代码 SHA-256 承诺，自动抓拍 12 张连环画（S01..S12）生成 leaderboard/blind/<pack_id>/

# 阶段二：独立评委盲评（只读 leaderboard/blind/<pack_id>/，按三步取证法与反端水铁律追加评分）
python src/scoring/judge_submit.py \
  --pack-dir leaderboard/blind/<pack_id> --case-id case-01 \
  --judge-id judge-01 --judge-model claude-opus-4 \
  --D1 10.2 --D2 9.5 --D3 8.5 \
  --evidence "[S03][S07][S08][S10] SVG零重叠+14周连续空闲顺延+耦合带入+503退避回执生成 + [code/app.js] C1-C5全核实" \
  --note "最强反证：移动端长文目录置于正文上方未支持一键折叠收起"

# 阶段三：盲评全部收齐后，执行隔离/时间审计并一键拉起三波浏览器剧本定稿出榜
python tools/isolation_audit.py --strict
python tools/timing_audit.py runs --strict
python leaderboard/finalize.py
```

---

## 仓库目录结构

```text
AGENTS.md                两角色（被测试者 / 独立评委）一进门即懂的操作规范与隔离红线
configs/benchmark.json   全局唯一配置源（连环门控阈值、A/B/C/D 权重、陡峭对比度与反截断节点、B2 时间常数）
src/sandbox_template/    选手开局释放的沙盒模板（含官方只读 mock_backend.js、TASK.md、CONTRACT.md、DECISIONS.md、index.html、smoke_public.py）
src/baselines/           双基线自检内置样本（naive_baseline 简陋异步弱实现 / golden_baseline 社论级防竞态黄金工作台基线，选手禁读）
src/scoring/             三波连环压测引擎（browser_waves.py + dom_probes.py）、12 图连环画（storyboard.py）、插值门控与汇总出榜
tools/                   开局工具（start_run.py）、评委靶向补测（judge_probe.py）、隔离审计（isolation_audit.py）与时间审计（timing_audit.py）
tests/                   计分/连环门控/木桶对比度/审计单元测试与端到端双基线全链路冒烟自检（smoke.ps1）
docs/                    赛制协议（protocol.md）、计分细则（scoring.md）与设计说明（design.md）
runs/                    当前赛季各模型运行沙盒、计时协议、词元自报及出榜物理测量报告留档
leaderboard/             总榜（scores.md）、历史归档（archive/）、裁决档案（verdicts/）、评审日志与匿名盲评目录
```
