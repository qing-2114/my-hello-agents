"""通过真实 HTTP 测试两日行程与图片补全。"""

from datetime import date, timedelta

import requests


def test_real_http_trip():
    today = date.today()
    response = requests.post("http://127.0.0.1:8001/api/trip/plan", json={
        "city": "北京", "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=1)).isoformat(), "days": 2,
        "preferences": ["历史文化"], "budget": 2000,
        "transportation": "公共交通", "accommodation": "经济型酒店",
    }, timeout=300)
    assert response.status_code == 200, f"真实两日行程 HTTP {response.status_code}"
    plan = response.json()
    assert plan["city"] == "北京" and len(plan["days"]) == 2
    for i, day in enumerate(plan["days"]):
        assert day["day_index"] == i
        assert day["date"] == (today + timedelta(days=i)).isoformat()
        assert 2 <= len(day["attractions"]) <= 3
        assert {"breakfast", "lunch", "dinner"} <= {m["type"] for m in day["meals"]}
    b = plan["budget"]
    assert b["total"] == sum(b[k] for k in (
        "total_attractions", "total_hotels", "total_meals", "total_transportation"))
    images = [a for day in plan["days"] for a in day["attractions"] if a.get("image_url")]
    assert images, "真实搜图未补全任何景点图片"
    assert all(a.get("image_photographer") and a.get("image_source_url") for a in images)
    print(f"PASS: real HTTP two-day trip, dates, meals, budget, {len(images)} credited images")


if __name__ == "__main__":
    test_real_http_trip()
