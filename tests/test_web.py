"""Exercise the real HTTP boundary around persisted evidence and confirmations."""

import http.client
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest

from pantry_recall.store import Store
from pantry_recall.web import Application, Handler, ThreadingHTTPServer


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "web.sqlite3")
        self.store.initialize()
        self.password = "test-reviewer-password-123456"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)
        self.app = self.server.app = Application(self.store, self.password, self.origin)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.cookie = None

    def request(self, path, body=None, **headers):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        self.addCleanup(connection.close)
        base = {"Origin": self.origin, "Content-Type": "application/json", "X-Pantry-Request": "reviewer"}
        if self.cookie:
            base["Cookie"] = self.cookie
        base.update(headers)
        connection.request("GET" if body is None else "POST", path, None if body is None else json.dumps(body), base)
        response = connection.getresponse()
        raw = response.read()
        data = json.loads(raw) if response.getheader("Content-Type").startswith("application/json") else raw
        return response.status, data, dict(response.getheaders())

    def login(self):
        status, _, headers = self.request("/api/login", {"password": self.password})
        self.assertEqual(status, 200)
        self.cookie = headers["Set-Cookie"].split(";")[0]

    def evidence(self, version="web-test-v3"):
        return self.request("/api/evidence", {"inventory_id": "missing_code", "expected_version": "synthetic-pantry-v2", "new_version": version,
            "actor": "Test reviewer", "changes": {"best_by_manufacturing_code": "BBD SEP 13 25 P", "evidence_note": "Synthetic all-unit inspection"}})

    def command(self, case):
        task = next(t for t in case["tasks"] if t["type"] == "PERFORM_ACTION" and t["status"] == "OPEN")
        return {"confirmation_id": "web-confirm-1", "task_id": task["task_id"], "inventory_id": case["inventory_id"],
                "inventory_version": case["inventory_version"], "recall_version": case["recall_version"], "quantity": 2,
                "unit": task["unit"], "actor": "Test reviewer", "note": "Two synthetic boxes isolated", "attest_isolated": True}

    def test_authentication_and_csrf_precede_writes(self):
        self.assertEqual(self.request("/api/state")[0], 401)
        self.assertEqual(self.evidence()[0], 401)
        self.assertEqual(self.request("/api/login", {"password": self.password}, Origin="https://other.example")[0], 403)
        self.login()
        self.assertEqual(self.request("/api/state")[0], 200)
        self.assertEqual(self.request("/api/evidence", {}, **{"X-Pantry-Request":""})[0], 403)
        self.request("/api/logout", {})
        self.assertEqual(self.store.overview()["confirmation_count"], 0)

    def test_complete_http_workflow_replay_and_persistence(self):
        self.login()
        status, case, _ = self.evidence()
        self.assertEqual(status, 200)
        self.assertEqual(case["identification_state"], "AFFECTED")
        command = self.command(case)
        status, partial, _ = self.request("/api/confirm-hold", command)
        self.assertEqual(status, 200)
        self.assertEqual(partial["remaining_quantity"], 2)
        self.assertEqual(partial["channel"], "human_confirmation_web")
        self.assertEqual(self.request("/api/confirm-hold", command)[1], partial)
        command["confirmation_id"] = "web-confirm-2"
        completed = self.request("/api/confirm-hold", command)[1]
        self.assertEqual(completed["action_state"], "COMPLETED_CONFIRMED")
        reopened = Store(self.store.path)
        self.assertEqual(reopened.overview()["confirmation_count"], 2)
        self.assertEqual(reopened.case("missing_code")["action_state"], "COMPLETED_CONFIRMED")
        self.assertIn("human_evidence_web", [e["channel"] for e in reopened.history("missing_code")["events"]])

    def test_http_confirmation_guards(self):
        self.login()
        command = self.command(self.evidence()[1])
        for patch, code in [({"attest_isolated": False}, "ATTESTATION_REQUIRED"), ({"quantity": True}, "INVALID_QUANTITY"),
                            ({"quantity": 5}, "EXCESS_QUANTITY"), ({"inventory_version": "old"}, "STALE_INVENTORY_VERSION")]:
            status, result, _ = self.request("/api/confirm-hold", {**command, **patch})
            self.assertEqual(status, 409)
            self.assertEqual(result["error"], code)
        self.assertEqual(self.store.overview()["confirmation_count"], 0)

    def test_stale_evidence_and_unknown_remain_unresolved(self):
        self.login()
        self.evidence()
        self.assertEqual(self.evidence("web-other-v3")[1]["error"], "STALE_INVENTORY_VERSION")
        status, case, _ = self.request("/api/evidence", {"inventory_id": "missing_code", "expected_version": "web-test-v3",
            "new_version": "web-test-v4", "actor": "Reviewer", "changes": {"best_by_manufacturing_code": None}})
        self.assertEqual(status, 200)
        self.assertEqual(case["identification_state"], "NEEDS_EVIDENCE")
        self.assertIsNone(case["proposed_identification_state"])

    def test_sources_are_authenticated_inert_and_not_filesystem_paths(self):
        self.assertEqual(self.request("/api/source?name=sources/notice.html")[0], 401)
        self.login()
        status, raw, headers = self.request("/api/source?name=sources/notice.html")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("text/plain"))
        self.assertEqual(raw, (Path("fixtures/pearl_milling_2025/sources/notice.html")).read_bytes())
        self.assertEqual(self.request("/api/source?name=../../.env")[0], 400)

    def test_agent_concurrency_idempotency_and_daily_limit(self):
        self.login()
        started, finish = threading.Event(), threading.Event()
        self.addCleanup(finish.set)
        def runner(store):
            started.set()
            finish.wait(3)
            return {"status":"COMPLETE", "validated_results":[], "agent_explanation_unverified":"advisory"}
        self.app.agent_runner = runner
        self.app.daily_runs = 1
        self.assertEqual(self.request("/api/agent", {"request_id":"test-run-1"})[0], 200)
        self.assertTrue(started.wait(1))
        self.assertEqual(self.request("/api/agent", {"request_id":"test-run-1"})[0], 200)
        self.assertEqual(self.request("/api/agent", {"request_id":"test-run-2"})[1]["error"], "AGENT_BUSY")
        finish.set()
        for _ in range(100):
            if self.app.run("test-run-1")["status"] != "RUNNING": break
            time.sleep(.01)
        self.assertEqual(self.app.run("test-run-1")["status"], "COMPLETE")
        self.assertEqual(self.request("/api/agent", {"request_id":"test-run-2"})[1]["error"], "AGENT_DAILY_LIMIT")
        self.evidence()
        run = self.request("/api/agent/test-run-1")[1]
        self.assertFalse(run["current"])
        self.assertNotIn("agent_explanation_unverified", run["report"])

    def test_incomplete_prose_is_preserved_but_not_presented(self):
        self.login()
        with self.store.transaction() as db:
            db.execute("INSERT INTO web_runs VALUES (?,?,?,?,?,?)", ("incomplete", "2026-09-12", "INCOMPLETE_TOOL_COVERAGE",
                json.dumps({"status":"INCOMPLETE_TOOL_COVERAGE", "agent_explanation_unverified":"Unverified claim"}),
                "synthetic-pantry-v2", self.store.overview()["event_count"]))
        self.assertNotIn("agent_explanation_unverified", self.request("/api/agent/incomplete")[1]["report"])
        with self.store.connection() as db:
            self.assertIn("Unverified claim", db.execute("SELECT report FROM web_runs").fetchone()[0])

    def test_password_attempts_are_bounded(self):
        for _ in range(5):
            self.assertEqual(self.request("/api/login", {"password":"wrong"})[1]["error"], "LOGIN_FAILED")
        self.assertEqual(self.request("/api/login", {"password":self.password})[1]["error"], "LOGIN_RATE_LIMIT")


if __name__ == "__main__":
    unittest.main()
