"""天气查询 MCP 服务。来源：https://hello-agents.datawhale.cc/"""

import json
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from hello_agents.protocols import MCPServer

weather_server = MCPServer(name="weather-server", description="真实天气查询服务")
CITY_MAP = {
    "北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou",
    "深圳": "Shenzhen", "杭州": "Hangzhou", "成都": "Chengdu",
    "重庆": "Chongqing", "武汉": "Wuhan", "西安": "Xi'an",
    "南京": "Nanjing", "天津": "Tianjin", "苏州": "Suzhou",
}


def get_wttr_weather(city: str) -> dict:
    """获取当前天气；中文映射外的城市也可直接交给 wttr.in 解析。"""
    city = city.strip()
    if not city or len(city) > 100:
        raise ValueError("城市名不能为空且不能超过 100 字符")
    location = quote(CITY_MAP.get(city, city), safe="")
    response = requests.get(f"https://wttr.in/{location}", params={"format": "j1"}, timeout=15)
    response.raise_for_status()
    data = response.json()
    current = data["current_condition"][0]
    return {
        "city": city,
        "resolved_location": data.get("nearest_area", []),
        "temperature": float(current["temp_C"]),
        "feels_like": float(current["FeelsLikeC"]),
        "humidity": int(current["humidity"]),
        "condition": current["weatherDesc"][0]["value"],
        "wind_speed": round(float(current["windspeedKmph"]) / 3.6, 1),
        "visibility": float(current["visibility"]),
        "observed_at": current.get("localObsDateTime"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "wttr.in",
        "units": {"temperature": "°C", "feels_like": "°C", "humidity": "%", "wind_speed": "m/s", "visibility": "km"},
    }


def get_open_meteo_weather(city: str) -> dict:
    """备用源：地理编码后查询 Open-Meteo 当前模型天气，非实测站观测。"""
    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": CITY_MAP.get(city, city), "count": 1, "language": "zh"}, timeout=15,
    )
    response.raise_for_status()
    locations = response.json().get("results", [])
    if not locations:
        raise ValueError("备用源未找到该城市")
    location = locations[0]
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": location["latitude"], "longitude": location["longitude"],
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "wind_speed_unit": "ms", "timezone": "auto"}, timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    current = data["current"]
    code = int(current["weather_code"])
    if code == 0:
        condition = "晴"
    elif code in (1, 2, 3):
        condition = {1: "大部晴朗", 2: "局部多云", 3: "阴"}[code]
    elif code in (45, 48):
        condition = "雾"
    elif code in (51, 53, 55, 56, 57):
        condition = "毛毛雨（可能冻雨）"
    elif code in (61, 63, 65, 66, 67, 80, 81, 82):
        condition = "雨（可能冻雨或阵雨）"
    elif code in (71, 73, 75, 77, 85, 86):
        condition = "雪"
    elif code in (95, 96, 99):
        condition = "雷暴（可能伴冰雹）"
    else:
        condition = f"WMO 天气代码 {code}"
    return {
        "city": city, "resolved_location": location,
        "temperature": float(current["temperature_2m"]),
        "feels_like": float(current["apparent_temperature"]),
        "humidity": int(current["relative_humidity_2m"]),
        "condition": condition, "weather_code": code,
        "wind_speed": float(current["wind_speed_10m"]), "visibility": None,
        "observed_at": current["time"], "timezone": data["timezone"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "Open-Meteo", "data_type": "当前模型天气，非气象站实测",
        "units": {"temperature": "°C", "feels_like": "°C", "humidity": "%", "wind_speed": "m/s", "visibility": "km"},
    }


def get_weather_data(city: str) -> dict:
    city = city.strip()
    if not city or len(city) > 100:
        raise ValueError("城市名不能为空且不能超过 100 字符")
    errors = []
    for provider in (get_wttr_weather, get_open_meteo_weather):
        try:
            result = provider(city)
            result["provider_attempts"] = len(errors) + 1
            if errors:
                result["fallback_reason"] = errors[0]
            return result
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            errors.append(f"{provider.__name__}: {type(exc).__name__}")
    raise ValueError("所有天气源查询失败；每个源各请求一次，无应用层重试。" + "; ".join(errors))


def get_weather(city: str) -> str:
    """查询城市当前天气（非全天预报），wttr.in 失败时使用 Open-Meteo；失败返回 error。"""
    try:
        result = get_weather_data(city)
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        result = {"error": f"{type(exc).__name__}: {exc}", "city": city}
    return json.dumps(result, ensure_ascii=False, indent=2)


def list_supported_cities() -> str:
    """列出内置中文城市映射；其他城市支持情况由上游决定。"""
    return json.dumps({"cities": list(CITY_MAP), "count": len(CITY_MAP)}, ensure_ascii=False)


def get_server_info() -> str:
    """获取服务器信息。"""
    return json.dumps({"name": "Weather MCP Server", "version": "1.0.0", "tools": ["get_weather", "list_supported_cities", "get_server_info"]})


weather_server.add_tool(get_weather)
weather_server.add_tool(list_supported_cities)
weather_server.add_tool(get_server_info)

if __name__ == "__main__":
    weather_server.run()
