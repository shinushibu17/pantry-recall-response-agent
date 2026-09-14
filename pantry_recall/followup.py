"""Persisted opt-in follow-ups derived from accepted workflow events."""

import json

from .store import encoded, WorkflowError


class FollowUp:
    def __init__(self, store):
        self.store = store
        with store.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS web_agent_control (id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL, last_attempt INTEGER NOT NULL, notice TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO web_agent_control VALUES (1,0,0,'')")
            db.execute("CREATE TABLE IF NOT EXISTS web_run_context (run_id TEXT PRIMARY KEY REFERENCES web_runs(id), context TEXT NOT NULL)")

    @staticmethod
    def state_in(db):
        control = dict(db.execute("SELECT * FROM web_agent_control WHERE id=1").fetchone())
        latest_change = db.execute("SELECT coalesce(max(sequence),0) FROM events WHERE kind IN ('EVIDENCE_ADDED','HOLD_CONFIRMED')").fetchone()[0]
        return {"enabled": bool(control["enabled"]), "pending": bool(control["enabled"] and latest_change > control["last_attempt"]),
                "pending_event": latest_change, "notice": control["notice"]}

    def state(self):
        with self.store.connection() as db:
            return self.state_in(db)

    def enable(self, enabled):
        if type(enabled) is not bool:
            raise WorkflowError("INVALID_FOLLOWUP", "Follow-up setting must be true or false")
        with self.store.transaction() as db:
            db.execute("UPDATE web_agent_control SET enabled=?,notice='' WHERE id=1", (enabled,))

    def notice(self, value):
        with self.store.transaction() as db:
            db.execute("UPDATE web_agent_control SET notice=? WHERE id=1 AND notice!=?", (value, value))

    def record_run(self, db, request_id, automatic, watermark):
        prior = db.execute("SELECT event_count FROM web_runs WHERE status='COMPLETE' AND id!=? ORDER BY rowid DESC LIMIT 1", (request_id,)).fetchone()
        context = {"kind": "workflow_change" if automatic else "manual", "since_event": prior["event_count"] if prior else 0,
                   "snapshot_event": watermark}
        db.execute("INSERT INTO web_run_context VALUES (?,?)", (request_id, encoded(context)))
        db.execute("UPDATE web_agent_control SET enabled=1,last_attempt=?,notice='' WHERE id=1", (watermark,))

    def running_context(self):
        with self.store.connection() as db:
            row = db.execute("SELECT context FROM web_run_context JOIN web_runs ON id=run_id WHERE status='RUNNING' ORDER BY web_runs.rowid DESC LIMIT 1").fetchone()
            return json.loads(row["context"]) if row else {"kind": "manual", "since_event": 0}
