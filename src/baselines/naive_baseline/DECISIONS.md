# 交互设计与工程架构说明（DECISIONS.md · 简陋基线）

## 1. 整体架构与模块划分
- `index.html`：单页基础 HTML 结构与内联简单样式；
- `mock_backend.js`：官方只读本地异步后端服务；
- `app.js`：直接调用 `LincheMockAPI` 渲染列表、详情、规划台与联系表单的基础脚本。

## 2. 异步时序、异常恢复与状态一致性方案
- **快慢异步请求防竞态机制**：当前仅使用基础 `.then()` 回调直接更新 DOM，未实现 `AbortController` 取消或请求序号比对；
- **提交防并发重入与瞬时繁忙（`503 SERVICE_BUSY`）恢复**：点击提交按钮直接调用 `submitInquiry`，捕获异常后将错误文本展示在 `#cErr`；
- **跨模块状态联动、历史回退（Undo/Redo）与本地存储降级容错**：顶栏放置了撤销/重做占位按钮但未绑定历史栈，本地存储直接调用 `localStorage` 与 `JSON.parse`。

## 3. 业务痛点回应与自发交互细节
1. **选型对比与详情返回**：勾选对比后点击底部栏展开基础文字列表与静态示意 SVG，返回列表时重置滚动到顶部；
2. **检索无结果引导**：当项目与文章均无匹配时显示基础无结果文字提示；
3. **长文代码表格排版与目录导航**：详情页加载文章 HTML 并提取 `toc` 生成顶部锚点链接；
4. **排期规划冲突处理、方案带入与回执复制**：直接输出 `evaluatePlan` 返回的周期预算与冲突提示文本，点击带入时写入留言框，复制调用 `navigator.clipboard.writeText`。

## 4. 可直接定位核验的 5 条源码实现声明（C1–C5）
- **C1**：首屏启动调用 `LincheMockAPI.getBootstrap()` 渲染简介、分类按钮与规划选项，位于 `app.js` 第 `221–302` 行的启动回调中。
- **C2**：搜索与分类切换调用 `LincheMockAPI.queryCatalog()` 更新项目与文章卡片列表，位于 `app.js` 第 `46–104` 行的 `reloadCatalog` 函数。
- **C3**：规划台变更调用 `LincheMockAPI.evaluatePlan()` 更新周期、预算与里程碑文本，位于 `app.js` 第 `107–116` 行的 `refreshEstimate` 函数。
- **C4**：打开项目或文章详情调用 `LincheMockAPI.getDetail()` 渲染正文与章节链接，位于 `app.js` 第 `118–152` 行的 `openProject` 与 `openArticle` 函数。
- **C5**：联系表单提交调用 `LincheMockAPI.submitInquiry()` 并将返回摘要写入 `contact-receipt`，位于 `app.js` 第 `202–214` 行的 `#cSub.onclick` 处理函数。
