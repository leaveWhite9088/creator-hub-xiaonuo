/* eslint-disable no-var */
/**
 * 林澈顾问工作台 · 本地离线模拟后端服务（mock_backend.js · Official Read-Only）
 *
 * 警告：本文件属于基准受保护基础设施（纳入 SHA-256 完整性校验），严禁修改、覆盖或删除！
 * 请通过全局只读对象 window.LincheMockAPI 调用异步接口，勿在前端硬编码复制本文件业务数据。
 */
(function initLincheMockBackend(global) {
  "use strict";

  var TELEMETRY = {
    bootstrapCalls: 0,
    queryCalls: 0,
    detailCalls: 0,
    planCalls: 0,
    submitCalls: 0,
    abortedCalls: 0,
    duplicateSubmits: 0,
    transient503Triggered: 0,
    successfulInquiries: 0,
    issuedInquiryIds: []
  };

  var requestSeqCounter = 0;
  var inFlightSubmitCount = 0;
  var validSubmitAttempts = 0;

  var PROFILE = {
    name: "林澈",
    studio: "林澈 · 应用研究与工程顾问工作室",
    location: "中国 · 杭州（支持远程与驻场协作）",
    title: "独立 AI 应用研究者 · 评测与智能体落地顾问",
    tagline: "把脆弱的演示原型，打磨成经得起对抗压测与线上波动的工程系统。",
    bio: "曾在互联网研发团队负责两年大模型应用工程化落地，现独立开展私有评测基准构建、复杂智能体状态流诊断与轻量离线研究工具开发。",
    metrics: [
      { label: "聚焦方向", value: "评测基准 / 智能体 / 离线工具" },
      { label: "交付准则", value: "可复现 · 可解释 · 零黑盒" },
      { label: "常驻城市", value: "杭州 · 1对1深度协作" }
    ],
    demoNotice: "演示说明：本页展示的项目档案、实测手记、忙闲档期与预算测算均来自本地模拟服务演示样本，并非真实商业客户合同承诺。",
    contactEmail: "linche@example.com",
    contactEmailNote: "演示占位邮箱（正式上线前待替换）"
  };

  var CATEGORIES = [
    { id: "all", label: "全部方向" },
    { id: "eval", label: "评测基准" },
    { id: "agent", label: "智能体工程" },
    { id: "tool", label: "离线研究工具" }
  ];

  var SORT_OPTIONS = [
    { id: "featured", label: "综合推荐顺序" },
    { id: "latest", label: "按更新时间最新" },
    { id: "depth", label: "按工程复杂度优先" }
  ];

  var RADAR_AXES = ["回归覆盖度", "接入轻量度", "排障可解释性", "交付敏捷度"];

  var PROJECTS = [
    {
      id: "proj-eval-kit",
      featuredRank: 1,
      title: "端到端回归沙盒与语义漂移门禁套件",
      category: "eval",
      categoryLabel: "评测基准",
      date: "2026-06",
      depthScore: 92,
      durationHint: "2～3 周标准接入",
      summary: "面向高频发版团队的离线确定性回归底座，自动捕获提示词迭代引发的格式破损与边界退化。",
      scenario: "适合已有初步大模型业务链路、但每次改提示词或换模型都靠人工抽查救火的研发团队。",
      deliverables: [
        "分层黄金与对抗回归样本库（200～500 条结构化用例）",
        "零外网依赖的确定性断言执行器与差异对比报告",
        "发版前语义漂移熔断器配置与持续集成门禁脚本"
      ],
      tags: ["回归门禁", "对抗样本", "确定性断言"],
      radarAxes: RADAR_AXES,
      metrics: {
        "回归覆盖度": 95,
        "接入轻量度": 78,
        "排障可解释性": 91,
        "交付敏捷度": 82
      },
      detailParagraphs: [
        "许多团队在模型应用上线初期只做几十条主观打分表，一旦进入多轮迭代，修好一个坏案例往往悄悄改崩另外三个历史场景。本套件围绕“失败优先”设计，将线上真实坏样本沉淀为可自动重放的本地确定性契约。",
        "核心引擎内置语义漂移熔断器，不依赖外部商业裁判接口即可对结构化字段完整性、拒答边界、引用溯源一致性与延迟分位数做毫秒级核验，帮助研发在合并代码前直接定位退化根因。"
      ],
      architectureNotes: "采用用例配置层、沙盒执行层与差异归因层三段式解耦，单机无网环境即可跑完全量门禁。"
    },
    {
      id: "proj-agent-trace",
      featuredRank: 2,
      title: "多步工具调用状态机与因果快照诊断台",
      category: "agent",
      categoryLabel: "智能体工程",
      date: "2026-09",
      depthScore: 96,
      durationHint: "3～4 周深度共创",
      summary: "针对长链路智能体的死循环、工具参数幻觉与并发竞态，提供可逐帧回退重放的状态诊断工作台。",
      scenario: "适合工具调用超过 5 步、频繁出现偶发卡死或上下文污染却难以复现现场的智能体产品团队。",
      deliverables: [
        "带幂等锁与超时熔断的显式有限状态机骨架",
        "因果快照回放树查看器（支持任意中间节点分叉重跑）",
        "工具返回异常与半截流式中断的降级恢复策略"
      ],
      tags: ["状态机", "链路回放", "竞态治理"],
      radarAxes: RADAR_AXES,
      metrics: {
        "回归覆盖度": 86,
        "接入轻量度": 68,
        "排障可解释性": 98,
        "交付敏捷度": 74
      },
      detailParagraphs: [
        "长链路智能体最怕把所有历史对话胡乱塞进同一个可变数组：一旦某步工具超时重试或用户中途改口，旧响应很容易在半秒后倒灌进新状态，导致界面与底层记忆彻底撕裂。",
        "该项目通过因果快照回放树完整记录每一次模型决策、工具入参与环境回执。排障工程师点选任意异常节点即可离线重放上下文，无需反复消耗线上词元就能复现罕见竞态故障。"
      ],
      architectureNotes: "内置请求代际序号锁与不可变事件日志，彻底隔离慢速旧工具回调对当前活跃会话的污染。"
    },
    {
      id: "proj-offline-rag",
      featuredRank: 3,
      title: "本地双索引技术文档分块与引用溯源检索引擎",
      category: "tool",
      categoryLabel: "离线研究工具",
      date: "2026-03",
      depthScore: 84,
      durationHint: "1.5～2 周快速交付",
      summary: "专为内网与离线环境设计的轻量混合检索工具，保留代码块与表格上下文边界并精确高亮原文出处。",
      scenario: "适合需要在私有环境检索内部架构规范、接口契约与故障复盘库且严禁数据出境的技术组织。",
      deliverables: [
        "感知标题层级与代码表格边界的自适应分块器",
        "双索引倒排分片与词元交集重排模块",
        "精确到段落行号的原文溯源对照面板"
      ],
      tags: ["混合检索", "表格保真", "私有离线"],
      radarAxes: RADAR_AXES,
      metrics: {
        "回归覆盖度": 80,
        "接入轻量度": 94,
        "排障可解释性": 88,
        "交付敏捷度": 92
      },
      detailParagraphs: [
        "传统按固定字数硬切文档的做法会把跨行参数表格和代码示例拦腰截断，导致模型拿到半截残缺上下文胡乱编造结论。本工具在解析阶段完整保留章节树、代码块与表格表头关联。",
        "检索层结合双索引倒排分片与多词交集加权策略，在普通笔记本本地即可实现十万字级技术手记的毫秒级召回，并直接定位到原始段落供人工交叉核验。"
      ],
      architectureNotes: "零外部数据库依赖，索引产物为纯静态紧凑 JSON 分片，支持增量构建与版本比对。"
    },
    {
      id: "proj-ui-probe",
      featuredRank: 4,
      title: "前端可用性与视口几何防遮挡自动化巡检器",
      category: "eval",
      categoryLabel: "评测基准",
      date: "2026-08",
      depthScore: 88,
      durationHint: "2 周定制集成",
      summary: "利用无头浏览器实测多视口溢出、悬浮栏遮挡、对比度短板与键盘焦点闭环的前端质量体验探针。",
      scenario: "适合使用生成式代码工具加速前端开发、但经常在手机小屏和深色模式下翻车的敏捷团队。",
      deliverables: [
        "桌面与窄屏四档视口物理包围盒巡检脚本",
        "深浅色 WCAG 真实合成对比度短板木桶审计器",
        "模态弹窗焦点闭环与纯键盘可达性冒烟流水线"
      ],
      tags: ["几何探针", "无障碍审计", "视觉防崩"],
      radarAxes: RADAR_AXES,
      metrics: {
        "回归覆盖度": 92,
        "接入轻量度": 89,
        "排障可解释性": 90,
        "交付敏捷度": 88
      },
      detailParagraphs: [
        "代码生成模型写业务逻辑往往很快，却看不见真实渲染后的像素碰撞：比如窄屏下吸顶导航和底部对比栏把正文按钮挡死、或者深色模式下浅底徽章配浅灰字根本没法读。",
        "本工具通过视口包围盒几何探针直接采集真实计算样式与中心点命中元素，把原本依赖人工肉眼逐屏检查的排版硬伤转化为可量化、可阻断发版的客观指标。"
      ],
      architectureNotes: "基于标准无头浏览器脚本驱动，单次全视口巡检耗时控制在 5 秒以内。"
    }
  ];

  var ARTICLES = [
    {
      id: "art-gauntlet",
      featuredRank: 1,
      title: "为什么保底分喂不出好工程：从静态清单走向连环状态压测",
      date: "2026-10-18",
      readingMinutes: 6,
      category: "评测基准",
      tags: ["基准设计", "区分度", "木桶效应"],
      summary: "复盘内部前端与智能体评测体系迭代：当基础静态检查全部饱和后，如何靠耦合业务链路与短板木桶模型拉开真实工程差距。",
      toc: [
        { id: "sec-saturation", title: "一、静态打勾清单为何迅速失效", level: 2 },
        { id: "sec-barrel", title: "二、连环门控与短板木桶聚合曲线", level: 2 },
        { id: "sec-data", title: "三、实测得分分布对照与落地建议", level: 2 }
      ],
      bodyHtml:
        '<h2 id="sec-saturation">一、静态打勾清单为何迅速失效</h2>' +
        "<p>在搭建内部工程基准的早期，我们曾把一半以上的权重放在静态存在性检查上：页面有没有搜索框、有没有四个卡片、有没有切换按钮。结果不到两个月，几乎所有中轻量模型都能靠机械堆砌标签拿到八成以上的高分，但真正打开页面试用两分钟，各种状态撕裂和排版遮挡依然层出不穷。</p>" +
        "<blockquote>把答案写在题目清单里的评测，测出来的不是工程解决能力，而是指令复读顺从度。</blockquote>" +
        "<p>问题根源在于真实软件的脆弱点从来不在孤立静态节点，而在多模块同时交互时的耦合边界：一边筛着分类、一边改着排期、中途反悔撤销再切到手机窄屏，任何一环偷懒都会让整条业务链路断掉。</p>" +
        '<h2 id="sec-barrel">二、连环门控与短板木桶聚合曲线</h2>' +
        "<p>为了挤掉虚假保底水分，我们在新版评测里引入了连环门控与短板木桶聚合曲线：上游基础检索或报价计算一旦失真，下游衍生步骤不再独立送分；同时在视觉可读性上采用最低单点高权重混合公式，杜绝用九个高对比段落掩盖一个完全看不清的报错提示。</p>" +
        "<ul>" +
        "<li>砍掉静态占位赠分，把分值集中到跨模块联动与异常恢复节点；</li>" +
        "<li>删掉手把手教按钮命名的剧透提示，只考核最终业务不变量是否成立；</li>" +
        "<li>引入真实异步延迟与瞬时故障，检验前端是否具备生产级防御本能。</li>" +
        "</ul>" +
        '<h2 id="sec-data">三、实测得分分布对照与落地建议</h2>' +
        "<p>下表记录了同一批候选模型在旧版静态清单制与新版连环压测制下的实测区分度对比：</p>" +
        "<table><thead><tr><th>评测机制版本</th><th>简陋实现均分</th><th>轻量模型均分</th><th>旗舰模型均分</th><th>极差跨度</th></tr></thead>" +
        "<tbody>" +
        "<tr><td>旧版静态清单制</td><td>58.4</td><td>82.1</td><td>86.5</td><td>28.1</td></tr>" +
        "<tr><td>新版连环压测制</td><td>22.6</td><td>64.8</td><td>91.2</td><td>68.6</td></tr>" +
        "</tbody></table>" +
        "<p>可以看到，当评测标准回归真实工程联调场景后，糊弄过关的样板代码立刻现出原形，而真正扎实处理时序与几何细节的方案则获得了清晰的领先身位。</p>"
    },
    {
      id: "art-async-race",
      featuredRank: 2,
      title: "异步前端最隐蔽的线上事故：慢请求倒灌与重复提交锁",
      date: "2026-09-26",
      readingMinutes: 7,
      category: "智能体工程",
      tags: ["异步竞态", "幂等保护", "容错回退"],
      summary: "拆解搜索筛选、动态测算与表单提交中最常翻车的两类时序故障：先发慢回覆盖新状态，以及网络抖动下的表单丢失与连点重发。",
      toc: [
        { id: "sec-race", title: "一、为什么本地没问题、一上线就张冠李戴", level: 2 },
        { id: "sec-token", title: "二、单调递增请求令牌与中止信号模式", level: 2 },
        { id: "sec-submit", title: "三、提交锁释放与瞬时故障保底准则", level: 2 }
      ],
      bodyHtml:
        '<h2 id="sec-race">一、为什么本地没问题、一上线就张冠李戴</h2>' +
        "<p>很多前端原型在本地用内存假数组开发时丝滑无比，一旦接上真实后端接口立刻怪病频发。最典型的场景是：访客先输入一个宽泛热词触发全表扫描（耗时三百毫秒），紧接着敲入第二个限定词命中缓存索引（耗时四十毫秒）。如果不做时序保护，后返回的慢请求就会把页面重新刷回旧结果，造成输入框文字与列表内容完全对不上。</p>" +
        "<ol>" +
        "<li>检索与分类快速连切时，旧分类列表晚回来顶掉新分类；</li>" +
        "<li>报价台勾选多项重算中途点击重置，旧的高价结果半秒后倒灌回摘要栏；</li>" +
        "<li>连续点击上下篇文章时，前一篇慢响应覆盖当前正在阅读的章节。</li>" +
        "</ol>" +
        '<h2 id="sec-token">二、单调递增请求令牌与中止信号模式</h2>' +
        "<p>解决乱序倒灌并不需要引入沉重的第三方状态库。只需为每一条异步通道维护一个单调递增请求令牌，并配合浏览器原生中止控制器，在发起新请求时主动作废在途旧请求，并在回调落盘前二次核验令牌一致性：</p>" +
        "<pre><code>let latestSeq = 0;\nlet activeCtrl = null;\nasync function runSafeQuery(params) {\n  if (activeCtrl) activeCtrl.abort();\n  const ctrl = new AbortController();\n  activeCtrl = ctrl;\n  const seq = ++latestSeq;\n  const data = await api.queryCatalog(params, { signal: ctrl.signal });\n  if (seq !== latestSeq) return;\n  renderCatalog(data);\n}</code></pre>" +
        '<h2 id="sec-submit">三、提交锁释放与瞬时故障保底准则</h2>' +
        "<p>在表单提交环节，工程成熟度体现在两个细节：一是请求在途期间必须锁定提交入口，防止访客手快连点发出双份咨询单；二是遇到网关偶发五零三繁忙报错时，必须在最终分支可靠解锁按钮，同时原封不动保留访客已经敲好的姓名、邮箱与长段留言，让访客点一下重试就能顺利过关。</p>" +
        "<p>很多线上投诉并不是因为接口偶发报错本身，而是报错发生的一瞬间前端提前清空了输入框，逼着客户重新回忆并手打几百字需求背景。把异步请求视为默认不可靠的外部边界，先确认服务端回执落盘再归档本地草稿，才是经得起真实流量考验的前端基本功。</p>"
    },
    {
      id: "art-offline-rag",
      featuredRank: 3,
      title: "离线技术文库分块实践：别让硬截断毁掉数据表格与代码上下文",
      date: "2026-07-11",
      readingMinutes: 5,
      category: "离线研究工具",
      tags: ["文档解析", "检索召回", "离线架构"],
      summary: "对比三种技术文档切分策略在跨列参数表与长代码块场景下的召回准确率，给出零外部依赖的轻量离线索引方案。",
      toc: [
        { id: "sec-chunk-pain", title: "一、固定窗口硬切分的三处重灾区", level: 2 },
        { id: "sec-boundary", title: "二、结构感知的离线词元切分边界", level: 2 },
        { id: "sec-bench", title: "三、三种分块策略召回耗时对比", level: 2 }
      ],
      bodyHtml:
        '<h2 id="sec-chunk-pain">一、固定窗口硬切分的三处重灾区</h2>' +
        "<p>在处理包含大量配置表格与示例脚本的工程手册时，按五百字符机械滑动切分几乎必然破坏语义完整性：表头留在上一块而数据行掉进下一块，或者函数签名与异常处理逻辑被拆成两半，模型拿到碎片后只能靠猜补全。</p>" +
        "<p>尤其在离线内网顾问场景下，架构文档往往夹杂多列配置阈值表、版本迁移对照表与命令行脚本。一旦表头列含义丢失，即使向量相似度排在前列，拼进上下文后也会产生张冠李戴的参数建议。</p>" +
        "<blockquote>检索质量的下限由分块器决定；被切碎的表格即使召回排在第一名，也只会误导下游回答。</blockquote>" +
        '<h2 id="sec-boundary">二、结构感知的离线词元切分边界</h2>' +
        "<p>我们在本地检索引擎中采用了基于语法树节点的离线词元切分边界算法：遇到代码块与表格时优先保持整体原子性；若超大表格必须拆分，则自动向每个子分片注入表头行与所属章节面包屑路径，确保任意单块独立可读。</p>" +
        "<ul>" +
        "<li>章节面包屑前置注入，保留上级业务语境与适用版本范围；</li>" +
        "<li>跨页宽表格自动携带表头字段名副本，避免裸数字脱离单位；</li>" +
        "<li>多关键词空格交集匹配并支持正文深处短语定位与原文溯源。</li>" +
        "</ul>" +
        '<h2 id="sec-bench">三、三种分块策略召回耗时对比</h2>' +
        "<p>在四百篇内部工程复盘手记样本上，三种离线切分策略的实测指标如下：</p>" +
        "<table><thead><tr><th>分块方案</th><th>表格问答准确率</th><th>代码定位召回率</th><th>本地构建耗时</th></tr></thead>" +
        "<tbody>" +
        "<tr><td>固定字符滑窗</td><td>51.0%</td><td>62.5%</td><td>0.8s</td></tr>" +
        "<tr><td>纯段落换行切分</td><td>68.5%</td><td>74.0%</td><td>1.1s</td></tr>" +
        "<tr><td>结构感知保真切分</td><td>91.5%</td><td>93.0%</td><td>1.6s</td></tr>" +
        "</tbody></table>" +
        "<p>多花不到一秒的离线预处理时间，就能换来表格与代码问答超过二十个百分点的准确率提升，同时避免了引入重型外部解析服务的运维负担，是性价比极高的工程投入。</p>"
    },
    {
      id: "art-a11y-dark",
      featuredRank: 4,
      title: "工具型网页的耐看与顺手：窄屏防挤占、深色层次与键盘归位",
      date: "2026-08-09",
      readingMinutes: 5,
      category: "评测基准",
      tags: ["排版细节", "深浅配色", "键盘无障碍"],
      summary: "好用的工作台不靠刺眼渐变炫技，而藏在不撑破窄屏的数据表、层次分明的深色表面与顺滑的焦点闭环里。",
      toc: [
        { id: "sec-mobile-box", title: "一、小屏视口下的悬浮层预算管理", level: 2 },
        { id: "sec-dark-contrast", title: "二、深色模式不是简单反相变黑", level: 2 },
        { id: "sec-focus-stack", title: "三、弹窗焦点闭环与焦点回退锚点栈", level: 2 }
      ],
      bodyHtml:
        '<h2 id="sec-mobile-box">一、小屏视口下的悬浮层预算管理</h2>' +
        "<p>桌面宽屏下看似宽敞的吸顶导航栏与底部常驻对比条，一到三百七十五像素宽的手机屏幕上往往变成灾难：上下两道固定栏吃掉近四成高度，中间正文区连点个操作按钮都被悬浮层死死挡住。克制的响应式设计必须严格控制固定层总高度占比，并为底部留出充足的安全滚动余量。</p>" +
        "<p>此外，长文里的多列对比表格、代码片段与多维矢量图表在窄屏下绝不能硬设固定像素最小宽度撑裂视口，而应结合局部横向滚动容器与弹性折行规则，让正文边距始终从容呼吸。</p>" +
        '<h2 id="sec-dark-contrast">二、深色模式不是简单反相变黑</h2>' +
        "<p>许多粗糙的深色主题只把页面背景改成纯黑，却忘了同步调整选中态胶囊、次要说明字和报错提示的明度对比，导致蓝底蓝字或暗红字在深灰卡片上几乎隐形。建立清晰的表面层级变量并在两套主题下逐一校验文本与背景合成对比度，才能保证长文久看依然柔和清晰。</p>" +
        '<h2 id="sec-focus-stack">三、弹窗焦点闭环与焦点回退锚点栈</h2>' +
        "<p>对于高频使用键盘的工程师访客，打开横向对比面板后按制表键焦点不应漏到背景长页面里，关闭面板或从文章详情退回列表时，通过焦点回退锚点栈将光标与滚动高度一并归还到触发前的位置，这种润物无声的确定感正是专业工具质感的核心来源。</p>" +
        "<pre><code>function restoreOriginFocus(originEl, savedScrollY) {\n  window.scrollTo(0, savedScrollY);\n  if (originEl && typeof originEl.focus === 'function') {\n    originEl.focus({ preventScroll: true });\n  }\n}</code></pre>" +
        "<p>真正耐用的工作台不需要满屏闪烁动效：当每一次筛选、对比、撤销与返回都稳稳落在用户心理预期的位置上时，克制而周到的秩序感自然会建立起专业信任。</p>"
    }
  ];

  var PLANNER_MODES = [
    {
      id: "diag",
      label: "短期评测体系诊断",
      baseWeeks: 2,
      baseMinK: 18,
      baseMaxK: 24,
      description: "梳理核心业务坏案例、搭建本地回归门禁与首批高区分度样本基线"
    },
    {
      id: "proto",
      label: "智能体工作流原型共创",
      baseWeeks: 3,
      baseMinK: 32,
      baseMaxK: 42,
      description: "联合设计状态机架构、打通异步工具容错链路并交付可验证原型"
    },
    {
      id: "workshop",
      label: "研发团队工程实战内训",
      baseWeeks: 1,
      baseMinK: 12,
      baseMaxK: 16,
      description: "结合团队真实代码库开展评测方法、竞态排障与前端可用性演练"
    }
  ];

  var PLANNER_ADDONS = [
    { id: "dataset", label: "对抗回归样本集扩充", addWeeks: 1, addMinK: 8, addMaxK: 11 },
    { id: "replay", label: "状态快照回放诊断面板", addWeeks: 1, addMinK: 9, addMaxK: 13 },
    { id: "ci_gate", label: "无头自动化门禁脚本集成", addWeeks: 1, addMinK: 6, addMaxK: 9 },
    { id: "handover", label: "双周陪跑与维护交接手册", addWeeks: 1, addMinK: 5, addMaxK: 7 }
  ];

  var PLANNER_SCALES = [
    { id: "standard", label: "单业务线标准规模", weekDelta: 0, priceMultiplier: 1.0 },
    { id: "multi", label: "跨团队多模块协同", weekDelta: 1, priceMultiplier: 1.25 },
    { id: "critical", label: "核心生产级高合规", weekDelta: 2, priceMultiplier: 1.55 }
  ];

  // 14 周完整连续档期日历（前 8 周可作为期望启动周，后 6 周供长周期项目跨度顺延校验）
  var CALENDAR_WEEKS = [
    { week: "2026-W47", index: 0, label: "11月第3周", selectableAsStart: true, busy: false, busyReason: "" },
    { week: "2026-W48", index: 1, label: "11月第4周", selectableAsStart: true, busy: true, busyReason: "存量金融客户评测验收周（已约满）" },
    { week: "2026-W49", index: 2, label: "12月第1周", selectableAsStart: true, busy: false, busyReason: "" },
    { week: "2026-W50", index: 3, label: "12月第2周", selectableAsStart: true, busy: false, busyReason: "" },
    { week: "2026-W51", index: 4, label: "12月第3周", selectableAsStart: true, busy: true, busyReason: "年度智能体架构封闭内训周（已约满）" },
    { week: "2026-W52", index: 5, label: "12月第4周", selectableAsStart: true, busy: false, busyReason: "" },
    { week: "2027-W01", index: 6, label: "1月第1周", selectableAsStart: true, busy: false, busyReason: "" },
    { week: "2027-W02", index: 7, label: "1月第2周", selectableAsStart: true, busy: false, busyReason: "" },
    { week: "2027-W03", index: 8, label: "1月第3周", selectableAsStart: false, busy: false, busyReason: "" },
    { week: "2027-W04", index: 9, label: "1月第4周", selectableAsStart: false, busy: false, busyReason: "" },
    { week: "2027-W05", index: 10, label: "2月第1周", selectableAsStart: false, busy: false, busyReason: "" },
    { week: "2027-W06", index: 11, label: "2月第2周", selectableAsStart: false, busy: false, busyReason: "" },
    { week: "2027-W07", index: 12, label: "2月第3周", selectableAsStart: false, busy: false, busyReason: "" },
    { week: "2027-W08", index: 13, label: "2月第4周", selectableAsStart: false, busy: false, busyReason: "" }
  ];

  function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
  }

  function stripHtml(html) {
    return String(html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  }

  function makeAbortError() {
    var err = new Error("Request aborted by client signal");
    err.name = "AbortError";
    err.code = "ABORTED";
    err.retryable = false;
    return err;
  }

  function makeApiError(code, message, retryable, extra) {
    var err = new Error(message);
    err.name = "LincheApiError";
    err.code = code;
    err.retryable = Boolean(retryable);
    if (extra && typeof extra === "object") {
      Object.keys(extra).forEach(function (k) {
        err[k] = extra[k];
      });
    }
    return err;
  }

  function delayWithSignal(ms, signal) {
    return new Promise(function (resolve, reject) {
      if (signal && signal.aborted) {
        TELEMETRY.abortedCalls += 1;
        reject(makeAbortError());
        return;
      }
      var done = false;
      var timer = setTimeout(function () {
        if (done) return;
        done = true;
        if (signal && onAbort) {
          try {
            signal.removeEventListener("abort", onAbort);
          } catch (_e) {}
        }
        resolve();
      }, Math.max(0, Number(ms) || 0));

      var onAbort = null;
      if (signal && typeof signal.addEventListener === "function") {
        onAbort = function () {
          if (done) return;
          done = true;
          clearTimeout(timer);
          TELEMETRY.abortedCalls += 1;
          reject(makeAbortError());
        };
        signal.addEventListener("abort", onAbort, { once: true });
      }
    });
  }

  function toProjectSummary(p) {
    var metricList = p.radarAxes.map(function (ax) {
      return { axis: ax, score: p.metrics[ax] };
    });
    return {
      id: p.id,
      featuredRank: p.featuredRank,
      title: p.title,
      category: p.category,
      categoryLabel: p.categoryLabel,
      date: p.date,
      depthScore: p.depthScore,
      durationHint: p.durationHint,
      summary: p.summary,
      scenario: p.scenario,
      deliverables: deepClone(p.deliverables),
      tags: deepClone(p.tags),
      radarAxes: deepClone(p.radarAxes),
      metrics: deepClone(p.metrics),
      metricList: metricList
    };
  }

  function toArticleSummary(a) {
    return {
      id: a.id,
      featuredRank: a.featuredRank,
      title: a.title,
      date: a.date,
      readingMinutes: a.readingMinutes,
      category: a.category,
      tags: deepClone(a.tags),
      summary: a.summary,
      tocCount: a.toc.length
    };
  }

  function computePlanSync(params) {
    var p = params || {};
    var mode = PLANNER_MODES.find(function (m) { return m.id === p.modeId; }) || PLANNER_MODES[0];
    var addonIds = Array.isArray(p.addonIds) ? p.addonIds : [];
    var chosenAddons = PLANNER_ADDONS.filter(function (a) { return addonIds.indexOf(a.id) !== -1; });
    var scale = PLANNER_SCALES.find(function (s) { return s.id === p.scaleId; }) || PLANNER_SCALES[0];

    var startIdx = CALENDAR_WEEKS.findIndex(function (w) { return w.week === p.startWeek; });
    if (startIdx < 0) startIdx = 2; // 默认 2026-W49（12月第1周，无冲突）

    var addonWeeks = chosenAddons.reduce(function (acc, a) { return acc + a.addWeeks; }, 0);
    var totalWeeks = mode.baseWeeks + addonWeeks + scale.weekDelta;

    var rawMin = mode.baseMinK + chosenAddons.reduce(function (acc, a) { return acc + a.addMinK; }, 0);
    var rawMax = mode.baseMaxK + chosenAddons.reduce(function (acc, a) { return acc + a.addMaxK; }, 0);
    var budgetMinK = Math.round(rawMin * scale.priceMultiplier);
    var budgetMaxK = Math.round(rawMax * scale.priceMultiplier);

    var spanWeeks = CALENDAR_WEEKS.slice(startIdx, startIdx + totalWeeks);
    var overflowBeyondHorizon = (startIdx + totalWeeks) > CALENDAR_WEEKS.length;
    var busyHits = spanWeeks
      .filter(function (w) { return w.busy; })
      .map(function (w) {
        return { week: w.week, label: w.label, reason: w.busyReason };
      });
    if (overflowBeyondHorizon) {
      busyHits.push({
        week: "HORIZON_END",
        label: "超出近期开放排期窗口",
        reason: "所选启动周过晚，剩余开放周次不足以容纳完整交付周期"
      });
    }

    // 拆分为 3 个阶段里程碑
    var w1 = Math.max(1, Math.floor(totalWeeks * 0.3));
    var w2 = Math.max(1, Math.ceil((totalWeeks - w1) * 0.5));
    var w3 = Math.max(0, totalWeeks - w1 - w2);

    function weekLabelAt(offset) {
      var target = CALENDAR_WEEKS[startIdx + offset];
      return target ? target.label : ("顺延第" + (offset + 1) + "周");
    }

    function rangeLabel(offsetStart, len) {
      if (len <= 1) return weekLabelAt(offsetStart);
      return weekLabelAt(offsetStart) + " – " + weekLabelAt(offsetStart + len - 1);
    }

    var milestones = [
      {
        phase: "阶段一",
        title: "现状走查、场景基线对齐与契约冻结",
        weeks: w1,
        weekRangeLabel: rangeLabel(0, w1),
        deliverable: mode.label + "核心边界定义与基线样本"
      },
      {
        phase: "阶段二",
        title: chosenAddons.length > 0
          ? ("核心模块共创与叠加交付（含" + chosenAddons.map(function (a) { return a.label; }).join("、") + "）")
          : "核心原型构建、压测验证与问题归因",
        weeks: w2,
        weekRangeLabel: rangeLabel(w1, w2),
        deliverable: "可运行工程产物与对抗压测报告"
      }
    ];

    if (w3 >= 1) {
      milestones.push({
        phase: "阶段三",
        title: "联调验收、团队演练与维护文档移交",
        weeks: w3,
        weekRangeLabel: rangeLabel(w1 + w2, w3),
        deliverable: "门禁接入流水线与独立维护手册"
      });
    }

    var hasConflict = busyHits.length > 0;
    var conflictMsg = hasConflict
      ? ("当前排期（" + weekLabelAt(0) + "起共 " + totalWeeks + " 周）与忙碌档期冲突：" +
          busyHits.map(function (b) { return b.label + "（" + b.reason + "）"; }).join("；"))
      : "";

    return {
      modeId: mode.id,
      modeLabel: mode.label,
      addonIds: chosenAddons.map(function (a) { return a.id; }),
      addonLabels: chosenAddons.map(function (a) { return a.label; }),
      scaleId: scale.id,
      scaleLabel: scale.label,
      startWeek: CALENDAR_WEEKS[startIdx].week,
      startWeekLabel: CALENDAR_WEEKS[startIdx].label,
      endWeekLabel: weekLabelAt(Math.max(0, totalWeeks - 1)),
      totalWeeks: totalWeeks,
      budgetMinK: budgetMinK,
      budgetMaxK: budgetMaxK,
      milestones: milestones,
      conflict: {
        hasConflict: hasConflict,
        busyWeeks: busyHits,
        message: conflictMsg
      }
    };
  }

  var api = {
    /**
     * 获取首屏初始化元数据（个人简介、分类字典、排序项、排期规划台配置与 14 周忙闲日历）
     */
    getBootstrap: function getBootstrap(options) {
      TELEMETRY.bootstrapCalls += 1;
      var signal = options && options.signal;
      return delayWithSignal(65, signal).then(function () {
        return {
          profile: deepClone(PROFILE),
          categories: deepClone(CATEGORIES),
          sortOptions: deepClone(SORT_OPTIONS),
          defaultPlan: {
            modeId: "diag",
            addonIds: [],
            scaleId: "standard",
            startWeek: "2026-W49"
          },
          plannerCatalog: {
            modes: deepClone(PLANNER_MODES),
            addons: deepClone(PLANNER_ADDONS),
            scales: deepClone(PLANNER_SCALES),
            calendarWeeks: deepClone(CALENDAR_WEEKS)
          }
        };
      });
    },

    /**
     * 跨项目与长文检索、分类筛选与排序接口
     * 注意：单关键词宽泛全表检索耗时较长（~230ms），多词精确交集或清空重置响应较快（~35ms）。
     */
    queryCatalog: function queryCatalog(params, options) {
      TELEMETRY.queryCalls += 1;
      var reqSeq = ++requestSeqCounter;
      var p = params || {};
      var signal = options && options.signal;

      var rawQ = typeof p.query === "string" ? p.query.trim() : "";
      var tokens = rawQ ? rawQ.toLowerCase().split(/\s+/).filter(Boolean) : [];
      var cat = (p.category || "all").toLowerCase();
      var sortBy = p.sortBy || "featured";
      var favSet = Array.isArray(p.favoriteIds) ? new Set(p.favoriteIds) : null;
      var favOnly = Boolean(p.favoritesOnly);

      var isSlowBroadScan = (tokens.length === 1 && tokens[0].length <= 4) || (tokens.length === 0 && cat === "all" && reqSeq > 1 && sortBy === "featured" && p._broadHint);
      var delayMs = isSlowBroadScan ? 230 : 35;

      return delayWithSignal(delayMs, signal).then(function () {
        var matchedProjects = PROJECTS.filter(function (item) {
          if (cat !== "all" && item.category.toLowerCase() !== cat) return false;
          if (favOnly && favSet && !favSet.has(item.id)) return false;
          if (tokens.length > 0) {
            var haystack = [
              item.title,
              item.categoryLabel,
              item.summary,
              item.scenario,
              item.deliverables.join(" "),
              item.tags.join(" "),
              item.detailParagraphs.join(" "),
              item.architectureNotes
            ].join(" ").toLowerCase();
            for (var i = 0; i < tokens.length; i++) {
              if (haystack.indexOf(tokens[i]) === -1) return false;
            }
          }
          return true;
        });

        var matchedArticles = ARTICLES.filter(function (art) {
          if (tokens.length > 0) {
            var haystack = [
              art.title,
              art.category,
              art.tags.join(" "),
              art.summary,
              stripHtml(art.bodyHtml)
            ].join(" ").toLowerCase();
            for (var i = 0; i < tokens.length; i++) {
              if (haystack.indexOf(tokens[i]) === -1) return false;
            }
          }
          return true;
        });

        if (sortBy === "latest") {
          matchedProjects.sort(function (a, b) { return b.date.localeCompare(a.date); });
          matchedArticles.sort(function (a, b) { return b.date.localeCompare(a.date); });
        } else if (sortBy === "depth") {
          matchedProjects.sort(function (a, b) { return b.depthScore - a.depthScore; });
          matchedArticles.sort(function (a, b) { return b.readingMinutes - a.readingMinutes; });
        } else {
          matchedProjects.sort(function (a, b) { return a.featuredRank - b.featuredRank; });
          matchedArticles.sort(function (a, b) { return a.featuredRank - b.featuredRank; });
        }

        return {
          requestSeq: reqSeq,
          query: rawQ,
          category: cat,
          sortBy: sortBy,
          projects: matchedProjects.map(toProjectSummary),
          articles: matchedArticles.map(toArticleSummary)
        };
      });
    },

    /**
     * 获取单个项目完整详情或单篇长文全文（含目录与上下篇相邻 ID）
     */
    getDetail: function getDetail(params, options) {
      TELEMETRY.detailCalls += 1;
      var p = params || {};
      var signal = options && options.signal;
      var type = p.type;
      var id = p.id;

      var isHeavyDoc = (id === "proj-eval-kit" || id === "art-gauntlet");
      var delayMs = isHeavyDoc ? 195 : 40;

      return delayWithSignal(delayMs, signal).then(function () {
        if (type === "project") {
          var proj = PROJECTS.find(function (x) { return x.id === id; });
          if (!proj) {
            throw makeApiError("NOT_FOUND", "找不到指定的演示项目：" + String(id), false);
          }
          var outProj = toProjectSummary(proj);
          outProj.detailParagraphs = deepClone(proj.detailParagraphs);
          outProj.architectureNotes = proj.architectureNotes;
          return { type: "project", item: outProj };
        }

        if (type === "article") {
          var idx = ARTICLES.findIndex(function (x) { return x.id === id; });
          if (idx < 0) {
            throw makeApiError("NOT_FOUND", "找不到指定的实测长文：" + String(id), false);
          }
          var art = ARTICLES[idx];
          var prevArt = ARTICLES[(idx - 1 + ARTICLES.length) % ARTICLES.length];
          var nextArt = ARTICLES[(idx + 1) % ARTICLES.length];
          return {
            type: "article",
            item: {
              id: art.id,
              title: art.title,
              date: art.date,
              readingMinutes: art.readingMinutes,
              category: art.category,
              tags: deepClone(art.tags),
              summary: art.summary,
              toc: deepClone(art.toc),
              bodyHtml: art.bodyHtml,
              prevArticle: { id: prevArt.id, title: prevArt.title },
              nextArticle: { id: nextArt.id, title: nextArt.title }
            }
          };
        }

        throw makeApiError("BAD_REQUEST", "未知的详情类型：" + String(type), false);
      });
    },

    /**
     * 异步测算合作周期、参考预算区间、分阶段里程碑及忙闲档期冲突详情
     */
    evaluatePlan: function evaluatePlan(params, options) {
      TELEMETRY.planCalls += 1;
      var p = params || {};
      var signal = options && options.signal;
      var addonCount = Array.isArray(p.addonIds) ? p.addonIds.length : 0;
      var delayMs = addonCount >= 2 ? 185 : 35;

      return delayWithSignal(delayMs, signal).then(function () {
        return computePlanSync(p);
      });
    },

    /**
     * 异步提交合作咨询单
     * 行为契约：
     *   - 若存在未完成的在途提交请求时再次并发调用，将拒绝并抛出 code='DUPLICATE_SUBMIT'；
     *   - 若姓名/邮箱/留言长度(10~500字)不合规，抛出 code='VALIDATION_ERROR'；
     *   - 若附带的 planSnapshot 存在未消解的档期冲突，抛出 code='SCHEDULE_CONFLICT'；
     *   - 模拟真实网关偶发拥塞：首次合规提交会触发一次瞬时繁忙（code='SERVICE_BUSY', retryable=true），后续重试恢复正常并返回回执单号。
     */
    submitInquiry: function submitInquiry(payload, options) {
      TELEMETRY.submitCalls += 1;
      var body = payload || {};
      var signal = options && options.signal;

      if (inFlightSubmitCount > 0) {
        TELEMETRY.duplicateSubmits += 1;
        return Promise.reject(
          makeApiError("DUPLICATE_SUBMIT", "上一笔咨询请求仍在处理中，请勿重复提交。", false)
        );
      }

      inFlightSubmitCount += 1;
      var name = typeof body.name === "string" ? body.name.trim() : "";
      var email = typeof body.email === "string" ? body.email.trim() : "";
      var message = typeof body.message === "string" ? body.message.trim() : "";

      return delayWithSignal(165, signal)
        .then(function () {
          if (!name || name.length > 60) {
            throw makeApiError("VALIDATION_ERROR", "请填写有效的姓名或团队称呼（1～60 字）。", false, { field: "name" });
          }
          if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
            throw makeApiError("VALIDATION_ERROR", "请填写格式正确的回复邮箱地址。", false, { field: "email" });
          }
          if (message.length < 10 || message.length > 500) {
            throw makeApiError(
              "VALIDATION_ERROR",
              "合作留言需在 10～500 字之间（当前 " + message.length + " 字）。",
              false,
              { field: "message" }
            );
          }

          if (body.planSnapshot && typeof body.planSnapshot === "object") {
            var verifyPlan = computePlanSync(body.planSnapshot);
            if (verifyPlan.conflict.hasConflict) {
              throw makeApiError(
                "SCHEDULE_CONFLICT",
                "提交被拦截：所选排期仍存在繁忙周冲突（" + verifyPlan.conflict.message + "），请先调整至空闲档期。",
                false,
                { field: "startWeek" }
              );
            }
          }

          validSubmitAttempts += 1;
          if (validSubmitAttempts === 1) {
            TELEMETRY.transient503Triggered += 1;
            throw makeApiError(
              "SERVICE_BUSY",
              "咨询网关瞬时繁忙（503），您的填写内容未丢失，请稍候重试。",
              true,
              { status: 503 }
            );
          }

          TELEMETRY.successfulInquiries += 1;
          var inquiryId = "INQ-2026-" + String(1000 + TELEMETRY.successfulInquiries);
          TELEMETRY.issuedInquiryIds.push(inquiryId);

          var comparedIds = Array.isArray(body.comparedProjectIds) ? body.comparedProjectIds : [];
          var comparedTitles = comparedIds
            .map(function (pid) {
              var found = PROJECTS.find(function (x) { return x.id === pid; });
              return found ? found.title : pid;
            })
            .filter(Boolean);

          var summaryLines = [
            "【合作咨询回执单】" + inquiryId,
            "收件顾问：林澈 <" + PROFILE.contactEmail + ">（演示占位）",
            "来访称呼：" + name,
            "回复邮箱：" + email
          ];
          if (comparedTitles.length > 0) {
            summaryLines.push("参考对比项目：" + comparedTitles.join(" / "));
          }
          if (body.planSnapshot && typeof body.planSnapshot === "object") {
            var snap = computePlanSync(body.planSnapshot);
            summaryLines.push(
              "意向排期方案：" + snap.modeLabel + "｜" + snap.startWeekLabel + "启动（共" + snap.totalWeeks + "周，参考预算 " + snap.budgetMinK + "k–" + snap.budgetMaxK + "k）"
            );
          }
          summaryLines.push("合作背景与需求：\n" + message);

          return {
            ok: true,
            inquiryId: inquiryId,
            receivedAt: "2026-11-15T12:00:00+08:00",
            recipientEmail: PROFILE.contactEmail,
            formattedSummary: summaryLines.join("\n")
          };
        })
        .finally(function () {
          inFlightSubmitCount = Math.max(0, inFlightSubmitCount - 1);
        });
    },

    /**
     * 只读运行遥测快照（供自动化验收核验接口真实调用与并发行为）
     */
    getTelemetry: function getTelemetry() {
      return deepClone(TELEMETRY);
    }
  };

  Object.defineProperty(global, "LincheMockAPI", {
    value: Object.freeze(api),
    writable: false,
    configurable: false,
    enumerable: true
  });
})(typeof window !== "undefined" ? window : globalThis);
