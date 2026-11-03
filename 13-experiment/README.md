# 第十三章实验

本目录用于 Datawhale「Hello Agents」教程第十三章的学习与实践。

教程来源：<https://hello-agents.datawhale.cc/>

## 目录约定

按实际实验主题建立子目录，示例程序放在主题目录的 `demos/`，对应测试放在 `tests/`，测试文件使用 `test_*.py` 命名。跨主题共享内容按需放在 `common/`，不预先创建空目录。

## 运行方式

自主实现位于 `trip-assistant/`，后端代码放在 `trip-assistant/demos/backend/app/`，前端放在 `trip-assistant/demos/frontend/`，测试放在 `trip-assistant/tests/`。已完成数据模型及四 Agent 顺序协作实现，运行与验证方式见 [自主实现说明](trip-assistant/README.md)。下列启动命令用于官方参考样例。

官方项目位于 `helloagents-trip-planner/`，来源：<https://github.com/datawhalechina/hello-agents/tree/main/code/chapter13/helloagents-trip-planner>。

下载版本：`36f583c233ea5cee4537ef93455702b55053af18`，共 35 个源文件。保留官方目录结构方便对照教程。

本章独立 Python 环境为 `13-experiment/.venv`（Python 3.12，hello-agents 0.2.9）。后端 `.env` 已从项目根目录配置复制 LLM、高德和 Unsplash 所需字段；前端 `.env` 配置 JS API Key 和安全密钥，均被 Git 忽略。修改根配置后需同步后端并重启服务。

在项目根目录打开两个 PowerShell 终端，分别运行：

```powershell
# 终端一：后端
cd 13-experiment/helloagents-trip-planner/backend
../../.venv/Scripts/python.exe -X utf8 -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

```powershell
# 终端二：前端（5173 已被本机其他项目使用）
cd 13-experiment/helloagents-trip-planner/frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

访问 <http://127.0.0.1:5174>，后端文档为 <http://127.0.0.1:8000/docs>。服务已经在后台启动，再次手动启动前请先停止已有实例。

本地适配：前端加载高德 JS SDK 前设置安全密钥；两处高德 MCP 启动命令增加 `--with pydantic==2.10.6`，解决上游 MCP 包导入不兼容；修复 `/api/trip/health` 引用了旧版单 Agent 属性的问题。前端 CORS 增加本机 5174 端口。

前端 JS Key 和安全密钥会随浏览器请求使用；本配置用于本机快速体验。

## 验证记录

- 2026-11-03：初始化章节目录和 README，尚未添加实验代码。
- 2026-11-03：下载官方代码；安装前后端依赖，`npm.cmd run build` 通过，首页和后端 `/health` 可访问。
- 真实 API：高德地理编码返回 `status=1, info=OK`；Unsplash 搜图返回 HTTP 200；真实 LLM 北京一日游规划成功，返回故宫博物院、景山公园，非上游备用模板。
- 高德 MCP 完成连接并发现 16 个工具。完整行程结果保存为本地忽略文件 `quick-experience-result.json`。前端结果页地图仍需实际生成行程后验证。
