# 第十章实验：智能体通信协议（MCP / A2A / ANP）

## 目录结构

- `mcp/demos/`：MCP 客户端、服务端与传输示例。
- `a2a/demos/`、`a2a/tests/`：A2A 示例与测试。
- `anp/demos/`、`anp/tests/`：ANP 服务发现、组网、调度及负载均衡。
- `common/demos/`：跨协议快速体验。

以下命令默认在项目根目录执行。

## 自定义天气 MCP 服务

来源：<https://hello-agents.datawhale.cc/>。三个工具通过 stdio 提供服务，由客户端启动子进程，无需另开终端启动服务器。

- `mcp/demos/weather_mcp_server.py`：`get_weather`、`list_supported_cities`、`get_server_info`。
- `mcp/demos/weather_assistant.py`：展开 MCP 子工具并注册到 `SimpleAgent`，固定读取根目录 `.env` 的 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_ID`。
- `mcp/tests/test_weather_mcp_server.py`：真实 stdio 通信及北京、深圳的真实天气请求；返回 `error` 时测试失败并以非零状态退出。

```powershell
.\.conda\python.exe -X utf8 10-experiment\mcp\tests\test_weather_mcp_server.py
.\.conda\python.exe -X utf8 10-experiment\mcp\demos\weather_assistant.py demo
.\.conda\python.exe -X utf8 10-experiment\mcp\demos\weather_assistant.py
```

交互模式输入 `quit` / `exit` 退出。子进程使用 `sys.executable -X utf8`，不依赖系统 `python` 或教程中的 `HelloAgents` 相对路径。

天气工具不需要 API Key；Agent 会调用真实模型并产生 API 用量。内置 12 个中文城市映射不是上游支持城市的完整列表。默认使用 wttr.in，失败后通过 Open-Meteo 地理编码及当前天气接口查询，每个天气源各尝试一次，无应用层重试。备用源明确标注 `source`、`data_type`、`timezone`、`fallback_reason` 和 `provider_attempts`；它返回当前模型天气而非气象站实测，未提供能见度时 `visibility=null`。地理编码只取首个匹配，重名城市应核对 `resolved_location`。返回当前天气，不是全天预报；包含上游时间、UTC 查询时间及单位，避免将本机查询时间误当作数据时间。

2026-11-02 验证记录：工具发现、服务器信息、城市列表及空城市错误分支通过；根目录 `.env` 配置检查通过，真实模型已调用 `mcp_get_weather` 并说明查询失败。**真实天气 API 测试未完成**：北京、深圳请求均遇到 `SSLError / UNEXPECTED_EOF_WHILE_READING`，未取得天气数据，不能视为天气查询成功。未关闭 TLS 证书校验，也未使用 Mock 天气代替。

同日修复后复测：wttr.in 仍出现 SSL 错误，Open-Meteo 备用源成功返回北京 8.3°C、深圳 24.5°C（仅为本次数据快照）；真实 MCP 测试全部通过。读取根目录 `.env` 的真实模型演示已完成天气工具调用，并回答北京天气、备用源和模型数据性质。`AuthlibDeprecationWarning` 是依赖弃用提醒，与天气请求失败无直接关系；`Max retries exceeded` 也不能证明应用代码重试了三次。

## ANP 智能任务调度（节点推荐）

在当前项目根目录运行：

```powershell
.\.conda\python.exe -X utf8 10-experiment\anp\demos\anp_task_scheduler.py
.\.conda\python.exe -X utf8 10-experiment\anp\demos\anp_task_scheduler.py --task "训练图像分类模型" --requires-gpu
.\.conda\python.exe -X utf8 10-experiment\anp\tests\test_anp_task_scheduler.py
```

- 注册 10 个计算节点，默认随机种子 42；可用 `--seed` 调整资源快照。
- `SimpleAgent` 使用根目录 `.env` 的真实模型配置，通过 `ANPTool` 查询节点，逐个分析后返回 JSON 推荐和理由。每个任务清空历史，记录实际工具调用。
- 校验工具确实被调用、10 个节点全部被分析、节点 ID 真实存在及 GPU 硬约束；无符合条件节点时允许返回 null。高内存和轻量任务的偏好由模型判断，当前不保证数学最优，也不校验自然语言分析的每个事实。
- 自定义 GPU 任务应显式添加 `--requires-gpu`；自然语言描述不作为程序层约束解析器。未量化的“大型模型”不能据此保证显存或训练资源足够。
- 该示例实现服务发现和调度推荐，`http://nodeN:8000` 是示例端点。没有启动远程计算服务、提交任务、资源预留、负载更新、任务状态持久化或失败重试，因此还不是可执行任务的完整分布式调度系统。
- 集成测试调用真实模型验证三个原始任务；缺少配置或 API 不可用时失败，不使用 Mock 替代。

