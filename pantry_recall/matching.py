"""Conservative deterministic comparisons for the single reviewed fixture.

Candidate discovery never supplies a disposition. No fuzzy identifier matching,
model calls, external actions, persisted tasks, or human-confirmation boundary.
"""

from copy import deepcopy
from datetime import date
import re

from .fixtures import row_digest, validate_instructions, validate_inventory, validate_scope


def words(value: str | None) -> str | None:
    return " ".join(value.casefold().split()) if value is not None else None


def printed_upc(value: str | None) -> str | None:
    return "".join(value.split()) if value is not None else None


def code_date(value: str | None) -> date | None:
    # Literal named-month grammar, including the manufacturing suffix. No repair.
    match = re.fullmatch(r"BBD ([A-Z]{3}) (\d{2}) (\d{2}) ([A-Z])", value or "")
    if not match:
        return None
    months = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
    try:
        return date(2000 + int(match[3]), months.index(match[1]) + 1, int(match[2]))
    except ValueError:
        return None


def find_candidate(row: dict, scope: dict) -> dict:
    if scope.get("profile") == "jif_16oz_creamy_2022":
        from .jif import find_jif_candidate
        return find_jif_candidate(row, scope)
    variant = scope["variant"]
    name = words(row["product_name"])
    tokens = set(re.findall(r"[a-z]+", name or ""))
    brand_matches = words(row["brand"]) == words(variant["brand"])
    features = []
    if printed_upc(row["upc"]) == printed_upc(variant["upc"]):
        features.append("printed_upc")
    if name in {words(variant["product_name"]), words(variant["brand"] + " " + variant["product_name"])}:
        features.append("product_name")
    if brand_matches and tokens & {"pancake", "waffle"}:
        features.append("brand_and_category")
    if {"pancake", "waffle", "mix"} <= tokens:
        features.append("category_words")
    if name is None:
        features.append("missing_product_identity")
    return {"included": bool(features), "features": features, "basis": "policy.candidate"}


