"""Time-bounded cross-model category-head comparison using training-only retrieval."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from datetime import datetime, timezone
from tools import semeval_taxonomy as previous
from tools.semeval_product import digest, target_hash, TrainingRetriever, request_for, parse_tool

original = previous.original
ROOT, DATA, FIELDS, INVALID = previous.ROOT, previous.DATA, previous.FIELDS, previous.INVALID
PUBLIC = ROOT / "evaluation/semeval-st1-v8"
OUTPUT = ROOT / "outputs/semeval-st1-v8"
VARIANTS = ("deepseek", "qwen")
HEADS = ("v5", *VARIANTS)
COMBINATIONS = tuple((h, p) for h in HEADS for p in HEADS if (h, p) != ("v5", "v5"))
CUTOFF = datetime(2026, 9, 14, 21, 0, tzinfo=timezone.utc)
TEST_START_CUTOFF = datetime(2026, 9, 14, 20, 40, tzinfo=timezone.utc)


def combo_name(hazard, product):
    return f"h-{hazard}-p-{product}"


def combine_records(hazard, product, labels):
    if hazard["id"] != product["id"] or hazard["input_sha256"] != product["input_sha256"]:
        raise ValueError("Cannot mix different target records")
    prediction = {FIELDS[0]: hazard["prediction"][FIELDS[0]], FIELDS[1]: product["prediction"][FIELDS[1]]}
    if any(prediction[f] not in labels[f] for f in FIELDS):
        prediction = {f: INVALID for f in FIELDS}
        return prediction, "ERROR" if "ERROR" in (hazard["status"], product["status"]) else "INVALID_OUTPUT"
    if hazard["status"] != "VALID" or product["status"] != "VALID":
        raise ValueError("Valid category values require valid parent records")
    return prediction, "VALID"



def taxonomy(train):
    """Keep all fine-label mappings observed in training, including ambiguous ones."""
    labels = {field: sorted({r[field] for r in train}) for field in FIELDS}
    guidance = {}
    for field, fine in zip(FIELDS, ("hazard", "product")):
        guidance[field] = []
        for index, label in enumerate(labels[field]):
            counts = Counter(r[fine] for r in train if r[field] == label)
            values = sorted(counts, key=lambda item: (-counts[item], item))
            guidance[field].append({"id": index, "label": label, "training_fine_labels": values})
    return labels, guidance


def choose(results, incumbent):
    names = [combo_name(*pair) for pair in COMBINATIONS]
    winner = max(names, key=lambda name: (results[name]["official_st1_score"] or -1, -names.index(name)))
    value = results[winner]["official_st1_score"]
    return winner, value is not None and value >= incumbent["official_st1_score"] + 0.005


def prepare():
    if (PUBLIC / "plan.json").exists():
        raise FileExistsError("Plan already frozen")
    base, _ = previous.load_protocol(previous.PUBLIC / "validation-pro-taxonomy-protocol.json")
    for folder in ("semeval-st1", "semeval-st1-v2", "semeval-st1-v3", "semeval-st1-v4", "semeval-st1-v5", "semeval-st1-v6"):
        directory = ROOT / "evaluation" / folder
        for item in json.loads((directory / "publication-manifest.json").read_text(encoding="utf-8"))["artifacts"]:
            if original.sha(directory / item["path"]) != item["sha256"]:
                raise ValueError("Archived evidence changed")
    incumbent = json.loads((previous.PUBLIC / "validation-pro-taxonomy/results.json").read_text(encoding="utf-8"))
    rows = original.read_rows(DATA / "incidents_valid.csv")
    inherited = {}
    for split, name in (("validation", "validation-pro-taxonomy"), ("test-regression", "test-regression-pro-taxonomy")):
        inherited[split] = {"directory": str((previous.OUTPUT / name).relative_to(ROOT)).replace("\\", "/"),
            "records": {p.name: original.sha(p) for p in sorted((previous.OUTPUT / name).glob("row-*.json"))}}
    plan = {"frozen_at": original.now(), "models": {"deepseek":"deepseek.v3.2", "qwen":"qwen.qwen3-next-80b-a3b"},
        "combinations": [combo_name(*pair) for pair in COMBINATIONS], "target":{"metric":"official_st1_score", "value":0.9},
        "incumbent_validation_metrics": {k:incumbent[k] for k in ("official_st1_score", "hazard_accuracy", "product_accuracy")},
        "inherited_predictions": inherited,
        "selection_rule": "Run both models once on all 565 validation reports. Evaluate eight prelisted fixed hazard/product combinations from v5, DeepSeek and Qwen. Select highest unrounded ST1, ties by listed order. Require >=0.005 improvement over v5 validation. Launch only one selected 997-report combined regression by 20:40 UTC, invoking only its required new model components. No incomplete candidate may win. Preserve all labels and errors. Stop new model calls and retries at 21:00 UTC (5 p.m. Eastern); preserve in-flight responses and incomplete runs. At cutoff retain the best completed observed test result across experiments, disclosed as exposed-test selection, not unbiased generalization.",
        "changes": "Same v5 system prompt, full training taxonomy, target title/full text and four unchanged training-only examples. DeepSeek V3.2 vs Qwen3 Next; toolChoice=auto (named forcing not supported generally), temperature0,maxTokens2048, six workers per model. Strict single two-ID tool parser unchanged. No evidence-description output requirement, SVM or category-balanced retrieval.",
        "maximum_logical_classifications":3124, "cutoff_utc":CUTOFF.isoformat(), "test_launch_cutoff_utc":TEST_START_CUTOFF.isoformat(),
        "test_exposure":"All six earlier test regressions exposed. V7 is concurrent and its Nova Pro validation score seen; no v7 test score seen when this design was frozen. No new target-row annotations used for model prompts. Repeated-validation optimization and exposed-test selection, not a fresh held-out or leaderboard result.",
        "access": "Both alternatives passed synthetic auto-tool checks. OpenAI Terra access unavailable for account; no dataset rows sent to Terra. No access-policy changes made.",
        "documentation":["https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-deepseek-deepseek-v3-2.html", "https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ToolChoice.html"]}
    original.write_json(PUBLIC / "plan.json", plan)
    hashes = dict(base["code_hashes"])
    hashes.update({"tools/semeval_ensemble.py":original.sha(Path(__file__)), "tests/test_semeval_ensemble.py":original.sha(ROOT / "tests/test_semeval_ensemble.py")})
    for variant in VARIANTS:
        p = json.loads(json.dumps(base))
        p.update(frozen_at=original.now(), variant=variant, model_id=plan["models"][variant], workers=6,
            inference_config={"temperature":0,"maxTokens":2048}, code_hashes=hashes,
            plan_sha256=original.sha(PUBLIC / "plan.json"), test_exposure=plan["test_exposure"])
        p["tool_config"]["toolChoice"] = {"auto":{}}
        original.write_json(PUBLIC / f"validation-{variant}-protocol.json", p)
    for h, product in COMBINATIONS:
        p = json.loads(json.dumps(base))
        p.update(frozen_at=original.now(), variant=combo_name(h,product), component_heads={FIELDS[0]:h,FIELDS[1]:product},
            code_hashes=hashes, plan_sha256=original.sha(PUBLIC / "plan.json"), test_exposure=plan["test_exposure"],
            execution="Combine frozen per-target component predictions; no direct model call for this protocol. model_id and prompt describe the inherited v5 component only.")
        original.write_json(PUBLIC / f"validation-{p['variant']}-protocol.json", p)
    print("Frozen two model runs and eight validation head combinations", flush=True)


def load_protocol(path):
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for file, expected in protocol["source_hashes"].items():
        if original.sha(DATA / file) != expected:
            raise ValueError("Pinned source changed: " + file)
    for file, expected in protocol["code_hashes"].items():
        if original.sha(ROOT / file) != expected:
            raise ValueError("Frozen implementation changed: " + file)
    if original.sha(PUBLIC / "plan.json") != protocol["plan_sha256"]:
        raise ValueError("Development plan changed")
    rows = original.read_rows(DATA / protocol["data_file"])
    if [r[""] for r in rows] != protocol["row_ids"]:
        raise ValueError("Split membership changed")
    return protocol, rows


def classify(client, row, protocol, protocol_hash, examples, directory):
    from pantry_recall.aws_access import error_details
    path = directory / f"row-{row['']}.json"
    request = request_for(row, protocol, examples)
    request_hash = digest(request)
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved["protocol_sha256"] != protocol_hash or saved["request_sha256"] != request_hash or saved["id"] != row[""]:
            raise ValueError("Cached result binding mismatch")
        return {**saved, "_cached": True}
    record = {"id": row[""], "started_at": original.now(), "protocol_sha256": protocol_hash,
              "input_sha256": target_hash(row), "request_sha256": request_hash,
              "training_examples": [{k: e[k] for k in ("training_id", "similarity", "full_text_sha256")} for e in examples],
              "prediction": {f: INVALID for f in FIELDS}, "status": "ERROR", "attempts": []}
    for attempt_number in range(1, 4):
        if datetime.now(timezone.utc) >= CUTOFF:
            record["cutoff_reached"] = True
            break
        attempt = {"number": attempt_number, "started_at": original.now()}
        try:
            response = client.converse(**request)
            attempt.update(status="RESPONSE", raw_content=response["output"]["message"]["content"],
                           stop_reason=response.get("stopReason"), usage=response.get("usage", {}),
                           request_id=response.get("ResponseMetadata", {}).get("RequestId"))
            try:
                record["prediction"] = parse_tool(response, protocol["labels"])
                record["status"] = "VALID"
            except (ValueError, TypeError, KeyError):
                record["status"] = "INVALID_OUTPUT"
            record["attempts"].append(attempt)
            break
        except Exception as error:
            details = error_details(error)
            attempt.update(status="ERROR", error=details)
            record["attempts"].append(attempt)
            retryable = (details.get("aws_error_code") in {"ThrottlingException", "ServiceUnavailableException", "InternalServerException", "ModelTimeoutException", "ModelNotReadyException", "ModelErrorException"}
                         or type(error).__name__ in {"ConnectTimeoutError", "ReadTimeoutError", "EndpointConnectionError", "ConnectionClosedError"})
            if not retryable or attempt_number == 3:
                record["fatal_error"] = not retryable
                break
            time.sleep(2 ** attempt_number)
    record["finished_at"] = original.now()
    original.write_json(path, record)
    return record


def run(protocol_path, profile):
    from botocore.config import Config
    from pantry_recall.aws_access import session_for
    protocol, rows = load_protocol(protocol_path)
    label = f"{protocol['split']}-{protocol['variant']}"
    directory = OUTPUT / label
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "run.json").exists():
        metadata = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        if metadata["protocol_sha256"] != original.sha(protocol_path):
            raise ValueError("Run protocol mismatch")
    else:
        metadata = {"started_at": original.now(), "protocol_sha256": original.sha(protocol_path), "rows": len(rows)}
        original.write_json(directory / "run.json", metadata)
    retriever = TrainingRetriever(original.read_rows(DATA / "incidents_train.csv"), protocol["retrieval"])
    # Fit and query the training-only index before concurrent model calls.
    examples = [retriever.examples(row) for row in rows]
    client = session_for(profile, protocol["region"]).client("bedrock-runtime", config=Config(
        connect_timeout=10, read_timeout=90, retries={"total_max_attempts": 1}, max_pool_connections=8))
    with ThreadPoolExecutor(max_workers=protocol["workers"]) as executor:
        for start in range(0, len(rows), protocol["workers"]):
            if datetime.now(timezone.utc) >= CUTOFF:
                metadata.update(status="INCOMPLETE_CUTOFF", stopped_at=original.now())
                original.write_json(directory / "run.json", metadata)
                return 3
            batch = list(executor.map(lambda pair: classify(client, pair[0], protocol, original.sha(protocol_path), pair[1], directory), zip(rows[start:start+protocol["workers"]], examples[start:start+protocol["workers"]])))
            count = start + len(batch)
            fatal = any(r.get("fatal_error") and not r.get("_cached") for r in batch)
            if count % 40 == 0 or count == len(rows) or fatal:
                print(f"{label}: {count}/{len(rows)} rows persisted", flush=True)
            if fatal:
                metadata.update(status="BLOCKED", stopped_at=original.now())
                original.write_json(directory / "run.json", metadata)
                return 2
    metadata.update(status="COMPLETE", finished_at=original.now())
    original.write_json(directory / "run.json", metadata)
    return 0


def score(protocol_path):
    import numpy as np
    from sklearn.metrics import accuracy_score, classification_report, f1_score
    protocol, rows = load_protocol(protocol_path)
    directory = OUTPUT / f"{protocol['split']}-{protocol['variant']}"
    records = []
    for row in rows:
        record = json.loads((directory / f"row-{row['']}.json").read_text(encoding="utf-8"))
        if (record["id"] != row[""] or record["protocol_sha256"] != original.sha(protocol_path)
                or record["input_sha256"] != target_hash(row)):
            raise ValueError("Result identity mismatch")
        records.append(record)
    ht, pt = (np.array([r[f] for r in rows]) for f in FIELDS)
    hp, pp = (np.array([r["prediction"][f] for r in records]) for f in FIELDS)
    mask = hp == ht
    usage = Counter()
    for record in records:
        for attempt in record["attempts"]:
            usage.update({k: value for k, value in attempt.get("usage", {}).items() if isinstance(value, (int, float))})
    result = {"execution_status": "COMPLETE", "scored_at": original.now(), "split": protocol["split"], "variant": protocol["variant"],
              "rows": len(rows), "valid_outputs": sum(r["status"] == "VALID" for r in records),
              "invalid_outputs": sum(r["status"] == "INVALID_OUTPUT" for r in records), "error_rows": sum(r["status"] == "ERROR" for r in records),
              "official_st1_score": float(original.official_score(ht, pt, hp, pp)) if mask.any() else None,
              "hazard_macro_f1": float(f1_score(ht, hp, average="macro")),
              "product_macro_f1_on_hazard_correct_rows": float(f1_score(pt[mask], pp[mask], average="macro")) if mask.any() else None,
              "hazard_accuracy": float(accuracy_score(ht, hp)), "product_accuracy": float(accuracy_score(pt, pp)),
              "joint_accuracy": float(np.mean((ht == hp) & (pt == pp))), "hazard_correct_rows": int(mask.sum()),
              "per_category": {f: classification_report(t, p, output_dict=True, zero_division=0) for f, t, p in zip(FIELDS, (ht, pt), (hp, pp))},
              "model_attempts": sum(len(r["attempts"]) for r in records), "reported_usage": dict(usage),
              "protocol_sha256": original.sha(protocol_path), "test_exposure": protocol["test_exposure"]}
    original.write_json(directory / "results.json", result)
    print(json.dumps({k: result[k] for k in ("split", "variant", "rows", "official_st1_score", "invalid_outputs", "error_rows", "model_attempts")}, indent=2))
    return result


def combine_phase(path):
    protocol, rows = load_protocol(path)
    directory = OUTPUT / f"{protocol['split']}-{protocol['variant']}"
    plan = json.loads((PUBLIC / "plan.json").read_text(encoding="utf-8"))
    metadata = {"started_at":original.now(), "protocol_sha256":original.sha(path), "rows":len(rows), "new_model_calls":0}
    for row in rows:
        records, bindings = [], {}
        for field in FIELDS:
            name = protocol["component_heads"][field]
            parent_dir = ROOT / plan["inherited_predictions"][protocol["split"]]["directory"] if name == "v5" else OUTPUT / f"{protocol['split']}-{name}"
            parent = parent_dir / f"row-{row['']}.json"
            sha = original.sha(parent)
            if name == "v5" and sha != plan["inherited_predictions"][protocol["split"]]["records"][parent.name]:
                raise ValueError("Inherited record changed")
            record = json.loads(parent.read_text(encoding="utf-8"))
            if record["input_sha256"] != target_hash(row) or record["id"] != row[""]:
                raise ValueError("Parent input binding mismatch")
            records.append(record)
            bindings[field] = {"component":name,"record_sha256":sha}
        prediction, status = combine_records(*records, protocol["labels"])
        original.write_json(directory / f"row-{row['']}.json", {"id":row[""], "input_sha256":target_hash(row),
            "protocol_sha256":original.sha(path), "prediction":prediction,"status":status,"attempts":[],"components":bindings})
    metadata.update(status="COMPLETE",finished_at=original.now())
    original.write_json(directory / "run.json", metadata)
    return score(path)


def select():
    if (PUBLIC / "decision.json").exists():
        raise FileExistsError("Selection already frozen")
    for name in VARIANTS:
        if json.loads((OUTPUT / f"validation-{name}/run.json").read_text())["status"] != "COMPLETE":
            raise ValueError("Both model runs must be complete")
        score(PUBLIC / f"validation-{name}-protocol.json")
    results = {combo_name(*pair):combine_phase(PUBLIC / f"validation-{combo_name(*pair)}-protocol.json") for pair in COMBINATIONS}
    plan = json.loads((PUBLIC / "plan.json").read_text(encoding="utf-8"))
    winner, improved = choose(results, plan["incumbent_validation_metrics"])
    decision = {"decided_at":original.now(),"winner":winner,"improved_on_validation":improved,
        "candidate_scores":{k:r["official_st1_score"] for k,r in results.items()},"plan_sha256":original.sha(PUBLIC / "plan.json"),
        "test_launch_in_time":datetime.now(timezone.utc)<TEST_START_CUTOFF}
    original.write_json(PUBLIC / "decision.json", decision)
    if not improved or not decision["test_launch_in_time"]:
        print("No new test run under the frozen gain/time rule", flush=True)
        return
    protocol, _ = load_protocol(PUBLIC / f"validation-{winner}-protocol.json")
    rows = original.read_rows(DATA / "incidents_test.csv")
    update = {"frozen_at":original.now(),"split":"test-regression","data_file":"incidents_test.csv","row_ids":[r[""] for r in rows],"decision_sha256":original.sha(PUBLIC / "decision.json")}
    protocol.update(update)
    original.write_json(PUBLIC / "test-protocol.json", protocol)
    for name in sorted(set(protocol["component_heads"].values())-{"v5"}):
        component, _ = load_protocol(PUBLIC / f"validation-{name}-protocol.json")
        component.update(update)
        original.write_json(PUBLIC / f"test-{name}-protocol.json", component)
    print("Frozen selected test combination: "+winner, flush=True)


def run_test(profile):
    protocol, _ = load_protocol(PUBLIC / "test-protocol.json")
    if datetime.now(timezone.utc)>=TEST_START_CUTOFF:
        print("Test launch cutoff reached",flush=True)
        return 3
    names = sorted(set(protocol["component_heads"].values())-{"v5"})
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        statuses = list(pool.map(lambda name:run(PUBLIC / f"test-{name}-protocol.json",profile),names))
    if any(status != 0 for status in statuses):
        return 3
    combine_phase(PUBLIC / "test-protocol.json")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run", "score", "select", "test"])
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--profile", default="pantry-recall")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "select":
        select()
    elif args.command == "test":
        return run_test(args.profile)
    else:
        if not args.protocol:
            parser.error("--protocol is required for run/score")
        if args.command == "run":
            return run(args.protocol, args.profile)
        score(args.protocol)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
