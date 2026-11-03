# 智能旅行助手（自主实现）

基于 Datawhale「Hello Agents」第十三章学习并自行实现。

教程来源：<https://hello-agents.datawhale.cc/>。
同级 `../helloagents-trip-planner/` 为官方参考样例。

## 目录

```text
trip-assistant/
├── demos/
│   ├── backend/app/
│   │   ├── models/schemas.py  # 数据模型，从这里开始编写
│   │   ├── agents/           # 旅行规划 Agent
│   │   ├── services/         # 模型与外部工具服务
│   │   └── api/              # FastAPI 接口
│   └── frontend/             # 前端实现
└── tests/                    # test_*.py 测试
```

## 当前状态

2026-11-03：按自主设计完成 `schemas.py` 中的八个 Pydantic 模型：`Location`、`Attraction`、`Meal`、`Hotel`、`Budget`、`DayPlan`、`WeatherInfo`、`TripPlan`。保留设计中的字段、默认值、约束，以及温度字符串解析失败返回 0 的规则。

已使用本章 `.venv` 完成模型加载、JSON Schema 生成、经纬度边界拒绝、温度单位解析及 JSON 序列化往返检查。这些检查仅验证数据模型，不涉及真实 API 调用。

已实现请求模型 `TripPlanRequest`（city、start_date、end_date、days、preferences、budget、transportation、accommodation）。日期范围包含首尾，必须与 days 一致。

## 多 Agent 协作

- `demos/backend/app/agents/prompts.py`：四个专家的提示词。
- `demos/backend/app/agents/trip_planner_agent.py`：`TripPlannerAgent` 按景点搜索 → 天气查询 → 酒店推荐 → 行程规划顺序执行，解析 JSON 并校验目的地、日期、每天2–3个景点、三餐及预算加总。不合格输出交给规划 Agent 修正一次，再次失败抛出异常。
- `demos/backend/app/services/runtime.py`：显式读取项目根目录 `.env`，检查 LLM 三项配置及高德密钥，创建共享 LLM 和 MCP 工具。前三个 Agent 注册高德工具，规划 Agent 只整合信息。

提示词占位需求随每次查询传入，不在初始化时绑定城市。按当前 hello-agents 接口使用 `llm=` 和 `system_prompt=`。天气超出工具预报范围时允许缺失并要求说明，避免生成虚假天气。

从项目根目录运行真实集成验证：

```powershell
./13-experiment/.venv/Scripts/python.exe -X utf8 13-experiment/trip-assistant/tests/test_real_trip_planner.py
```

此验证会实际调用 LLM 与高德 MCP，检查一日行程、2–3 个景点、三餐及预算加总。依赖本章环境中的 hello-agents、pydantic、python-dotenv，以及可运行的 uvx。单个规划器含对话历史，请勿并发复用。

2026-11-03 验证记录更正：先前一日游测试验证了真实 LLM 输出的景点数量、三餐和预算，但测试的 StringIO 日志重定向不支持 Windows 子进程所需的 fileno，导致 MCP 发现失败后仅注册父工具，不能作为高德调用成功的证据。测试已改用临时文件处理日志，工具工厂增加必需工具发现检查，失败会明确抛错。

## 高德 MCP 接入

`app/config.py` 提供 `get_settings()`；`services/amap_service.py` 提供 `create_amap_mcp_tool()`，供三个查询 Agent 共享。当前安装版本使用 `server_command`，不接受示例中的 `command`/`args`。沿用本章已安装的 Python `amap-mcp-server`（uvx 启动，并固定其 pydantic 兼容依赖），对应密钥环境变量为 `AMAP_MAPS_API_KEY`。

工具名称设为 `amap`，因此自动展开后为 `amap_maps_text_search`、`amap_maps_weather` 等，与提示词保持一致。当前版本通过 `agent.list_tools()` 查看工具，不使用 `agent.tools`。数量由服务实际发现结果决定。

`TripPlannerAgent` 在初始化时只调用一次 `create_runtime()`，将返回值保存到 `self.llm` 和 `self.mcp_tool`。四个 Agent 共享同一 LLM，景点、天气、酒店三个 Agent 各自注册同一个 `self.mcp_tool`；每个展开工具都引用这个共享 MCP 对象。共享范围为单个规划器实例。框架在工具发现和调用时管理 MCP 会话，共享工具对象不代表始终维持同一个子进程或连接。

