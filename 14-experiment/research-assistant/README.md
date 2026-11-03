# 自己的深度研究智能体

基于 Datawhale「Hello Agents」第十四章学习实践：<https://hello-agents.datawhale.cc/>。
参考第十三章 `trip-assistant/demos/backend/app/` 布局，独立于本章官方参考项目。

当前包含三个 Agent、搜索服务、顺序研究流程、FastAPI SSE接口及Vue全屏研究工作台。

| 文件（相对本目录） | 用途 |
| --- | --- |
| `demos/backend/app/agents/prompts.py` | 三个角色的提示词 |
| `demos/backend/app/agents/research_agents.py` | PlanningService、SummarizationService、ReportingService |
| `demos/backend/app/agents/tool_aware_agent.py` | 自定义 ToolAwareSimpleAgent 和工具监听接口 |
| `demos/backend/app/agents/deep_research_agent.py` | 创建三个角色，顺序执行研究并转发事件 |
| `demos/backend/app/services/search_service.py` | 真实搜索，规范化及去重来源 |
| `demos/backend/app/config.py` | 搜索后端、结果数量及单来源预算配置 |
| `demos/backend/app/services/source_processing.py` | URL去重和摘要长度估算限制 |
| `demos/backend/app/services/notes_service.py` | NoteTool持久化研究计划、任务资料与总结、最终报告 |
| `demos/backend/app/services/tool_registry.py` | ResearchToolManager统一注册search与note工具 |
| `demos/backend/app/models/schemas.py` | TodoItem、SummaryState |
| `demos/backend/app/services/llm_service.py` | 从根目录 .env 创建共享 HelloAgentsLLM |
| `tests/test_real_agents.py` | 三个角色的真实模型验证 |
| `demos/backend/app/api/main.py` | POST研究端点、SSE流和后台线程桥接 |
| `demos/frontend/src/components/ResearchModal.vue` | 响应式全屏研究对话框 |
| `demos/frontend/src/composables/useResearch.ts` | POST流式读取、进度与任务状态、停止及连接清理 |
| `demos/frontend/src/components/MarkdownContent.vue` | marked与DOMPurify安全渲染Markdown |

## 启动自己的研究工作台

在项目根目录运行后端（复用第十四章环境）：

```powershell
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m uvicorn app.api.main:app --app-dir ./14-experiment/research-assistant/demos/backend --host 127.0.0.1 --port 8003
```

另开终端运行前端：

```powershell
cd 14-experiment/research-assistant/demos/frontend
npm.cmd ci
npm.cmd run dev
```

前端：<http://127.0.0.1:5177/>；接口文档：<http://127.0.0.1:8003/docs>；
健康检查：<http://127.0.0.1:8003/healthz>。Vite将 `/api` 请求代理到8003，浏览器不接触密钥。
前端可选择搜索服务，初始选择Tavily；需要在根目录 `.env` 配置对应搜索服务。
后端模型仍读取根目录现有的 `LLM_API_KEY/LLM_BASE_URL/LLM_MODEL_ID`。
依赖使用现有环境中的 `fastapi`、`uvicorn`、`hello-agents`、`requests`、`python-dotenv`、`pydantic`。

界面包含主题输入与示例问题、任务路径、实时阶段进度、逐任务总结、最终报告与Markdown下载。
桌面使用左右分栏；手机切换为横向任务列表及独立滚动的阅读区。
原生 `dialog.showModal()` 提供焦点约束和Escape关闭；关闭只收起窗口，可从首页重新打开，研究继续。
“停止研究”断开流连接，后端在当前网络调用完成后的阶段边界停止，之前保存的笔记保留。
刷新或关闭页面会断开当前连接，前端未实现跨刷新恢复；笔记文件可在本地查看。
Markdown使用GFM和换行支持，DOMPurify清理HTML，不执行资料中的脚本；来源链接安全地在新窗口打开。

### 流式接口约定

`POST /api/research`，JSON请求体为 `{"topic":"研究主题","search_api":"tavily"}`。
主题去除首尾空白后不能为空，最多1000字符；搜索后端可省略以使用后端配置。
返回 `text/event-stream`，前端使用 `fetch` 读取POST响应，处理UTF-8分块和SSE帧边界，
不使用只能发送GET的 `EventSource`。同步Agent流程在独立线程执行，不对同步服务错误地使用 `await`。

