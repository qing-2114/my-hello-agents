"""搜索配置；凭证仍由服务从项目根目录 .env 读取。"""
from enum import Enum
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[5]


class SearchAPI(str, Enum):
    TAVILY = 'tavily'
    DUCKDUCKGO = 'duckduckgo'
    PERPLEXITY = 'perplexity'
    SEARXNG = 'searxng'
    ADVANCED = 'advanced'


class Configuration(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    search_api: SearchAPI = SearchAPI.DUCKDUCKGO
    max_search_results: int = Field(default=5, ge=1, le=10)
    max_tokens_per_source: int = Field(default=2000, ge=1)
    searxng_url: str = 'http://localhost:8888'
    notes_workspace: str = str(ROOT / '14-experiment' / '.local' / 'research-assistant' / 'notes')
    search_cache_dir: str = str(ROOT / '14-experiment' / '.local' / 'research-assistant' / 'cache' / 'search')
    search_cache_ttl_seconds: int = Field(default=86400, ge=0)

    @classmethod
    def from_env(cls):
        values = dotenv_values(ROOT / '.env')
        mapping = {
            'SEARCH_API': 'search_api',
            'MAX_SEARCH_RESULTS': 'max_search_results',
            'MAX_TOKENS_PER_SOURCE': 'max_tokens_per_source',
            'SEARXNG_URL': 'searxng_url',
            'NOTES_WORKSPACE': 'notes_workspace',
            'SEARCH_CACHE_DIR': 'search_cache_dir',
            'SEARCH_CACHE_TTL_SECONDS': 'search_cache_ttl_seconds',
        }
        return cls(**{field: values[key] for key, field in mapping.items() if values.get(key)})