专项测试同时校验三个 Agent 的 LLM 对象身份、工具名称集合，以及每个展开工具的 `mcp_tool is planner.mcp_tool`。

```python
from app.services.amap_service import create_amap_mcp_tool

mcp_tool = create_amap_mcp_tool()
agent.add_tool(mcp_tool)
print(agent.list_tools())
```

真实 MCP 专项验证（实际调用景点搜索与天气，无需生成整份行程）：

```powershell
./13-experiment/.venv/Scripts/python.exe -X utf8 13-experiment/trip-assistant/tests/test_real_amap_mcp.py
```

2026-11-03 专项验证通过：实际发现并注册16个工具，真实调用北京故宫 POI 搜索及北京天气，均返回有效数据。此次未重新运行完整四 Agent 行程生成。

## Unsplash 图片与旅行接口

`services/unsplash_service.py` 提供 `search_photos()`、`get_photo_url()` 和 `enrich_trip_plan()`。根目录 `.env` 使用 `UNSPLASH_ACCESS_KEY`，通过 Authorization 请求头发送，不放入查询 URL。搜索结果保留摄影师姓名、摄影师链接及照片页面链接，供后续前端署名。景点模型现增加图片摄影师与来源链接，结果页随图片显示署名。

`api/routes/trip.py` 的 `POST /api/trip/plan` 在四 Agent 规划完成后，为缺少图片的景点按“景点名称 城市”搜索并填充图片，直接返回 `TripPlan`。已有图片保留，重复查询在单份行程内复用，搜图失败返回空结果并保留行程。关键词搜图尚未校验是否准确对应景点。

从项目根目录启动自主实现：

```powershell
./13-experiment/.venv/Scripts/python.exe -X utf8 -m uvicorn app.api.main:app --app-dir 13-experiment/trip-assistant/demos/backend --host 127.0.0.1 --port 8001
```

接口文档：<http://127.0.0.1:8001/docs>。

真实 Unsplash 验证命令：

```powershell
./13-experiment/.venv/Scripts/python.exe -X utf8 13-experiment/trip-assistant/tests/test_real_unsplash.py
```

2026-11-03：真实 Unsplash 搜图、摄影师元数据及行程图片补全验证通过；FastAPI 路由加载及 OpenAPI 响应结构检查通过。未重跑整个四 Agent HTTP 规划流程。

真实 API 测试统一读取项目根目录已有 `.env`；不在源码或测试输出中写入密钥。

## 前端类型

`demos/frontend/src/types/index.ts` 定义 `Location`、`Attraction`、`Meal`、`Hotel`、`Budget`、`DayPlan`、`WeatherInfo`、`TripPlan` 和 `TripPlanRequest`。可空字段显式允许 `null`。

API 请求中的 `preferences` 为 `string[]`，`budget` 为可选的 `number | null`，与后端一致；`TripPlanFormData` 保留文本表单所需的两个字符串字段，后续 API 服务应负责提交前转换。当前接口直接返回 `TripPlan`，无 success/data 包装。

已实现 Home.vue、Result.vue、路由、应用入口和 Vite 配置。

2026-11-03：使用本机已安装的 TypeScript 编译器进行严格模式 `--noEmit` 类型检查，通过。本步骤仅增加静态类型，无需真实 API 调用。

## 前端 API 服务

`demos/frontend/src/services/api.ts` 使用 Axios 封装 `generateTripPlan(request): Promise<TripPlan>`，请求 `POST /trip/plan` 并直接返回响应体。超时为300秒，错误继续向调用页面抛出；拦截器只打印方法、路径、状态或错误码，不打印完整请求和响应。

默认 API 地址改为同源 `/api`，Vite 开发代理转发至 `http://127.0.0.1:8001`，避免开发跨域问题；可用 `VITE_API_BASE_URL` 覆盖，部署时需配置同源反向代理或 CORS。首页直接维护偏好数组和数值预算，与 API 契约一致。

前端目录内运行 `npm.cmd install` 安装依赖，`npm.cmd run typecheck` 检查类型，`npm.cmd run build` 构建生产文件。已安装 Vue、Vue Router、Ant Design Vue、Vite、高德 SDK 和导出依赖。


## Home 与 Result 页面

从项目根目录启动后端（见上文），再进入 `13-experiment/trip-assistant/demos/frontend` 运行 `npm.cmd run dev`，访问 <http://127.0.0.1:5175/>。

