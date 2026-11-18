# CHANGELOG · creator-hub-xiaonuo

## [xiaonuo-v4.0] — 2026-11-15

### 两大天花板级进化：官方真实感异步模拟后端 + 彻底剥离交互答案剧透
- **进化一：引入官方只读异步模拟后端 `mock_backend.js`（零规模膨胀，回归真实前端异步工程）**：
  - 官方在沙盒内提供冻结的 `window.LincheMockAPI`（含 `getBootstrap`、`queryCatalog`、`getDetail`、`evaluatePlan`、`submitInquiry`），彻底免去选手编造 400 行静态项目/文章假文案的无意义体力活，并将 `B2` 满分窗适配收紧至 `18` 分钟（半衰期 `24` 分钟）；
  - 接口内置确定性非均匀延迟（`35ms`–`230ms`，精准触发快速检索、快速切篇、快速重置时的**先慢后快乱序覆盖竞态**）、原生 `AbortSignal` 取消支持、14 周忙闲日历排期校验、并发双提拒绝（`429 DUPLICATE_SUBMIT`）以及首次提交必现的 `503 SERVICE_BUSY`（`retryable: true`）瞬时拥塞故障；
  - `start_run.py`、`judge_pack.py`、`isolation_audit.py` 与 `score_run.py` 全链路锁定并校验 `mock_backend.js` 的归一化 SHA-256，严防篡改数据或绕过异步接口。
- **进化二：彻底剥离 `TASK.md` 与 `CONTRACT.md` 中的交互答案剧透（考察产品直觉与工程防御本能）**：
  - `TASK.md` 删光一切“防抖、焦点归位、一键顺延按钮、非破坏合并、重试按钮”等显式交互处方，仅以第一人称自然陈述业务背景与四类真实糟糕体验；
  - `CONTRACT.md` 移除 `est-conflict` 与 `est-resolve-conflict` 等剧透标识，将联系区静态拼接出口升级为真实异步提交入口 `contact-submit` 与回执展示区 `contact-receipt`；
  - `browser_waves.py` 与 `storyboard.py` 升级为基于业务状态不变量与语义可访问性探测：新增搜索/测算/详情三条链路的慢请求乱序防倒灌压测、SVG `<text>` 包围盒零重叠校验、2 周短跨度与 5–6 周长跨度连续空闲排期冲突消解探测、15ms 快速连点防并发锁实测及 `503` 瞬时故障恢复与 `INQ-2026-` 真实回执核验（`A1=2.0, A2=9.5, A3=12.0, A4=6.5`）。
- **双基线重构与历史归档**：重构对接 `LincheMockAPI` 的 `golden_baseline` 与 `naive_baseline`，并将 `xiaonuo-v3.0` 全部运行数据、盲评包与总榜完整归档至 `leaderboard/archive/xiaonuo-v3.0/`。

---

## [xiaonuo-v3.0] — 2026-11-15

### 两大结构性改革：深层耦合业务交互工作台 + 连环组合压测过关制
- **改革一：由“展示型个人主页”全面升级为带深层耦合状态的“真实业务交互工作台”（`TASK.md` + `CONTRACT.md` + 全链路测试同步）**：
  - **动态原生 `<svg>` 多维量化对比图（`compare-chart`）**：对比弹层内除并排表格外，新增零依赖原生 `<svg>` 多维能力叠加图（`≥3` 个坐标轴 `<text>` 标签 + 多序列独立配色多边形），随对比项目从 2 项增至 3 项动态重算顶点坐标重绘；
  - **分阶段里程碑拆解与档期容量冲突自动顺延（`est-start-week` / `est-milestones` / `est-conflict` / `est-resolve-conflict`）**：顾问规划台内置连续忙闲排期日历，实时拆分多阶段交付里程碑并检测周期跨度是否撞上已约满繁忙周，支持点击“顺延至最近空闲档期”一键切至最近无冲突窗口并重算里程碑；
  - **跨模块共享撤销/重做历史栈与输入框焦点防劫持（`workbench-undo` / `workbench-redo`）**：对比篮增删与规划台配置变更共享统一历史栈，支持按钮与 `Ctrl+Z` / `Ctrl+Y` 跨模块回退前进，且在 `INPUT` / `TEXTAREA` 内聚焦打字时绝不误劫持原生撤销；
  - **跨模块全状态耦合带入与刷新守恒**：一键带入留言时自动将“已选对比项目 + 排期与阶段里程碑方案”合并写入结构块且保留访客手写备注，跨刷新保持全工作台状态。
