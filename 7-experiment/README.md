# 第七章实验：智能体评估

本目录用于实践 Datawhale「Hello Agents」教程第七章的智能体评估实验。

项目来源：<https://hello-agents.datawhale.cc/>

后续实验代码、数据、评估器和运行说明均放在本目录内。

## 目录结构

```text
7-experiment/
├── agents/                 # 自定义 Agent 与 LLM 实现
│   ├── my_llm.py
│   ├── my_simple_agent.py
│   ├── my_react_agent.py
│   └── my_reflection_agent.py
├── core/                   # 基础抽象、配置和消息模型
│   ├── agent.py
│   ├── config.py
│   └── message.py
├── demos/                  # 可直接运行的命令行示例
│   ├── simple_agent_demo.py
│   ├── custom_llm_demo.py
│   ├── react_agent_demo.py
│   └── reflection_agent_demo.py
└── README.md
```

所有 Demo 从 `7-experiment` 目录以模块方式运行，避免相对导入因当前工作目录不同而失效。

## SimpleAgent 基础对话

`demos/simple_agent_demo.py` 显式读取项目根目录 `.env` 中的统一配置：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL_ID`

仅检查配置和 Agent 初始化，不发起真实 API 请求：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.simple_agent_demo --check
```

运行两轮真实对话：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.simple_agent_demo
```

`hello-agents==0.1.1` 的原生 `SimpleAgent` 尚未提供 `add_tool` 方法，因此这个基础
Demo 中的 `CalculatorTool` 只完成初始化，计算问题仍由 LLM 回答。需要模型自主调用
工具时，使用本章已经实现的 `agents/my_simple_agent.py`。

## 工具增强 SimpleAgent（MySimpleAgent）

`agents/my_simple_agent.py` 在原生 `SimpleAgent` 上增加文本工具调用、多轮工具结果回灌、
流式响应以及工具的添加、移除和查询接口。模型按
`[TOOL_CALL:tool_name:parameters]` 输出动作，Agent 执行工具后把结果写回上下文，再生成
最终回答。

```python
from hello_agents import HelloAgentsLLM, ToolRegistry
from hello_agents.tools import CalculatorTool
from agents.my_simple_agent import MySimpleAgent

registry = ToolRegistry()
registry.register_tool(CalculatorTool())
agent = MySimpleAgent("工具助手", HelloAgentsLLM(), tool_registry=registry)
print(agent.run("请调用 python_calculator 计算 18 * 7"))
```

## 自定义 LLM 与 ModelScope 扩展

`agents/my_llm.py` 演示如何在不修改 `hello-agents` 库源码的前提下，通过继承
`HelloAgentsLLM` 扩展新供应商：

- `MyLLM()`：自动读取项目根目录 `.env` 中的 `LLM_API_KEY`、
  `LLM_BASE_URL` 和 `LLM_MODEL_ID`，并根据配置识别供应商。
- `MyLLM(provider="modelscope")`：显式走 ModelScope 自定义分支，优先读取 `MODELSCOPE_API_KEY`，
  未设置时回退到项目统一的 `LLM_API_KEY`，使用 ModelScope 的 OpenAI 兼容接口
  （`https://api-inference.modelscope.cn/v1/`）。
- 其他 `provider` 值：通过 `super().__init__(...)` 完全复用父类逻辑，
  原有 OpenAI/DeepSeek/Qwen 等供应商不受影响。

### 配置

在项目根目录 `.env` 中添加：

```dotenv
# 可选：不设置时使用统一的 LLM_API_KEY
MODELSCOPE_API_KEY="your-modelscope-api-key"
# 可选：单独指定 ModelScope 模型，避免与 LLM_MODEL_ID（DeepSeek）冲突
MODELSCOPE_MODEL_ID="Qwen/Qwen2.5-VL-72B-Instruct"
```

### 运行

使用项目统一配置检查 MyLLM 初始化，不调用 API：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.custom_llm_demo --check
```

使用项目统一配置真实调用（`think` 等方法均从父类继承，无需重写）：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.custom_llm_demo
```

## 改进版 ReAct Agent（MyReActAgent）

`agents/my_react_agent.py` 在不修改 `hello-agents` 库源码的前提下，重写框架自带的
`ReActAgent`：保持「思考 → 行动 → 观察 → Finish」的核心循环不变，重点改进四点：

1. 提示词 `MY_REACT_PROMPT`：不再让模型加粗回显 Thought/Action，并明确禁止代码
   围栏、开场白与结语，显著减少「解析不到 Action」的格式错误；
2. 解析更健壮：`_parse_output` / `_parse_action` 容忍加粗、代码围栏、跨行思考、
   一段输出含多组动作与行尾附注，同时兼容 `思考/行动` 中文标记；
3. 出错自纠：模型没给出可用 Action（或格式无效）时，不再像父类那样直接终止，
   而是把格式要求作为 Observation 回灌，让它用剩余步数自我纠正；
   `Finish[]` 空答案同样会被要求补全；
4. 防幻觉（第 7、8 条，经 A/B 实验验证）：Finish 必须只依据本轮 Observation，
   未在搜索结果中出现的信息（如官网地址）要如实说明「未找到」，不得编造新网址。

### 文件

- `agents/my_react_agent.py`：改进版提示词模板与 `MyReActAgent` 实现。
- `demos/react_agent_demo.py`：命令行示例；`--check` 只检查配置，不调用 API。

### 运行

检查配置（不调用 API）：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.react_agent_demo --check
```

真实调用（需 `.env` 中的 LLM 配置；配置了 `TAVILY_API_KEY`/`SERPAPI_API_KEY` 时会
额外注册 `search` 工具）：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.react_agent_demo
```

在代码中直接使用：

```python
from hello_agents import HelloAgentsLLM, ToolRegistry
from hello_agents.tools import CalculatorTool
from agents.my_react_agent import MyReActAgent

llm = HelloAgentsLLM()
registry = ToolRegistry()
registry.register_tool(CalculatorTool())

agent = MyReActAgent("助手", llm, registry, max_steps=5)
print(agent.run("请计算 2+3*4 并用中文作答"))
```

> 提示：本机默认代码页为 GBK，若把输出重定向到文件时遇到 `UnicodeEncodeError`
> （框架与 Agent 大量打印 ✅/🤖 等 emoji），先执行 `$env:PYTHONIOENCODING='utf-8'`
> 再运行命令；直接在 PowerShell 终端运行时无需设置。

## 通用 Reflection Agent

`agents/my_reflection_agent.py` 根据第四章 Reflection Agent 的结构实现了通用的
“初始回答 -> 反思 -> 改进”循环。它使用题目给出的 `initial`、`reflect` 和 `refine`
三段提示词，不假设输出是代码，因此可用于学习计划、文章、总结、翻译、方案设计等
文本任务。每次 `run()` 会重置本次任务的短期记忆，但会把最终问答保留在 Agent 历史中。

### 离线验证

默认 demo 使用 FakeLLM，不需要 API Key，任务是设计机器人专业学生的一周学习计划：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.reflection_agent_demo
```

运行离线单元测试：

```powershell
F:\my-hello-agent\.conda\python.exe -m unittest discover -s .\tests -p "test_*.py" -v
```

### 真实 LLM 调用

确认根目录 `.env` 已配置 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL_ID` 后，显式传入
`--live`：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.reflection_agent_demo --live
```

`max_iterations` 表示反思与改进的最多轮数，不包含初始回答。也可以通过
`custom_prompts` 部分覆盖三段模板，并通过 `get_trajectory()` 获取本次任务的完整轨迹。
