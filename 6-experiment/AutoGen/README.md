# AutoGen 软件开发团队实验

项目来源：<https://hello-agents.datawhale.cc/>。

本实验使用 AutoGen AgentChat 0.7.5 的 `RoundRobinGroupChat`，按照固定顺序组织四个角色：

1. `ProductManager`：把比特币价格应用需求整理为计划和验收标准。
2. `Engineer`：通过受限文件工具在 `generated_app` 中实际编写 HTML/CSS/JavaScript。
3. `CodeReviewer`：读取真实文件并运行静态测试，提出审查意见。
4. `UserProxy`：自动执行最终验收；通过时返回 `APPROVE`，否则反馈问题并进入下一轮。

团队持续按上述顺序轮询，直到 UserProxy 批准，或达到消息数上限。文件工具拒绝目录穿越，
模型不能通过它们写到 `generated_app` 以外，也不会获得 `.env` 中的 API Key。
运行时终端会按角色实时显示 `TextMessage`，并隐藏冗长的模型思考片段和底层工具事件。

## 环境安装

项目根目录 `.env` 应配置已有的 OpenAI 兼容接口：

```dotenv
LLM_MODEL_ID=your-model-id
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-openai-compatible-endpoint
LLM_TIMEOUT=60
```

依赖安装到项目已有 `.conda` 环境：

```powershell
& 'F:\my-hello-agent\.conda\python.exe' -X utf8 -m pip install -r 'F:\my-hello-agent\6-experiment\AutoGen\requirements.txt'
```

## 运行团队

```powershell
& 'F:\my-hello-agent\.conda\python.exe' -X utf8 'F:\my-hello-agent\6-experiment\AutoGen\team.py'
```

默认使用交互式 `UserProxy`。轮到用户代理时，终端会显示 `Enter your response:`：输入反馈会让
团队继续下一轮，确认结束时输入 `TERMINATE`。程序最后会打印参与智能体数量和完成状态摘要。

如需无人值守运行并让验收器自动决定是否批准：

```powershell
& 'F:\my-hello-agent\.conda\python.exe' -X utf8 'F:\my-hello-agent\6-experiment\AutoGen\team.py' --auto-approve
```

默认最多 13 条群聊消息：1 条初始任务加最多三轮完整的四角色流程。调试时可跳过外部行情连通性检查：

```powershell
& 'F:\my-hello-agent\.conda\python.exe' -X utf8 'F:\my-hello-agent\6-experiment\AutoGen\team.py' --no-live-check --max-messages 9
```

运行会调用真实 LLM API，并可能产生费用。生成结果位于 `generated_app`。在该目录启动静态服务器：

```powershell
& 'F:\my-hello-agent\.conda\python.exe' -m http.server 8000 --directory 'F:\my-hello-agent\6-experiment\AutoGen\generated_app'
```

然后访问 <http://localhost:8000>。不要直接双击 HTML；浏览器对 `file://` 页面可能施加额外限制。

## 离线验证

以下命令不调用 LLM，也不请求行情 API：

```powershell
& 'F:\my-hello-agent\.conda\python.exe' -X utf8 -m unittest discover -s 'F:\my-hello-agent\6-experiment\AutoGen' -p 'test_*.py' -v
```

参考：[AutoGen AgentChat 安装](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/installation.html)、
[RoundRobinGroupChat API](https://microsoft.github.io/autogen/stable/reference/python/autogen_agentchat.teams.html)、
[Human-in-the-Loop](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/human-in-the-loop.html)。
