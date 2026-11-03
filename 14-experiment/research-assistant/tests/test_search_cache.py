"""缓存命中、损坏回退、参数隔离与过期的补充测试。"""
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))
from app.config import Configuration
from app.services.search_service import SearchService
from app.agents.research_agents import ReportingService
from app.models.schemas import TodoItem


class SearchCacheTest(unittest.TestCase):
    def test_cache_lifecycle(self):
        with TemporaryDirectory() as workspace, patch('app.services.search_service.SearchTool') as tool:
            tool.return_value.run.return_value = {'results': [
                {'title': '资料', 'url': 'https://example.org/a', 'content': 'x' * 50},
            ]}
            service = SearchService(config=Configuration(search_cache_dir=workspace))
            first = service.search('测试', max_results=2)
            first[0]['title'] = '修改调用结果'
            cached = service.search('测试', max_results=2)
            self.assertEqual(cached[0]['title'], '资料')
            self.assertEqual(tool.return_value.run.call_count, 1)
            reopened = SearchService(config=service.config)
            self.assertEqual(reopened.search('测试', 2), cached)
            self.assertEqual(tool.return_value.run.call_count, 1)
            service.search('测试', 2, use_cache=False)
            self.assertEqual(tool.return_value.run.call_count, 2)
            path = service.cache_dir / f'{service._generate_cache_key("测试", 2)}.json'
            path.write_text('{broken', encoding='utf-8')
            service.search('测试', 2)
            self.assertEqual(tool.return_value.run.call_count, 3)
            old = time.time() - service.config.search_cache_ttl_seconds - 10
            os.utime(path, (old, old))
            service.search('测试', 2)
            self.assertEqual(tool.return_value.run.call_count, 4)
            key = service._generate_cache_key('测试', 2)
            service.config.max_tokens_per_source = 10
            self.assertNotEqual(key, service._generate_cache_key('测试', 2))
            self.assertNotEqual(key, service._generate_cache_key('测试', 3))
            self.assertFalse(list(Path(workspace).glob('*.tmp')))

    def test_report_input_preserves_sources_outside_summary(self):
        task = TodoItem(7, '任务', '研究目标', 'query')
        text = ReportingService._format_summaries([(task, '总结中没有链接', ['https://example.org/a'])])
        self.assertIn('[T7-S1] https://example.org/a', text)
        self.assertIn('研究目标', text)


if __name__ == '__main__':
    unittest.main()
