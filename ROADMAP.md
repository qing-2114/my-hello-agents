# ROADMAP：从教程实验到企业级 Agent 工程

项目来源：<https://hello-agents.datawhale.cc/>

本文件记录暂停教程跟踪后的学习路线。目标不是"再学几个框架"，而是**把已有的 Agent
能力工程化到可以交付、可以度量、可以维护的程度**——这是企业招聘实际筛选的东西。

时间假设：每周 10-15 小时。全程 18 周；若全职投入可压缩到 8-10 周。
每个阶段以「可验证交付物 + 验收标准」结束，沿用本项目已有的验证记录习惯。

---

## 一、当前基线（已具备的能力）

| 能力域 | 已有证据 | 判断 |
| --- | --- | --- |
| Agent 循环原理 | `4-experiment/ReAct`（手写解析/回灌/最大步数）、`Reflection`（含 trajectory.json）、`Plan-and-Solve` | 扎实，能脱离框架手写 |
| 框架使用 | `6-experiment`：AutoGen 团队协作、AgentScope 角色+规则控制器、CAMEL RolePlaying、LangGraph StateGraph | 广度足够，超出多数候选人 |
| 框架改造 | `7-experiment`：扩展 LLM Provider、重写 ReActAgent（格式自纠 + 防幻觉）、`register_function` 注册工具、工具链、线程池并行执行 | 能读源码并绕过框架缺陷，是加分项 |
| 记忆与 RAG | `8-experiment`：Qdrant + Neo4j + Embedding、命名空间隔离、MQE/HyDE、PDF 入库、`framework_fixes.py` 打补丁不改 site-packages | 真实链路跑通，不是 demo 级 |
| 上下文工程 | `9-experiment`：GSSC 四阶段、`ContextConfig` 对比实验（token 预算实测）、发现中文分词导致 `min_relevance` 全过滤的真实缺陷 | 有独立发现能力，含金量高 |
| 产品化意识 | `1.3-experiment`：SessionState、显式 accept/reject、连续拒绝触发策略反思、记忆按用户隔离、`recommendation_id` 幂等、TTL/限流备注 | 方向对，但只停在注释和 README 里 |
| 工程纪律 | 教程写法差异表、离线确定性测试 + 真实 API 实测、token/耗时记录、跨进程验证 | 这是最强项，很多在职工程师做不到 |

**结论：概念和框架层面已经超过"能上手"的门槛，真正缺的是最后一公里——服务化、
可观测、评测、部署、安全。** 目前的 9 个实验都是"能跑通并验证"，没有一个能对外提供服务。

风险提示：招聘方看的是**一个做深的、有数字的项目**，不是九个章节实验。后续要主动收敛，
把已有的东西挑一个做到生产级，而不是继续横向铺新框架。

---

## 二、差距清单（企业会问，你现在答不上来的）

1. **服务化**：没有 HTTP 接口、没有流式输出、会话只在进程内存里、没有并发处理。
   项目里搜不到任何 `fastapi` / `uvicorn` / `APIRouter` 代码。
2. **可观测性**：没有结构化日志、没有 trace、没有 token/成本/延迟指标。
   现在只有 `print` 和 README 里手抄的耗时表。
3. **自动化评测**：没有 pytest，没有固定测试集，改一次 prompt 只能靠人肉重跑。
   第四章/第七章的测试是离线单元测试 + 手动真实调用，不成体系。
4. **部署**：没有 Dockerfile、没有 CI、密钥只靠 `.env`，没有配置分层（dev/prod）。
5. **安全**：没有 prompt injection 防护、没有工具权限边界、没有输出校验。
   计算器工具用 AST 白名单是好苗头，但没有推广到其他工具。
6. **成本与延迟工程**：没有缓存、没有模型分级路由、没有上下文预算的运行时强制。
7. （可选）**模型层**：没做过 SFT/LoRA，不了解训练侧数据构造。部分岗位会要求。

---

## 三、路线总览

