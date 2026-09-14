"""SQLite workflow state; immutable evidence versions and append-only events.

The agent may request deterministic evaluation and read history. Evidence entry
and physical-action confirmation are separate application boundaries.
"""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import NAMESPACE_URL, uuid5

from .fixtures import DEFAULT_FIXTURE, FixtureError, digest, load_fixture, row_digest, validate_inventory
from .matching import evaluate_inventory


class WorkflowError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def encoded(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recalls (
  version TEXT PRIMARY KEY, sha256 TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
  recall_version TEXT NOT NULL REFERENCES recalls(version), name TEXT NOT NULL,
  sha256 TEXT NOT NULL, content BLOB NOT NULL, PRIMARY KEY(recall_version, name)
);
CREATE TABLE IF NOT EXISTS inventories (
  version TEXT PRIMARY KEY, parent_version TEXT REFERENCES inventories(version),
  sha256 TEXT NOT NULL, payload TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
  case_id TEXT PRIMARY KEY, inventory_id TEXT NOT NULL,
  recall_version TEXT NOT NULL REFERENCES recalls(version),
  inventory_version TEXT NOT NULL REFERENCES inventories(version), row_sha256 TEXT NOT NULL,
  finding TEXT NOT NULL, identification_state TEXT NOT NULL, action_state TEXT NOT NULL,
  proposed_identification_state TEXT, UNIQUE(recall_version, inventory_id)
);
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
  inventory_version TEXT NOT NULL REFERENCES inventories(version),
  recall_version TEXT NOT NULL REFERENCES recalls(version),
  type TEXT NOT NULL CHECK(type IN ('IDENTIFY_STOCK','REVIEW_SCOPE','PERFORM_ACTION')),
  status TEXT NOT NULL CHECK(status IN ('OPEN','DONE','SUPERSEDED')),
  quantity INTEGER NOT NULL CHECK(quantity > 0),
  confirmed_quantity INTEGER NOT NULL DEFAULT 0 CHECK(confirmed_quantity >= 0 AND confirmed_quantity <= quantity),
  unit TEXT NOT NULL, location TEXT NOT NULL, details TEXT NOT NULL,
  UNIQUE(case_id, inventory_version, type)
);
CREATE TABLE IF NOT EXISTS confirmations (
  confirmation_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
  payload TEXT NOT NULL, receipt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
  kind TEXT NOT NULL, case_id TEXT, actor TEXT NOT NULL, channel TEXT NOT NULL,
  payload TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(SCHEMA)
            # These records are evidence/history, not mutable current-state rows.
            for table in ("recalls", "sources", "inventories", "confirmations", "events"):
                for operation in ("UPDATE", "DELETE"):
                    connection.execute(
                        f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation.lower()} "
                        f"BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable evidence/history'); END"
                    )

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @staticmethod
    def _event(connection, kind, payload, case_id=None, actor="application", channel="deterministic") -> int:
        cursor = connection.execute(
            "INSERT INTO events(occurred_at,kind,case_id,actor,channel,payload) VALUES (?,?,?,?,?,?)",
            (now(), kind, case_id, actor, channel, encoded(payload)),
        )
        return cursor.lastrowid

    @staticmethod
    def _meta(connection, key):
        row = connection.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        if row is None:
            raise WorkflowError("NOT_INITIALIZED", "Initialize this workflow database first")
        return row["value"]

    @staticmethod
    def _inventory(connection, version):
        row = connection.execute("SELECT * FROM inventories WHERE version=?", (version,)).fetchone()
        if row is None:
            raise WorkflowError("UNKNOWN_VERSION", "Inventory version does not exist")
        if digest(row["payload"].encode("utf-8")) != row["sha256"]:
            raise WorkflowError("EVIDENCE_CORRUPT", "Inventory snapshot hash mismatch")
        return json.loads(row["payload"])

    def _context(self, connection):
        recall_version = self._meta(connection, "recall_version")
        row = connection.execute("SELECT * FROM recalls WHERE version=?", (recall_version,)).fetchone()
        if row is None or digest(row["payload"].encode("utf-8")) != row["sha256"]:
            raise WorkflowError("EVIDENCE_CORRUPT", "Recall snapshot hash mismatch")
        for source in connection.execute("SELECT * FROM sources WHERE recall_version=?", (recall_version,)):
            if digest(source["content"]) != source["sha256"]:
                raise WorkflowError("EVIDENCE_CORRUPT", "Stored source hash mismatch")
        fixture = json.loads(row["payload"])
        fixture["inventory"] = self._inventory(connection, self._meta(connection, "inventory_version"))
        return fixture

    def load_context(self) -> dict:
        with self.connection() as connection:
            connection.execute("BEGIN")
            return self._context(connection)

    def initialize(self, fixture_path: Path = DEFAULT_FIXTURE) -> dict:
        fixture = load_fixture(fixture_path)
        recall = {key: value for key, value in fixture.items() if key != "inventory"}
        recall_payload = encoded(recall)
        recall_version = fixture["scope"]["version"]
        inventory = fixture["inventory"]
        with self.transaction() as connection:
            current = connection.execute("SELECT value FROM metadata WHERE key='recall_version'").fetchone()
            if current is not None:
                if current["value"] != recall_version:
                    raise WorkflowError("RECALL_MIGRATION_REQUIRED", "Use a separately reviewed migration or a separate database for a new recall version")
                existing = connection.execute("SELECT payload FROM recalls WHERE version=?", (recall_version,)).fetchone()
                if existing["payload"] != recall_payload:
                    raise WorkflowError("VERSION_CONFLICT", "A recall version cannot be redefined")
            else:
                connection.execute("INSERT INTO recalls VALUES (?,?,?)", (recall_version, digest(recall_payload.encode("utf-8")), recall_payload))
                for name in fixture["lock"]["files"]:
                    if name.startswith("sources/"):
                        raw = (Path(fixture_path) / name).read_bytes()
                        connection.execute("INSERT INTO sources VALUES (?,?,?,?)", (recall_version, name, digest(raw), raw))
                payload = encoded(inventory)
                connection.execute("INSERT INTO inventories VALUES (?,?,?,?,?,?)",
                                   (inventory["version"], None, digest(payload.encode("utf-8")), payload, "fixture", now()))
                connection.executemany("INSERT INTO metadata VALUES (?,?)", [
                    ("recall_version", recall_version), ("inventory_version", inventory["version"]), ("schema_version", "1")])
                self._event(connection, "WORKFLOW_INITIALIZED", {"recall_version": recall_version, "inventory_version": inventory["version"], "synthetic": True})
                for row in inventory["rows"]:
                    self._evaluate(connection, fixture, row)
        return self.overview()

    @staticmethod
    def _case_row(connection, inventory_id):
        row = connection.execute("SELECT * FROM cases WHERE inventory_id=?", (inventory_id,)).fetchone()
        if row is None:
            raise WorkflowError("UNKNOWN_STOCK_GROUP", "Stock group does not exist in this workflow")
        return row

    @staticmethod
    def _task(row):
        result = json.loads(row["details"])
        result.update({key: row[key] for key in ("task_id", "inventory_version", "recall_version", "type", "status", "quantity", "confirmed_quantity", "unit", "location")})
        result.update(draft_only=False, remaining_quantity=row["quantity"] - row["confirmed_quantity"] if row["type"] == "PERFORM_ACTION" else None)
        if row["type"] == "PERFORM_ACTION" and row["confirmed_quantity"]:
            result["original_instruction"] = result["instruction"]
            result["instruction"] = (
                "Specified hold quantity confirmed by synthetic human assertion; further recall review remains."
                if row["status"] == "DONE" else
                "Partial hold quantity confirmed; the remaining quantity still requires a human confirmation."
            )
        return result

    def _case(self, connection, inventory_id):
        row = self._case_row(connection, inventory_id)
        tasks = [self._task(task) for task in connection.execute("SELECT * FROM tasks WHERE case_id=? ORDER BY rowid", (row["case_id"],))]
        return {"case_id": row["case_id"], "inventory_id": inventory_id, "recall_version": row["recall_version"],
                "inventory_version": row["inventory_version"], "row_sha256": row["row_sha256"],
                "identification_state": row["identification_state"], "action_state": row["action_state"],
                "proposed_identification_state": row["proposed_identification_state"],
                "scope_finding": json.loads(row["finding"]), "tasks": tasks,
                "action_scope": "Hold/isolation of the specified synthetic stock only; no release or completion of other recall obligations."}

    def case(self, inventory_id: str) -> dict:
        with self.connection() as connection:
            connection.execute("BEGIN")
            return self._case(connection, inventory_id)

    def overview(self) -> dict:
        with self.connection() as connection:
            connection.execute("BEGIN")
            return {"recall_version": self._meta(connection, "recall_version"),
                    "inventory_version": self._meta(connection, "inventory_version"),
                    "cases": [self._case(connection, row["inventory_id"]) for row in connection.execute("SELECT inventory_id FROM cases ORDER BY rowid")],
                    "event_count": connection.execute("SELECT count(*) FROM events").fetchone()[0],
                    "confirmation_count": connection.execute("SELECT count(*) FROM confirmations").fetchone()[0]}

    def history(self, inventory_id: str) -> dict:
        with self.connection() as connection:
            connection.execute("BEGIN")
            case = self._case(connection, inventory_id)
            events = []
            for row in connection.execute("SELECT * FROM events WHERE case_id=? ORDER BY sequence", (case["case_id"],)):
                event = dict(row)
                event["payload"] = json.loads(event["payload"])
                events.append(event)
            return {"case": case, "events": events}

    def inventory_version(self, version: str) -> dict:
        with self.connection() as connection:
            return self._inventory(connection, version)

    def _evaluate(self, connection, fixture, row):
        existing = connection.execute("SELECT * FROM cases WHERE inventory_id=?", (row["inventory_id"],)).fetchone()
        if existing is not None and existing["row_sha256"] == row_digest(row):
            # A global snapshot revision doesn't invalidate unchanged stock's
            # evidence bindings, create duplicate tasks, or erase confirmations.
            return self._result(connection, row["inventory_id"])
        version = fixture["inventory"]["version"]
        finding = evaluate_inventory(fixture, {"version": version, "rows": [row]})[0]
        case_id = str(uuid5(NAMESPACE_URL, encoded([fixture["scope"]["version"], row["inventory_id"]])))
        if existing is not None:
            for task in connection.execute("SELECT * FROM tasks WHERE case_id=? AND status='OPEN'", (case_id,)).fetchall():
                evidence_resolved = finding["identification_state"] == "AFFECTED" or finding["proposed_identification_state"] == "NOT_AFFECTED_BY_THIS_RECALL"
                status = "DONE" if task["type"] == "IDENTIFY_STOCK" and evidence_resolved else "SUPERSEDED"
                connection.execute("UPDATE tasks SET status=? WHERE task_id=?", (status, task["task_id"]))
                self._event(connection, "TASK_" + status, {"task_id": task["task_id"], "type": task["type"], "previous_inventory_version": task["inventory_version"], "resolving_inventory_version": version, "physical_action_confirmed": False}, case_id)
        connection.execute(
            "INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET "
            "inventory_version=excluded.inventory_version,row_sha256=excluded.row_sha256,finding=excluded.finding,"
            "identification_state=excluded.identification_state,action_state=excluded.action_state,proposed_identification_state=excluded.proposed_identification_state",
            (case_id, row["inventory_id"], finding["recall_version"], version, row_digest(row), encoded(finding), finding["identification_state"], finding["action_state"], finding["proposed_identification_state"]),
        )
        self._event(connection, "CASE_EVALUATED", {"inventory_version": version, "recall_version": finding["recall_version"], "row_sha256": row_digest(row),
                    "identification_state": finding["identification_state"], "action_state": finding["action_state"],
                    "proposed_identification_state": finding["proposed_identification_state"],
                    "evidence_refs": finding["candidate"]["evidence_refs"]}, case_id)
        if finding["task"]:
            task = finding["task"]
            task_id = str(uuid5(NAMESPACE_URL, encoded([case_id, version, task["type"]])))
            connection.execute("INSERT INTO tasks(task_id,case_id,inventory_version,recall_version,type,status,quantity,unit,location,details) VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (task_id, case_id, version, finding["recall_version"], task["type"], "OPEN", task["quantity"], task["unit"], task["location"], encoded(task)))
            self._event(connection, "TASK_CREATED", {"task_id": task_id, "type": task["type"], "inventory_version": version, "quantity": task["quantity"], "unit": task["unit"], "basis": task["basis"], "evidence_refs": task["evidence_refs"]}, case_id)
        return self._result(connection, row["inventory_id"])

    def _result(self, connection, inventory_id):
        case = self._case(connection, inventory_id)
        finding = deepcopy(case["scope_finding"])
        finding["action_state"] = case["action_state"]
        current_tasks = [task for task in case["tasks"] if task["inventory_version"] == case["inventory_version"] and task["status"] != "SUPERSEDED"]
        finding["task"] = current_tasks[-1] if current_tasks else None
        finding["workflow"] = {key: case[key] for key in ("case_id", "inventory_version", "identification_state", "action_state", "tasks", "action_scope")}
        return finding

    def evaluate(self, inventory_ids: list[str], expected_inventory_version: str, expected_recall_version: str) -> list[dict]:
        with self.transaction() as connection:
            fixture = self._context(connection)
            if fixture["inventory"]["version"] != expected_inventory_version or fixture["scope"]["version"] != expected_recall_version:
                raise WorkflowError("STALE_AGENT_SNAPSHOT", "Evidence changed during this agent run; start a new run")
            rows = {row["inventory_id"]: row for row in fixture["inventory"]["rows"]}
            if not inventory_ids or len(set(inventory_ids)) != len(inventory_ids) or any(key not in rows for key in inventory_ids):
                raise WorkflowError("INVALID_STOCK_GROUPS", "Supply distinct existing stock group IDs")
            return [self._evaluate(connection, fixture, rows[key]) for key in inventory_ids]

    def reject(self, error: WorkflowError, operation: str, inventory_id: str, actor: str) -> None:
        with self.transaction() as connection:
            case = connection.execute("SELECT case_id FROM cases WHERE inventory_id=?", (inventory_id,)).fetchone()
            self._event(connection, "COMMAND_REJECTED", {"operation": operation, "code": error.code, "inventory_id": inventory_id},
                        case["case_id"] if case else None, actor, "application_boundary")

    def supply_evidence(self, inventory_id: str, expected_version: str, new_version: str, changes: dict, actor: str, *, channel="human_evidence_cli") -> dict:
        """Application evidence-entry operation; never registered as an agent tool."""
        try:
            allowed = {"best_by_manufacturing_code", "lot_code", "best_by_date", "evidence_note", "stock_group", "label_coverage"}
            if not isinstance(changes, dict) or not changes or not set(changes) <= allowed:
                raise WorkflowError("INVALID_EVIDENCE_FIELDS", "Only label/coverage evidence can be changed in this milestone")
            if not isinstance(new_version, str) or not new_version.strip() or new_version == expected_version:
                raise WorkflowError("INVALID_VERSION", "Evidence requires a distinct nonempty version")
            if not isinstance(actor, str) or not actor.strip():
                raise WorkflowError("ACTOR_REQUIRED", "Evidence entry requires an actor")
            with self.transaction() as connection:
                base = self._inventory(connection, expected_version)
                snapshot = deepcopy(base)
                row = next((row for row in snapshot["rows"] if row["inventory_id"] == inventory_id), None)
                if row is None:
                    raise WorkflowError("UNKNOWN_STOCK_GROUP", "Stock group not found")
                row.update(changes)
                snapshot["version"] = new_version
                try:
                    validate_inventory(snapshot)
                except FixtureError as error:
                    raise WorkflowError("INVALID_INVENTORY", str(error)) from error
                payload = encoded(snapshot)
                previous = connection.execute("SELECT * FROM inventories WHERE version=?", (new_version,)).fetchone()
                if previous:
                    if previous["payload"] != payload or previous["parent_version"] != expected_version:
                        raise WorkflowError("VERSION_CONFLICT", "An inventory version cannot be redefined")
                    return self._case(connection, inventory_id)
                if self._meta(connection, "inventory_version") != expected_version:
                    raise WorkflowError("STALE_INVENTORY_VERSION", "Evidence was based on a stale snapshot")
                case = self._case_row(connection, inventory_id)
                connection.execute("INSERT INTO inventories VALUES (?,?,?,?,?,?)", (new_version, expected_version, digest(payload.encode("utf-8")), payload, actor, now()))
                connection.execute("UPDATE metadata SET value=? WHERE key='inventory_version'", (new_version,))
                self._event(connection, "EVIDENCE_ADDED", {"previous_inventory_version": expected_version, "inventory_version": new_version,
                            "inventory_id": inventory_id, "row_sha256": row_digest(row), "changed_fields": sorted(changes)}, case["case_id"], actor, channel)
                fixture = self._context(connection)
                self._evaluate(connection, fixture, row)
                return self._case(connection, inventory_id)
        except WorkflowError as error:
            self.reject(error, "supply_evidence", inventory_id, actor)
            raise
