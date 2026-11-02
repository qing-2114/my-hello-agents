"""真实 stdio MCP + wttr.in 测试；错误必须导致非零退出。"""

import asyncio
import json
import sys
from pathlib import Path

from hello_agents.protocols import MCPClient

SERVER = Path(__file__).resolve().parents[1] / "demos" / "weather_mcp_server.py"


async def test_weather_server():
    failures = []
    async with MCPClient([sys.executable, "-X", "utf8", str(SERVER)]) as client:
        tools = await client.list_tools()
        assert {t["name"] for t in tools} == {"get_weather", "list_supported_cities", "get_server_info"}
        info = json.loads(await client.call_tool("get_server_info", {}))
        assert info["name"] == "Weather MCP Server"
        cities = json.loads(await client.call_tool("list_supported_cities", {}))
        assert cities["count"] == len(cities["cities"]) == 12
        invalid = json.loads(await client.call_tool("get_weather", {"city": " "}))
        assert "error" in invalid
        print("PASS: 工具发现、元数据、空城市错误分支")
        for city in ("北京", "深圳"):
            weather = json.loads(await client.call_tool("get_weather", {"city": city}))
            if "error" in weather:
                failures.append(f"{city}: {weather['error']}")
                continue
            assert weather["city"] == city
            assert isinstance(weather["temperature"], (int, float))
            assert 0 <= weather["humidity"] <= 100
            assert weather["wind_speed"] >= 0
            assert weather["visibility"] is None or weather["visibility"] >= 0
            assert weather["condition"] and weather["source"] in {"wttr.in", "Open-Meteo"}
            assert weather["provider_attempts"] in (1, 2)
            if weather["source"] == "Open-Meteo":
                assert weather["fallback_reason"] and weather["data_type"]
            print(f"PASS: {city} {weather['temperature']}°C {weather['condition']} 来源={weather['source']}")
    if failures:
        raise AssertionError("真实天气 API 测试未完成：" + "; ".join(failures))
    print("PASS: 所有真实天气 MCP 测试通过")


if __name__ == "__main__":
    asyncio.run(test_weather_server())
