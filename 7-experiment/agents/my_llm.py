"""第七章实验：通过继承 HelloAgentsLLM 扩展 ModelScope 支持。

不修改 hello-agents 库源码，仅通过子类重写 __init__ 拦截
provider="modelscope" 的分支，其余情况完全复用父类逻辑。
"""

from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI
from hello_agents import HelloAgentsLLM

MODELSCOPE_DEFAULT_BASE_URL = "https://api-inference.modelscope.cn/v1/"
MODELSCOPE_DEFAULT_MODEL = "Qwen/Qwen2.5-VL-72B-Instruct"


class MyLLM(HelloAgentsLLM):
    """自定义 LLM 客户端，通过继承为框架增加 ModelScope 平台支持。"""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs,
    ) -> None:
        if provider == "modelscope":
            print("正在使用自定义的 ModelScope Provider")
            self.provider = "modelscope"

            # 解析 ModelScope 凭证：显式参数优先，其次环境变量
            # 与 hello-agents 原生 provider 保持一致：专用密钥优先，
            # 未设置时回退到项目统一的 LLM_API_KEY。
            self.api_key = (
                api_key
                or os.getenv("MODELSCOPE_API_KEY")
                or os.getenv("LLM_API_KEY")
            )
            self.base_url = base_url or MODELSCOPE_DEFAULT_BASE_URL

            if not self.api_key:
                raise ValueError(
                    "ModelScope API key not found. "
                    "Please set MODELSCOPE_API_KEY or LLM_API_KEY environment variable."
                )

            # ModelScope 使用独立的模型配置，避免误用其他 provider 的模型 ID。
            # 优先级为：显式参数 > MODELSCOPE_MODEL_ID > ModelScope 默认值。
            self.model = (
                model
                or os.getenv("MODELSCOPE_MODEL_ID")
                or MODELSCOPE_DEFAULT_MODEL
            )
            self.temperature = kwargs.get("temperature", 0.7)
            self.max_tokens = kwargs.get("max_tokens")
            self.timeout = kwargs.get("timeout", 60)
            self.kwargs = kwargs

            # ModelScope 提供 OpenAI 兼容接口，直接创建 OpenAI 客户端
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        else:
            # 非 modelscope：完全交由父类处理（OpenAI/DeepSeek/Qwen 等内置供应商）
            super().__init__(
                model=model,
                api_key=api_key,
                base_url=base_url,
                provider=provider,
                **kwargs,
            )
