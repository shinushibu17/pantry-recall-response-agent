"""Frozen training-only SVM and category-balanced retrieval experiment for ST1."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

from tools import semeval_taxonomy as prior
from tools.semeval_product import TrainingRetriever, normalized_text, target_hash, digest, request_for

original = prior.original
ROOT, DATA, FIELDS, INVALID = prior.ROOT, prior.DATA, prior.FIELDS, prior.INVALID
PUBLIC = ROOT / "evaluation/semeval-st1-v6"
OUTPUT = ROOT / "outputs/semeval-st1-v6"
MODES = ("both", "hazard", "product", "margin")
VARIANTS = tuple(f"svm-{weight}-{mode}" for weight in ("standard", "balanced") for mode in MODES) + ("pro-balanced-retrieval",)


class BalancedRetriever(TrainingRetriever):
    """Product neighbors plus the nearest distinct body for each training hazard."""
    def examples(self, row):
        result = super().examples(row)
        used = {normalized_text(row["text"])}
        by_id = {r[""]: r for r in self.train}
        used.update(normalized_text(by_id[e["training_id"]]["text"]) for e in result)
        scores = (self.matrix @ self.vectorizer.transform([row["text"]]).T).toarray().ravel()
        # All categories get a representative even if already in product neighbors.
        # Existing neighbors remain intact; category samples are clearly identified.
        for category in sorted({r[FIELDS[0]] for r in self.train}):
            indices = sorted((i for i, r in enumerate(self.train) if r[FIELDS[0]] == category), key=lambda i: (-float(scores[i]), i))
            for i in indices:
                source = self.train[i]
                if scores[i] <= 0 or self.normalized[i] in used:
                    continue
                text = source["text"]
                limit = self.config["hazard_example_characters"]
                excerpt = text if len(text) <= limit else text[:limit-200] + "\n[...excerpt shortened...]\n" + text[-200:]
                result.append({"training_id": source[""], "similarity": float(scores[i]), "title": source["title"], "text": excerpt,
                    "annotated_product": source["product"], "annotated_hazard": source["hazard"],
                    "full_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "retrieval_role": "hazard_category_representative", **{f: source[f] for f in FIELDS}})
                used.add(self.normalized[i])
                break
        return result


class TrainingClassifier:
    def __init__(self, train, weight):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.svm import LinearSVC
        self.body = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=80000, sublinear_tf=True, strip_accents="unicode")
        self.title = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=80000, sublinear_tf=True, strip_accents="unicode")
        from scipy.sparse import hstack
        matrix = hstack([self.body.fit_transform([r["text"] for r in train]), 2*self.title.fit_transform([r["title"] for r in train])]).tocsr()
        self.models = {}
        for field in FIELDS:
            self.models[field] = LinearSVC(C=1, class_weight=None if weight == "standard" else "balanced", dual="auto", random_state=0, max_iter=5000).fit(matrix, [r[field] for r in train])

    def predict(self, rows):
        import numpy as np
        from scipy.sparse import hstack
        matrix = hstack([self.body.transform([r["text"] for r in rows]), 2*self.title.transform([r["title"] for r in rows])]).tocsr()
        scores = {f: model.decision_function(matrix) for f, model in self.models.items()}
        result = []
        for i, row in enumerate(rows):
            trace = {"id": row[""], "input_sha256": target_hash(row), "prediction": {}, "margins": {}, "decision_scores": {}}
            for f, model in self.models.items():
                values = scores[f][i]
                order = np.argsort(values, kind="stable")
                trace["prediction"][f] = str(model.classes_[order[-1]])
                trace["margins"][f] = float(values[order[-1]] - values[order[-2]])
                trace["decision_scores"][f] = dict(zip(map(str, model.classes_), map(float, values)))
            result.append(trace)
        return result


def combine(svm, incumbent, mode):
    result = dict(incumbent)
    for i, field in enumerate(FIELDS):
        if mode == "both" or mode == ("hazard" if i == 0 else "product") or (mode == "margin" and svm["margins"][field] >= 1.0):
            result[field] = svm["prediction"][field]
    return result


def select_best(results, incumbent):
    winner = max(VARIANTS, key=lambda name: (results[name]["official_st1_score"] or -1, -VARIANTS.index(name)))
    return winner, results[winner]["official_st1_score"] > incumbent["official_st1_score"]


def prepare():
    if (PUBLIC / "plan.json").exists():
        raise FileExistsError("Experiment already frozen")
    base, _ = prior.load_protocol(prior.PUBLIC / "validation-pro-taxonomy-protocol.json")
    prior.load_protocol(prior.PUBLIC / "test-protocol.json")
    hashes = dict(base["code_hashes"])
    for filename in ("tools/semeval_hybrid.py", "tests/test_semeval_hybrid.py"):
        hashes[filename] = original.sha(ROOT / filename)
    train = original.read_rows(DATA / "incidents_train.csv")
    validation = original.read_rows(DATA / "incidents_valid.csv")
    train_bodies = {normalized_text(r["text"]) for r in train}
    incumbent = json.loads((prior.PUBLIC / "validation-pro-taxonomy/results.json").read_text(encoding="utf-8"))
    inherited = {}
    for split, name in (("validation", "validation-pro-taxonomy"), ("test-regression", "test-regression-pro-taxonomy")):
        inherited[split] = {"directory": str((prior.OUTPUT / name).relative_to(ROOT)).replace("\\", "/"),
            "records": {p.name: original.sha(p) for p in sorted((prior.OUTPUT / name).glob("row-*.json"))}}
    plan = {"frozen_at": original.now(), "target": {"metric": "official_st1_score", "value": 0.9}, "candidates": list(VARIANTS),
        "selection": "Score all nine candidates once on all 565 validation rows. Highest unrounded ST1; ties prefer earlier listed candidate. Only a strict improvement on v5 validation authorizes one selected 997-row test regression. No test-based selection or gold-label changes.",
        "svm": "Two LinearSVC heads; C=1, dual=auto, random_state=0, max_iter=5000; class_weight=None or balanced. Training-only fit: body word TFIDF 1-2grams, min_df2, cap80000; title char_wb TFIDF 3-5grams, min_df2, cap80000, weight2; sublinear_tf and Unicode accents. Modes: both heads, hazard only, product only, or override each v5 head at top-two decision margin >=1.0. Margin is not probability. No threshold search.",
        "retrieval": "Unchanged four product neighbors plus nearest positive-body-similarity distinct training example from each hazard category; 900-character hazard excerpts. Exclude exact normalized target body and duplicate bodies per query. Nova Pro, unchanged full taxonomy and target title/body. Category-balanced examples do not estimate prevalence.",
        "duplicate_disclosure": {"validation_rows_with_exact_training_body": sum(normalized_text(r["text"]) in train_bodies for r in validation),
            "policy": "SVM fits the original training split, which contains exact-body overlaps with validation; it is not decontaminated. Retrieval excludes exact target bodies per query. Report overlap count on selected test if run."},
        "test_exposure": "Five prior test regressions exposed. This design used training counts and validation errors only. Repeated-validation development and exposed-test regression, not fresh held-out or official leaderboard evidence.",
        "incumbent_validation": incumbent, "inherited_predictions": inherited,
        "maximum_new_bedrock_classifications": 1562, "code_hashes": hashes, "source_hashes": base["source_hashes"]}
    original.write_json(PUBLIC / "plan.json", plan)
    for variant in VARIANTS:
        p = dict(base)
        p.update(frozen_at=original.now(), variant=variant, code_hashes=hashes, plan_sha256=original.sha(PUBLIC / "plan.json"),
            test_exposure=plan["test_exposure"], retrieval={**base["retrieval"], "hazard_example_characters": 900})
        if variant == "pro-balanced-retrieval":
            p["system_prompt"] += "\nExamples tagged hazard_category_representative are a balanced sample across training hazard categories, not evidence of target hazard or category frequency. Compare the specific recall cause, including rare category conventions; do not infer a cause from product identity."
        original.write_json(PUBLIC / f"validation-{variant}-protocol.json", p)
    print("Frozen eight supervised/hybrid candidates and one balanced-retrieval candidate", flush=True)


def load_protocol(path):
    p = json.loads(path.read_text(encoding="utf-8"))
    if original.sha(PUBLIC / "plan.json") != p["plan_sha256"]:
        raise ValueError("Plan changed")
    for file, sha in p["code_hashes"].items():
        if original.sha(ROOT / file) != sha:
            raise ValueError("Frozen code changed: " + file)
    for file, sha in p["source_hashes"].items():
        if original.sha(DATA / file) != sha:
            raise ValueError("Source changed: " + file)
    rows = original.read_rows(DATA / p["data_file"])
    if [r[""] for r in rows] != p["row_ids"]:
        raise ValueError("Split changed")
    return p, rows


def run_svm(paths):
    train = original.read_rows(DATA / "incidents_train.csv")
    plan = json.loads((PUBLIC / "plan.json").read_text(encoding="utf-8"))
    models, traces = {}, {}
    for path in paths:
        p, rows = load_protocol(path)
        _, weight, mode = p["variant"].split("-")
        directory = OUTPUT / f"{p['split']}-{p['variant']}"
        if (directory / "run.json").exists():
            raise FileExistsError("Supervised run already exists")
        started = original.now()
        if weight not in models:
            models[weight] = TrainingClassifier(train, weight)
        key = (p["split"], weight)
        if key not in traces:
            traces[key] = models[weight].predict(rows)
        source = plan["inherited_predictions"][p["split"]]
        trace_path = OUTPUT / f"{p['split']}-svm-{weight}-trace.json"
        original.write_json(trace_path, traces[key])
        for row, trace in zip(rows, traces[key]):
            filename = f"row-{row['']}.json"
            parent = ROOT / source["directory"] / filename
            if original.sha(parent) != source["records"][filename]:
                raise ValueError("Inherited prediction changed")
            saved = json.loads(parent.read_text(encoding="utf-8"))
            if saved["input_sha256"] != target_hash(row):
                raise ValueError("Inherited input mismatch")
            prediction = combine(trace, saved["prediction"], mode)
            original.write_json(directory / filename, {"id": row[""], "input_sha256": target_hash(row), "protocol_sha256": original.sha(path),
                "prediction": prediction, "status": "VALID" if all(prediction[f] in p["labels"][f] for f in FIELDS) else "INVALID_OUTPUT",
                "attempts": [], "svm_trace_sha256": digest(trace), "parent_sha256": original.sha(parent)})
        original.write_json(directory / "run.json", {"status": "COMPLETE", "started_at": started, "finished_at": original.now(), "rows": len(rows), "protocol_sha256": original.sha(path), "svm_trace_file": trace_path.name, "svm_trace_sha256": original.sha(trace_path), "new_bedrock_calls": 0})
        score(path)


def run_bedrock(path, profile):
    from botocore.config import Config
    from pantry_recall.aws_access import session_for
    p, rows = load_protocol(path)
    directory = OUTPUT / f"{p['split']}-{p['variant']}"
    directory.mkdir(parents=True, exist_ok=True)
    runpath = directory / "run.json"
    metadata = json.loads(runpath.read_text(encoding="utf-8")) if runpath.exists() else {"started_at": original.now(), "protocol_sha256": original.sha(path), "rows": len(rows)}
    if metadata["protocol_sha256"] != original.sha(path):
        raise ValueError("Run protocol changed")
    original.write_json(runpath, metadata)
    retriever = BalancedRetriever(original.read_rows(DATA / "incidents_train.csv"), p["retrieval"])
    examples = [retriever.examples(row) for row in rows]
    client = session_for(profile, p["region"]).client("bedrock-runtime", config=Config(connect_timeout=10, read_timeout=60, retries={"total_max_attempts": 1}, max_pool_connections=4))
    with ThreadPoolExecutor(max_workers=p["workers"]) as executor:
        for start in range(0, len(rows), p["workers"]):
            batch = list(executor.map(lambda pair: prior.classify(client, pair[0], p, original.sha(path), pair[1], directory), zip(rows[start:start+p["workers"]], examples[start:start+p["workers"]])))
            count = start+len(batch)
            fatal = any(r.get("fatal_error") and not r.get("_cached") for r in batch)
            if count % 40 == 0 or count == len(rows) or fatal:
                print(f"{p['split']}-{p['variant']}: {count}/{len(rows)} persisted", flush=True)
            if fatal:
                metadata.update(status="BLOCKED", stopped_at=original.now())
                original.write_json(runpath, metadata)
                return 2
    metadata.update(status="COMPLETE", finished_at=original.now())
    original.write_json(runpath, metadata)
    score(path)
    return 0


def score(path):
    import numpy as np
    from sklearn.metrics import f1_score, classification_report
    p, rows = load_protocol(path)
    directory = OUTPUT / f"{p['split']}-{p['variant']}"
    records = [json.loads((directory / f"row-{r['']}.json").read_text(encoding="utf-8")) for r in rows]
    for row, record in zip(rows, records):
        if (record["id"], record["input_sha256"], record["protocol_sha256"]) != (row[""], target_hash(row), original.sha(path)):
            raise ValueError("Record binding mismatch")
    ht, pt = (np.array([r[f] for r in rows]) for f in FIELDS)
    hp, pp = (np.array([r["prediction"][f] for r in records]) for f in FIELDS)
    mask = ht == hp
    usage = Counter()
    for record in records:
        for attempt in record["attempts"]:
            usage.update({k: v for k, v in attempt.get("usage", {}).items() if isinstance(v, (int, float))})
    result = {"execution_status": "COMPLETE", "scored_at": original.now(), "split": p["split"], "variant": p["variant"], "rows": len(rows),
        "official_st1_score": float(original.official_score(ht, pt, hp, pp)) if mask.any() else None,
        "hazard_macro_f1": float(f1_score(ht, hp, average="macro")), "product_macro_f1_on_hazard_correct_rows": float(f1_score(pt[mask], pp[mask], average="macro")) if mask.any() else None,
        "hazard_accuracy": float(np.mean(mask)), "product_accuracy": float(np.mean(pt == pp)), "joint_accuracy": float(np.mean(mask & (pt == pp))), "hazard_correct_rows": int(mask.sum()),
        "valid_outputs": sum(r["status"] == "VALID" for r in records), "invalid_outputs": sum(r["status"] == "INVALID_OUTPUT" for r in records), "error_rows": sum(r["status"] == "ERROR" for r in records),
        "model_attempts": sum(len(r["attempts"]) for r in records), "reported_usage": dict(usage),
        "per_category": {f: classification_report(t, pred, output_dict=True, zero_division=0) for f, t, pred in zip(FIELDS, (ht, pt), (hp, pp))},
        "protocol_sha256": original.sha(path), "test_exposure": p["test_exposure"]}
    original.write_json(directory / "results.json", result)
    print(json.dumps({k: result[k] for k in ("split", "variant", "official_st1_score", "hazard_accuracy", "product_accuracy", "error_rows")}), flush=True)
    return result


def select():
    if (PUBLIC / "decision.json").exists():
        raise FileExistsError("Selection already frozen")
    results = {v: score(PUBLIC / f"validation-{v}-protocol.json") for v in VARIANTS}
    plan = json.loads((PUBLIC / "plan.json").read_text(encoding="utf-8"))
    winner, improved = select_best(results, plan["incumbent_validation"])
    original.write_json(PUBLIC / "decision.json", {"decided_at": original.now(), "winner": winner, "improved_on_validation": improved,
        "candidate_scores": {k: v["official_st1_score"] for k, v in results.items()}, "incumbent_score": plan["incumbent_validation"]["official_st1_score"], "plan_sha256": original.sha(PUBLIC / "plan.json")})
    if improved:
        p, _ = load_protocol(PUBLIC / f"validation-{winner}-protocol.json")
        rows = original.read_rows(DATA / "incidents_test.csv")
        p.update(frozen_at=original.now(), split="test-regression", data_file="incidents_test.csv", row_ids=[r[""] for r in rows], decision_sha256=original.sha(PUBLIC / "decision.json"))
        original.write_json(PUBLIC / "test-protocol.json", p)
    print(f"Selected {winner}; improved={improved}", flush=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("command", choices=("prepare", "svm-validation", "run", "select", "score"))
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--profile", default="pantry-recall")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "svm-validation":
        run_svm([PUBLIC / f"validation-{v}-protocol.json" for v in VARIANTS if v.startswith("svm-")])
    elif args.command == "select":
        select()
    elif args.command == "score":
        score(args.protocol)
    else:
        p, _ = load_protocol(args.protocol)
        if p["variant"].startswith("svm-"):
            run_svm([args.protocol])
        else:
            return run_bedrock(args.protocol, args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
