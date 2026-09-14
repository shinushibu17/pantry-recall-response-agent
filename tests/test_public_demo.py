"""Public demo isolation, anonymous HTTP sessions, and service-wide spend bounds."""

import http.client
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest

from pantry_recall.demo import DemoHost
from pantry_recall.fixtures import DEFAULT_FIXTURE
from pantry_recall.store import Store
from pantry_recall.web import Handler, ThreadingHTTPServer


class PublicDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name)/"registry.sqlite3")
        self.store.initialize()
        self.server = ThreadingHTTPServer(("127.0.0.1",0),Handler)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        self.host = self.server.app = DemoHost(self.store,self.origin,DEFAULT_FIXTURE)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self,path,body=None,cookie=None,origin=None):
        conn = http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=5)
        self.addCleanup(conn.close)
        headers={"Origin":origin or self.origin,"Content-Type":"application/json","X-Pantry-Request":"reviewer"}
        if cookie: headers["Cookie"]=cookie
        conn.request("GET" if body is None else "POST",path,None if body is None else json.dumps(body),headers)
        response=conn.getresponse()
        raw=response.read()
        value=json.loads(raw) if response.getheader("Content-Type").startswith("application/json") else raw
        return response.status,value,response.getheader("Set-Cookie")

    def visitor(self):
        status,state,cookie=self.request("/api/state")
        self.assertEqual(status,200)
        self.assertTrue(state["demo_mode"])
        self.assertIn("HttpOnly",cookie)
        self.assertIn("SameSite=Strict",cookie)
        return cookie.split(";")[0]

    def evidence(self,cookie):
        return self.request("/api/evidence",{"inventory_id":"missing_code","expected_version":"synthetic-pantry-v2",
            "new_version":"public-demo-v3","changes":{"best_by_manufacturing_code":"BBD SEP 13 25 P"},"actor":"Demo visitor"},cookie)

    def test_no_password_and_per_visitor_evidence_isolation(self):
        alice,bob=self.visitor(),self.visitor()
        self.assertNotEqual(alice,bob)
        self.assertEqual(self.evidence(alice)[1]["identification_state"],"AFFECTED")
        a=self.request("/api/history?id=missing_code",cookie=alice)[1]
        b=self.request("/api/history?id=missing_code",cookie=bob)[1]
        self.assertEqual(a["case"]["identification_state"],"AFFECTED")
        self.assertEqual(b["case"]["identification_state"],"NEEDS_EVIDENCE")
        self.assertEqual(self.store.case("missing_code")["identification_state"],"NEEDS_EVIDENCE")

    def test_reset_preserves_old_history_without_reusing_it(self):
        old=self.visitor()
        self.evidence(old)
        status,_,cookie=self.request("/api/session",{},old)
        self.assertEqual(status,200)
        new=cookie.split(";")[0]
        self.assertNotEqual(old,new)
        self.assertEqual(self.request("/api/history?id=missing_code",cookie=new)[1]["case"]["identification_state"],"NEEDS_EVIDENCE")
        self.assertEqual(self.request("/api/history?id=missing_code",cookie=old)[1]["case"]["identification_state"],"AFFECTED")

    def test_other_visitors_cannot_confirm_a_changed_stock_version(self):
        alice,bob=self.visitor(),self.visitor()
        case=self.evidence(alice)[1]
        task=next(t for t in case["tasks"] if t["type"]=="PERFORM_ACTION")
        command={"confirmation_id":"public-confirm","inventory_id":"missing_code","inventory_version":case["inventory_version"],
            "recall_version":case["recall_version"],"task_id":task["task_id"],"quantity":2,"unit":"boxes","actor":"Demo visitor","note":"Synthetic hold","attest_isolated":True}
        self.assertEqual(self.request("/api/confirm-hold",command,bob)[0],409)
        self.assertEqual(self.request("/api/confirm-hold",command,alice)[1]["remaining_quantity"],2)
        self.assertEqual(self.request("/api/state",cookie=bob)[1]["confirmation_count"],0)

    def test_write_origin_and_registered_cookie_still_required(self):
        cookie=self.visitor()
        self.assertEqual(self.request("/api/session",{},cookie,origin="https://unrelated.example")[0],403)
        self.assertEqual(self.evidence("pantry_session="+"0"*64)[1]["error"],"SESSION_EXPIRED")
        self.assertEqual(self.request("/api/source?name=../../private",cookie=cookie)[0],400)
        self.assertEqual(self.request("/api/login",{"password":"anything"},cookie)[1]["error"],"NOT_FOUND")

    def test_global_agent_limit_cannot_be_reset_with_a_new_visitor(self):
        self.host.daily_runs=1
        started,finish=threading.Event(),threading.Event()
        self.addCleanup(finish.set)
        def runner(store):
            started.set(); finish.wait(3)
            return {"status":"COMPLETE","validated_results":[]}
        self.host.agent_runner=runner
        alice,bob=self.visitor(),self.visitor()
        self.assertEqual(self.request("/api/agent",{"request_id":"run-one-123"},alice)[0],200)
        self.assertTrue(started.wait(1))
        self.assertEqual(self.request("/api/agent",{"request_id":"run-one-123"},alice)[0],200)
        self.assertEqual(self.request("/api/agent",{"request_id":"run-two-123"},bob)[1]["error"],"AGENT_BUSY")
        self.assertEqual(self.request("/api/agent/run-one-123",cookie=bob)[1]["error"],"UNKNOWN_RUN")
        finish.set()
        for _ in range(100):
            with self.store.connection() as db:
                done=db.execute("SELECT status FROM demo_runs").fetchone()[0]!="RUNNING"
            if done:break
            time.sleep(.01)
        self.assertTrue(done)
        self.assertEqual(self.request("/api/agent",{"request_id":"run-two-123"},bob)[1]["error"],"AGENT_DAILY_LIMIT")
        self.server.app=DemoHost(self.store,self.origin,DEFAULT_FIXTURE,daily_runs=1)
        self.assertEqual(self.request("/api/agent",{"request_id":"after-restart"},bob)[1]["error"],"AGENT_DAILY_LIMIT")

    def test_visitor_allocation_is_bounded(self):
        self.host.session_limit=1
        cookie=self.visitor()
        self.assertEqual(self.request("/api/state")[1]["error"],"DEMO_CAPACITY")
        self.assertEqual(self.request("/api/state",cookie=cookie)[0],200)

    def test_expired_cookie_cannot_write_to_old_replay(self):
        cookie=self.visitor()
        with self.store.transaction() as db:
            db.execute("UPDATE demo_sessions SET created_at=?",(time.time()-8*86400,))
        self.assertEqual(self.evidence(cookie)[1]["error"],"SESSION_EXPIRED")
        self.assertEqual(self.request("/api/state",cookie=cookie)[0],200)

    def test_new_session_does_not_reset_original_workflow_or_receipts(self):
        cookie=self.visitor()
        self.evidence(cookie)
        self.server.app=DemoHost(self.store,self.origin,DEFAULT_FIXTURE)
        self.assertEqual(self.request("/api/history?id=missing_code",cookie=cookie)[1]["case"]["identification_state"],"AFFECTED")
        self.assertEqual(self.store.overview()["confirmation_count"],0)


if __name__=="__main__": unittest.main()
