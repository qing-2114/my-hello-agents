"""前两个模型503故障注入后，真实调用新增的第二备用模型。"""

import sys
from pathlib import Path

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos" / "backend"))

from app.services.llm_service import FallbackLLM, create_llm


def test_real_second_fallback_llm():
    llm = create_llm()
    assert isinstance(llm, FallbackLLM) and llm.tertiary is not None
    expected_model = llm.tertiary.model
    clients = [llm.primary._client, llm.fallback._client, llm.tertiary._client]
    calls = []

    def unavailable(request):
        calls.append(request.url.host)
        return httpx.Response(503, json={"error": {"message": "temporary unavailable"}})

    for model in (llm.primary, llm.fallback):
        client = OpenAI(api_key="test-only", base_url="https://test.invalid/v1",
                        http_client=httpx.Client(transport=httpx.MockTransport(unavailable)),
                        max_retries=0)
        clients.append(client)
        model._client = client
    try:
        answer = llm.invoke([{"role": "user", "content": "请只回复：连接成功"}], max_tokens=128)
        assert isinstance(answer, str) and answer.strip()
        assert llm.using_tertiary and llm.model == expected_model
        assert len(calls) == 3  # 主模型一次、第一备用模型两次。
    finally:
        for client in clients:
            client.close()
    print("PASS: primary 503 -> fallback 503 with retry -> real configured second fallback response")


if __name__ == "__main__":
    try:
        test_real_second_fallback_llm()
    except Exception as error:
        print("FAIL: 新模型真实 API 测试未完成；错误类型：" + type(error).__name__)
        raise SystemExit(1)
