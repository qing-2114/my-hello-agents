"""来源处理和搜索配置的确定性补充测试。"""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))
from app.config import Configuration, SearchAPI
from app.services.search_service import SearchService
from app.services.source_processing import deduplicate_sources, limit_source_tokens


class SearchProcessingTest(unittest.TestCase):
    def test_deduplicate_and_budget(self):
        source = {'title': '资料', 'url': 'https://example.org/a', 'snippet': '中' * 20}
        other = {**source, 'url': 'https://example.org/b'}
        self.assertEqual(deduplicate_sources([source, source, other]), [source, other])
        limited = limit_source_tokens(source, 2)
        self.assertEqual(limited['snippet'], '中' * 5 + '...')
        self.assertEqual(source['snippet'], '中' * 20)
        self.assertEqual(limit_source_tokens({**source, 'snippet': '12345678'}, 2)['snippet'], '12345678')
        with self.assertRaises(ValueError):
            limit_source_tokens(source, 0)

    def test_config_validation(self):
        self.assertEqual(Configuration().search_api, SearchAPI.DUCKDUCKGO)
        for backend in SearchAPI:
            self.assertEqual(Configuration(search_api=backend.value).search_api, backend)
        for kwargs in ({'search_api': 'invalid'}, {'max_search_results': 0}, {'max_tokens_per_source': 0}):
            with self.assertRaises(ValueError):
                Configuration(**kwargs)

    def test_search_normalizes_filters_and_limits(self):
        with patch('app.services.search_service.SearchTool') as tool:
            tool.return_value.run.return_value = {'results': [
                {'title': 'A', 'url': 'https://example.org/a', 'content': 'x' * 50},
                {'title': 'A duplicate', 'url': 'https://example.org/a', 'content': 'duplicate'},
                {'title': 'Invalid', 'url': 'file:///tmp/a', 'content': 'invalid'},
                {'title': 'B', 'url': 'https://example.org/b', 'snippet': 'valid'},
            ]}
            result = SearchService(config=Configuration(max_tokens_per_source=2)).search('query', use_cache=False)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['title'], 'A')
            self.assertEqual(len(result[0]['snippet']), 8)
            tool.return_value.run.return_value = {'results': []}
            with self.assertRaises(RuntimeError):
                SearchService().search('query', use_cache=False)


if __name__ == '__main__':
    unittest.main()
