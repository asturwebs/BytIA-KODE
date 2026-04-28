"""OpenAI-compatible provider client.

Works with: Z.AI, OpenRouter, MiniMax, Ollama, llama.cpp server, vLLM, anything that speaks /v1/chat/completions.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Message(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    reasoning_content: str | None = None


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: dict  # {"name": "...", "arguments": "{...}"}


class ToolDef(BaseModel):
    type: str = "function"
    function: dict  # {"name", "description", "parameters"}


class ProviderResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
    usage: dict | None = None
    reasoning_content: str | None = None


class ProviderClient:
    """Async OpenAI-compatible chat completions client."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def is_local(self) -> bool:
        """True if this provider is a local server (llama.cpp router, Ollama, etc.)."""
        url = self.base_url.lower()
        return "localhost" in url or "127.0.0.1" in url

    @property
    def supports_grammar(self) -> bool:
        """True if this provider supports GBNF grammar constraints."""
        if ":11434" in url.lower():
            return False
        return self.is_local

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def _request_with_retry(self, request_fn, max_retries: int = 2):
        """Retry on 5xx, timeout, and connection errors with exponential backoff."""
        for attempt in range(max_retries + 1):
            try:
                return await request_fn()
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt < max_retries:
                    wait = 1.0 * (2 ** attempt)
                    logger.warning("Request failed (attempt %d/%d): %s. Retrying in %.1fs",
                                   attempt + 1, max_retries + 1, exc, wait)
                    await asyncio.sleep(wait)
                else:
                    raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code >= 500 and attempt < max_retries:
                    wait = 1.0 * (2 ** attempt)
                    logger.warning("HTTP %d (attempt %d/%d). Retrying in %.1fs",
                                   exc.response.status_code, attempt + 1, max_retries + 1, wait)
                    await asyncio.sleep(wait)
                else:
                    raise

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        stream: bool = False,
    ) -> ProviderResponse:
        """Send a chat completion request."""
        if stream:
            raise NotImplementedError("Use chat_stream() for streaming responses")

        client = await self._get_client()

        payload: dict = {
            "model": self.model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = [t.model_dump() for t in tools]

        logger.debug(f"-> {self.model} | {len(messages)} msgs | tools={len(tools) if tools else 0}")

        async def _do_post():
            r = await client.post("/chat/completions", json=payload)
            r.raise_for_status()
            return r

        resp = await self._request_with_retry(_do_post)

        data = resp.json()
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices or not isinstance(choices, list):
            raise RuntimeError("Provider response missing choices")

        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message") if isinstance(choice, dict) else {}
        if not isinstance(message, dict):
            message = {}

        tool_calls = []
        raw_tool_calls = message.get("tool_calls")
        if isinstance(raw_tool_calls, list):
            for tc in raw_tool_calls:
                try:
                    tool_calls.append(ToolCall(**tc))
                except Exception:
                    continue

        return ProviderResponse(
            content=message.get("content"),
            tool_calls=tool_calls or None,
            finish_reason=choice.get("finish_reason") if isinstance(choice, dict) else None,
            usage=data.get("usage") if isinstance(data, dict) else None,
            reasoning_content=message.get("reasoning_content"),
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> AsyncIterator[tuple[str, str | list[ToolCall]]]:
        """Stream a chat completion with tool call and reasoning support.

        Yields tuples of (type, data):
          ("text", delta_str)         — text chunk
          ("reasoning", delta_str)    — reasoning/thinking chunk
          ("tool_calls", [ToolCall])  — accumulated tool calls (once, at end)
        """
        client = await self._get_client()

        payload: dict = {
            "model": self.model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = [t.model_dump() for t in tools]

        tool_calls_acc: dict[int, dict] = {}

        async with client.stream("POST", "/chat/completions", json=payload) as resp:
            if resp.status_code >= 400:
                body = await resp.aread() if not resp.is_closed else ""
                logger.error(f"Provider HTTP {resp.status_code}: model={self.model} body={body[:500]}")
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})

                    if delta.get("content"):
                        yield ("text", delta["content"])

                    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                    if reasoning:
                        yield ("reasoning", reasoning)

                    if delta.get("tool_calls"):
                        for tc_delta in delta["tool_calls"]:
                            idx = tc_delta.get("index", 0)
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                            if tc_delta.get("id"):
                                tool_calls_acc[idx]["id"] = tc_delta["id"]
                            func = tc_delta.get("function", {})
                            if func.get("name"):
                                tool_calls_acc[idx]["function"]["name"] += func["name"]
                            if func.get("arguments"):
                                tool_calls_acc[idx]["function"]["arguments"] += func["arguments"]
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

        if tool_calls_acc:
            final_tool_calls = []
            for idx in sorted(tool_calls_acc):
                tc = tool_calls_acc[idx]
                final_tool_calls.append(ToolCall(
                    id=tc["id"],
                    type="function",
                    function=tc["function"],
                ))
            yield ("tool_calls", final_tool_calls)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def list_models(self) -> list[str]:
        """List available models from OpenAI-compatible or Ollama endpoint."""
        base = self.base_url.removesuffix("/v1")
        client = await self._get_client()
        # Try OpenAI-compatible format first (llama.cpp, vLLM, etc.)
        try:
            resp = await client.get(f"{base}/v1/models", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]
                if models:
                    return models
        except Exception:
            pass
        # Fall back to Ollama format
        try:
            resp = await client.get(f"{base}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    async def detect_loaded_model(self) -> str | None:
        """Query router API to find which model is currently loaded."""
        try:
            base = self.base_url.removesuffix("/v1")
            client = await self._get_client()
            resp = await client.get(f"{base}/v1/models", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    status = m.get("status", {}).get("value", "")
                    if status == "loaded":
                        return m["id"]
            return None
        except httpx.ConnectError:
            logger.warning("Router not reachable for model detection")
            return None
        except Exception as exc:
            logger.error("Error in detect_loaded_model: %s", exc)
            return None

    async def get_router_info(self) -> dict:
        """Get loaded model info from router: name, ctx-size, prompt tokens."""
        info: dict = {}
        try:
            base = self.base_url.removesuffix("/v1")
            client = await self._get_client()
            resp = await client.get(f"{base}/v1/models", timeout=5.0)
            if resp.status_code != 200:
                return info
            data = resp.json()
            for m in data.get("data", []):
                status = m.get("status", {}).get("value", "")
                if status != "loaded":
                    continue
                info["model"] = m.get("id", "")
                args = m.get("status", {}).get("args", [])
                for i, arg in enumerate(args):
                    if arg == "--ctx-size" and i + 1 < len(args):
                        try:
                            info["ctx_size"] = int(args[i + 1])
                        except ValueError:
                            pass
                        break
                break
            if info.get("model"):
                metrics_resp = await client.get(
                    f"{base}/metrics?model={info['model']}", timeout=5.0
                )
                if metrics_resp.status_code == 200:
                    for line in metrics_resp.text.splitlines():
                        if line.startswith("llamacpp:prompt_tokens_total "):
                            try:
                                info["prompt_tokens"] = int(line.split()[-1])
                            except ValueError:
                                pass
                        elif line.startswith("llamacpp:tokens_predicted_total "):
                            try:
                                info["predicted_tokens"] = int(line.split()[-1])
                            except ValueError:
                                pass
        except Exception:
            pass
        return info