本目录用于实践 Datawhale「Hello Agents」教程第十章的智能体通信协议实验。

项目来源：<https://hello-agents.datawhale.cc/>

## 环境

与其他章节统一使用项目根目录的 `.conda` 环境，依赖写在根目录 `requirements.txt`。

教程写的是 `hello-agents[protocol]==0.2.2`，本项目不采用：0.2.2 要求 `numpy<2`，
并且会把第八、九章使用的 `hello-agents==0.2.8` 降级。0.2.8 本身已包含 `protocols`
模块，`MCPTool` / `A2ATool` / `ANPTool` 的用法与教程一致，因此改为在 0.2.8 上
安装 `protocols` extra。

```powershell
conda activate .\.conda
python -m pip install -r .\requirements.txt
```

已知兼容性问题（已在根目录 `requirements.txt` 中处理）：

| 问题 | 处理 |
| --- | --- |
| extra 名是 `protocols`，`[protocol]` 会被忽略 | 使用 `hello-agents[protocols]==0.2.8` |
| a2a-sdk 1.x 移除了 `a2a.client.A2AClient`，导致 `A2A_AVAILABLE=False` | 固定 `a2a-sdk<0.4`（实测 0.3.26） |
| `A2AServer` 依赖 Flask，但包未声明 | 额外安装 `flask` |
| Windows 控制台 GBK 无法编码 emoji，MCP 调用报 `'gbk' codec can't encode` | 脚本内把 stdout/stderr 改为 UTF-8 |

## 快速体验：三种协议的基本功能

```powershell
cd D:\WorkSpace\learning_space\my-hello-agents
.\.conda\python.exe -X utf8 10-experiment\common\demos\protocols_quickstart.py
```

- **MCP**：`MCPTool()` 不传 `server_command` 时连接内置的内存 MCP 服务器，调用 `add(10, 20)` 返回 `30.0`。
- **ANP**：`ANPTool` 在本地注册 `calculator` 服务，再通过 `discover_services` 发现它。
- **A2A**：只创建指向 `http://localhost:5000` 的 `A2ATool` 客户端，不发起连接。

本示例只在本地体验协议机制，不调用 LLM。

## MCP 客户端：连接服务器与发现工具

需要 Node.js（`npx`），首次运行会从 npm 下载 `@modelcontextprotocol/server-filesystem`。

```powershell
.\.conda\python.exe -X utf8 10-experiment\mcp\demos\mcp_client_basics.py
```

- **连接服务器**（`connect_to_server`）：用异步 `MCPClient` 分别连接社区文件系统服务器和
  自定义 Python 服务器 `mcp/demos/my_mcp_server.py`（教程未提供该文件，这里补了一个最小实现，提供 `add` 工具、一个资源和 `code_review` 提示）。
- **发现工具**（`discover_tools`）：列出文件系统服务器的 14 个工具及其参数。
- **安全调用工具**（`safe_tool_call`）：故意读取不存在的 `nonexistent.txt`，服务器返回错误后
  `call_tool` 抛出异常，被 `try/except` 捕获并打印 `工具调用失败: ENOENT: no such file or directory ...`。
- **资源与提示**（`use_resources_and_prompts`）：连接自定义服务器，列出并读取资源
  `file:///10-experiment/README.md`，列出提示并获取 `code_review(language="python")` 的内容。

与教程代码的差异：

| 教程 | 本项目 | 原因 |
| --- | --- | --- |
| 文件系统根目录写 `"."` | 固定为 `10-experiment` 目录 | `"."` 取运行时工作目录，结果随启动位置变化 |
| 读取 `tool['inputSchema']` | 读取 `tool['input_schema']` | hello-agents 0.2.8 的 `list_tools()` 返回的键名是 `input_schema`，按教程写法参数信息会被静默跳过 |
| 资源与提示连接文件系统服务器 | 连接自定义服务器 `my_mcp_server.py` | 文件系统服务器只提供工具，`list_resources` / `list_prompts` 返回 `Method not found` |
| `client.list_resources()` 等不加 `await` | 加 `await` | hello-agents 的这些方法都是 `async`，不加只会得到协程对象 |
| 直接调用 `list_resources` / `read_resource` / `list_prompts` | 改用 `*_compat` 兼容函数 | hello-agents 0.2.8 按旧版 fastmcp 格式解析：`list_resources`、`list_prompts` 抛 `AttributeError`，`read_resource` 静默返回 `None`；`get_prompt` 正常 |

