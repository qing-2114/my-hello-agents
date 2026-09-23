# my-hello-agent

## 项目状态

教程跟踪阶段已完成到第九章，实验覆盖 `1.3` / `3.2` / `4` / `6` / `7` / `8` / `9`，
其中第八章（记忆与检索）与第九章（上下文工程）均已通过真实 API 实测验证。

**自 2026-09-24 起暂停按 hello-agents 教程逐章推进。** 后续不再按章节组织，
改为围绕工程化能力推进：把已有 Agent 做成可上线的服务，补齐可观测性、自动化评测与部署，
再做纵深专题和作品集。计划见 [ROADMAP.md](ROADMAP.md)。

各实验目录仍保留教程章节编号与来源说明，便于回溯；README 不再预留尚未开工的章节小节。

## 统一环境变量配置

全项目只读取根目录的 `.env`。首次使用时直接在项目根目录创建 `.env`，
再按需填写 LLM、Tavily 和 SerpApi 配置；真实 `.env` 已被 Git 忽略。

## 文件职责

- `1.3-experiment/prompts/travel_agent.md`: 智能体的系统提示词，只保存提示词文本。
- `1.3-experiment/agent.py`: 读取系统提示词、构造发送给 LLM 的 `messages`，并提供工具分发函数。
- `1.3-experiment/tools.py`: 天气、景点搜索，以及可复现的本地模拟查票、备选和购票工具。
- `1.3-experiment/llm_client.py`: DeepSeek 的 OpenAI 兼容客户端封装。
- `1.3-experiment/memory_store.py`: V0 记忆读取、按用户隔离和关键词检索。
- `1.3-experiment/session_agent.py`: 多轮会话状态、显式接受/拒绝反馈，以及连续拒绝 3 次后的策略反思。
- `1.3-experiment/data/memories.jsonl`: 手工写入的用户偏好记忆（JSONL，一行一条记录）。
- `1.3-experiment/test_memory_v0.py`: 3 个离线记忆读取用例。

## 运行检查

```powershell
python .\1.3-experiment\agent.py
```

工具分发示例：

```python
from tools import available_tools

result = available_tools["get_weather"]("杭州")
# 或使用 agent.invoke_tool("get_weather", city="杭州")
```

安装依赖：

```powershell
conda activate F:\my-hello-agent\.conda
python -m pip install -r F:\my-hello-agent\requirements.txt
```

本项目使用项目内的 Conda 隔离环境 `F:\my-hello-agent\.conda`，Python 3.12，
并包含适配 NVIDIA GPU 的 PyTorch、Transformers。验证 GPU：

```powershell
conda run --prefix F:\my-hello-agent\.conda python -c "import torch, transformers; print(torch.__version__); print(transformers.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

景点工具调用前需要在根目录 `.env` 中配置 `TAVILY_API_KEY`；LLM 配置项为
`LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL_ID`。

启动完整的 LLM + 工具主循环：

```powershell
python .\1.3-experiment\agent.py
```

主循环会读取模型的 `Action`，执行 `available_tools` 中对应的函数，并把工具结果反馈给模型，直到模型返回 `Finish[...]`。

## V0 记忆功能

当前示例为 `demo-user` 手工保存了两条偏好：不喜欢室内活动（如博物馆），以及不喜欢西湖醋鱼。每次用户请求开始时，程序先按关键词检索相关记忆，再将 Top-K 结果作为“仅供参考的上下文”追加到系统提示词；记忆不会写入 `prompt_history`，也不能单独授权工具调用。

运行 3 个离线用例：

```powershell
python -m unittest discover -s .\\1.3-experiment -p "test_memory_v0.py" -v
```

真正调用模型时，将 `build_messages(user_input)` 的返回值传给你的 SDK。例如：

```python
response = client.chat.completions.create(
    model="MODEL_NAME",
    messages=build_messages(user_input),
)
```

不同 SDK 的参数名可能不同，但系统提示词的位置都是 `role="system"`。

## 实验 3-2：本地调用 Qwen1.5-0.5B-Chat

实验代码位于 `3.2-experiment/qwen_chat.py`，说明和运行命令见
`3.2-experiment/README.md`。它使用 Transformers 加载
`Qwen/Qwen1.5-0.5B-Chat`，默认采用教程中的贪心解码，也可以用 `--sample` 比较采样参数的影响。

## 第四章：ReAct 工具调用循环

`4-experiment/ReAct/agent.py` 已实现一个可交互的 ReAct Agent：模型按
`Thought` / `Action` 格式输出，Action 可调用注册工具或返回 `Finish[最终答案]`；
工具 Observation 会回灌到下一步上下文。当前搜索工具通过 SerpApi 提供网页摘要，
只有实际运行交互程序时才会使用配置好的 API。

离线单元测试不访问外部服务，可验证解析、工具回灌、格式错误恢复和最大步数限制：

```powershell
F:\my-hello-agent\.conda\python.exe -m unittest discover -s .\4-experiment\ReAct -p "test_*.py" -v
```

## 多轮拒绝与策略调整

`max_steps=5` 只限制单次用户请求内部的 Thought/Action 和工具调用循环。用户在智能体返回结果之后发起的新请求属于新的用户回合，应继续使用相同的 `SessionState`，并重新获得最多 5 个内部步骤。

```python
from session_agent import SessionState, continue_session

