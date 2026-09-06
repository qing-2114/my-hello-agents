"""受限的项目文件工具与 Web 应用验收器。

项目来源：https://hello-agents.datawhale.cc/
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EXPERIMENT_DIR = Path(__file__).resolve().parent
APP_DIR = EXPERIMENT_DIR / "generated_app"
ALLOWED_SUFFIXES = {".html", ".css", ".js", ".json", ".md"}
MAX_FILE_SIZE = 100_000
PRICE_API_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin&vs_currencies=usd"
)


def _safe_path(relative_path: str) -> Path:
    """把相对路径限制在 generated_app 内，防止目录穿越。"""
    candidate = (APP_DIR / relative_path).resolve()
    try:
        candidate.relative_to(APP_DIR.resolve())
    except ValueError as exc:
        raise ValueError("路径必须位于 generated_app 目录内") from exc
    if candidate.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError(f"不允许写入 {candidate.suffix or '无扩展名'} 文件")
    return candidate


def write_project_file(relative_path: str, content: str) -> str:
    """在 generated_app 内创建或覆盖一个 Web 项目文本文件。"""
    if len(content.encode("utf-8")) > MAX_FILE_SIZE:
        return f"ERROR: 文件超过 {MAX_FILE_SIZE} 字节限制"
    try:
        target = _safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except (OSError, ValueError) as exc:
        return f"ERROR: {exc}"
    relative_target = target.relative_to(APP_DIR.resolve())
    return f"OK: 已写入 generated_app/{relative_target.as_posix()}"


def read_project_file(relative_path: str) -> str:
    """读取 generated_app 内的一个项目文件。"""
    try:
        target = _safe_path(relative_path)
        return target.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        return f"ERROR: {exc}"


def list_project_files() -> str:
    """列出 generated_app 内当前存在的文件。"""
    if not APP_DIR.exists():
        return "generated_app 尚不存在"
    files = sorted(
        str(path.relative_to(APP_DIR)).replace("\\", "/")
        for path in APP_DIR.rglob("*")
        if path.is_file()
    )
    return "\n".join(files) if files else "generated_app 为空"


def _check_live_price() -> tuple[bool, str]:
    request = Request(
        PRICE_API_URL,
        headers={"Accept": "application/json", "User-Agent": "AutoGen-BTC-Lab/1.0"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
        price = payload["bitcoin"]["usd"]
        if not isinstance(price, (int, float)) or price <= 0:
            return False, "实时行情 API 返回了无效价格"
        return True, f"实时行情 API 正常，BTC/USD={price:,.2f}"
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
        return False, f"实时行情 API 暂不可用：{exc}"


def validate_web_app(check_live_price: bool = False) -> str:
    """执行静态验收；可选地检查真实比特币行情 API。"""
    failures: list[str] = []
    passed: list[str] = []
    required = ("index.html", "styles.css", "app.js")

    for filename in required:
        path = APP_DIR / filename
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            failures.append(f"缺少或为空：{filename}")
    if failures:
        return "FAIL\n- " + "\n- ".join(failures)

    html = (APP_DIR / "index.html").read_text(encoding="utf-8").lower()
    css = (APP_DIR / "styles.css").read_text(encoding="utf-8").lower()
    javascript = (APP_DIR / "app.js").read_text(encoding="utf-8").lower()

    html_expectations = {
        "引用 styles.css": "styles.css",
        "引用 app.js": "app.js",
        "价格展示节点": "price",
        "状态展示节点": "status",
    }
    for label, token in html_expectations.items():
        if token not in html:
            failures.append(f"index.html 缺少{label}")
    if "updated-at" not in html and "last-updated" not in html:
        failures.append("index.html 缺少更新时间节点（updated-at 或 last-updated）")
    js_expectations = {
        "fetch 请求": "fetch(",
        "Bitcoin 查询": "bitcoin",
        "USD 币种": "usd",
        "错误处理": "catch",
        "定时刷新": "setinterval",
    }
    for label, token in js_expectations.items():
        if token not in javascript:
            failures.append(f"app.js 缺少{label}")
    css_adds_dollar = re.search(
        r"\.price::before\s*\{[^}]*content\s*:\s*['\"]\$['\"]",
        css,
        flags=re.DOTALL,
    )
    js_formats_currency = re.search(
        r"style\s*:\s*['\"]currency['\"]",
        javascript,
    )
    if css_adds_dollar and js_formats_currency:
        failures.append("CSS 与 JavaScript 同时添加美元符号，会显示为双 $ 符号")

    node = shutil.which("node")
    if node:
        result = subprocess.run(
            [node, "--check", str(APP_DIR / "app.js")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            passed.append("JavaScript 语法检查通过")
        else:
            failures.append(f"JavaScript 语法错误：{result.stderr.strip()}")
    else:
        passed.append("未安装 Node.js，已跳过 JavaScript 语法检查")

    if check_live_price:
        live_ok, live_message = _check_live_price()
        # 外部服务不可用不应否定本地交付，但会明确记录为警告。
        passed.append(("通过：" if live_ok else "警告：") + live_message)

    if failures:
        return "FAIL\n- " + "\n- ".join(failures) + "\nINFO\n- " + "\n- ".join(passed)
    return "PASS\n- " + "\n- ".join(passed or ["静态验收通过"])


def run_project_tests() -> str:
    """供 CodeReviewer 调用的无网络验收工具。"""
    return validate_web_app(check_live_price=False)


__all__ = [
    "APP_DIR",
    "list_project_files",
    "read_project_file",
    "run_project_tests",
    "validate_web_app",
    "write_project_file",
]
