# AGENTS.md — 角色分流、操作规范与留档手册

> 给进入本仓库的 **AI 智能体与人类操作者**的第一入口说明。
> 本基准只有**两个角色（两个严格隔离的信任域）**：**① 被测试者（选手）** 与 **② 独立评委（盲评与收官出榜）**。
> **进门第一件事：在下方第 0 节认领你当前的唯一身份，然后只阅读属于你的章节并按命令执行，严禁越界翻阅！**

---

## 0. 一眼认领身份：你是谁？现在该干什么？

本基准在同一仓库内通过**物理目录边界 + 哈希承诺（`env_commit` / `code_sha256`）+ 生命周期台账 + 事后隔离审计**保障评测公正。同一智能体绝不能在同一批次中既当选手又给自己当评委。

| 你的角色 | 怎么判断是你 | 进来后唯一允许阅读的内容 | 标准动作（一步不漏） | 绝对禁止触碰的红线 |
| --- | --- | --- | --- | --- |
| **① 被测试者（选手域）** | 用户让你“完成这个前端基准 / 作为某模型参赛”，并指定了模型标识 | **只读本文 `§0–§1`**；开局后全程只读 `runs/<模型名>/workspace/` 内的文件 | 1. 跑 `tools/start_run.py` 开局建沙盒打 `t0`<br>2. 在沙盒内对接官方只读 `mock_backend.js` 开发离线网页、跑通 `smoke_public.py`、如实填写 `token_usage.json`<br>3. 清空 `draft/` 后跑 `src/scoring/judge_pack.py` 冻结 `t1` 并自动抓拍连环画生成匿名包，只把 `leaderboard/blind/<pack_id>` 路径交给用户/评委 | 严禁读本文 `§2–§3`、严禁读 `README.md` / `构建与设计说明.md` / `docs/` / `configs/` / `src/` / `leaderboard/` / 他人 `runs/*`；严禁改动或替换 `mock_backend.js`；严禁运行 `score_run.py` 或 `finalize.py`；冻结 `t1` 后严禁再改沙盒代码 |
| **② 独立评委（盲评与收官汇总）** | 用户把 `leaderboard/blind/<pack_id>` 交给你做盲评，或在盲评收齐后让你汇总出榜 | **只读本文 `§0` 与 `§2`**；盲评期间只允许访问交接给你的 `leaderboard/blind/<pack_id>/` | 1. **盲评阶段**：看 `RUBRIC.md`、`STORYBOARD.md`（及 12 张截图 `S01..S12`）与 `code/`（按需用 `tools/judge_probe.py` 靶向补测），运行 `judge_submit.py` 追加 D1/D2/D3（各 10 分）<br>2. **出榜阶段**（盲评全收齐后）：跑 `isolation_audit.py` 与 `timing_audit.py`，再跑 `leaderboard/finalize.py` 现场拉起无头浏览器定稿客观分并合成总榜 | **盲评期间**严禁开启全屏桌面视觉操控（Computer Use）乱点、严禁访问 `runs/`、`blind-maps/`、`reviews.jsonl`、`scores.md`、`verdicts/` 或打探客观分；全程不得替选手修改沙盒代码 |

### 通用目录卫生与留档纪律（两角色共同遵守）
- 除下文规定的正式留档路径外，不得在仓库根目录或其他目录随意新建、改动文件。
- 确需存放临时演算稿或评委靶向补测截图时，**只允许写入 `draft/` 目录，且收尾前必须彻底删除清空**（`isolation_audit.py --strict` 会拦截任何非空 `draft/`）。

---

## 1. 被测试者（选手域）：三分钟上手与规范交接

> **选手请止步于本节末尾**：读完 `§1` 后请立即执行第 1 步命令进入专属沙盒，不要继续往下滚动阅读！

### 第一步：一键开局（记录起点时钟 `t0` + 创建专属沙盒）

在仓库根目录执行（将 `<你的模型名>` 替换为指定的模型名称，例如 `deepseek-v4.1-flash`）：

```sh
python tools/start_run.py --model <你的模型名>
```

该命令会自动完成留档初始化：
- 创建你的专属工作目录 `runs/<你的模型名>/workspace/`；
- 在 `runs/<你的模型名>/protocol.json` 中记录起点时间 `t0` 与评测脚本防篡改承诺 `env_commit`；
- 向运行台账 `leaderboard/runs_log.jsonl` 写入开局记录。