session = SessionState(session_id="web-session-001", user_id="demo-user")

result = continue_session(session, "推荐一个杭州周末景点")
result = continue_session(session, "人太多了，换一个", feedback_type="reject")
result = continue_session(session, "我不喜欢商业街", feedback_type="reject")
result = continue_session(session, "也不想去室内", feedback_type="reject")

print(result.reflected)         # True
print(result.strategy_version)  # 1
print(result.answer)            # 已应用新策略的下一次推荐
```

直接运行可连续交互的命令行版本：

```powershell
python .\1.3-experiment\session_agent.py
```

每次模型返回 `Finish[...]` 后，程序仍会等待下一条输入。普通文字会经过一次反馈分类，自动判断为接受、拒绝或普通消息；使用 `/reject 拒绝原因` 和 `/accept` 可以在调试时明确覆盖分类结果，使用 `/exit` 结束整个会话。例如：

```text
你：推荐一个杭州景点
智能体：……
你：人太多了，换一个
智能体：……
你：我不喜欢商业街
智能体：……
你：这个也不合适，我想去安静的户外地点
[已根据连续 3 次拒绝调整推荐策略]
智能体：……
```

自然语言反馈分类最多增加一次独立的 LLM 调用，不占用 `max_steps_per_turn=5`；这 5 步仍只约束生成当前答案时的 Thought/Action 和工具调用循环。

记忆检索会使用本轮输入和同一会话最近的用户输入。因此第一轮检索到的偏好不会因为后续用户只说“不要”而立即消失；例如“不喜欢博物馆”会继续作为系统上下文约束后续推荐。反思同时读取这些长期偏好，而且不能把没有具体原因的景点拒绝扩大成对整个活动类别的拒绝。触发三次拒绝时，命令行先显示 `[已根据连续 3 次拒绝调整推荐策略]` 和新策略摘要，再使用该策略执行本轮 Agent Loop。

## 模拟票务与售罄备选

票务实验使用 `tools.py` 中的本地固定库存，不连接真实票务平台，也不会产生真实交易。当前杭州模拟数据中，灵隐寺和雷峰塔余票为 0；西溪国家湿地公园、杭州宋城和千岛湖中心湖区有票。重启程序后库存恢复，离线测试可调用 `reset_mock_ticket_inventory()` 主动复位。

Agent 在推荐需要购票的景点前先调用 `check_ticket_availability`。用户明确确认景点、日期和数量后才能调用 `book_ticket`。如果返回 `SOLD_OUT`，Agent 在同一轮调用 `find_ticket_alternatives` 并向用户展示备选；用户需要再次确认后，下一轮才会购买备选景点。

可直接验证工具：

```python
from tools import check_ticket_availability, find_ticket_alternatives

print(check_ticket_availability("杭州", "灵隐寺", "2026-09-10", 1))
print(find_ticket_alternatives("杭州", "2026-09-10", 1, ["灵隐寺"]))
```

接入 HTTP 服务时，服务端应通过 `session_id` 读取并保存 `SessionState`。请求体应显式包含 `feedback_type`（`none`、`accept` 或 `reject`），不要让模型决定是否计为拒绝。生产环境可把状态放入 Redis 或数据库；此示例保留为可注入、可测试的内存对象。

推荐沿用同一个“继续会话”接口，例如：

```http
POST /sessions/web-session-001/turns
Content-Type: application/json

