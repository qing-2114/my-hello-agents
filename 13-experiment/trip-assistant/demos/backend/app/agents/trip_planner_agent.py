"""景点、天气、酒店专家依次查询，规划专家汇总输出。"""

import json
from datetime import date, timedelta

from hello_agents import SimpleAgent

from ..models.schemas import Location, TripPlan, TripPlanRequest
from ..services.runtime import create_runtime
from ..services.weather_service import WeatherService
from ..services.amap_service import search_verified_places
from .prompts import (
    ATTRACTION_AGENT_PROMPT,
    HOTEL_AGENT_PROMPT,
    PLANNER_AGENT_PROMPT,
    WEATHER_AGENT_PROMPT,
)


class TripPlannerAgent:
    """顺序编排四个 SimpleAgent；同一实例不应并发处理多个请求。"""

    def __init__(self):
        # 每个规划器只创建一份 LLM 和 MCP 工具，供所有专家共享。
        self.llm, self.mcp_tool = create_runtime()
        self.attraction_agent = SimpleAgent(
            name="AttractionSearchAgent", llm=self.llm, system_prompt=ATTRACTION_AGENT_PROMPT
        )
        self.weather_agent = SimpleAgent(
            name="WeatherQueryAgent", llm=self.llm, system_prompt=WEATHER_AGENT_PROMPT
        )
        self.hotel_agent = SimpleAgent(
            name="HotelAgent", llm=self.llm, system_prompt=HOTEL_AGENT_PROMPT
        )
        self.planner_agent = SimpleAgent(
            name="PlannerAgent", llm=self.llm, system_prompt=PLANNER_AGENT_PROMPT
        )
        for agent in (self.attraction_agent, self.weather_agent, self.hotel_agent):
            agent.add_tool(self.mcp_tool)

    def plan_trip(self, request: TripPlanRequest) -> TripPlan:
        start = date.fromisoformat(request.start_date)
        end = date.fromisoformat(request.end_date)
        if (end - start).days + 1 != request.days:
            raise ValueError("起止日期必须与旅行天数一致（包含首尾日期）")
        for agent in (self.attraction_agent, self.weather_agent,
                      self.hotel_agent, self.planner_agent):
            agent.clear_history()
        verified_attractions = search_verified_places(request.city, "景点")
        verified_hotels = search_verified_places(request.city, "酒店")
        attraction_response = self.attraction_agent.run(
            f"请使用工具搜索{request.city}的景点，偏好：{request.preferences}。"
            f"为{request.days}天准备足够的候选景点。"
        )
        weather_service = WeatherService()
        try:
            weather = weather_service.forecast(request.city, start, end, request.weather_source,
                                              Location(**verified_attractions[0]["location"]))
        finally:
            weather_service.close()
        weather_evidence = json.dumps({
            "weather_info": [w.model_dump() for w in weather.weather_info], "notes": weather.notes
        }, ensure_ascii=False)
        weather_response = self.weather_agent.run(
            "已由后端多源天气服务取得以下原始预报。请据此提供出行建议，不再调用高德天气工具；"
            "不得改变日期、温度或来源，不得推测缺失日期。\n" + weather_evidence
        )
        weather_response += "\n权威天气凭据（以此为准）：" + weather_evidence
        hotel_response = self.hotel_agent.run(
            f"请使用工具搜索{request.city}的{request.accommodation}酒店。"
        )
        # 独立取得原始地点凭据，避免仅依赖专家的自然语言总结。
        attraction_response += "\n可用景点原始凭据（只能选用以下名称）：" + json.dumps(verified_attractions, ensure_ascii=False)
        hotel_response += "\n可用酒店原始凭据（只能选用以下名称）：" + json.dumps(verified_hotels, ensure_ascii=False)
        query = self._build_planner_query(
            request, attraction_response, weather_response, hotel_response
        )
        for attempt in range(2):
            response = self.planner_agent.run(query)
            try:
                plan = self._parse_trip_plan(response, weather.weather_info)
                plan.weather_notes = weather.notes

                self._apply_verified_places(plan, verified_attractions, verified_hotels)
                self._validate_plan(plan, request, start)
                return plan
            except ValueError as exc:
                if attempt:
                    raise
                query = f"请修正上一份输出的问题：{exc}。重新输出完整 JSON。\n{query}"
        raise RuntimeError("规划未完成")

    @staticmethod
    def _apply_verified_places(plan, attractions, hotels):
        for day in plan.days:
            for item, candidates in [(a, attractions) for a in day.attractions] + (
                    [(day.hotel, hotels)] if day.hotel else []):
                match = next((p for p in candidates if p["name"] == item.name), None)
                if match is None:
                    raise ValueError("景点或酒店必须使用原始凭据中的完整名称")
                item.address = match["address"]
                item.location = Location(**match["location"])

    @staticmethod
    def _validate_plan(plan: TripPlan, request: TripPlanRequest, start: date):
        expected = [(start + timedelta(days=i)).isoformat() for i in range(request.days)]
        if (plan.city != request.city or plan.start_date != request.start_date
                or plan.end_date != request.end_date
                or [day.date for day in plan.days] != expected
                or [day.day_index for day in plan.days] != list(range(request.days))):
            raise ValueError("生成的目的地或行程日期与请求不一致")
        if plan.budget is None:
            raise ValueError("生成的行程缺少预算")
        for day in plan.days:
            if not 2 <= len(day.attractions) <= 3:
                raise ValueError("每天必须安排2-3个景点")
            if not {"breakfast", "lunch", "dinner"} <= {meal.type for meal in day.meals}:
                raise ValueError("每天必须包含早中晚三餐")
        budget = plan.budget
        costs = [budget.total_attractions, budget.total_hotels,
                 budget.total_meals, budget.total_transportation]
        if min(costs) < 0 or budget.total != sum(costs):
            raise ValueError("预算必须非负且总额等于各分类费用之和")

    def _build_planner_query(self, request: TripPlanRequest,
                             attraction_response: str, weather_response: str,
                             hotel_response: str) -> str:
        return f"""请生成{request.city}的{request.days}日旅行计划。
用户需求：
{request.model_dump_json()}
景点信息：
{attraction_response}
天气信息：
{weather_response}
酒店信息：
{hotel_response}
以下是必须遵循的完整输出 JSON Schema：
{json.dumps(TripPlan.model_json_schema(), ensure_ascii=False)}
请返回详细行程、三餐、住宿、天气、建议和预算。"""

    @staticmethod
    def _parse_trip_plan(response: str, weather_info=None) -> TripPlan:
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[-1].strip() != "```":
                raise ValueError("行程 JSON 代码块未闭合")
            text = "\n".join(lines[1:-1])
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("行程必须为 JSON 对象")
        if weather_info is not None:
            payload["weather_info"] = [w.model_dump() for w in weather_info]
            payload["weather_notes"] = []  # 缺失及切换说明由后端确定。
        return TripPlan.model_validate(payload)
