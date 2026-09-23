# 第九章实验：上下文工程（ContextBuilder）

本目录用于实践 Datawhale「Hello Agents」教程第九章的上下文工程实验。

项目来源：<https://hello-agents.datawhale.cc/>

本章对应 `hello-agents==0.2.8`（当前环境实测版本）。该版本的 `hello_agents.context`
只实现了 `ContextBuilder` / `ContextConfig` / `ContextPacket` 三个对象，即
**GSSC 流水线**（Gather-Select-Structure-Compress）；模块文档里提到的
`Compactor` / `NotesManager` / `ContextObserver` 尚未随包发布。

`ContextBuilder.build()` 的四步：

| 阶段 | 行为（0.2.8 实现） |
| --- | --- |
| Gather | 收集系统指令、记忆检索结果（`MemoryTool.execute("search", ...)`）、RAG 检索结果（`RAGTool.run({"action": "search", ...})`）、最近 10 条对话历史 |
| Select | 空格分词算相关性（0.7 权重）+ 时间衰减算新近性（0.3 权重），按 `min_relevance` 过滤后按 token 预算填充 |
| Structure | 组织成 `[Role & Policies]` / `[Task]` / `[State]` / `[Evidence]` / `[Context]` / `[Output]` 六段模板 |
| Compress | 超预算时按行截断（不是摘要；`enable_compression=False` 可关闭） |

## 快速体验：ContextBuilder 构建上下文

教程示例的可运行版本位于 `demos/context_builder_demo.py`：
初始化 `MemoryTool` 与 `RAGTool` → 写入 2 条记忆（语义 + 情景）与 1 篇知识库文档 →
准备 4 轮对话历史 → `ContextBuilder.build(...)` 构建上下文并打印 →
把构建好的上下文整体交给 LLM 回答。

在 `9-experiment` 目录下运行：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.context_builder_demo --check
F:\my-hello-agent\.conda\python.exe -m demos.context_builder_demo
```

`--check` 只检查根目录 `.env` 与工具初始化（含 Qdrant / Neo4j / Embedding 连通），
不发起对话 LLM 请求。完整运行会真实写入记忆与向量、真实检索并调用 LLM
（RAG 高级检索默认开启，含 MQE + HyDE 两次查询改写调用）。

实测一次完整运行（2026-09-20，model=deepseek-v4-flash）：

- 构建耗时约 20s，上下文 628 tokens：
  `[Role & Policies] 58 | [Task] 19 | [State] 93 | [Evidence] 256 | [Context] 122 | [Output] 79`
- LLM 回答约 26s，正确引用知识库文档（相似度 0.79-0.81）与用户记忆，
  并按 `[Output]` 要求输出「结论 / 依据 / 风险与假设 / 下一步行动建议」四段。

## 教程写法差异（相对教程示例）

1. **`min_relevance`**：教程示例用 `0.2`，在 0.2.8 下会把非系统包全部过滤
   （见下节「实测发现」）。Demo 默认改为 `0.0`；传 `--min-relevance 0.2`
   可复现教程现象。
2. **RAG 命名空间**：`ContextBuilder._gather` 内部检索不带 `namespace`，
   `RAGTool._preprocess_parameters` 会把它填成 `"default"`，与第八章实验数据混用。
   `core/chapter9_tools.py` 的 `Chapter9RAGTool` 在 `run()` 里补上本章的
   命名空间（`chapter9`）与集合（`chapter9_rag`）。
3. **记忆用户**：教程用 `user123`；本实验用 `ch9_demo_user`，避免与第八章实验的
   记忆互相干扰。
4. **可复现性**：每次运行先按 `user_id` 清理本实验上次写入的记忆。框架自带的
   `remove` / `clear_all` 只作用于进程内缓存或整库清空，无法按用户清理跨进程遗留
   数据，因此 `core/chapter9_tools.py` 直接操作底层存储（Qdrant 按 user_id 过滤删除、
   SQLite 按 user_id 查询后逐条删除）。
5. **`top_k` 参数**：`ContextBuilder` 调用 RAG 检索时传的是 `{"top_k": 5}`，
   而 `RAGTool._search` 的参数名是 `limit`，`top_k` 会落进 `**kwargs` 被忽略，
   实际生效的是 `limit` 默认值 5（数值相同，无可见影响，但值得知道）。

## 实测发现：`min_relevance` 对中文查询会过滤掉全部候选包

`hello_agents/context/builder.py::_select` 用**空格分词后的词集合重叠度**计算相关性：

```python
query_tokens = set(user_query.lower().split())          # "如何优化Pandas的内存占用?" -> 1 个 token
overlap = len(query_tokens & content_tokens) / len(query_tokens)
```

中文查询没有空格，整个查询是一个 token，与任何候选包内容都不重叠，因此所有非系统包的
`relevance_score = 0`。当 `min_relevance > 0`（教程默认 `0.2`）时，
`[State]`、`[Evidence]`、`[Context]` 会被**全部过滤**，上下文只剩系统指令、任务与
输出约束——检索到的记忆与知识库内容一条都进不去。

复现方式（任一）：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.context_builder_demo --min-relevance 0.2
F:\my-hello-agent\.conda\python.exe -m demos.context_config_experiment --offline
```