| 阶段 | 周次 | 主题 | 交付物 |
| --- | --- | --- | --- |
| 1 | 1-4 | Agent 服务化 | 可对外调用的 Agent 服务（流式 + 持久会话 + 容错 + 鉴权限流 + 容器化） |
| 2 | 5-7 | 可观测性与成本 | trace 链路 + 指标看板 + 成本优化前后对比 |
| 3 | 8-10 | 评测与回归 | 固定测试集 + 自动评测 + CI 回归门禁 |
| 4 | 11-14 | 纵深专题（三选二） | 生产级 RAG / 协议与多智能体 / 长程自主 Agent |
| 5 | 15-18 | 作品集与面试 | 1 个产品级项目 + 1 个开源技术组件 + 面试问答准备 |

排序理由：服务化先给出一条稳定边界，后面所有东西（trace、评测、部署）都挂在这条边界上；
可观测性在评测之前，因为没有 trace 就拿不到评测需要的中间数据；
纵深专题放在评测之后，这样每次改进都有改前/改后的数字，这是企业里做技术决策的方式。

---

## 四、分阶段详解

### 阶段 1（第 1-4 周）：Agent 服务化

把 `1.3-experiment` 的旅行助手（已有会话状态、反馈分类、策略反思、票务工具）抽成服务。
它是现有代码里产品逻辑最完整的一个，改造成本最低。

任务：

1. 抽一层 `AgentService`，把 `session_agent.py` 的会话逻辑与传输层解耦。
2. FastAPI 接口：`POST /sessions/{id}/turns`（非流式）+ `POST /sessions/{id}/turns/stream`（SSE 流式）。
3. 会话持久化：先把 `SessionState` 存到 SQLite（复用 `8-experiment` 的做法），
   再换 Redis；进程重启后会话必须还在。
4. 容错：LLM/工具调用加超时 + 指数退避重试；超时返回降级答复而不是 500；
   保留现有 Tavily→SerpApi 这类 fallback 思路并统一成策略。
5. 幂等：`recommendation_id` + 请求 ID 去重，网络重试不重复计拒绝次数（README 里已设计，落实成代码）。
6. 鉴权与限流：API Key 或 JWT；按用户维度限流；请求体用 pydantic 严格校验。
7. 容器化：Dockerfile + docker-compose（app + redis），`.env` 不进镜像，改成运行时注入。
8. 测试：pytest 覆盖服务层（用 stub LLM），加真实 API 冒烟脚本。

验收标准：

- `curl` 能看到 SSE 逐字输出，断流后会话状态仍正确。
- 杀进程重启，同一 `session_id` 继续对话，历史与拒绝计数不丢。
- 50 并发请求压测无串话（不同 session 不互相污染），无 500。
- 注入 LLM 超时/工具异常，接口返回降级响应且日志可定位。
- `docker compose up` 一条命令起服务，无需手工配环境。

需要新装：`pytest`、`pytest-asyncio`、`redis`（或 `fakeredis`）、Docker Desktop。

已装可直接用（2026-09-24 实测）：`fastapi`、`uvicorn`、`sse_starlette`、`httpx`、`tenacity`、
`pydantic`、`pydantic_settings`、`sqlalchemy`、`aiofiles`、`orjson`、`openai`、
`qdrant_client`、`neo4j`、`tiktoken`。也就是说传输层和容错层不需要新依赖，
会话持久化可以先用 `sqlalchemy` + SQLite 起步，再换 Redis。

#### 代码级落点（2026-09-24 逐文件核实）

服务化的工作量不在"加一层 FastAPI"，而在这四个耦合点上。改错顺序会返工：

1. **Agent 循环在打印，不在返回**。`1.3-experiment/agent.py:117-141` 的 `run_agent`
   每一步都 `print` 用户输入、模型输出、Observation，`trace_memory` 还会把完整
   system prompt 打出来。服务里既不能往 stdout 写，又需要把这些中间步骤变成
   SSE 事件和 trace span。改法：`run_agent` 增加
   `on_event: Callable[[AgentEvent], None]` 回调（`llm_request` / `llm_response` /
   `tool_call` / `tool_result` / `finish`），CLI 传打印实现，服务层传 SSE + span 实现。
   **这一处改完，阶段 2 的可观测性才有地方挂**，所以要排在第 1 周做，不要留到最后。

