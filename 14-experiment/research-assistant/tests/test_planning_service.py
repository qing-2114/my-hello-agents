"""规划解析和评分规则的确定性补充测试。"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))
from app.agents.research_agents import PlanningService
from app.models.schemas import TodoItem


class PlanningServiceTest(unittest.TestCase):
    def setUp(self):
        self.payload = [
            {'title': f'任务{i}', 'intent': '理解原理', 'query': f'asyncio topic {i}'}
            for i in range(1, 4)
        ]

    def test_json_extraction(self):
        self.payload[0]['title'] = '包含[方括号]和引号"的标题'
        raw = json.dumps(self.payload, ensure_ascii=False)
        for response in (raw, f'```json\n{raw}\n```', f'已规划如下：\n{raw}\n以上是三个任务。'):
            with self.subTest(response=response[:20]):
                self.assertEqual(PlanningService._extract_tasks(response), self.payload)

    def test_invalid_and_ambiguous_responses(self):
        raw = json.dumps(self.payload)
        for response in ('', 'not json', raw + raw, json.dumps(self.payload[:2]),
                         json.dumps({'tasks': self.payload}), '[null, null, null]'):
            with self.subTest(response=response[:20]):
                with self.assertRaises(ValueError):
                    PlanningService._extract_tasks(response)
        for bad_value in (' ', None, 123, ['query']):
            self.payload[0]['query'] = bad_value
            with self.assertRaisesRegex(ValueError, '任务1'):
                PlanningService._extract_tasks(json.dumps(self.payload))

    def test_scoring_chinese_duplicates_and_floor(self):
        tasks = [
            TodoItem(1, '基础', '概念', '异步编程事件循环原理'),
            TodoItem(2, '实践', '用法', 'asyncio task cancellation'),
            TodoItem(3, '限制', '边界', 'asyncio limitations'),
        ]
        self.assertEqual(PlanningService.evaluate_plan(tasks), {'score': 100, 'suggestions': []})
        tasks[2].query = 'asyncio'
        result = PlanningService.evaluate_plan(tasks)
        self.assertEqual(result['score'], 90)
        tasks[2].query = tasks[1].query.upper()
        self.assertEqual(PlanningService.evaluate_plan(tasks)['score'], 90)
        self.assertEqual(PlanningService.evaluate_plan(tasks[:1])['score'], 80)
        many = [TodoItem(i, '重复', '目标', 'x') for i in range(20)]
        self.assertEqual(PlanningService.evaluate_plan(many)['score'], 0)


if __name__ == '__main__':
    unittest.main()
