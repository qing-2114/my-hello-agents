"""智能旅行助手的数据模型。"""

from typing import List, Optional, Literal
from datetime import date
import re

from pydantic import BaseModel, Field, field_validator, model_validator


class TripPlanRequest(BaseModel):
    """用户的旅行规划需求。"""

    city: str = Field(..., min_length=1, description="目的地城市")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    days: int = Field(..., ge=1, le=30, description="旅行天数")
    preferences: List[str] = Field(default_factory=list, description="旅行偏好")
    budget: Optional[int] = Field(default=None, ge=0, description="每人预算上限(元)")
    transportation: str = Field(..., description="交通方式")
    accommodation: str = Field(..., description="住宿类型")
    weather_source: Literal["auto", "amap", "hko", "open_meteo"] = "auto"

    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("目的地城市不能为空")
        return value

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("日期必须使用 YYYY-MM-DD 格式")
        date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def validate_date_range(self):
        if (date.fromisoformat(self.end_date) - date.fromisoformat(self.start_date)).days + 1 != self.days:
            raise ValueError("日期范围必须与旅行天数一致，且结束日期不能早于开始日期")
        return self


class Location(BaseModel):
    """位置信息（经纬度坐标）。"""

    longitude: float = Field(..., description="经度", ge=-180, le=180)
    latitude: float = Field(..., description="纬度", ge=-90, le=90)


class Attraction(BaseModel):
    """景点信息。"""

    name: str = Field(..., description="景点名称")
    address: str = Field(..., description="地址")
    location: Location = Field(..., description="经纬度坐标")
    visit_duration: int = Field(..., description="建议游览时间(分钟)", gt=0)
    description: str = Field(..., description="景点描述")
    category: Optional[str] = Field(default="景点", description="景点类别")
    rating: Optional[float] = Field(default=None, ge=0, le=5, description="评分")
    image_url: Optional[str] = Field(default=None, description="图片URL")
    image_photographer: Optional[str] = Field(default=None, description="摄影师署名")
    image_photographer_url: Optional[str] = Field(default=None, description="摄影师页面")
    image_source_url: Optional[str] = Field(default=None, description="图片来源页面")
    ticket_price: int = Field(default=0, ge=0, description="门票价格(元)")


class Meal(BaseModel):
    """餐饮信息。"""

    type: str = Field(..., description="餐饮类型：breakfast/lunch/dinner/snack")
    name: str = Field(..., description="餐饮名称")
    address: Optional[str] = Field(default=None, description="地址")
    location: Optional[Location] = Field(default=None, description="经纬度坐标")
    description: Optional[str] = Field(default=None, description="描述")
    estimated_cost: int = Field(default=0, description="预估费用(元)")


class Hotel(BaseModel):
    """酒店信息。"""

    name: str = Field(..., description="酒店名称")
    address: str = Field(default="", description="酒店地址")
    location: Optional[Location] = Field(default=None, description="酒店位置")
    price_range: str = Field(default="", description="价格范围")
    rating: str = Field(default="", description="评分")
    distance: str = Field(default="", description="距离景点距离")
    type: str = Field(default="", description="酒店类型")
    estimated_cost: int = Field(default=0, description="预估费用(元/晚)")


class Budget(BaseModel):
    """预算信息。"""

    total_attractions: int = Field(default=0, description="景点门票总费用")
    total_hotels: int = Field(default=0, description="酒店总费用")
    total_meals: int = Field(default=0, description="餐饮总费用")
    total_transportation: int = Field(default=0, description="交通总费用")
    total: int = Field(default=0, description="总费用")


class DayPlan(BaseModel):
    """单日行程。"""

    date: str = Field(..., description="日期")
    day_index: int = Field(..., description="第几天(从0开始)")
    description: str = Field(..., description="当日行程描述")
    transportation: str = Field(..., description="交通方式")
    accommodation: str = Field(..., description="住宿安排")
    hotel: Optional[Hotel] = Field(default=None, description="酒店信息")
    attractions: List[Attraction] = Field(default_factory=list, description="景点列表")
    meals: List[Meal] = Field(default_factory=list, description="餐饮安排")


class WeatherInfo(BaseModel):
    """天气信息。"""

    date: str = Field(..., description="日期")
    day_weather: str = Field(..., description="白天天气")
    night_weather: str = Field(..., description="夜间天气")
    day_temp: int = Field(..., description="白天温度(摄氏度)")
    night_temp: int = Field(..., description="夜间温度(摄氏度)")
    wind_direction: str = Field(..., description="风向")
    wind_power: str = Field(..., description="风力")
    source: str = ""
    source_url: str = ""
    temperature_basis: Literal["day_night", "daily_range"] = "day_night"


    @field_validator("day_temp", "night_temp", mode="before")
    @classmethod
    def parse_temperature(cls, v):
        """解析温度字符串：\"16°C\" -> 16。"""
        if isinstance(v, str):
            v = v.replace("°C", "").replace("℃", "").replace("°", "").strip()
            try:
                return int(v)
            except ValueError:
                return 0
        return v


class TripPlan(BaseModel):
    """旅行计划。"""

    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    days: List[DayPlan] = Field(default_factory=list, description="每日行程")
    weather_info: List[WeatherInfo] = Field(default_factory=list, description="天气信息")
    weather_notes: List[str] = Field(default_factory=list, description="天气来源切换及缺失日期说明")
    overall_suggestions: str = Field(..., description="总体建议")
    budget: Optional[Budget] = Field(default=None, description="预算信息")