英文查询（`split()` 后多个 token）不受影响，但要求词级完全相等，实际也很少命中；
在 0.2.8 上做中文上下文实验时，把 `min_relevance` 设为 `0.0` 是唯一稳妥的选择。

## 配置对比实验

`demos/context_config_experiment.py` 对同一查询、同一份数据只改 `ContextConfig`，
比较 GSSC 各阶段的实际影响。4 组配置共用一次 RAG 检索结果（缓存），避免重复的
MQE / HyDE 调用。

```powershell
# 离线桩数据：不访问网络，确定性复现 Select / Compress 行为
F:\my-hello-agent\.conda\python.exe -m demos.context_config_experiment --offline
# 真实工具：写入记忆与知识库后构建
F:\my-hello-agent\.conda\python.exe -m demos.context_config_experiment
```

真实运行结果（2026-09-20，同一次运行内对比）：

| 配置 | max_tokens | min_relevance | 压缩 | tokens | 预算 | 截断 | 出现的分区 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A 教程配置 | 3000 | 0.2 | 开 | 157 | 2400 | 否 | Role & Policies, Task, Output |
| B 修正阈值 | 3000 | 0.0 | 开 | 628 | 2400 | 否 | Role & Policies, Task, State, Evidence, Context, Output |
| C 小预算 | 150 | 0.0 | 开 | 104 | 120 | 是 | Role & Policies, Task, Output |
| D 关闭压缩 | 150 | 0.0 | 关 | 157 | 120 | 否 | Role & Policies, Task, Output |

离线模式（桩数据）结果一致，C 组被截断在 `[State]` 分区中间（真实运行里 C 组截断在
`[Output]` 分区中间——截断点取决于哪些分区进入了预算）：

| 配置 | tokens | 预算 | 截断 | 出现的分区 |
| --- | --- | --- | --- | --- |
| A 教程配置 | 157 | 2400 | 否 | Role & Policies, Task, Output |
| B 修正阈值 | 462 | 2400 | 否 | Role & Policies, Task, State, Evidence, Context, Output |
| C 小预算 | 106 | 120 | 是 | Role & Policies, Task, State |
| D 关闭压缩 | 219 | 120 | 否 | Role & Policies, Task, State, Output |

结论：

- **A → B**：相关性阈值决定候选包能否进入上下文。中文查询下 `min_relevance=0.2`
  等于关闭了记忆与 RAG 注入。
- **B → C**：预算 150（可用 120 tokens）时 Select 只放得下系统指令与任务，
  Compress 再按行截断到预算内，`[Output]` 被截断在第二行。
- **C → D**：关闭压缩后上下文可以超预算（157 > 120）。压缩是「超预算兜底」而非
  自动摘要，且按行截断，可能截在分区中间——需要高保真压缩时要自己用 LLM 做摘要。

## 长期项目助手：ProjectAssistant（§9.4.4）

教程 §9.4.4「与 ContextBuilder 的深度集成」的示例：把 NoteTool 的结构化笔记检索出来
转成 ContextPacket，注入 GSSC 上下文，让 Agent 跨轮次、跨进程保持项目连续性。
可运行版本在 `core/project_assistant.py`，演示脚本 `demos/project_assistant_demo.py`：

