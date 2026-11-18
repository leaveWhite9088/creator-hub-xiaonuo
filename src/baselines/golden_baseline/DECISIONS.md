# 交互设计与工程维护说明（DECISIONS.md）

## 1. 架构分层与异步状态流说明

- **本地打开与联调方式**：直接通过浏览器 `file://` 协议离线打开 `index.html`，无需构建工具或外网连接；页面优先加载官方只读模拟后端 `mock_backend.js`（`window.LincheMockAPI`），在 `app.js` 的 `bootstrap()`（L2074-L2113）中异步拉取首屏名片与排期字典，随后并发执行初始目录检索与默认方案测算。
- **前端文件与模块职责划分**：
  - `mock_backend.js`（官方只读接口）：提供个人资料、代表项目、技术长文、14 周忙闲日历、排期报价评估与合作咨询回执生成的本地异步 Promise 服务。
  - `styles.css`：集中管理浅色暖纸张与深色高对比两套 CSS 语义令牌（`:root` 与 `html[data-theme="dark"]`）、流式排版节奏、吸顶栏与底部对比悬浮条高度预算，以及 `.table-scroll-wrap` / 代码块局部横向滚动约束。
  - `index.html`：提供语义化地标骨架、跳转主内容链接、`aria-live` 状态播报区及去剧透语义容器（如 `role="alert"` 冲突提示横幅与瞬时繁忙重试横幅）。
  - `app.js`：统一承载安全持久化容错层、三条独立异步读取链路的 `AbortController` + 单调序号并发门禁、跨模块操作历史栈（Undo/Redo）、原生 `<svg>` 零重叠多维雷达图、14 周连续空闲排期求解器以及表单防连点与 `503` 自动退避恢复状态机。

## 2. 日常扩展与定制维护指南

- **调整浅色/深色主题配色、字号层级与版式间距变量**：仅需修改 `styles.css` 顶部的 `:root`（浅色令牌）与 `html[data-theme="dark"]`（深色令牌），所有卡片、徽章、告警条与激活按钮均引用该组变量；雷达图深浅色序列色板集中在 `app.js` 顶部的 `UI_CONFIG.radarColorsLight` / `radarColorsDark`（L12-L21）。
- **扩展横向对比视图的字段行或调整 `<svg>` 多维图视觉样式**：并排对比表格的维度定义集中在 `app.js` 的 `renderCompareTable()`（L871-L889 `rows` 数组）；多维雷达图的极坐标半径、网格环与轴文字外扩锚点（`start`/`middle`/`end` 防重叠）集中在 `renderCompareRadarChart()`（L784-L856）。
- **调整排期冲突处理策略或工作台方案带入格式**：连续空闲周搜索算法位于 `app.js` 的 `findNextConflictFreeStartWeek()`（L1082-L1100）；结构化标记块替换与字数上限保护位于 `mergeStructuredBlockIntoMessage()` 与 `applyEstimatorToContact()`（L1114-L1155）。
- **调整异步加载过渡态、异常重试策略或本地持久化键名**：存储键名统一定义在 `app.js` 的 `STORAGE_KEYS`（L24-L31）；搜索防抖阈值定义在 `UI_CONFIG.searchDebounceMs`（L10）；咨询提交并发锁与 `503 SERVICE_BUSY` 退避重试逻辑位于 `handleSubmitInquiry()`（L1608-L1698）。

## 3. 视觉设计与四类糟糕体验的应对方案