### 第二步：在专属沙盒内独立开发、自查与撰写说明

进入 `runs/<你的模型名>/workspace/`，只围绕里面的模板文件开展工作：
1. 仔细阅读 **`TASK.md`**（林澈口述的主页业务诉求与日常真实遭遇的糟糕体验）；
2. 仔细阅读 **`CONTRACT.md`**（双击 `index.html` 本地 `file://` 零外网离线打开规矩、官方只读模拟后端 `mock_backend.js` 的接口契约，以及最基础主干入口的 `data-testid` 约定）；
3. 在 `workspace/` 下完成 `index.html`（及你自行拆分的本地 `.css` / `.js` 等文件）开发，记得移除初始模板 `<html>` 上的 `data-unimplemented="true"` 占位属性，且**绝不可修改或替换官方只读文件 `mock_backend.js`**（收尾与出榜均会校验其 SHA-256）；
4. 运行沙盒自带的公开连通性冒烟检查，确认断网 `file://` 可正常打开、已连通本地模拟接口且基础契约标识无遗漏：
   ```sh
   python runs/<你的模型名>/workspace/smoke_public.py
   ```
   *(注：`smoke_public.py` 只验基础入口连通性，请务必自行全面检查多宽度排版、深浅色对比度、异步交互过渡与异常容错、纯键盘焦点归位及业务场景完整闭环。)*

### 第三步：自报词元消耗、冻结计时并生成匿名盲评包

1. 打开 `runs/<你的模型名>/token_usage.json`，如实填入本轮开发的累计词元用量（仅用于成本诊断留档，不参与计分；若宿主无法获取请保留 `null` 并在 `note` 说明）：
   ```json
   {
     "input_tokens": 0,
     "output_tokens": 0,
     "total_tokens": 0,
     "source": "self_report",
     "note": "宿主统计口径说明"
   }
   ```
2. 确认临时目录 `draft/` 已清空后，在仓库根目录执行官方收尾打包脚本：
   ```sh
   python src/scoring/judge_pack.py --model <你的模型名>
   ```
   - 脚本会自动打下结束时间戳 `t1`、锁定沙盒代码的 `code_sha256` 承诺（**此后严禁再改动沙盒内任何文件，否则出榜核验将判成绩作废！**）；
   - 自动启动无头浏览器“替身体验官”走完选型对比、预算估算联动与四大痛点场景，抓拍 **12 张《交互状态连环画》**（`S01`–`S12`），连同彻底脱敏后的前端源码打包至 `leaderboard/blind/<pack_id>/`。
3. **只将终端打印出的 `leaderboard/blind/<pack_id>` 目录路径汇报给用户/评委即可收工**。严禁交付 `blind-map.json` 或 `runs/` 路径，严禁运行 `score_run.py` 或 `finalize.py`！

*(如果你是被测试者选手，阅读到此结束，禁止继续向下阅读！)*

---

## 2. 独立评委（盲评与收官汇总）：三步取证盲评 + 一键压测出榜

> 本节供承担 **D 层盲评（满分 30 分 = D1 10 分 + D2 10 分 + D3 10 分）**及**盲评后收官出榜**的评委智能体或维护者阅读。
> 全流程严格遵守先后顺序：**先盲评提交落盘，最后统一跑浏览器压测定稿出榜**。

### 阶段一：独立盲评提交（零客观分干扰、零选手自述包装、零全屏乱点）

- **唯一合法输入**：用户交给你的匿名盲评包目录 `leaderboard/blind/<pack_id>/`。
- **绝对禁止**：
  1. 严禁开启全屏桌面视觉操控（Computer Use）去随机自由点击（既慢又会因点击偏差造成不公）；
  2. 盲评期间严禁访问 `runs/`、`leaderboard/blind-maps/`、`leaderboard/reviews.jsonl`、`leaderboard/scores.md`、`leaderboard/verdicts/`，严禁运行 `score_run.py` 或 `finalize.py`。

