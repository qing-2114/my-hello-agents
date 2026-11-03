"""可独立查询全球天气，不依赖高德 POI 是否覆盖目的地。"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException

from ...services.weather_service import WeatherService

router = APIRouter(prefix="/weather", tags=["天气"])


@router.get("/forecast")
def forecast(city: str, start_date: date, end_date: date,
             source: Literal["auto", "amap", "hko", "open_meteo"] = "auto"):
    if not city.strip() or len(city) > 100 or not 0 <= (end_date - start_date).days < 30:
        raise HTTPException(422, "请提供目的地及1–30天的有效日期范围")
    service = WeatherService()
    try:
        result = service.forecast(city, start_date, end_date, source)
        return {"city": city, "weather_info": result.weather_info, "notes": result.notes}
    finally:
        service.close()