| 事件 | 含义 |
| --- | --- |
| `progress` | `stage/percentage/text`，阶段与任务完成比例；不是模型生成token进度 |
| `plan` | `data` 为任务字典列表 |
| `task_started` / `task_completed` | `task_id`，任务开始及已保存总结的完成状态 |
| `task_summary` | `task_id/summary/source_urls`，阶段总结与来源 |
| `note_saved` | 笔记类型及ID，用于更新保存数量 |
| `tool_call` | Agent和工具名，不向浏览器广播参数或原始结果 |
| `report` | `data` 为最终Markdown报告 |
| `completed` | 独立的成功终止事件；前端结束加载并清理连接 |
| `error` | 脱敏错误消息，停止加载并提供重试入口 |

后端约每10秒发送SSE注释心跳；最多同时处理2份研究，忙碌时返回429。
前端识别连接提前结束、HTTP错误及流内错误，不将报告生成前的断线标记为成功。
前端构建命令：`npm.cmd run build`。

```powershell
# 确定性协议与校验补充测试
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_http_stream.py -v
# 先启动8003后端，再进行真实HTTP、搜索和模型测试
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_real_http_research.py -v
```

HTTP测试产物保存在 `.local/research-assistant/http/`；浏览器验证截图保存在
`.local/research-assistant/ui/`（均位于第十四章目录下，已Git忽略）。

三个服务各自持有一个本项目的 ToolAwareSimpleAgent，均支持可选的
`tool_call_listener` 和 `tool_registry`。单独创建服务时按传入注册表使用；
`DeepResearchAgent` 默认自动注册 `search` 和 `note`，供三个角色共用。
每次调用清除历史，同一实例不用于并发请求。
规划严格校验3-5个任务和非空字段，支持纯JSON、JSON代码块或说明文字中的单个JSON数组。
总结接收 `title/url/snippet` 字典列表，由调用者提供资料；使用
`[T1-S1]` 等任务范围内唯一编号，避免不同任务的 `[1]` 混淆。
引用保真目前依赖提示词和真实测试，尚无运行时事实或引用校验器。

在项目根目录使用：

```powershell
$env:PYTHONPATH = "$PWD/14-experiment/research-assistant/demos/backend"
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_real_agents.py -v
```

调用示例：

```python
from app.agents.research_agents import PlanningService, SummarizationService, ReportingService
from app.models.schemas import SummaryState
from app.services.llm_service import create_llm

llm = create_llm()
tasks = PlanningService(llm).plan_todo_list(SummaryState(research_topic="你的研究主题"))
# search_results 由后续搜索服务提供，每项包含 title、url、snippet。
# summary, source_urls = SummarizationService(llm).summarize_task(tasks[0], search_results)
# report = ReportingService(llm).generate_report("你的研究主题", [(tasks[0], summary, source_urls)])
```

依赖复用第十四章 `.venv` 中的 `hello-agents`、`python-dotenv`，Windows 的时区数据需要 `tzdata`。
测试将实际调用根目录 `.env` 中的模型，使用固定的Python官方文档资料片段；不验证搜索能力或完整研究质量。

## 任务规划服务

`PlanningService` 保留 `plan_todo_list(SummaryState) -> list[TodoItem]` 接口，
接收共享模型、工具监听器和可选注册表；以Asia/Shanghai时区获取 `YYYY年MM月DD日` 日期。
主题不能空白，规划成功后更新 `state.todo_items`，每次调用前后清除Agent历史。

解析使用 `JSONDecoder.raw_decode` 提取完整JSON数组，避免贪婪正则误处理嵌套括号和字符串。
若响应中有多个独立数组则拒绝猜测；字段缺失、空白、非字符串或任务数量不在3-5内时报错。
最终仅保留 `title/intent/query`，按顺序分配从1开始的任务ID。

```python
planner = PlanningService(llm)
state = SummaryState(research_topic='Python asyncio工程实践')
tasks = planner.plan_todo_list(state)
evaluation = planner.evaluate_plan(tasks)
# {'score': 100, 'suggestions': []}，具体分数取决于规划内容
```

`evaluate_plan` 从100分开始：少于3项扣20，多于5项扣10；每项空白字段扣10，
过短查询扣10，重复标题或查询扣10，最低0分。
查询若含至少6个汉字或至少2个英文/数字词块，不因长度扣分。
它是规则式提示，不代表对任务逻辑、主题覆盖或检索效果的语义评估，也不自动触发重规划。

```powershell
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_planning_service.py -v
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_real_planning.py -v
```

## 总结与报告的来源传递

