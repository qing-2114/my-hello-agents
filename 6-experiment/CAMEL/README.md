# CAMEL：AI 心理学家与 AI 作家协作电子书

本实验使用 CAMEL 的 `RolePlaying` 构建两个角色：作家负责按目录逐章发出
`Instruction / Input`，心理学家负责以 `Solution / Next request` 交付可出版章节，
最终生成《拖延症心理学》Markdown 电子书和完整协作轨迹。

项目学习来源：<https://hello-agents.datawhale.cc/>  
CAMEL 官方仓库：<https://github.com/camel-ai/camel>  
依赖固定为 2026-09-06 的最新稳定版 `camel-ai==0.2.90`（不采用预发布版本）。

## 安装

在项目根目录执行：

```powershell
F:\my-hello-agent\.conda\python.exe -m pip install -r .\6-experiment\CAMEL\requirements.txt
```

程序读取项目根目录 `.env`，需要以下 OpenAI 兼容配置：

```dotenv
LLM_API_KEY=...
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL_ID=your-model-name
```

可选配置为 `CAMEL_TEMPERATURE`（默认 `0.4`）和 `CAMEL_MAX_TOKENS`
（默认 `2600`）。程序不会打印密钥。

## 运行

```powershell
$env:PYTHONIOENCODING='utf-8'
F:\my-hello-agent\.conda\python.exe .\6-experiment\CAMEL\main.py
```

终端会实时按“协作任务 → 具体任务描述 → 作家 → 心理学家”的顺序显示完整过程。
展示层会固定补齐 `Instruction / Input / Solution / Next request` 字段，因此即使模型
偶尔省略协议标签，终端仍保持统一、易读的协作轨迹；传给 CAMEL 的仍是模型原始消息。
生成文件：

- `output/拖延症心理学.md`：去掉协作协议包装后的电子书正文；
- `output/协作轨迹.md`：保留每轮 `Instruction / Input / Solution / Next request`。

大模型对篇幅的遵循存在波动，因此程序会统计 CJK 汉字数，并明确提示是否落在
8000–10000 字目标区间。每完成一章都会立即更新两个文件；模型提供方偶发返回
空消息时默认重试 3 次，也可通过 `--retries` 调整。内容为心理科普，不替代专业
诊断或治疗。

若运行被中断，或作家要求心理学家补写了同名章节，可从轨迹重新组装；同名章节
会以后一次交付覆盖前一次：

```powershell
F:\my-hello-agent\.conda\python.exe .\6-experiment\CAMEL\ebook.py --rebuild
```

## 离线测试

```powershell
F:\my-hello-agent\.conda\python.exe -m unittest discover -s .\6-experiment\CAMEL -p "test_*.py" -v
```
