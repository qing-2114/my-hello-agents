# FastAPI 实验：把旅行 Agent 暴露为服务

这个实验复用 `1.3-experiment` 的旅行助手，重点观察 **Agent 逻辑和 HTTP 接口层如何分离**。
项目来源仍是 [Datawhale Hello Agents](https://hello-agents.datawhale.cc/)。

## 实验目标

1. 用 FastAPI 接收 JSON 请求并自动校验参数。
2. 通过 `session_id` 把多轮对话路由到同一个 `SessionState`。
3. 复用已有的天气、景点和模拟票务工具，不复制 Agent 主循环。
4. 用可注入的 StubLLM 做确定性 HTTP 测试。
5. 观察真实 API 接入时，FastAPI、Agent、LLM 和工具之间的边界。

## 当前版本的边界

本实验先实现内存会话和非流式 REST 接口，便于理解基础链路：

```text
客户端 → FastAPI → AgentService → 1.3-experiment/session_agent.py
                              ↓
                    大模型 / 天气 / 景点 / 票务工具
```

服务重启后内存会话会清空。SQLite 持久化、SSE 流式输出、鉴权、限流和重试属于后续迭代，不在第一版混入。

## 启动服务

在项目根目录执行：

```powershell
& ".\.conda\python.exe" -m uvicorn app:app --app-dir ".\FASTAPI_Experiment" --reload
```

打开接口文档：<http://127.0.0.1:8000/docs>

## 手动调用

创建会话：

```powershell
$session = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/sessions" `
  -Method Post `
  -ContentType "application/json" `
  -Body (@{ user_id = "demo-user" } | ConvertTo-Json)

$sessionId = $session.session_id
```

发送一轮消息：

```powershell
$body = @{ message = "我周末想去杭州旅游"; feedback_type = "none" } | ConvertTo-Json
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/sessions/$sessionId/turns" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

明确拒绝上一条推荐时，把计数交给请求体：

```powershell
$body = @{ message = "人太多了，请换一个"; feedback_type = "reject" } | ConvertTo-Json
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/sessions/$sessionId/turns" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

## 离线测试

```powershell
& ".\.conda\python.exe" -m unittest discover `
  -s ".\FASTAPI_Experiment" -p "test_*.py" -v
```

测试使用 StubLLM，只验证 HTTP 路由、Pydantic 校验、会话隔离和已有 `SessionState` 的接线，不能作为真实模型成功的结论。

## 下一步迭代

1. 把 `1.3-experiment` 提取成正常的 `travel_agent` Python 包，移除导入桥接。
2. 给 `SessionState` 增加 `to_dict/from_dict` 和 schema 版本，接入 SQLite。
3. 将 Agent 事件从 `print` 改成回调，增加 `POST /turns/stream` SSE。
4. 增加请求 ID 和 `recommendation_id` 幂等，避免网络重试重复计数。
5. 在真实 API 冒烟测试中检查天气工具、模型调用和错误降级。