1. **整体视觉气质与多端可读性设计**：采用浅色暖白社论风与深色高对比暗夜双主题，全部前景/背景角色均满足严格对比度余量；移动端顶部导航栏与底部悬浮对比条采用紧凑单行折行约束，占屏远低于视口 30%；长文详情页在 `renderArticleDetailPayload()`（L1286-L1294）自动为正文 `<table>` 包裹 `.table-scroll-wrap`，配合代码块局部横向滚动，确保 `320px` 极窄屏下零页面级横向溢出。
2. **针对“手快连切时页面抽风或张冠李戴”**：搜索输入框接入 `compositionstart` / `compositionend` 中文拼字保护（L1748-L1769）；目录检索、排期评估与详情读取分别配备独立的 `AbortController` 与单调递增请求令牌（`catalogReqSeq` / `planReqSeq` / `detailReqSeq`），切换或重置时立即中止在途旧请求并校验序号，彻底杜绝高延迟旧响应晚到覆盖当前新状态；异步等待期间标记 `aria-busy="true"` 平滑保留上下文。
3. **针对“来回翻找丢位置、空手而归没出路”**：进入项目或文章详情前记录主页 `savedListScrollY` 与触发按钮引用，通过返回按钮、键盘 `Escape` 或浏览器前进/后退回到列表时双帧恢复原滚动高度与焦点；对比弹层内置随 2～3 项动态重绘的原生 `<svg>` 多维能力雷达图；无匹配结果时隐藏空表头并提供一键清空搜索词、退出收藏过滤及推荐工程词直达按钮（L637-L668）。
4. **针对“反复试算与填表提交太脆弱”**：规划台检测到繁忙周冲突时以 `role="alert"` 明确说明冲突原因，并提供按当前方案完整周跨度 `totalWeeks` 计算连续空闲窗口的“一键顺延至最近连续空闲周”动作；内置覆盖对比篮与规划台全参数的 30 步快照撤销/重做栈，且在焦点处于输入框时自动放行原生文本 `Ctrl+Z`；点击带入方案时仅更新起止标记块而完整保留访客手写备注；点击提交时立即启用 `submitInFlight` 并发锁拦截快速连点，遇到网关瞬时 `503 SERVICE_BUSY` 自动保留全部表单输入并在 65ms 退避后完成静默重试（同时保留手动立即重试按钮兜底）。

## 4. 五条可在前端源码中直接核验的核心声明（C1–C5）

- **声明 C1**：`app.js` 在 L181-L188 为目录检索、排期测算、详情加载分别维护独立的 `AbortController` 与单调递增序号（`catalogReqSeq`、`planReqSeq`、`detailReqSeq`），并在 `runCatalogQuery`（L475-L545）、`runPlanEvaluation`（L1053-L1080）与 `syncRouteFromHash`（L1385-L1431）中通过 `mySeq !== *ReqSeq` 阻断慢响应倒灌。
- **声明 C2**：`app.js` 在 L1082-L1112 实现 `findNextConflictFreeStartWeek` 与 `resolveScheduleConflict`，依据当前方案总周数 `totalWeeks` 在完整的 14 周 `calendarWeeks` 序列上校验连续 `span` 周全部 `!slot.busy`，同时支持 2 周短方案与 5～6 周高负载方案的一键无冲突顺延。
- **声明 C3**：`app.js` 在 L266-L320 实现覆盖 `compareIds` 与 `estimator` 的跨模块历史栈（`pushHistoryBeforeMutation` / `performUndo` / `performRedo`），并在 L2046-L2067 的键盘监听中检测 `INPUT`/`TEXTAREA`/`SELECT`/`isContentEditable` 焦点状态以防劫持表单打字撤销。
- **声明 C4**：`app.js` 在 L1114-L1155 通过 `WORKBENCH_BLOCK_REGEX` 实现对比项目与排期里程碑的非破坏合并带入；在 L1608-L1698 的 `handleSubmitInquiry` 中通过 `submitInFlight` 阻断并发双提交，并对 `503 SERVICE_BUSY` 实施保留草稿的 65ms 自动退避重试与手动重试横幅双保险。
- **声明 C5**：`app.js` 在 L47-L96 封装带内存回退与降级提示条的 `safeGetRaw`/`safeSetRaw` 及脏缓存清洗；在 L1355-L1362 与 L2005-L2038 实现主页滚动与焦点精准归位，以及对比模态框的 `Tab`/`Shift+Tab` 双向焦点环闭。
