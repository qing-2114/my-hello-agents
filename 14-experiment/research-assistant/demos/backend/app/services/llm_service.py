"""统一读取项目根目录配置，不依赖官方项目。"""
from pathlib import Path
from dotenv import dotenv_values
from hello_agents import HelloAgentsLLM


def create_llm() -> HelloAgentsLLM:
    root = Path(__file__).resolve().parents[6]
    config = dotenv_values(root / '.env')
    names = ('LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL_ID')
    missing = [name for name in names if not config.get(name)]
    if missing:
        raise ValueError('根目录 .env 缺少配置：' + '、'.join(missing))
    return HelloAgentsLLM(
        provider='custom', api_key=config[names[0]], base_url=config[names[1]],
        model=config[names[2]], temperature=0.2, timeout=60,
    )
