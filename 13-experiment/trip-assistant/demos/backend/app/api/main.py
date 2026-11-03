"""自主实现的 FastAPI 入口。"""

from fastapi import FastAPI

from .routes.trip import router
from .routes.map import router as map_router
from .routes.weather import router as weather_router

app = FastAPI(title="智能旅行助手")
app.include_router(router, prefix="/api")
app.include_router(map_router, prefix="/api")

app.include_router(weather_router, prefix="/api")