本示例只连接 MCP 服务器，不调用 LLM。

## Memory（内存）传输

```powershell
.\.conda\python.exe -X utf8 10-experiment\mcp\demos\mcp_memory_transport_demo.py
```

- **内置演示服务器**（教程代码）：`MCPTool()` 不传 `server_command` 时使用内置的
  `HelloAgents-BuiltinServer`，列出 6 个工具（`add`/`subtract`/`multiply`/`divide`/`greet`/`get_system_info`），调用 `add(10, 20)` 返回 `30.0`。
- **自定义服务器实例**：从 `my_mcp_server.py` 导入 FastMCP 实例，直接传给 `MCPClient(server)`，
  即走内存传输；同一个服务器用 `MCPClient(["python", "my_mcp_server.py"])` 则走 stdio。
- 内存传输不启动子进程、不需要 Node.js，客户端与服务器在同一进程内，适合单元测试。
  控制台的 `INFO:mcp.server...` 日志来自同进程内的服务器，不是报错。

## Stdio 传输

需要 Node.js（`npx`）。

```powershell
.\.conda\python.exe -X utf8 10-experiment\mcp\demos\mcp_stdio_transport_demo.py
```

- **方式1：自定义 Python 服务器**：`MCPTool(server_command=["python", "my_mcp_server.py"])`，列出工具并调用 `add(10, 20)` 返回 `30.0`。
- **方式2：社区文件系统服务器**：`MCPTool(server_command=["npx", ..., "server-filesystem", ...])`，列出 14 个工具并用 `read_file` 读取 `README.md`。

与教程代码的差异：

| 教程 | 本项目 | 原因 |
| --- | --- | --- |
| 两种方式写在一起，第二次赋值覆盖第一次 | 拆成 `custom_server_demo` / `filesystem_server_demo` 分别演示 | 教程写法中方式1 创建后从未被使用 |
| 服务器脚本和根目录用相对路径 | 固定为绝对路径 | 相对路径依赖运行时工作目录 |
| `read_file` 读取整个 `README.md` | 加 `head: 5` | 避免输出过长 |

与内存传输示例对照：同一个 `my_mcp_server.py`，这里每次 `run()` 都会启动一次子进程
（输出中可见 3 次 `Starting MCP server 'my-server' with transport 'stdio'`）。

## HTTP（Streamable HTTP）传输

```powershell
.\.conda\python.exe -X utf8 10-experiment\mcp\demos\mcp_http_transport_demo.py
```

- 教程连接的 `http://api.example.com/mcp` 并不存在，这里补了本机服务器 `mcp/demos/http_mcp_server.py`，
  提供教程中的 `process_data` 工具（`uppercase` / `lowercase` / `reverse`），监听 `http://127.0.0.1:8765/mcp`。
- 脚本先在后台启动该服务器、等端口就绪，再用 `MCPClient(url)` 连接：列出 1 个工具，
  `process_data("Hello, World!", "uppercase")` 返回 `HELLO, WORLD!`，结束时关闭服务器。
- `MCPClient` 收到 `http://` 开头的 URL 时默认使用 Streamable HTTP；传 `transport_type="sse"` 才走旧的 SSE 传输。
- 也可以手动分开运行：先 `python 10-experiment\mcp\demos\http_mcp_server.py` 启动服务器，再在另一个终端运行客户端。
  实际工程中 HTTP 服务器是独立部署的服务，客户端只负责按 URL 连接。

## SSE 传输

```powershell
.\.conda\python.exe -X utf8 10-experiment\mcp\demos\mcp_sse_transport_demo.py
```

- 教程连接的 `http://localhost:8080/sse` 需要自备服务器，这里补了本机服务器 `mcp/demos/sse_mcp_server.py`，
  监听 `http://127.0.0.1:8767/sse`，提供 `stream_process` 工具：把输入每 2 个字分一块处理，
  `stream=True` 时每处理完一块就通过 `ctx.report_progress` 推送一次进度。