```powershell
# 仅检查 .env、工具初始化与笔记工作区
F:\my-hello-agent\.conda\python.exe -m demos.project_assistant_demo --check
# 完整实验：写入记忆/知识库 -> 两轮交互 -> 笔记摘要（真实 API）
F:\my-hello-agent\.conda\python.exe -m demos.project_assistant_demo
# 清空本实验的笔记工作区与该项目记忆后重新开始
F:\my-hello-agent\.conda\python.exe -m demos.project_assistant_demo --reset
# 离线确定性检查：桩 LLM / 桩记忆 / 桩 RAG + 临时笔记目录，不访问网络
F:\my-hello-agent\.conda\python.exe -m demos.project_assistant_demo --offline
# 复现教程阈值（min_relevance=0.2，观察笔记包被相关性阈值过滤）
F:\my-hello-agent\.conda\python.exe -m demos.project_assistant_demo --min-relevance 0.2
```

两轮交互（教程原文）：先汇报项目状态并 `note_as_action=True` 落成笔记，再提依赖冲突
问题——第二轮应检索到第一轮的笔记并放进 `[State]`。

数据隔离（相对教程示例的调整）：笔记写 `9-experiment/notes/<project_name>/`
（教程用 CWD 下的 `./<project>_notes`），记忆用 `user_id=ch9_<project_name>`
（教程直接用 project_name），RAG 复用本章的 `chapter9` / `chapter9_rag`
（教程另建 `./<project>_kb`）。

### 教程写法差异（0.2.8 实测）

| # | 教程写法 | 0.2.8 实际行为 | 本实现的处理 |
| --- | --- | --- | --- |
| 1 | `note_tool.run({"action": "list"/"search"})` 当 `list[dict]` 用 | 返回格式化字符串，不是列表 | 读 `notes_index` + 笔记文件，自建结构化记录 |
| 2 | 笔记键 `note_id`、字段 `updated_at` | 索引里是 `id`，且索引没有 `updated_at` | 用 `id`；`updated_at` 从笔记文件 frontmatter 解析 |
| 3 | `builder.build(..., custom_packets=...)` | 参数名是 `additional_packets` | 传 `additional_packets` |
| 4 | `metadata={"type": "note", ...}` | Structure 只认识固定类型，`note` 会被**静默丢弃** | blocker/action → `task_state`（[State]），其余 → `retrieval`（[Evidence]） |
| 5 | `relevance_score=0.75`、`token_count=len(content)//4` | `_select` 用空格分词重算相关性，写死的 0.75 无效 | 不写死；`token_count` 留 0 由 tiktoken 精确计算 |
| 6 | `self.llm.invoke(context)` | `invoke()` 接收 messages 列表 | `invoke([{"role": "user", "content": context}])` |
| 7 | `ContextConfig()` 默认 `min_relevance=0.3` | 中文查询下所有非系统包（含笔记包）相关性为 0，全被过滤 | 显式 `min_relevance=0.0`（见上文「实测发现」） |

两条保留教程语义、但值得知道的行为：

- **落笔记在回答之后**：`note_as_action=True` 时笔记写在本轮 LLM 调用之后，
  本轮回答看不到本轮笔记，只有后续轮次（或新进程）能检索到。
- **笔记检索是字面匹配**：本实现按关键词打分（英文按词、中文按 2 字滑窗）+
  blocker 优先。同义改写、跨语言提问会漏检；生产做法是把笔记也索引进向量库
  （用 RAGTool 建「笔记检索」），可以当作后续练习方向。

### 实测发现：内置 search 对中文整句恒不命中

`NoteTool._search_notes` 用 `query in note["title"].lower() or query in note["content"].lower()`
做**整串子串**匹配。教程第二轮查询「在重构业务逻辑层时,我遇到了依赖版本冲突的问题,该如何解决?」
在 0.2.8 下的返回是：

```text
📝 未找到匹配 '在重构业务逻辑层时,我遇到了依赖版本冲突的问题,该如何解决?' 的笔记
```

同一份笔记用关键词打分稳定命中（标题含「重构业务逻辑层」）。`builtin_note_search()`
保留了教程的调用路径，演示脚本每轮都会打印这组对照。

### 真实运行实测（2026-09-20，model=deepseek-flash）

| 轮次 | 检索到的笔记 | 上下文 tokens | 分区 | 耗时 |
| --- | --- | --- | --- | --- |
| 第一次（汇报状态，落笔记） | 0 条 | 627 | Role & Policies, Task, State, Evidence, Output | 42.6s |
| 第二次（依赖冲突问题） | 1 条（上一轮的 action 笔记） | 2864 | 六段全出现 | 41.8s |