`SummarizationService.summarize_task(task, search_results)` 返回 `(summary, source_urls)`。
URL列表按输入搜索资料的顺序直接提取，不依赖模型生成；顺序与 `[T任务号-S来源号]` 一致。
`ReportingService.generate_report(topic, task_summaries)` 接收
`[(task, summary, source_urls), ...]`，将来源编号和URL显式写入每项任务的报告上下文，
要求最终参考文献按任务分组。研究流程与对应真实API测试已更新为该接口。

三个详细提示词已恢复用户最初提供的任务说明、字段要求、示例和约束；
总结与报告中的引用示例适配为跨任务唯一编号，并补充资料只作为数据的执行约定。
完整文本在 `agents/prompts.py`，由服务格式化后实际传入Agent。

## 工具调用监听

自定义类直接继承 `SimpleAgent`，使用当前库的 `_parse_tool_parameters` 接口，
再由父类实际执行工具。工具只执行一次；执行后回调收到
`agent_name/tool_name/parsed_parameters/result`，其中 `result` 为父类格式化的结果字符串。
工具失败、工具不存在及未配置注册表时，也会通知监听器；监听器异常不改变工具返回结果。
目前使用 `SimpleAgent.run` 的非流式调用与解析能力，未扩展流式工具调用。

```python
from hello_agents.tools import ToolRegistry
from app.agents.deep_research_agent import DeepResearchAgent

registry = ToolRegistry()
# registry.register_tool(your_tool)

def on_event(event):
    # 可接日志或后续前端事件队列；需要时由调用方脱敏参数和结果。
    if event['type'] == 'tool_call':
        print(event['type'], event['agent'], event['tool'])

research = DeepResearchAgent(tool_registry=registry, event_listener=on_event)
# 三个服务共用模型、注册表和同一个工具监听器：
# research.planner.plan_todo_list(state)
# research.summarizer.summarize_task(task, search_results)
# research.reporter.generate_report(topic, task_summaries)
```

统一事件字段为 `type="tool_call"`、`agent`、`tool`、`parameters`、`result`。
事件只通过回调交付，不默认打印或长期保存参数与结果。
模型自主工具调用才产生 `tool_call`；流程直接调用搜索服务，不伪装为模型工具事件。

```powershell
# 确定性补充测试：实际执行本地演示工具，不调用模型
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_tool_listener.py -v
# 真实模型驱动工具调用：三个角色分别调用本地演示工具，验证统一事件
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_real_tool_listener.py -v
```

## ToolRegistry工具管理

`DeepResearchAgent` 默认通过 `ResearchToolManager` 创建一份 `ToolRegistry`，
将同一份注册表传给三个 `ToolAwareSimpleAgent`：

- `search`：`ResearchSearchTool` 适配已有 `SearchService`，底层复用SDK的 `SearchTool`。
  参数为 `query`，返回资料JSON数组；搜索后端、去重、条数和摘要预算与研究流程一致。
  搜索服务首次使用时初始化。选择 `SearchAPI.ADVANCED` 可使用SDK的hybrid回退逻辑。
- `note`：注册当前 `NotesService.note_tool` 的真实实例，名称保持 `note`，不展开为多个子工具。
  模型写入和流程持久化共用一个索引；后续 `run()` 切换会话时更新同一注册表中的note实例。

```python
from app.agents.deep_research_agent import DeepResearchAgent
from app.config import Configuration, SearchAPI

research = DeepResearchAgent(config=Configuration(search_api=SearchAPI.ADVANCED))
print(research.tool_registry.list_tools())  # ['search', 'note']
# 注册额外工具：research.tool_registry.register_tool(your_tool)
# 取回当前笔记工具：research.tool_registry.get_tool('note')
# 运行：report = research.run('研究主题')
```

也可直接构建管理器并把注册表传给单个Agent：

```python
from app.services.tool_registry import ResearchToolManager
from app.agents.tool_aware_agent import ToolAwareSimpleAgent
from app.services.llm_service import create_llm

tools = ResearchToolManager(Configuration.from_env())
agent = ToolAwareSimpleAgent(
    name='研究助手', system_prompt='你是一个研究助手',
    llm=create_llm(), tool_registry=tools.registry,
)
```

显式传入 `DeepResearchAgent(tool_registry=your_registry)` 时原样使用，不自动覆盖或添加工具。
此模式的工具配置由调用方管理；流程自带的搜索和笔记服务仍按已有配置独立执行。

```powershell
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_tool_registry.py -v
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_real_registry.py -v
```

## 顺序执行完整研究

```python
from app.agents.deep_research_agent import DeepResearchAgent

def on_event(event):
    if event['type'] == 'status':
        print(event['message'])

report = DeepResearchAgent(event_listener=on_event).run('Python asyncio 的适用场景和限制')
```

