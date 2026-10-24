# 第十章实验：智能体通信协议（MCP / A2A / ANP）

本目录用于实践 Datawhale「Hello Agents」教程第十章的智能体通信协议实验。

项目来源：<https://hello-agents.datawhale.cc/>

## 环境

与其他章节统一使用项目根目录的 `.conda` 环境，依赖写在根目录 `requirements.txt`。

教程写的是 `hello-agents[protocol]==0.2.2`，本项目不采用：0.2.2 要求 `numpy<2`，
并且会把第八、九章使用的 `hello-agents==0.2.8` 降级。0.2.8 本身已包含 `protocols`
模块，`MCPTool` / `A2ATool` / `ANPTool` 的用法与教程一致，因此改为在 0.2.8 上
安装 `protocols` extra。

```powershell
conda activate F:\my-hello-agent\.conda
python -m pip install -r F:\my-hello-agent\requirements.txt
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
cd F:\my-hello-agent\10-experiment
F:\my-hello-agent\.conda\python.exe demos\protocols_quickstart.py
```

- **MCP**：`MCPTool()` 不传 `server_command` 时连接内置的内存 MCP 服务器，调用 `add(10, 20)` 返回 `30.0`。
- **ANP**：`ANPTool` 在本地注册 `calculator` 服务，再通过 `discover_services` 发现它。
- **A2A**：只创建指向 `http://localhost:5000` 的 `A2ATool` 客户端，不发起连接。

本示例只在本地体验协议机制，不调用 LLM。

## MCP 客户端：连接服务器与发现工具

需要 Node.js（`npx`），首次运行会从 npm 下载 `@modelcontextprotocol/server-filesystem`。

```powershell
F:\my-hello-agent\.conda\python.exe F:\my-hello-agent\10-experiment\demos\mcp_client_basics.py
```

- **连接服务器**（`connect_to_server`）：用异步 `MCPClient` 分别连接社区文件系统服务器和
  自定义 Python 服务器 `demos/my_mcp_server.py`（教程未提供该文件，这里补了一个最小实现，提供 `add` 工具、一个资源和 `code_review` 提示）。
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
F:\my-hello-agent\.conda\python.exe F:\my-hello-agent\10-experiment\demos\mcp_memory_transport_demo.py
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
F:\my-hello-agent\.conda\python.exe F:\my-hello-agent\10-experiment\demos\mcp_stdio_transport_demo.py
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
F:\my-hello-agent\.conda\python.exe F:\my-hello-agent\10-experiment\demos\mcp_http_transport_demo.py
```

- 教程连接的 `http://api.example.com/mcp` 并不存在，这里补了本机服务器 `demos/http_mcp_server.py`，
  提供教程中的 `process_data` 工具（`uppercase` / `lowercase` / `reverse`），监听 `http://127.0.0.1:8765/mcp`。
- 脚本先在后台启动该服务器、等端口就绪，再用 `MCPClient(url)` 连接：列出 1 个工具，
  `process_data("Hello, World!", "uppercase")` 返回 `HELLO, WORLD!`，结束时关闭服务器。
- `MCPClient` 收到 `http://` 开头的 URL 时默认使用 Streamable HTTP；传 `transport_type="sse"` 才走旧的 SSE 传输。
- 也可以手动分开运行：先 `python demos\http_mcp_server.py` 启动服务器，再在另一个终端运行客户端。
  实际工程中 HTTP 服务器是独立部署的服务，客户端只负责按 URL 连接。

## SSE 传输

```powershell
F:\my-hello-agent\.conda\python.exe F:\my-hello-agent\10-experiment\demos\mcp_sse_transport_demo.py
```

- 教程连接的 `http://localhost:8080/sse` 需要自备服务器，这里补了本机服务器 `demos/sse_mcp_server.py`，
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
F:\my-hello-agent\.conda\python.exe F:\my-hello-agent\10-experiment\demos\github_mcp_demo.py
```

- 使用同步 `MCPTool` 连接 `@modelcontextprotocol/server-github`，列出 26 个工具，
  并调用 `search_repositories` 搜索 `AI agents language:python`（每页 3 条）。
- 教程要求手动设置 shell 环境变量；本项目改为从 `.env` 读取，未配置时脚本直接退出并提示。
  `MCPTool` 会根据 `server-github` 自动检测该变量并传给服务器子进程。
- `@modelcontextprotocol/server-github` 已在 npm 上标记为弃用（最后版本 2025.4.8），目前仍可运行；
  官方替代为 `github/github-mcp-server`（需 Docker 或单独下载二进制）。
- 同步 `MCPTool` 每次 `run()` 都会重新启动服务器：本示例中初始化发现工具、`list_tools`、
  `call_tool` 共启动了 3 次。
