"""第四章：基础的 OpenAI 兼容 LLM 客户端。

配置统一从项目根目录的 ``.env`` 读取通用的 ``LLM_*`` 变量。
项目来源：<https://hello-agents.datawhale.cc/>。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI


PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")


def _env(*names: str, default: Optional[str] = None) -> Optional[str]:
    """按顺序读取第一个已设置的环境变量。"""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


class HelloAgentsLLM:
    """调用任意兼容 OpenAI Chat Completions 接口的语言模型。"""

    def __init__(
        self,
        model: Optional[str] = None,
        apiKey: Optional[str] = None,
        baseUrl: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        """初始化客户端；显式参数优先于 ``.env`` 配置。"""
        self.model = model or _env("LLM_MODEL_ID")
        apiKey = apiKey or _env("LLM_API_KEY")
        baseUrl = baseUrl or _env("LLM_BASE_URL", default="https://api.deepseek.com")

        timeout_value = timeout
        if timeout_value is None:
            timeout_value = int(_env("LLM_TIMEOUT", default="60"))

        if not all([self.model, apiKey, baseUrl]):
            raise ValueError(
                "模型 ID、API 密钥和服务地址必须通过参数或 .env 文件提供。"
                "请在项目根目录配置 LLM_MODEL_ID/LLM_API_KEY/LLM_BASE_URL。"
            )

        self.client = OpenAI(api_key=apiKey, base_url=baseUrl, timeout=timeout_value)

    def think(
        self, messages: List[Dict[str, str]], temperature: float = 0
    ) -> Optional[str]:
        """以流式方式调用模型，打印并返回完整的响应文本。"""
        print(f"🧠 正在调用 {self.model} 模型...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )

            print("✅ 大语言模型响应成功:")
            collected_content: List[str] = []
            for chunk in response:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content or ""
                print(content, end="", flush=True)
                collected_content.append(content)
            print()
            return "".join(collected_content)
        except Exception as exc:
            print(f"❌ 调用 LLM API 时发生错误: {exc}")
            return None


if __name__ == "__main__":
    try:
        llm_client = HelloAgentsLLM()
        example_messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that writes Python code.",
            },
            {"role": "user", "content": "写一个快速排序算法"},
        ]
        print("--- 调用 LLM ---")
        response_text = llm_client.think(example_messages)
        if response_text:
            print("\n\n--- 完整模型响应 ---")
            print(response_text)
    except ValueError as exc:
        print(exc)


__all__ = ["HelloAgentsLLM"]
