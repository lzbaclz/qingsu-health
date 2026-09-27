"""模型适配层：不联网，用模拟传输层检查请求体与解析。"""
import json

import httpx
import httpx2
import pytest

from app.llm import provider as P
from app.protocol import get_protocol

PROTO = get_protocol("lbp_adult_v0.1")
GOOD = {"facts": [{"key": "leg_numbness", "status": "denied", "value": None, "quote": "腿不麻"}], "unmapped_mentions": []}


def test_anthropic_request_shape(monkeypatch):
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={
            "id": "msg_x", "type": "message", "role": "assistant", "model": "claude-opus-5",
            "content": [{"type": "text", "text": json.dumps(GOOD, ensure_ascii=False)}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 1200, "output_tokens": 80, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        })

    import anthropic
    monkeypatch.setattr(P.AnthropicProvider, "__init__", lambda self: None)
    prov = P.AnthropicProvider()
    prov._anthropic = anthropic
    prov.client = anthropic.Anthropic(api_key="test", http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
    prov.model = "claude-opus-5"
    prov.name = "anthropic:claude-opus-5"
    P.USAGE.reset()
    out = prov.extract("腰疼，腿不麻。", PROTO)
    assert out.facts[0].key == "leg_numbness" and out.facts[0].status == "denied"
    body = seen["body"]
    assert body["model"] == "claude-opus-5"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["headers"]["anthropic-beta"]
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "thinking" not in body            # Opus 5 默认自适应思考，不传
    assert P.USAGE.snapshot()["input_tokens"] == 1200


def test_anthropic_refusal_becomes_provider_error(monkeypatch):
    def handler(request):
        return httpx2.Response(200, json={
            "id": "msg_x", "type": "message", "role": "assistant", "model": "claude-opus-5", "content": [],
            "stop_reason": "refusal", "stop_sequence": None, "stop_details": {"type": "refusal", "category": None, "explanation": None},
            "usage": {"input_tokens": 0, "output_tokens": 0}})

    import anthropic
    monkeypatch.setattr(P.AnthropicProvider, "__init__", lambda self: None)
    prov = P.AnthropicProvider()
    prov._anthropic = anthropic
    prov.client = anthropic.Anthropic(api_key="test", http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
    prov.model, prov.name = "claude-opus-5", "anthropic:claude-opus-5"
    with pytest.raises(P.ProviderError):
        prov.extract("腰疼。", PROTO)


def test_compat_provider_json_and_retry(monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        content = "不是JSON" if len(calls) == 1 else "```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 900, "completion_tokens": 60}})

    monkeypatch.setattr(P.settings.__class__, "__setattr__", object.__setattr__)
    monkeypatch.setattr(P.settings, "compat_base_url", "https://example.invalid/v1")
    monkeypatch.setattr(P.settings, "compat_api_key", "k")
    monkeypatch.setattr(P.settings, "compat_model", "deepseek-chat")
    prov = P.CompatProvider(transport=httpx.MockTransport(handler))
    out = prov.extract("腰疼，腿不麻。", PROTO)
    assert out.facts[0].key == "leg_numbness"
    assert len(calls) == 2 and calls[0]["response_format"] == {"type": "json_object"}
    assert calls[1]["messages"][-1]["role"] == "user" and "Schema" in calls[1]["messages"][-1]["content"]


def test_ollama_provider_request_shape(monkeypatch):
    """本机模型：走 Ollama 原生接口，带上下文长度、关掉思考，并把 JSON Schema 交给服务端约束输出。"""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": json.dumps(GOOD, ensure_ascii=False)},
                                         "prompt_eval_count": 2900, "eval_count": 80, "done": True})

    monkeypatch.setattr(P.settings.__class__, "__setattr__", object.__setattr__)
    monkeypatch.setattr(P.settings, "ollama_model", "qwen3:4b")
    monkeypatch.setattr(P.settings, "ollama_think", "false")
    prov = P.OllamaProvider(transport=httpx.MockTransport(handler))
    assert prov.name == "ollama:qwen3:4b"
    out = prov.extract("腰疼，腿不麻。", PROTO)
    assert out.facts[0].key == "leg_numbness"
    url, body = calls[0]
    assert url.endswith("/api/chat") and body["stream"] is False and body["think"] is False
    assert body["options"]["num_ctx"] >= 8192 and body["options"]["temperature"] == 0
    assert body["format"]["title"] == "ExtractionOutput"
    # 本地模式下叙述用模板：不再调用模型（避免思考过程混进医生摘要）
    assert "患者" in prov.narrative(["腿或脚是否发麻：明确否认"], PROTO) and len(calls) == 1
    prov.extract_red_flags("腰疼，腿不麻。", PROTO)
    assert "只看需要尽快让医生知道的情况" in calls[1][1]["messages"][0]["content"]


def test_ollama_provider_needs_model_and_reports_connection(monkeypatch):
    monkeypatch.setattr(P.settings.__class__, "__setattr__", object.__setattr__)
    monkeypatch.setattr(P.settings, "ollama_model", "")
    with pytest.raises(P.ProviderError):
        P.OllamaProvider()
    monkeypatch.setattr(P.settings, "ollama_model", "gpt-oss:20b")
    monkeypatch.setattr(P.settings, "ollama_think", "low")

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    prov = P.OllamaProvider(transport=httpx.MockTransport(refuse))
    assert prov.think == "low"
    with pytest.raises(P.ProviderError, match="Ollama"):
        prov.extract("腰疼。", PROTO)


def test_resilient_provider_falls_back_to_mock():
    class Broken:
        name = "anthropic:x"

        def extract(self, text, protocol):
            raise P.ProviderError("down")

        def narrative(self, lines, protocol):
            raise P.ProviderError("down")

    r = P.ResilientProvider(Broken(), P.MockProvider())
    out = r.extract("腿不麻。", PROTO)
    assert r.last_used == "mock(fallback)" and any(f.key == "leg_numbness" for f in out.facts)
    assert "患者" in r.narrative(["腿或脚是否发麻：明确否认"], PROTO)



@pytest.mark.parametrize("text,key,status", [
    ("没有腿麻。", "leg_numbness", "denied"),
    ("右腿有点麻。", "leg_numbness", "present"),          # "有点"是程度，不是拿不准
    ("会阴部发麻。", "leg_numbness", None),               # 会阴麻不是腿麻
    ("以前从来没麻过，这两天左脚开始发麻。", "leg_numbness", "present"),
    ("腿好像有点麻。", "leg_numbness", "uncertain"),
    ("右边屁股好像也有点疼，说不好是不是串过去的。", "radiation_present", "uncertain"),  # 疑问句式不是否定
])
def test_mock_negation_and_hedges(text, key, status):
    out = P.MockProvider().extract(text, PROTO)
    got = [f.status for f in out.facts if f.key == key]
    if status is None:
        assert got == []
    else:
        assert status in got and ("denied" not in got or status == "denied")
