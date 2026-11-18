# 离线运行、模拟后端接口与结构锚点契约（CONTRACT.md）

为保证前端作品在拥有完整视觉、状态架构与交互设计自由度的同时，能与本地模拟后端及自动化验收工具顺畅对接，请严格遵守以下契约。

---

## 1. 本地离线运行与只读后端规范

1. **唯一入口文件**：工作目录根路径下的 `index.html`（即 `workspace/index.html`），可自行拆分同目录或子目录的本地 `.css`、`.js`、`.svg` 等静态资源。
2. **零外网依赖**：运行环境通过 `file://` 协议直接打开 `index.html`，并**拦截一切 `http://`、`https://`、`ws://`、`wss://` 请求**。严禁引用在线字体、CDN 脚本/样式库或外链媒体。
3. **经典脚本加载与只读后端保护**：
   - 在 `file://` 协议下，`<script type="module">` 与本地 `fetch('./xxx.json')` 会受跨源策略限制报错；请使用标准经典脚本加载：
     ```html
     <script src="mock_backend.js"></script>
     <script src="app.js"></script>
     ```
   - 同目录的 **`mock_backend.js` 为官方受保护只读文件（纳入 SHA-256 完整性审计），严禁修改、删除或覆盖**，也严禁在前端代码中静态复制后端数据集绕过接口调用。
4. **移除未实现占位属性**：开发完成后，**必须移除**初始 `<html>` 标签上的 `data-unimplemented="true"` 属性。

---

## 2. 本地模拟后端接口文档（`window.LincheMockAPI`）

加载 `mock_backend.js` 后，全局只读对象 `window.LincheMockAPI` 提供以下返回 `Promise` 的异步方法。所有方法均模拟真实线上延迟波动（约 `35ms～240ms` 不等），且第二个可选参数 `options` 均支持传入标准 `{ signal: AbortSignal }`：

### 2.1 `LincheMockAPI.getBootstrap(options?)`
获取首屏初始化配置与排期字典：
- **返回结构**：
  - `profile`：`{ name, studio, location, title, tagline, bio, metrics: [{ label, value }], demoNotice, contactEmail, contactEmailNote }`
  - `categories`：`[{ id: 'all' | 'eval' | 'agent' | 'tool', label }]`
  - `sortOptions`：`[{ id: 'featured' | 'latest' | 'depth', label }]`
  - `defaultPlan`：`{ modeId, addonIds, scaleId, startWeek }`
  - `plannerCatalog`：
    - `modes`：`[{ id, label, baseWeeks, baseMinK, baseMaxK, description }]`
    - `addons`：`[{ id, label, addWeeks, addMinK, addMaxK }]`
    - `scales`：`[{ id, label, weekDelta, priceMultiplier }]`
    - `calendarWeeks`：长度 14 的连续周次数组 `[{ week, index, label, selectableAsStart, busy, busyReason }]`（其中 `selectableAsStart: true` 的前 8 周可作为期望启动周，完整 14 周用于跨周排期忙闲核对）

### 2.2 `LincheMockAPI.queryCatalog(params?, options?)`
跨项目与长文全文检索、分类筛选与排序：
- **入参 `params`**：`{ query?: string, category?: string, sortBy?: string, favoritesOnly?: boolean, favoriteIds?: string[] }`
- **返回结构**：`{ requestSeq, query, category, sortBy, projects: ProjectSummary[], articles: ArticleSummary[] }`
  - `ProjectSummary`：`{ id, title, category, categoryLabel, date, depthScore, durationHint, summary, scenario, deliverables: string[], tags: string[], radarAxes: string[], metrics: Record<string, number>, metricList: [{ axis, score }] }`
  - `ArticleSummary`：`{ id, title, date, readingMinutes, category, tags: string[], summary, tocCount }`

### 2.3 `LincheMockAPI.getDetail(params, options?)`
获取单份项目完整方案或单篇长文全文：
- **入参 `params`**：`{ type: 'project' | 'article', id: string }`
- **返回结构**：
  - 当 `type === 'project'`：`{ type: 'project', item: ProjectSummary & { detailParagraphs: string[], architectureNotes: string } }`
  - 当 `type === 'article'`：`{ type: 'article', item: { id, title, date, readingMinutes, category, tags, summary, toc: [{ id, title, level }], bodyHtml: string, prevArticle: { id, title }, nextArticle: { id, title } } }`
- **异常**：找不到对应条目时 reject `{ code: 'NOT_FOUND', message, retryable: false }`。

### 2.4 `LincheMockAPI.evaluatePlan(params, options?)`
异步测算合作周期、参考预算区间、分阶段排期与忙闲冲突：
- **入参 `params`**：`{ modeId: string, addonIds: string[], scaleId: string, startWeek: string }`
- **返回结构**：
  - `{ modeId, modeLabel, addonIds, addonLabels, scaleId, scaleLabel, startWeek, startWeekLabel, endWeekLabel, totalWeeks, budgetMinK, budgetMaxK, milestones: [{ phase, title, weeks, weekRangeLabel, deliverable }], conflict: { hasConflict: boolean, busyWeeks: [{ week, label, reason }], message: string } }`

### 2.5 `LincheMockAPI.submitInquiry(payload, options?)`
异步提交合作咨询单并生成回执：
- **入参 `payload`**：
  - `{ name: string, email: string, message: string, comparedProjectIds?: string[], planSnapshot?: { modeId, addonIds, scaleId, startWeek } }`
