"""真实高德静态地图与参数校验，不输出 Key 或完整供应商 URL。"""

import requests


def test_real_static_map():
    url = "http://127.0.0.1:8001/api/map/static"
    response = requests.get(url, params={"locations": "116.397,39.9163;116.4106,39.8822"}, timeout=25)
    assert response.status_code == 200
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    for locations in ("invalid", "181,90", "116,91", ""):
        invalid = requests.get(url, params={"locations": locations}, timeout=10)
        assert invalid.status_code == 422
    print("PASS: real static map PNG and 4 invalid-coordinate HTTP cases")


if __name__ == "__main__":
    test_real_static_map()
