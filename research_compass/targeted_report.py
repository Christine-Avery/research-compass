"""Reproducible, label-driven report for the seven-record targeted review."""

from __future__ import annotations

import json
from pathlib import Path

from research_compass.human_eval import parse_relevance, parse_yes_no
from research_compass.targeted_review import candidates, gate_metrics, load_reviewed, snapshot_rows


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2%}"


def _four(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def _delta(before: float | None, after: float | None) -> str:
    return "N/A" if before is None or after is None else f"{after - before:+.4f}"


def build(snapshot_path: Path, events_dir: Path) -> tuple[str, dict]:
    original = snapshot_rows(snapshot_path)
    revised, reviewed = load_reviewed(snapshot_path, events_dir)
    selected = candidates(original)
    initial = gate_metrics(original)
    current = gate_metrics(revised)
    complete = len(reviewed & {rid for rid, _ in selected}) == len(selected) and current["evidence_missing"] == 0
    original_by_id = {row["review_id"]: row for row in original}
    changed = []
    for row in revised:
        before = original_by_id[row["review_id"]]
        if any(row.get(field, "") != before.get(field, "") for field in ("human_relevance_label", "human_evidence_eligible_label")):
            changed.append({
                "review_id": row["review_id"], "branch": row["branch"], "raw_rank": row["raw_rank"],
                "paper_id": row["paper_id"], "title": row["title"],
                "relevance_before": before.get("human_relevance_label", ""),
                "relevance_after": row.get("human_relevance_label", ""),
                "evidence_before": before.get("human_evidence_eligible_label", ""),
                "evidence_after": row.get("human_evidence_eligible_label", ""),
            })
    events = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(events_dir.glob("*.json"))] if events_dir.exists() else []
    relevant_misses = [
        row for row in revised
        if row["version"] == "V1_Optimized_Rules"
        and row["rule_status"] != "Evidence Eligible"
        and parse_relevance(row.get("human_relevance_label")) in (1, 2)
        and parse_yes_no(row.get("human_evidence_eligible_label")) is True
    ]
    inconsistent = [
        row for row in revised
        if row["version"] == "V1_Optimized_Rules"
        and parse_relevance(row.get("human_relevance_label")) == 0
        and parse_yes_no(row.get("human_evidence_eligible_label")) is True
    ]
    lines = [
        "# Research Compass：定向标注复核报告",
        "",
        f"**状态：{'最终版：7 条均经人工复核，准入标签已填满' if complete else '待人工复核完成：以下修正版指标为阶段性结果'}。**",
        "",
        "原始 `human_labels.csv` 保持只读；人工复核事件另存，首次保存时建立 `human_labels_reviewed.csv`。未复核条目沿用历史值，缺失准入不补填。原始检索 Trace 和系统 `rule_status` 均未改变。",
        "",
        f"定向条目：已复核 {len(reviewed & {rid for rid, _ in selected})}/{len(selected)}；V1 人工准入已填 {current['evidence_judged']}/{current['v1_rows']}。全部 35 条相关性均已标注；V0 的 20 条不在本轮复核范围。",
        "",
        "## 指标定义与分母",
        "",
        "- 相关性 ≥1 算命中。Precision@5 分母为每分支前 5 条；版本结果是完整标注分支的宏平均。V0 为 4 分支 / 20 条，V1 为 3 分支 / 15 条。",
        "- nDCG@5 使用人工等级 0/1/2 对应增益 0/1/3，按原始排名计算，每分支以该分支前 5 条的理想排序归一化，再对分支宏平均。",
        "- 无关证据率 = 系统 `Evidence Eligible` 中人工相关性为 0 的条数 / 系统准入且已标相关性的条数。V0 没有 Evidence Gate，记 N/A。",
        "- Gate TP/FP/FN/TN 只纳入已填人工准入 yes/no 的 V1 记录。Precision = TP/(TP+FP)，Recall = TP/(TP+FN)；分母为 0 时 N/A。误收录 = FP，误拒绝 = FN。未填准入排除而不视为 no。",
        "- 评测负样本保留在检索评测集中，用于衡量排除能力；它并不因此适合进入 Evidence Generation。相关性和摘要支持性分别人工判断。",
        "",
        "## V0 / V1 修正版结果",
        "",
        "| 方案 | Precision@5 | nDCG@5 | 无关证据率 | 误收录 FP | 误拒绝 FN | Gate Precision | Gate Recall |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, result in (("V0 历史", current["v0"]), ("V1 修正版", current["v1"])):
        if name.startswith("V0"):
            lines.append(f"| {name} | {_four(result['precision_at_k'])} (1/20) | {_four(result['ndcg_at_k'])} (4 分支) | N/A | N/A | N/A | N/A | N/A |")
        else:
            relevant_hits = sum(parse_relevance(row.get("human_relevance_label")) in (1, 2) for row in revised if row["version"] == "V1_Optimized_Rules")
            lines.append(
                f"| {name} | {_four(result['precision_at_k'])} ({relevant_hits}/15) | {_four(result['ndcg_at_k'])} (3 分支) | "
                f"{result['irrelevant_evidence_numerator']}/{result['irrelevant_evidence_denominator']} "
                f"({_pct(result['irrelevant_evidence_rate'])}) | {current['fp']} | {current['fn']} | "
                f"{current['tp']}/{current['precision_denominator']} ({_pct(current['precision'])}) | "
                f"{current['tp']}/{current['recall_denominator']} ({_pct(current['recall'])}) |"
            )
    lines += [
        "",
        f"V1 Gate 混淆计数：TP={current['tp']}、FP={current['fp']}、FN={current['fn']}、TN={current['tn']}；分母为 {current['evidence_judged']} 条已填人工准入的 V1 记录。",
        "",
        "## 标签修正造成的变化（历史 → 修正）",
        "",
        "| 指标 | 历史 | 修正 | 变化 |",
        "| --- | ---: | ---: | ---: |",
        f"| V1 Precision@5 | {_four(initial['v1']['precision_at_k'])} | {_four(current['v1']['precision_at_k'])} | {_delta(initial['v1']['precision_at_k'], current['v1']['precision_at_k'])} |",
        f"| V1 nDCG@5 | {_four(initial['v1']['ndcg_at_k'])} | {_four(current['v1']['ndcg_at_k'])} | {_delta(initial['v1']['ndcg_at_k'], current['v1']['ndcg_at_k'])} |",
        f"| V1 无关证据率 | {initial['v1']['irrelevant_evidence_numerator']}/{initial['v1']['irrelevant_evidence_denominator']} | {current['v1']['irrelevant_evidence_numerator']}/{current['v1']['irrelevant_evidence_denominator']} | {_delta(initial['v1']['irrelevant_evidence_rate'], current['v1']['irrelevant_evidence_rate'])} |",
        f"| V1 误收录 FP | {initial['fp']} | {current['fp']} | {current['fp'] - initial['fp']:+d} |",
        f"| V1 误拒绝 FN | {initial['fn']} | {current['fn']} | {current['fn'] - initial['fn']:+d} |",
        f"| V1 Gate Precision | {initial['tp']}/{initial['precision_denominator']} ({_pct(initial['precision'])}) | {current['tp']}/{current['precision_denominator']} ({_pct(current['precision'])}) | {_delta(initial['precision'], current['precision'])} |",
        f"| V1 Gate Recall | {initial['tp']}/{initial['recall_denominator']} ({_pct(initial['recall'])}) | {current['tp']}/{current['recall_denominator']} ({_pct(current['recall'])}) | {_delta(initial['recall'], current['recall'])} |",
        "",
        "历史准入缺 1 条，因此历史 Gate 指标使用 14/15 条；修正列按当前已填数量计算，若仍缺失同样属于阶段性数值。V0 排名标签未修正，V0 指标无变化。",
        "",
        "### 实际改动的人工标签",
        "",
    ]
    if changed:
        lines += ["| 论文 / 分支 / 排名 | 相关性 | 证据准入 |", "| --- | --- | --- |"]
        for item in changed:
            lines.append(
                f"| [{item['title']}]({item['paper_id']}) · {item['branch']} #{item['raw_rank']} | "
                f"{item['relevance_before'] or '空'} → {item['relevance_after'] or '空'} | "
                f"{item['evidence_before'] or '空'} → {item['evidence_after'] or '空'} |"
            )
    else:
        lines.append("尚无标签值变更。人工确认但未修改的复核事件仍保留在 `changes/`。")
    lines += ["", "### 复核事件（含原因和 UTC 时间）", ""]
    if events:
        for event in events:
            lines.append(
                f"- {event['timestamp_utc']} · [{event['paper_id']}]({event['paper_id']}) · "
                f"相关性 {event['before']['human_relevance_label'] or '空'} → {event['after']['human_relevance_label'] or '空'}；"
                f"准入 {event['before']['human_evidence_eligible_label'] or '空'} → {event['after']['human_evidence_eligible_label'] or '空'}；"
                f"原因：{event['change_reason']}"
            )
    else:
        lines.append("尚无人为保存的复核事件。")
    lines += ["", "## 仍被 Gate 拒绝、但人工标为应准入的论文", ""]
    if relevant_misses:
        for row in relevant_misses:
            scope = "目标领域直接漏收候选" if row["branch"] == "target_method" else "跨领域 / 迁移边界判断，须复核证据用途"
            lines.append(
                f"- [{row['title']}]({row['paper_id']})：{row['branch']} #{row['raw_rank']}，"
                f"人工相关性 {row['human_relevance_label']}，系统 {row['rule_status']}；{scope}。"
                f" 人工理由：{row.get('evidence_reason') or '未填写'}。"
            )
    else:
        lines.append("当前修正标签下无相关且人工准入、但系统拒绝的 V1 论文。")
    lines += [
        "",
        "其中 `target_method` 两篇 GP 控制论文的摘要直接涉及 GP 与控制，是优先修复的 Gate 漏收。"
        "`comparison_transfer` 中的 NLP 论文虽被人工改为相关性 2、准入 yes，但复核理由指出仅与神经网络有关、未考虑控制理论场景；"
        "它计入上表正式指标中的 FN，同时应单独核对是否真能支持本研究问题，不据此放宽 Gate。",
    ]
    if inconsistent:
        lines += ["", f"尚有 {len(inconsistent)} 条 V1 ‘相关性 0 / 准入是’组合，需确认是否有特殊证据用途；不自动更正。"]
    lines += [
        "",
        "## 修复判断",
        "",
        "优先修 Evidence Gate：目标方法分支中已检出的两篇 GP 控制论文仍被拒绝，应先改控制领域术语及准入判断，并用冻结快照检查误收录。其次改 Query Planning：`comparison_transfer` 分支需减少偏离 NN→GP 控制研究目标的结果，并区分跨领域启发与直接证据。NLP 论文的人工评分与理由需单独复核，不能当作改宽 Gate 的依据。该顺序只依据当前单案例，不推断总体效果。",
        "",
        "复现：在项目根目录运行 `.\\.venv\\Scripts\\python.exe evaluation\\build_targeted_report.py`。脚本仅读取历史标签和人工复核事件，重建修正版 CSV 与报告，不调用 Qwen/OpenAlex。",
        "",
    ]
    machine = {
        "status": "final" if complete else "pending_human_review",
        "candidate_count": len(selected), "reviewed_candidate_count": len(reviewed & {rid for rid, _ in selected}),
        "event_count": len(events), "changed_labels": changed,
        "original": initial, "corrected": current,
        "remaining_relevant_gate_misses": [
            {key: row[key] for key in ("review_id", "branch", "raw_rank", "paper_id", "title", "human_relevance_label")}
            for row in relevant_misses
        ],
        "remaining_direct_target_method_misses": [row["review_id"] for row in relevant_misses if row["branch"] == "target_method"],
        "remaining_transfer_branch_judgments": [row["review_id"] for row in relevant_misses if row["branch"] == "comparison_transfer"],
        "remaining_v1_relevance_evidence_conflicts": [row["review_id"] for row in inconsistent],
    }
    return "\n".join(lines), machine


def write_report(snapshot_path: Path, output_dir: Path) -> dict:
    report, metrics = build(snapshot_path, output_dir / "changes")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metrics
