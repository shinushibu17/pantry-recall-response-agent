"""Reviewed Jif source adapter, limited to the 16-ounce creamy variant.

Other variants remain review items. This is an explicit adapter, not automated
scope extraction or a claim that the existing matcher generalized blindly.
"""

import re

from .fixtures import FixtureError, validate_inventory


VARIANT = {"brand": "Jif", "product_name": "Creamy Peanut Butter", "package_size": "16 oz", "upc": "5150025516",
           "code_scope": "prefix_range_and_plant", "lot_rule": {"prefix_digits": 4, "minimum": 1274, "maximum": 2140, "following_digits": "425"}}
LOT_QUOTE = "In the lot code, if the first four digits are between 1274 and 2140, and if the next three numbers after that are '425', this product has been recalled and you should not consume this product."
CONSUMER_QUOTE = "If consumers have products matching the above description in their possession, they should dispose of it immediately."
RETAILER_QUOTE = "Do not sell or serve recalled peanut butter or products containing recalled peanut butter."
CLEANING_QUOTE = "FDA recommends that if you have used the recalled Jif brand peanut butter that have lot code numbers 1274425 through 2140425 and the first seven digits end with 425, you should wash and sanitize surfaces and utensils that could have touched the peanut butter."
INSTRUCTIONS = [
    {"id": "consumer_disposal", "action": "Dispose of the recalled product immediately.", "audience": "consumers", "trigger": "The consumer possesses a product matching the recalled description and lot conditions.", "issuer": "The J. M. Smucker Co.", "source_kind": "company_announcement_hosted_by_fda_archived", "evidence_refs": ["notice.consumer_instruction"], "automatic_pantry_instruction": False},
    {"id": "retailer_nonservice", "action": RETAILER_QUOTE, "audience": "retailers, re-packers, and manufacturers", "trigger": "The product is recalled peanut butter or contains recalled peanut butter.", "issuer": "FDA", "source_kind": "fda_guidance", "evidence_refs": ["guidance.retailer_instruction"], "automatic_pantry_instruction": False},
    {"id": "conditional_cleaning", "action": "Wash and sanitize surfaces and utensils that could have touched the recalled peanut butter.", "audience": "consumers; retailers, re-packers, and manufacturers via the steps above", "trigger": "The recalled Jif peanut butter was used, and surfaces or utensils could have touched it.", "issuer": "FDA", "source_kind": "fda_guidance", "evidence_refs": ["guidance.cleaning_instruction"], "automatic_pantry_instruction": False},
]


def validate_jif_instructions(scope):
    if scope["instructions"] != INSTRUCTIONS:
        raise FixtureError("Unsupported Jif instruction, audience, condition, or attribution")
    for evidence_id, quote in [("notice.consumer_instruction", CONSUMER_QUOTE), ("guidance.retailer_instruction", RETAILER_QUOTE), ("guidance.cleaning_instruction", CLEANING_QUOTE)]:
        if scope["evidence"][evidence_id]["quote"] != quote:
            raise FixtureError("Jif instruction lacks its reviewed supporting quotation")


def validate_jif_scope(scope, record):
    issues = []
    if scope["review"]["scope_status"] != "reviewed" or scope["variant"] != VARIANT:
        issues.append("Unsupported or unreviewed Jif scope; only the pinned 16-ounce creamy projection is implemented")
    expected_quotes = {"notice.product_table": "JIF 16 OUNCE CREAMY PEANUT BUTTER 5150025516",
                       "notice.lot_scope": "Recalled products include the products below with lot codes 1274425 \u2013 2140425.",
                       "guidance.lot_rule": LOT_QUOTE}
    if any(scope["evidence"][key]["quote"] != quote for key, quote in expected_quotes.items()):
        issues.append("Jif scope does not reproduce its source table and complete FDA lot restriction")
    if (record["recall_number"] != "F-1107-2022" or record["event_id"] != "90255"
            or not all(token in record["product_description"] for token in ["JIF CREAMY PEANUT BUTTER", "16oz"])
            or not all(token in record["code_info"] for token in ["1274425", "2140425", "5150025516"])):
        issues.append("Selected enforcement product or lot evidence conflicts with the reviewed notice projection")
    return issues


def lot_truth(value, rule):
    if value is None:
        return "unknown", "missing"
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{7,}", value):
        return "unknown", "unrecognized_lot_code"
    # FDA describes positions, not a numeric interval for the complete string.
    matched = rule["minimum"] <= int(value[:4]) <= rule["maximum"] and value[4:7] == rule["following_digits"]
    return ("true", "prefix_and_plant_match") if matched else ("false", "outside_compound_lot_scope")


def find_jif_candidate(row, scope):
    from .matching import printed_upc, words
    name = words(row["product_name"])
    tokens = set(re.findall(r"[a-z]+", name or ""))
    features = []
    if printed_upc(row["upc"]) == scope["variant"]["upc"]:
        features.append("printed_upc")
    if name in {"creamy peanut butter", "jif creamy peanut butter"}:
        features.append("product_name")
    if {"peanut", "butter"} <= tokens:
        features.append("category_words")
    if name is None:
        features.append("missing_product_identity")
    return {"included": bool(features), "features": features, "basis": "policy.candidate"}


def compare_jif(row, scope, policy, version, record):
    from .matching import finish_comparison, printed_upc, words
    validate_inventory({"version": version, "rows": [row]})
    validate_jif_instructions(scope)
    variant = scope["variant"]
    inventory_ref = f"inventory:{version}:{row['inventory_id']}"
    conditions = {}

    def condition(field, truth, reason, normalized, expected, refs):
        conditions[field] = {"truth": truth, "reason": reason, "raw": row.get(field), "normalized": normalized,
                             "expected": expected, "evidence_refs": refs + [f"{inventory_ref}#{field}"]}

    for field in ["brand", "product_name", "package_size", "upc"]:
        value = printed_upc(row[field]) if field == "upc" else words(row[field])
        alternatives = {words(variant[field])}
        if field == "product_name":
            alternatives.add("jif creamy peanut butter")
        if field == "package_size":
            alternatives |= {"16 ounce", "16 ounces"}
        truth, reason = (("unknown", "missing") if value is None else
                         ("true", "reviewed_identity") if value in alternatives else
                         ("unknown", "outside_reviewed_variant"))
        condition(field, truth, reason, value, variant[field], ["notice.product_table"])
    lot = row.get("lot_code")
    truth, reason = lot_truth(lot, variant["lot_rule"])
    condition("lot_code", truth, reason, lot, variant["lot_rule"], ["notice.lot_scope", "guidance.lot_rule"])
    complete = row["stock_group"] == "single_code_group" and row["label_coverage"] == "all_units"
    condition("stock_group", "true" if complete else "unknown", "entire_group_checked" if complete else "inspect_and_split_entire_group",
              {"stock_group": row["stock_group"], "label_coverage": row["label_coverage"]},
              {"stock_group": "single_code_group", "label_coverage": "all_units"}, ["policy.stock_coverage"])
    conditions["stock_group"]["evidence_refs"].append(f"{inventory_ref}#label_coverage")
    missing = [field for field, value in conditions.items() if value["reason"] == "missing"]
    if not complete:
        missing.append("stock_group")
    review = [field for field, value in conditions.items() if value["truth"] == "unknown" and value["reason"] not in {"missing", "inspect_and_split_entire_group"}]
    return finish_comparison(row, scope, policy, version, conditions, missing, review, validate_jif_scope(scope, record),
                             inspection_instruction="Inspect every jar's product label and actual lot code beside the Best If Used By date; split mixed-lot groups.")
