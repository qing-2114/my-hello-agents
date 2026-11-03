"""真实模型验证三个角色；资料为固定测试输入，不代表运行了搜索引擎。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))

from app.agents.research_agents import PlanningService, SummarizationService, ReportingService
from app.models.schemas import SummaryState
from app.services.llm_service import create_llm


class RealAgentsTest(unittest.TestCase):
    def test_three_agents(self):
        llm = create_llm()
        state = SummaryState(research_topic='Python asyncio 的概念、并发使用与限制')
        tasks = PlanningService(llm).plan_todo_list(state)
        self.assertTrue(3 <= len(tasks) <= 5)
        # 固定资料只用于验证总结与报告接口，不作为完整研究成果。
        sources = [{
            'title': 'Python documentation: asyncio',
            'url': 'https://docs.python.org/3/library/asyncio.html',
            'snippet': 'asyncio is a library to write concurrent code using the async/await syntax. '
                       'asyncio is often a perfect fit for IO-bound and high-level structured network code.',
        }]
        task = tasks[0]
        summary, source_urls = SummarizationService(llm).summarize_task(task, sources)
        self.assertEqual(source_urls, [source['url'] for source in sources])
        marker = f'[T{task.id}-S1]'
        self.assertIn(marker, summary)
        self.assertIn(sources[0]['url'], summary)
        report = ReportingService(llm).generate_report(state.research_topic, [(task, summary, source_urls)])
        self.assertIn(marker, report)
        self.assertIn(sources[0]['url'], report)
        self.assertTrue(report.startswith('#'))


if __name__ == '__main__':
    unittest.main()
