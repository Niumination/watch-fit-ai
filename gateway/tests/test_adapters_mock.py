"""Adapter diuji terhadap server palsu sungguhan (bukan mock fungsi)."""
import pytest

from app.adapters.opencode import OpencodeAdapter
from app.adapters.http_generic import HttpAgentAdapter


async def collect(adapter, text):
    out = []
    async for chunk in adapter.stream(text):
        out.append(chunk)
    await adapter.aclose()
    return "".join(out)


async def test_opencode_adapter_streams_and_authenticates(mock_agents_url):
    a = OpencodeAdapter(base_url=mock_agents_url, password="rahasia")
    text = await collect(a, "ringkas status deploy")
    assert "opencode palsu" in text
    assert "ringkas status deploy" in text


async def test_opencode_adapter_without_password_gets_401(mock_agents_url):
    a = OpencodeAdapter(base_url=mock_agents_url, password="")
    with pytest.raises(Exception):
        await collect(a, "halo")


async def test_generic_http_adapter(mock_agents_url):
    a = HttpAgentAdapter("deepseek-harness", f"{mock_agents_url}/ask", token="tok123")
    text = await collect(a, "analisa log")
    assert "deepseek-harness palsu" in text


async def test_openai_compatible_adapter(mock_agents_url):
    a = HttpAgentAdapter("x", mock_agents_url, token="tok123", openai=True)
    text = await collect(a, "halo")
    assert "OpenAI-compat" in text
