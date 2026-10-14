"""Opt-in live Upstash acceptance checks; never calls a model or clears Redis.

Run with the project interpreter from the repository root. All Redis keys are
written beneath a unique ``rc-test:acceptance:<run-id>`` namespace and are left
in place as audit evidence. The script prints no credential or endpoint values.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
import tomllib
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_compass.public_budget import (
    BREAKER_FAILURE_LIMIT,
    BREAKER_SECONDS,
    MAX_CALLS_PER_VISITOR_PER_DAY,
    MAX_CONCURRENT,
    REQUEST_TIMEOUT_SECONDS,
    PublicBudgetError,
    PublicBudgetManager,
    RESERVE_LUA,
    UpstashRestClient,
    build_upstash_opener,
)


SECRETS_FILE = ROOT / ".streamlit" / "secrets.toml"
TEST_QUERY = "acceptance-only synthetic reservation; no model request"
TEST_VISITOR = "rc-test-acceptance-visitor"


def load_private_settings() -> tuple[str, str, str, dict[str, bool]]:
    if not SECRETS_FILE.is_file():
        raise RuntimeError("private Streamlit Secrets file is unavailable")
    settings = tomllib.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    required = ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "PUBLIC_BUDGET_HMAC_KEY")
    values = {key: str(settings.get(key, "")).strip() for key in required}
    enabled_flags = {
        key: str(os.getenv(key, settings.get(key, "false"))).strip().lower() == "true"
        for key in ("PUBLIC_QWEN_ENABLED", "PUBLIC_QWEN_SECURITY_REVIEW_PASSED")
    }
    # Public model calls remain unavailable throughout this acceptance run.
    if any(enabled_flags.values()):
        raise RuntimeError("public Qwen safety switches must both remain false")
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise RuntimeError("private Redis configuration is incomplete")
    if len(values["PUBLIC_BUDGET_HMAC_KEY"].encode("utf-8")) < 32:
        raise RuntimeError("private Redis configuration failed validation")
    return values[required[0]], values[required[1]], values[required[2]], enabled_flags


def manager_for(url: str, token: str, secret: str, namespace: str) -> PublicBudgetManager:
    return PublicBudgetManager(UpstashRestClient(url, token, timeout=8.0), secret, namespace=namespace)


def redacted_connectivity_diagnostic(url: str) -> dict[str, object]:
    """Check DNS and the application's strict TLS path without credentials."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    outcome: dict[str, object] = {"dns": "not_run", "tls": "not_run", "http_status": None, "eval": "not_run"}
    try:
        addresses = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        outcome["dns"] = "resolved" if addresses else "empty_answer"
    except OSError as exc:
        outcome["dns"] = type(exc).__name__
        return outcome
    request = Request(url, method="HEAD", headers={"User-Agent": "ResearchCompass-Upstash-Acceptance/1"})
    try:
        with build_upstash_opener().open(request, timeout=12) as response:
            outcome["http_status"] = response.status
            outcome["tls"] = "verified"
    except HTTPError as exc:
        outcome["http_status"] = exc.code
        outcome["tls"] = "verified_http_error"
    except URLError as exc:
        outcome["tls"] = type(exc.reason).__name__
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            outcome["tls_verify_code"] = exc.reason.verify_code
            outcome["tls_verify_message"] = exc.reason.verify_message
    except (TimeoutError, OSError) as exc:
        outcome["tls"] = type(exc).__name__
    return outcome


def try_reserve(manager: PublicBudgetManager, index: int) -> tuple[bool, str]:
    try:
        manager.reserve(visitor_ip=f"acceptance-visitor-{index}", query=f"parallel synthetic query {index}")
        return True, "reserved"
    except PublicBudgetError as exc:
        return False, str(exc)


