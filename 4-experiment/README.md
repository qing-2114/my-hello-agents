# 第四章实验：基础 LLM 调用

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
