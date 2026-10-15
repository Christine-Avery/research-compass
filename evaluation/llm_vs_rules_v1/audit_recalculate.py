"""Independent, read-only recalculation from paired_runs.jsonl and relevance_labels.csv."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent


def read_inputs():
    query_document = json.loads((ROOT / "test_queries.json").read_text(encoding="utf-8"))
    queries = query_document["cases"]
    runs = [json.loads(line) for line in (ROOT / "paired_runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    with (ROOT / "relevance_labels.csv").open(encoding="utf-8-sig", newline="") as f:
        labels = list(csv.DictReader(f))
    return queries, runs, labels


def is_complete(group):
    return (group.get("request_status") == "live" and group.get("retrieval_mode") == "live"
            and isinstance(group.get("selected_path"), dict) and len(group.get("top5", [])) == 5)


def score(grades):
    p5 = sum(g >= 1 for g in grades) / 5
    gains = [2**g - 1 for g in grades]
    dcg = sum(g / math.log2(rank + 2) for rank, g in enumerate(gains))
    ideal = sorted(grades, reverse=True)[:5]
    idcg = sum((2**g - 1) / math.log2(rank + 2) for rank, g in enumerate(ideal))
    return {"grades": grades, "precision_at_5": p5, "dcg": dcg, "idcg": idcg,
            "ndcg_at_5": dcg / idcg if idcg else 0.0}


def calculate():
    queries, runs, labels = read_inputs()
    query_ids = [q["query_id"] for q in queries]
    labels_by_key = {(r["query_id"], r["paper_id"]): int(r["score_0_1_2"]) for r in labels}
    label_duplicates = Counter((r["query_id"], r["paper_id"]) for r in labels)
    run_by_id = {r["query_id"]: r for r in runs}
    per_query, group_scores = {}, {"A": [], "B": []}
    complete_ids = {g: [] for g in ("A", "B")}
    absent_labels, top5_dupes, id_mismatches, request_mismatches = [], [], [], []
    label_values = Counter(int(r["score_0_1_2"]) for r in labels)
    for qid in query_ids:
        run = run_by_id[qid]
        per_query[qid] = {"category": run["category"]}
        for g in ("A", "B"):
            block = run[g]
            complete = is_complete(block)
            ids = [p.get("paper_id") for p in block.get("top5", [])]
            if len(ids) != len(set(ids)):
                top5_dupes.append({"query_id": qid, "group": g, "ids": ids})
            if complete:
                complete_ids[g].append(qid)
                grades = []
                returned = {pid for req in block.get("openalex_queries", []) for pid in req.get("returned_ids_in_api_order", [])}
                for pid in ids:
                    if pid not in returned:
                        id_mismatches.append({"query_id": qid, "group": g, "paper_id": pid, "reason": "top5 id absent from actual request returned IDs"})
                    key = (qid, pid)
                    if key not in labels_by_key:
                        absent_labels.append({"query_id": qid, "group": g, "paper_id": pid})
                        grades.append(0)
                    else:
                        grades.append(labels_by_key[key])
                s = score(grades)
                group_scores[g].append(s)
                per_query[qid][g] = {"eligible": True, **s}
            else:
                per_query[qid][g] = {"eligible": False, "request_status": block.get("request_status"),
                                     "retrieval_mode": block.get("retrieval_mode"),
                                     "selected_path": block.get("selected_path"), "error": block.get("error")}
        if per_query[qid]["A"]["eligible"] and per_query[qid]["B"]["eligible"]:
            per_query[qid]["delta_precision_at_5"] = per_query[qid]["B"]["precision_at_5"] - per_query[qid]["A"]["precision_at_5"]
            per_query[qid]["delta_ndcg_at_5"] = per_query[qid]["B"]["ndcg_at_5"] - per_query[qid]["A"]["ndcg_at_5"]

    pairs = sorted(set(complete_ids["A"]) & set(complete_ids["B"]))
    def aggregate(ids, g):
        vals = [per_query[q][g] for q in ids]
        return {"n": len(vals), "mean_precision_at_5": mean(v["precision_at_5"] for v in vals) if vals else None,
                "mean_ndcg_at_5": mean(v["ndcg_at_5"] for v in vals) if vals else None}
    cats = {}
    for cat in ("S1", "S2", "S3", "S4"):
        ids = [q for q in pairs if per_query[q]["category"] == cat]
        cats[cat] = {"n_complete_pairs": len(ids), "A": aggregate(ids, "A"), "B": aggregate(ids, "B")}
    direction_rows = []
    for run in runs:
        exp = run.get("frozen_expectations", {})
        if not exp.get("relationship_type"):
            continue
        raw_intent = (run.get("B", {}).get("qwen", {}).get("raw_response") or {}).get("intent", {}) or {}
        parsed = run.get("B", {}).get("intent", {}) or {}
        direction_rows.append({"query_id": run["query_id"], "expected_source": exp.get("source_method"),
                               "expected_target": exp.get("target_method"),
                               "raw_source": raw_intent.get("source_method"), "raw_target": raw_intent.get("target_method"),
                               "raw_relationship": raw_intent.get("relationship_type"),
                               "parsed_source": parsed.get("source_method"), "parsed_target": parsed.get("target_method"),
                               "parsed_relationship": parsed.get("relationship"),
                               "qwen_error": run.get("B", {}).get("error"),
                               "raw_direction_present": bool(raw_intent.get("source_method") or raw_intent.get("target_method") or raw_intent.get("relationship_type"))})
    report = {
        "frozen_set": {"n": len(queries), "unique_ids": len(set(query_ids)), "run_rows": len(runs),
                       "run_unique_ids": len(run_by_id), "query_ids_missing_runs": sorted(set(query_ids)-set(run_by_id)),
                       "run_ids_not_in_queries": sorted(set(run_by_id)-set(query_ids)),
                       "sha256": hashlib.sha256((ROOT / "test_queries.json").read_bytes()).hexdigest()},
        "labels": {"rows": len(labels), "unique_query_paper_pairs": len(label_duplicates),
                   "duplicate_query_paper_keys": sum(n > 1 for n in label_duplicates.values()),
                   "grade_counts": dict(sorted(label_values.items())), "missing_top5_labels": absent_labels,
                   "human_review_status_counts": dict(Counter(r["human_review_status"] for r in labels)),
                   "label_status_counts": dict(Counter(r["label_status"] for r in labels)),
                   "ai_assisted_counts": dict(Counter(r["ai_assisted"] for r in labels))},
        "coverage": {"A_complete_ids": sorted(complete_ids["A"]), "B_complete_ids": sorted(complete_ids["B"]),
                     "A_only": sorted(set(complete_ids["A"])-set(pairs)), "B_only": sorted(set(complete_ids["B"])-set(pairs)),
                     "paired_ids": pairs, "paired_n": len(pairs), "unpaired_ids": sorted(set(query_ids)-set(pairs)),
                     "S4_paired_n": cats["S4"]["n_complete_pairs"]},
        "metrics": {"A": aggregate(pairs, "A"), "B": aggregate(pairs, "B"),
                    "delta_precision_at_5": aggregate(pairs, "B")["mean_precision_at_5"]-aggregate(pairs, "A")["mean_precision_at_5"] if pairs else None,
                    "delta_ndcg_at_5": aggregate(pairs, "B")["mean_ndcg_at_5"]-aggregate(pairs, "A")["mean_ndcg_at_5"] if pairs else None,
                    "wins_precision": {"Qwen": sum(per_query[q]["delta_precision_at_5"] > 1e-12 for q in pairs),
                                       "Rules": sum(per_query[q]["delta_precision_at_5"] < -1e-12 for q in pairs),
                                       "tie": sum(abs(per_query[q]["delta_precision_at_5"]) <= 1e-12 for q in pairs)},
                    "wins_ndcg": {"Qwen": sum(per_query[q]["delta_ndcg_at_5"] > 1e-12 for q in pairs),
                                  "Rules": sum(per_query[q]["delta_ndcg_at_5"] < -1e-12 for q in pairs),
                                  "tie": sum(abs(per_query[q]["delta_ndcg_at_5"]) <= 1e-12 for q in pairs)},
                    "by_category": cats, "per_query": per_query},
        "integrity": {"duplicate_top5_ids": top5_dupes, "missing_labels_for_top5": absent_labels,
                       "top5_id_request_mismatches": id_mismatches},
        "qwen_direction_audit": direction_rows,
    }
    prior = json.loads((ROOT / "metrics.json").read_text(encoding="utf-8"))
    ledger = json.loads((ROOT / "qwen_experiment_ledger.json").read_text(encoding="utf-8"))
    run_manifest = json.loads((ROOT / "run_manifest.json").read_text(encoding="utf-8"))
    def near(left, right):
        return left is not None and right is not None and abs(left-right) <= 1e-12
    old = prior["precision_ndcg"]
    checks = {
        "A_n": report["metrics"]["A"]["n"] == old["A_rules_v1"]["n"],
        "B_n": report["metrics"]["B"]["n"] == old["B_qwen_v2"]["n"],
        "A_mean_P@5": near(report["metrics"]["A"]["mean_precision_at_5"], old["A_rules_v1"]["mean_precision_at_5"]),
        "B_mean_P@5": near(report["metrics"]["B"]["mean_precision_at_5"], old["B_qwen_v2"]["mean_precision_at_5"]),
        "A_mean_nDCG@5": near(report["metrics"]["A"]["mean_ndcg_at_5"], old["A_rules_v1"]["mean_ndcg_at_5"]),
        "B_mean_nDCG@5": near(report["metrics"]["B"]["mean_ndcg_at_5"], old["B_qwen_v2"]["mean_ndcg_at_5"]),
        "delta_P@5": near(report["metrics"]["delta_precision_at_5"], old["delta_B_minus_A"]["precision_at_5"]),
        "delta_nDCG@5": near(report["metrics"]["delta_ndcg_at_5"], old["delta_B_minus_A"]["ndcg_at_5"]),
        "paired_n": report["coverage"]["paired_n"] == old["paired_n"],
        "P@5_wins": report["metrics"]["wins_precision"] == old["paired_wins_by_precision"],
        "nDCG@5_wins": report["metrics"]["wins_ndcg"] == old["paired_wins_by_ndcg"],
    }
    report["metrics_consistency"] = {"checks": checks, "all_passed": all(checks.values()),
                                     "source": "Independent calculations from paired_runs.jsonl and relevance_labels.csv compared with prior metrics.json; prior file not overwritten."}
    file_hash_checks = {}
    for name, expected_hash in run_manifest.get("evaluation_outputs_sha256", {}).items():
        file_hash_checks[name] = (hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected_hash
                                  if (ROOT / name).exists() else None)
    mutable_report_names = {"RESULTS.md"}
    raw_hash_checks = {name: ok for name, ok in file_hash_checks.items()
                       if name not in mutable_report_names and ok is not None}
    report["provenance_audit"] = {
        "qwen_ledger_attempts": len(ledger.get("calls", [])),
        "qwen_ledger_status_counts": dict(Counter(c.get("status", "unknown") for c in ledger.get("calls", []))),
        "qwen_calls_with_unknown_usage": sum(c.get("actual_input_tokens") is None or c.get("actual_output_tokens") is None for c in ledger.get("calls", [])),
        "automatic_retries": sum(int(c.get("attempt", 1)) > 1 for c in ledger.get("calls", [])),
        "historic_ledger_hash_before_after_equal": run_manifest.get("historic_qwen_ledger_sha256_before") == run_manifest.get("historic_qwen_ledger_sha256_after"),
        "recorded_output_hash_checks": file_hash_checks,
        "manifest_outputs_not_in_this_archive": sorted(name for name, ok in file_hash_checks.items() if ok is None),
        "raw_artifact_hash_checks": raw_hash_checks,
        "all_unchanged_raw_artifact_hashes_match": all(raw_hash_checks.values()),
        "known_hash_exception": "RESULTS.md was intentionally rewritten during this archive round; the historic manifest records its prior version hash and was left unchanged.",
    }
    return report


def main():
    report = calculate()
    out = ROOT / "audit_recalculation.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "frozen_set": report["frozen_set"], "labels": report["labels"],
                      "coverage": report["coverage"], "metrics": {k:v for k,v in report["metrics"].items() if k != "per_query"},
                      "integrity": report["integrity"], "qwen_direction_audit": report["qwen_direction_audit"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