- **教程写法**：`MCPClient(url, transport_type="sse")` + `call_tool`，只拿到最终结果
  `处理完成，共 4 块：[大量][数据][处理][请求]`。hello-agents 的 `call_tool` 不接收进度推送。
- **接收进度推送**：改用底层 fastmcp 客户端 `client.client.call_tool(..., progress_handler=...)`，
  依次收到 `进度 1/4 … 4/4`，再拿到最终结果。
- 必须显式传 `transport_type="sse"`：`http://` 开头的 URL 默认走 Streamable HTTP。
- 服务器日志可见 SSE 的两条通道：`GET /sse` 建立服务器推送的长连接，
  客户端消息则 `POST /messages/?session_id=...`；Streamable HTTP 只用一个 `/mcp` 地址。
- SSE 已在 MCP 规范中被 Streamable HTTP 取代，新项目应使用 HTTP 传输，SSE 仅用于兼容旧服务器。

## GitHub MCP 服务

在项目根目录 `.env` 中添加 `GITHUB_PERSONAL_ACCESS_TOKEN`（Fine-grained token，
Repository access 选 Public repositories (read-only) 即可），然后运行：

```powershell
.\.conda\python.exe -X utf8 10-experiment\mcp\demos\github_mcp_demo.py
```

- 使用同步 `MCPTool` 连接 `@modelcontextprotocol/server-github`，列出 26 个工具，
  并调用 `search_repositories` 搜索 `AI agents language:python`（每页 3 条）。
- 教程要求手动设置 shell 环境变量；本项目改为从 `.env` 读取，未配置时脚本直接退出并提示。
  `MCPTool` 会根据 `server-github` 自动检测该变量并传给服务器子进程。
- `@modelcontextprotocol/server-github` 已在 npm 上标记为弃用（最后版本 2025.4.8），目前仍可运行；
  官方替代为 `github/github-mcp-server`（需 Docker 或单独下载二进制）。
- 同步 `MCPTool` 每次 `run()` 都会重新启动服务器：本示例中初始化发现工具、`list_tools`、
  `call_tool` 共启动了 3 次。

## A2A 计算器智能体

```powershell
.\.conda\python.exe -X utf8 10-experiment\a2a\demos\a2a_calculator_agent.py
```

- 用 `A2AServer` 创建 `calculator-agent`，通过 `@calculator.skill(...)` 注册 `add`、`multiply`、`info` 三个技能。
- 示例只在本地直接调用 `calc_agent.skills[...]`，不启动 HTTP 服务器（需要对外提供服务时调用 `calc_agent.run(port=5000)`，依赖 Flask）。
- 修正教程代码：原写法先替换 `加` 再替换 `加上`，导致 `计算 2 加上 3` 变成 `2 +上 3` 而解析失败，这里调换了顺序；
  路由判断也补上了 `加` / `乘以`，可以识别中文运算词。

## A2A 客户端调用

```powershell
# 终端 1：启动计算器服务端（只监听 127.0.0.1:5000）
.\.conda\python.exe -X utf8 10-experiment\a2a\demos\a2a_calculator_agent.py --serve
# 终端 2：运行客户端
.\.conda\python.exe -X utf8 10-experiment\a2a\demos\a2a_calculator_client.py
```

- 教程原示例连接的是研究员 Agent 的 `research` 技能，这里改为连接本项目的 `calculator-agent`。
- 客户端依次演示 `get_info`、`list_skills`、`execute_skill`、`ask` 四种调用，分别对应服务端的
  `/info`、`/skills`、`/execute/<skill>`、`/ask` 接口；调用未注册的 `divide` 技能用于演示 404 错误分支。
- `A2AServer` 没有鉴权，因此服务端绑定 `127.0.0.1` 而不是默认的 `0.0.0.0`。

## A2A 多智能体协作

```powershell
.\.conda\python.exe -X utf8 10-experiment\a2a\demos\a2a_multi_agent_collab.py
```

- 同一进程内用线程启动 `researcher`、`writer`、`editor` 三个 `A2AServer`（端口 5001-5003），
  再各建一个 `A2AClient`，按「研究 → 撰写 → 编辑」串联：上一个 Agent 的 `result` 作为下一个的输入。
- 修正教程代码：
  - `eval` 改为 `ast.literal_eval`，避免执行收到的任意字符串；
  - 正则加 `re.DOTALL`，否则多行文章传给编辑员时只剩第一行标题；
  - 用 `/health` 轮询并校验 Agent 名称代替固定 `time.sleep(2)`；
  - 端口从教程的 5000-5002 改为 5001-5003。实测在 Windows 上，5000 被计算器服务端占用时，
    新服务线程不会报错，`researcher` 的请求会落到计算器上返回 404，所以启动前会先检查端口。
  - 某一步调用失败时直接抛错，不把错误信息当正常数据传给下一个 Agent。