- `Home.vue`：目的地、起止日期、偏好标签、交通、住宿、每人预算；自动计算包含首尾的1–30天行程，预算为非负整数，可留空。重复提交受保护，失败显示错误并恢复按钮。进度明确标注为等待估算。
- `Result.vue`：逐日景点、三餐、住宿、天气、预算和总体建议，支持无行程空状态、图片加载失败占位、重新规划。最近一次行程保存于当前标签页 sessionStorage，刷新可恢复。
- 地图从首个景点定位，按全程连续编号标记并自动适配视野；离开结果页销毁实例。可选地图配置为前端 `.env.local` 中的 `VITE_AMAP_WEB_KEY`、`VITE_AMAP_SECURITY_CODE`。本机已复用官方参考前端已有的 Web JS 配置，仅写入忽略文件。地图加载失败不影响文本行程。
- `services/export.ts`：PNG 导出与分页 A4 PDF 导出；使用跨域图片加载，地图通过服务端高德静态地图接口获取后写入导出副本，失败时改为坐标清单。长页按 A4 高度切片，卡片可能跨页；远程图片是否能导出受其网络与跨域响应影响。
- 搜图补全增加 `image_photographer`、`image_photographer_url`、`image_source_url` 可选字段，随结果展示 Unsplash 署名。原有模型字段仍保留。

2026-11-03：Vue 严格类型检查与生产构建通过；真实 Unsplash 图片补全复测通过。开发服务使用8001/5175端口，与官方样例分开。

浏览器真实联调记录：从首页提交北京一日游，经真实 LLM、高德 MCP 与 Unsplash 返回结果页，显示3个地图标记及图片署名；刷新保留行程。PNG 下载成功（1134×7588），PDF 下载成功并检查为5页。导出在当前窄窗口下采用单列布局；图片已视觉检查。


## 行程编辑与分区导航

结果页提供编辑、上移、下移、确认删除、保存和取消。编辑期间禁用导出；保存后更新 sessionStorage、地图标记与门票总价、预算总额；取消完整恢复编辑前数据。允许清空当天景点，仍保留餐饮住宿。其余预算及建议不自动重新规划，需要用户按新路线核实。

顶部固定导航定位行程概览、预算、地图、每日行程、天气；不存在的预算/天气栏目不显示导航入口。等待进度展示明确标为估算的阶段文字。

导出调用同源 `/api/map/static` 获取高德静态地图，再替换导出文档副本中的地图节点，不修改实时页面，因此无需恢复原地图。服务端持有高德 Web 服务 Key；静态图片不可用时提供坐标清单。禁用 allowTaint，PDF 保持多页裁切。

2026-11-03 本轮验证：前端严格类型检查及生产构建通过。新版预算提示词的真实 API 测试未完成：LLM 服务返回 HTTP 503（Service is too busy），在景点 Agent 首次调用阶段失败；不能将此前成功记录作为本轮验证成功。

## 备用模型

`services/llm_service.py` 为四个 Agent 的共享 LLM 增加非流式故障切换。根目录 `.env` 配置 `LLM_FALLBACK_BASE_URL`、`LLM_FALLBACK_API_KEY`、`LLM_FALLBACK_MODEL_ID`；三个字段需完整，密钥仅存于 Git 忽略的配置中。当前备用服务为 `https://api.cloudborne.cn/v1`，模型为 `deepseek-v4.1-flash-1017`，当前主模型为 `gpt-6.1-sol`，第一备用为 `deepseek-v4.1-flash-1017`，第二备用为原主模型 `deepseek-flash`。第二备用使用 `LLM_FALLBACK_2_API_KEY/BASE_URL/MODEL_ID` 配置。

主模型遇到 HTTP 408、429、5xx 或连接/超时异常时，使用相同消息调用备用模型；当前规划器后续调用继续使用备用模型，新请求重新从主模型开始。400/401/403 等配置或鉴权错误不自动切换。主模型单次超时30秒、备用60秒，禁用 SDK 自动重试，避免重复等待；整个多 Agent 请求仍可能超过前端300秒限制。当前仅支持旅行助手使用的 `invoke`，不提供流式故障切换。

验证命令：

```powershell
./13-experiment/.venv/Scripts/python.exe -X utf8 13-experiment/trip-assistant/tests/test_real_fallback_llm.py
./13-experiment/.venv/Scripts/python.exe -X utf8 13-experiment/trip-assistant/tests/test_real_trip_planner.py
```

