"""使用真实 NoteTool 验证落盘和重新打开后的读取。"""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))
from app.models.schemas import TodoItem
from app.services.notes_service import NotesService


class NotesServiceTest(unittest.TestCase):
    def test_save_and_reopen(self):
        with TemporaryDirectory() as workspace:
            notes = NotesService(workspace)
            task = TodoItem(1, '异步研究', '理解协程', 'asyncio')
            plan_id = notes.save_plan('研究主题', [task])
            summary_id = notes.save_task_summary(task, [{
                'title': 'Python官方文档', 'url': 'https://docs.python.org/3/library/asyncio.html',
                'snippet': 'asyncio 使用 async/await 语法编写并发代码。',
            }], '总结[T1-S1]')
            report_id = notes.save_report('研究主题', '# 研究报告\n\n结论[T1-S1]')
            reopened = NotesService(workspace)
            self.assertIn('研究主题', reopened.read_note(plan_id))
            content = reopened.read_note(summary_id)
            for text in ('理解协程', 'asyncio', 'https://docs.python.org', '总结[T1-S1]', '[T1-S1] Python官方文档'):
                self.assertIn(text, content)
            self.assertIn('结论[T1-S1]', reopened.read_note(report_id))
            self.assertEqual(len(list(Path(workspace).glob('note_*.md'))), 3)

    def test_failed_create_is_not_success(self):
        with TemporaryDirectory() as workspace:
            notes = NotesService(workspace)
            notes.note_tool.max_notes = 0
            with self.assertRaises(RuntimeError):
                notes.save_report('主题', '# 报告')


if __name__ == '__main__':
    unittest.main()
