# 第十二章实验

本目录用于 Datawhale「Hello Agents」教程第十二章的学习与实践。

教程来源：<https://hello-agents.datawhale.cc/>

## 目录约定

后续按实际实验主题建立子目录，示例程序放在主题目录的 `demos/`，测试放在 `tests/`，测试文件使用 `test_*.py` 命名。跨主题共享内容按需放在 `common/`。

## 环境准备（Windows PowerShell）

本章使用独立的 `.venv`，避免降级项目原有 `.conda` 中的 HelloAgents 0.2.8。以下命令均从项目根目录执行：

```powershell
.\.conda\python.exe -m venv 12-experiment\.venv
.\12-experiment\.venv\Scripts\python.exe -m pip install "hello-agents[evaluation]==0.2.7"
.\12-experiment\.venv\Scripts\python.exe -m pip install "numpy==1.26.4" bfcl-eval
.\12-experiment\.venv\Scripts\python.exe -m pip install "huggingface-hub==0.36.2" "transformers==4.49.0" "sentence-transformers==3.4.1" "contourpy<1.4" "datasets==3.6.0" "pyarrow==19.0.1"
.\12-experiment\.venv\Scripts\python.exe -m pip install "soundfile==0.14.0"
```

注意：教程分步安装会覆盖 HelloAgents 声明的 `numpy>=2.0.0` 依赖；安装完成不等于依赖检查完全通过。后续安装其他包时注意解析器可能重新升级 NumPy。

VS Code 请为本章选择 `12-experiment/.venv/Scripts/python.exe` 解释器。也可以直接用上述完整解释器路径运行程序，无需激活环境。

## BFCL v4 数据集（GitHub 克隆）

从项目根目录执行：

```powershell
git clone --depth 1 https://github.com/ShishirPatil/gorilla.git 12-experiment/bfcl/data/temp_gorilla
Get-ChildItem 12-experiment/bfcl/data/temp_gorilla/berkeley-function-call-leaderboard/bfcl_eval/data/
Get-ChildItem 12-experiment/bfcl/data/temp_gorilla/berkeley-function-call-leaderboard/bfcl_eval/data/possible_answer/
```

`--depth 1` 仅省略旧提交历史，不省略当前版本的数据文件。下载仓库已通过本章 `.gitignore` 忽略，避免把第三方嵌套 Git 仓库提交进本项目。

2026-11-03 克隆版本：`6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`。

在项目根目录运行代码时，显式指定数据路径（框架默认的 `./temp_gorilla/...` 与本项目目录布局不同）：

```python
from hello_agents.evaluation import BFCLDataset

dataset = BFCLDataset(
    bfcl_data_dir="12-experiment/bfcl/data/temp_gorilla/berkeley-function-call-leaderboard/bfcl_eval/data",
    category="simple_python",
)
items = dataset.load()
print(f"题目：{len(items)}，标准答案：{len(dataset.ground_truth)}")
```

数据验证记录：

- 20 个顶层 `BFCL_v4_*.json` 数据文件、16 个同类标准答案文件全部解析通过（35 个 JSONL 文件、1 个普通 JSON 文件）。
- 通过 HelloAgents 实际加载并核对题目 ID 与标准答案：`simple_python` 400 题、`multiple` 200 题、`parallel` 200 题、`parallel_multiple` 200 题、`simple_java` 100 题、`simple_javascript` 50 题。
- 官方当前目录中 `format_sensitivity`、`irrelevance`、`live_irrelevance`、`live_relevance` 没有同名标准答案文件，不能对这些类别套用“必须存在同名答案文件”的检查。
- 本次仅验证数据获取、解析和加载，未执行真实 LLM 的 BFCL 评测，不代表获得评测分数。

### 五样本评估示例

从项目根目录运行（读取根目录 `.env`，使用真实 LLM API）：

```powershell
.\12-experiment\.venv\Scripts\python.exe -X utf8 12-experiment/bfcl/demos/evaluate_simple_python.py
```

