"""Budgeted Qwen intent understanding and dynamic query planning.

This module does not summarize evidence or make research-gap claims. It only
turns a user's interest into editable intent slots and search branches.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from research_compass.exploration import SearchBranch, clean_text
from research_compass.planning import CONCEPTS, GOALS, ResearchIntent, normalize_concepts, normalize_domain, parse_intent


INPUT_PRICE_CNY_PER_M = 0.8
OUTPUT_PRICE_CNY_PER_M = 2.7
MAX_CALLS = 5
MAX_INPUT_TOKENS = 4_500
MAX_OUTPUT_TOKENS = 1_800
MAX_RUN_COST_CNY = 0.10  # Conservative: CNY 0.10 is below USD 0.10.
LEDGER = Path(__file__).resolve().parents[1] / "evaluation" / "runs" / "v3_20261014" / "qwen_ledger.json"


class QwenPlanningError(RuntimeError):
    """A safe-to-display Qwen planning failure (never includes the API key)."""


class _RejectCredentialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _estimate_max_cost_cny() -> float:
    return (MAX_INPUT_TOKENS * INPUT_PRICE_CNY_PER_M + MAX_OUTPUT_TOKENS * OUTPUT_PRICE_CNY_PER_M) / 1_000_000


def _validated_base_url(value: str) -> str:
    """Keep the paid API key on a documented DashScope endpoint."""
    url = value.strip().rstrip("/")
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in {
        "dashscope.aliyuncs.com", "dashscope-intl.aliyuncs.com",
        "dashscope-us.aliyuncs.com",
    } or parts.port not in (None, 443) or parts.username or parts.password
            or parts.path != "/compatible-mode/v1" or parts.query or parts.fragment):
        raise QwenPlanningError("DASHSCOPE_BASE_URL 不是已核验的百炼 HTTPS 地址；未发送请求。")
    return url


def _ledger_read() -> dict:
    if not LEDGER.exists():
        return {"attempts": 0, "estimated_reserved_cny": 0.0, "calls": []}
    try:
        obj = json.loads(LEDGER.read_text(encoding="utf-8"))
        if not isinstance(obj, dict) or not isinstance(obj.get("calls"), list):
            raise ValueError("invalid ledger")
        return obj
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise QwenPlanningError("Qwen 预算记录无法读取；为避免超预算，已停止调用。") from exc


def _ledger_write(value: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(LEDGER)


def _reserve_call(model: str) -> str:
    ledger = _ledger_read()
    reserved = _estimate_max_cost_cny()
    if int(ledger.get("attempts", 0)) >= MAX_CALLS:
        raise QwenPlanningError("本轮 Qwen API 调用次数已达 5 次上限。")
    spent = float(ledger.get("estimated_reserved_cny", 0.0))
    if spent + reserved > MAX_RUN_COST_CNY:
        raise QwenPlanningError("本轮 Qwen 预算上限将被超过；已停止调用。")
    call_id = f"qwen-{int(ledger.get('attempts', 0)) + 1:02d}"
    ledger["attempts"] = int(ledger.get("attempts", 0)) + 1
    ledger["estimated_reserved_cny"] = round(spent + reserved, 8)
    ledger["calls"].append({
        "call_id": call_id, "model": model, "status": "reserved",
        "max_input_tokens": MAX_INPUT_TOKENS, "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_cost_cny": round(reserved, 8), "actual_input_tokens": None,
        "actual_output_tokens": None, "actual_cost_cny": None,
    })
    _ledger_write(ledger)
    return call_id


def _record_usage(call_id: str, *, status: str, usage: dict | None = None, error_type: str | None = None, latency_ms: float | None = None) -> dict:
    ledger = _ledger_read()
    entry = next((item for item in ledger["calls"] if item["call_id"] == call_id), None)
    if entry is None:
        raise QwenPlanningError("Qwen 预算记录丢失；为避免重复扣费风险，已停止调用。")
    input_tokens = int((usage or {}).get("prompt_tokens", 0) or 0)
    output_tokens = int((usage or {}).get("completion_tokens", 0) or 0)
    actual = (input_tokens * INPUT_PRICE_CNY_PER_M + output_tokens * OUTPUT_PRICE_CNY_PER_M) / 1_000_000
    entry.update({
        "status": status, "actual_input_tokens": input_tokens if usage else None,
        "actual_output_tokens": output_tokens if usage else None,
        "actual_cost_cny": round(actual, 8) if usage else None,
        "error_type": error_type,
        "latency_ms": latency_ms,
    })
    # An attempt with unknown usage retains its full reservation; successful
    # attempts replace the reservation with the API-reported actual bill.
    if usage:
        ledger["estimated_reserved_cny"] = round(
            max(0.0, float(ledger.get("estimated_reserved_cny", 0.0)) - float(entry["max_cost_cny"])) + actual,
            8,
        )
    _ledger_write(ledger)
    return entry


def _extract_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I)
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("model response must be a JSON object")
    return value


def _string(value, *, limit: int = 240) -> str:
    return clean_text(value)[:limit] if isinstance(value, str) else ""


def _items(value, *, max_items: int = 8) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict.fromkeys(clean_text(item)[:240] for item in value if isinstance(item, str) and clean_text(item)))[:max_items]


def validate_plan(interest: str, data: dict, *, goal: str | None = None, clarified_constraints: str = "") -> tuple[ResearchIntent, list[SearchBranch]]:
    """Validate model output, reject invented constraints, and create safe types."""
    raw = data.get("intent") if isinstance(data.get("intent"), dict) else data
    concepts = _items(raw.get("concepts"), max_items=8)
    # A model may suggest adjacent methods; do not promote them to the user's
    # confirmed research objects or hard relevance requirements.
    grounded_concepts = normalize_concepts(interest)
    concepts = tuple(item for item in concepts if item in grounded_concepts)
    if not concepts:
        concepts = grounded_concepts
    if not concepts:
        # Let language-specific entity strings through only if echoed from user text.
        concepts = tuple(name for name in known_concepts if name.casefold() in interest.casefold())
    source = _string(raw.get("source_method"))
    target = _string(raw.get("target_method"))
    if source not in concepts:
        source = ""
    if target not in concepts:
        target = ""
    domain = _string(raw.get("domain"))
    domain = normalize_domain(domain) or normalize_domain(interest) or domain
    explicit_raw = _items(raw.get("explicit_constraints"))
    # Constraint strings must be traceable to the user's original words.
    explicit = tuple(item for item in explicit_raw if item.casefold() in interest.casefold())
    if clarified_constraints.strip():
        explicit += (clean_text(clarified_constraints),)
    relation_type = _string(raw.get("relationship_type"), limit=40).lower()
    relation = f"{source} → {target}" if source and target and relation_type in {"comparison", "transfer", "comparison_transfer"} else ""
    task = _string(raw.get("task")) or ("方法比较与研究思路迁移" if relation_type == "comparison_transfer" else "探索研究版图")
    allowed_goals = set(GOALS)
    normalized_goal = goal if goal in allowed_goals else _string(raw.get("goal"), limit=40)
    if normalized_goal not in allowed_goals:
        normalized_goal = "transfer" if relation_type in {"transfer", "comparison_transfer"} else "methods" if relation_type == "comparison" else "map"
    inferred = _items(raw.get("inferred"))
    unconfirmed = _items(raw.get("unconfirmed"))
    provenance = {
        "domain": "Qwen 推断；需用户确认" if domain else "未识别",
        "concepts": "从原文规范化；需用户确认" if concepts else "未识别",
        "source_method_role": "Qwen 根据上下文识别；需用户确认" if source else "未确认",
        "target_method_role": "Qwen 根据上下文识别；需用户确认" if target else "未确认",
        "task": "Qwen 理解；需用户确认",
        "relationship_direction": "Qwen 理解；需用户确认" if relation else "未确认",
        "constraints": "用户明确表达" if explicit else "未明确提出",
        "goal": "用户在澄清中确认" if goal else "Qwen 推断；需用户确认",
    }
    intent = ResearchIntent(
        original_interest=clean_text(interest), theme=domain or ", ".join(concepts) or clean_text(interest),
        approach=", ".join(concepts), goal=normalized_goal, constraints="; ".join(explicit),
        domain=domain, source_method=source, target_method=target, task=task,
        relationship=relation, explicit_constraints=explicit, inferred=inferred,
        unconfirmed=unconfirmed, concepts=concepts, field_provenance=provenance,
        parser_version="qwen_intent_v1",
    )
    raw_branches = data.get("branches", [])
    branches: list[SearchBranch] = []
    if isinstance(raw_branches, list):
        for index, item in enumerate(raw_branches[:5]):
            if not isinstance(item, dict):
                continue
            query = _string(item.get("query"), limit=360)
            key = re.sub(r"[^a-z0-9_]+", "_", _string(item.get("key"), limit=60).lower()).strip("_") or f"qwen_branch_{index + 1}"
            title = _string(item.get("title"), limit=100) or f"探索方向 {index + 1}"
            purpose = _string(item.get("purpose"), limit=240)
            methods = tuple(value for value in _items(item.get("required_methods"), max_items=4) if value in concepts)
            focus = _string(item.get("focus_method"), limit=100)
            if focus not in concepts:
                focus = ""
            if query and len(branches) < 3:
                branches.append(SearchBranch(key, title, purpose, query, focus_method=focus, required_methods=methods))
    if not branches:
        raise ValueError("model returned no valid search branches")
    return intent, branches


def plan_with_qwen(interest: str, *, goal: str | None = None, clarified_constraints: str = "") -> tuple[ResearchIntent, list[SearchBranch], dict]:
    """Make one non-retrieval Qwen request; network/HTTP failure is never retried."""
    if len(interest) > 2_000:
        raise QwenPlanningError("研究兴趣过长，未发送至 Qwen（最多 2,000 字符）。")
    public_mode = os.getenv("PUBLIC_DEPLOYMENT", "false").lower() == "true"
    public_reservation = None
    if public_mode:
        from research_compass.public_budget import public_budget_enabled
        if not public_budget_enabled():
            raise QwenPlanningError("公网 Qwen 未启用；当前使用规则降级。")
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise QwenPlanningError("未配置 DASHSCOPE_API_KEY；请检查本地 .env 或 Streamlit Secrets。")
    model = os.getenv("DASHSCOPE_MODEL", "qwen3.8-flash").strip()
    if model != "qwen3.8-flash":
        raise QwenPlanningError("预算保护仅核实了 qwen3.8-flash 的价格；当前配置模型未匹配，已停止付费调用。")
    base_url = _validated_base_url(os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"))

    system = (
        "You are a research-intent parser and academic query planner. Do not answer the research question. "
        "Return only a JSON object with keys intent and branches. Keep the user's explicit constraints empty unless "
        "the user explicitly states them. Separate inferred and unconfirmed fields. Preserve source-to-target direction. "
        "Use canonical English academic names for concepts and domain. Generate 2-4 clearly distinct, concise English "
        "academic search queries grounded in the user's topic; never assert a research gap. Each branch must include key, "
        "title, purpose, query, focus_method, and required_methods. Use relationship_type from comparison, transfer, "
        "comparison_transfer, none. Intent keys: domain, concepts, source_method, target_method, task, "
        "relationship_type, explicit_constraints, inferred, unconfirmed, goal."
    )
    user = json.dumps({
        "interest": clean_text(interest), "clarified_goal": goal or "",
        "clarified_constraints": clean_text(clarified_constraints),
        "allowed_concepts": list(CONCEPTS), "allowed_goals": list(GOALS),
    }, ensure_ascii=False)
    if len(system) + len(user) > MAX_INPUT_TOKENS:
        raise QwenPlanningError("本次请求超过预算保护的输入长度；未发送。")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": MAX_OUTPUT_TOKENS,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "enable_thinking": False,
    }
    encoded_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    from research_compass.public_budget import MAX_REQUEST_BYTES
    if len(encoded_payload) > MAX_REQUEST_BYTES:
        raise QwenPlanningError("本次请求超出公网预算限制的字节上限；未发送。")
    if public_mode:
        # Reserve immediately before network I/O, only after all local checks.
        from research_compass.public_budget import PublicBudgetError, streamlit_reservation
        try:
            public_reservation = streamlit_reservation(interest)
        except PublicBudgetError as exc:
            raise QwenPlanningError(str(exc)) from None
    call_id = public_reservation.call_id if public_reservation else _reserve_call(model)
    public_request_recorded = False
    request = Request(
        f"{base_url}/chat/completions",
        data=encoded_payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        if public_reservation:
            response_context = build_opener(_RejectCredentialRedirect()).open(request, timeout=25)
        else:
            response_context = urlopen(request, timeout=25)
        with response_context as response:
            body = json.loads(response.read().decode("utf-8"))
        usage = body.get("usage") or {}
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        if public_reservation:
            public_reservation.finish(success=True, usage=usage, latency_ms=latency_ms)
            public_request_recorded = True
            from research_compass.public_budget import INPUT_PRICE_CNY_PER_M as PUBLIC_INPUT_RATE, OUTPUT_PRICE_CNY_PER_M as PUBLIC_OUTPUT_RATE
            input_tokens = int(usage.get("prompt_tokens", 0) or 0)
            output_tokens = int(usage.get("completion_tokens", 0) or 0)
            actual_cost = (input_tokens * PUBLIC_INPUT_RATE + output_tokens * PUBLIC_OUTPUT_RATE) / 1_000_000
            entry = {"actual_input_tokens": input_tokens, "actual_output_tokens": output_tokens, "actual_cost_cny": round(actual_cost, 8)}
        else:
            entry = _record_usage(call_id, status="success", usage=usage, latency_ms=latency_ms)
        content = body["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        intent, branches = validate_plan(interest, parsed, goal=goal, clarified_constraints=clarified_constraints)
        metadata = {
            "call_id": call_id, "model": model, "latency_ms": latency_ms,
            "input_tokens": entry["actual_input_tokens"], "output_tokens": entry["actual_output_tokens"],
            "cost_cny": entry["actual_cost_cny"], "status": "success",
            "raw_response": parsed,
        }
        return intent, branches, metadata
    except HTTPError as exc:
        # Do not include the response body (it can contain request or account data).
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        if public_reservation:
            try:
                public_reservation.finish(success=False, usage=None, latency_ms=latency_ms)
            except Exception as ledger_exc:
                from research_compass.public_budget import PublicBudgetError
                if isinstance(ledger_exc, PublicBudgetError):
                    raise QwenPlanningError(str(ledger_exc)) from None
                raise
        else:
            _record_usage(call_id, status="http_error_unknown_usage", error_type=f"HTTP {exc.code}", latency_ms=latency_ms)
        raise QwenPlanningError(f"Qwen 请求失败（HTTP {exc.code}）。没有自动重试。") from None
    except (URLError, TimeoutError, OSError) as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        if public_reservation:
            try:
                public_reservation.unknown_failure(latency_ms=latency_ms)
            except Exception as ledger_exc:
                from research_compass.public_budget import PublicBudgetError
                if isinstance(ledger_exc, PublicBudgetError):
                    raise QwenPlanningError(str(ledger_exc)) from None
                raise
        else:
            _record_usage(call_id, status="network_error_unknown_usage", error_type=type(exc).__name__, latency_ms=latency_ms)
        raise QwenPlanningError("Qwen 网络请求失败。没有自动重试；预算按单次上限预留。") from None
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        # If usage exists the request has already been recorded as success; do not retry malformed output.
        if public_reservation:
            if not public_request_recorded:
                try:
                    public_reservation.finish(success=False, usage=None, latency_ms=round((time.perf_counter() - started) * 1000, 2))
                except Exception:
                    pass  # Keep the durable reservation if finalization fails.
            raise QwenPlanningError("Qwen 返回结构无法验证。没有自动重试。") from None
        current = _ledger_read()
        entry = next(item for item in current["calls"] if item["call_id"] == call_id)
        if entry["status"] == "reserved":
            _record_usage(call_id, status="invalid_response_unknown_usage", error_type=type(exc).__name__, latency_ms=round((time.perf_counter() - started) * 1000, 2))
        raise QwenPlanningError("Qwen 返回结构无法验证。没有自动重试。") from None
    except Exception as exc:
        from research_compass.public_budget import PublicBudgetError
        if isinstance(exc, PublicBudgetError):
            raise QwenPlanningError(str(exc)) from None
        raise


def plan_batch_with_qwen(cases: list[dict]) -> tuple[dict[str, tuple[ResearchIntent, list[SearchBranch]]], dict]:
    """Evaluate up to three inputs with one bounded request and one ledger entry."""
    if os.getenv("PUBLIC_DEPLOYMENT", "false").lower() == "true":
        raise QwenPlanningError("Public batch planning is disabled; use the gated single-request flow.")
    if not 1 <= len(cases) <= 3:
        raise QwenPlanningError("批量评测一次仅允许 1 到 3 个案例。")
    if any(len(str(case.get("interest", ""))) > 2_000 for case in cases):
        raise QwenPlanningError("至少一个案例超过 2,000 字符，未发送。")
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise QwenPlanningError("未配置 DASHSCOPE_API_KEY。")
    model = os.getenv("DASHSCOPE_MODEL", "qwen3.8-flash").strip()
    if model != "qwen3.8-flash":
        raise QwenPlanningError("当前模型价格未进入本轮预算保护白名单，已停止付费调用。")
    base_url = _validated_base_url(os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
    system = (
        "You parse research intent and plan academic searches. Return only JSON with a plans array. "
        "For each case, include case_id, intent, branches. Never answer the research question or claim a gap. "
        "Keep explicit_constraints empty unless directly stated in that case's interest. Preserve source-to-target direction. "
        "Use canonical English academic names where possible. Generate 2-4 distinct English academic queries grounded in each input. "
        "Each intent has domain, concepts, source_method, target_method, task, relationship_type, explicit_constraints, inferred, unconfirmed, goal. "
        "Each branch has key, title, purpose, query, focus_method, required_methods. relationship_type is one of comparison, transfer, comparison_transfer, none."
    )
    user = json.dumps({"cases": cases, "allowed_concepts": list(CONCEPTS), "allowed_goals": list(GOALS)}, ensure_ascii=False)
    if len(system) + len(user) > MAX_INPUT_TOKENS:
        raise QwenPlanningError("批量请求超过预算保护的输入长度，未发送。")
    call_id = _reserve_call(model)
    payload = {
        "model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": MAX_OUTPUT_TOKENS, "temperature": 0.1,
        "response_format": {"type": "json_object"}, "enable_thinking": False,
    }
    request = Request(
        f"{base_url}/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
        usage = body.get("usage") or {}
        entry = _record_usage(call_id, status="success", usage=usage)
        result = _extract_json(body["choices"][0]["message"]["content"])
        raw_plans = result.get("plans")
        if not isinstance(raw_plans, list):
            raise ValueError("missing plans")
        inputs = {str(case["case_id"]): case for case in cases}
        plans = {}
        for plan in raw_plans:
            if not isinstance(plan, dict) or str(plan.get("case_id")) not in inputs:
                continue
            case = inputs[str(plan["case_id"])]
            plans[str(plan["case_id"])] = validate_plan(
                str(case["interest"]), plan, goal=case.get("goal"),
                clarified_constraints=str(case.get("clarified_constraints", "")),
            )
        metadata = {
            "call_id": call_id, "model": model, "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "input_tokens": entry["actual_input_tokens"], "output_tokens": entry["actual_output_tokens"],
            "cost_cny": entry["actual_cost_cny"], "status": "success", "raw_response": result,
        }
        return plans, metadata
    except HTTPError as exc:
        _record_usage(call_id, status="http_error_unknown_usage", error_type=f"HTTP {exc.code}")
        raise QwenPlanningError(f"Qwen 请求失败（HTTP {exc.code}）。没有自动重试。") from None
    except (URLError, TimeoutError, OSError) as exc:
        _record_usage(call_id, status="network_error_unknown_usage", error_type=type(exc).__name__)
        raise QwenPlanningError("Qwen 网络请求失败；没有自动重试，预算按单次上限预留。") from None
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        current = _ledger_read()
        entry = next(item for item in current["calls"] if item["call_id"] == call_id)
        if entry["status"] == "reserved":
            _record_usage(call_id, status="invalid_response_unknown_usage", error_type=type(exc).__name__)
        raise QwenPlanningError("Qwen 批量响应无法验证。没有自动重试。") from None
