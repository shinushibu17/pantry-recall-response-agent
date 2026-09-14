"""Anonymous, isolated synthetic replays with one persisted service-wide agent budget."""

from contextlib import closing
import hashlib
from http.cookies import CookieError, SimpleCookie
import re
import secrets
import sqlite3
import threading
import time

from .store import Store, WorkflowError, now


class DemoHost:
    def __init__(self, store, public_url, fixture_path, agent_runner=None, daily_runs=20, session_limit=200):
        self.store, self.public_url, self.fixture_path = store, public_url.rstrip("/"), fixture_path
        self.secure = self.public_url.startswith("https://")
        self.agent_runner, self.daily_runs, self.session_limit = agent_runner, daily_runs, session_limit
        self.apps, self.lock = {}, threading.Lock()
        with store.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS demo_sessions (id TEXT PRIMARY KEY, created_at REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS demo_runs (session_id TEXT NOT NULL, request_id TEXT NOT NULL, started_at TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(session_id,request_id))")
            db.execute("UPDATE demo_runs SET status='INTERRUPTED' WHERE status='RUNNING'")

    def _load_app(self, session_id):
        from .web import Application, live_agent
        visitor = Store(self.store.path.parent / "visitors" / (session_id + ".sqlite3"))
        visitor.initialize(self.fixture_path)
        app = Application(visitor, None, self.public_url, self.agent_runner or live_agent,
                          daily_runs=self.daily_runs, budget=self, session_id=session_id)
        self.apps[session_id] = app
        return app

    def resume_pending(self, load_saved=False):
        with self.lock:
            if load_saved:
                with self.store.connection() as db:
                    sessions = db.execute("SELECT id FROM demo_sessions WHERE created_at>=?", (time.time()-7*86400,)).fetchall()
                for session in sessions:
                    path = self.store.path.parent / "visitors" / (session["id"] + ".sqlite3")
                    if session["id"] in self.apps or not path.exists():
                        continue
                    with closing(sqlite3.connect(path)) as db:
                        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='web_agent_control'").fetchone():
                            continue
                        db.row_factory = sqlite3.Row
                        from .followup import FollowUp
                        pending = FollowUp.state_in(db)["pending"]
                    if pending:
                        self._load_app(session["id"])
            apps = list(self.apps.values())
        for app in apps:
            app.resume_pending()

    def resolve(self, cookie, create=False, fresh=False):
        token = ""
        try:
            token = SimpleCookie(cookie or "")["pantry_session"].value
        except (CookieError, KeyError):
            pass
        session_id = hashlib.sha256(token.encode()).hexdigest() if re.fullmatch(r"[0-9a-f]{64}", token) else None
        previous_id = session_id
        new_cookie = None
        with self.lock:
            with self.store.transaction() as db:
                row = db.execute("SELECT * FROM demo_sessions WHERE id=?", (session_id,)).fetchone()
                if fresh or row is None or row["created_at"] < time.time() - 7 * 86400:
                    if not create:
                        raise WorkflowError("SESSION_EXPIRED", "Reload to start your own demo pantry")
                    if db.execute("SELECT count(*) FROM demo_sessions").fetchone()[0] >= self.session_limit:
                        raise WorkflowError("DEMO_CAPACITY", "The demo has reached its visitor capacity. Existing sessions can continue.")
                    token = secrets.token_hex(32)
                    session_id = hashlib.sha256(token.encode()).hexdigest()
                    db.execute("INSERT INTO demo_sessions VALUES (?,?)", (session_id, time.time()))
                    new_cookie = token
            if fresh and row is not None:
                previous = self.apps.get(previous_id) or self._load_app(previous_id)
                previous.followup.enable(False)
            if session_id not in self.apps:
                self._load_app(session_id)
            return self.apps[session_id], new_cookie

    def reserve(self, session_id, request_id):
        with self.store.transaction() as db:
            if db.execute("SELECT 1 FROM demo_runs WHERE session_id=? AND request_id=?", (session_id, request_id)).fetchone():
                # The local report transaction did not commit; never repeat a billed call.
                raise WorkflowError("RUN_INTERRUPTED", "This run was already reserved. Start a new run.")
            if db.execute("SELECT 1 FROM demo_runs WHERE status='RUNNING'").fetchone():
                raise WorkflowError("AGENT_BUSY", "Another visitor's agent run is finishing. Try again shortly; you can still inspect evidence.")
            if db.execute("SELECT count(*) FROM demo_runs WHERE started_at>=?", (now()[:10],)).fetchone()[0] >= self.daily_runs:
                raise WorkflowError("AGENT_DAILY_LIMIT", "Today's live agent allowance is used. Evidence comparisons and the full inspection demo still work.")
            db.execute("INSERT INTO demo_runs VALUES (?,?,?,'RUNNING')", (session_id, request_id, now()))

    def finish(self, session_id, request_id, status):
        with self.store.transaction() as db:
            db.execute("UPDATE demo_runs SET status=? WHERE session_id=? AND request_id=?", (status, session_id, request_id))