def script_reserve(
    client: UpstashRestClient,
    secret: str,
    namespace: str,
    *,
    visitor_ip: str,
    query: str,
    call_id: str,
    budget_microcny: int = 5_000_000,
    reserve_microcny: int = 50_000,
    max_visits: int = MAX_CALLS_PER_VISITOR_PER_DAY,
    max_concurrent: int = MAX_CONCURRENT,
    now: int | None = None,
) -> str:
    """Exercise the production Lua with explicit limits in a test namespace."""
    if not namespace.startswith("rc-test:acceptance:"):
        raise RuntimeError("refusing Redis test outside the approved isolated namespace")
    manager = manager_for(client.url, client.token, secret, namespace)
    timestamp = int(time.time()) if now is None else now
    day = time.strftime("%Y%m%d", time.gmtime(timestamp))
    visitor = manager._digest(visitor_ip)
    idem = manager._digest(f"{visitor}:{day}:{query}")
    keys = [
        f"{namespace}:reserved_microcny", f"{namespace}:reservations",
        f"{namespace}:active", f"{namespace}:visitors:{day}:{visitor}",
        f"{namespace}:idempotency:{day}:{visitor}", f"{namespace}:failures",
        f"{namespace}:breaker_until",
    ]
    args = ["reserve", str(timestamp), str(budget_microcny), str(reserve_microcny),
            str(max_visits), str(max_concurrent), str(BREAKER_FAILURE_LIMIT),
            str(BREAKER_SECONDS), call_id, visitor, idem, "172800", "", "", "", "0"]
    response = client.eval(RESERVE_LUA, keys, args)
    if not isinstance(response, list) or len(response) < 2:
        return "invalid_response"
    return response[1].decode() if isinstance(response[1], bytes) else str(response[1])


def run_transport_fault_case(url: str, token: str, kind: str) -> bool:
    """Exercise the real client error mapping with an injected socket failure."""
    from urllib.error import URLError

    class FaultingOpener:
        def open(self, *_args, **_kwargs):
            if kind == "timeout":
                raise URLError(TimeoutError("simulated timeout"))
            raise URLError(ConnectionError("simulated disconnect"))

    client = UpstashRestClient(url, token, timeout=1.0)
    with patch("research_compass.public_budget.build_opener", return_value=FaultingOpener()):
        try:
            client.eval("return 1", [], [])
        except PublicBudgetError:
            return True
    return False


def worker() -> int:
    url, token, secret, _ = load_private_settings()
    namespace = sys.argv[2]
    if sys.argv[1] == "--worker-state":
        label = sys.argv[3]
        manager = manager_for(url, token, secret, namespace)
        admitted = reserve_result(manager, f"cross-process-{label}", f"cross-process-query-{label}")
        client = UpstashRestClient(url, token, timeout=8.0)
        reserved = client.eval("return redis.call('GET', KEYS[1])", [f"{namespace}:reserved_microcny"], [])
        active = client.eval("return redis.call('SCARD', KEYS[1])", [f"{namespace}:active"], [])
        print(json.dumps({"admitted": admitted, "reserved_microcny": int(reserved or 0), "active": int(active)}))
        return 0
    manager = manager_for(url, token, secret, namespace)
    try:
        manager.reserve(visitor_ip=TEST_VISITOR, query=TEST_QUERY)
    except PublicBudgetError:
        # A duplicate is expected; only report a boolean, never exception text.
        print(json.dumps({"cross_process_duplicate_blocked": True}))
        return 0
    print(json.dumps({"cross_process_duplicate_blocked": False}))
    return 3


def persist_report(result: dict[str, object]) -> str:
    report_dir = ROOT / "evaluation" / "security_acceptance"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"upstash_live_{result['run_id']}.json"
    relative_path = str(report_path.relative_to(ROOT)).replace("\\", "/")
    result["report_path"] = relative_path
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return relative_path


def reserve_result(manager: PublicBudgetManager, visitor: str = TEST_VISITOR, query: str = TEST_QUERY) -> bool:
    try:
        manager.reserve(visitor_ip=visitor, query=query)
        return True
    except PublicBudgetError:
        return False


