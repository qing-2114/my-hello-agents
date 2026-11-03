"""真实高德 MCP 连接、自动展开及搜索/天气调用验证。"""

import contextlib
import tempfile
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos" / "backend"))

from app.agents.trip_planner_agent import TripPlannerAgent


def test_real_amap_mcp():
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as logs, contextlib.redirect_stdout(logs), contextlib.redirect_stderr(logs):
        planner = TripPlannerAgent()
        tool = planner.mcp_tool
        names = planner.attraction_agent.list_tools()
        for agent in (planner.attraction_agent, planner.weather_agent, planner.hotel_agent):
            assert agent.llm is planner.llm
            assert set(agent.list_tools()) == set(names)
            for name in names:
                assert agent.tool_registry.get_tool(name).mcp_tool is tool
        assert {"amap_maps_text_search", "amap_maps_weather"} <= set(names)
        for name, args in (
            ("maps_text_search", {"keywords": "故宫博物院", "city": "北京"}),
            ("maps_weather", {"city": "北京"}),
        ):
            result = tool.run({"tool_name": name, "arguments": args})
            # MCP text content 包装中包含高德原始 JSON。
            assert result.startswith(f"工具 '{name}' 执行结果:\n"), "MCP 工具调用失败"
            parsed = json.loads(result.split("\n", 1)[1])
            if isinstance(parsed, list):
                parsed = [json.loads(item["text"]) for item in parsed if item.get("type") == "text"]
                assert parsed, "MCP 未返回文本内容"
            else:
                parsed = [parsed]
            success = any(str(item.get("status")) == "1" or (
                "status" not in item and (item.get("pois") or item.get("forecasts") or item.get("lives"))
            ) for item in parsed)
            if not success:
                raise AssertionError(f"{name}: result keys=" + str([list(item) for item in parsed])
                                     + "; info=" + str([item.get("info") for item in parsed]))
    print(f"PASS: {len(names)} expanded tools; real POI search and weather succeeded")
    print("\n".join(names))


if __name__ == "__main__":
    test_real_amap_mcp()

