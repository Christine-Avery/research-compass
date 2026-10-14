"""Fail-closed persistent budget gate for public Qwen calls.

Production uses Upstash Redis REST EVAL so reservation, visitor quota,
idempotency, and concurrency admission are one atomic server operation.
No query text, IP address, or API credential is stored in Redis.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import ssl
import time
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener


PUBLIC_BUDGET_CNY = 5.0
RESERVATION_CNY = 0.05
RESERVATION_MICROCNY = 50_000
MAX_CONCURRENT = 2
MAX_CALLS_PER_VISITOR_PER_DAY = 2
MAX_REQUEST_BYTES = 32_768
REQUEST_TIMEOUT_SECONDS = 25
MAX_OUTPUT_TOKENS = 1_800
INPUT_PRICE_CNY_PER_M = 1.094
OUTPUT_PRICE_CNY_PER_M = 3.427
BREAKER_FAILURE_LIMIT = 3
BREAKER_SECONDS = 900


class PublicBudgetError(RuntimeError):
    """Safe public message; never contains credentials or query content."""


class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def upstash_tls_context() -> ssl.SSLContext:
    """Build a strict TLS context from certifi's maintained Mozilla CA bundle."""
    try:
        import certifi
    except ImportError:
        raise PublicBudgetError("Upstash TLS trust bundle is unavailable; paid calls are disabled.") from None

    context = ssl.create_default_context(cafile=certifi.where())
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise PublicBudgetError("Upstash TLS verification is not configured securely; paid calls are disabled.")
    return context


def build_upstash_opener(context: ssl.SSLContext | None = None):
    """Use urllib's normal proxy discovery with strict certifi-backed HTTPS."""
    tls_context = context or upstash_tls_context()
    if tls_context.verify_mode != ssl.CERT_REQUIRED or not tls_context.check_hostname:
        raise PublicBudgetError("Upstash TLS verification is not configured securely; paid calls are disabled.")
    return build_opener(_RejectRedirect(), HTTPSHandler(context=tls_context))


def conservative_reservation_cny() -> float:
    # UTF-8 serialized payload byte cap is used as a conservative input-token
    # bound. Includes the maximum configured output at the highest verified
    # Qwen3.8-Flash listed rate. The extra margin rounds the computed ~¥0.042
    # to ¥0.05 per attempt.
    estimate = (MAX_REQUEST_BYTES * INPUT_PRICE_CNY_PER_M + MAX_OUTPUT_TOKENS * OUTPUT_PRICE_CNY_PER_M) / 1_000_000
    return max(RESERVATION_CNY, estimate)


RESERVE_LUA = r"""
local op = ARGV[1]
local now = tonumber(ARGV[2])
local max_budget = tonumber(ARGV[3])
local reserve = tonumber(ARGV[4])
local max_visits = tonumber(ARGV[5])
local max_concurrent = tonumber(ARGV[6])
local breaker_limit = tonumber(ARGV[7])
local breaker_ttl = tonumber(ARGV[8])
local call_id = ARGV[9]
local visitor_key = ARGV[10]
local idem_key = ARGV[11]
local day_ttl = tonumber(ARGV[12])
local usage_json = ARGV[13]
local latency = ARGV[14]
local result_status = ARGV[15]

-- KEYS: reserved micro-CNY, reservation hash, active set, day visitor counter,
-- day idempotency hash, breaker counter, breaker-until timestamp.
if op == 'reserve' then
  local breaker_until = tonumber(redis.call('GET', KEYS[7]) or '0')
  if breaker_until > now then return {0, 'breaker_open'} end
  if redis.call('HEXISTS', KEYS[5], idem_key) == 1 then return {0, 'duplicate'} end
  local current = tonumber(redis.call('GET', KEYS[1]) or '0')
  if current + reserve > max_budget then return {0, 'budget_exhausted'} end
  if tonumber(redis.call('SCARD', KEYS[3])) >= max_concurrent then return {0, 'concurrency_limit'} end
  local visits = tonumber(redis.call('GET', KEYS[4]) or '0')
  if visits >= max_visits then return {0, 'visitor_limit'} end
  redis.call('INCRBY', KEYS[1], reserve)
  redis.call('SADD', KEYS[3], call_id)
  redis.call('HSET', KEYS[2], call_id, cjson.encode({status='reserved', reserved_microcny=reserve, started_at=now}))
  redis.call('HSET', KEYS[5], idem_key, call_id)
  redis.call('INCR', KEYS[4])
  redis.call('EXPIRE', KEYS[4], day_ttl)
  redis.call('EXPIRE', KEYS[5], day_ttl)
  return {1, 'reserved'}
elseif op == 'finish' or op == 'unknown_failure' then
  local raw = redis.call('HGET', KEYS[2], call_id)
  if not raw then return {0, 'reservation_missing'} end
  local item = cjson.decode(raw)
  item.status = result_status
  item.usage_json = usage_json
  item.latency_ms = latency
  if usage_json ~= '' then
    local usage = cjson.decode(usage_json)
    item.actual_input_tokens = tonumber(usage.prompt_tokens or usage.input_tokens or 0)
    item.actual_output_tokens = tonumber(usage.completion_tokens or usage.output_tokens or 0)
    item.actual_estimated_cost_cny = tonumber(ARGV[16])
  else
    item.actual_input_tokens = cjson.null
    item.actual_output_tokens = cjson.null
    item.actual_estimated_cost_cny = cjson.null
  end
  item.finished_at = now
  redis.call('HSET', KEYS[2], call_id, cjson.encode(item))
  if op == 'finish' then redis.call('SREM', KEYS[3], call_id) end
  if result_status == 'error' then
    local failures = redis.call('INCR', KEYS[6])
    if failures == 1 then redis.call('EXPIRE', KEYS[6], breaker_ttl) end
    if failures >= breaker_limit then redis.call('SET', KEYS[7], now + breaker_ttl, 'EX', breaker_ttl) end
  elseif result_status == 'success' then
    redis.call('DEL', KEYS[6])
    redis.call('DEL', KEYS[7])
  end
  return {1, 'recorded'}
end
return {0, 'unknown_operation'}
"""


