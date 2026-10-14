"""Token-free DashScope DNS/TCP/TLS/HTTP diagnosis; never sends the API key."""

from __future__ import annotations

import os
import socket
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, getproxies, urlopen

from dotenv import load_dotenv


load_dotenv()
base = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")).strip().rstrip("/")
parts = urlsplit(base)
host = parts.hostname or ""
key = os.getenv("DASHSCOPE_API_KEY", "").strip()
proxy_values = [value for name, value in os.environ.items() if "PROXY" in name.upper()]


def describe(error: BaseException) -> str:
    chain = []
    seen = set()
    current: BaseException | None = error
    while current and id(current) not in seen:
        seen.add(id(current))
        message = str(current)
        for secret in [key, *proxy_values]:
            if secret:
                message = message.replace(secret, "[redacted]")
        chain.append(f"{type(current).__name__}: {message[:300]}")
        if isinstance(current, URLError) and isinstance(current.reason, BaseException):
            current = current.reason
        else:
            current = current.__cause__ or current.__context__
    return " <- ".join(chain)


print(f"config: key_loaded={bool(key)} model={os.getenv('DASHSCOPE_MODEL', 'qwen3.8-flash')} scheme={parts.scheme} host={host} path={parts.path}")
print("proxy: " + ", ".join(f"{scheme}={urlsplit(value).hostname or 'configured'}" for scheme, value in getproxies().items()))
if parts.scheme != "https" or not host:
    raise SystemExit("Invalid HTTPS base URL")

try:
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    print(f"dns: ok addresses={len(addresses)}")
except Exception as exc:
    print(f"dns: {describe(exc)}")

try:
    with socket.create_connection((host, 443), timeout=6) as connection:
        with ssl.create_default_context().wrap_socket(connection, server_hostname=host) as secure:
            print(f"direct_tcp_tls: ok tls={secure.version()}")
except Exception as exc:
    print(f"direct_tcp_tls: {describe(exc)}")

try:
    request = Request(f"{base}/models", method="GET")
    with urlopen(request, timeout=8) as response:
        print(f"unauthenticated_https_get: HTTP {response.status}")
except HTTPError as exc:
    print(f"unauthenticated_https_get: HTTP {exc.code} (endpoint responded)")
except Exception as exc:
    print(f"unauthenticated_https_get: {describe(exc)}")

if "--auth" in sys.argv:
    if not key:
        print("authenticated_models_get: key_missing")
    else:
        try:
            request = Request(f"{base}/models", headers={"Authorization": f"Bearer {key}"}, method="GET")
            with urlopen(request, timeout=8) as response:
                print(f"authenticated_models_get: HTTP {response.status}")
        except HTTPError as exc:
            print(f"authenticated_models_get: HTTP {exc.code}")
        except Exception as exc:
            print(f"authenticated_models_get: {describe(exc)}")