- **改革二：大刀砍掉已饱和保底分权重，改为“连环组合压测过关制”（`configs/benchmark.json` + `metrics.py` + `browser_waves.py`）**：
  - **保底分大幅压缩与重心重配**：`A1` 静态离线与内容保底分由 `5.0` 腰斩至 `2.5`（`A2=9.5`、`A3=11.0`、`A4=7.0`）；`C` 层大幅压缩基础可达/脏缓存保底分，重仓 `C2.3` 模态双向焦点锁（`Tab` + `Shift+Tab` + `Escape`，`5.5` 分）与陡峭 WCAG AA 9 角色木桶对比度 `C3.4`（`4.8` 分，`0.35 * 均值 + 0.65 * 最低角色`）；`B1` 高压注入提升至 `320` 张卡片、空转 `rAF` 罚分提至 `40%`，`B2` 适配工作台体量设为 22 分钟满分窗 / 26 分钟半衰期；
  - **连环组合过关门控（`apply_chain_gates`）**：`A2`、`A3`、`A4` 三条业务长链按关卡顺序执行上游及格门控（`pass_threshold = 0.55`），任一上游关卡未达标时，后续下游关卡得分统一乘连坐系数 `0.20`，彻底杜绝靠孤立局部小点拼凑高分。
- **双基线与历史归档同步**：升级 `golden_baseline` 与 `naive_baseline`（客观分差拉大至 `>50` 分），并将 `xiaonuo-v2.0` 全部运行记录与榜单完整归档至 `leaderboard/archive/xiaonuo-v2.0/`。

---

## [xiaonuo-v2.0] — 2026-11-14

### 全面升级：贴合真实日常前端工程与高区分度评测
- **扩充恰当饱满的真实业务与多状态耦合交互（`TASK.md` + `CONTRACT.md`）**：
  - 内容升级为 4 份跨至少 3 个方向的代表项目 + 4 篇富格式实测长文（全面覆盖列表、引用、代码块与**结构化多列数据对比表 `<table>`**）；
  - 新增列表排序器（`sort-control`）、空格多关键词交集全文检索、**最多 3 项项目横向对比篮**（`compare-toggle` / `compare-bar` / `compare-panel`）以及**顾问合作范围与周期实时估算工作台**（`estimator-section`，支持实时单调重算、一键重置与**非破坏性带入合作留言框**）；
  - `TASK.md` 全面去清单化，移除底层异常类名、正则转义、焦点陷阱及 WCAG 数字提示，考察模型真实的工程防御本能。
- **硬化三波无头浏览器确定性压测引擎（`browser_waves.py` + `dom_probes.py` + `metrics.py`）**：
  - **第一波（A 层 30 分）**：取消历史后退兜底赠分，实测连续多步浏览器历史栈（`筛选 → 文1 → 下一篇文2 → Back → Back → Forward`）、点击目录真实滚动与吸顶栏防遮挡、详情页取消收藏返回列表实时同步空状态、正则元字符与 XSS 注入防护、估算结果非破坏性合并及跨刷新持久化；
  - **第二波（C1 9 分 + C3 8 分）**：新增反 `overflow: hidden` 偷裁控件检测、底部悬浮对比栏激活态防遮挡与按钮包围盒防重叠检测、多态脏 `localStorage`（数字串/非数组对象/破损 JSON）+ `SecurityError` + `QuotaExceededError` + 剪贴板拒绝全链路容错，以及覆盖激活态按钮、徽章、代码块、报错红字等 **9 类角色的 WCAG 2.1 短板木桶对比度模型**（`0.45 * 均值 + 0.55 * 最低角色`）；
  - **第三波（C2 8 分 + B1 5 分 + B2 10 分）**：实测全站 6 大交互区键盘可达性、定制化 `:focus-visible` 焦点环、对比弹层 `Tab` 焦点包含锁与 `Escape` 归位、空闲无限 `requestAnimationFrame` 空转惩罚（`-35%`）以及 240 节点高压 DOM 注入下的搜索 `P95` 延迟；B2 适配 v2.0 工程体量调整为 18 分钟内满分、半衰期 22 分钟。
- **升级 12 张《交互状态连环画》与反端水盲评规约（`storyboard.py` + `judge_pack.py`）**：
  - 扩展抓拍 `S01`–`S12`（新增并排对比面板 `S03`、窄屏数据表格/代码长文 `S06`、估算工作台 `S07`、非破坏性带入与报错拦截 `S08`、手机端悬浮对比条 `S12`），强化视觉审美定档与硬伤直接扣分铁律。
- **重构双基线与历史归档**：
  - 全新编写社论级高质感 `golden_baseline` 与模拟常见弱模型偷懒缺陷的 `naive_baseline`，并将 `xiaonuo-v1.0` 历史评测数据完整归档至 `leaderboard/archive/xiaonuo-v1.0/`。

---

## [xiaonuo-v1.0] — 2026-11-14

### 新增与构建完成
- **同仓两角色闭环架构**：建立清晰的“① 被测试者（选手）”与“② 独立评委（盲评与收官汇总）”双信任域及全套生命周期留档（`protocol.json`、`runs_log.jsonl`、`reviews.jsonl`、`verdicts/*.json`、`scores.md`）。
- **两层痛点式沙盒模板（`src/sandbox_template/`）**：提供离线主页 `TASK.md`、`CONTRACT.md`、`DECISIONS.md` 与 `smoke_public.py`。
- **替身体验官与 10 张《交互状态连环画》打包（`storyboard.py` + `judge_pack.py`）**及评委靶向补测工具 `tools/judge_probe.py`。
- **三波无头浏览器客观评测引擎与双基线冒烟自检（`tests/smoke.ps1`）**。
