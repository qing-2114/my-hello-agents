"""需先启动8003后端；真实HTTP、SSE、搜索与模型的端到端测试。"""
import json
from pathlib import Path
import unittest

import requests
from dotenv import dotenv_values


class RealHttpResearchTest(unittest.TestCase):
    def test_real_sse(self):
        root = Path(__file__).resolve().parents[3]
        backend = 'tavily' if dotenv_values(root / '.env').get('TAVILY_API_KEY') else 'duckduckgo'
        events = []
        with requests.post('http://127.0.0.1:8003/api/research', json={
            'topic': 'Python asyncio 入门：核心概念、实践与限制。请规划3个任务，报告精练。',
            'search_api': backend,
        }, stream=True, timeout=(10, 180)) as response:
            response.raise_for_status()
            response.encoding = 'utf-8'
            self.assertIn('text/event-stream', response.headers['Content-Type'])
            for line in response.iter_lines(decode_unicode=True):
                if not line.startswith('data: '):
                    continue
                event = json.loads(line[6:])
                events.append(event)
                if event['type'] == 'progress':
                    print(event['text'], flush=True)
        self.assertTrue(events)
        self.assertEqual(events[-1]['type'], 'completed')
        self.assertFalse(any(event['type'] == 'error' for event in events))
        tasks = next(event['data'] for event in events if event['type'] == 'plan')
        summaries = [event for event in events if event['type'] == 'task_summary']
        self.assertEqual(len(summaries), len(tasks))
        self.assertTrue(all(event['source_urls'] for event in summaries))
        percentages = [event['percentage'] for event in events if event['type'] == 'progress']
        self.assertEqual(percentages, sorted(percentages))
        self.assertEqual(percentages[-1], 100)
        report = next(event['data'] for event in events if event['type'] == 'report')
        self.assertTrue(report.startswith('#'))
        self.assertIn('http', report)
        output = root / '14-experiment' / '.local' / 'research-assistant' / 'http'
        output.mkdir(parents=True, exist_ok=True)
        (output / 'last-events.json').write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8')
        (output / 'last-report.md').write_text(report, encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