**标准三步取证法（100% 凭真实渲染截图与源码本身定级）**：
1. **看连环画与物理事实批注**：阅读 `<pack_dir>/README.md` 与 `<pack_dir>/RUBRIC.md`；打开 `<pack_dir>/case-01/STORYBOARD.md` 并**逐张查看 `<pack_dir>/case-01/storyboard/S01..S12.png` 真实画面**（核查首屏社论级排版留白、对比弹层内零依赖 `<svg>` 多维对比图真实渲染与并排表格清晰度、空搜索恢复按钮与建议词、长文 50% 处数据表格/代码块在桌面与手机端的自适应及目录高亮、顾问规划台阶段里程碑与繁忙档期冲突提示、自发设计的冲突顺延动作并合并对比项目非破坏带入留言框、字段改对即时消错、异步提交防连点与 `503` 瞬时繁忙恢复后的 `INQ-2026-` 回执生成、点击复制后 100ms 瞬时反馈、深色层次及手机端吸顶栏 + 悬浮对比条防遮挡）。
2. **查脱敏源码简洁度与高内聚架构质量**：阅读 `<pack_dir>/case-01/OVERVIEW.md` 与 `code/` 下全部代码：
   - 直接追踪主题令牌、对比字段与 `<svg>` 图表、排期冲突策略、跨模块历史栈、异步通道 `AbortController` 与序号防竞态、以及提交容错逻辑是否简洁高内聚（并确认 `mock_backend.js` 未被硬编码绕过）；
   - **严守定档与反端水铁律（严禁温和折中，必须拉开真实区分度）**：
     - **绝不端水**：严禁把有明显体验硬伤、视觉平庸粗糙或代码臃肿/工程瑕疵的作品扎堆打在 7.5～8.5 的“安全折中区”（微调 ±0.2 分对冲功过）。必须先按硬伤直接降档，再看亮点。
     - **基础定档线**：只把基本主干做通但界面像简陋后台表单、缺乏异步并发保护与工作台耦合体贴设计的，最高给 5 级达标分（约一半分数）；兼具精致耐看的现代视觉质感、体贴交互巧思与精炼高内聚代码且无硬伤的，才给 8.5～9.6+ 级。
     - **三个维度独立聚焦与硬伤重扣（每项满分 10 分，命中硬伤直接扣 1.0～2.5 分，不予亮点对冲）**：
       - **D1 视觉设计质感与信息层级（0–10 分）**：纯看 12 张真实截图的版式秩序、留白节奏、字号层级、深浅色多层表面与组件微质感。整体缺乏字号层级与留白、卡片拥挤生硬（封顶 ≤ 6.0 分）；`[S03]` 对比面板 `<svg>` 多维图区域画面完全空白或文字重叠（重扣 2.0～2.5 分，封顶 ≤ 7.2 分）；下拉框等控件显示空白或错位（扣 1.0～1.5 分）；手机端吸顶栏 + 悬浮对比条遮挡正文（扣 1.5～2.0 分）。
       - **D2 开放痛点的自发交互巧思（0–10 分）**：纯看四大开放痛点下的自发产品交互设计。排期冲突未可视化 14 周忙闲或未提供一键顺延至连续空闲周（扣 1.5～2.0 分）；规划台一键带入留言时漏掉已选对比项目或粗暴覆盖访客已填附注（重扣 1.5～2.2 分）；联系表单改对单字段后错误框未即时隐藏，或 `503` 重试拿到回执后旧红色报错条仍残留在页面上（扣 1.2～1.8 分）；缺少长文阅读进度指示或目录高亮跟随（扣 0.8～1.2 分）；因详情返回列表卡死导致后续工作台与提交交互在连环画中无法触发（封顶 ≤ 4.2 分）。
       - **D3 代码简洁度与高内聚架构（0–10 分）**：直接审阅源码本身。奖励 1500～2800 行干净利落的高内聚实现，代码臃肿堆砌（4000+ 行大量重复拼接）或状态/DOM 散乱耦合（扣 1.0～2.0 分）；检索/详情/测算缺乏独立 `AbortController` + 递增序号防倒灌（重扣 1.8～2.5 分）；存在 CSS `display:flex` 覆盖 `[hidden]`、初始枚举值与后端字典脱节、路由返回盲目调用 `history.back()`、输入框 `Ctrl+Z` 被劫持或无限 `rAF` 空转等工程漏洞（每项扣 1.0～2.0 分）。