`run(topic)` 按规划→逐任务搜索与总结→报告顺序执行并返回Markdown字符串。
内部将主题包装为 `SummaryState` 调用已有规划接口。
事件包含 `status`、`tasks`、逐任务 `task_completed` 和最终 `report`，另有笔记目录及保存事件；
`tasks` 使用字典列表，便于JSON序列化。流程失败时发出 `error` 并继续抛出异常，
不将部分任务或失败搜索包装为完整报告。

搜索由 `Configuration.search_api` 显式选择，默认DuckDuckGo（不再根据Tavily Key自动切换）。
支持 `tavily`、`duckduckgo`、`perplexity`、`searxng`、`advanced`。
`advanced` 使用库内回退顺序：Tavily→SerpApi→DuckDuckGo；并非同时查询所有后端。
Tavily和Perplexity分别读取根目录 `.env` 的 `TAVILY_API_KEY` 和 `PERPLEXITY_API_KEY`。
SearXNG须提供可用实例并支持JSON搜索；实例URL从配置读取，不修改进程环境。
每任务默认最多5条资料，仅检索摘要，不声称读取了网页全文。
无有效搜索资料时停止研究。可通过构造参数 `search_service` 注入其他兼容搜索服务。
实例不支持并发运行，单次运行状态局部保存，不混入此前任务。

```python
from app.config import Configuration, SearchAPI
from app.agents.deep_research_agent import DeepResearchAgent

config = Configuration(
    search_api=SearchAPI.TAVILY,
    max_search_results=5,
    max_tokens_per_source=2000,
)
research = DeepResearchAgent(config=config)
# report = research.run('研究主题')
```

不传配置时，从根目录 `.env` 读取可选的 `SEARCH_API`、`MAX_SEARCH_RESULTS`、
`MAX_TOKENS_PER_SOURCE`、`SEARXNG_URL`，未设置时使用模型默认值。
来源先规范化并过滤无效项，再按URL精确去重（保留首次出现顺序），最后限制条数和摘要长度。
默认每来源2000个估算token，即8000字符；截断以 `...` 结尾并计入字符预算。
此为1 token约4字符的粗略估算，不保证满足模型实际token限制，尤其是中文。
处理函数返回新字典，不修改调用者资料。

```powershell
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_real_research.py -v
```

此测试实际调用搜索与模型，将报告及事件写入Git忽略的
`14-experiment/.local/research-assistant/last-report.md` 和 `last-events.json`。

## 搜索调度与磁盘缓存

```python
from app.services.search_service import SearchService

search = SearchService(config)
sources = search.search('Python asyncio', max_results=5, use_cache=True)
fresh_sources = search.search('Python asyncio', max_results=5, use_cache=False)
```

`max_results` 不传时使用配置中的数量；单次覆盖不修改服务默认值。
默认缓存目录为Git忽略的 `14-experiment/.local/research-assistant/cache/search/`。
可设置 `Configuration.search_cache_dir`、`search_cache_ttl_seconds`，或根 `.env` 的
`SEARCH_CACHE_DIR`、`SEARCH_CACHE_TTL_SECONDS`；默认有效期86400秒。
TTL为0时不读取旧缓存；`use_cache=False` 同时跳过读取和写入。

SHA256缓存键涵盖查询、结果数量、后端、单来源预算、SearXNG地址及格式版本，不包含凭证。
缓存保存去重和限长后的结果，命中时校验结构、URL和预算；损坏或过期时重新搜索。
写入使用临时文件原子替换；缓存写入失败不影响已取得的真实搜索结果。
搜索服务失败或没有有效来源时仍抛出异常，不保存失败结果，避免继续生成无资料报告。
日志只记录结果数量和缓存状态，不输出查询、密钥或供应商原始异常。

```powershell
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_search_cache.py -v
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_real_search_cache.py -v
```

## NoteTool持久化进度

每次 `run()` 在 `Configuration.notes_workspace` 下新建独立研究目录，默认位置：
`14-experiment/.local/research-assistant/notes/<run-id>/`，在Git忽略范围内。
可通过配置或根目录 `.env` 的 `NOTES_WORKSPACE` 设置其他目录。

流程分别通过 NoteTool 创建研究计划、每个任务的资料及总结、最终报告笔记。
任务笔记包含标题、意图、查询、搜索结果原文摘要和URL，以及带 `[T1-S1]` 等编号的总结。
任务总结成功落盘后才发出 `task_completed`；最终报告保存后才发出 `report`。
写入失败时流程抛出异常，之前成功保存的笔记保留，可在重启后读取。
当前持久化支持事后读取进度，尚未实现自动断点续跑；重新运行会创建新的研究目录。