def script_reserve(
    client: UpstashRestClient,
    secret: str,
    namespace: str,
    *,
    visitor_ip: str,
    query: str,
    call_id: str,
    budget_microcny: int = 5_000_000,
    reserve_microcny: int = 50_000,
    max_visits: int = MAX_CALLS_PER_VISITOR_PER_DAY,
    max_concurrent: int = MAX_CONCURRENT,
) -> str:
    """Run the production Lua with explicit limits inside the approved test prefix."""
    if not namespace.startswith("rc-test:acceptance:"):
        raise RuntimeError("refusing Redis test outside the approved isolated namespace")
    manager = manager_for(client.url, client.token, secret, namespace)
    timestamp = int(time.time())
    day = time.strftime("%Y%m%d", time.gmtime(timestamp))
    visitor = manager._digest(visitor_ip)
    idem = manager._digest(f"{visitor}:{day}:{query}")
    keys = [
        f"{namespace}:reserved_microcny", f"{namespace}:reservations",
        f"{namespace}:active", f"{namespace}:visitors:{day}:{visitor}",
        f"{namespace}:idempotency:{day}:{visitor}", f"{namespace}:failures",
        f"{namespace}:breaker_until",
    ]
    args = ["reserve", str(timestamp), str(budget_microcny), str(reserve_microcny),
            str(max_visits), str(max_concurrent), str(BREAKER_FAILURE_LIMIT),
            str(BREAKER_SECONDS), call_id, visitor, idem, "172800", "", "", "", "0"]
    response = client.eval(RESERVE_LUA, keys, args)
    if not isinstance(response, list) or len(response) < 2:
        return "invalid_response"
    return response[1].decode() if isinstance(response[1], bytes) else str(response[1])


