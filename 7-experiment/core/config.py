"""配置管理。"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Config(BaseModel):
    """HelloAgents 配置类。"""

    # LLM 配置
    default_model: str = "deepseek-v4-flash"
    default_provider: str = "deepseek"
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    # 系统配置
    debug: bool = False
    log_level: str = "INFO"

    # 其他配置
    max_history_length: int = 100

    @classmethod
    def from_env(cls) -> "Config":
        """加载项目根目录 .env，并从环境变量创建配置。"""
        load_dotenv(ENV_FILE)
        max_tokens = os.getenv("MAX_TOKENS")
        return cls(
            default_model=os.getenv("LLM_MODEL_ID", "deepseek-v4-flash"),
            default_provider=os.getenv("LLM_PROVIDER", "deepseek"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_tokens=int(max_tokens) if max_tokens else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return self.model_dump()
