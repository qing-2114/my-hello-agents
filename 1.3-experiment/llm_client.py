"""OpenAI-compatible client configuration for the DeepSeek API."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv(Path(__file__).resolve().parent / ".env")


class OpenAICompatibleClient:
    """Call any OpenAI-compatible chat-completions service."""

    def __init__(self, model: str, api_key: str, base_url: str):
        if not api_key:
            raise ValueError("未配置 LLM API Key。请检查 1.3-experiment/.env。")
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, prompt: str, system_prompt: str) -> str:
        """Generate one assistant response."""
        print("正在调用大语言模型...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
            )
            answer = response.choices[0].message.content
            print("大语言模型响应成功。")
            return answer or "错误:模型返回了空响应。"
        except Exception as exc:
            print(f"调用LLM API时发生错误: {exc}")
            return "错误:调用语言模型服务时出错。"


def create_deepseek_client() -> OpenAICompatibleClient:
    """Create a client from the local .env configuration."""
    return OpenAICompatibleClient(
        model=os.getenv("DEEPSEEK_MODEL", "flash"),
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )


__all__ = ["OpenAICompatibleClient", "create_deepseek_client"]
