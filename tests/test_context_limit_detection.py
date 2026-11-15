"""Detección de la ventana de contexto real del servidor.

Incidente 2026-11-15: Unsloth Studio sirve `-c 62208` pero KODE asumía
MAX_CONTEXT_TOKENS (262144) porque `get_router_info` solo extraía `--ctx-size`
de `status.args`, campo que Studio no envía. El resultado: el prompt desbordó
la ventana real y el modelo respondía vacío, con la compactación muerta
(umbral 0.75 x 262144 inalcanzable).
"""
import httpx
import pytest

from bytia_kode.providers.client import ProviderClient


def _client_with_models(payload: dict) -> ProviderClient:
    """ProviderClient cuyo /v1/models devuelve `payload` (sin red real)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/models"):
            return httpx.Response(200, json=payload)
        if "/metrics" in request.url.path:
            return httpx.Response(200, text="")
        return httpx.Response(404)

    client = ProviderClient("http://localhost:8888/v1", "fake-key", "auto")

    async def fake_get_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    client._get_client = fake_get_client  # type: ignore[method-assign]
    return client


class TestContextLimitDetection:
    @pytest.mark.asyncio
    async def test_ctx_size_from_studio_context_length(self):
        """Unsloth Studio publica la ventana efectiva como `context_length`."""
        client = _client_with_models(
            {
                "data": [
                    {
                        "id": "unsloth/Qwen3.8-27B-GGUF",
                        "status": {"value": "loaded"},
                        "context_length": 62208,
                        "max_context_length": 62208,
                        "native_context_length": 262144,
                    }
                ]
            }
        )
        info = await client.get_router_info()
        assert info["ctx_size"] == 62208

    @pytest.mark.asyncio
    async def test_launch_args_win_over_model_field(self):
        """El router llama.cpp manda: --ctx-size de los args tiene prioridad."""
        client = _client_with_models(
            {
                "data": [
                    {
                        "id": "gpt-oss-20b",
                        "status": {"value": "loaded", "args": ["--ctx-size", "32768"]},
                        "context_length": 62208,
                    }
                ]
            }
        )
        info = await client.get_router_info()
        assert info["ctx_size"] == 32768

    @pytest.mark.asyncio
    async def test_loaded_boolean_alone_identifies_model(self):
        """Studio también marca el modelo cargado con `loaded: true`."""
        client = _client_with_models(
            {
                "data": [
                    {
                        "id": "unsloth/Qwen3.8-27B-GGUF",
                        "loaded": True,
                        "context_length": 62208,
                    }
                ]
            }
        )
        info = await client.get_router_info()
        assert info["ctx_size"] == 62208

    @pytest.mark.asyncio
    async def test_native_context_length_is_never_used(self):
        """`native_context_length` es el máximo del modelo, no la ventana servida."""
        client = _client_with_models(
            {
                "data": [
                    {
                        "id": "unsloth/Qwen3.8-27B-GGUF",
                        "status": {"value": "loaded"},
                        "native_context_length": 262144,
                    }
                ]
            }
        )
        info = await client.get_router_info()
        assert "ctx_size" not in info