- **成功返回**：`{ ok: true, inquiryId: string, receivedAt: string, recipientEmail: string, formattedSummary: string }`
- **可能抛出的异步错误（`Promise` reject 错误对象含 `code`、`message`、`retryable` 字段）**：
  - `VALIDATION_ERROR`（`retryable: false`）：姓名、邮箱格式或留言长度（10～500 字）不合规（附带 `field` 字段）；
  - `SCHEDULE_CONFLICT`（`retryable: false`）：附带的 `planSnapshot` 存在未消解的忙碌周冲突；
  - `DUPLICATE_SUBMIT`（`retryable: false`）：存在未完成的在途提交请求时发生并发重复提交；
  - `SERVICE_BUSY`（`retryable: true, status: 503`）：模拟网关偶发瞬时繁忙，稍后重试即可恢复。

---

## 3. 页面结构定位锚点（`data-testid`）

自动化工具通过以下基础结构锚点定位区域（不限制内部 DOM 层级、交互形态与样式类名）：

### 3.1 全局与首屏
| `data-testid` | 结构定位说明 |
| --- | --- |
| `hero-section` | 首屏个人介绍主容器 |
| `theme-toggle` | 主题切换按钮（在 `<html>` 上同步 `data-theme="light"` 或 `"dark"`） |
| `demo-notice` | 演示内容说明元素 |
| `workbench-undo` | 工作台撤销按钮 |
| `workbench-redo` | 工作台重做按钮 |

### 3.2 搜索、筛选与排序
| `data-testid` | 结构定位说明 |
| --- | --- |
| `search-input` | 搜索输入框（`<input>`） |
| `category-filter` | 分类筛选容器 |
| `category-option` | 分类选项（带 `data-category` 属性；当前选中项标 `aria-pressed="true"` 或 `data-active="true"`） |
| `favorite-filter` | 只看已收藏开关（开启时标 `aria-pressed="true"` 或 `data-active="true"`） |
| `sort-control` | 排序控件（`<select>` 或含 `[data-sort]` 按钮的容器） |
| `empty-state` | 无匹配结果时的空状态容器 |

### 3.3 项目列表与对比视图
| `data-testid` | 结构定位说明 |
| --- | --- |
| `project-list` | 项目列表容器 |
| `project-card` | 单张项目卡片（带项目 `data-id` 属性） |
| `project-open` | 卡片内打开项目详情的触发元素 |
| `favorite-btn` | 收藏切换按钮（已收藏时标 `aria-pressed="true"` 或 `data-favorited="true"`） |
| `compare-toggle` | 卡片内对比切换按钮（已加入对比时标 `aria-pressed="true"` 或 `data-compared="true"`） |
| `compare-bar` | 已选对比状态栏容器 |
| `compare-open` | 打开对比面板的按钮 |
| `compare-clear` | 清空对比项的按钮 |
| `compare-panel` | 横向对比面板容器 |
| `compare-chart` | 对比面板内的原生 `<svg>` 多维对比图元素 |
| `compare-close` | 关闭对比面板的按钮 |

### 3.4 长文列表与详情阅读
| `data-testid` | 结构定位说明 |
| --- | --- |
| `article-list` | 长文列表容器 |
| `article-card` | 单篇长文卡片（带文章 `data-id` 属性） |
| `article-open` | 卡片内打开长文的触发元素 |
| `detail-view` | 详情视图主容器 |
| `detail-title` | 详情标题元素 |
| `detail-body` | 详情正文容器 |
| `detail-back` | 返回列表按钮 |
| `article-toc` | 长文目录容器 |
| `article-prev` | 上一篇按钮 |
| `article-next` | 下一篇按钮 |

### 3.5 排期与预算测算区
| `data-testid` | 结构定位说明 |
| --- | --- |
| `estimator-section` | 排期与预算测算主容器 |
| `est-type` | 合作模式选项（选中项标 `aria-pressed="true"` / `aria-checked="true"` / `data-active="true"` 或原生 radio） |
| `est-addon` | 附加交付模块选项（选中项标 `aria-pressed="true"` / `data-active="true"` 或原生 checkbox） |
| `est-scale` | 业务规模控件（`<select>`、`<input>` 或含档位按钮的容器） |
| `est-start-week` | 期望启动周选择控件（`<select>` 或含 `[data-week]` 选项按钮的容器） |
| `est-result` | 周期与预算结果汇总容器 |
| `est-milestones` | 分阶段里程碑排期列表容器 |
| `est-reset` | 重置测算配置按钮 |
| `est-apply-to-contact` | 将工作台方案带入合作咨询表单的按钮 |

### 3.6 合作咨询提交区
| `data-testid` | 结构定位说明 |
| --- | --- |
| `contact-section` | 合作咨询区主容器 |
| `contact-name` | 姓名输入框（`<input>`） |
| `contact-email` | 回复邮箱输入框（`<input>`） |
| `contact-message` | 合作留言输入框（`<textarea>`） |
| `contact-error` | 错误提示元素 |
| `contact-submit` | 提交合作咨询单按钮 |
| `contact-receipt` | 提交成功后的回执单号与咨询摘要展示容器 |
| `contact-copy` | 复制回执摘要按钮 |

---

## 4. 公开连通性冒烟自检

交付前可在仓库根目录执行冒烟脚本，快速检查离线加载、`mock_backend.js` 完整性及基础结构锚点是否连通：

```sh
python runs/<你的模型名>/workspace/smoke_public.py
```

> 注：`smoke_public.py` 仅检查最基础的页面打开与静态锚点存在性，不涵盖异步竞态压测、长短排期冲突消解、撤销历史边界、并发提交与瞬时故障恢复、多视口几何防遮挡及可读性对比度，请务必自行全面检验。
