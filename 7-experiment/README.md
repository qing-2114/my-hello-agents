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
│   ├── my_reflection_agent.py
│   └── my_plan_solve_agent.py
├── tools/                  # 自定义工具
│   ├── my_calculator_tool.py
│   ├── my_advanced_search.py
│   ├── tool_chain_manager.py
│   └── async_tool_executor.py
├── core/                   # 基础抽象、配置和消息模型
│   ├── agent.py
│   ├── config.py
│   └── message.py
├── demos/                  # 可直接运行的命令行示例
│   ├── simple_agent_demo.py
│   ├── custom_llm_demo.py
│   ├── react_agent_demo.py
│   ├── reflection_agent_demo.py
│   ├── calculator_tool_demo.py
│   ├── tool_chain_demo.py
│   └── async_tool_demo.py
├── tests/                  # 离线单元测试与真实 API 冒烟测试
│   ├── test_my_reflection_agent.py
│   ├── test_plan_solve_agent.py
│   ├── test_calculator_tool.py
│   ├── test_my_calculator.py
│   ├── test_my_advanced_search.py
│   ├── test_advanced_search.py
│   ├── test_tool_chain.py
│   └── test_async_tool_executor.py
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

## 改进版 Plan-and-Solve Agent（MyPlanAndSolveAgent）

`agents/my_plan_solve_agent.py` 在第四章 Plan-and-Solve 的「先规划、再逐步执行」主流程
之上做四点改进，可以直接替换第四章的 `PlanAndSolveAgent`：

1. 提示词（对应第四章的 `DEFAULT_PLANNER_PROMPT` / `DEFAULT_EXECUTOR_PROMPT`）：
   `MY_PLANNER_PROMPT` 要求步骤原子化、显式引用前序结果、总步数控制在 2-5 步、
   不在计划里提前给出答案、最后一步必须回答原始问题；`MY_EXECUTOR_PROMPT` 要求只输出
   当前步骤结论、直接引用历史结果而不重算、先写算式再给结果、只使用题目与历史中
   出现过的数据，最后一步必须完整回答原问题。
2. 解析更健壮：`extract_plan()` 兼容带 python/json 标注或没有标注的代码围栏、无围栏的
   裸列表，以及「1. 步骤」/「- 步骤」形式的列表；步骤描述内部出现方括号也能正确配平。
3. 出错自纠：计划解析失败时把格式要求回灌给模型重新规划（`max_plan_attempts`），仍失败
   时默认退回「单步直接作答」（`allow_direct_fallback=False` 可关闭并保持第四章的终止
   行为）；执行阶段拒绝空响应并重试（`max_step_attempts`），避免空结果污染后续步骤。
4. 过程可追溯：`get_plan()` 返回最近一次实际执行的计划，`get_trajectory()` 返回逐步结果，
   便于第七章的评估环节记录完整轨迹。

### 真实 API 测试

`tests/test_plan_solve_agent.py` 本身就是可直接运行的真实 API 测试，需先确认根目录 `.env`
中的 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL_ID`：

```powershell
F:\my-hello-agent\.conda\python.exe .\7-experiment\tests\test_plan_solve_agent.py
```

脚本会依次打印生成的计划、最终答案、逐步执行轨迹和对话历史条数；真实调用放在
`main()` 中并由 `if __name__ == "__main__":` 触发，因此 `unittest discover` 导入该文件时
不会发起 API 请求。

在代码中直接使用（`agents` 目录在 `sys.path` 上时两种导入方式都可以）：

```python
from hello_agents.core.llm import HelloAgentsLLM
from my_plan_solve_agent import MyPlanAndSolveAgent
# 或者：from agents.my_plan_solve_agent import MyPlanAndSolveAgent

agent = MyPlanAndSolveAgent(name="我的规划执行助手", llm=HelloAgentsLLM())
print(agent.run("一个水果店周一卖出了15个苹果……"))
print(agent.get_plan())
print(agent.get_trajectory())
```

## 自定义计算器工具（函数注册）

`tools/my_calculator_tool.py` 演示如何在不继承 `Tool` 的前提下，用
`ToolRegistry.register_function` 把纯函数注册成工具。计算走安全的 AST 求值，
只允许 `+`、`-`、`*`、`/`、一元负号、`sqrt()` 和常量 `pi`，不执行任意 Python 代码。

```python
from tools.my_calculator_tool import create_calculator_registry, my_calculate

print(my_calculate("2 + 3 * 4"))          # 14
print(my_calculate("sqrt(16)"))           # 4.0

registry = create_calculator_registry()
print(registry.execute_tool("my_calculator", "(15 + 9) * 3"))  # 72
```

直接运行工具文件会打印若干本地样例，不调用 LLM：

```powershell
F:\my-hello-agent\.conda\python.exe .\7-experiment\tools\my_calculator_tool.py
```

离线单元测试：

```powershell
F:\my-hello-agent\.conda\python.exe -m unittest discover -s .\7-experiment\tests -p "test_calculator_tool.py" -v
```

仅检查本地计算、工具注册和根目录 `.env`，不调用 LLM：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.calculator_tool_demo --check
```