## A2A 智能客服系统

在项目根目录运行（使用当前项目路径，无需修改脚本）：

```powershell
# 自动演示 API 调用、企业版价格、Python 集成三个问题
.\.conda\python.exe -X utf8 10-experiment\a2a\demos\a2a_customer_service.py
# 连续对话：/reset 清空历史，/exit 退出
.\.conda\python.exe -X utf8 10-experiment\a2a\demos\a2a_customer_service.py --interactive
# 单个咨询；端口冲突时可加 --tech-port 6010 --sales-port 6011
.\.conda\python.exe -X utf8 10-experiment\a2a\demos\a2a_customer_service.py --query "企业版价格和Python接入方法是什么？"
```

- 接待员是 `SimpleAgent`，读取根目录 `.env` 中的 `LLM_API_KEY`、`LLM_BASE_URL`、
  `LLM_MODEL_ID` 调用真实模型，选择专家并整理回答。运行会产生 API 用量。
- 两位专家通过 `A2AServer` 暴露 `answer` 技能，只监听 `127.0.0.1:6000/6001`。
  `A2ATool` 以 `action=ask`、`question=问题` 调用 `/ask`，无需给问题添加 `answer` 前缀。
  启动前检查端口，通过 `/health` 校验专家名称后才接待客户。
- 技术咨询分流到 `tech_expert`，价格和购买分流到 `sales_advisor`，混合咨询可调用两者。
  交互模式保留当前会话历史；默认三个演示问题分别清空历史。
- 专家使用脚本中的 `TECH_KNOWLEDGE` / `SALES_KNOWLEDGE` 示例资料，不额外调用 LLM。
  替换这两处即可补入产品文档和正式报价；当前不会提供未经配置的具体价格或优惠。
  Python 代码仅用于声明兼容 OpenAI 的服务，不代表任意产品都支持该接口。
- 这是本地命令行教学系统，会话保存在内存中；主进程退出时两个专家线程随之结束。
  本例沿用 hello-agents 0.2.8 的 Flask HTTP 封装。

真实 API 集成测试（缺少配置时直接失败，不回退到 Mock）：

```powershell
.\.conda\python.exe -X utf8 10-experiment\a2a\tests\test_a2a_customer_service.py
```

测试覆盖三个原始问题、混合咨询、问候、追问及历史清空，并记录实际 A2A 工具调用，
核对专家选择、请求参数和 HTTP 返回资料；另补充多行与空输入检查。

## A2A 协商机制

```powershell
# 默认：提议 3 天 → 反提议 7 天 → 重新提交并确认 7 天
.\.conda\python.exe -X utf8 10-experiment\a2a\demos\a2a_negotiation.py
# 首次直接接受
.\.conda\python.exe -X utf8 10-experiment\a2a\demos\a2a_negotiation.py --deadline 8
# 委托方最多接受 5 天，无法满足执行方至少 7 天的要求，协商拒绝
.\.conda\python.exe -X utf8 10-experiment\a2a\demos\a2a_negotiation.py --max-deadline 5
# 只允许一次提案，收到反提案后因轮数耗尽而终止
.\.conda\python.exe -X utf8 10-experiment\a2a\demos\a2a_negotiation.py --max-rounds 1
```

- Agent 1 是任务执行方，`propose` 技能根据最低工期决定接受或反提案。
- Agent 2 是任务委托方，`negotiate` 技能通过真实 `A2AClient.execute_skill` 向 Agent 1
  发提案；只有反提案在自身期限预算内时才重新提交，收到对方确认后才返回 `agreed`。
- 默认监听 `127.0.0.1:7000/7001`；可用 `--port1` / `--port2` 修改。
  主进程退出时服务线程结束，不在导入模块时启动服务。
- `deadline` 是所需天数，不是日历日期；`--min-days` 设置执行方最低工期，
  `--max-deadline` 设置委托方最长可接受工期，`--max-rounds` 限制提案次数（最多 10）。
- JSON 请求例子：`{"task":"开发客服","deadline":3,"max_deadline":10,"max_rounds":3}`。
  也兼容教程的 `negotiate task:开发客服 deadline:3`；省略预算时默认取首次工期和 7 的较大值。
  推荐显式指定预算，尤其是修改执行方最低工期时。