class EvalClient(Protocol):
    def eval(self, script: str, keys: list[str], args: list[str]) -> object: ...


class UpstashRestClient:
    def __init__(self, url: str, token: str, *, timeout: float = 3.0):
        parsed = urlsplit(url.strip())
        if (parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".upstash.io")
                or parsed.port not in (None, 443) or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or not token or "replace-with" in token.lower()):
            raise PublicBudgetError("公网预算服务未正确配置；Qwen 已关闭。")
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.tls_context = upstash_tls_context()

    def eval(self, script: str, keys: list[str], args: list[str]) -> object:
        command = ["EVAL", script, str(len(keys)), *keys, *args]
        request = Request(
            self.url,
            data=json.dumps(command, separators=(",", ":")).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            opener = build_upstash_opener(self.tls_context)
            with opener.open(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            raise PublicBudgetError("持久预算服务不可用；为避免无预算调用，Qwen 已关闭。") from None
        if not isinstance(payload, dict) or payload.get("error"):
            raise PublicBudgetError("持久预算服务返回无效响应；Qwen 已关闭。")
        return payload.get("result")


@dataclass
class PublicReservation:
    manager: "PublicBudgetManager"
    call_id: str

    def finish(self, *, success: bool, usage: dict | None, latency_ms: float) -> None:
        self.manager.finish(self.call_id, success=success, usage=usage, latency_ms=latency_ms)

    def unknown_failure(self, *, latency_ms: float) -> None:
        # Unknown provider outcome retains both spend reservation and active slot.
        self.manager.unknown_failure(self.call_id, latency_ms=latency_ms)


class PublicBudgetManager:
    def __init__(self, client: EvalClient, hmac_secret: str, *, namespace: str = "research_compass:public:v1"):
        if len(hmac_secret.encode("utf-8")) < 32 or "replace-with" in hmac_secret.lower():
            raise PublicBudgetError("公网预算 HMAC 密钥缺失或过短；Qwen 已关闭。")
        self.client = client
        self.secret = hmac_secret.encode("utf-8")
        self.namespace = namespace

    def _digest(self, text: str) -> str:
        return hmac.new(self.secret, text.encode("utf-8"), hashlib.sha256).hexdigest()

    def reserve(self, *, visitor_ip: str, query: str, call_id: str | None = None, now: int | None = None) -> PublicReservation:
        if not visitor_ip or len(query.encode("utf-8")) > MAX_REQUEST_BYTES:
            raise PublicBudgetError("请求身份缺失或请求过长；Qwen 已关闭。")
        timestamp = int(time.time() if now is None else now)
        day = time.strftime("%Y%m%d", time.gmtime(timestamp))
        visitor = self._digest(visitor_ip)
        idem = self._digest(f"{visitor}:{day}:{query}")
        call_id = call_id or self._digest(f"{idem}:{timestamp}:{time.monotonic_ns()}")
        keys = [
            f"{self.namespace}:reserved_microcny",
            f"{self.namespace}:reservations",
            f"{self.namespace}:active",
            f"{self.namespace}:visitors:{day}:{visitor}",
            f"{self.namespace}:idempotency:{day}:{visitor}",
            f"{self.namespace}:failures",
            f"{self.namespace}:breaker_until",
        ]
        args = ["reserve", str(timestamp), "5000000", str(RESERVATION_MICROCNY),
                str(MAX_CALLS_PER_VISITOR_PER_DAY), str(MAX_CONCURRENT),
                str(BREAKER_FAILURE_LIMIT), str(BREAKER_SECONDS), call_id, visitor,
                idem, str(172800), "", "", "", "0"]
        result = self.client.eval(RESERVE_LUA, keys, args)
        status = _decode_status(result)
        if status != "reserved":
            raise PublicBudgetError(_DENIALS.get(status, "预算检查失败；Qwen 已关闭。"))
        return PublicReservation(self, call_id)

    def _record(self, call_id: str, *, op: str, success: bool, usage: dict | None, latency_ms: float) -> None:
        now = int(time.time())
        keys = [f"{self.namespace}:reserved_microcny", f"{self.namespace}:reservations",
                f"{self.namespace}:active", "unused", "unused", f"{self.namespace}:failures",
                f"{self.namespace}:breaker_until"]
        usage_json = json.dumps(usage, separators=(",", ":")) if usage is not None else ""
        result_status = "success" if success else "error"
        actual_cost = ""
        if usage is not None:
            input_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
            output_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
            actual_cost = (input_tokens * INPUT_PRICE_CNY_PER_M + output_tokens * OUTPUT_PRICE_CNY_PER_M) / 1_000_000
        args = [op, str(now), "5000000", str(RESERVATION_MICROCNY),
                str(MAX_CALLS_PER_VISITOR_PER_DAY), str(MAX_CONCURRENT),
                str(BREAKER_FAILURE_LIMIT), str(BREAKER_SECONDS), call_id, "", "", "172800",
                usage_json, f"{latency_ms:.2f}", result_status, f"{actual_cost:.8f}" if actual_cost != "" else ""]
        result = self.client.eval(RESERVE_LUA, keys, args)
        status = _decode_status(result)
        if status != "recorded":
            raise PublicBudgetError("预算调用记录写入失败；后续 Qwen 已关闭。")

    def finish(self, call_id: str, *, success: bool, usage: dict | None, latency_ms: float) -> None:
        self._record(call_id, op="finish", success=success, usage=usage, latency_ms=latency_ms)

    def unknown_failure(self, call_id: str, *, latency_ms: float) -> None:
        self._record(call_id, op="unknown_failure", success=False, usage=None, latency_ms=latency_ms)


def _decode_status(value: object) -> str:
    try:
        if isinstance(value, dict):
            value = value.get("result")
        if isinstance(value, list) and len(value) >= 2:
            if not isinstance(value[0], (int, float)) or int(value[0]) != 1:
                return value[1].decode() if isinstance(value[1], bytes) else str(value[1])
            return value[1].decode() if isinstance(value[1], bytes) else str(value[1])
    except (TypeError, ValueError, IndexError):
        pass
    raise PublicBudgetError("预算服务状态无法验证；Qwen 已关闭。")


_DENIALS = {
    "duplicate": "该访客当天已提交相同请求；已阻止重复付费调用。",
    "budget_exhausted": "公网 Qwen 预算已耗尽；已切换规则模式。",
    "concurrency_limit": "当前请求较多，请稍后重试；本次未调用 Qwen。",
    "visitor_limit": "该访客今日的 Qwen 调用次数已用完。",
    "breaker_open": "Qwen 服务暂时熔断；已切换规则模式。",
}


def public_budget_enabled() -> bool:
    """Two explicit switches are required; template defaults remain false."""
    return (os.getenv("PUBLIC_DEPLOYMENT", "false").lower() == "true"
            and os.getenv("PUBLIC_QWEN_ENABLED", "false").lower() == "true"
            and os.getenv("PUBLIC_QWEN_SECURITY_REVIEW_PASSED", "false").lower() == "true")


def streamlit_reservation(query: str, call_id: str | None = None) -> PublicReservation:
    if not public_budget_enabled():
        raise PublicBudgetError("公网 Qwen 未启用；当前使用规则降级。")
    url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    secret = os.getenv("PUBLIC_BUDGET_HMAC_KEY", "")
    if not url or not token or not secret:
        raise PublicBudgetError("公网预算服务缺少配置；当前使用规则降级。")
    try:
        import streamlit as st
        visitor_ip = st.context.ip_address or ""
    except Exception:
        visitor_ip = ""
    client = UpstashRestClient(url, token)
    manager = PublicBudgetManager(client, secret)
    return manager.reserve(visitor_ip=visitor_ip, query=query, call_id=call_id)
