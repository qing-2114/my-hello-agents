"""SSE协议、输入验证和线程桥接的确定性补充测试；不替代真实API验证。"""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))
from fastapi.testclient import TestClient
from app.api.main import app, StreamAdapter, encode_sse


class HttpStreamTest(unittest.TestCase):
    def test_validation(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/healthz').json(), {'status': 'ok'})
            for body in ({'topic': ' '}, {'topic': 'x', 'search_api': 'invalid'}, {'topic': 'x' * 1001}):
                self.assertEqual(client.post('/api/research', json=body).status_code, 422)

    def test_adapter_progress_and_unicode(self):
        events = []
        adapter = StreamAdapter(events.append)
        adapter({'type': 'status', 'stage': 'planning', 'message': '规划'})
        adapter({'type': 'tasks', 'tasks': [{'id': 1, 'title': '任务'}]})
        adapter({'type': 'task_started', 'task_id': 1})
        adapter({'type': 'task_completed', 'task_id': 1})
        adapter({'type': 'status', 'stage': 'reporting', 'message': '报告'})
        percentages = [event['percentage'] for event in events if event['type'] == 'progress']
        self.assertEqual(percentages, [5, 10, 10, 80, 90])
        frame = encode_sse({'type': 'report', 'data': '# 中文\n\n内容'})
        self.assertTrue(frame.endswith('\n\n'))
        self.assertEqual(json.loads(frame[6:].strip())['data'], '# 中文\n\n内容')

    def test_worker_stream_and_error(self):
        class Runner:
            def __init__(self, **kwargs):
                self.listener = kwargs['event_listener']
            def run(self, topic):
                self.listener({'type': 'status', 'stage': 'planning', 'message': '规划'})
                self.listener({'type': 'report', 'content': '# 测试报告'})
        with TestClient(app) as client, patch('app.api.main.DeepResearchAgent', Runner):
            response = client.post('/api/research', json={'topic': '协议验证'})
            self.assertIn('text/event-stream', response.headers['content-type'])
            events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
            self.assertEqual(events[-1], {'type': 'completed'})
            self.assertTrue(any(event.get('percentage') == 100 for event in events))
        with TestClient(app) as client, patch('app.api.main.DeepResearchAgent', side_effect=RuntimeError('private detail')):
            response = client.post('/api/research', json={'topic': '错误验证'})
            self.assertIn('"type": "error"', response.text)
            self.assertNotIn('private detail', response.text)
            self.assertNotIn('"type": "completed"', response.text)


if __name__ == '__main__':
    unittest.main()
