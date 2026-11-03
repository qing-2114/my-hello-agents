"""手动运行的真实 LLM + 高德 MCP 集成验证；不输出底层日志与配置。"""

import contextlib
import tempfile
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos" / "backend"))

from app.agents.trip_planner_agent import TripPlannerAgent
from app.models.schemas import TripPlanRequest


def test_real_trip_planner():
    request = TripPlanRequest(
        city="北京", start_date=date.today().isoformat(),
        end_date=date.today().isoformat(), days=1,
        preferences=["历史文化"], budget=1000,
        transportation="公共交通", accommodation="经济型",
    )
    # 框架可能打印底层调用信息；验证不回显这些日志。
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as logs, contextlib.redirect_stdout(logs), contextlib.redirect_stderr(logs):
        planner = TripPlannerAgent()
        plan = planner.plan_trip(request)
    assert len(plan.days) == 1
    day = plan.days[0]
    assert 2 <= len(day.attractions) <= 3
    assert {"breakfast", "lunch", "dinner"} <= {meal.type for meal in day.meals}
    assert plan.budget is not None
    b = plan.budget
    assert b.total == b.total_attractions + b.total_hotels + b.total_meals + b.total_transportation
    assert all(agent.list_tools() for agent in (
        planner.attraction_agent, planner.weather_agent, planner.hotel_agent
    ))
    print("PASS: real LLM + MCP trip, 2-3 attractions, three meals, budget sum")


if __name__ == "__main__":
    test_real_trip_planner()

