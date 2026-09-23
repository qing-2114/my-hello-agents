# 第八章实验：记忆与检索

本目录用于实践 Datawhale「Hello Agents」教程第八章的记忆系统与 RAG 实验。

项目来源：<https://hello-agents.datawhale.cc/>

本章对应 `hello-agents==0.2.0`。若该版本遇到模型不可用，可查看
[issue #320](https://github.com/datawhalechina/hello-agents/issues/320)，
或切换 `hello-agents==0.2.8 / 0.2.9` 再测（当前环境实测 0.2.8 可用，
`core/framework_fixes.py` 对 0.2.0 与 0.2.8 都做了兼容）。

注意：安装 `hello-agents[evaluation]` 会按它的依赖把 gradio 降到 4.x，而
4.44.1 与当前 starlette / fastapi 不兼容（首页模板渲染会报
`TypeError: unhashable type: 'dict'`）。`app.py` 需要 gradio 6.x；
hello-agents 运行时并不导入 gradio，两者可以并存，恢复命令：

```powershell
F:\my-hello-agent\.conda\python.exe -m pip install "gradio==6.28.0"
```

后续实验代码、数据、Demo 和运行说明均放在本目录内。

## 快速体验：记忆 + RAG 智能体

教程 8.1.4 的 30 秒示例位于 `demos/memory_rag_agent_demo.py`。
它会从项目根目录 `.env` 读取 LLM、Qdrant、Neo4j 和 Embedding 配置，
再注册 `MemoryTool` 与 `RAGTool`，用 `SimpleAgent` 跑一轮对话。

在 `8-experiment` 目录下运行：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.memory_rag_agent_demo --check
F:\my-hello-agent\.conda\python.exe -m demos.memory_rag_agent_demo
```

`--check` 会初始化记忆库和 RAG（含 Qdrant / Neo4j / Embedding 连通），
但不发起对话 LLM 请求。去掉 `--check` 会真实调用模型，让助手记住
「我叫张三，我是一名Python开发者」。

## MemoryTool：添加、搜索与摘要

教程中的 MemoryTool 示例位于 `demos/memory_tool_demo.py`。
它创建带 `MemoryTool` 的 `SimpleAgent`（记忆助手），写入三条语义记忆
（张三 / 李四 / 王五），再搜索「前端工程师」并打印记忆摘要。

`hello-agents==0.2.0` 的 `Tool.run` 只接受参数字典，Demo 用 `run_memory()`
把教程写法 `memory_tool.run("add", content=...)` 适配为
`{"action": "add", ...}`。

在 `8-experiment` 目录下运行：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.memory_tool_demo --check
F:\my-hello-agent\.conda\python.exe -m demos.memory_tool_demo
```

`--check` 只初始化 LLM 与 MemoryTool。完整运行会通过 Embedding、Qdrant
和 Neo4j 真实写入、检索语义记忆，不发起对话 LLM 请求。

## RAGTool：添加文本、搜索与统计

教程中的 RAGTool 示例位于 `demos/rag_tool_demo.py`。
它创建带 `RAGTool` 的 `SimpleAgent`（知识助手），写入三条文本知识
（Python 简介 / 机器学习基础 / RAG 概念），再搜索「Python编程语言的历史」
并打印知识库统计。

`hello-agents==0.2.0` 的 `_preprocess_parameters` 会把未传入的 `namespace`
设成 `"default"`，覆盖 `RAGTool(rag_namespace=...)`。Demo 用 `run_rag()`
补上工具自身的命名空间。

在 `8-experiment` 目录下运行：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.rag_tool_demo --check
F:\my-hello-agent\.conda\python.exe -m demos.rag_tool_demo
```

`--check` 只初始化 LLM 与 RAGTool（含 Qdrant / Embedding 连通）。
完整运行会真实写入文本、向量检索并打印统计；默认搜索会走高级检索
（含 LLM 改写），因此会发起 Embedding 与 LLM 请求，但不会走对话 `agent.run()`。

## PDF 智能文档问答助手

`core/pdf_assistant.py` 把 `MemoryTool` 与 `RAGTool` 组合成面向单份 PDF 的
学习助手：加载 PDF → 提问（可选 MQE + HyDE 高级检索）→ 记笔记 → 回顾学习
历程 → 生成学习报告。数据按 `user_id` 隔离（RAG 命名空间为 `pdf_<user_id>`）。

- `app.py`：Gradio Web 界面（上传 PDF / 问答 / 笔记 / 统计 / 报告下载）；
- `demos/pdf_learning_assistant_demo.py`：命令行演示与验证。

启动 Web 界面（在 `8-experiment` 目录下）：

```powershell
F:\my-hello-agent\.conda\python.exe app.py
# 浏览器打开 http://127.0.0.1:7860
```

命令行验证：

```powershell
# 仅检查 .env 与工具初始化
F:\my-hello-agent\.conda\python.exe -m demos.pdf_learning_assistant_demo --check

# 加载 PDF 并提问（--question 可多次传入）
F:\my-hello-agent\.conda\python.exe -m demos.pdf_learning_assistant_demo --pdf "C:/path/to/book.pdf" --question "这本书主要讲什么？"
```

适配说明（相对教程写法的差异）：

- 0.2.0 的 `execute()` 返回带 ✅/❌ 前缀的格式化字符串（不是字典），助手用
  字符串前缀判断成功；
- 每个 RAG 调用都显式传 `namespace=pdf_<user_id>`，否则会被
  `_preprocess_parameters` 覆盖为 `default`；
- 语义记忆依赖 Neo4j；连不上时助手自动降级为「工作 + 情景」记忆（笔记降级
  保存为情景记忆），PDF 问答主链路不受影响，降级状态会显示在学习统计、加载
  状态和报告中；
- hello-agents 0.2.0 有三个实测缺陷会阻塞 PDF 入库：分块器在「单个段落超过
  `chunk_size - overlap`」时死循环（LaTeX 排版的中文 PDF 实测触发）、
  DashScope Embedding 单请求超过 10 条被拒、PDF 解析失败时兜底把二进制流当
  文本写入。`core/framework_fixes.py` 在不改动 site-packages 的前提下打补丁，
  助手初始化时自动应用（离线回归测试见 `test_framework_fixes.py`）。

## 本章内容

教程在第七章框架上增加两块能力：

- **记忆系统（Memory）**：工作记忆、情景记忆、语义记忆、感知记忆
- **检索增强生成（RAG）**：文档解析、向量检索、问答生成

框架侧对应模块：

```text
hello_agents/
├── memory/
│   ├── manager.py          # MemoryManager
│   ├── embedding.py        # DashScope / 本地 / TF-IDF
│   ├── types/              # working / episodic / semantic / perceptual
│   ├── storage/            # Qdrant / Neo4j / SQLite
│   └── rag/                # RAG pipeline
└── tools/builtin/
    ├── memory_tool.py
    └── rag_tool.py
```

## 环境

使用项目内 Conda 环境 `F:\my-hello-agent\.conda`。配置统一读取项目根目录 `.env`，
不在源码、测试或日志中写入密钥。

PDF 解析依赖 MarkItDown 的 pdf 扩展（`pdfminer.six` + `pdfplumber`）；缺失时
`add_document` 无法解析 PDF（`core/framework_fixes.py` 会阻止把二进制流写入
向量库）。

需要的变量：

- LLM：`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_ID`
- Qdrant：`QDRANT_URL`、`QDRANT_API_KEY`、`QDRANT_COLLECTION`、`QDRANT_VECTOR_SIZE`
- Neo4j：`NEO4J_URI`、`NEO4J_USERNAME`、`NEO4J_PASSWORD`、`NEO4J_DATABASE`
- Embedding：`EMBED_MODEL_TYPE`、`EMBED_API_KEY`、`EMBED_BASE_URL`

通义 `text-embedding-v3` 默认 1024 维，`QDRANT_VECTOR_SIZE` 需与之一致。

`hello-agents==0.2.0` 会导入 `qdrant_client.http.models.SearchRequest`，
该符号在 `qdrant-client 1.19` 中已移除。本环境将客户端钉在
`qdrant-client==1.15.1`。Qdrant Cloud 服务端可能是 1.19，初始化时会有
版本不匹配警告，但不影响本章连通和写入。

## 目录结构

```text
8-experiment/
├── README.md
├── app.py                              # PDF 问答助手 Gradio Web 界面
├── core/config.py                      # 读取项目根目录 .env
├── core/pdf_assistant.py               # PDFLearningAssistant（MemoryTool + RAGTool）
├── demos/memory_rag_agent_demo.py      # 教程 8.1.4 记忆 + RAG 示例
├── demos/memory_tool_demo.py           # MemoryTool 添加 / 搜索 / 摘要
├── demos/rag_tool_demo.py              # RAGTool 添加文本 / 搜索 / 统计
├── demos/pdf_learning_assistant_demo.py # PDF 问答助手命令行演示
├── knowledge_base/                     # RAG 知识库目录（可放入文档）
├── memory_data/                        # 本地 SQLite 记忆库（已 gitignore）
└── reports/                            # 学习报告输出（已 gitignore）
```
