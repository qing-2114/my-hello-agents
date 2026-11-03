# 第十四章实验：深度研究智能体

本目录用于 Datawhale「Hello Agents」教程第十四章的学习与实践。

教程来源：<https://hello-agents.datawhale.cc/>

## 官方源码

- 项目：`helloagents-deepresearch/`
- GitHub：<https://github.com/datawhalechina/hello-agents/tree/main/code/chapter14/helloagents-deepresearch>
- 上游仓库：<https://github.com/datawhalechina/hello-agents>
- 获取版本：`36f583c233ea5cee4537ef93455702b55053af18`
- 获取方式：浅克隆上游仓库，通过 sparse-checkout 获取第十四章，再复制本章项目；保留官方目录结构，与第十三章参考源码的组织方式一致。

## 目录

- `research-assistant/`：自己的版本，参照第十三章结构，包含三个研究 Agent、顺序研究流程、多后端搜索、NoteTool进度持久化、共享ToolRegistry，以及Vue全屏研究工作台和FastAPI SSE接口；前端5177、后端8003，启动及验证命令见该目录 README。
- `helloagents-deepresearch/backend/`：Python 后端、研究 Agent 与规划、搜索、总结、报告等服务。
- `helloagents-deepresearch/frontend/`：Vue + TypeScript + Vite 前端。

## 运行准备

后端依赖见 `backend/pyproject.toml`，配置模板见 `backend/.env.example`；前端依赖及命令见 `frontend/package.json`。后续本地配置应读取项目根目录已有 `.env`，不得提交密钥。

## 验证记录

- 2026-11-03：已从官方 GitHub 仓库获取本章源码，共 31 个文件；尚未安装依赖、启动服务或进行真实 API 测试。

## 本机启动

已建立独立 Python 3.12 环境 `.venv/`，安装后端依赖及 `hello-agents` 导入时需要的 `huggingface-hub`、`datasets`。前端依赖已通过 `npm ci` 安装。

在项目根目录分别运行：

```powershell
# 后端：读取根目录 .env 的 LLM 配置，使用 custom provider
14-experiment/.venv/Scripts/python.exe -X utf8 14-experiment/start_backend.py
```

```powershell
# 前端
cd 14-experiment/helloagents-deepresearch/frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5176 --strictPort
```

前端：<http://127.0.0.1:5176/>；后端文档：<http://127.0.0.1:8002/docs>；健康检查：<http://127.0.0.1:8002/healthz>。

前端本地配置 `.env.local` 指向 8002 端口。研究笔记和验证输出保存到被 Git 忽略的 `.local/`。根配置存在 Tavily Key 时默认使用 Tavily，否则使用 DuckDuckGo；页面可选择搜索服务。

- 2026-11-03：前端构建通过，前端 HTTP 200，后端健康检查返回 `status=ok`。首次真实研究请求因模型供应商返回 HTTP 503（服务繁忙）未完成。
