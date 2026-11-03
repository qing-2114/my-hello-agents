"""旅行规划与景点图片补全接口。"""

from fastapi import APIRouter, HTTPException
from ...services.llm_service import ModelServiceError
from ...services.amap_service import MapDataError

from ...agents.trip_planner_agent import TripPlannerAgent
from ...config import get_settings
from ...models.schemas import TripPlan, TripPlanRequest
from ...services.unsplash_service import UnsplashService

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post("/plan", response_model=TripPlan)
def create_trip_plan(request: TripPlanRequest) -> TripPlan:
    # 每次请求单独创建规划器，避免并发请求共享 Agent 对话历史。
    # 同步路由由 FastAPI 在线程池中运行，避免同步网络调用阻塞事件循环。
    try:
        trip_plan = TripPlannerAgent().plan_trip(request)
    except (ModelServiceError, MapDataError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except ValueError:
        raise HTTPException(status_code=502, detail="模型生成的行程未通过格式或内容校验，请重试") from None
    service = UnsplashService(get_settings().unsplash_access_key)
    return service.enrich_trip_plan(trip_plan)
