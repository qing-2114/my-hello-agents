"""真实模型通过默认注册表调用真实搜索与NoteTool。"""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))
from dotenv import dotenv_values
from app.agents.deep_research_agent import DeepResearchAgent
from app.config import Configuration, ROOT, SearchAPI
from app.services.notes_service import NotesService


class RealRegistryTest(unittest.TestCase):
    def test_model_search_and_note(self):
        backend = SearchAPI.TAVILY if dotenv_values(ROOT / '.env').get('TAVILY_API_KEY') else SearchAPI.DUCKDUCKGO
        with TemporaryDirectory() as workspace:
            events = []
            research = DeepResearchAgent(config=Configuration(
                search_api=backend, notes_workspace=workspace, max_search_results=2,
                max_tokens_per_source=200,
            ), event_listener=events.append)
            research.summarizer._run(
                '这是工具注册集成测试。必须先调用search工具，query为'
                'site:docs.python.org asyncio event loop。收到结果后停止调用工具，简要说明结果。'
            )
            searches = [event for event in events if event['type'] == 'tool_call' and event['tool'] == 'search']
            self.assertTrue(searches, '模型没有调用真实搜索')
            self.assertTrue(any('https://' in event['result'] for event in searches))
            research.reporter._run(
                '这是笔记工具集成测试。请调用note工具创建一条笔记，使用JSON参数：'
                '{"action":"create","title":"注册表验证","content":"REGISTRY_NOTE_OK"}。'
                '创建成功后不再调用工具，回复保存成功。'
            )
            notes = [event for event in events if event['type'] == 'tool_call' and event['tool'] == 'note']
            self.assertTrue(any('笔记创建成功' in event['result'] for event in notes))
            service = research.tool_manager.notes
            index = json.loads((service.workspace / 'notes_index.json').read_text(encoding='utf-8'))
            reopened = NotesService(str(service.workspace))
            self.assertTrue(any('REGISTRY_NOTE_OK' in reopened.read_note(note['id']) for note in index['notes']))


if __name__ == '__main__':
    unittest.main()
