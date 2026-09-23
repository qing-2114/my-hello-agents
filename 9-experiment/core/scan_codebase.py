"""标准库代码库扫描脚本（供 TerminalTool 在 Windows 下调用）。

教程的代码库探索命令是 ``find`` / ``grep`` / ``wc`` / ``head`` 组合，在
Windows 的 cmd.exe 下不可用（GNU 语法不同，且 TerminalTool 的命令白名单不含
findstr）。本脚本只依赖标准库，用 PATH 上的 python 解释器执行：

    python 9-experiment/core/scan_codebase.py structure --limit 20
    python 9-experiment/core/scan_codebase.py loc
    python 9-experiment/core/scan_codebase.py todo --limit 10

默认扫描当前目录（TerminalTool 的 workspace），跳过 .conda / .git /
__pycache__ 等目录。输出为纯 ASCII（路径 + 数字），避免 Windows 控制台编码问题。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterator

EXCLUDED_DIRS = {
    ".conda",
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".zcode",
}


def iter_python_files(root: Path) -> Iterator[Path]:
    """按路径排序遍历 root 下的 .py 文件，跳过排除目录。"""
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        yield path


def relative(path: Path, root: Path) -> str:
    """尽量输出相对路径，失败时退回绝对路径（正斜杠形式）。"""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def cmd_structure(root: Path, limit: int) -> None:
    files = list(iter_python_files(root))
    print(f"python files: {len(files)}")
    for path in files[:limit]:
        print(relative(path, root))


def cmd_loc(root: Path) -> None:
    files = list(iter_python_files(root))
    total_lines = 0
    for path in files:
        try:
            total_lines += len(
                path.read_text(encoding="utf-8", errors="ignore").splitlines()
            )
        except OSError:
            continue
    print(f"files: {len(files)}")
    print(f"lines: {total_lines}")


def cmd_todo(root: Path, limit: int) -> None:
    hits = []
    for path in iter_python_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if "TODO" in line or "FIXME" in line:
                hits.append(f"{relative(path, root)}:{lineno}: {line.strip()[:100]}")
    print(f"matches: {len(hits)}")
    for hit in hits[:limit]:
        print(hit)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="代码库扫描（仅标准库）")
    parser.add_argument("action", choices=["structure", "loc", "todo"])
    parser.add_argument("--root", default=".", help="扫描根目录（默认当前目录）")
    parser.add_argument("--limit", type=int, default=20, help="输出条数上限")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SystemExit(f"目录不存在: {root}")

    if args.action == "structure":
        cmd_structure(root, args.limit)
    elif args.action == "loc":
        cmd_loc(root)
    else:
        cmd_todo(root, args.limit)


if __name__ == "__main__":
    main()
