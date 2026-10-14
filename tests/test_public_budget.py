from __future__ import annotations

import threading
import time
import ssl

import pytest

from research_compass.public_budget import (
    MAX_CONCURRENT,
    PUBLIC_BUDGET_CNY,
    RESERVATION_MICROCNY,
    PublicBudgetError,
    PublicBudgetManager,
    UpstashRestClient,
    upstash_tls_context,
    conservative_reservation_cny,
    public_budget_enabled,
)


class SimulatedRedis:
    """Atomic in-memory EVAL test double; state survives client/manager recreation."""

    def __init__(self):
        self.lock = threading.Lock()
        self.counters = {}
        self.hashes = {}
        self.sets = {}
        self.expiry = {}

    def eval(self, script, keys, args):
        with self.lock:
            op, now, budget, reserve, max_visits, max_concurrent, breaker_limit, breaker_ttl, call_id, visitor, idem, day_ttl, usage_json, latency, result_status, actual_cost = args
            if op == "reserve":
                if int(self.counters.get(keys[6], 0)) > int(now):
                    return [0, "breaker_open"]
                idem_hash = self.hashes.setdefault(keys[4], {})
                if idem in idem_hash:
                    return [0, "duplicate"]
                if int(self.counters.get(keys[0], 0)) + int(reserve) > int(budget):
                    return [0, "budget_exhausted"]
                active = self.sets.setdefault(keys[2], set())
                if len(active) >= int(max_concurrent):
                    return [0, "concurrency_limit"]
                visits = int(self.counters.get(keys[3], 0))
                if visits >= int(max_visits):
                    return [0, "visitor_limit"]
                self.counters[keys[0]] = int(self.counters.get(keys[0], 0)) + int(reserve)
                active.add(call_id)
                self.hashes.setdefault(keys[1], {})[call_id] = {"status": "reserved", "reserved_microcny": int(reserve)}
                idem_hash[idem] = call_id
                self.counters[keys[3]] = visits + 1
                return [1, "reserved"]
            record = self.hashes.get(keys[1], {}).get(call_id)
            if record is None:
                return [0, "reservation_missing"]
            record.update(status=result_status, usage_json=usage_json, latency_ms=latency, actual_estimated_cost_cny=float(actual_cost) if actual_cost else None)
            if op == "finish":
                self.sets.setdefault(keys[2], set()).discard(call_id)
            if result_status == "error":
                failures = int(self.counters.get(keys[5], 0)) + 1
                self.counters[keys[5]] = failures
                if failures >= int(breaker_limit):
                    self.counters[keys[6]] = int(now) + int(breaker_ttl)
            elif result_status == "success":
                self.counters.pop(keys[5], None)
                self.counters.pop(keys[6], None)
            return [1, "recorded"]


def make_manager(redis=None, namespace="budget-test"):
    return PublicBudgetManager(redis or SimulatedRedis(), "x" * 48, namespace=namespace)


def test_reserve_records_without_query_or_ip_and_survives_manager_recreation():
    redis = SimulatedRedis()
    first = make_manager(redis)
    reservation = first.reserve(visitor_ip="203.0.113.8", query="research idea", call_id="c1", now=1_800_000_000)
    assert redis.counters["budget-test:reserved_microcny"] == RESERVATION_MICROCNY
    assert "research idea" not in str(redis.hashes)
    assert "203.0.113.8" not in str(redis.counters)
    second = make_manager(redis)
    with pytest.raises(PublicBudgetError, match="相同请求"):
        second.reserve(visitor_ip="203.0.113.8", query="research idea", call_id="c2", now=1_800_000_000)
    reservation.finish(success=True, usage={"prompt_tokens": 100, "completion_tokens": 80}, latency_ms=321)
    assert redis.hashes["budget-test:reservations"]["c1"]["status"] == "success"
    assert redis.hashes["budget-test:reservations"]["c1"]["latency_ms"] == "321.00"
    assert redis.hashes["budget-test:reservations"]["c1"]["actual_estimated_cost_cny"] > 0


def test_concurrent_reservations_never_exceed_two_slots():
    redis = SimulatedRedis()
    manager = make_manager(redis)
    barrier = threading.Barrier(24)
    accepted = []

    def attempt(index):
        barrier.wait()
        try:
            accepted.append(manager.reserve(visitor_ip=f"198.51.100.{index}", query=f"query {index}", call_id=f"call-{index}", now=1_800_000_000))
        except PublicBudgetError:
            pass

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(24)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(accepted) == MAX_CONCURRENT
    assert len(redis.sets["budget-test:active"]) == MAX_CONCURRENT


