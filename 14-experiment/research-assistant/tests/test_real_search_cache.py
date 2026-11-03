"""真实搜索首次落盘，第二次命中缓存且不重复请求。"""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))
from dotenv import dotenv_values
from app.config import Configuration, ROOT, SearchAPI
from app.services.search_service import SearchService


class RealSearchCacheTest(unittest.TestCase):
    def test_real_cache(self):
        backend = SearchAPI.TAVILY if dotenv_values(ROOT / '.env').get('TAVILY_API_KEY') else SearchAPI.DUCKDUCKGO
        with TemporaryDirectory() as workspace:
            service = SearchService(config=Configuration(
                search_api=backend, search_cache_dir=workspace, max_tokens_per_source=100,
            ))
            with patch.object(service, '_execute_search', wraps=service._execute_search) as execute:
                first = service.search('site:docs.python.org asyncio coroutines', max_results=2)
                cached = service.search('site:docs.python.org asyncio coroutines', max_results=2)
                self.assertTrue(first)
                self.assertEqual(first, cached)
                self.assertEqual(execute.call_count, 1)
            self.assertEqual(len(list(Path(workspace).glob('*.json'))), 1)


if __name__ == '__main__':
    unittest.main()