- 用 JSON 代替 `eval`；结果包含 `status`、实际轮数和每轮提案/答复。
  可能状态为 `agreed`、`rejected`、`max_rounds`、`error`，仅 `agreed` 包含最终协议。
  命令行达成协议退出码为 0，其余为 1。
- 本例是应用层规则协商，A2A 负责通信；协议本身不会自动生成协商策略。
  不使用 LLM，不读取 `.env`，不产生模型 API 费用；协议确认只作为本次返回结果，不持久化任务或预约资源。

实际 HTTP API 测试（两个真实服务，非 Mock，也不是 LLM API 测试）：

```powershell
.\.conda\python.exe -X utf8 10-experiment\a2a\tests\test_a2a_negotiation.py
```

## ANP 负载均衡

```powershell
.\.conda\python.exe -X utf8 10-experiment\anp\demos\anp_load_balancer.py
.\.conda\python.exe -X utf8 10-experiment\anp\tests\test_anp_load_balancer.py
```

- 注册 5 个 API 服务，以固定种子生成可重复的初始负载；每次分配前选择当前最低负载服务，再把模拟负载增加指定值。支持 `--seed`、`--requests`、`--increment` 调整演示。
- 负载为可超过 1 的累加分数，不是实际 CPU 利用率。仅更新本地服务元数据，不发送 HTTP 请求，也不是生产级并发负载均衡器；多进程部署时需要共享、原子更新的负载状态。
- 确定性测试覆盖最低负载轮转、空服务列表和零负载增量。

## ANP 服务发现与 Agent 网络

```powershell
# 服务发现：注册 + 按类型/能力/元数据查找 + 按负载选最优
.\.conda\python.exe -X utf8 10-experiment\anp\demos\anp_service_discovery.py
# 组网：建网络 + 按能力互连 + 路由/广播/统计
.\.conda\python.exe -X utf8 10-experiment\anp\demos\anp_network.py
```

- `anp_service_discovery.py` 在内存中注册 4 个服务（`nlp_agent_1`、`nlp_agent_2`、
  `translate_agent`、`router_agent`），`find_services()` 支持类型、能力、元数据组合查找，
  `select_best_service()` 按负载取最小、负载相同时比价格。
- 教程里的 `min(services, key=lambda s: s.metadata.get("load", 1.0))` 就是这里选型的简化版；
  本项目额外把缺失或非数值的 `load` 统一当作 1.0，避免混入字符串时抛 `TypeError`。
- `discover_service()` 只接受 `service_type`，能力与自定义元数据要在结果上再筛一次；
  元数据过滤是全等比较，不支持范围查询。
- `anp_network.py` 把发现到的服务建成 `ai_cluster` 网络，按能力交集建立双向连接，
  再用最低负载的 NLP 服务给 `router_agent` 建一条派发边，最后演示 1 跳 / 2 跳路由、
  广播与网络统计。

与库行为的差异（示例里做了防护，未改动 site-packages）：

| 库行为 | 示例处理 |
| --- | --- |
| `add_node()` 遇到同名节点直接覆盖，并清空该节点已有连接 | `add_node()` 先检查，重复添加抛 `ValueError`，不破坏已有连接 |
| `connect_nodes()` 只建单向边，`route_message()` 反向不可达 | `connect()` 同时建反向边 |
| `connect_nodes()` 对不存在的节点静默忽略 | `connect()` 先做存在性检查，不存在抛 `KeyError` |
| 重复 `connect_nodes()` 被库去重 | `connect()` 返回本次是否真的新增了连接 |

- `route_message()` 只搜索 1 跳和 2 跳路径，更远返回 `None`。示例中
  `router_agent → nlp_agent_2` 走的正是经 `nlp_agent_1` 中转的两跳路径。
- 两个示例都是纯内存操作，不启动 HTTP 服务、不读取 `.env`、不调用 LLM，不产生 API 费用。

离线测试（纯内存拓扑，无 LLM，也不涉及真实 API）：

```powershell
.\.conda\python.exe -X utf8 10-experiment\anp\tests\test_anp_discovery_network.py
```

覆盖注册与去重、类型/能力/元数据查找、负载与价格选型、重复添加节点、连接不存在的节点、
双向与幂等连接、能力匹配建边、1 跳/2 跳/无路径路由、广播、移除节点后的连线清理，共 21 项。
