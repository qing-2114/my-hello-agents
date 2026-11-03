"""通过 NoteTool 保存研究计划、任务证据与最终报告。"""
from pathlib import Path
import re

from hello_agents.tools.builtin.note_tool import NoteTool

from ..models.schemas import TodoItem


class NotesService:
    """单个研究目录内顺序使用，不并发共享同一 NoteTool 索引。"""

    def __init__(self, workspace: str):
        self.workspace = Path(workspace).resolve()
        self.note_tool = NoteTool(workspace=str(self.workspace))

    def _create(self, title: str, content: str, tags: list[str], note_type: str) -> str:
        result = self.note_tool.run({
            'action': 'create', 'title': title, 'content': content,
            'tags': tags, 'note_type': note_type,
        })
        match = re.search(r'^ID:\s*(\S+)\s*$', result, re.MULTILINE)
        if not result.startswith('✅') or match is None:
            raise RuntimeError('NoteTool 创建笔记失败')
        return match.group(1)

    def read_note(self, note_id: str) -> str:
        if not re.fullmatch(r'note_[A-Za-z0-9_]+', note_id):
            raise ValueError('无效的笔记ID')
        result = self.note_tool.run({'action': 'read', 'note_id': note_id})
        if result.startswith('❌'):
            raise RuntimeError('NoteTool 读取笔记失败')
        return result

    def save_plan(self, topic: str, tasks: list[TodoItem]) -> str:
        content = f'# 研究主题\n\n{topic}\n\n## 研究任务\n\n'
        content += '\n\n'.join(
            f'### 任务{task.id}：{task.title}\n意图：{task.intent}\n查询：{task.query}'
            for task in tasks
        )
        return self._create('研究计划', content, ['research', 'plan'], 'task_state')

    def save_task_summary(self, task: TodoItem, search_results: list[dict], summary: str) -> str:
        return self._create(
            f'任务{task.id}：{task.title}',
            self._format_note_content(task, search_results, summary),
            ['research', 'summary', f'task_{task.id}'], 'task_state',
        )

    @staticmethod
    def _format_note_content(task: TodoItem, search_results: list[dict], summary: str) -> str:
        content = (f'# 任务{task.id}：{task.title}\n\n## 任务信息\n\n'
                   f'- **意图**：{task.intent}\n- **查询**：{task.query}\n\n## 搜索结果\n\n')
        for idx, source in enumerate(search_results, 1):
            content += (f"[T{task.id}-S{idx}] {source['title']}\n"
                        f"URL: {source['url']}\n摘要: {source['snippet']}\n\n")
        return content + f'## 总结\n\n{summary}\n'

    def save_report(self, topic: str, report: str) -> str:
        return self._create(f'研究报告：{topic}', report, ['research', 'report'], 'conclusion')
