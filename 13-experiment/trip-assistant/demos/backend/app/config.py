"""自主实现的配置入口，仅从项目根目录 .env 读取。"""

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class Settings:
    llm_api_key: str = field(repr=False)
    llm_base_url: str
    llm_model_id: str
    amap_api_key: str = field(repr=False)
    unsplash_access_key: str = field(default="", repr=False)
    llm_fallback_api_key: str = field(default="", repr=False)
    llm_fallback_base_url: str = ""
    llm_fallback_model_id: str = ""
    llm_fallback_2_api_key: str = field(default="", repr=False)
    llm_fallback_2_base_url: str = ""
    llm_fallback_2_model_id: str = ""


def get_settings() -> Settings:
    config = dotenv_values(Path(__file__).resolve().parents[5] / ".env")
    return Settings(
        llm_api_key=config.get("LLM_API_KEY") or "",
        llm_base_url=config.get("LLM_BASE_URL") or "",
        llm_model_id=config.get("LLM_MODEL_ID") or "",
        amap_api_key=config.get("AMAP_API_KEY") or config.get("AMAP_MAPS_API_KEY") or "",
        unsplash_access_key=config.get("UNSPLASH_ACCESS_KEY") or "",
        llm_fallback_api_key=config.get("LLM_FALLBACK_API_KEY") or "",
        llm_fallback_base_url=config.get("LLM_FALLBACK_BASE_URL") or "",
        llm_fallback_model_id=config.get("LLM_FALLBACK_MODEL_ID") or "",
        llm_fallback_2_api_key=config.get("LLM_FALLBACK_2_API_KEY") or "",
        llm_fallback_2_base_url=config.get("LLM_FALLBACK_2_BASE_URL") or "",
        llm_fallback_2_model_id=config.get("LLM_FALLBACK_2_MODEL_ID") or "",
    )