- 第二轮上下文的 `[State]` 里出现 `[笔记:我们已经完成了数据模型层的重构…]`，
  LLM 的「依据」段明确引用「历史笔记：我们已经完成了数据模型层的重构…」。
- 第一次没有 `[Context]` 分区：首轮没有对话历史（Gather 只收集已有历史）。
- 跨进程验证：另起进程构造 ProjectAssistant，索引中 1 条笔记，同一查询检索到 1 条
  ——笔记的持久化确实跨进程，这是「长期助手」的关键。
- 离线模式（桩 LLM / 桩记忆 / 桩 RAG + 临时笔记目录）7/7 通过，包含：
  「交互已落成笔记」「内置 search 未命中」「关键词命中上一轮笔记」
  「笔记进入 [State]」「min_relevance=0.2 时笔记与检索结果被全部过滤」。

## 代码库维护助手：CodebaseMaintainer（长程智能体综合示例）

教程的「代码库维护助手」（长程智能体示例）把 ContextBuilder + NoteTool +
TerminalTool + MemoryTool 组合成跨会话的代码库维护任务管理。可运行版本在
`core/codebase_maintainer.py`，演示脚本 `demos/codebase_maintainer_demo.py`：

```powershell
# 仅检查 .env、工具初始化与三条扫描命令，不发起对话
F:\my-hello-agent\.conda\python.exe -m demos.codebase_maintainer_demo --check
# 完整实验：explore / analyze / plan 三轮交互 + 笔记 + 报告（真实 API）
F:\my-hello-agent\.conda\python.exe -m demos.codebase_maintainer_demo --reset
# 清空本实验的笔记工作区与该项目的记忆后重新开始（可单独执行）
F:\my-hello-agent\.conda\python.exe -m demos.codebase_maintainer_demo --reset
# 离线确定性检查：桩 LLM / 桩记忆 / 桩终端 + 临时笔记目录，不访问网络
F:\my-hello-agent\.conda\python.exe -m demos.codebase_maintainer_demo --offline
# 复现教程阈值（min_relevance=0.2，观察预处理包与笔记被相关性阈值过滤）
F:\my-hello-agent\.conda\python.exe -m demos.codebase_maintainer_demo --min-relevance 0.2
# 指定被维护的代码库目录（默认项目根目录）
F:\my-hello-agent\.conda\python.exe -m demos.codebase_maintainer_demo --codebase F:\my-hello-agent\9-experiment
```

数据隔离（相对教程示例的调整）：笔记写 `9-experiment/notes/my_hello_agent/`
（教程用 CWD 下的 `./<project>_notes`），记忆用 `user_id=ch9_my_hello_agent`，
会话报告写 `9-experiment/reports/`（教程写到 CWD）。本示例不使用 RAG。

### 教程写法差异（0.2.8 实测）

| # | 教程写法 | 0.2.8 实际行为 | 本实现的处理 |
| --- | --- | --- | --- |
| 1 | `builder.build(..., custom_packets=...)` | 参数名是 `additional_packets` | 传 `additional_packets` |
| 2 | `self.llm.invoke(context)` | `invoke()` 接收 messages 列表 | `invoke([{"role": "user", "content": context}])` |
| 3 | `note_tool.run(...)` 当 `list[dict]` 用 | 返回格式化字符串：`_retrieve_relevant_notes` 的合并抛 AttributeError 并被自身 except 吞掉（检索恒为空）；plan 模式 `note['title']` 直接 TypeError | 读 `notes_index` + 解析笔记文件（复用 ProjectAssistant 的关键词打分） |
| 4 | `metadata={"type": "note" / "code_structure" / "code_analysis" / "task_plan"}` | Structure 只认识固定类型，未列出的包被静默丢弃 | 笔记 → `task_state`/`retrieval`，终端结果 → `tool_result`，任务列表 → `task_state` |
| 5 | `relevance_score=0.75` 等、`token_count=len(content)//4` | 相关性被 `_select` 用空格分词重算覆盖；`len//4` 对中文低估约 4 倍 | 不写死；`token_count` 留 0 由 tiktoken 计算 |
| 6 | `min_relevance=0.2` | 中文查询下非系统包全被过滤 | 默认 `0.0`（同 ProjectAssistant） |
| 7 | `find` / `grep` / `head` / `wc` 组合命令 | Windows cmd.exe 下不可用；且 TerminalTool 按 UTF-8 严格解码 GBK 输出，读取线程崩溃、输出整体丢失 | 命令按平台生成：Windows 用 `dir /s /b *.py` + `core/scan_codebase.py`（PATH python，仅标准库）；POSIX 保留教程命令。`Chapter9TerminalTool` 按 UTF-8 → 本地编码 → GBK 依次解码 |
| 8 | 自动笔记按回复关键词触发、if/elif 顺序 | 中文回复几乎必然命中「问题」；计划分支不可达 | 改为按用户输入分类，blocker / action 两个分支都可达 |
| 9 | 报告写到 CWD | 污染运行目录 | 写到 `9-experiment/reports/`（可传入目录） |

