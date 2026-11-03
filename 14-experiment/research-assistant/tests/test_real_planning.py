"""真实模型生成规划并执行结构校验和质量评分。"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demos' / 'backend'))
from app.agents.research_agents import PlanningService
from app.models.schemas import SummaryState
from app.services.llm_service import create_llm


class RealPlanningTest(unittest.TestCase):
    def test_plan_and_evaluate(self):
        planner = PlanningService(create_llm())
        state = SummaryState('研究Python asyncio的核心概念、工程实践和适用边界')
        tasks = planner.plan_todo_list(state)
        self.assertTrue(3 <= len(tasks) <= 5)
        self.assertEqual([task.id for task in tasks], list(range(1, len(tasks) + 1)))
        self.assertEqual(state.todo_items, tasks)
        self.assertTrue(all(task.title and task.intent and task.query for task in tasks))
        result = planner.evaluate_plan(tasks)
        self.assertTrue(0 <= result['score'] <= 100)
        self.assertIsInstance(result['suggestions'], list)
        self.assertEqual(planner._agent._history, [])
        print(json.dumps({'tasks_count': len(tasks), **result}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    unittest.main()
