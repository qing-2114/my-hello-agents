# AgentScope 2.x 三国狼人杀

本实验基于 Datawhale「Hello Agents」第六章的三国狼人杀案例重新设计，
保留项目来源：<https://hello-agents.datawhale.cc/>。

实现使用当前 AgentScope `2.0.7.post1`。AgentScope 2.x 已不再公开教程
1.x 中的 `ReActAgent`、`MsgHub` 和 `fanout_pipeline`，因此本实验使用：

- `Agent` 与 `ReActConfig` 创建真实模型玩家；
- `UserMsg`、`AssistantMsg` 作为所有交互的统一载体；
- 显式消息投递模拟狼人私密频道和白天公开频道；
- `asyncio.gather` 并发收集夜间击杀票和白天放逐票；
- Pydantic `structured_schema` 约束模型的讨论、查验、用药和投票行为。

## 游戏阵容

固定六人阵容便于观察和复现实验：

| 三国人物 | 游戏身份 | 人物特点 |
| --- | --- | --- |
| 孙权 | 狼人 | 年轻果决，善于权衡 |
| 周瑜 | 狼人 | 才思敏捷，谋略缜密 |
| 曹操 | 预言家 | 善察人心，言辞犀利 |
| 张飞 | 女巫 | 豪爽刚烈，直截了当 |
| 司马懿 | 村民 | 深谋远虑，善于隐忍 |
| 赵云 | 村民 | 忠勇沉着，言简意赅 |

规则状态由 Python 控制器裁定，模型只负责发言和提出行动。这样能够保证：

- 狼人不能击杀狼人同伴；
- 玩家不能投自己或死亡玩家；
- 女巫的解药和毒药各只能使用一次；
- 预言家查验结果只写入自己的上下文；
- 同票时无人放逐；
- 狼人全灭或狼人数量达到其他玩家数量时正确结束游戏。
- 单个模型调用失败时，该玩家本阶段切换到合法的安全决策，游戏继续推进。

## 安装

项目统一使用 `F:\my-hello-agent\.conda`：

```powershell
F:\my-hello-agent\.conda\python.exe -m pip install -r F:\my-hello-agent\6-experiment\AgentScope\requirements.txt
```

## 离线演示

离线模式不读取密钥，也不会发送 API 请求，适合先验证完整终端流程：

```powershell
F:\my-hello-agent\.conda\python.exe F:\my-hello-agent\6-experiment\AgentScope\main.py --demo --max-rounds 1
```

## 真实模型运行

默认模式读取项目根目录 `F:\my-hello-agent\.env` 中已有的：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL_ID`

```powershell
F:\my-hello-agent\.conda\python.exe F:\my-hello-agent\6-experiment\AgentScope\main.py --max-rounds 3
```

真实模式每个阶段都会调用模型，一局会产生多次 API 请求和相应费用。程序不会打印
或写入 API Key。若 `LLM_BASE_URL` 指向 DeepSeek，则使用 AgentScope 2.x 原生
`DeepSeekChatModel`；其他 OpenAI 兼容地址使用 `OpenAIChatModel`。

## 测试

```powershell
F:\my-hello-agent\.conda\python.exe -m unittest discover -s F:\my-hello-agent\6-experiment\AgentScope -p "test_*.py" -v
```

测试为纯离线测试，不会调用真实模型。
