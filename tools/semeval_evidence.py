"""Evidence-first classification, bounded by the user's 5 p.m. Eastern cutoff."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from datetime import datetime, timezone
from tools import semeval_taxonomy as previous
from tools.semeval_product import digest, target_hash, TrainingRetriever, request_for as base_request, parse_tool as base_parse, tool_config

original = previous.original
ROOT, DATA, FIELDS, INVALID = previous.ROOT, previous.DATA, previous.FIELDS, previous.INVALID
PUBLIC = ROOT / "evaluation/semeval-st1-v7"
OUTPUT = ROOT / "outputs/semeval-st1-v7"
VARIANTS = ("pro-evidence", "nova2-low-evidence")
CUTOFF = datetime(2026, 9, 14, 21, 0, tzinfo=timezone.utc)
TEST_START_CUTOFF = datetime(2026, 9, 14, 20, 35, tzinfo=timezone.utc)


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


def evidence_tool_config(labels):
    config = tool_config(labels)
    schema = config["tools"][0]["toolSpec"]["inputSchema"]["json"]
    schema["properties"] = {"product_description": {"type": "string", "minLength": 1, "maxLength": 500},
        "hazard_description": {"type": "string", "minLength": 1, "maxLength": 500}, **schema["properties"]}
    schema["required"] = ["product_description", "hazard_description", "hazard_id", "product_id"]
    config["tools"][0]["toolSpec"]["description"] = "Identify the affected food and stated recall cause in brief evidence-grounded phrases; then submit the category IDs."
    return config


def parse_tool(response, labels):
    calls = [b["toolUse"] for b in response["output"]["message"]["content"] if "toolUse" in b]
    if len(calls) != 1:
        raise ValueError("Exactly one classification required")
    values = calls[0].get("input")
    if not isinstance(values, dict) or set(values) != {"product_description", "hazard_description", "hazard_id", "product_id"}:
        raise ValueError("Expected evidence descriptions and category IDs")
    for key in ("product_description", "hazard_description"):
        if not isinstance(values[key], str) or not values[key].strip() or len(values[key]) > 500:
            raise ValueError("Invalid evidence description")
    reduced = {"stopReason": response.get("stopReason"), "output": {"message": {"content": [
        {"toolUse": {**calls[0], "input": {k: values[k] for k in ("hazard_id", "product_id")}}}]}}}
    return base_parse(reduced, labels)


def request_for(row, protocol, examples):
    request = base_request(row, protocol, examples)
    if protocol.get("additional_model_request_fields"):
        request["additionalModelRequestFields"] = protocol["additional_model_request_fields"]
    return request


def choose(results, incumbent):
    winner = max(VARIANTS, key=lambda name: (results[name]["official_st1_score"] or -1, -VARIANTS.index(name)))
    value = results[winner]["official_st1_score"]
    return winner, value is not None and value >= incumbent["official_st1_score"] + 0.005


def prepare():
    if (PUBLIC / "plan.json").exists():
        raise FileExistsError("Development plan already frozen")
    base, _ = previous.load_protocol(previous.PUBLIC / "validation-pro-taxonomy-protocol.json")
    for folder in ("semeval-st1", "semeval-st1-v2", "semeval-st1-v3", "semeval-st1-v4", "semeval-st1-v5", "semeval-st1-v6"):
        directory = ROOT / "evaluation" / folder
        for item in json.loads((directory / "publication-manifest.json").read_text(encoding="utf-8"))["artifacts"]:
            if original.sha(directory / item["path"]) != item["sha256"]:
                raise ValueError("Archived evidence changed")
    incumbent_path = previous.PUBLIC / "validation-pro-taxonomy/results.json"
    incumbent = json.loads(incumbent_path.read_text(encoding="utf-8"))
    rows = original.read_rows(DATA / "incidents_valid.csv")
    labels, guidance = taxonomy(original.read_rows(DATA / "incidents_train.csv"))
    assert labels == base["labels"]
    # Keep v5 evidence/taxonomy instructions, replacing only the response instruction.
    instructions = base["system_prompt"].replace(
        "Submit exactly one classify_incident tool call with the two integer category IDs. Do not explain, invent category names, or submit physical-action instructions.",
        "Submit exactly one classify_incident tool call. First fill product_description with a brief description of the concrete recalled food, and hazard_description with the reported reason for recall. These are concise evidence extractions from the target title/body, not invented facts or copied neighbor conclusions. If a cause is not stated, describe that missing evidence honestly. Then assign the two integer category IDs using the supplied training taxonomy and examples. Use the specific stated cause rather than a generic potential consequence. Avoid category-name invention or physical-action instructions.")
    assert instructions != base["system_prompt"]
    plan = {"frozen_at": original.now(), "candidates": list(VARIANTS), "target": {"metric": "official_st1_score", "value": 0.9},
        "incumbent_validation_metrics": {k: incumbent[k] for k in ("official_st1_score", "hazard_accuracy", "product_accuracy")},
        "selection_rule": "Run both fixed candidates on all 565 validation rows. Highest unrounded ST1, ties prefer Pro. Only a gain of at least 0.005 over v5 validation authorizes a single 997-row test regression, and only if selected by 20:35 UTC. Partial runs are incomplete and cannot win or replace a complete score. Do not change denominators, labels or examples after scores. User cutoff 21:00 UTC (5 p.m. Eastern); no new calls or retries after cutoff. In-flight calls may finish and are preserved. No model changes deployed to pantry app.",
        "candidate_changes": "Evidence-first structured extraction before category IDs. Nova Pro (temperature0, maxTokens2048) vs Nova2 Lite low extended thinking (temperature0,maxTokens4096). Four unchanged v5 training-only examples and complete training taxonomy; no SVM or balanced retrieval. Four workers per model. Strict four-field tool schema; invalid outputs map both categories to original sentinel, without content retries.",
        "validation_count": len(rows), "validation_ids": [r[""] for r in rows], "maximum_logical_classifications": 2127,
        "cutoff_utc": CUTOFF.isoformat(), "test_launch_cutoff_utc": TEST_START_CUTOFF.isoformat(),
        "test_exposure": "All six prior test regressions exposed. V6 supervised candidate regressed after a negligible validation gain; this design therefore requires a pre-frozen 0.005 validation gain. No new test-row error examples used. Repeated validation and exposed-test regression, not fresh held-out or leaderboard evidence.",
        "reasoning_documentation": "https://docs.aws.amazon.com/nova/latest/nova2-userguide/extended-thinking.html"}
    original.write_json(PUBLIC / "plan.json", plan)
    hashes = dict(base["code_hashes"])
    hashes.update({"tools/semeval_evidence.py": original.sha(Path(__file__)), "tests/test_semeval_evidence.py": original.sha(ROOT / "tests/test_semeval_evidence.py")})
    for variant in VARIANTS:
        p = dict(base)
        p.update(frozen_at=original.now(), variant=variant, system_prompt=instructions, tool_config=evidence_tool_config(labels),
            code_hashes=hashes, plan_sha256=original.sha(PUBLIC / "plan.json"), test_exposure=plan["test_exposure"], workers=4,
            inference_config={"temperature":0, "maxTokens":2048 if variant == "pro-evidence" else 4096},
            model_id="amazon.nova-pro-v1:0" if variant == "pro-evidence" else "us.amazon.nova-2-lite-v1:0",
            additional_model_request_fields={} if variant == "pro-evidence" else {"reasoningConfig":{"type":"enabled","maxReasoningEffort":"low"}},
            invalid_policy="Exactly one completed classify_incident call with two nonempty <=500-character evidence description strings and two in-range integer IDs; no extra fields, repair or content retry. Evidence descriptions are model-generated, not independently verified quotations.")
        original.write_json(PUBLIC / f"validation-{variant}-protocol.json", p)
    print("Frozen two evidence-first candidates; hard cutoff 21:00 UTC", flush=True)


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
        connect_timeout=10, read_timeout=120, retries={"total_max_attempts": 1}, max_pool_connections=4))
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


def select():
    target = PUBLIC / "test-protocol.json"
    if target.exists():
        raise FileExistsError("Winner and test protocol already frozen")
    results = {v: score(PUBLIC / f"validation-{v}-protocol.json") for v in VARIANTS}
    plan = json.loads((PUBLIC / "plan.json").read_text(encoding="utf-8"))
    winner, improved = choose(results, plan["incumbent_validation_metrics"])
    original.write_json(PUBLIC / "decision.json", {"decided_at": original.now(), "winner": winner,
        "improved_on_validation": improved, "incumbent_validation_metrics": plan["incumbent_validation_metrics"],
        "product_accuracy": {name: r["product_accuracy"] for name, r in results.items()},
        "hazard_accuracy": {name: r["hazard_accuracy"] for name, r in results.items()},
        "candidate_scores": {v: results[v]["official_st1_score"] for v in VARIANTS}, "plan_sha256": original.sha(PUBLIC / "plan.json")})
    if datetime.now(timezone.utc) >= TEST_START_CUTOFF:
        print("Test launch cutoff reached; retain completed validation evidence only", flush=True)
        return
    if not improved:
        print("Neither candidate beats the incumbent; no new test run authorized by this plan.", flush=True)
        return
    protocol, _ = load_protocol(PUBLIC / f"validation-{winner}-protocol.json")
    rows = original.read_rows(DATA / "incidents_test.csv")
    protocol.update(frozen_at=original.now(), split="test-regression", data_file="incidents_test.csv", row_ids=[r[""] for r in rows],
                    selection_evidence={v: {"score": results[v]["official_st1_score"], "sha256": original.sha(OUTPUT / f"validation-{v}/results.json")} for v in VARIANTS})
    original.write_json(target, protocol)
    print("Frozen validation-selected test candidate: " + winner, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run", "score", "select"])
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--profile", default="pantry-recall")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "select":
        select()
    else:
        if not args.protocol:
            parser.error("--protocol is required for run/score")
        if args.command == "run":
            return run(args.protocol, args.profile)
        score(args.protocol)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
