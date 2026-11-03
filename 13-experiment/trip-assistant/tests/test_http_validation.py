"""对正在运行的后端测试无效输入，确认在调用 Agent 前返回422。"""

import requests


def test_http_validation():
    valid = dict(city="北京", start_date="2026-11-03", end_date="2026-11-03",
                 days=1, preferences=["历史文化"], budget=1000,
                 transportation="公共交通", accommodation="经济型酒店")
    for changes in (
        {"budget": -1}, {"days": 0}, {"days": 31}, {"city": "   "},
        {"start_date": "not-a-date"}, {"start_date": "2026-02-30"},
        {"days": 2}, {"end_date": "2026-11-02"}, {"preferences": "历史文化"},
    ):
        response = requests.post("http://127.0.0.1:8001/api/trip/plan",
                                 json={**valid, **changes}, timeout=15)
        assert response.status_code == 422, f"字段 {list(changes)} 未返回422"
    print("PASS: 9 real HTTP input validation cases -> 422")


if __name__ == "__main__":
    test_http_validation()
