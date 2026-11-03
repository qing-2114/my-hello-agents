"""非流式调用的模型故障切换，供旅行助手四个 Agent 共用。"""

import logging
import time

from hello_agents import HelloAgentsLLM
from openai import APIConnectionError, APIStatusError

from ..config import get_settings

logger = logging.getLogger(__name__)


class ModelServiceError(RuntimeError):
    """可安全展示给前端的模型服务错误。"""


def is_transient_error(error: Exception) -> bool:
    """HelloAgents 包装异常后，沿异常链读取底层 SDK 状态。"""
    seen = set()
    current = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, APIConnectionError):
            return True
        if isinstance(current, APIStatusError):
            return current.status_code in (408, 429) or current.status_code >= 500
        current = current.__cause__ or current.__context__
    return False


class FallbackLLM(HelloAgentsLLM):
    """按主模型、第一备用、第二备用顺序切换，当前实例保留切换状态。"""

    def __init__(self, primary: HelloAgentsLLM, fallback: HelloAgentsLLM,
                 tertiary: HelloAgentsLLM | None = None):
        # 委托已配置的客户端，不额外初始化模型连接。
        self.primary = primary
        self.fallback = fallback
        self.using_fallback = False
        self.tertiary = tertiary
        self.using_tertiary = False

    @property
    def model(self):
        return self.active_llm.model

    @property
    def provider(self):
        return self.active_llm.provider

    @property
    def active_llm(self):
        if self.using_tertiary:
            return self.tertiary
        return self.fallback if self.using_fallback else self.primary

    def _invoke_tertiary(self, messages, **kwargs) -> str:
        for attempt in range(2):
            try:
                return self.tertiary.invoke(messages, **kwargs)
            except Exception as error:
                if is_transient_error(error) and attempt == 0:
                    logger.warning("第二备用模型暂时不可用，重试一次")
                    time.sleep(1)
                    continue
                raise ModelServiceError("第二备用模型调用失败，请稍后重试或检查服务状态") from None

    def invoke(self, messages, **kwargs) -> str:
        if self.using_tertiary:
            return self._invoke_tertiary(messages, **kwargs)
        if not self.using_fallback:
            try:
                return self.primary.invoke(messages, **kwargs)
            except Exception as error:
                if not is_transient_error(error):
                    raise ModelServiceError("主模型调用失败，请检查模型配置与服务状态") from None
                self.using_fallback = True
                logger.warning("主模型暂时不可用，当前旅行规划切换至备用模型")
        for attempt in range(2):
            try:
                return self.fallback.invoke(messages, **kwargs)
            except Exception as error:
                transient = is_transient_error(error)
                if transient and attempt == 0:
                    logger.warning("备用模型暂时不可用，重试一次")
                    time.sleep(1)
                    continue
                if transient and self.tertiary is not None:
                    self.using_tertiary = True
                    logger.warning("第一备用模型暂时不可用，切换至第二备用模型")
                    return self._invoke_tertiary(messages, **kwargs)
                reason = "主模型与备用模型暂时不可用，请稍后重试" if transient else "备用模型调用失败，请检查模型服务或额度"
                raise ModelServiceError(reason) from None

    def stream_invoke(self, messages, **kwargs):
        raise NotImplementedError("旅行助手当前使用 invoke；暂不支持流式故障切换")


def create_llm() -> HelloAgentsLLM:
    settings = get_settings()
    primary_values = (settings.llm_api_key, settings.llm_base_url, settings.llm_model_id)
    if not all(primary_values):
        raise ValueError("根目录 .env 的 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_ID 必须完整")
    primary = HelloAgentsLLM(api_key=primary_values[0], base_url=primary_values[1],
                             model=primary_values[2], timeout=30)
    fallback_values = (settings.llm_fallback_api_key, settings.llm_fallback_base_url,
                       settings.llm_fallback_model_id)
    if not any(fallback_values):
        if any((settings.llm_fallback_2_api_key, settings.llm_fallback_2_base_url,
                settings.llm_fallback_2_model_id)):
            raise ValueError("请先配置第一备用模型，再配置第二备用模型")
        return primary
    if not all(fallback_values):
        raise ValueError("备用模型配置 LLM_FALLBACK_API_KEY/BASE_URL/MODEL_ID 必须完整")
    # 主模型单次失败即切换，避免 SDK 自动重试增加整份行程的等待时间。
    primary._client = primary._client.with_options(max_retries=0)
    fallback = HelloAgentsLLM(api_key=fallback_values[0], base_url=fallback_values[1],
                              model=fallback_values[2], timeout=60)
    fallback._client = fallback._client.with_options(max_retries=0)
    tertiary_values = (settings.llm_fallback_2_api_key, settings.llm_fallback_2_base_url,
                       settings.llm_fallback_2_model_id)
    tertiary = None
    if any(tertiary_values):
        if not all(tertiary_values):
            raise ValueError("第二备用模型配置 LLM_FALLBACK_2_API_KEY/BASE_URL/MODEL_ID 必须完整")
        tertiary = HelloAgentsLLM(api_key=tertiary_values[0], base_url=tertiary_values[1],
                                  model=tertiary_values[2], timeout=60)
        tertiary._client = tertiary._client.with_options(max_retries=0)
    return FallbackLLM(primary, fallback, tertiary)
