"""Load pinned evidence and reject altered or unsupported source annotations."""

import hashlib
import json
from pathlib import Path

from tools.acquire_fixture import notice_text


DEFAULT_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "pearl_milling_2025"


class FixtureError(ValueError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def row_digest(row: dict) -> str:
    return digest(json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_inventory(inventory: dict) -> None:
    if not isinstance(inventory.get("version"), str) or not inventory["version"]:
        raise FixtureError("Inventory requires a nonempty version")
    seen = set()
    text_fields = (
        "product_name", "brand", "package_size", "upc", "best_by_manufacturing_code", "best_by_date",
        "received_date", "donation_source", "evidence_note",
    )
    for row in inventory["rows"]:
        inventory_id = row.get("inventory_id")
        if not isinstance(inventory_id, str) or not inventory_id or inventory_id in seen:
            raise FixtureError("Inventory IDs must be unique nonempty strings")
        seen.add(inventory_id)
        for field in text_fields:
            if field not in row:
                raise FixtureError(f"{inventory_id}: {field} must be supplied; use null for unknown")
            value = row[field]
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise FixtureError(f"{inventory_id}: {field} must be a nonempty string or null")
        if row.get("lot_code") is not None and (not isinstance(row["lot_code"], str) or not row["lot_code"].strip()):
            raise FixtureError(f"{inventory_id}: lot_code must be nonempty text or null")
        if type(row.get("quantity")) is not int or row["quantity"] <= 0:
            raise FixtureError("quantity must be a positive integer for these packaged stock groups")
        for field in ("unit", "storage_location"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise FixtureError(f"{field} is required for an actionable inspection")
        if row.get("stock_group") not in {"single_code_group", "mixed_codes", "unknown"}:
            raise FixtureError("Unsupported stock_group")
        if row.get("label_coverage") not in {"all_units", "one_unit", "none"}:
            raise FixtureError("Unsupported label_coverage")


def validate_scope(scope: dict, record: dict) -> list[str]:
    """This milestone supports only the reviewed single-row, bounded-code notice."""
    if scope.get("profile") == "jif_16oz_creamy_2022":
        from .jif import validate_jif_scope
        return validate_jif_scope(scope, record)
    issues = []
    variant = scope["variant"]
    if scope["review"]["scope_status"] != "reviewed":
        issues.append("Scope interpretation requires review")
    if variant["code_scope"] != "bounded_list" or len(variant["best_by_manufacturing_codes"]) != 1:
        issues.append("Unsupported scope expression; do not approximate it")
    table = " ".join([
        variant["brand"], variant["product_name"], variant["package_size"],
        variant["upc"], " ".join(variant["best_by_manufacturing_codes"]),
    ])
    if table != scope["evidence"]["notice.product_table"]["quote"]:
        issues.append("Normalized scope does not reproduce the source product row")
    if " ".join(record["product_description"].split()) != table:
        issues.append("Enforcement and notice product scopes differ")
    if record["code_info"] not in variant["best_by_manufacturing_codes"]:
        issues.append("Enforcement and notice codes differ")
    return issues


def validate_instructions(scope: dict) -> None:
    if scope.get("profile") == "jif_16oz_creamy_2022":
        from .jif import validate_jif_instructions
        return validate_jif_instructions(scope)
    if scope.get("profile") is not None:
        raise FixtureError("Unsupported reviewed recall profile")
    # Closed, manually reviewed projection of this notice's conditional sentence.
    # A real quotation alone cannot support an arbitrary action attached to it.
    expected = {
        "id": "conditional_consumer_instruction",
        "action": "Do not consume the recalled product; discard it immediately.",
        "audience": "consumers",
        "trigger": "The consumer has an allergy or sensitivity to milk AND has the recalled product.",
        "issuer": "The Quaker Oats Company",
        "source_kind": "company_announcement_hosted_by_fda",
        "evidence_refs": ["notice.consumer_instruction"],
        "automatic_pantry_instruction": False,
    }
    if scope["instructions"] != [expected]:
        raise FixtureError("Unsupported action, audience, trigger, attribution or instruction citation")
    if scope["evidence"]["notice.consumer_instruction"]["quote"] != (
        "If consumers have an allergy or sensitivity to milk, they should not consume the product and discard it immediately."
    ):
        raise FixtureError("Instruction is not supported by the reviewed conditional source sentence")


def load_fixture(path: Path = DEFAULT_FIXTURE) -> dict:
    path = Path(path)
    lock = read_json(path / "fixture.lock.json")
    for name, expected_hash in lock["files"].items():
        file = (path / name).resolve()
        if not file.is_relative_to(path.resolve()):
            raise FixtureError("Fixture path escapes its directory")
        if digest(file.read_bytes()) != expected_hash:
            raise FixtureError(f"Pinned file hash mismatch: {name}")
    acquisition = read_json(path / "sources/acquisition.json")
    if acquisition["state"] != "AVAILABLE":
        raise FixtureError(f"Source unavailable: {acquisition['state']}")
    raw_html = (path / "sources/notice.html").read_bytes()
    raw_text = (path / "sources/notice.txt").read_bytes()
    raw_enforcement = (path / "sources/enforcement.json").read_bytes()
    for raw, expected_hash in (
        (raw_html, acquisition["notice"]["sha256"]),
        (raw_text, acquisition["notice_text_sha256"]),
        (raw_enforcement, acquisition["enforcement"]["sha256"]),
    ):
        if digest(raw) != expected_hash:
            raise FixtureError("Acquisition hash mismatch")
    if notice_text(raw_html).encode("utf-8") != raw_text:
        raise FixtureError("Notice text is not the deterministic HTML derivative")
    scope = read_json(path / "scope.json")
    validate_instructions(scope)
    policy = read_json(path / "policy.json")
    notice = raw_text.decode("utf-8")
    issuer = "The J. M. Smucker Co." if scope.get("profile") == "jif_16oz_creamy_2022" else "The Quaker Oats Company"
    if "Company Name: " + issuer not in notice:
        raise FixtureError("Instruction issuer not found in the notice's company metadata")
    documents = {"sources/notice.txt": (notice, raw_html, raw_text, acquisition["notice"])}
    if scope.get("profile") == "jif_16oz_creamy_2022":
        html = (path / "sources/investigation.html").read_bytes()
        text = (path / "sources/investigation.txt").read_bytes()
        if (digest(html) != acquisition["investigation"]["sha256"]
                or digest(text) != acquisition["investigation_text_sha256"]
                or notice_text(html).encode("utf-8") != text):
            raise FixtureError("FDA guidance acquisition or derivative hash mismatch")
        documents["sources/investigation.txt"] = (text.decode("utf-8"), html, text, acquisition["investigation"])
    for evidence_id, span in scope["evidence"].items():
        if span["source_file"] not in documents:
            raise FixtureError(f"Unknown source document: {evidence_id}")
        source_text, html, raw, metadata = documents[span["source_file"]]
        if (span["source_url"] != metadata["url"]
                or span["source_sha256"] != digest(html)
                or span["text_sha256"] != digest(raw)
                or not 0 <= span["start"] < span["end"] <= len(source_text)
                or source_text[span["start"]:span["end"]] != span["quote"]):
            raise FixtureError(f"Invalid source span: {evidence_id}")
    enforcement = json.loads(raw_enforcement)
    if len(enforcement["results"]) != 1:
        raise FixtureError("Expected one pinned enforcement record")
    record = enforcement["results"][0]
    if (record["recall_number"] != scope["recall_number"]
            or record["event_id"] != acquisition["record_identifiers"]["event_id"]):
        raise FixtureError("Recall record identifiers differ")
    inventory = read_json(path / "inventory.json")
    validate_inventory(inventory)
    return {
        "scope": scope, "policy": policy, "inventory": inventory,
        "record": record, "acquisition": acquisition, "lock": lock,
        "scope_issues": validate_scope(scope, record),
    }
