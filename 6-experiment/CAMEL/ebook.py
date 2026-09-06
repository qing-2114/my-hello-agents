"""协作消息的展示、清洗与电子书落盘。"""

from __future__ import annotations

import re
import argparse
from pathlib import Path
from typing import Iterable


OUTPUT_DIR = Path(__file__).resolve().parent / "output"
EBOOK_PATH = OUTPUT_DIR / "拖延症心理学.md"
TRACE_PATH = OUTPUT_DIR / "协作轨迹.md"
REFERENCE_SECTION = """## 参考文献

- Gollwitzer, P. M. (1999). Implementation intentions: Strong effects of simple plans. *American Psychologist, 54*(7), 493–503. https://doi.org/10.1037/0003-066X.54.7.493
- Sirois, F. M., & Pychyl, T. A. (2013). Procrastination and the priority of short-term mood regulation: Consequences for future self. *Social and Personality Psychology Compass, 7*(2), 115–127. https://doi.org/10.1111/spc3.12011
- Steel, P. (2007). The nature of procrastination: A meta-analytic and theoretical review of quintessential self-regulatory failure. *Psychological Bulletin, 133*(1), 65–94. https://doi.org/10.1037/0033-2909.133.1.65
- Steel, P., & König, C. J. (2006). Integrating theories of motivation. *Academy of Management Review, 31*(4), 889–913. https://doi.org/10.5465/amr.2006.22527462
- Tice, D. M., & Baumeister, R. F. (1997). Longitudinal study of procrastination, performance, stress, and health. *Psychological Science, 8*(6), 454–458. https://doi.org/10.1111/j.1467-9280.1997.tb00460.x
"""


def response_content(response: object) -> str:
    """兼容 CAMEL 单消息响应，安全提取文本。"""
    msgs = getattr(response, "msgs", None)
    if not msgs:
        return ""
    return str(getattr(msgs[0], "content", "")).strip()


def clean_solution(content: str) -> str:
    """移除协议包装，只保留可出版章节。"""
    text = content.strip()
    text = re.sub(r"^\s*Solution\s*:\s*", "", text, count=1, flags=re.I)
    text = re.sub(r"\s*Next request\.?\s*$", "", text, count=1, flags=re.I)
    return text.strip()


def chinese_character_count(text: str) -> int:
    """统计 CJK 汉字数量，作为中文“字数”的透明近似值。"""
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))


def chapter_key(chapter: str) -> str:
    """用首个 Markdown 二级标题识别章节。"""
    match = re.search(r"(?m)^##\s+(.+?)\s*$", chapter)
    return match.group(1).strip() if match else ""


def upsert_chapter(chapters: list[str], chapter: str) -> None:
    """同名章节以较新的完整交付覆盖，避免补写时正文重复。"""
    key = chapter_key(chapter)
    if key:
        for index, existing in enumerate(chapters):
            if chapter_key(existing) == key:
                chapters[index] = chapter
                return
    chapters.append(chapter)


def trace_entries(markdown: str) -> list[tuple[str, str]]:
    """从本实验生成的轨迹 Markdown 中恢复角色消息。"""
    markers = list(re.finditer(r"(?m)^## (作家|心理学家)\s*$", markdown))
    entries: list[tuple[str, str]] = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(markdown)
        entries.append((marker.group(1), markdown[marker.end() : end].strip()))
    return entries


def rebuild_from_trace() -> tuple[Path, Path, int]:
    """从协作轨迹重建正文，可用于恢复或应用同名章节覆盖规则。"""
    trace = trace_entries(TRACE_PATH.read_text(encoding="utf-8"))
    chapters: list[str] = []
    for role, content in trace:
        if role == "心理学家":
            chapter = clean_solution(content)
            if chapter:
                upsert_chapter(chapters, chapter)
    return write_artifacts(chapters, trace)


def write_artifacts(chapters: Iterable[str], trace: Iterable[tuple[str, str]]) -> tuple[Path, Path, int]:
    """写入电子书和完整协作记录，返回路径与正文汉字数。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(chapter.strip() for chapter in chapters if chapter.strip())
    ebook = (
        "# 拖延症心理学\n\n"
        "> AI 心理学家与 AI 作家基于 CAMEL 角色扮演协作生成。"
        "本书用于心理科普，不替代专业诊断或治疗。\n\n"
        f"{body}\n\n{REFERENCE_SECTION}"
    )
    EBOOK_PATH.write_text(ebook, encoding="utf-8")

    trace_blocks = ["# 《拖延症心理学》CAMEL 协作轨迹"]
    for role, content in trace:
        trace_blocks.append(f"## {role}\n\n{content.strip()}")
    TRACE_PATH.write_text("\n\n".join(trace_blocks) + "\n", encoding="utf-8")
    return EBOOK_PATH, TRACE_PATH, chinese_character_count(body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 CAMEL 协作轨迹重建电子书")
    parser.add_argument("--rebuild", action="store_true", help="按同名章节覆盖规则重建")
    cli_args = parser.parse_args()
    if cli_args.rebuild:
        path, _, count = rebuild_from_trace()
        print(f"已重建：{path}")
        print(f"正文汉字数：{count}")
