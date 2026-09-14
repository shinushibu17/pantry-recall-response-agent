"""Frozen ST1 capacity comparison: eight Lite examples versus four Pro examples."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from tools import semeval_product as previous
from tools.semeval_product import digest, target_hash, TrainingRetriever, request_for, parse_tool

original = previous.original
ROOT, DATA, FIELDS, INVALID = previous.ROOT, previous.DATA, previous.FIELDS, previous.INVALID
PUBLIC = ROOT / "evaluation/semeval-st1-v4"
OUTPUT = ROOT / "outputs/semeval-st1-v4"
VARIANTS = ("lite-eight", "pro-four")


def candidates(incumbent):
    """Change only example count or model, leaving the existing prompt intact."""
    result = {}
    for variant in VARIANTS:
        p = json.loads(json.dumps(incumbent))
        p["variant"] = variant
        p["model_id"] = "amazon.nova-lite-v1:0" if variant == "lite-eight" else "amazon.nova-pro-v1:0"
        p["retrieval"]["neighbors"] = 8 if variant == "lite-eight" else 4
        result[variant] = p
    return result


def choose(results, incumbent_score):
    def rank(variant):
        r = results[variant]
        return (-1 if r["official_st1_score"] is None else r["official_st1_score"],
                -r["invalid_outputs"]-r["error_rows"], variant == "lite-eight")
    winner = max(VARIANTS, key=rank)
    value = results[winner]["official_st1_score"]
    return winner, value is not None and value > incumbent_score


def prepare():
    if (PUBLIC / "plan.json").exists():
        raise FileExistsError("Development plan already frozen")
    base, _ = previous.load_protocol(previous.PUBLIC / "test-protocol.json")
    for item in json.loads((previous.PUBLIC / "publication-manifest.json").read_text(encoding="utf-8"))["artifacts"]:
        if original.sha(previous.PUBLIC / item["path"]) != item["sha256"]:
            raise ValueError("Prior archived artifact changed: " + item["path"])
    incumbent_path = previous.PUBLIC / "validation-title-weighted/results.json"
    incumbent = json.loads(incumbent_path.read_text(encoding="utf-8"))
    rows = original.read_rows(DATA / "incidents_valid.csv")
    plan = {"frozen_at": original.now(), "candidates": list(VARIANTS),
            "incumbent_validation_score": incumbent["official_st1_score"],
            "incumbent_report_sha256": original.sha(incumbent_path),
            "selection_rule": "Run both candidates once on all 565 validation reports. Highest unrounded official ST1 score; tie: fewer invalid/error rows, then lite-eight. Only if strictly above the v3 incumbent, freeze one test regression run; otherwise retain v3 without another test run.",
            "candidate_changes": {"lite-eight": "Nova Lite, eight title-weighted examples instead of four", "pro-four": "Nova Pro, four title-weighted examples, unchanged prompt"},
            "validation_count": len(rows), "validation_ids": [r[""] for r in rows],
            "maximum_logical_classifications": 2127,
            "test_exposure": "All three earlier test results have been seen. This design inspected validation errors only. Any new test run is another exposed-test regression, not fresh held-out evidence. No test selection of prompts, models or row subsets."}
    original.write_json(PUBLIC / "plan.json", plan)
    for variant, p in candidates(base).items():
        p.pop("selection_evidence", None)
        p.update(frozen_at=original.now(), split="validation", data_file="incidents_valid.csv",
                 row_ids=plan["validation_ids"], plan_sha256=original.sha(PUBLIC / "plan.json"),
                 test_exposure=plan["test_exposure"],
                 code_hashes={"tools/semeval_capacity.py": original.sha(Path(__file__)),
                              "tools/semeval_product.py": original.sha(Path(previous.__file__)),
                              "tools/semeval_eval.py": original.sha(Path(original.__file__)),
                              "tests/test_semeval_capacity.py": original.sha(ROOT / "tests/test_semeval_capacity.py"),
                              "uv.lock": original.sha(ROOT / "uv.lock")})
        original.write_json(PUBLIC / f"validation-{variant}-protocol.json", p)
    print("Frozen two capacity candidates on all 565 validation reports", flush=True)


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
        connect_timeout=10, read_timeout=60, retries={"total_max_attempts": 1}, max_pool_connections=4))
    with ThreadPoolExecutor(max_workers=4) as executor:
        for start in range(0, len(rows), 4):
            batch = list(executor.map(lambda pair: classify(client, pair[0], protocol, original.sha(protocol_path), pair[1], directory), zip(rows[start:start+4], examples[start:start+4])))
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
            usage.update(attempt.get("usage", {}))
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
    winner, improved = choose(results, plan["incumbent_validation_score"])
    original.write_json(PUBLIC / "decision.json", {"decided_at": original.now(), "winner": winner,
        "improved_on_validation": improved, "incumbent_validation_score": plan["incumbent_validation_score"],
        "candidate_scores": {v: results[v]["official_st1_score"] for v in VARIANTS}, "plan_sha256": original.sha(PUBLIC / "plan.json")})
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