def test_budget_boundary_and_daily_visitor_limit():
    redis = SimulatedRedis()
    manager = make_manager(redis)
    for i in range(100):
        manager.reserve(visitor_ip=f"192.0.2.{i}", query=f"q{i}", call_id=f"c{i}", now=1_800_000_000).finish(success=True, usage={}, latency_ms=1)
    with pytest.raises(PublicBudgetError, match="预算已耗尽"):
        manager.reserve(visitor_ip="192.0.2.200", query="last", call_id="last", now=1_800_000_000)
    assert redis.counters["budget-test:reserved_microcny"] == 5_000_000

    visitor_store = SimulatedRedis()
    manager = make_manager(visitor_store, "visitor-limit")
    for i in range(2):
        manager.reserve(visitor_ip="198.51.100.9", query=f"different {i}", call_id=f"v{i}", now=1_800_000_000).finish(success=True, usage={}, latency_ms=1)
    with pytest.raises(PublicBudgetError, match="今日的 Qwen 调用次数"):
        manager.reserve(visitor_ip="198.51.100.9", query="third", call_id="v3", now=1_800_000_000)


def test_failure_reservation_is_not_refunded_and_breaker_opens():
    redis = SimulatedRedis()
    manager = make_manager(redis)
    now = int(time.time())
    for i in range(3):
        manager.reserve(visitor_ip=f"203.0.113.{i}", query=f"fail {i}", call_id=f"f{i}", now=now).finish(success=False, usage=None, latency_ms=20)
    assert redis.counters["budget-test:reserved_microcny"] == 3 * RESERVATION_MICROCNY
    with pytest.raises(PublicBudgetError, match="熔断"):
        manager.reserve(visitor_ip="203.0.113.5", query="later", call_id="later", now=now + 1)


def test_unknown_outcome_keeps_concurrency_slot_and_redis_failure_fails_closed():
    redis = SimulatedRedis()
    manager = make_manager(redis)
    manager.reserve(visitor_ip="203.0.113.1", query="unknown", call_id="u1", now=1_800_000_000).unknown_failure(latency_ms=25_000)
    assert "u1" in redis.sets["budget-test:active"]
    assert redis.counters["budget-test:reserved_microcny"] == RESERVATION_MICROCNY
    assert redis.hashes["budget-test:reservations"]["u1"]["actual_estimated_cost_cny"] is None

    class BrokenRedis:
        def eval(self, *_):
            raise OSError("no connection")

    with pytest.raises(OSError):
        make_manager(BrokenRedis()).reserve(visitor_ip="203.0.113.2", query="q", now=1_800_000_000)


def test_price_reserve_is_conservative_and_public_switches_default_off(monkeypatch):
    assert conservative_reservation_cny() >= RESERVATION_MICROCNY / 1_000_000
    assert conservative_reservation_cny() < 0.06
    monkeypatch.delenv("PUBLIC_DEPLOYMENT", raising=False)
    monkeypatch.delenv("PUBLIC_QWEN_ENABLED", raising=False)
    monkeypatch.delenv("PUBLIC_QWEN_SECURITY_REVIEW_PASSED", raising=False)
    assert public_budget_enabled() is False
    monkeypatch.setenv("PUBLIC_DEPLOYMENT", "true")
    monkeypatch.setenv("PUBLIC_QWEN_ENABLED", "true")
    assert public_budget_enabled() is False
    monkeypatch.setenv("PUBLIC_QWEN_SECURITY_REVIEW_PASSED", "true")
    assert public_budget_enabled() is True


def test_public_qwen_disabled_fails_before_model_or_local_ledger_call(monkeypatch):
    from research_compass.qwen_planning import QwenPlanningError, plan_with_qwen

    monkeypatch.setenv("PUBLIC_DEPLOYMENT", "true")
    monkeypatch.setenv("PUBLIC_QWEN_ENABLED", "false")
    monkeypatch.setenv("PUBLIC_QWEN_SECURITY_REVIEW_PASSED", "false")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-only-not-a-real-key")
    with pytest.raises(QwenPlanningError, match="未启用"):
        plan_with_qwen("a bounded test question")


def test_redis_config_rejects_untrusted_endpoint_and_template_secrets():
    with pytest.raises(PublicBudgetError):
        UpstashRestClient("https://attacker.example", "not-a-real-token")
    with pytest.raises(PublicBudgetError):
        UpstashRestClient("https://example-upstash.upstash.io", "replace-with-a-token")
    with pytest.raises(PublicBudgetError):
        PublicBudgetManager(SimulatedRedis(), "replace-with-a-random-secret-at-least-32-bytes")


def test_upstash_tls_context_uses_strict_certificate_and_hostname_verification():
    context = upstash_tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.cert_store_stats()["x509_ca"] > 0


def test_upstash_transport_failure_is_mapped_to_fail_closed_error(monkeypatch):
    from urllib.error import URLError

    class BrokenOpener:
        def open(self, *_args, **_kwargs):
            raise URLError("simulated connection failure")

    monkeypatch.setattr("research_compass.public_budget.build_opener", lambda *_args: BrokenOpener())
    client = UpstashRestClient("https://acceptance-test.upstash.io", "test-only-token")
    with pytest.raises(PublicBudgetError):
        client.eval("return 1", [], [])