### Windows 实测：教程命令的失败与替代

同一台机器（cmd.exe，`Chapter9TerminalTool` 对照）：

```text
find . -type f -name '*.py' | head -n 20
  0.2.8 原版 TerminalTool：'⚠️ 命令返回码: 255'（输出整体丢失，读取线程 UnicodeDecodeError）
  Chapter9TerminalTool  ：'找不到文件 - '*.py' / 'head' 不是内部或外部命令…'（错误信息可见）

dir /s /b *.py（本实现，explore）
  → 仓库根目录 27189 行原始输出，过滤 .conda/.git 等后 95 个 .py，耗时约 1-2s

python core/scan_codebase.py loc / todo（本实现，analyze）
  → 'files: 95 / lines: 11811'、TODO 匹配 10 条
```

`scan_codebase.py` 只依赖标准库，用 PATH 上的 python 执行（本机 3.14.2）。
TODO 扫描与教程 grep 一样是纯子串匹配，会命中文档/字符串里的 TODO 字样
（本次 10 条全部是扫描器与演示自身的文本，属于预期噪声，模型在回答里识别了这一点）。

### 离线检查（13 项）

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.codebase_maintainer_demo --offline
```

覆盖：explore/auto 预处理包映射为 `tool_result` 并进入 `[Evidence]`（.conda 行被过滤）、
analyze 统计与 TODO 注入、内置 search 未命中 vs 关键词命中 blocker 笔记、
笔记进入 `[State]`、plan 任务列表加载（教程此处会崩溃）、自动笔记两个分支可达、
`min_relevance=0.2` 复现过滤、报告生成与历史更新。

### 真实运行实测（2026-09-20，model=deepseek-flash）

| 轮次 | 预处理包 | 检索笔记 | 上下文 tokens | 分区 | 耗时 |
| --- | --- | --- | --- | --- | --- |
| explore（整体结构） | tool_result | 0 条 | 623 | Role & Policies, Task, Evidence, Output | 24.1s |
| analyze（代码质量） | tool_result | 0 条 | 2813 | Role & Policies, Task, Evidence, Context, Output | 31.4s |
| plan（规划下一步） | task_state | 1 条（task_state） | 337 | Role & Policies, Task, State, Output | 23.8s |

- explore 轮：模型基于 `[代码库结构]`（95 个文件、显示前 20 个）给出按实验目录分层
  与演进路径的分析；结构包确实进入了上下文。
- analyze 轮：`[代码统计]`（95 files / 11811 lines）与 `[待办事项]`（10 条匹配）注入；
  模型指出 10 条 TODO 全部是扫描器/演示自身文本（见上文说明）。
- plan 轮：`[当前任务]` 列表 + 关键词检索到的 task_state 笔记进入 `[State]`，
  回答引用了笔记 ID；本轮回答后自动落了一条 action 笔记（落笔记在回答之后，
  本轮上下文看不到它）。
- 报告：`reports/maintainer_report_session_20260920_224946.json`，
  `activity = {'commands_executed': 3, 'notes_created': 2, 'issues_found': 0}`。
- 观察：explore 轮模型自称「已记录到笔记」，实际系统只在用户输入命中
  blocker/action 触发词时才自动落笔记（`_postprocess_response`）；
  模型的自述不等于系统行为，读回答时需要区分。

## 环境

使用项目内 Conda 环境 `F:\my-hello-agent\.conda`。配置统一读取项目根目录 `.env`，
不在源码、测试或日志中写入密钥。

需要的变量（与第八章相同）：

- LLM：`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_ID`
- Qdrant：`QDRANT_URL`、`QDRANT_API_KEY`、`QDRANT_COLLECTION`、`QDRANT_VECTOR_SIZE`
- Neo4j：`NEO4J_URI`、`NEO4J_USERNAME`、`NEO4J_PASSWORD`、`NEO4J_DATABASE`
- Embedding：`EMBED_MODEL_TYPE`、`EMBED_API_KEY`、`EMBED_BASE_URL`

说明：

- 语义记忆依赖 Neo4j（`SemanticMemory` 初始化即连接），连不上时 `MemoryTool`
  会直接初始化失败，不像第八章 PDF 助手那样降级；本实验按「必须可用」处理。
- 本章 RAG 数据写入独立的 Qdrant 集合 `chapter9_rag`（命名空间 `chapter9`），
  与第八章的 `rag_knowledge_base` / `default` 隔离。
- 本环境将 `qdrant-client` 钉在 `1.15.1`，Qdrant Cloud 服务端为 1.19，
  初始化时会打印版本不匹配告警，不影响本章读写（与第八章一致）。

## 目录结构

```text
9-experiment/
├── README.md
├── core/config.py                    # 读取项目根目录 .env 与目录常量
├── core/chapter9_tools.py            # Chapter9RAGTool / Chapter9TerminalTool + 记忆清理等辅助
├── core/project_assistant.py         # §9.4.4 长期项目助手（笔记 → ContextPacket）
├── core/codebase_maintainer.py       # 代码库维护助手（长程智能体综合示例）
├── core/scan_codebase.py             # 标准库代码扫描（Windows 下供 TerminalTool 调用）
├── demos/context_builder_demo.py     # 教程示例的可运行版本（构建 + LLM 回答）
├── demos/context_config_experiment.py # ContextConfig 对比实验（含 --offline）
├── demos/project_assistant_demo.py   # ProjectAssistant 演示（含 --offline / --reset）
├── demos/codebase_maintainer_demo.py # CodebaseMaintainer 演示（含 --check / --offline / --reset）
├── knowledge_base/pandas_memory_optimization.md  # RAG 知识库文档
├── notes/                            # NoteTool 笔记工作区（已 gitignore）
├── memory_data/                      # 本地 SQLite 情景记忆（已 gitignore）
└── reports/                          # CodebaseMaintainer 会话报告（已 gitignore）
```

## 验证记录

- 2026-09-20：`--check` 通过（Qdrant / Neo4j 云服务连通，Embedding 1024 维，
  RAG 集合 `chapter9_rag` 创建成功）。
- 2026-09-20：完整运行 `demos.context_builder_demo` 真实 API 通过（见上文实测数据）。
- 2026-09-20：`demos.context_config_experiment` 真实与离线两种模式均通过，
  结果与预期一致（见上文对比表）。
- 2026-09-20：`demos.project_assistant_demo --check` 通过（工具初始化，
  笔记工作区 `notes/data_pipeline_refactoring/` 创建成功）。
- 2026-09-20：`demos.project_assistant_demo` 真实 API 通过（两轮交互 + 笔记摘要，
  数据见上文「真实运行实测」）。
- 2026-09-20：`demos.project_assistant_demo --offline` 7/7 通过；
  跨进程笔记检索单独验证通过（新进程检索到上一进程写入的笔记）。
- 2026-09-20：`demos.project_assistant_demo --reset` 后重复运行，结果与首次一致
  （第二轮 2832 tokens、六段分区、同样引用上一轮笔记），重置路径可复现。
- 2026-09-20：`demos.codebase_maintainer_demo --check` 通过（工具初始化 + 三条扫描命令：
  结构 95 个 .py、统计 11811 行、TODO 10 条）。
- 2026-09-20：`demos.codebase_maintainer_demo --offline` 13/13 通过（含教程阈值复现）。
- 2026-09-20：`demos.codebase_maintainer_demo --reset` 真实 API 通过
  （三轮交互 + 自动笔记 + 报告，数据见上文「真实运行实测」）。
- 2026-09-20：`demos.project_assistant_demo --offline` 回归 7/7 通过
  （`chapter9_tools.py` 增加 `Chapter9TerminalTool` 后无影响）。