2026-11-03 执行记录：`simple_python` 前 5 题在 HelloAgents 内置 AST 评估中得到 5/5（100%）。结果及报告位于 `bfcl/runs/20261103_003229/`，运行产物已忽略。

默认附带的 BFCL 官方 CLI 复核未完成：启动阶段报 `ModuleNotFoundError: No module named 'soundfile'`（Qwen Agent 的依赖）。因此上述 100% 仅为 HelloAgents 内置评分，不是官方 CLI 评分，也不是完整 400 题成绩。工具默认使用 `Qwen/Qwen3-8B` 作为官方导出标签，该标签不代表根目录 `.env` 实际配置的模型。

后续修复记录（2026-11-03）：已补装 `soundfile==0.14.0`，并启用 `PYTHONUTF8=1` 解决 Windows GBK 无法输出 emoji 的问题。复用用户运行目录 `bfcl/runs/20261103_003427/` 中已有的 5 条真实 API 预测，官方 CLI 复核成功，`simple_python` 准确率 100%（5/5），没有再次调用模型。评分产物位于该目录的 `score/`。这是 `--partial-eval` 子集评分，不是完整数据集或排行榜成绩。

从项目根目录复核上述已有结果：

```powershell
$env:BFCL_PROJECT_ROOT = (Resolve-Path '12-experiment/bfcl/runs/20261103_003427').Path
$env:PYTHONUTF8 = '1'
.\12-experiment\.venv\Scripts\bfcl.exe evaluate --model Qwen/Qwen3-8B --test-category simple_python --partial-eval
```

## Hugging Face Token 与 GAIA

1. 注册并登录 <https://huggingface.co/>。
2. 打开 <https://huggingface.co/settings/tokens>，创建名为 `hello-agents-ch12` 的 Token，选择 Read 权限。
3. 打开 <https://huggingface.co/datasets/gaia-benchmark/GAIA>，按页面要求申请访问或接受条款。Token 不会自动授予受限数据集权限。
4. 在项目根目录已有的 `.env` 中添加 `HF_TOKEN=hf_你的Token`，不要提交或在日志中打印。程序需显式调用 `load_dotenv()` 加载根目录配置。

临时配置当前 PowerShell 会话可使用以下命令（教程的 `export` 是 Bash 语法）：

```powershell
$env:HF_TOKEN = "hf_你的Token"
```

官方说明：<https://huggingface.co/docs/hub/security-tokens>。

## 实验与验证记录

2026-11-03：

- 已在本章 `.venv` 安装 HelloAgents 0.2.7、bfcl-eval 2026.3.23、NumPy 1.26.4。原项目 `.conda` 保持 0.2.8。
- 修正自动安装的新版依赖冲突：Hub 0.36.2、Transformers 4.49.0、Sentence Transformers 3.4.1、Datasets 3.6.0、PyArrow 19.0.1、ContourPy 1.3.3。
- `SimpleAgent`、BFCL/GAIA 数据集与评估器、`bfcl_eval`、`datasets`、NumPy、Matplotlib 导入通过。
- 已读取根目录 `.env`，确认三个 LLM 配置项存在，并完成一次真实聊天 API 请求，收到非空响应。尚未运行完整 BFCL/GAIA 评测。
- `HF_TOKEN` 尚未配置，GAIA 下载和权限验证未完成。
- `pip check` 仍有两项冲突：HelloAgents 声明 NumPy >=2，但教程指定 1.26.4；Gradio Client 1.3.0 要求 websockets <13，而新版 BFCL 引入的 Google GenAI 需要更新版本。当前安装为 websockets 17.4，Gradio 客户端功能未验证。需要 Gradio UI 时建议再隔离环境，不应据此声称所有组件兼容。
- `requirements-lock.txt` 是安装版本快照；由于上述冲突，不能作为可直接一次性解析安装的锁文件。复现时按上述分步命令操作。

网络受限时的数据集选择参见 [数据集选择.md](数据集选择.md)。
