"""多源真实预报：香港天文台、高德、Open-Meteo；逐日补缺，不外推。"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from math import isfinite

import requests

from ..config import get_settings
from ..models.schemas import Location, WeatherInfo


HKO_CITIES = {"香港", "香港特别行政区", "香港特別行政區", "hong kong", "hongkong"}
SOURCE_NAMES = {"hko": "香港天文台", "amap": "高德天气", "open_meteo": "Open-Meteo"}
# 全球地名服务对中文别名存在歧义，例如“伦敦”首项可能是加拿大城市。
CITY_ALIASES = {
    "东京": ("Tokyo", "JP"), "東京": ("Tokyo", "JP"), "日本东京": ("Tokyo", "JP"),
    "伦敦": ("London", "GB"), "倫敦": ("London", "GB"), "英国伦敦": ("London", "GB"),
    "台北": ("Taipei", "TW"), "臺北": ("Taipei", "TW"), "台北市": ("Taipei", "TW"),
    "澳门": ("Macao", "MO"), "澳門": ("Macao", "MO"),
    "巴黎": ("Paris", "FR"), "纽约": ("New York", "US"),
    "首尔": ("Seoul", "KR"), "新加坡": ("Singapore", "SG"),
    "大阪": ("Osaka", "JP"), "曼谷": ("Bangkok", "TH"), "悉尼": ("Sydney", "AU"),
}
WMO = {
    0: "晴", 1: "大致晴朗", 2: "局部多云", 3: "阴", 45: "雾", 48: "冻雾",
    51: "小毛毛雨", 53: "毛毛雨", 55: "强毛毛雨", 56: "轻冻毛毛雨", 57: "强冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "轻冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒", 80: "小阵雨",
    81: "中阵雨", 82: "强阵雨", 85: "小阵雪", 86: "强阵雪",
    95: "雷雨", 96: "雷雨伴小冰雹", 99: "雷雨伴大冰雹",
}


class WeatherSourceError(RuntimeError):
    """不包含请求 URL、密钥的天气源失败。"""


@dataclass
class WeatherResult:
    weather_info: list[WeatherInfo] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class WeatherService:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "HelloAgentsTripAssistant/1.0"

    def close(self):
        self.session.close()

    def _get(self, url, params):
        try:
            response = self.session.get(url, params=params, timeout=(5, 15))
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("invalid payload")
            return data
        except (requests.RequestException, ValueError):
            raise WeatherSourceError("天气服务请求失败或响应无效") from None

    def forecast(self, city: str, start: date, end: date, preferred="auto",
                 location: Location | None = None) -> WeatherResult:
        if preferred not in {"auto", *SOURCE_NAMES}:
            raise ValueError("不支持的天气源")
        if not 0 <= (end - start).days < 30:
            raise ValueError("天气日期范围应为1–30天")
        is_hk = city.strip().lower() in HKO_CITIES
        order = ["hko", "open_meteo"] if is_hk else ["amap", "open_meteo"]
        if preferred != "auto":
            order = [preferred] + [p for p in order if p != preferred]
        expected = {(start + timedelta(days=i)).isoformat() for i in range((end-start).days+1)}
        found = {}
        result = WeatherResult()
        for provider in order:
            if expected <= found.keys():
                break
            if provider == "hko" and not is_hk:
                result.notes.append("香港天文台仅适用于香港，已改用其他来源。")
                continue
            try:
                if provider == "hko":
                    rows = self._hko()
                elif provider == "amap":
                    rows = self._amap(city)
                else:
                    rows = self._open_meteo(city, location)
                if not rows:
                    raise WeatherSourceError("没有有效预报")
                added = 0
                for row in rows:
                    if row.date in expected and row.date not in found:
                        found[row.date] = row
                        added += 1
                if not added:
                    result.notes.append(f"{SOURCE_NAMES[provider]}的预报暂未覆盖所选日期，尝试其他来源。")
            except (WeatherSourceError, ValueError, KeyError, TypeError, IndexError):
                result.notes.append(f"{SOURCE_NAMES[provider]}暂不可用，已尝试其他来源。")
        result.weather_info = [found[d] for d in sorted(found)]
        missing = sorted(expected - found.keys())
        if missing:
            result.notes.append("以下日期没有可用预报（可能超出预报范围）：" + "、".join(missing) + "。出行前请再次查询。")
        return result

    def _hko(self):
        data = self._get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php",
                         {"dataType": "fnd", "lang": "tc"})
        rows = []
        for day in data.get("weatherForecast", []):
            try:
                d = day["forecastDate"]
                rows.append(WeatherInfo(
                    date=date(int(d[:4]), int(d[4:6]), int(d[6:8])).isoformat(),
                    day_weather=day["forecastWeather"], night_weather=day["forecastWeather"],
                    day_temp=round(float(day["forecastMaxtemp"]["value"])),
                    night_temp=round(float(day["forecastMintemp"]["value"])),
                    wind_direction="", wind_power=day["forecastWind"],
                    source="香港天文台", source_url="https://www.hko.gov.hk/tc/wxinfo/currwx/fnd.htm",
                    temperature_basis="daily_range"))
            except (ValueError, KeyError, TypeError, OverflowError):
                continue
        return rows

    def _amap(self, city):
        data = self._get("https://restapi.amap.com/v3/weather/weatherInfo", {
            "key": get_settings().amap_api_key, "city": city, "extensions": "all"})
        if data.get("status") != "1":
            raise WeatherSourceError("高德不支持该城市或服务暂不可用")
        rows = []
        for forecast in data.get("forecasts", []):
            for day in forecast.get("casts", []):
                try:
                    rows.append(WeatherInfo(
                        date=date.fromisoformat(day["date"]).isoformat(),
                        day_weather=day["dayweather"], night_weather=day["nightweather"],
                        day_temp=round(float(day["daytemp"])), night_temp=round(float(day["nighttemp"])),
                        wind_direction=day["daywind"], wind_power=day["daypower"] + "级",
                        source="高德天气", source_url="https://lbs.amap.com/api/webservice/guide/api/weatherinfo"))
                except (ValueError, KeyError, TypeError, OverflowError):
                    continue
        return rows

    def _coordinates(self, city):
        if city.strip().lower() in HKO_CITIES:
            return Location(latitude=22.3193, longitude=114.1694)
        query, country = CITY_ALIASES.get(city.strip(), (city, None))
        params = {"name": query, "count": 10, "language": "zh", "format": "json"}
        if country:
            params["countryCode"] = country
        data = self._get("https://geocoding-api.open-meteo.com/v1/search", params)
        places = data.get("results") or []
        if country:
            places = [p for p in places if p.get("country_code") == country]
        if not places:
            raise WeatherSourceError("目的地未定位")
        place = max(places, key=lambda p: p.get("population") or 0)
        return Location(latitude=place["latitude"], longitude=place["longitude"])

    def _open_meteo(self, city, location=None):
        point = location or self._coordinates(city)
        data = self._get("https://api.open-meteo.com/v1/forecast", {
            "latitude": point.latitude, "longitude": point.longitude,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,wind_speed_10m_max,wind_direction_10m_dominant",
            "timezone": "auto", "forecast_days": 16, "wind_speed_unit": "kmh"})
        daily = data.get("daily", {})
        rows = []
        directions = ["北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风"]
        for i, day in enumerate(daily.get("time", [])):
            try:
                high, low, speed, angle = [float(daily[key][i]) for key in (
                    "temperature_2m_max", "temperature_2m_min", "wind_speed_10m_max", "wind_direction_10m_dominant")]
                if not all(isfinite(v) for v in (high, low, speed, angle)):
                    continue
                description = WMO.get(int(daily["weather_code"][i]), "天气现象未分类")
                rows.append(WeatherInfo(
                    date=date.fromisoformat(day).isoformat(), day_weather=description, night_weather=description,
                    day_temp=round(high), night_temp=round(low), wind_direction=directions[int((angle+22.5)//45) % 8],
                    wind_power=f"最大风速 {speed:g} km/h", source="Open-Meteo",
                    source_url="https://open-meteo.com/", temperature_basis="daily_range"))
            except (ValueError, KeyError, TypeError, IndexError, OverflowError):
                continue
        return rows
