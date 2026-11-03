"""真实搜索与真实模型端到端研究验证。"""
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))

from app.agents.deep_research_agent import DeepResearchAgent
from app.config import Configuration, ROOT, SearchAPI
from app.services.notes_service import NotesService
from dotenv import dotenv_values


class RealResearchTest(unittest.TestCase):
    def test_full_research(self):
        events = []

        def on_event(event):
            events.append(event)
            if event['type'] == 'status':
                print(event['message'], flush=True)

        config = Configuration.from_env()
        if dotenv_values(ROOT / '.env').get('TAVILY_API_KEY'):
            config.search_api = SearchAPI.TAVILY
        report = DeepResearchAgent(event_listener=on_event, config=config).run(
            'Python asyncio 入门：协程、任务与事件循环，以及适用场景和限制。'
            '请只规划3个互补任务，优先检索Python官方文档。'
        )
        tasks = next(event['tasks'] for event in events if event['type'] == 'tasks')
        completed = [event['task_id'] for event in events if event['type'] == 'task_completed']
        self.assertEqual(completed, [task['id'] for task in tasks])
        self.assertEqual(events[-1], {'type': 'report', 'content': report})
        self.assertFalse(any(event['type'] == 'error' for event in events))
        workspace = next(event['path'] for event in events if event['type'] == 'notes_workspace')
        reopened = NotesService(workspace)
        saved = [event for event in events if event['type'] == 'note_saved']
        self.assertEqual(len(saved), len(tasks) + 2)
        for event in saved:
            content = reopened.read_note(event['note_id'])
            if event['kind'] == 'task_summary':
                self.assertIn(f"[T{event['task_id']}-S", content)
                self.assertIn('URL:', content)
            elif event['kind'] == 'report':
                self.assertIn(report, content)
        self.assertTrue(report.startswith('#'))
        self.assertRegex(report, r'https?://')
        self.assertTrue(re.search(r'\[T\d+-S\d+\]', report))
        json.dumps(events, ensure_ascii=False)  # 所有事件可直接发送给后续前端。
        output = Path(__file__).resolve().parents[2] / '.local' / 'research-assistant'
        output.mkdir(parents=True, exist_ok=True)
        (output / 'last-report.md').write_text(report, encoding='utf-8')
        (output / 'last-events.json').write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