def compare_scope(row: dict, scope: dict, policy: dict, inventory_version: str,
                  record: dict) -> dict:
    """Return condition evidence and a reviewable proposal; never mutate stock."""
    if scope.get("profile") == "jif_16oz_creamy_2022":
        from .jif import compare_jif
        return compare_jif(row, scope, policy, inventory_version, record)
    validate_inventory({"version": inventory_version, "rows": [row]})
    validate_instructions(scope)
    variant = scope["variant"]
    inventory_ref = f"inventory:{inventory_version}:{row['inventory_id']}"
    conditions = {}

    def condition(field, truth, reason, normalized, expected, source_refs=None):
        conditions[field] = {
            "truth": truth, "reason": reason, "raw": row[field],
            "normalized": normalized, "expected": expected,
            "evidence_refs": (source_refs or ["notice.product_table"]) + [f"{inventory_ref}#{field}"],
        }

    # Only reviewed names establish identity or an identity mismatch. A typo or
    # unfamiliar alias remains unknown, regardless of text similarity.
    for field in ("brand", "product_name"):
        observed, expected = words(row[field]), words(variant[field])
        alternatives = {expected}
        if field == "product_name":
            alternatives.add(words(variant["brand"] + " " + variant[field]))
        if observed is None:
            truth, reason = "unknown", "missing"
        elif observed in alternatives:
            truth, reason = "true", "reviewed_identity"
        elif field == "product_name" and observed in {words(p) for p in policy["reviewed_other_product_names"]}:
            truth, reason = "false", "reviewed_different_variant"
        else:
            truth, reason = "unknown", "unrecognized_identity"
        refs = ["notice.product_table", "notice.other_products"] if truth == "false" else None
        condition(field, truth, reason, observed, expected, refs)

    size = words(row["package_size"])
    if size is None:
        truth, reason, normalized = "unknown", "missing", None
    elif size in {words(variant["package_size"]), "32 oz", "2 lb", "907g", "907 g"}:
        truth, reason, normalized = "true", "reviewed_size", "32 oz"
    elif re.fullmatch(r"[1-9]\d* oz", size):
        truth, reason, normalized = "false", "different_explicit_size", size
    else:
        truth, reason, normalized = "unknown", "unrecognized_size", size
    condition("package_size", truth, reason, normalized, variant["package_size"])

    upc, expected_upc = printed_upc(row["upc"]), printed_upc(variant["upc"])
    if upc is None:
        truth, reason = "unknown", "missing"
    elif upc == expected_upc:
        truth, reason = "true", "same_printed_upc"
    elif re.fullmatch(r"\d{" + str(len(expected_upc)) + r"}", upc):
        truth, reason = "false", "different_printed_upc"
    else:
        truth, reason = "unknown", "unverified_upc_representation"
    condition("upc", truth, reason, upc, expected_upc)

    lot = row["best_by_manufacturing_code"]
    if lot is None:
        truth, reason = "unknown", "missing"
    elif code_date(lot) is None:
        truth, reason = "unknown", "unrecognized_complete_code"
    else:
        truth = "true" if lot in variant["best_by_manufacturing_codes"] else "false"
        reason = "bounded_code_member" if truth == "true" else "outside_bounded_code_list"
    condition("best_by_manufacturing_code", truth, reason, lot, variant["best_by_manufacturing_codes"])

    complete = row["stock_group"] == "single_code_group" and row["label_coverage"] == "all_units"
    condition("stock_group", "true" if complete else "unknown",
              "entire_group_checked" if complete else "inspect_and_split_entire_group",
              {"stock_group": row["stock_group"], "label_coverage": row["label_coverage"]},
              {"stock_group": "single_code_group", "label_coverage": "all_units"}, ["policy.stock_coverage"])
    conditions["stock_group"]["evidence_refs"].append(f"{inventory_ref}#label_coverage")

    missing = sorted(field for field, c in conditions.items() if c["reason"] == "missing")
    if not complete:
        missing.append("stock_group")
    review = sorted(field for field, c in conditions.items()
                    if c["truth"] == "unknown" and c["reason"] not in {"missing", "inspect_and_split_entire_group"})
    issues = validate_scope(scope, record)
    # Positive UPC evidence contradicting a known different variant/package, or
    # a different UPC on the otherwise matching variant, needs human review.
    identity = [conditions[f]["truth"] for f in ("brand", "product_name", "package_size")]
    if ((conditions["upc"]["truth"] == "true" and "false" in identity)
            or (all(t == "true" for t in identity) and conditions["upc"]["truth"] == "false")):
        review.append("upc")
        issues.append("Printed UPC conflicts with the transcribed product identity")
    if row["best_by_date"] is not None:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["best_by_date"]):
                raise ValueError("Ambiguous date representation")
            best_by = date.fromisoformat(row["best_by_date"])
            if code_date(lot) is not None and best_by != code_date(lot):
                raise ValueError("Best-by transcription contradicts the complete printed code")
        except ValueError as error:
            review.append("best_by_date")
            issues.append(str(error))

    return finish_comparison(row, scope, policy, inventory_version, conditions, missing, review, issues)


