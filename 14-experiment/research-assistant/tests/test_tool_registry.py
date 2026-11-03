"""注册表共享、会话切换及搜索适配验证。"""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))
from app.agents.deep_research_agent import DeepResearchAgent
from app.config import Configuration
from app.services.llm_service import create_llm
from app.services.tool_registry import ResearchToolManager
from hello_agents.tools import ToolRegistry


class ToolRegistryTest(unittest.TestCase):
    def test_shared_registry_and_session(self):
        with TemporaryDirectory() as workspace:
            research = DeepResearchAgent(config=Configuration(notes_workspace=workspace))
            manager = research.tool_manager
            self.assertEqual(set(research.tool_registry.list_tools()), {'search', 'note'})
            for service in (research.planner, research.summarizer, research.reporter):
                self.assertIs(service._agent.tool_registry, research.tool_registry)
            self.assertIs(research.tool_registry.get_tool('note'), manager.notes.note_tool)
            old_notes = manager.notes
            note_id = old_notes.save_report('旧会话', '# 旧报告')
            manager.start_notes_workspace()
            self.assertNotEqual(old_notes.workspace, manager.notes.workspace)
            self.assertIs(research.tool_registry.get_tool('note'), manager.notes.note_tool)
            self.assertIn('旧报告', old_notes.read_note(note_id))

    def test_search_adapter_and_custom_registry(self):
        with TemporaryDirectory() as workspace:
            search = Mock()
            search.search.return_value = [{'title': '资料', 'url': 'https://example.org', 'snippet': '摘要'}]
            manager = ResearchToolManager(Configuration(notes_workspace=workspace), search)
            result = manager.registry.get_tool('search').run({'query': '主题'})
            self.assertEqual(json.loads(result), search.search.return_value)
            search.search.assert_called_once_with('主题')
            registry = ToolRegistry()
            research = DeepResearchAgent(llm=create_llm(), tool_registry=registry)
            self.assertIs(research.tool_registry, registry)
            self.assertEqual(registry.list_tools(), [])


if __name__ == '__main__':
    unittest.main()
