"""T2 (AST-15 O1-B): WebFetchTool SSRF mitigations.

Covers the three required scenarios plus regression guards:
- hosts that resolve to private/loopback/link-local/reserved ranges are
  rejected BEFORE connecting (every IP returned by the resolver is checked),
- redirects are followed manually (max 3 hops) and each hop's host is
  re-validated, so a public URL cannot pivot to an internal target,
- bodies over 1 MiB are rejected while streaming (iter_bytes counter).
"""
import ipaddress
import socket

import httpx
import pytest

from bytia_kode.tools.registry import WebFetchTool

PUBLIC_IP = "93.184.216.34"  # example.com — used as a stand-in public address


def _resolver(mapping: dict[str, list[str]]):
    """Build a fake socket.getaddrinfo honoring `mapping`; IP literals pass through."""

    def getaddrinfo(host, *args, **kwargs):
        host = host.strip("[]")
        if host in mapping:
            ips = mapping[host]
        else:
            try:
                ipaddress.ip_address(host)
            except ValueError:
                raise socket.gaierror(8, f"Name or service not known: {host}") from None
            ips = [host]
        results = []
        for ip in ips:
            family = socket.AF_INET6 if ":" in ip else socket.AF_INET
            sockaddr = (ip, 0, 0, 0) if family == socket.AF_INET6 else (ip, 0)
            results.append((family, socket.SOCK_STREAM, 6, "", sockaddr))
        return results

    return getaddrinfo


@pytest.fixture
def tool():
    return WebFetchTool()


@pytest.fixture
def mock_http(monkeypatch):
    """Install an httpx.MockTransport + fake DNS for WebFetchTool's own client."""

    def install(handler, dns=None):
        if dns is not None:
            monkeypatch.setattr(socket, "getaddrinfo", _resolver(dns))
        real_client = httpx.AsyncClient

        def client_factory(*args, **kwargs):
            return real_client(transport=httpx.MockTransport(handler), *args, **kwargs)

        monkeypatch.setattr("bytia_kode.tools.registry.httpx.AsyncClient", client_factory)

    return install


@pytest.mark.asyncio
async def test_private_ip_literals_rejected(tool):
    """Direct private/loopback/link-local/reserved targets never connect.

    IP literals need no DNS: getaddrinfo parses them, the range check denies.
    """
    for url in (
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata (link-local)
        "http://192.168.1.1/admin",  # RFC1918
        "http://10.0.0.5/",  # RFC1918
        "http://172.16.0.9/",  # RFC1918
        "http://127.0.0.1:8080/",  # loopback
        "http://0.0.0.0/",  # unspecified
        "http://[::1]/",  # IPv6 loopback
        "http://[fe80::1]/",  # IPv6 link-local
        "http://[fc00::1]/",  # IPv6 ULA (fc00::/7)
    ):
        result = await tool.execute(url=url)
        assert result.error, f"expected rejection for {url}"
        assert "Security violation" in result.output
        assert "non-public" in result.output


@pytest.mark.asyncio
async def test_hostname_resolving_to_private_ip_rejected(tool, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _resolver({"internal.corp": ["10.0.0.5"]}))
    result = await tool.execute(url="http://internal.corp/api")
    assert result.error
    assert "non-public" in result.output
    assert "10.0.0.5" in result.output


@pytest.mark.asyncio
async def test_mixed_resolution_any_private_ip_rejected(tool, monkeypatch):
    """A record set with one public + one private IP is denied — ALL IPs are checked."""
    monkeypatch.setattr(
        socket, "getaddrinfo", _resolver({"mixed.example": [PUBLIC_IP, "172.16.0.9"]})
    )
    result = await tool.execute(url="http://mixed.example/")
    assert result.error
    assert "172.16.0.9" in result.output


@pytest.mark.asyncio
async def test_unresolvable_host_rejected_as_error(tool, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _resolver({}))
    result = await tool.execute(url="http://does-not-exist.example/")
    assert result.error
    assert "Cannot resolve host" in result.output


@pytest.mark.asyncio
async def test_redirect_302_to_internal_ip_rejected(tool, mock_http):
    """The classic SSRF pivot: public URL 302s to an internal IP."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "public.example":
            return httpx.Response(302, headers={"Location": "http://10.0.0.9/secret"})
        raise AssertionError(f"connection to internal host leaked: {request.url}")

    mock_http(handler, dns={"public.example": [PUBLIC_IP]})
    result = await tool.execute(url="http://public.example/start")
    assert result.error
    assert "non-public" in result.output
    assert "10.0.0.9" in result.output


@pytest.mark.asyncio
async def test_redirect_302_to_private_hostname_rejected(tool, mock_http):
    """Same pivot but by hostname — the redirect target resolves private."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "public.example":
            return httpx.Response(302, headers={"Location": "http://internal.example/x"})
        raise AssertionError(f"connection to internal host leaked: {request.url}")

    mock_http(handler, dns={"public.example": [PUBLIC_IP], "internal.example": ["192.168.0.9"]})
    result = await tool.execute(url="http://public.example/start")
    assert result.error
    assert "non-public" in result.output


@pytest.mark.asyncio
async def test_redirect_chain_public_ok(tool, mock_http):
    """Public → public redirects (relative + absolute Location) still work."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/start":
            return httpx.Response(302, headers={"Location": "/hop1"})
        if path == "/hop1":
            return httpx.Response(302, headers={"Location": "http://ok2.example/hop2"})
        return httpx.Response(200, text="final content", headers={"Content-Type": "text/plain"})

    mock_http(handler, dns={"public.example": [PUBLIC_IP], "ok2.example": [PUBLIC_IP]})
    result = await tool.execute(url="http://public.example/start")
    assert not result.error, result.output
    assert "final content" in result.output


@pytest.mark.asyncio
async def test_too_many_redirects_rejected(tool, mock_http):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": f"{request.url.path}next"})

    mock_http(handler, dns={"public.example": [PUBLIC_IP]})
    result = await tool.execute(url="http://public.example/start")
    assert result.error
    assert "Too many redirects" in result.output


@pytest.mark.asyncio
async def test_download_over_1mb_rejected(tool, mock_http):
    """A body past the 1 MiB cap is rejected while streaming, not buffered."""
    big = "x" * (1_048_576 + 1024)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=big, headers={"Content-Type": "text/plain"})

    mock_http(handler, dns={"public.example": [PUBLIC_IP]})
    result = await tool.execute(url="http://public.example/big")
    assert result.error
    assert "download limit" in result.output


@pytest.mark.asyncio
async def test_download_under_1mb_ok(tool, mock_http):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="small body", headers={"Content-Type": "text/plain"})

    mock_http(handler, dns={"public.example": [PUBLIC_IP]})
    result = await tool.execute(url="http://public.example/small")
    assert not result.error, result.output
    assert "small body" in result.output