def finish_comparison(row, scope, policy, inventory_version, conditions, missing, review, issues,
                      inspection_instruction="Inspect every unit's front label and full top-panel BBD/manufacturing code; split mixed-code groups."):
    """Shared policy transitions; source adapters supply evidence, never a model verdict."""
    inventory_ref = f"inventory:{inventory_version}:{row['inventory_id']}"
    proposed = None
    if issues or review:
        state, action, task_type = "NEEDS_REVIEW", "HOLD_RECOMMENDED", "REVIEW_SCOPE"
    elif missing:
        state, action, task_type = "NEEDS_EVIDENCE", "HOLD_RECOMMENDED", "IDENTIFY_STOCK"
    elif any(c["truth"] == "false" for c in conditions.values()):
        state, action, task_type = "NEEDS_REVIEW", "REVIEW_REQUIRED", "REVIEW_SCOPE"
        proposed = "NOT_AFFECTED_BY_THIS_RECALL"
    else:
        state, action, task_type = "AFFECTED", "HOLD_RECOMMENDED", "PERFORM_ACTION"
    basis = "policy.exclusion_review" if proposed else "policy.hold"
    scope_refs = list(scope.get("scope_refs", ["notice.product_table"]))
    if proposed and "scope_refs" not in scope:
        scope_refs.append("notice.other_products")
    task = {
        "type": task_type, "status": "OPEN", "draft_only": True,
        "inventory_id": row["inventory_id"], "inventory_version": inventory_version,
        "quantity": row["quantity"], "unit": row["unit"], "location": row["storage_location"],
        "fields": sorted(set(missing + review)), "basis": basis,
        "instruction": (
            inspection_instruction
            if task_type == "IDENTIFY_STOCK" else
            "Review this recall-specific exclusion proposal; acceptance does not authorize distribution."
            if proposed else
            "Review the ambiguous or contradictory evidence and original source."
            if task_type == "REVIEW_SCOPE" else
            "Hold the specified stock pending human review; physical action remains unconfirmed."
        ),
        "evidence_refs": [basis, *scope_refs, inventory_ref],
    }
    if task_type == "IDENTIFY_STOCK":
        task["evidence_refs"].append(scope.get("label_location_ref", "notice.label_location"))
    return {
        "inventory_id": row["inventory_id"], "recall_number": scope["recall_number"],
        "recall_version": scope["version"],
        "inventory_evidence": {"id": inventory_ref, "version": inventory_version, "sha256": row_digest(row), "raw": deepcopy(row)},
        "conditions": conditions, "identification_state": state,
        "proposed_identification_state": proposed, "missing_fields": sorted(set(missing)),
        "review_fields": sorted(set(review)), "issues": issues,
        "context_evidence_refs": [*scope.get("context_evidence_refs", ["notice.purchase_availability", "notice.distribution"]), f"{inventory_ref}#received_date"],
        "action_state": action, "task": task,
        "recommendation": {
            "action": "Review proposed recall-specific exclusion" if proposed else "Hold stock pending review",
            "issuer": policy["issuer"], "basis": basis,
            "audience": "fictional pantry volunteers", "trigger": state,
            "human_must_confirm": "Stock group, evidence version, quantity and unit; no action is confirmed by this comparison.",
            "evidence_refs": [basis, *scope_refs, inventory_ref] if proposed else [basis, inventory_ref],
        },
        "published_instructions": deepcopy(scope["instructions"]),
    }


def evaluate_inventory(fixture: dict, inventory: dict | None = None) -> list[dict]:
    inventory = inventory if inventory is not None else fixture["inventory"]
    validate_inventory(inventory)
    scope, policy = fixture["scope"], fixture["policy"]
    results = []
    for row in inventory["rows"]:
        candidate = find_candidate(row, scope)
        if candidate["included"]:
            result = compare_scope(row, scope, policy, inventory["version"], fixture["record"])
        else:
            result = {
                "inventory_id": row["inventory_id"], "recall_number": scope["recall_number"], "recall_version": scope["version"],
                "inventory_evidence": {"id": f"inventory:{inventory['version']}:{row['inventory_id']}", "version": inventory["version"], "sha256": row_digest(row), "raw": deepcopy(row)},
                "conditions": {}, "identification_state": "PENDING",
                "proposed_identification_state": None, "missing_fields": [], "review_fields": [],
                "issues": [], "action_state": "NOT_ASSESSED", "task": None,
                "recommendation": None, "published_instructions": [],
            }
        result["candidate"] = candidate
        result["candidate"]["evidence_refs"] = ["policy.candidate", "notice.product_table", result["inventory_evidence"]["id"]]
        results.append(result)
    return results
