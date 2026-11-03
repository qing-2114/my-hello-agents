"""真实多源天气及故障注入后的真实备用验证，不回显密钥。"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos" / "backend"))

from app.agents.trip_planner_agent import TripPlannerAgent
from app.services.weather_service import WeatherService, WeatherSourceError


def test_real_weather_sources():
    service = WeatherService()
    try:
        # 以香港源实际返回日期为基准，避免执行主机与供应商时区差异。
        original_hko = service._hko
        hko = original_hko()
        assert len(hko) >= 4 and all(w.source == "香港天文台" for w in hko)
        start = date.fromisoformat(hko[0].date)
        end = start + timedelta(days=3)
        expected = [(start + timedelta(days=i)).isoformat() for i in range(4)]
        service._hko = lambda: hko  # 已取得的真实响应，不重复请求同一来源。
        result = service.forecast("香港", start, end)
        assert [w.date for w in result.weather_info] == expected
        assert all(w.source == "香港天文台" for w in result.weather_info)
        assert all(w.temperature_basis == "daily_range" and w.source_url for w in result.weather_info)
        print("PASS: real HKO Hong Kong four-day forecast, provenance and daily temperature range")

        global_result = service.forecast("香港", start, end, "open_meteo")
        assert [w.date for w in global_result.weather_info] == expected
        assert all(w.source == "Open-Meteo" for w in global_result.weather_info)
        print("PASS: real Open-Meteo Hong Kong four-day forecast")

        def unavailable():
            raise WeatherSourceError("injected failure")

        service._hko = unavailable
        fallback = service.forecast("香港", start, end)
        assert len(fallback.weather_info) == 4
        assert all(w.source == "Open-Meteo" for w in fallback.weather_info)
        assert fallback.notes
        print("PASS: injected HKO failure -> real Open-Meteo fallback")

        service._hko = lambda: hko[1:]
        partial = service.forecast("香港", start, end)
        assert len(partial.weather_info) == 4
        assert partial.weather_info[0].source == "Open-Meteo"
        assert all(w.source == "香港天文台" for w in partial.weather_info[1:])
        print("PASS: partial real HKO evidence -> missing date filled by real Open-Meteo")

        service._hko = lambda: hko
        far = start + timedelta(days=40)
        beyond = service.forecast("香港", far, far)
        assert not beyond.weather_info and any(far.isoformat() in n for n in beyond.notes)
        print("PASS: out-of-horizon dates stay missing; no fabricated weather")

        for city in ("Tokyo", "London"):
            overseas = service.forecast(city, start, end, "open_meteo")
            assert len(overseas.weather_info) == 4
            assert all(w.source == "Open-Meteo" for w in overseas.weather_info)
            print(f"PASS: real global geocoding and forecast for {city}")

        for city, bounds in (("东京", (139, 140, 35, 36)), ("伦敦", (-1, 1, 51, 52)),
                             ("台北", (121, 122, 25, 26))):
            point = service._coordinates(city)
            assert bounds[0] < point.longitude < bounds[1] and bounds[2] < point.latitude < bounds[3]
        print("PASS: Chinese overseas city aliases resolve to the intended country and coordinates")

        beijing = service.forecast("北京", start, start, "amap")
        assert len(beijing.weather_info) == 1 and beijing.weather_info[0].source == "高德天气"
        print("PASS: real Amap Beijing forecast retained")

        # 模型缺省、无效或编造的天气不会替换后端原始预报。
        payload = '{"city":"香港","start_date":"' + str(start) + '","end_date":"' + str(end) + '","overall_suggestions":"","weather_info":"invalid"}'
        parsed = TripPlannerAgent._parse_trip_plan(payload, result.weather_info)
        assert parsed.weather_info == result.weather_info
        print("PASS: planner weather overwritten by verified source records before schema validation")
    finally:
        service.close()


if __name__ == "__main__":
    try:
        test_real_weather_sources()
    except Exception as error:
        print("FAIL: 真实天气测试未完成；错误类型：" + type(error).__name__)
        raise SystemExit(1)