2. **LLM 客户端把异常吞成了字符串**。`1.3-experiment/llm_client.py:40-42` 用
   `except Exception` 捕获后返回 `"错误:调用语言模型服务时出错。"`，且 `stream=False`。
   上层无法区分"模型真的这么回答"和"调用失败"，重试、超时、降级都没法做——
   直接加 `tenacity` 也没用，因为异常根本传不上来。改法：新增
   `async def agenerate(...)`，失败抛 `LLMError`（带 status code 和是否可重试），
   超时与指数退避在这一层用 `tenacity` 实现；`generate` 保留为同步包装供 CLI 使用。

3. **会话状态是可变对象且没有序列化契约**。`session_agent.py:29-40` 的 `SessionState`
   是纯 dataclass，`Rejection` 是嵌套 dataclass，没有 schema 版本、没有
   `to_dict`/`from_dict`。直接 `asdict` 存库，以后加字段就无法兼容旧数据。
   改法：加 `schema_version`，实现 `to_dict()`/`from_dict()`，SQLite 存 JSON 列并对
   `session_id` 建索引；`AgentService` 只通过 `SessionRepository` 读写状态，
   另给一个内存实现供测试使用。

4. **`recommendation_id` 幂等只存在于 README**。`TurnResult`（`session_agent.py:43-48`）
   没有这个字段，`continue_session` 也没有 request_id 去重；README 第 182 行设计了它，
   代码里没实现。改法：`TurnResult` 增加 `recommendation_id`，服务层用
   `(session_id, request_id)` 建唯一索引，重复请求直接返回上次结果，不重复累计拒绝次数。

另有两处要先决定，否则改造会返工：

- `1.3-experiment/` 没有 `__init__.py`，模块间是平铺导入（`from agent import run_agent`）。
  要么把可复用部分提成 `travel_agent/` 包（干净，但要同步改所有测试的导入路径），
  要么在 `service/` 里加 `sys.path` 处理（快，但留技术债）。建议提包，测试文件一起挪。
- `classify_feedback`（`session_agent.py:51-76`）已经是一次独立的 LLM 调用，
  阶段 2 换小模型只需改这一处的 `llm` 注入，不用动架构。这是现有代码里少见的、
  已经为模型分级路由留好口子的地方，重构时别把它合并回主循环。

环境实测（2026-09-24）：`pytest`、`pytest-asyncio`、`redis`、`fakeredis` 均未安装；
**Docker Desktop 未安装**（`docker` 命令不存在），因此第 7 项容器化在装好之前无法验证，
建议排到第 4 周，或先只写 Dockerfile 标注"未实测"。项目内没有 Dockerfile、
没有 `.github/`，阶段 3 的 CI 门禁目前是零基础。

### 阶段 2（第 5-7 周）：可观测性与成本

任务：

1. 接 OpenTelemetry 或 Langfuse，一次请求一条 trace：每个 LLM 调用、每个工具调用
   都是 span，带耗时、token 数、模型名、成功/失败。
2. 结构化 JSON 日志，全链路带 `trace_id` / `session_id` / `turn_id`；密钥永不落日志。
3. 指标：token 进出、单轮成本、延迟 p50/p95、工具成功率、检索命中率、降级次数、缓存命中率。
4. 成本优化，逐项量化：
   - 模型分级路由：反馈分类、意图识别用小模型（现在 `1.3-experiment` 的分类已经独立成一次调用，直接换小模型）；
   - 结果缓存：同一查询的检索/工具结果缓存；
   - prompt caching：把稳定的系统提示词放在前缀；
   - 上下文预算运行时强制：把 `9-experiment` 的 GSSC 预算逻辑接进服务，而不是只在 demo 里。
5. 一张成本/延迟报表（可先用脚本输出 Markdown，不必上 Grafana）。

验收标准：

- 一次端到端请求能在 trace 里看到每一步耗时与 token，能按 session 聚合。
- 有一份优化前后对比表（单轮成本、p95 延迟、缓存命中率），数字可复现。
- 单轮成本相比阶段 1 基线明显下降（目标 30%+，具体看模型分级效果）。

依赖情况：`opentelemetry`（含 `sdk.trace`）和 OTLP 导出器已经装好，可以直接用；
`langsmith` 也已存在（随 langchain 装进来的）。要托管的 trace 面板再装 `langfuse`，
要用 Prometheus 抓指标再装 `prometheus_client`——两者都不是必需品，
先用 OTel + 结构化日志 + 脚本出的报表就能满足验收。

