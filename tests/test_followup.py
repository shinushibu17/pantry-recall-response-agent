"""Accepted events wake the agent once; stale prose and model limits do not alter facts."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest

from pantry_recall.demo import DemoHost
from pantry_recall.fixtures import DEFAULT_FIXTURE
from pantry_recall.store import Store
from pantry_recall.web import Application


class FollowUpTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/"pantry.sqlite3");self.store.initialize()
        self.calls=[]
        self.app=Application(self.store,None,"https://demo.example",self.runner)
        self.addCleanup(self.drain)

    def drain(self):
        for thread in threading.enumerate():
            if thread.name.startswith("pantry-agent-"):
                thread.join(5)

    def runner(self,store):
        self.calls.append(store.load_context()["inventory"]["version"])
        return {"status":"COMPLETE", "briefing":{"priorities":[]}, "agent_explanation_unverified":"Advisory"}

    def wait(self,predicate):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if predicate():return
            time.sleep(.01)
        self.fail("Background agent did not reach the expected state")

    def idle(self,app=None):
        app=app or self.app
        with app.store.connection() as db:
            return not db.execute("SELECT 1 FROM web_runs WHERE status='RUNNING'").fetchone()

    def change(self,app=None,old="synthetic-pantry-v2",new="changed-v3",code="BBD SEP 13 25 P"):
        return (app or self.app).post("/api/evidence",{"inventory_id":"missing_code","expected_version":old,"new_version":new,
                  "changes":{"best_by_manufacturing_code":code},"actor":"Synthetic reviewer"})

    def test_following_requires_start_and_exact_evidence_replay_does_not_repeat_inference(self):
        self.change()
        self.assertEqual(self.calls,[])
        self.app.start_agent("manual-first")
        self.wait(lambda:len(self.calls)==1 and self.idle())
        self.change(old="changed-v3",new="changed-v4",code="BBD SEP 14 25 P")
        self.wait(lambda:len(self.calls)==2 and self.idle())
        self.change(old="changed-v3",new="changed-v4",code="BBD SEP 14 25 P")
        self.drain()
        self.assertEqual(len(self.calls),2)
        with self.store.connection() as db:
            contexts=[json.loads(r[0]) for r in db.execute("SELECT context FROM web_run_context ORDER BY rowid")]
        self.assertEqual([c["kind"] for c in contexts],["manual","workflow_change"])
        self.assertEqual(self.store.overview()["confirmation_count"],0)

    def test_changes_during_inference_coalesce_and_stale_brief_is_withheld(self):
        started,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        def runner(store):
            self.calls.append(store.load_context()["inventory"]["version"])
            if len(self.calls)==1:started.set();release.wait(3)
            return {"status":"COMPLETE","briefing":{"priorities":[]},"agent_explanation_unverified":"Old explanation"}
        self.app.agent_runner=runner
        self.app.start_agent("manual-blocked")
        self.assertTrue(started.wait(1))
        self.change()
        self.change(old="changed-v3",new="changed-v4",code="BBD SEP 14 25 P")
        self.assertEqual(len(self.calls),1)
        self.assertTrue(self.app.followup.state()["pending"])
        release.set()
        self.wait(lambda:len(self.calls)==2 and self.idle())
        old=self.app.run("manual-blocked")
        self.assertFalse(old["current"])
        self.assertNotIn("briefing",old["report"])
        self.assertNotIn("agent_explanation_unverified",old["report"])
        self.assertEqual(self.calls[-1],"changed-v4")
        with self.store.connection() as db:
            self.assertIn("Old explanation",db.execute("SELECT report FROM web_runs WHERE id='manual-blocked'").fetchone()[0])

    def test_allowance_exhaustion_preserves_evidence_and_pending_followup_across_restart(self):
        self.app.daily_runs=1
        self.app.start_agent("one-allowed")
        self.wait(lambda:len(self.calls)==1 and self.idle())
        self.assertEqual(self.change()["identification_state"],"AFFECTED")
        self.assertTrue(self.app.followup.state()["pending"])
        self.assertIn("daily",self.app.followup.state()["notice"])
        self.drain()
        reopened=Application(Store(self.store.path),None,"https://demo.example",self.runner,daily_runs=2)
        reopened.resume_pending()
        self.wait(lambda:len(self.calls)==2 and self.idle(reopened))
        self.assertFalse(reopened.followup.state()["pending"])

    def test_pause_and_resume_control_accepted_change_followups(self):
        self.app.start_agent("start-following")
        self.wait(lambda:len(self.calls)==1 and self.idle())
        self.app.post("/api/follow-up",{"enabled":False})
        self.change()
        self.assertEqual(len(self.calls),1)
        self.app.post("/api/follow-up",{"enabled":True})
        self.wait(lambda:len(self.calls)==2 and self.idle())

    def test_failed_run_has_no_unbounded_automatic_retry(self):
        def failed(store):
            self.calls.append("failed")
            return {"status":"INCOMPLETE_TOOL_COVERAGE"}
        self.app.agent_runner=failed
        self.app.start_agent("incomplete-first")
        self.wait(lambda:len(self.calls)==1 and self.idle())
        self.drain();self.app.agent_state()
        self.assertEqual(len(self.calls),1)
        self.change()
        self.wait(lambda:len(self.calls)==2 and self.idle())
        self.drain();self.app.agent_state()
        self.assertEqual(len(self.calls),2)

    def test_other_visitor_finishing_wakes_queued_case_without_browser_polling(self):
        host=DemoHost(Store(Path(self.temp.name)/"registry.sqlite3"),"https://demo.example",DEFAULT_FIXTURE,agent_runner=self.runner)
        host.store.initialize()
        alice,_=host.resolve(None,create=True);bob,_=host.resolve(None,create=True)
        bob.start_agent("bob-first-run");self.wait(lambda:len(self.calls)==1 and self.idle(bob));self.drain()
        started,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        def blocked(store):
            started.set();release.wait(3)
            return {"status":"COMPLETE"}
        alice.agent_runner=blocked;alice.start_agent("alice-running");self.assertTrue(started.wait(1))
        self.change(bob)
        self.assertTrue(bob.followup.state()["pending"])
        self.assertEqual(len(self.calls),1)
        release.set()
        self.wait(lambda:len(self.calls)==2 and self.idle(bob))
        self.assertEqual(alice.store.case("missing_code")["identification_state"],"NEEDS_EVIDENCE")
        self.assertEqual(bob.store.case("missing_code")["identification_state"],"AFFECTED")

    def test_fresh_demo_pauses_old_followups_without_erasing_history(self):
        host=DemoHost(Store(Path(self.temp.name)/"registry.sqlite3"),"https://demo.example",DEFAULT_FIXTURE,agent_runner=self.runner)
        host.store.initialize()
        old,token=host.resolve(None,create=True)
        old.start_agent("old-manual-run");self.wait(lambda:len(self.calls)==1 and self.idle(old));self.drain()
        fresh,_=host.resolve("pantry_session="+token,create=True,fresh=True)
        self.assertFalse(old.followup.state()["enabled"])
        self.assertIsNone(fresh.agent_state()["latest_run_id"])
        self.assertEqual(old.run("old-manual-run")["status"],"COMPLETE")

    def test_saved_public_queue_resumes_on_host_start_without_cookie_or_polling(self):
        root=Store(Path(self.temp.name)/"registry.sqlite3");root.initialize()
        host=DemoHost(root,"https://demo.example",DEFAULT_FIXTURE,agent_runner=self.runner,daily_runs=1)
        app,_=host.resolve(None,create=True)
        app.start_agent("public-prior-run");self.wait(lambda:len(self.calls)==1 and self.idle(app));self.drain()
        self.change(app)
        self.assertTrue(app.followup.state()["pending"])
        reopened=DemoHost(Store(root.path),"https://demo.example",DEFAULT_FIXTURE,agent_runner=self.runner,daily_runs=2)
        reopened.resume_pending(load_saved=True)
        self.wait(lambda:len(self.calls)==2 and all(self.idle(a) for a in reopened.apps.values()))
        self.assertEqual(len(reopened.apps),1)