新增事件：`notes_workspace` 的 `path` 为本次目录；`note_saved` 带 `kind`、
`note_id`，任务总结还带 `task_id`。`kind` 为 `plan`、`task_summary` 或 `report`。
这是流程直接调用NoteTool的保存事件，不会伪装为模型自主发出的 `tool_call`。

```python
from app.services.notes_service import NotesService

notes = NotesService(workspace='你的研究目录')
note_id = notes.save_task_summary(task, search_results, summary)
content = NotesService(workspace='你的研究目录').read_note(note_id)
```

服务检查 NoteTool 的成功结果并返回笔记ID；NoteTool自身维护Markdown和索引文件。
同一目录不并发共享多个写入实例。

```powershell
& ./14-experiment/.venv/Scripts/python.exe -X utf8 -m unittest discover -s 14-experiment/research-assistant/tests -p test_notes_service.py -v
```

## 验证记录

- 2026-11-03（前端与SSE）：Vue/TypeScript生产构建通过，npm audit无已知漏洞，3项确定性SSE测试通过（输入校验、进度映射、线程事件与错误脱敏）。真实HTTP→Tavily→模型完整SSE测试通过（56.192秒），验证3个任务总结、单调进度、最终报告及completed事件。另在浏览器完成真实研究，验证100%状态、5条笔记、任务总结、来源链接、报告自动切换、Markdown下载、Escape收起/重开和停止操作。1440×900桌面及390×844手机布局已检查。
- 2026-11-03（来源传递与搜索缓存）：5项搜索处理/缓存补充测试及3项规划解析/评分测试通过。真实Tavily首次搜索并落盘、二次命中且仅执行一次网络搜索验证通过（2.750秒）；完整真实搜索与模型研究测试通过（58.843秒），覆盖新总结/报告来源接口、完整提示词、任务与报告笔记持久化。
- 2026-11-03（任务规划完善）：3项确定性测试通过，覆盖说明文字和代码块JSON提取、括号和引号、歧义数组拒绝、字段类型、任务数量及中英文查询评分。真实模型规划测试通过（7.803秒），生成5个合法任务，规则评分100分；状态更新和调用后历史清理验证通过。规则分数不代表语义质量结论。语法编译通过。
- 2026-11-03（ToolRegistry）：2项确定性测试通过，覆盖共享注册表、search适配、note会话切换及外部注册表兼容。真实模型通过注册表调用Tavily搜索和NoteTool测试通过（9.381秒），笔记重新打开读取成功。完整真实研究回归测试通过（84.665秒），完成3项任务和报告及5条流程笔记。语法编译通过。
- 2026-11-03（NoteTool持久化）：2项本地真实NoteTool测试通过，验证落盘、重新打开读取及创建失败处理。真实Tavily搜索与真实模型完整研究测试通过（130.309秒）：完成3个任务，保存5条笔记（计划、3条任务总结、报告），用新服务实例重新读取并验证内容与来源引用。语法编译通过。
- 2026-11-03（搜索优化）：3项确定性测试通过，覆盖后端枚举与配置校验、URL去重、预算边界、输入不变及无有效结果错误。真实Tavily搜索→真实模型总结测试通过（12.651秒）：3条有效且不重复来源，每条摘要不超过800字符，保留引用与来源URL。其他后端未在本次进行联网验证。
- 2026-11-03（完整研究流程）：真实Tavily搜索与真实模型端到端测试通过，117.446秒，完成3个任务的搜索、总结及最终报告；任务事件顺序、JSON序列化、报告引用标记和来源链接验证通过。既有4项工具监听确定性测试及语法编译通过。
- 2026-11-03：真实 API 测试通过（1项，57.27秒）：规划产生3-5个合法任务，总结和报告均保留来源编号及原始URL。语法编译通过。
- 2026-11-03（工具监听扩展后）：4项确定性测试通过。真实 API 测试未完成：重跑原有三角色测试及新增模型工具测试时，供应商返回 `404 model_not_found`，根配置中的 `deepseek-flash` 不受当前分组支持；未修改根目录配置。此前成功记录不代表本次真实验证成功。
- 2026-11-03（重新测试）：两项真实 API 测试全部通过，共38.224秒。规划、总结和报告的实际模型调用及引用传递通过；三个角色分别由真实模型触发本地 `research_lookup` 工具，参数、执行结果和统一事件均通过验证。本次未修改模型配置。工具为固定资料演示工具，此验证不包含互联网搜索。
