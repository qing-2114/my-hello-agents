"""真实模型集成测试；配置或 API 不可用时失败，不回退 Mock。"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos"))
from anp_task_scheduler import DEMO_TASKS, assign_task, create_discovery, create_scheduler, load_llm


class SchedulerIntegrationTests(unittest.TestCase):
    def test_three_tasks_with_real_api(self):
        discovery = create_discovery()
        scheduler, tool = create_scheduler(discovery, load_llm())
        for description, gpu in DEMO_TASKS:
            with self.subTest(task=description):
                result = assign_task(scheduler, tool, discovery, description, gpu)
                self.assertEqual(len(result["nodes"]), 10)
                selected = next(s for s in discovery.list_all_services()
                                if s.service_id == result["selected_node"])
                if gpu:
                    self.assertTrue(selected.metadata["gpu"])
                self.assertTrue(tool.calls)
                print(f"通过：{description} -> {selected.service_id}；{result['reason']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
