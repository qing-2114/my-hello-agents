"""主模型503故障注入后，实际调用根目录配置的备用 API。"""

import sys
from pathlib import Path

import httpx
from openai import OpenAI, APIStatusError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos" / "backend"))

from app.services.llm_service import FallbackLLM, create_llm, is_transient_error


def test_real_fallback_llm():
    llm = create_llm()
    assert isinstance(llm, FallbackLLM), "备用配置未生效"
    # 只替换主模型的 HTTP 传输，备用请求仍为真实网络调用。
    transport = httpx.MockTransport(lambda request: httpx.Response(
        503, json={"error": {"message": "temporary unavailable", "type": "service_unavailable"}}
    ))
    old_client = llm.primary._client
    client = OpenAI(api_key="test-only", base_url="https://primary.invalid/v1",
                    http_client=httpx.Client(transport=transport), max_retries=0)
    llm.primary._client = client
    real_fallback_invoke = llm.fallback.invoke
    attempts = []

    def fallback_with_transient_failure(messages, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise APIStatusError("test transient failure", response=httpx.Response(
                503, request=httpx.Request("POST", "https://test.invalid")), body={})
        return real_fallback_invoke(messages, **kwargs)

    llm.fallback.invoke = fallback_with_transient_failure
    try:
        answer = llm.invoke([{"role": "user", "content": "请只回复：备用模型连接成功"}], max_tokens=128)
        assert llm.using_fallback
        assert len(attempts) == 2
        assert isinstance(answer, str) and answer.strip()
        assert llm.model == llm.fallback.model
        assert not is_transient_error(ValueError("invalid configuration"))
    finally:
        client.close()
        old_client.close()
        llm.fallback._client.close()
        if llm.tertiary is not None:
            llm.tertiary._client.close()
    print("PASS: injected primary/fallback 503 -> one retry -> real fallback API response")


if __name__ == "__main__":
    try:
        test_real_fallback_llm()
    except Exception:
        # 避免底层响应或配置异常进入公开输出。
        print("FAIL: 真实备用 API 测试未完成，请检查服务状态、额度和模型配置")
        raise SystemExit(1)
