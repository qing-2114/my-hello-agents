"""工具执行和回调隔离的确定性补充验证，不调用模型。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))

from hello_agents.tools import Tool, ToolParameter, ToolRegistry
from app.agents.deep_research_agent import DeepResearchAgent
from app.agents.tool_aware_agent import ToolAwareSimpleAgent
from app.services.llm_service import create_llm


class ResearchLookupTool(Tool):
    """固定演示资料工具，不是搜索引擎。"""
    def __init__(self):
        super().__init__('research_lookup', '查询本地演示研究资料，返回验证标记')
        self.calls = []

    def get_parameters(self):
        return [ToolParameter(name='query', type='string', description='查询关键词')]

    def run(self, parameters):
        self.calls.append(dict(parameters))
        if parameters.get('query') == 'fail':
            raise ValueError('演示工具错误')
        return 'RESEARCH_TOOL_OK: asyncio supports concurrent code using async/await.'


class ToolListenerTest(unittest.TestCase):
    def setUp(self):
        self.tool = ResearchLookupTool()
        self.registry = ToolRegistry()
        self.registry.register_tool(self.tool)
        self.events = []
        self.agent = ToolAwareSimpleAgent(
            name='研究助手', system_prompt='研究工具测试', llm=create_llm(),
            tool_registry=self.registry, tool_call_listener=self.events.append,
        )

    def test_success_and_parameters(self):
        result = self.agent._execute_tool_call('research_lookup', '{"query":"asyncio"}')
        self.assertIn('RESEARCH_TOOL_OK', result)
        self.assertEqual(len(self.tool.calls), 1)
        self.assertEqual(self.events, [{
            'agent_name': '研究助手', 'tool_name': 'research_lookup',
            'parsed_parameters': {'query': 'asyncio'}, 'result': result,
        }])

    def test_listener_failure_does_not_repeat_tool(self):
        def broken_listener(info):
            raise RuntimeError('listener failed')
        self.agent._tool_call_listener = broken_listener
        with self.assertLogs('app.agents.tool_aware_agent', level='WARNING'):
            result = self.agent._execute_tool_call('research_lookup', '{"query":"asyncio"}')
        self.assertIn('RESEARCH_TOOL_OK', result)
        self.assertEqual(len(self.tool.calls), 1)

    def test_tool_failure_and_missing_tool_emit_events(self):
        result = self.agent._execute_tool_call('research_lookup', '{"query":"fail"}')
        self.assertIn('工具调用失败', result)
        self.assertEqual(self.events[0]['parsed_parameters'], {'query': 'fail'})
        self.agent._execute_tool_call('missing_tool', '{}')
        self.assertEqual(len(self.events), 2)
        self.agent.tool_registry = None
        self.agent._execute_tool_call('research_lookup', '{}')
        self.assertEqual(len(self.events), 3)

    def test_three_roles_forward_events(self):
        research = DeepResearchAgent(create_llm(), self.registry, self.events.append)
        for service in (research.planner, research.summarizer, research.reporter):
            service._agent._execute_tool_call('research_lookup', '{"query":"asyncio"}')
        self.assertEqual([event['agent'] for event in self.events],
                         ['TODO Planner', 'Task Summarizer', 'Report Writer'])
        self.assertTrue(all(event['type'] == 'tool_call' for event in self.events))
        self.assertTrue(all(event['parameters'] == {'query': 'asyncio'} for event in self.events))


if __name__ == '__main__':
    unittest.main()