{
  "message": "人太多了，换一个安静的",
  "feedback_type": "reject"
}
```

服务端把返回值映射为 `answer`、`reflected`、`consecutive_rejections` 和 `strategy_version`。正式对外提供接口时还应给每条推荐生成 `recommendation_id`，反馈请求携带该 ID，并用它做幂等校验，防止网络重试被重复计为两次拒绝。

建议分别设置以下边界：

- `max_steps_per_turn=5`：限制一次用户回合中的 LLM/工具循环，现有值可以保留。
- 每个用户回合最多反思 1 次：第三次拒绝只生成一次新策略，再用它产生下一条回复。
- 按 token 预算截断或摘要会话历史；示例暂时只注入最近 12 条消息。
- 给服务层设置会话 TTL 和请求频率限制。不要用总回合数 5 来提前结束正常对话。
- 如果调整策略后又连续拒绝 3 次，优先询问预算、距离、时间、同行人和活动类型等缺失约束，再生成下一批推荐。

运行全部离线测试：

```powershell
python -m unittest discover -s .\1.3-experiment -p "test_*.py" -v
```

## 第六章：多智能体框架与 LangGraph

`6-experiment/` 已包含 AgentScope、AutoGen、CAMEL 和 LangGraph 四组实验：

- `AgentScope/`：由模型角色与 Python 规则控制器共同推进三国狼人杀对局；
- `AutoGen/`：产品、开发、审查与用户代理协作生成并验收应用；
- `CAMEL/`：AI 作家与 AI 心理学家通过 `RolePlaying` 协作生成科普电子书；
- `LangGraph/`：使用 `SearchState` 和 `StateGraph` 串联
  `understand -> search -> answer`，支持 Tavily 搜索失败时回退到 LLM 知识回答。

运行 LangGraph 离线测试：

```powershell
F:\my-hello-agent\.conda\python.exe -m unittest .\6-experiment\LangGraph\test_graph.py -v
```

运行真实 LLM 与 Tavily 搜索链路：

```powershell
F:\my-hello-agent\.conda\python.exe .\6-experiment\LangGraph\graph.py "LangGraph 的 StateGraph 如何传递状态？"
```

## 第七章：框架扩展与智能体评估

第七章实验位于 `7-experiment/`，当前包含九组可运行扩展：

- `MyLLM`：在不修改 `hello-agents` 源码的前提下扩展 ModelScope Provider；
- `MySimpleAgent`：增加文本工具调用、多轮 Observation 回灌和流式响应；
- `MyReActAgent`：增强 Thought/Action 解析、格式错误自纠和基于 Observation 的防幻觉约束；
- `MyReflectionAgent`：实现适用于写作、总结、方案等文本任务的
  “初始回答 -> 反思 -> 改进”循环；
- `MyPlanAndSolveAgent`：改进第四章的 Plan-and-Solve，优化规划与执行提示词，
  计划解析更健壮，并在规划失败时自纠重试、必要时退回单步直接作答；
- `my_calculator`：用 `ToolRegistry.register_function` 注册的自定义计算器工具，
  通过 AST 安全求值支持四则运算、`sqrt` 和 `pi`；
- `advanced_search`：自定义高级搜索工具，优先 Tavily、失败时回退 SerpApi；
- `ToolChain`：把多个已注册工具按顺序串起来，用模板把上一步输出传给下一步；
- `AsyncToolExecutor`：用线程池 + `asyncio.gather` 并行执行多个工具。

各 Demo、离线测试和真实 API 运行命令见 `7-experiment/README.md`。项目统一从根目录
`.env` 读取 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL_ID`，不在源码或日志中保存密钥。

## 第八章：记忆与检索

第八章实验位于 `8-experiment/`，对应 `hello-agents==0.2.0` 的记忆系统与 RAG。
配置仍只读取根目录 `.env` 中的 LLM、Qdrant、Neo4j 和 Embedding 项。

快速体验（教程 8.1.4）：带 `MemoryTool` 和 `RAGTool` 的 `SimpleAgent`。

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.memory_rag_agent_demo
```

MemoryTool 添加、搜索与摘要示例：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.memory_tool_demo
```

RAGTool 添加文本、搜索与知识库统计示例：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.rag_tool_demo
```

请在 `8-experiment` 目录下执行。说明见 `8-experiment/README.md`。

### PDF 智能文档问答助手

`8-experiment/core/pdf_assistant.py` 把 MemoryTool 与 RAGTool 组合成 PDF 问答助手
（加载 → 提问 → 笔记 → 回顾 → 报告），`8-experiment/app.py` 提供 Gradio Web 界面。

```powershell
F:\my-hello-agent\.conda\python.exe .\8-experiment\app.py
# 浏览器打开 http://127.0.0.1:7860
```

命令行验证：`F:\my-hello-agent\.conda\python.exe -m demos.pdf_learning_assistant_demo --check`
（需在 `8-experiment` 目录下执行）。

## 后续方向

教程跟踪暂停在第九章，`10-experiment/` 尚未开工，README 不再预留该小节。
下一阶段按工程化能力组织，见 [ROADMAP.md](ROADMAP.md)。

已安装的 `hello-agents==0.2.8` 仍带有 `protocols`（MCP / A2A / ANP）、
`evaluation`（BFCL、GAIA、LLM-as-Judge、win-rate）和 `rl` 模块，
对应教程第十、十一、十二章的能力。需要时直接作为组件取用即可，
不再逐章复现教程示例。
