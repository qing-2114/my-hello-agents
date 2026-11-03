"""真实搜索与真实模型验证摘要预算后的来源可用性。"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))
from dotenv import dotenv_values
from app.config import Configuration, ROOT, SearchAPI
from app.models.schemas import TodoItem
from app.services.search_service import SearchService
from app.services.llm_service import create_llm
from app.agents.research_agents import SummarizationService


class RealSearchTest(unittest.TestCase):
    def test_search_and_summarize(self):
        backend = SearchAPI.TAVILY if dotenv_values(ROOT / '.env').get('TAVILY_API_KEY') else SearchAPI.DUCKDUCKGO
        sources = SearchService(config=Configuration(
            search_api=backend, max_search_results=3, max_tokens_per_source=200,
        )).search('site:docs.python.org asyncio tasks event loop', use_cache=False)
        self.assertTrue(1 <= len(sources) <= 3)
        self.assertEqual(len({source['url'] for source in sources}), len(sources))
        self.assertTrue(all(len(source['snippet']) <= 800 for source in sources))
        summary, urls = SummarizationService(create_llm()).summarize_task(
            TodoItem(id=1, title='asyncio基础', intent='了解任务与事件循环', query='asyncio tasks'), sources,
        )
        self.assertEqual(urls, [source['url'] for source in sources])
        self.assertRegex(summary, r'\[T1-S\d+\]')
        self.assertTrue(any(source['url'] in summary for source in sources))
        print(f'真实搜索后端：{backend.value}；有效来源：{len(sources)}', flush=True)


if __name__ == '__main__':
    unittest.main()