def run_transport_fault_case(url: str, token: str, kind: str) -> bool:
    """Inject transport failures into the real REST client's fail-closed path."""
    from urllib.error import URLError

    class FaultingOpener:
        def open(self, *_args, **_kwargs):
            if kind == "timeout":
                raise URLError(TimeoutError("simulated timeout"))
            raise URLError(ConnectionError("simulated disconnect"))

    client = UpstashRestClient(url, token, timeout=1.0)
    with patch("research_compass.public_budget.build_opener", return_value=FaultingOpener()):
        try:
            client.eval("return 1", [], [])
        except PublicBudgetError:
            return True
    return False


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("--worker", "--worker-state"):
        return worker()

    url, token, secret, qwen_switches = load_private_settings()
    run_id = uuid.uuid4().hex
    base = f"rc-test:acceptance:{run_id}"
    result: dict[str, object] = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "credentials_configured": True,
        "public_qwen_enabled": qwen_switches["PUBLIC_QWEN_ENABLED"],
        "public_qwen_security_review_passed": qwen_switches["PUBLIC_QWEN_SECURITY_REVIEW_PASSED"],
        "model_api_calls": 0,
        "isolated_key_prefix": base,
        "formal_budget_namespace_touched": False,
        "tests": {},
    }
    stage = "unauthenticated_tls_preflight"
    try:
        # Strict TLS check first; this HEAD carries no token and runs before EVAL.
        preflight = redacted_connectivity_diagnostic(url)
        result["tests"][stage] = preflight
        if preflight.get("tls") not in ("verified", "verified_http_error"):
            result["tests"]["real_upstash_eval"] = "NOT_RUN_TLS_BLOCKED"
            raise RuntimeError("strict unauthenticated HTTPS preflight failed")

        stage = "real_upstash_eval"
        client = UpstashRestClient(url, token, timeout=8.0)
        if client.eval("return redis.call('PING')", [], []) != "PONG":
            raise RuntimeError("Upstash EVAL connectivity check returned an unexpected result")
        result["tests"][stage] = "PASS"

        # Eight real concurrent admissions compete for the two shared slots.
        stage = "atomic_concurrency_limit"
        concurrent_manager = manager_for(url, token, secret, f"{base}:concurrency")
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda i: try_reserve(concurrent_manager, i), range(8)))
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        admitted = sum(1 for accepted, _ in outcomes if accepted)
        if admitted != MAX_CONCURRENT:
            raise RuntimeError("concurrency gate did not enforce the configured maximum")
        result[stage] = {"status": "PASS", "requests": 8, "admitted": admitted,
                         "limit": MAX_CONCURRENT, "elapsed_ms": elapsed}

        # Competing identical submissions must result in one reservation only.
        stage = "concurrent_duplicate_idempotency"
        idem_namespace = f"{base}:idempotency"
        idem_manager = manager_for(url, token, secret, idem_namespace)
        with ThreadPoolExecutor(max_workers=8) as pool:
            duplicate_race = list(pool.map(lambda _: reserve_result(idem_manager), range(8)))
        if sum(duplicate_race) != 1:
            raise RuntimeError("concurrent duplicate request was not idempotent")
        result[stage] = {"status": "PASS", "racing_requests": 8, "admitted": 1,
                         "rejected_as_duplicate": 7}

        # State must survive both manager reconstruction and a separate process.
        stage = "persistence_and_cross_process_sharing"
        reloaded_manager = manager_for(url, token, secret, idem_namespace)
        if reserve_result(reloaded_manager):
            raise RuntimeError("duplicate was admitted after manager reconstruction")
        child = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker", idem_namespace],
            cwd=ROOT, capture_output=True, text=True, timeout=20, check=False,
        )
        try:
            child_result = json.loads(child.stdout.strip())
        except (ValueError, json.JSONDecodeError):
            child_result = {}
        if child.returncode != 0 or child_result.get("cross_process_duplicate_blocked") is not True:
            raise RuntimeError("cross-process Redis state check failed")
        result[stage] = {"status": "PASS", "manager_reconstruction": True, "separate_process": True}

        stage = "cross_process_budget_and_concurrency_state"
        state_namespace = f"{base}:cross-process-state"
        manager_for(url, token, secret, state_namespace).reserve(
            visitor_ip="cross-process-parent", query="cross-process-parent-query")
        child_args = [sys.executable, str(Path(__file__).resolve()), "--worker-state", state_namespace]
        first_child = subprocess.run([*child_args, "first"], cwd=ROOT, capture_output=True,
                                     text=True, timeout=20, check=False)
        second_child = subprocess.run([*child_args, "second"], cwd=ROOT, capture_output=True,
                                      text=True, timeout=20, check=False)
        try:
            first_state = json.loads(first_child.stdout.strip())
            second_state = json.loads(second_child.stdout.strip())
        except (ValueError, json.JSONDecodeError):
            first_state, second_state = {}, {}
        if (first_child.returncode != 0 or second_child.returncode != 0
                or first_state.get("admitted") is not True
                or first_state.get("reserved_microcny") != 100_000
                or first_state.get("active") != 2
                or second_state.get("admitted") is not False
                or second_state.get("reserved_microcny") != 100_000
                or second_state.get("active") != 2):
            raise RuntimeError("cross-process budget/concurrency state was not shared")
        result[stage] = {"status": "PASS", "separate_processes": 2,
                         "shared_reserved_microcny": 100_000, "concurrent_slots_observed": 2,
                         "third_reservation_denied": True}

        # Exact configured ceiling in an isolated namespace: 100 × ¥0.05 = ¥5.
        stage = "five_cny_budget_boundary"
        budget_namespace = f"{base}:budget-boundary"
        outcomes = [script_reserve(client, secret, budget_namespace,
                                   visitor_ip=f"budget-visitor-{i}", query=f"budget-query-{i}",
                                   call_id=f"budget-call-{i}", max_concurrent=101)
                    for i in range(100)]
        denied = script_reserve(client, secret, budget_namespace,
                                visitor_ip="budget-visitor-over", query="budget-query-over",
                                call_id="budget-call-over", max_concurrent=101)
        reserved = client.eval("return redis.call('GET', KEYS[1])",
                               [f"{budget_namespace}:reserved_microcny"], [])
        if outcomes.count("reserved") != 100 or denied != "budget_exhausted" or str(reserved) != "5000000":
            raise RuntimeError("¥5/¥0.05 isolated budget boundary did not match 100 reservations")
        result[stage] = {"status": "PASS", "budget_cny": 5.0, "reservation_cny": 0.05,
                         "accepted_reservations": 100, "101st_result": denied,
                         "reserved_microcny": int(reserved)}

        # Per-visitor daily quota is checked independently of relevance or evidence.
        stage = "daily_visitor_limit"
        visitor_manager = manager_for(url, token, secret, f"{base}:visitor-limit")
        for index in range(MAX_CALLS_PER_VISITOR_PER_DAY):
            visitor_manager.reserve(visitor_ip=TEST_VISITOR, query=f"daily-query-{index}").finish(
                success=True, usage=None, latency_ms=1.0)
        visitor_denied = not reserve_result(visitor_manager, TEST_VISITOR, "daily-query-third")
        if not visitor_denied:
            raise RuntimeError("daily visitor quota admitted a third request")
        result[stage] = {"status": "PASS", "limit": MAX_CALLS_PER_VISITOR_PER_DAY,
                         "third_request_denied": True}

        # Simulated unknown provider outcome after reservation must keep its spend.
        stage = "timeout_reservation_not_refunded"
        timeout_namespace = f"{base}:timeout-after-reserve"
        timeout_manager = manager_for(url, token, secret, timeout_namespace)
        reservation = timeout_manager.reserve(visitor_ip=TEST_VISITOR, query="synthetic provider timeout")
        reservation.unknown_failure(latency_ms=REQUEST_TIMEOUT_SECONDS * 1000)
        spend = client.eval("return redis.call('GET', KEYS[1])",
                            [f"{timeout_namespace}:reserved_microcny"], [])
        active = client.eval("return redis.call('SCARD', KEYS[1])",
                             [f"{timeout_namespace}:active"], [])
        if str(spend) != "50000" or int(active) != 1:
            raise RuntimeError("unknown timeout outcome incorrectly refunded its reservation")
        result[stage] = {"status": "PASS", "provider_call": False,
                         "reservation_retained_microcny": int(spend), "active_slot_retained": True}

        # Invalid credential is sent only to Upstash; it cannot authorize a write.
        stage = "authentication_failure_fail_closed"
        bad_auth_client = UpstashRestClient(url, "invalid-acceptance-token", timeout=8.0)
        auth_denied = not reserve_result(
            PublicBudgetManager(bad_auth_client, secret, namespace=f"{base}:bad-auth"),
            "bad-auth-visitor", "isolated auth failure")
        if not auth_denied:
            raise RuntimeError("invalid Redis credential did not fail closed")
        result[stage] = {"status": "PASS", "expected_http_rejection": True}

        # Induce a real Redis script/type write error on a unique test-only key.
        stage = "redis_write_error_fail_closed"
        write_error = False
        try:
            client.eval("redis.call('SET', KEYS[1], 'test'); return redis.call('HSET', KEYS[1], 'f', 'v')",
                        [f"{base}:write-error:wrong-type"], [])
        except PublicBudgetError:
            write_error = True
        if not write_error:
            raise RuntimeError("Redis script write/type error did not fail closed")
        result[stage] = {"status": "PASS", "isolated_test_key_only": True}

        # Deterministic timeout/disconnect injection tests the same fail-closed client path.
        stage = "transport_timeout_disconnect_fail_closed"
        if not run_transport_fault_case(url, token, "timeout") or not run_transport_fault_case(url, token, "disconnect"):
            raise RuntimeError("simulated transport fault did not fail closed")
        result[stage] = {"status": "PASS", "mode": "injected transport faults",
                         "timeout": "fail_closed", "disconnect": "fail_closed"}

        result["status"] = "PASS"
        result["isolated_namespace_only"] = True
    except Exception as exc:
        result["status"] = "FAIL"
        result["failed_at"] = stage
        result["failure_type"] = type(exc).__name__
    report_path = persist_report(result)
    result["report_path"] = report_path
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
