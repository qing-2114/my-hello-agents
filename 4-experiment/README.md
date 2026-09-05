# 第四章实验：基础 LLM 调用与 ReAct 循环

`llm_client.py` 封装了一个默认使用流式响应的 OpenAI 兼容客户端，提供
`HelloAgentsLLM.think(messages)` 方法。

配置方式：

1. 将 `.env.example` 复制为 `4-experiment/.env`，填写 `LLM_MODEL_ID`、
   `LLM_API_KEY`、`LLM_BASE_URL` 和可选的 `LLM_TIMEOUT`；或
2. 直接复用实验 1-3 的 `1.3-experiment/.env`，使用其中的
   `DEEPSEEK_MODEL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`。

运行示例：

```powershell
F:\my-hello-agent\.conda\python.exe .\4-experiment\llm_client.py
```

未配置 API 密钥时，脚本会提示配置错误，不会发起网络请求。

## ReAct Agent

`ReAct/agent.py` 实现了教程中的 Thought → Action → Observation 循环：模型可
选择已注册工具，工具返回的 Observation 会追加到当前回合上下文；模型输出
`Finish[最终答案]` 时结束本回合。当前默认注册的工具是 `ReAct/tools.py` 中的
SerpApi 搜索，搜索密钥从 `1.3-experiment/.env` 的 `SERPAPI_API_KEY` 读取。

运行命令：

```powershell
F:\my-hello-agent\.conda\python.exe .\4-experiment\ReAct\agent.py
```

离线测试使用 Fake LLM 和本地工具函数，不会调用模型或搜索 API，覆盖工具结果回灌、
直接 Finish、格式错误和最大步数边界：

```powershell
F:\my-hello-agent\.conda\python.exe -m unittest discover -s .\4-experiment\ReAct -p "test_*.py" -v
```