### 阶段 3（第 8-10 周）：评测与回归

这是目前最薄弱、也最能拉开差距的一环。企业里改 prompt/换模型必须靠评测说话。

任务：

1. 建固定测试集：从旅行助手 + 代码库维护助手场景出发，50-200 条，
   覆盖正常问答、工具调用、多轮拒绝、知识库外问题、注入攻击、边界输入。
   每条要有期望行为（不是期望字符串，而是判据）。
2. 指标设计：
   - 任务成功率（端到端能否完成目标）
   - 工具调用准确率（该调时调、参数对不对、不该调时不调）
   - 忠实度 / 有无幻觉（回答是否只依据检索到的证据）
   - 拒答正确率（不知道就说不知道）
   - 延迟与成本（作为非功能指标一起评）
3. LLM-as-Judge：写清 rubric，用另一个模型打分；抽 20-30 条人工复核，
   算 judge 与人工的一致率——不一致的 rubric 等于没评测。
4. 确定性回归：把真实 API 的响应录制成 fixture，CI 里回放，保证测试不依赖网络与额度。
5. CI 门禁：GitHub Actions 跑 `pytest`，成功率下降超过阈值（如 2 个百分点）就 fail。

验收标准：

- 一条 `pytest` 命令跑完全部评测并输出 Markdown 报告（含各指标与对比基线）。
- 故意把某个 prompt 改坏，CI 能自动发现回归并指出是哪类用例变差。
- judge 与人工的一致率有明确数字，并说明哪些用例 judge 不可靠。

需要新装：`pytest`、`pytest-asyncio`、`vcrpy` 或自建录制器；可选 `ragas`（评估 RAG 质量）、`rank_bm25`（混合检索）。

### 阶段 4（第 11-14 周）：纵深专题（选两个，不要全选）

**A. 生产级 RAG**（推荐，岗位需求最大）
在 `8-experiment` 基础上做：分块策略对比实验、混合检索（BM25 + 向量）、
rerank 重排、多路召回融合、引用溯源（答案标注来源段落）、增量更新与去重、
多租户隔离、用阶段 3 的评测驱动调参（每组参数都要有数字）。
验收：一份检索质量对比报告，说明每组改动的收益与代价。

**B. 协议与多智能体**
自己写一个 MCP Server（不是消费现成的），暴露 2-3 个工具给客户端调用；
再做 supervisor / handoff 模式的编排、human-in-the-loop 审批节点、
工具执行沙箱与权限白名单。框架已装（`hello_agents.protocols` 含 MCP/A2A/ANP），
但重点是自己实现协议细节。
验收：MCP Server 能被第三方客户端（如 Claude Desktop 或官方 inspector）正常调用；
多智能体流程有明确的失败恢复与人工介入路径。

**C. 长程自主 Agent**
基于 `9-experiment` 的 CodebaseMaintainer 深化：任务分解与计划持久化、
断点续跑（崩溃后从检查点恢复）、记忆压缩策略、成本上限熔断、失败重试与放弃判据、
沙箱化的终端/文件操作。这是"自主 Agent"岗位的核心能力。
验收：一个需要 20+ 步的跨会话任务能跑完，中途杀进程后能续跑，成本超限自动停止。

**D. 模型层（可选，视岗位）**
教程第十一章的 Agentic-RL（SFT → GRPO）可作参考。至少掌握：
SFT 数据构造（从自己的 trace 里挖高质量轨迹）、LoRA 微调、微调前后用阶段 3 的评测对比。
环境里 `trl` / `peft` / `datasets` / `accelerate` / `transformers` 都已安装，可以直接开始。
验收：一次完整的 LoRA 微调 + 评测对比报告，说明微调在哪些用例上有效、哪些无效。

### 阶段 5（第 15-18 周）：作品集与面试

任务：

1. **一个产品级项目**（把阶段 1-3 的成果收成一个能演示的东西）：
   有界面或清晰的 API、有鉴权、有 trace、有评测报告、有部署方式、
   README 写清架构图与取舍、录一段 3-5 分钟 demo。
   建议就用旅行助手，它已经有会话、反馈、反思、票务这些真实业务逻辑。
