# 实验 3-2：本地调用 Qwen1.5-0.5B-Chat

本实验对应 Datawhale「Hello Agents」第三章 3.2.3 节，演示使用
`transformers` 在本地加载 `Qwen/Qwen1.5-0.5B-Chat`，应用对话模板并生成回答。
项目来源：<https://hello-agents.datawhale.cc/>。

## 运行

在项目根目录 `F:\my-hello-agent` 执行：

```powershell
F:\my-hello-agent\.conda\python.exe .\3.2-experiment\qwen_chat.py
```

首次运行会从 Hugging Face 下载模型（需要网络，约数百 MB 到 1 GB 级别，具体以仓库文件为准），
之后会复用本机缓存。脚本会自动选择 CUDA；当前项目环境已验证 CUDA 可用。

指定问题和生成长度：

```powershell
F:\my-hello-agent\.conda\python.exe .\3.2-experiment\qwen_chat.py `
  --prompt "请用三句话解释什么是Transformer。" `
  --max-new-tokens 128
```

实验采样参数对比（默认是不采样的贪心解码）：

```powershell
F:\my-hello-agent\.conda\python.exe .\3.2-experiment\qwen_chat.py --sample --temperature 0.7 --top-p 0.9
```

固定同一提示词运行多次，比较默认模式与 `--sample` 模式的回答稳定性和多样性即可。

## 本次运行记录（2026-09-04）

- 默认贪心模式：在 `cuda`（NVIDIA GeForce RTX 4050 Laptop GPU）上成功加载并生成中文回答。
- 采样模式：`--sample --temperature 0.7 --top-p 0.9 --max-new-tokens 32` 成功运行；输出与贪心模式存在差异。
- 首次下载的 `model.safetensors` 约 1.24 GB；模型文件已进入 Hugging Face 本地缓存。

## 实验边界

- 已实现并验证：模型加载代码、Qwen 对话模板、输入编码、截去输入 token、回答解码，以及贪心/采样两种生成路径。
- 没有模型缓存或网络不可用时，脚本会在加载阶段报错；可先在网络正常时完成首次下载。
- `--sample` 只在显式指定时启用；不指定时与教程示例一致，不传 `temperature` 和 `top_p`。
