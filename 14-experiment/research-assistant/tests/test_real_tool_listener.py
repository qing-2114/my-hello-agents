"""真实模型自主生成工具调用，验证三个角色共用的监听链路。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))

from hello_agents.tools import ToolRegistry
from app.agents.deep_research_agent import DeepResearchAgent
from app.services.llm_service import create_llm
from test_tool_listener import ResearchLookupTool


class RealToolListenerTest(unittest.TestCase):
    def test_llm_tools_and_events(self):
        tool = ResearchLookupTool()
        registry = ToolRegistry()
        registry.register_tool(tool)
        events = []
        research = DeepResearchAgent(create_llm(), registry, events.append)
        for service in (research.planner, research.summarizer, research.reporter):
            with self.subTest(role=service._agent.name):
                start = len(events)
                response = service._run(
                    '本次是工具集成验证。必须先调用 research_lookup 工具，query 为 asyncio。'
                    '不能自行回答或伪造工具结果。拿到结果后不再调用工具，'
                    '最终回答请原样包含工具返回的 RESEARCH_TOOL_OK 标记。'
                )
                own_events = events[start:]
                self.assertTrue(own_events, '真实模型未调用工具')
                self.assertTrue(any(e['agent'] == service._agent.name
                                    and e['tool'] == 'research_lookup'
                                    and e['parameters'].get('query') == 'asyncio'
                                    and 'RESEARCH_TOOL_OK' in e['result'] for e in own_events))
                self.assertIn('RESEARCH_TOOL_OK', response)


if __name__ == '__main__':
    unittest.main()