2. **一个技术组件开源**：MCP Server、评测框架、检索组件任选一个，
   发到 GitHub，带 benchmark 数据和对比基线。这是技术深度的证明。
3. **面试准备**，能讲清 trade-off 而不是背名词：
   - 为什么用 ReAct 而不是 Plan-and-Solve，各自失败模式是什么（你第四章的代码就是答案）
   - 上下文预算怎么定，超了怎么办，压缩为什么不能只靠截断（你第九章实测过）
   - 怎么评测一个 Agent，judge 不可靠时怎么办
   - 怎么防 prompt injection，工具权限怎么收（你 AST 白名单是个好例子）
   - 成本怎么降，模型分级路由的边界在哪
   - 多智能体什么时候是必要的、什么时候是过度设计
   - 记忆系统怎么设计，为什么不用一个向量库全塞进去
   - 你的项目里最难的 bug 是什么（`framework_fixes.py` 里的死循环和中文分词缺陷是极好的素材）

---

## 五、每周节奏建议

- 每周固定产出：一个可运行的东西 + 一段验证记录（沿用现有 README 的写法）。
- 每阶段结束时做一次「对外讲解」：写一篇 1500 字左右的技术笔记，讲清做了什么、
  数字是多少、踩了什么坑、还有什么没解决。写不清楚说明没真懂。
- 保留"离线确定性测试 + 真实 API 实测"双轨验证的习惯，这是本项目的优势，别丢。
- 每个阶段先写验收标准再动手，避免做成"又跑通一个 demo"。

---

## 六、明确不做的事

- 不追新框架。AutoGen / LangGraph / AgentScope 已经覆盖主流范式，再学新的边际收益很低。
- 不从零实现 Transformer、不手写 CUDA。除非目标岗位明确要求，否则投入产出比极差。
- 不做低代码平台（教程第五章 Coze/Dify/n8n）。除非目标岗位是"业务侧搭建"，
  否则对工程岗帮助有限，可以花半天了解概念即可。
- 不继续横向铺章节实验。每多一个"跑通"的实验，边际价值递减；缺的是深度。

---

## 七、立刻开始：本周清单

进度（2026-09-24 核实）：`8-experiment/`、`9-experiment/`、`ROADMAP.md` 仍未提交，
`README.md` / `requirements.txt` / `.gitignore` 有未提交改动；`service/` 目录尚未创建，
阶段 1 没有开工。

1. 提交当前未入库的工作（`8-experiment/`、`9-experiment/`、README 与 requirements 改动）。
2. 定目标岗位画像：Agent 应用开发 / Agent 基础设施 / 算法（含微调）。
   这决定阶段 4 选 A+B 还是 A+D。
3. 读一遍 `1.3-experiment/session_agent.py`，在纸上画出服务化的边界：
   哪些是业务逻辑、哪些是传输、哪些是状态。这决定了阶段 1 的改造范围。
4. 建 `service/` 目录骨架 + 装 `pytest`，把第一个接口用 stub LLM 跑通。

---

## 八、附：企业常见面试问题清单（自查用）

服务化与可靠性：

- 你的 Agent 服务怎么做会话持久化和并发隔离？
- LLM 调用超时或限流了怎么办？重试会不会导致重复副作用？
- 怎么保证工具调用幂等？

评测：

- 你怎么证明改了 prompt 之后变好了？
- 没有标注数据怎么做评测？LLM-as-Judge 的偏差怎么控制？
- 线上怎么发现效果退化？

RAG：

- 分块策略怎么选？为什么？
- 只用向量检索有什么问题？什么时候需要混合检索和 rerank？
- 怎么保证答案有据可查？检索不到时应该怎么办？

安全与成本：

- prompt injection 怎么防？用户输入里的指令和系统指令怎么隔离？
- 工具权限怎么控制？怎么防止 Agent 执行危险操作？
- 单轮成本怎么降？上下文长度和效果怎么权衡？

架构：

- 什么时候需要多智能体？单 Agent 做不到什么？
- 长任务怎么保证不半途而废？状态存哪？
- 上下文超长了怎么办？为什么不能只截断？
