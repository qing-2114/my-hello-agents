"""导出用高德静态地图代理，服务端持有 Web 服务 Key。"""

import requests
from fastapi import APIRouter, HTTPException, Query, Response

from ...config import get_settings
from ...models.schemas import Location

router = APIRouter(prefix="/map", tags=["地图"])


@router.get("/static")
def static_map(locations: str = Query(..., max_length=5000)):
    try:
        if any(len(pair.split(",")) != 2 for pair in locations.split(";")):
            raise ValueError("每个点应包含两个坐标")
        points = [Location(longitude=float(pair.split(",")[0]), latitude=float(pair.split(",")[1]))
                  for pair in locations.split(";")]
        if not 1 <= len(points) <= 30:
            raise ValueError("点位数量超限")
    except (ValueError, IndexError):
        raise HTTPException(422, "景点坐标格式或数量不正确") from None
    markers = "|".join(f"mid,0x176B5B,{i % 10}:{p.longitude},{p.latitude}"
                       for i, p in enumerate(points, 1))
    try:
        response = requests.get("https://restapi.amap.com/v3/staticmap", params={
            "key": get_settings().amap_api_key, "size": "1000*500", "scale": "2", "markers": markers,
        }, timeout=15)
        response.raise_for_status()
        if not response.headers.get("Content-Type", "").startswith("image/"):
            raise ValueError("静态地图未返回图片")
        return Response(content=response.content, media_type=response.headers["Content-Type"],
                        headers={"Cache-Control": "private, max-age=300"})
    except (requests.RequestException, ValueError):
        raise HTTPException(502, "静态地图暂不可用") from None