3. **（可选）轻量无头靶向补测 + 追加提交评分**：
   - 若源码中存在静态连环画未覆盖的特色痛点设计，可调用官方靶向补测脚本验证（**提交前务必删除 `draft/` 下的补测截图**）：
     ```sh
     python tools/judge_probe.py --case-dir "leaderboard/blind/<pack_id>/case-01" --viewport 1440x900 --press "Escape" --out draft/probe.png
     ```
   - 执行 `<pack_dir>/SUBMIT.md` 中的命令将评分原子追加至中心日志 `leaderboard/reviews.jsonl`（只写不读，不回显他人打分）：
     ```sh
     python src/scoring/judge_submit.py \
       --pack-dir "leaderboard/blind/<pack_id>" \
       --case-id case-01 \
       --judge-id <你的评委唯一ID，如 judge-alpha> \
       --judge-model <你的模型名称，如 claude-opus-4> \
       --D1 <0-10> --D2 <0-10> --D3 <0-10> \
       --evidence "[S01][S02][S06][S07] + [code/xxx.js:Lxx]" \
       --note "指出该作品的最强反证与最值得改进的一处视觉、交互或代码工程短板"
     ```

### 阶段二：盲评全部收齐后，审计并一键出榜

等所有待评模型的盲评均已写入 `leaderboard/reviews.jsonl` 后，按顺序执行以下三条命令完成审计、浏览器压测定稿与榜单归档：

```sh
# 1) 隔离、代码冻结、草稿清空与盲评脱敏严格审计
python tools/isolation_audit.py --strict

# 2) 同模型多批次端到端计时（B2）重叠审计
python tools/timing_audit.py runs --strict

# 3) 一键拉起无头浏览器三波剧本定稿客观分（70 分）并合并盲评（30 分）出榜
python leaderboard/finalize.py
```

常用可选用法：
- 预览多评委聚合统计表：`python src/scoring/review_merge.py --log leaderboard/reviews.jsonl --out leaderboard/reviews.merged.json`
- 仅汇总指定模型：`python leaderboard/finalize.py --model <模型名>`
- 允许部分未评完批次跳过先出已评批次：`python leaderboard/finalize.py --allow-partial`
- 仅演练打印不改写榜单文件：`python leaderboard/finalize.py --dry-run`

---

## 3. 全流程留档体系与维护自检（仅供维护基准时阅读）

### 3.1 规范留档地图（每一步都有据可查）

| 留档路径 | 写入时机与工具 | 留档内容与审计用途 |
| --- | --- | --- |
| `runs/<名>/protocol.json` | 开局 `start_run.py` / 收尾 `judge_pack.py` | 起点 `t0`、终点 `t1`、墙钟秒数、`env_commit` 环境哈希、`code_sha256` 沙盒代码冻结哈希 |
| `runs/<名>/token_usage.json` | 选手收尾自报 | 输入/输出/总词元消耗诊断记录 |
| `runs/<名>/{result.json,评分.json}` | 出榜 `finalize.py` 调 `score_run.py` | 三波无头浏览器原始物理测量值、逐项检查状态与连续插值客观得分（70 分） |
| `runs/<名>/{audit_report.md,wave_trace.jsonl}` | 出榜 `finalize.py` 调 `score_run.py` | 人类可读的物理测量缺陷报告与三波剧本逐步执行时间线 |
| `leaderboard/blind/<pack_id>/` | 收尾 `judge_pack.py` | 12 张《交互状态连环画》截图（`S01`–`S12`）、`STORYBOARD.md` 物理批注、脱敏源码与说明文档 |
| `leaderboard/blind-maps/*.json` | 收尾 `judge_pack.py` | 匿名 `pack_id`/`case_id` 到真实模型及代码承诺的私有映射 |
| `leaderboard/reviews.jsonl` | 盲评 `judge_submit.py` | 加锁只追加的评委打分、证据引用与反证记录 |
| `leaderboard/runs_log.jsonl` | `start` / `pack` / `finalize` 全程 | 全生命周期事件时间戳与哈希台账 |
| `leaderboard/verdicts/<模型>.json` | 出榜 `finalize.py` | 单模型结构化最终裁决档案（批次明细、均值、极差半宽） |
| `leaderboard/scores.md` | 出榜 `finalize.py` | 按总分降序排列的总榜与各模型分项成绩表 |

### 3.2 维护改动与双基线自检

- **单一配置源**：所有分值权重、视口尺寸、对比度与溢出像素插值节点、B2 时间衰减常数均定义在 `configs/benchmark.json`，禁止在脚本中硬编码阈值。
- **提交前必跑双基线全链路自检**（一次性验证 Python 语法、计分与审计单测、空壳基线 + 简陋基线 + 黄金参考基线的开局、连环画打包、隔离审计、多评委防重提交与一键出榜分数梯度）：
  ```sh
  pwsh tests/smoke.ps1
  ```
