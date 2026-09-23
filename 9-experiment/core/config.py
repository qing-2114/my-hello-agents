"""从项目根目录加载第九章所需的统一环境配置。"""

import os
from pathlib import Path

from dotenv import load_dotenv


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
KNOWLEDGE_BASE_DIR = EXPERIMENT_DIR / "knowledge_base"
MEMORY_DATA_DIR = EXPERIMENT_DIR / "memory_data"
NOTES_DIR = EXPERIMENT_DIR / "notes"
REPORTS_DIR = EXPERIMENT_DIR / "reports"

REQUIRED_ENV_VARS = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL_ID",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "NEO4J_URI",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
    "EMBED_API_KEY",
)


def load_project_environment() -> None:
    """加载根目录 .env，并确认记忆/RAG 所需变量齐全。"""
    if not ENV_FILE.is_file():
        raise FileNotFoundError(f"未找到项目环境配置文件：{ENV_FILE}")

    load_dotenv(ENV_FILE)
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"请在 {ENV_FILE} 中配置以下变量：{', '.join(missing)}"
        )

    KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_DATA_DIR.mkdir(parents=True, exist_ok=True)