真实 API：`MySimpleAgent` 按 `[TOOL_CALL:my_calculator:表达式]` 调用该工具。
需先确认根目录 `.env` 已配置 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL_ID`：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.calculator_tool_demo
```

或运行测试文件中的冒烟入口：

```powershell
F:\my-hello-agent\.conda\python.exe .\7-experiment\tests\test_calculator_tool.py
```

教程式脚本 `tests/test_my_calculator.py` 会先本地跑一组四则运算和 `sqrt`，再用
`HelloAgentsLLM.think` 把 `sqrt(16) + 2 * 3` 的工具结果转成自然语言（真实 API）：

```powershell
F:\my-hello-agent\.conda\python.exe .\7-experiment\tests\test_my_calculator.py
```

## 自定义高级搜索工具（多源整合）

`tools/my_advanced_search.py` 用 `ToolRegistry.register_function` 注册
`advanced_search`：优先 Tavily，失败再回退 SerpApi。密钥只从项目根目录 `.env`
的 `TAVILY_API_KEY` / `SERPAPI_API_KEY` 读取。

```python
from tools.my_advanced_search import create_advanced_search_registry

registry = create_advanced_search_registry()
print(registry.execute_tool("advanced_search", "Datawhale Hello Agents"))
```

离线单元测试（空查询和注册表，不访问搜索服务）：

```powershell
F:\my-hello-agent\.conda\python.exe -m unittest discover -s .\7-experiment\tests -p "test_my_advanced_search.py" -v
```

真实搜索冒烟：

```powershell
F:\my-hello-agent\.conda\python.exe .\7-experiment\tests\test_my_advanced_search.py
```

教程式脚本 `tests/test_advanced_search.py` 会依次搜索「Python编程语言的历史」
「人工智能的最新发展」「2024年科技趋势」，再检查配置并打印工具描述：

```powershell
F:\my-hello-agent\.conda\python.exe .\7-experiment\tests\test_advanced_search.py
```

## 工具链式调用

`tools/tool_chain_manager.py` 把已注册工具按顺序串起来。每一步的输入是模板字符串，
可以用 `{input}` 引用初始问题，用上一步的 `output_key` 引用中间结果。

```python
from tools.tool_chain_manager import (
    ToolChainManager,
    create_math_chain,
    create_research_chain,
    create_toolchain_registry,
)
from tools.my_calculator_tool import create_calculator_registry

# 纯计算链：先算 3+4，再把 7 乘以 2
registry = create_calculator_registry()
manager = ToolChainManager(registry)
manager.register_chain(create_math_chain())
print(manager.execute_chain("double_calculate", "3 + 4"))  # 14

# 研究链：先 search，再把结果交给 my_calculator
registry = create_toolchain_registry()
manager = ToolChainManager(registry)
manager.register_chain(create_research_chain())
print(manager.execute_chain("research_and_calculate", "Python 是哪一年诞生的"))
```

`create_research_chain` 按教程把搜索结果整段交给计算器；计算器只接受数学表达式，
因此第二步通常会返回「计算失败，请检查表达式格式」，这是在演示变量替换，不是计算错误。

离线单元测试（纯计算链，不访问搜索服务）：

```powershell
F:\my-hello-agent\.conda\python.exe -m unittest discover -s .\7-experiment\tests -p "test_tool_chain.py" -v
```

仅检查计算链，不调用搜索：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.tool_chain_demo --check
```

真实搜索链（需 `TAVILY_API_KEY` 或 `SERPAPI_API_KEY`）：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.tool_chain_demo
F:\my-hello-agent\.conda\python.exe .\7-experiment\tests\test_tool_chain.py
```

## 异步并行工具执行

`tools/async_tool_executor.py` 把同步的 `registry.execute_tool` 放到线程池里，
用 `asyncio.gather` 同时等待多个任务。教程示例会并行跑两次搜索和两次计算。

```python
import asyncio
from tools.async_tool_executor import AsyncToolExecutor
from tools.my_calculator_tool import create_calculator_registry

registry = create_calculator_registry()
executor = AsyncToolExecutor(registry)
results = asyncio.run(executor.execute_tools_parallel([
    {"tool_name": "my_calculator", "input_data": "2 + 2"},
    {"tool_name": "my_calculator", "input_data": "sqrt(16)"},
]))
executor.close()
print(results)  # ['4', '4.0']
```

离线单元测试（只并行计算，不访问搜索服务）：

```powershell
F:\my-hello-agent\.conda\python.exe -m unittest discover -s .\7-experiment\tests -p "test_async_tool_executor.py" -v
```

仅检查计算器并行，不调用搜索：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.async_tool_demo --check
```

真实并行搜索 + 计算（需 `TAVILY_API_KEY` 或 `SERPAPI_API_KEY`）：

```powershell
F:\my-hello-agent\.conda\python.exe -m demos.async_tool_demo
F:\my-hello-agent\.conda\python.exe .\7-experiment\tests\test_async_tool_executor.py
```
