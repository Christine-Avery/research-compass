"""Read-only Python TLS diagnostic for the locally configured Upstash URL.

This sends an unauthenticated HEAD request only. It never reads the Redis
token/HMAC value, never sends a Redis command, and never disables TLS checks.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import ssl
import sys
import time
import tomllib
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener, getproxies


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".streamlit" / "secrets.toml"
sys.path.insert(0, str(ROOT))
from research_compass.public_budget import build_upstash_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main() -> int:
    settings = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    url = str(settings.get("UPSTASH_REDIS_REST_URL", "")).strip()
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".upstash.io"):
        print(json.dumps({"configured_https_upstash_url": False}))
        return 2

    paths = ssl.get_default_verify_paths()
    context = ssl.create_default_context()
    proxy_map = getproxies()
    names = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR")
    report: dict[str, object] = {
        "configured_https_upstash_url": True,
        "python_version": sys.version.split()[0],
        "openssl_version": ssl.OPENSSL_VERSION,
        "trust_store_stats": context.cert_store_stats(),
        "default_cafile_configured": bool(paths.cafile),
        "default_cafile_exists": bool(paths.cafile and Path(paths.cafile).exists()),
        "default_capath_configured": bool(paths.capath),
        "default_capath_exists": bool(paths.capath and Path(paths.capath).exists()),
        "proxy_environment_set": {name: bool(os.getenv(name)) for name in names},
        "urllib_proxy_configured": bool(proxy_map),
        "urllib_proxy_schemes": sorted(proxy_map.keys()),
    }
    opener = build_opener(NoRedirect())
    request = Request(url, method="HEAD", headers={"User-Agent": "ResearchCompass-TLS-Diagnostic/1"})
    started = time.perf_counter()
    try:
        with opener.open(request, timeout=12) as response:
            report["http_status"] = response.status
            report["python_tls"] = "verified"
    except HTTPError as exc:
        # 401/403/405 still prove TLS succeeded; no auth header was sent.
        report["http_status"] = exc.code
        report["python_tls"] = "verified_http_error"
    except URLError as exc:
        reason = exc.reason
        report["python_tls"] = type(reason).__name__
        if isinstance(reason, ssl.SSLCertVerificationError):
            report["verify_code"] = reason.verify_code
            report["verify_message"] = reason.verify_message
    except (TimeoutError, OSError) as exc:
        report["python_tls"] = type(exc).__name__
    report["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)

    # Compare OpenSSL's regular Windows-store path against the same verified
    # Mozilla CA bundle that is already installed with the Python environment.
    try:
        import certifi

        certifi_context = ssl.create_default_context(cafile=certifi.where())
        certifi_opener = build_opener(NoRedirect(), HTTPSHandler(context=certifi_context))
        certifi_request = Request(url, method="HEAD", headers={"User-Agent": "ResearchCompass-TLS-Diagnostic/1"})
        started = time.perf_counter()
        try:
            with certifi_opener.open(certifi_request, timeout=12) as response:
                report["certifi_tls"] = "verified"
                report["certifi_http_status"] = response.status
        except HTTPError as exc:
            report["certifi_tls"] = "verified_http_error"
            report["certifi_http_status"] = exc.code
        except URLError as exc:
            reason = exc.reason
            report["certifi_tls"] = type(reason).__name__
            if isinstance(reason, ssl.SSLCertVerificationError):
                report["certifi_verify_code"] = reason.verify_code
                report["certifi_verify_message"] = reason.verify_message
        report["certifi_elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        report["certifi_bundle_configured"] = True
    except ImportError:
        report["certifi_bundle_configured"] = False

    # Check direct TLS by resolved address, still with normal CA and hostname
    # validation. No HTTP request or credential is sent in this section.
    direct_results: list[dict[str, object]] = []
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    seen: set[tuple[int, tuple]] = set()
    for family, socktype, proto, _canonname, sockaddr in addresses:
        marker = (family, sockaddr)
        if marker in seen:
            continue
        seen.add(marker)
        item: dict[str, object] = {"address_family": "IPv6" if family == socket.AF_INET6 else "IPv4"}
        try:
            with socket.create_connection(sockaddr, timeout=8) as raw:
                with context.wrap_socket(raw, server_hostname=parsed.hostname):
                    item["python_direct_tls"] = "verified"
        except ssl.SSLCertVerificationError as exc:
            item["python_direct_tls"] = type(exc).__name__
            item["verify_code"] = exc.verify_code
            item["verify_message"] = exc.verify_message
        except (TimeoutError, OSError) as exc:
            item["python_direct_tls"] = type(exc).__name__
        direct_results.append(item)
    report["python_direct_tls_by_family"] = direct_results

    # Exercise the exact strict transport configured for live Upstash EVAL,
    # but make an unauthenticated HEAD request and send no Redis command.
    app_opener = build_upstash_opener()
    app_request = Request(url, method="HEAD", headers={"User-Agent": "ResearchCompass-TLS-Diagnostic/1"})
    started = time.perf_counter()
    try:
        with app_opener.open(app_request, timeout=12) as response:
            report["application_transport_tls"] = "verified"
            report["application_transport_http_status"] = response.status
    except HTTPError as exc:
        report["application_transport_tls"] = "verified_http_error"
        report["application_transport_http_status"] = exc.code
    except URLError as exc:
        reason = exc.reason
        report["application_transport_tls"] = type(reason).__name__
        if isinstance(reason, ssl.SSLCertVerificationError):
            report["application_transport_verify_code"] = reason.verify_code
            report["application_transport_verify_message"] = reason.verify_message
    except (TimeoutError, OSError) as exc:
        report["application_transport_tls"] = type(exc).__name__
    report["application_transport_elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)

    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
