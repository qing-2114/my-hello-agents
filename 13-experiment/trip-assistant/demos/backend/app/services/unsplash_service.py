"""Unsplash 搜图与行程图片补全服务。"""

import logging
from typing import Dict, List, Optional

import requests

from ..models.schemas import TripPlan

logger = logging.getLogger(__name__)


class UnsplashService:
    """搜图失败返回空结果，不阻断旅行规划。"""

    def __init__(self, access_key: str):
        self.access_key = access_key
        self.base_url = "https://api.unsplash.com"

    def search_photos(self, query: str, per_page: int = 10) -> List[Dict]:
        if not 1 <= per_page <= 30:
            raise ValueError("per_page 必须在1到30之间")
        if not self.access_key or not query.strip():
            return []
        try:
            response = requests.get(
                f"{self.base_url}/search/photos",
                params={"query": query, "per_page": per_page},
                headers={"Authorization": f"Client-ID {self.access_key}",
                         "Accept-Version": "v1"},
                timeout=10,
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            photos = []
            for result in results:
                url = (result.get("urls") or {}).get("regular")
                if not url:
                    continue
                user = result.get("user") or {}
                photos.append({
                    "url": url,
                    "description": result.get("description") or result.get("alt_description") or "",
                    "photographer": user.get("name", ""),
                    "photographer_url": (user.get("links") or {}).get("html", ""),
                    "photo_url": (result.get("links") or {}).get("html", ""),
                })
            return photos
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            # 不记录请求头、完整异常或响应内容，避免密钥和请求信息进入日志。
            logger.warning("Unsplash 搜图失败，本次跳过图片补全")
            return []

    def get_photo_url(self, query: str) -> Optional[str]:
        photos = self.search_photos(query, per_page=1)
        return photos[0]["url"] if photos else None

    def enrich_trip_plan(self, trip_plan: TripPlan) -> TripPlan:
        """仅补全缺失图片，同一行程内相同查询只请求一次。"""
        cache: Dict[str, Optional[Dict]] = {}
        for day in trip_plan.days:
            for attraction in day.attractions:
                if attraction.image_url:
                    continue
                query = f"{attraction.name} {trip_plan.city}"
                if query not in cache:
                    photos = self.search_photos(query, per_page=1)
                    cache[query] = photos[0] if photos else None
                photo = cache[query]
                if photo:
                    attraction.image_url = photo["url"]
                    attraction.image_photographer = photo["photographer"]
                    attraction.image_photographer_url = photo["photographer_url"]
                    attraction.image_source_url = photo["photo_url"]
        return trip_plan
