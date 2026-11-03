"""高德 MCP 工具工厂，供三个查询 Agent 共享。"""

from hello_agents.tools import MCPTool

from ..config import get_settings


def create_amap_mcp_tool() -> MCPTool:
    settings = get_settings()
    if not settings.amap_api_key:
        raise ValueError("项目根目录 .env 缺少 AMAP_API_KEY/AMAP_MAPS_API_KEY")
    tool = MCPTool(
        name="amap",
        description="高德地图搜索、天气及路线查询",
        server_command=["uvx", "--with", "pydantic==2.10.6", "amap-mcp-server"],
        env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
        auto_expand=True,
    )
    tool.expandable = True
    names = {item.name for item in tool.get_expanded_tools()}
    if not {"amap_maps_text_search", "amap_maps_weather"} <= names:
        raise RuntimeError("高德 MCP 工具发现失败，请检查 uvx、网络和 MCP 服务启动环境")
    return tool


class MapDataError(RuntimeError):
    """地图数据不可用，不能生成带虚构位置的行程。"""


def search_verified_places(city: str, keywords: str) -> list[dict]:
    """补全 MCP 搜索结果省略的坐标，保留高德原始地点凭据。"""
    import requests
    try:
        response = requests.get("https://restapi.amap.com/v3/place/text", params={
            "key": get_settings().amap_api_key, "keywords": keywords,
            "city": city, "citylimit": "true", "offset": 25,
        }, timeout=20)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "1":
            raise ValueError("地图查询失败")
        places = []
        for poi in data.get("pois", []):
            try:
                longitude, latitude = map(float, poi["location"].split(","))
                if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                    continue
                places.append({"name": poi["name"], "address": poi.get("address") or "",
                               "location": {"longitude": longitude, "latitude": latitude}})
            except (KeyError, ValueError, TypeError):
                continue
        if not places:
            raise ValueError("没有可核实坐标的地点")
        return places
    except (requests.RequestException, ValueError, TypeError):
        raise MapDataError("高德地点查询未取得有效名称和坐标，请稍后重试或更换目的地") from None
