# Reflection 实验

项目来源：<https://hello-agents.datawhale.cc/>。

`agent.py` 中的 `ReflectionAgent` 调用 `prompts.py` 的三个模板，先生成代码，
再循环进行评审和优化；`memory.py` 保存本次任务的代码与反馈。
每次 `run()` 都会清空上一次任务的记忆。

在项目根目录执行默认素数任务（会调用真实 API）：

```powershell
& 'F:\my-hello-agent\.conda\python.exe' -X utf8 'F:\my-hello-agent\4-experiment\Reflection\agent.py'
```

可通过位置参数指定任务，通过 `--max-iterations 3` 设置最多反思与优化三轮。
初次生成不计入轮数，因此默认最多调用模型七次。
复用第四章 `llm_client.py` 的环境配置，不在源码中保存 API Key。

评审单独回答“无需改进”时提前结束，否则达到轮数上限后返回最新代码。
空响应会抛出异常并停止。返回的是代码文本，Agent 不会自动执行该代码；
模型的评审也不代表正确性验证或最优性证明。

本次手动实验的 API 原始响应、轨迹和日志保存在 `outputs` 下的时间戳目录。
直接运行上述命令只打印结果，记忆默认不落盘。
