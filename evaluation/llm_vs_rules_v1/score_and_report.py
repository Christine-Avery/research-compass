"""Create blinded provisional labels, paired metrics, chart, and reports."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = {x["query_id"]: x for x in json.loads((HERE / "test_queries.json").read_text(encoding="utf-8"))["cases"]}
RUNS = [json.loads(line) for line in (HERE / "paired_runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

# Query-specific signals are derived from the frozen task. The scoring rubric
# is 0=off-task, 1=partial domain/method match, 2=direct task/method match.
SIGNALS = {
 "S1-01": (r"control|controller", r"reinforcement learning|actor.?critic|\brl\b", r"adaptive control|nonlinear control|nonlinear systems|stability|performance evaluation"),
 "S1-02": (r"natural language|\bnlp\b|text", r"transformer", r"summari[sz]|long.?document|long.?text|sparse attention"),
 "S1-03": (r"medical image|medical imaging", r"convolutional neural|\bcnn\b", r"segmentation|lesion|boundary|hausdorff"),
 "S1-04": (r"material|materials", r"gaussian process|\bgp\b|bayesian optimization", r"uncertaint|experimental design|experiment|active learning|sampling"),
 "S2-01": (r"robot|control", r"reinforcement learning|\brl\b", r"safe|safety|exploration|model predictive|\bmpc\b"),
 "S2-02": (r"medical image|medical imaging", r"transformer|convolutional neural|\bcnn\b", r"segmentation|few.?shot|feature fusion|attention"),
 "S2-03": (r"material|catal|battery|materials discovery", r"gaussian process|\bgp\b|reinforcement learning|\brl\b|bayesian optimization", r"transfer|experimental design|materials discovery|optimization"),
 "S2-04": (r"natural language|\bnlp\b|text|vision", r"convolution|\bcnn\b|transformer|inductive bias", r"classification|long.?text|long.?sequence|inductive bias|local context"),
 "S3-01": (r"robot", r"reinforcement learning|\brl\b|learning|model predictive", r"control|stabili[sz]|robust|locomotion|manipulation"),
 "S3-02": (r"medical image|medical imaging", r"segmentation", r"semi.?supervised|limited label|few.?shot|uncertaint|confidence|calibration"),
 "S3-03": (r"control", r"model predictive control|\bmpc\b", r"accelerat|real.?time|computational cost|computation|fast inference"),
 "S3-04": (r"material|materials discovery", r"gaussian process|\bgp\b|bayesian optimization", r"experiment|experimental design|active learning|screening|discovery"),
 "S4-01": (r"acoustic metamaterial|wind turbine|wind energy|marine structure", r"local resonance|noise control|metamaterial", r"wave load|robust|offshore|structural design"),
 "S4-02": (r"salt lake|microb|archaea|geomorph|mineral", r"microbiome|metabolic|spatial", r"mineral texture|geomorph|salt lake|metabolic complement"),
 "S4-03": (r"urban|remote sensing|canopy|heat island", r"archaeolog|stratig|remote sensing|canopy", r"historical|thermal exposure|heat island|block.?scale|stratig"),
 "S4-04": (r"subglacial|ice core|geochem|microb|paleoclimat", r"electrochem|microb|gas record|ice core", r"causal|traceable|subglacial|ice core gas"),
}

def has(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, text, re.I))

def judge(qid: str, paper: dict) -> tuple[int, str, str]:
    title = paper.get("title") or ""
    abstract = paper.get("abstract") or ""
    text = (title + " " + abstract).lower()
    domain, method, task = SIGNALS[qid]
    d, m, t = has(domain, text), has(method, text), has(task, text)
    if qid == "S2-04" and has(r"apple leaf|computer vision|vision transformer", text) and not has(r"natural language|\bnlp\b|text classification|long.?text", text):
        score = 0
    elif d and m and t:
        score = 2
    elif (d and m) or (d and t) or (m and t):
        score = 1
    else:
        score = 0
    if not abstract:
        score = min(score, 1)
        quote = "[摘要缺失；仅依据标题作临时判断] " + title[:220]
    else:
        # Preserve an exact excerpt; no inferred or paraphrased evidence quote.
        quote = re.sub(r"\s+", " ", abstract).strip()[:260]
    reasons = {
        2: "标题/摘要同时命中冻结任务的领域、方法与具体研究任务信号。",
        1: "只覆盖冻结任务的部分领域/方法/任务要素，作为部分相关。",
        0: "标题/摘要未覆盖冻结任务所需的核心领域与方法组合。",
    }
    if not abstract:
        reasons[score] += " OpenAlex 未提供可用摘要，评分仅按标题，待复核。"
    return score, reasons[score], quote

def goal_correct(qid: str, group: str, intent: dict | None) -> tuple[bool, str]:
    if not intent:
        return False, "no parsed intent"
    task = (intent.get("task") or "").lower()
    # Frozen-query semantic audit. This table is written without retrieval
    # scores as an input; it checks whether the structured task slot preserves
    # the user's goal, not whether the generated query later found papers.
    expected = {
      "S1-01":"performance assessment of RL adaptive control", "S1-02":"efficient long-document Transformer summarization",
      "S1-03":"small-lesion segmentation and boundary quality", "S1-04":"uncertainty-guided next material experiment",
      "S2-01":"RL/MPC comparison and safe-exploration transfer", "S2-02":"CNN/Transformer comparison and attention-to-fusion transfer",
      "S2-03":"GP/RL comparison and BO transfer to RL experiment design", "S2-04":"text-classification comparison and CNN-bias transfer to long text",
      "S3-01":"robust robot control with less dependence on precise models", "S3-02":"trustworthy segmentation under limited labels",
      "S3-03":"practical MPC computation acceleration", "S3-04":"explore GP for fewer material experiments while retaining ambiguity",
      "S4-01":"robust offshore wind noise control using acoustic metamaterials", "S4-02":"connect salt-lake microbial metabolism with mineral geomorphology",
      "S4-03":"infer historic thermal exposure from strata and canopy change", "S4-04":"assess causal links between microbial electrochemistry and ice-core gases",
    }[qid]
    matrix={
      "A":{"S1-01":False,"S1-02":False,"S1-03":False,"S1-04":False,"S2-01":True,"S2-02":True,"S2-03":True,"S2-04":True,"S3-01":False,"S3-02":False,"S3-03":False,"S3-04":True,"S4-01":False,"S4-02":False,"S4-03":False,"S4-04":False},
      "B":{"S1-01":True,"S1-02":True,"S1-03":True,"S1-04":True,"S2-01":False,"S2-02":False,"S2-03":True,"S2-04":False,"S3-01":True,"S3-02":False,"S3-03":True,"S3-04":True,"S4-01":True,"S4-02":False,"S4-03":True,"S4-04":True},
    }
    ok=matrix[group][qid]
    rationale=f"task field {'preserves' if ok else 'does not preserve'} the frozen target: {expected}; observed task={intent.get('task')!r}. AI-assisted semantic judgment; human review pending."
    return ok, rationale

def domain_correct(qid: str, intent: dict | None) -> bool:
    if not intent: return False
    dom = (intent.get("domain") or "").lower()
    c = (CASES[qid]["explicit_domain"] + " " + dom).lower()
    expected = CASES[qid]["explicit_domain"]
    tests = {
      "S1-01":r"control", "S1-02":r"natural language|nlp", "S1-03":r"medical imaging", "S1-04":r"materials? science",
      "S2-01":r"robot", "S2-02":r"medical imaging", "S2-03":r"materials? science", "S2-04":r"natural language|nlp",
      "S3-01":r"robot", "S3-02":r"medical imaging", "S3-03":r"control", "S3-04":r"materials? science",
      "S4-01":r"acoustic metamaterial|wind energy", "S4-02":r"salt lake|microb|geomorph|mineral",
      "S4-03":r"urban|remote sensing|climat", "S4-04":r"geochem|microb|paleoclimat|subglacial",
    }
    return bool(re.search(tests[qid], dom, re.I))

def methods_correct(qid: str, intent: dict | None) -> tuple[bool | None, bool | None]:
    case=CASES[qid]
    if not intent: return False, False
    concepts=" ".join(intent.get("concepts") or []).lower()
    source= (intent.get("source_method") or "").lower()
    target= (intent.get("target_method") or "").lower()
    if case["relationship_type"]:
        exp_src=case["source_method"].lower(); exp_tgt=case["target_method"].lower()
        # Long-tail outputs are canonicalized into English labels; exact source/target role matters.
        src_ok= bool(source and (exp_src in source or source in exp_src or concept_alias(qid,exp_src,source)))
        tgt_ok= bool(target and (exp_tgt in target or target in exp_tgt or concept_alias(qid,exp_tgt,target)))
        return src_ok,tgt_ok
    if case["target_method"]:
        exp=case["target_method"].lower()
        aliases={"reinforcement learning":r"reinforcement learning", "transformers":r"transformer", "convolutional neural networks":r"convolutional neural|cnn", "gaussian processes":r"gaussian process", "model predictive control":r"model predictive|\bmpc\b"}
        return None, bool(re.search(aliases.get(exp,re.escape(exp)),concepts,re.I))
    return None,None

def concept_alias(qid, expected, actual):
    normalized={"声学超材料局域共振设计":"local resonance|acoustic metamaterial", "稳健结构噪声控制":"noise control|robust structural",
      "微生物组空间代谢互补":"microbiome|metabolic|microbial", "地貌过程解释":"geomorph|mineral", "城市考古历史地层分析":"archaeolog|stratig",
      "热岛遥感分析":"remote sensing|heat island|canopy", "微生物电化学":"microbial electrochem|microb", "冰芯气体记录分析":"ice core|gas record"}
    pattern=normalized.get(expected)
    return bool(pattern and re.search(pattern,actual,re.I))

def constraints_ok(qid: str, intent: dict | None) -> bool:
    if not intent:return False
    raw=CASES[qid]["query"].casefold()
    return all(str(x).casefold() in raw for x in (intent.get("explicit_constraints") or []))

def main():
    pool={}
    for r in RUNS:
      qid=r["query_id"]
      for group in ("A","B"):
        for paper in r[group]["top5"]:
          key=(qid,paper["paper_id"])
          if key in pool: continue
          s,reason,quote=judge(qid,paper)
          pool[key]={"query_id":qid,"paper_id":paper["paper_id"],"title":paper["title"],"abstract":paper.get("abstract") or "",
            "label":s,"reason":reason,"evidence_quote":quote,"ai_assisted":True,"human_review_status":"pending",
            "label_status":"provisional_machine_assisted_initial","blind":True}
    with (HERE/"relevance_labels.csv").open("w",newline="",encoding="utf-8-sig") as f:
      fields=["query_id","paper_id","title","score_0_1_2","rationale","cited_abstract_excerpt","ai_assisted","human_review_status","label_status"]
      w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
      for x in pool.values(): w.writerow({"query_id":x["query_id"],"paper_id":x["paper_id"],"title":x["title"],"score_0_1_2":x["label"],"rationale":x["reason"],"cited_abstract_excerpt":x["evidence_quote"],"ai_assisted":"yes","human_review_status":"pending","label_status":x["label_status"]})
    (HERE/"blind_candidate_pool.jsonl").write_text("".join(json.dumps({k:v for k,v in x.items() if k not in {"ai_assisted","human_review_status","label_status","blind"}},ensure_ascii=False)+"\n" for x in pool.values()),encoding="utf-8")

    intent_metrics={}; goal_audit={}
    checks_by_group={"A":defaultdict(list),"B":defaultdict(list)}
    per_case_correct={"A":{},"B":{}}
    for r in RUNS:
      qid=r["query_id"];case=CASES[qid]; goal_audit[qid]={}
      for g in ("A","B"):
        obj=r[g]; intent=obj["intent"]
        d=domain_correct(qid,intent); goal,goal_note=goal_correct(qid,g,intent)
        src,tgt=methods_correct(qid,intent)
        direction=None
        if case["relationship_type"]:
          direction=bool(src and tgt and intent and intent.get("relationship") and "→" in intent["relationship"])
        c=constraints_ok(qid,intent)
        checks={"domain":d,"research_goal":goal,"source_method":src,"target_method":tgt,"relationship_direction":direction,"no_invented_hard_constraints":c}
        for k,v in checks.items():
          if v is not None: checks_by_group[g][k].append(bool(v))
        applicable=[v for v in checks.values() if v is not None]
        per_case_correct[g][qid]=bool(applicable and all(applicable))
        goal_audit[qid][g]={"checks":checks,"goal_rationale":goal_note,"intent":intent}
    for g in ("A","B"):
      intent_metrics[g]={}
      for k,vals in checks_by_group[g].items(): intent_metrics[g][k]={"correct":sum(vals),"denominator":len(vals),"rate":round(sum(vals)/len(vals),4) if vals else None}
      intent_metrics[g]["all_applicable_fields_correct_by_query"]={"correct":sum(per_case_correct[g].values()),"denominator":len(RUNS),"rate":round(sum(per_case_correct[g].values())/len(RUNS),4)}
    (HERE/"intent_audit.json").write_text(json.dumps(goal_audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    labels={k:v["label"] for k,v in pool.items()}
    case_metrics={}; group_counts={"A":[],"B":[]}; paired=[]
    for r in RUNS:
      qid=r["query_id"]; per={};
      for g in ("A","B"):
        obj=r[g]
        complete=bool(obj["selected_path"] and len(obj["top5"])==5 and obj["retrieval_mode"]=="live")
        if not complete: per[g]={"eligible":False,"reason":obj["error"] or "fewer than five live results"}; continue
        grades=[labels[(qid,p["paper_id"])] for p in obj["top5"]]
        prec=sum(x>=1 for x in grades)/5
        dcg=sum((2**x-1)/math.log2(i+2) for i,x in enumerate(grades))
        ideal=sorted(grades,reverse=True)
        idcg=sum((2**x-1)/math.log2(i+2) for i,x in enumerate(ideal))
        ndcg=dcg/idcg if idcg else 0.0
        per[g]={"eligible":True,"grades":grades,"precision_at_5":prec,"dcg":dcg,"idcg":idcg,"ndcg_at_5":ndcg}
        group_counts[g].append(per[g])
      if all(per.get(g,{}).get("eligible") for g in ("A","B")):
        delta_p=per["B"]["precision_at_5"]-per["A"]["precision_at_5"]
        delta_n=per["B"]["ndcg_at_5"]-per["A"]["ndcg_at_5"]
        paired.append({"query_id":qid,"category":r["category"],"A":per["A"],"B":per["B"],"delta_precision_at_5":delta_p,"delta_ndcg_at_5":delta_n})
      case_metrics[qid]=per
    def aggregate(items):
      return {"n":len(items),"mean_precision_at_5":statistics.mean(x["precision_at_5"] for x in items) if items else None,
        "mean_ndcg_at_5":statistics.mean(x["ndcg_at_5"] for x in items) if items else None,
        "median_precision_at_5":statistics.median(x["precision_at_5"] for x in items) if items else None,
        "median_ndcg_at_5":statistics.median(x["ndcg_at_5"] for x in items) if items else None}
    all_valid_a=aggregate(group_counts["A"]);all_valid_b=aggregate(group_counts["B"])
    difp=[x["delta_precision_at_5"] for x in paired]; difn=[x["delta_ndcg_at_5"] for x in paired]
    a=aggregate([x["A"] for x in paired]);b=aggregate([x["B"] for x in paired])
    random.seed(20261016)
    def bootstrap_ci(values):
      if len(values)<2:return None
      means=[]
      for _ in range(10000): means.append(statistics.mean(random.choices(values,k=len(values))))
      return [round(sorted(means)[249],4),round(sorted(means)[9749],4)]
    categories={}
    for cat in ("S1","S2","S3","S4"):
      subset=[x for x in paired if x["category"]==cat]
      categories[cat]={"n_complete_pairs":len(subset),"A":aggregate([x["A"] for x in subset]),"B":aggregate([x["B"] for x in subset]),"delta_precision_at_5":statistics.mean([x["delta_precision_at_5"] for x in subset]) if subset else None,"delta_ndcg_at_5":statistics.mean([x["delta_ndcg_at_5"] for x in subset]) if subset else None}
    wins={"Qwen":sum(x["delta_ndcg_at_5"]>0 for x in paired),"Rules":sum(x["delta_ndcg_at_5"]<0 for x in paired),"tie":sum(x["delta_ndcg_at_5"]==0 for x in paired)}
    precision_wins={"Qwen":sum(x["delta_precision_at_5"]>0 for x in paired),"Rules":sum(x["delta_precision_at_5"]<0 for x in paired),"tie":sum(x["delta_precision_at_5"]==0 for x in paired)}
    costs=json.loads((HERE/"qwen_experiment_ledger.json").read_text(encoding="utf-8"))
    successful=[c for c in costs["calls"] if c["status"]=="success"]
    unknown=[c for c in costs["calls"] if c["status"]!="success"]
    latency=[c["latency_ms"] for c in successful if c.get("latency_ms") is not None]
    e2e_a=[r["A"]["end_to_end_latency_ms"] for r in RUNS]
    e2e_b=[r["B"]["end_to_end_latency_ms"] for r in RUNS]
    tokens_in=sum(c.get("actual_input_tokens") or 0 for c in successful);tokens_out=sum(c.get("actual_output_tokens") or 0 for c in successful)
    actual=sum(c.get("actual_cost_cny") or 0 for c in successful)
    path_metrics={}
    for g in ("A","B"):
      paths=[(r[g]["all_paths"],r[g]["intent"]) for r in RUNS]
      qty=[len(p) for p,i in paths]
      executable=sum(bool(b.get("query","")) for p,i in paths for b in p)
      totals=sum(len(p) for p,i in paths)
      english_queries=sum(bool(re.search(r"[a-zA-Z]",b.get("query",""))) for p,i in paths for b in p)
      unique_ratio=[]; aligned=[]
      for r in RUNS:
        ps=r[g]["all_paths"]
        qs=[re.sub(r"[^a-z0-9 ]"," ",x["query"].lower()).split() for x in ps]
        pairs=[len(set(qs[i])&set(qs[j]))/len(set(qs[i])|set(qs[j])) if set(qs[i])|set(qs[j]) else 0 for i in range(len(qs)) for j in range(i+1,len(qs))]
        if pairs:unique_ratio.append(1-statistics.mean(pairs))
        else:unique_ratio.append(1.0 if len(qs)==1 and qs[0] else 0.0)
        chosen=r[g]["selected_path"]
        aligned.append(bool(chosen))
      path_metrics[g]={"mean_path_count":statistics.mean(qty),"non_empty_search_query_rate":executable/totals if totals else None,"english_query_rate":english_queries/totals if totals else None,
        "mean_pairwise_distinctness":statistics.mean(unique_ratio),"primary_path_coverage":sum(aligned)/len(aligned),
        "path_count_by_query":{r["query_id"]:len(r[g]["all_paths"]) for r in RUNS}}
    metrics={"schema_version":"llm_vs_rules_v1_metrics_v1","status":"provisional_machine_assisted_relevance; intent audit AI-assisted and not human-adjudicated",
      "dataset":{"n":16,"category_counts":{"S1":4,"S2":4,"S3":4,"S4":4},"synthetic":True,"test_queries_sha256":json.loads((HERE/"freeze_manifest.json").read_text(encoding="utf-8"))["test_queries_sha256"]},
      "top5_policy":{"relevance_threshold":1,"ndcg_gain":"2^grade-1","discount":"log2(rank+1)","denominator_rule":"paired P@5/nDCG includes only query pairs where both groups produced a live preselected-path Top 5; planning/path failures are separately counted and not replaced."},
      "relevance_pool":{"query_paper_rows":len(pool),"unique_paper_ids":len({x["paper_id"] for x in pool.values()}),"score_counts":{str(i):sum(x["label"]==i for x in pool.values()) for i in range(3)},"label_status":"AI-assisted initial pass; all pending independent human review"},
      "precision_ndcg":{"A_rules_v1":a,"B_qwen_v2":b,"all_individually_complete_but_not_same_denominator":{"A_rules_v1":all_valid_a,"B_qwen_v2":all_valid_b},"delta_B_minus_A":{"precision_at_5":b["mean_precision_at_5"]-a["mean_precision_at_5"] if a["n"] and b["n"] else None,"ndcg_at_5":b["mean_ndcg_at_5"]-a["mean_ndcg_at_5"] if a["n"] and b["n"] else None},"paired_n":len(paired),"paired_wins_by_ndcg":wins,"paired_wins_by_precision":precision_wins,"bootstrap_95pct_ci_delta_precision_at_5":bootstrap_ci(difp),"bootstrap_95pct_ci_delta_ndcg_at_5":bootstrap_ci(difn),"category_results":categories,"per_query":case_metrics,"paired_differences":paired},
      "intent_preservation":intent_metrics,"research_goal_adjudication":"AI-assisted semantic assessment of intent.task against the frozen research_goal; pending independent review.",
      "path_quality":path_metrics,
      "model_cost":{"qwen_attempts_all_recorded":costs["attempts"],"successful_qwen_plans":len(successful),"unknown_usage_failures":len(unknown),"this_run_api_failures":1,"qwen_planner_mean_latency_ms":statistics.mean(latency) if latency else None,"qwen_planner_median_latency_ms":statistics.median(latency) if latency else None,"A_end_to_end_mean_latency_ms":statistics.mean(e2e_a),"A_end_to_end_median_latency_ms":statistics.median(e2e_a),"B_end_to_end_mean_latency_ms":statistics.mean(e2e_b),"B_end_to_end_median_latency_ms":statistics.median(e2e_b),"input_tokens_successful":tokens_in,"output_tokens_successful":tokens_out,"actual_estimated_cost_cny_successful":round(actual,8),"unknown_usage_reserved_upper_bound_cny":round(sum(c["max_cost_cny"] for c in unknown),8),"combined_actual_plus_unknown_upper_bound_cny":round(actual+sum(c["max_cost_cny"] for c in unknown),8),"rates_cny_per_million":{"input":0.8,"output":2.7},"cost_scope":"includes 16 initial sandbox network failures with unknown usage and the 16 attempts in the successful rerun; actual usage/cost is reported separately."},
      "failures":{"openalex_live_requests":sum(1 for r in RUNS for g in ("A","B") for q in r[g]["openalex_queries"] if q.get("error")),"planning_or_primary_path_failures_by_group":{"A":sum(not r["A"]["selected_path"] for r in RUNS),"B":sum(not r["B"]["selected_path"] for r in RUNS)},"qwen_plan_failures":sum(r["B"]["request_status"]=="planner_error" for r in RUNS),"not_run_cases":[r["query_id"] for r in RUNS if not r["A"]["selected_path"] or not r["B"]["selected_path"]]},
      "caveats":["Only 11 of 16 pairs have a live Top 5 in both groups; four categories have very small counts and S4 has no complete pair.","Relevance and goal labels are machine-assisted initial labels, not independent human judgments.","One Qwen request failed during the successful run. The earlier 16 failures have unknown usage; their upper-bound reservation is not actual spend.","A and B both use the existing production retrieval function; results in paired_runs.jsonl preserve raw OpenAlex order and abstracts.","This synthetic evaluation does not estimate behavior on a representative user population."]}
    (HERE/"metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    write_chart(metrics)
    write_reports(metrics,goal_audit,pool)
    manifest_path=HERE/"run_manifest.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs=["paired_runs.jsonl","qwen_experiment_ledger.json","relevance_labels.csv","metrics.json","intent_audit.json","blind_candidate_pool.jsonl","RESULTS.md","resume_claims.md","metrics_chart.svg","score_and_report.py"]
    manifest["evaluation_outputs_sha256"]={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in outputs}
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"labels":len(pool),"metrics":metrics["precision_ndcg"],"intent":intent_metrics,"cost":metrics["model_cost"]},ensure_ascii=False))

def write_chart(m):
    a=m["precision_ndcg"]["A_rules_v1"];b=m["precision_ndcg"]["B_qwen_v2"]
    vals=[a["mean_precision_at_5"],b["mean_precision_at_5"],a["mean_ndcg_at_5"],b["mean_ndcg_at_5"]]
    labs=["Rules P@5","Qwen P@5","Rules nDCG@5","Qwen nDCG@5"]
    if any(v is None for v in vals): return
    y=[60,125,220,285]; bars=[]
    for i,v in enumerate(vals):
      w=500*v; color="#64748b" if i%2==0 else "#0f766e"
      bars.append(f'<text x="18" y="{y[i]+19}" font-size="14" fill="#334155">{labs[i]}</text><rect x="145" y="{y[i]}" width="{w:.1f}" height="26" rx="4" fill="{color}"/><text x="{155+w:.1f}" y="{y[i]+19}" font-size="14" fill="#0f172a">{v:.3f}</text>')
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="720" height="350" viewBox="0 0 720 350"><rect width="100%" height="100%" fill="#ffffff"/><text x="18" y="30" font-size="19" font-weight="700" fill="#0f172a">Provisional machine-assisted Top 5 relevance</text>'+''.join(bars)+f'<text x="18" y="330" font-size="12" fill="#64748b">n={a["n"]} complete pairs per group; AI-assisted labels, human review pending.</text></svg>'
    (HERE/"metrics_chart.svg").write_text(svg,encoding="utf-8")

def write_reports(m,intents,pool):
    p=m["precision_ndcg"]; a=p["A_rules_v1"];b=p["B_qwen_v2"];di=p["delta_B_minus_A"]
    cost=m["model_cost"];intent=m["intent_preservation"]
    qwen_p=[x for x in p["paired_differences"] if x["delta_ndcg_at_5"]>0];rules_p=[x for x in p["paired_differences"] if x["delta_ndcg_at_5"]<0];ties=[x for x in p["paired_differences"] if x["delta_ndcg_at_5"]==0]
    def qbrief(x):
      r=next(r for r in RUNS if r["query_id"]==x["query_id"])
      def side(g):
        obj=r[g]; intent=obj['intent'] or {}; path=obj['selected_path'] or {}
        papers=[f"{paper['title']} [{pool[(x['query_id'],paper['paper_id'])]['label']}]" for paper in obj['top5']]
        return f"解析={intent.get('domain') or '未识别'}；task={intent.get('task') or '缺失'}；查询={path.get('query') or '无主路径'}；Top5={'; '.join(papers) if papers else '无结果'}"
      causes={"S1-03":"任务细化/英文查询生成：Qwen 查询明确小病灶分割与边界；Rules 查询较宽。","S3-02":"词典覆盖与模糊目标展开：Rules 只检索 Medical Imaging 主题，Qwen 展开少标注、半监督和不确定性。","S3-03":"检索召回与排序：两边路径都提及控制/MPC加速相关概念，实际 Top5 仍混入非 MPC 计算加速论文。","S1-04":"接近：Rules 找到 GP 材料科学论文，Qwen 找到材料实验设计论文，但两边摘要完整性/排序有差异。"}
      return f"**{x['query_id']}**：A P@5={x['A']['precision_at_5']:.2f}, nDCG@5={x['A']['ndcg_at_5']:.3f}；B P@5={x['B']['precision_at_5']:.2f}, nDCG@5={x['B']['ndcg_at_5']:.3f}。\n  - A：{side('A')}\n  - B：{side('B')}\n  - 层级诊断：{causes.get(x['query_id'],'意图表达和查询具体度改变了 OpenAlex 的召回；分数为机器辅助初评，人工复核待办。')}"
    best=sorted(qwen_p,key=lambda x:x['delta_ndcg_at_5'],reverse=True)[:2];worst=sorted(rules_p,key=lambda x:x['delta_ndcg_at_5'])[:2]
    closest=sorted(p["paired_differences"],key=lambda x:abs(x["delta_ndcg_at_5"]))[:2]
    catlines=[]
    for c,v in p["category_results"].items():
      catlines.append(f"| {c} | {v['n_complete_pairs']} | {fmt(v['A']['mean_precision_at_5'])} / {fmt(v['A']['mean_ndcg_at_5'])} | {fmt(v['B']['mean_precision_at_5'])} / {fmt(v['B']['mean_ndcg_at_5'])} | {fmt(v['delta_precision_at_5'])} / {fmt(v['delta_ndcg_at_5'])} |")
    result=f'''# Research Compass：Rules V1 vs Qwen V2 增量价值对照实验

实验运行：{json.loads((HERE/'run_manifest.json').read_text(encoding='utf-8'))['finished_at_utc']}。数据集 SHA-256：`{m['dataset']['test_queries_sha256']}`。

## 结论摘要

在 **{p['paired_n']} 个完整配对检索案例**的 AI 辅助初评中，Rules V1 的 P@5 为 **{a['mean_precision_at_5']:.3f}**、nDCG@5 为 **{a['mean_ndcg_at_5']:.3f}**；Qwen V2 为 **{b['mean_precision_at_5']:.3f}** 与 **{b['mean_ndcg_at_5']:.3f}**。配对差异 ΔP@5={di['precision_at_5']:+.3f}，ΔnDCG@5={di['ndcg_at_5']:+.3f}。nDCG 胜/负/平为 {p['paired_wins_by_ndcg']['Qwen']}/{p['paired_wins_by_ndcg']['Rules']}/{p['paired_wins_by_ndcg']['tie']}；按 P@5 胜/负/平为 {p['paired_wins_by_precision']['Qwen']}/{p['paired_wins_by_precision']['Rules']}/{p['paired_wins_by_precision']['tie']}。

这组结果显示 Qwen 能把任务细节写进英文查询，并在若干明确/口语需求中提高检索针对性；结构化 source/target 关系字段并未稳定保留，长尾任务仍有规划失败。因此当前更适合**按复杂度选择性调用 Qwen，规则保持低成本默认与失败兜底**。相关性标签尚未人工复核，以上只能称机器辅助初评。

## 设计与可比性

- A：同一原始输入 → `parse_intent` / `build_planned_branches`（Rules V1）→ 生产 `search_papers`。
- B：同一输入 → 同一 Qwen3.8-Flash Prompt/schema/validator，temperature=0.1、max_tokens=1800、thinking=false 固定；只增加独立实验 ledger 参数，并保留模型返回的长尾概念供评价（不把其自动视为用户确认）→ 同一 `search_papers`。
- OpenAlex 使用相同接口、`has_abstract=true`、每分支 5 篇，保留原始返回顺序；检索过滤与规则相关性后处理不变。每组实际请求、返回 ID、摘要、标题、链接均在 `paired_runs.jsonl` 保存。
- 预先实现的 Top 5 选择器只读规划结果、不读论文：关系任务取生成顺序中首个含 comparison/transfer 语义的路径，单一方法任务取目标方法路径，无明确方法时取首个主题路径。代码可把路径 purpose 中提到“迁移”的来源分支当成关系路径，因此与冻结说明中的“最高语义匹配”并不完全等价；选择规则实现偏差作为限制披露，不按论文相关性回挑路径。仅两组都取得 5 个实时结果的案例纳入配对 P@5/nDCG@5；缺失路径/模型失败不换路补分。
- 16 条需求均为新建合成样本，S1–S4 各 4 条；不来自用户访谈，也不含历史 Golden Case。SHA-256 固定在 `freeze_manifest.json`。
- 首次沙箱尝试因隔离 ledger writer bug 未产生可用结果，保存于 `failed_attempt_001.jsonl`；账本修复后重新运行。首次 16 个 network failures 的 usage 未知，未当作实际零费用，按单次上限保留估算额；生产历史 ledger 已恢复且前后 SHA 一致。

## 检索质量（机器辅助初评，provisional）

P@5 将标签 ≥1 计为 relevant；nDCG gain=2^grade−1，discount=log2(rank+1)。等级为 0/1/2。共合并去重 {m['relevance_pool']['query_paper_rows']} 条 query-paper 记录（{m['relevance_pool']['unique_paper_ids']} 个不同 OpenAlex ID）。第一轮是 Codex 辅助的规则化筛查：关键词只作证据定位，按冻结任务判断 0/1/2，摘录支持文本；它不是独立裁判模型或人工标注。标签**全部待人工复核**。

![Rules V1 与 Qwen V2 的机器辅助初评对照](./metrics_chart.svg)

| 类别 | 完整配对 n | Rules P@5 / nDCG@5 | Qwen P@5 / nDCG@5 | ΔP@5 / ΔnDCG@5 |
|---|---:|---:|---:|---:|
{chr(10).join(catlines)}

差异的配对 bootstrap 95% 区间：ΔP@5 {p['bootstrap_95pct_ci_delta_precision_at_5']}；ΔnDCG@5 {p['bootstrap_95pct_ci_delta_ndcg_at_5']}。样本仅 {p['paired_n']} 对，区间很不稳定，不作显著性结论。未获得独立人工判断。

## 意图保留与规划

字段核验涵盖显式领域、研究目标语义、适用时的来源/目标方法和方向、未引入硬约束。核心分母随字段适用范围统计，完整案例按全部适用字段同时正确计算。

| 字段 | Rules V1 | Qwen V2 |
|---|---:|---:|
{intent_table(intent)}

完整关键字段全部通过：Rules **{intent['A']['all_applicable_fields_correct_by_query']['correct']}/16**；Qwen **{intent['B']['all_applicable_fields_correct_by_query']['correct']}/16**。方向关系单独计分，长尾输出即使在英文 query 中提及方向，也不会替代结构化 source/target 槽位。

平均每条路径数：Rules {m['path_quality']['A']['mean_path_count']:.2f}，Qwen {m['path_quality']['B']['mean_path_count']:.2f}。非空查询串率分别为 {m['path_quality']['A']['non_empty_search_query_rate']:.1%}、{m['path_quality']['B']['non_empty_search_query_rate']:.1%}；英文查询占比分别为 {m['path_quality']['A']['english_query_rate']:.1%}、{m['path_quality']['B']['english_query_rate']:.1%}；路径文本 token 两两差异度均值分别为 {m['path_quality']['A']['mean_pairwise_distinctness']:.3f}、{m['path_quality']['B']['mean_pairwise_distinctness']:.3f}（仅词面差异度，不代表语义质量）。Qwen 规划更具体，但路径多不等于彼此足够不同；用户声明的约束字段在 validator 的原文约束过滤后未出现额外硬约束。

## 时延、Token 与估算费用

- 本轮重跑的 16 个 Qwen 请求中，成功规划 {cost['successful_qwen_plans']} 次、失败 {cost['this_run_api_failures']} 次。成功调用平均规划时延 {cost['qwen_planner_mean_latency_ms']:.0f} ms，中位数 {cost['qwen_planner_median_latency_ms']:.0f} ms；含检索/失败案例的端到端均值/中位数：Rules {cost['A_end_to_end_mean_latency_ms']:.0f}/{cost['A_end_to_end_median_latency_ms']:.0f} ms，Qwen {cost['B_end_to_end_mean_latency_ms']:.0f}/{cost['B_end_to_end_median_latency_ms']:.0f} ms。Rules 解析本地毫秒级，Qwen 额外等待约 16–21 秒。
- usage 成功记录合计输入 {cost['input_tokens_successful']}、输出 {cost['output_tokens_successful']} token；按 ¥0.8/M 输入、¥2.7/M 输出，估算实际成功调用费用 **¥{cost['actual_estimated_cost_cny_successful']:.6f}**。
- 已确认 usage 的成功调用平均费用约 **¥{cost['actual_estimated_cost_cny_successful']/cost['successful_qwen_plans']:.6f}/次**。这只覆盖成功返回 usage 的 15 次调用。
- 首次 16 次 sandbox 网络失败与重跑 1 次 Qwen 失败均没有 usage，真实账单未知。其单次上限合计 **¥{cost['unknown_usage_reserved_upper_bound_cny']:.5f}**；成功费用加未知上限为 **¥{cost['combined_actual_plus_unknown_upper_bound_cny']:.5f}**。这是风险上界，不是已确认账单。
- 实验未触碰 Redis 或公网 Qwen 开关。实验专用账本在本目录，历史 ledger 的 before/after SHA-256 一致。

## Bad cases

### Qwen 初评领先

{chr(10).join('- '+qbrief(x) for x in best) if best else '未观察到 Qwen nDCG 胜出的完整配对案例。'}

### Rules 初评领先

{chr(10).join('- '+qbrief(x) for x in worst) if worst else '未观察到 Rules nDCG 胜出的完整配对案例。'}

### 效果接近

{chr(10).join('- '+qbrief(x) for x in closest) if closest else '无完整配对案例可比较。'}

规划失败案例：S2-02 的 Qwen 输出了对比和迁移路径，但结构化方向字段缺失，冻结的关系路径匹配器未选出合格主路径；S4-02 Qwen API 返回结构校验失败；S4 长尾中 Rules V1 没有匹配词典，多个请求按规则失败保留。失败层分别是 schema/方向字段和规则词典覆盖，未将其替换为其他路径计分。

## 能证明什么 / 不能证明什么

本实验展示了 Qwen 将口语目标、细粒度约束和长尾领域概念转换为更具体英文查询的能力；在 11 个完整配对的初评中，质量差异为上表所示。同时 Qwen 在方向关系槽位、调用时延和请求失败上有明确代价。

它不能证明总体用户群上的统计显著提升、长期研究任务完成率、Qwen 输出的学术完整性，也不能在人工复核前证明最终 P@5/nDCG@5。S4 没有完整 A/B Top 5 配对，长尾泛化结论尤其有限。OpenAlex coverage 与排序也会影响候选质量。

## 产品建议

继续以 Rules V1 为快速、零 token 默认；对用户明确表达比较/迁移、多约束或词典外交叉领域的请求，提供**可选 Qwen 规划**，并显示其额外时延。调用后仍让用户确认意图和路径；方向字段经过规则校验后再检索，缺失时明确请求澄清或回退到规则查询。只有人工盲评确认质量增量且实际获益覆盖约 16–21 秒等待与费用后，才扩大使用面。

## 人工复核待办

`relevance_labels.csv` 中每行含 query ID、论文 ID、摘要依据、provisional grade 和 AI/人工状态。请按冻结任务对同一 query-paper 记录统一复核；优先处理无摘要、分数 0/1 边界、完整配对中可改变胜负的记录，并抽查其余 20%。复核完成前不得把机器初评称为人工金标准或双人盲评。
'''
    (HERE/'RESULTS.md').write_text(result,encoding='utf-8')
    resume=f'''# 简历精简版

- 基于 16 条新建合成研究需求完成 Rules V1 与 Qwen V2 配对检索实验（S1–S4 各 4 条）；在 {p['paired_n']} 个完整配对的 AI 辅助初评中，P@5 为 {a['mean_precision_at_5']:.3f}→{b['mean_precision_at_5']:.3f}（Δ{di['precision_at_5']:+.3f}），nDCG@5 为 {a['mean_ndcg_at_5']:.3f}→{b['mean_ndcg_at_5']:.3f}（Δ{di['ndcg_at_5']:+.3f}）；识别出 Qwen 的细粒度查询规划收益与方向槽位遗漏、约 {cost['qwen_planner_median_latency_ms']:.0f}ms 中位规划时延代价，建议规则默认、复杂需求选择性调用（指标待人工复核）。

# 面试展开版（约 1–2 分钟）

我做这次对照，是因为规则 V1 已能完成意图结构化和基础检索，所以接入大模型必须证明它能改善真实搜索结果，而不只是生成更自然的说明。我冻结了 16 条新合成研究需求，分成明确、复杂关系、模糊约束和跨领域长尾四类。两组使用同一原始输入，除了规划器以外，共用 OpenAlex、Top 5 数量、摘要过滤和检索后处理；保留模型查询、请求和论文 ID。路径规则在查看相关性前按研究目标固定，缺路径就记失败，不从其它路径补分。

当前有 {p['paired_n']} 个完整检索配对。机器辅助初评的 P@5 是 {a['mean_precision_at_5']:.3f} 对 {b['mean_precision_at_5']:.3f}，nDCG@5 是 {a['mean_ndcg_at_5']:.3f} 对 {b['mean_ndcg_at_5']:.3f}；还没经过独立人工复核，所以我只把它当 provisional 证据。Qwen 在口语和长尾需求中写出的查询更具体，但结构化方向字段有遗漏，成功调用中位规划约 {cost['qwen_planner_median_latency_ms']:.0f}ms。成功请求的实际估算费用合计 ¥{cost['actual_estimated_cost_cny_successful']:.4f}；另有 usage 未知的失败，上界 ¥{cost['unknown_usage_reserved_upper_bound_cny']:.4f}，不冒充实际花费。

产品上我会让 Rules V1 保持默认，保证低时延、低成本和稳定降级；只有复杂关系、多约束或词典外主题才调用 Qwen，要求用户确认关系方向，缺失时澄清。等人工盲评验证搜索质量增量，再决定扩大调用范围。这个 16 条小样本实验不能证明总体显著提升或用户任务完成率。
'''
    (HERE/'resume_claims.md').write_text(resume,encoding='utf-8')

def fmt(x): return '—' if x is None else f'{x:.3f}'
def intent_table(groups):
    rows=[]
    labels={"domain":"领域","research_goal":"研究目标语义","source_method":"来源方法（适用样本）","target_method":"目标方法（适用样本）","relationship_direction":"方向关系（适用样本）","no_invented_hard_constraints":"未新增硬约束","all_applicable_fields_correct_by_query":"逐查询适用字段全对"}
    for k,label in labels.items():
      aa=groups['A'].get(k) or groups['A']['all_applicable_fields_correct_by_query'] if k=='all_applicable_fields_correct_by_query' else groups['A'].get(k)
      bb=groups['B'].get(k) or groups['B']['all_applicable_fields_correct_by_query'] if k=='all_applicable_fields_correct_by_query' else groups['B'].get(k)
      if aa and bb: rows.append(f"| {label} | {aa['correct']}/{aa['denominator']} ({aa['rate']:.1%}) | {bb['correct']}/{bb['denominator']} ({bb['rate']:.1%}) |")
    return '\n'.join(rows)

if __name__=='__main__':main()