2026-11-03：主模型 HTTP 503 故障注入后，真实备用 API 返回有效响应，故障切换验证通过；状态分类检查通过（400/401/403不切换）；配置备用模型后的真实四 Agent + 高德 MCP 一日游复测通过，包含2–3个景点、三餐及预算加总。后端8001服务已重启加载新实现。


## 完整功能验证

2026-11-03：已完成真实API、一日游浏览器全流程、两日HTTP行程、编辑保存/取消、地图、导航、PNG/PDF、窄屏与错误路径验证。详细结果和修复见 [完整验证记录](tests/VALIDATION-2026-11-03.md)。本轮已修复非法日期500、导出地图底图空白、等待超时过短及编辑后旧建议未提示的问题。

2026-11-03：按用户要求将根目录 `.env` 的主模型改为 `gpt-6.1-sol`，原主模型移至第二备用。真实主模型调用通过，确认未触发备用；此记录仅验证模型连接，不代表重新完成整套旅行流程。根目录共用配置的其他实验也会读取新的主模型。

## 香港地点与天气查询修复

2026-11-03：真实香港 MCP 地点搜索返回名称地址但省略坐标；天气以香港名称或810000查询均返回 UNKNOWN_ERROR。新增高德原始地点查询，规划器只能选取原始候选中的景点及酒店，服务端填入真实地址坐标，未匹配名称触发修正或502；地点接口不可用返回503。天气工具返回错误时强制清空 weather_info 并提示核实。北京一日真实多Agent复测通过，香港原始坐标补全和虚构名称拒绝验证通过。

## 多源天气（2026-11-03）

天气已改由 `services/weather_service.py` 查询原始服务，再由天气 Agent 基于凭据提供建议；最终 `weather_info` 由后端覆盖，模型不得补造日期或温度。天气故障不会阻断其他行程内容。

| 来源 | 范围及预报 | 认证 / 免费条件 |
| --- | --- | --- |
| 香港天文台 HKO | 香港九天天气预报 | 无需 Key，政府开放数据；显示来源链接 |
| Open-Meteo | 全球，最多16天（含当天），目的地本地时区 | 无需 Key；免费服务限非商业用途，少于每日10,000、每小时5,000、每分钟600次调用；CC BY 4.0署名 |
| 高德天气 | 保留现有来源，以实际返回日期为准 | 复用根目录既有 Key |

自动策略：香港优先 HKO，再用 Open-Meteo 补缺；其他城市先高德，再 Open-Meteo。首页可选择优先来源，不可用或日期不全时自动切换；HKO 不会用于非香港城市。不同日期保留各自来源，不覆盖先取得的有效预报。超过所有源预报范围的日期保持缺失并明确列出，不用历史天气冒充未来预报。

HKO 与 Open-Meteo 返回的高低温表示全天最高/最低，并非真实白天/夜间分段预报；通过 `temperature_basis=daily_range` 标识，前端按实际含义展示。`WeatherInfo` 增加 `source`、`source_url`；`TripPlan` 增加 `weather_notes`；请求新增可选 `weather_source=auto|hko|open_meteo|amap`，旧请求默认自动。

独立查询端点无需先获得高德景点结果，可查询海外城市天气：

```text
GET /api/weather/forecast?city=香港&start_date=2026-11-04&end_date=2026-11-07&source=auto
```

常用中文海外城市增加国家限定及别名，防止把“东京”“伦敦”定位到其他同名城市；更多重名目的地建议使用英文及明确目的地。全球天气源不代表酒店、地图或行程搜索的海外覆盖已扩展。

真实测试：

```powershell
./13-experiment/.venv/Scripts/python.exe -X utf8 13-experiment/trip-assistant/tests/test_real_weather_sources.py
```

官方资料：[HKO API](https://www.hko.gov.hk/en/weatherAPI/doc/files/HKO_Open_Data_API_Documentation.pdf)、[Open-Meteo 文档](https://open-meteo.com/en/docs)、[免费服务条款](https://open-meteo.com/en/terms)、[高德错误码](https://lbs.amap.com/api/webservice/guide/tools/info)。本次高德香港返回 status=0、infocode=20003（其他未知错误），同一 Key 查询北京成功；无法仅据此确定高德内部失败原因。

2026-11-03 滚动修复：首页及结果页共用独立内容滚动区，小窗口可完整访问表单和行程；地图不再用滚轮缩放。真实浏览器验证桌面四日行程到底部、640×480首页及390px手机宽度和键盘滚动通过。
