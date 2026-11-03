"""真实 Unsplash 搜索与图片补全验证。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos" / "backend"))

from app.config import get_settings
from app.models.schemas import Attraction, DayPlan, Location, TripPlan
from app.services.unsplash_service import UnsplashService


def test_real_unsplash():
    key = get_settings().unsplash_access_key
    assert key, "真实 API 测试未完成：根目录 .env 缺少 UNSPLASH_ACCESS_KEY"
    service = UnsplashService(key)
    photos = service.search_photos("Forbidden City Beijing", per_page=1)
    assert photos and photos[0]["url"].startswith("https://images.unsplash.com/"), "真实 API 搜图未返回图片"
    assert photos[0]["photographer"]
    attraction = Attraction(name="Forbidden City", address="北京", location=Location(
        longitude=116.397, latitude=39.917), visit_duration=120, description="故宫")
    plan = TripPlan(city="Beijing", start_date="2026-11-03", end_date="2026-11-03",
                    overall_suggestions="提前预约", days=[DayPlan(
                        date="2026-11-03", day_index=0, description="文化游",
                        transportation="步行", accommodation="酒店", attractions=[attraction])])
    service.enrich_trip_plan(plan)
    assert plan.days[0].attractions[0].image_url
    assert plan.days[0].attractions[0].image_photographer
    assert plan.days[0].attractions[0].image_source_url
    existing = plan.days[0].attractions[0].image_url
    service.enrich_trip_plan(plan)
    assert plan.days[0].attractions[0].image_url == existing
    print("PASS: real Unsplash search, attribution metadata, trip image enrichment")


if __name__ == "__main__":
    test_real_unsplash()
