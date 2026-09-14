"""Small authenticated reviewer server. Human write operations are never agent tools."""

import argparse
from collections import defaultdict
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlsplit, parse_qs

from .confirmations import HoldConfirmation, record_human_confirmation
from .fixtures import DEFAULT_FIXTURE
from .demo import DemoHost
from .followup import FollowUp
from .store import Store, WorkflowError, encoded, now

STATIC = Path(__file__).with_name("static")
LOG = logging.getLogger(__name__)


def live_agent(store):
    from strands.models import BedrockModel
    from .agent import run_agent
    from .aws_access import session_for, client_config, DEFAULT_MODEL
    session = session_for(os.getenv("AWS_PROFILE"), os.getenv("AWS_REGION", "us-east-1"))
    model = BedrockModel(model_id=DEFAULT_MODEL, boto_session=session,
                         boto_client_config=client_config(), streaming=False, temperature=0, max_tokens=2048)
    report = run_agent(model, store.load_context(), store=store, investigate=True,
                       trigger=FollowUp(store).running_context())
    report.update(provider="Amazon Bedrock", model_id=DEFAULT_MODEL, region=session.region_name)
    return report


class Application:
    def __init__(self, store, password, public_url, agent_runner=live_agent, daily_runs=20, budget=None, session_id=None):
        if password is not None and len(password) < 20:
            raise ValueError("Reviewer password must contain at least 20 characters")
        self.store, self.password = store, (password or secrets.token_urlsafe(32)).encode()
        self.budget, self.session_id = budget, session_id
        self.public_url = public_url.rstrip("/")
        self.secure = self.public_url.startswith("https://")
        self.agent_runner, self.daily_runs = agent_runner, daily_runs
        self.login_attempts = defaultdict(list)
        self.lock = threading.Lock()
        self.dispatch_lock = threading.RLock()
        with store.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS web_runs (id TEXT PRIMARY KEY, started_at TEXT NOT NULL, status TEXT NOT NULL, report TEXT, inventory_version TEXT NOT NULL, event_count INTEGER NOT NULL)")
            db.execute("UPDATE web_runs SET status='INTERRUPTED' WHERE status='RUNNING'")
        self.followup = FollowUp(store)

    def session(self):
        expiry = str(int(time.time()) + 8 * 3600)
        return expiry + "." + hmac.new(self.password, expiry.encode(), hashlib.sha256).hexdigest()

    def authenticated(self, cookie):
        try:
            jar = SimpleCookie(cookie or "")
            expiry, signature = jar["pantry_session"].value.split(".")
            return int(expiry) > time.time() and hmac.compare_digest(signature, hmac.new(self.password, expiry.encode(), hashlib.sha256).hexdigest())
        except (KeyError, ValueError):
            return False

    def login(self, password, address):
        with self.lock:
            attempts = [t for t in self.login_attempts[address] if t > time.time() - 60]
            if len(attempts) >= 5:
                raise WorkflowError("LOGIN_RATE_LIMIT", "Too many attempts. Wait one minute.")
            attempts.append(time.time())
            self.login_attempts[address] = attempts
        if not isinstance(password, str) or not hmac.compare_digest(password.encode(), self.password):
            raise WorkflowError("LOGIN_FAILED", "Incorrect reviewer password")
        return self.session()

    def state(self):
        self.resume_pending()
        # All fields refer to the same SQLite read snapshot.
        with self.store.connection() as db:
            db.execute("BEGIN")
            fixture = self.store._context(db)
            cases = [self.store._case(db, row["inventory_id"]) for row in fixture["inventory"]["rows"]]
            latest = db.execute("SELECT id FROM web_runs ORDER BY rowid DESC LIMIT 1").fetchone()
            return {"inventory": fixture["inventory"], "scope": fixture["scope"], "policy": fixture["policy"], "source_metadata": fixture["acquisition"],
                    "cases": cases, "event_count": db.execute("SELECT count(*) FROM events").fetchone()[0],
                    "confirmation_count": db.execute("SELECT count(*) FROM confirmations").fetchone()[0],
                    "latest_run_id": latest["id"] if latest else None, "synthetic": True,
                    "demo_mode": self.budget is not None, "agent_followup": self.followup.state_in(db)}

    def start_agent(self, request_id, *, automatic=False):
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{8,80}", request_id):
            raise WorkflowError("INVALID_REQUEST_ID", "Supply a stable request ID")
        with self.dispatch_lock, self.store.transaction() as db:
            prior = db.execute("SELECT id FROM web_runs WHERE id=?", (request_id,)).fetchone()
            if prior:
                return {"id": request_id}
            if automatic and not self.followup.state_in(db)["pending"]:
                return None
            if db.execute("SELECT 1 FROM web_runs WHERE status='RUNNING'").fetchone():
                raise WorkflowError("AGENT_BUSY", "An agent run is already in progress")
            count = db.execute("SELECT count(*) FROM web_runs WHERE started_at >= ?", (now()[:10],)).fetchone()[0]
            if count >= self.daily_runs:
                raise WorkflowError("AGENT_DAILY_LIMIT", "This demo's daily agent-run limit has been reached")
            if self.budget:
                self.budget.reserve(self.session_id, request_id)
            try:
                db.execute("INSERT INTO web_runs VALUES (?,?, 'RUNNING', NULL, ?, ?)",
                           (request_id, now(), self.store._meta(db, "inventory_version"), db.execute("SELECT count(*) FROM events").fetchone()[0]))
                self.followup.record_run(db, request_id, automatic, db.execute("SELECT count(*) FROM events").fetchone()[0])
            except Exception:
                if self.budget:
                    self.budget.finish(self.session_id, request_id, "FAILED")
                raise
        threading.Thread(target=self._run, args=(request_id,), daemon=True, name="pantry-agent-"+request_id).start()
        return {"id": request_id}

    def resume_pending(self):
        with self.dispatch_lock:
            state = self.followup.state()
            if not state["pending"]:
                return
            try:
                self.start_agent("auto-event-" + str(state["pending_event"]), automatic=True)
            except WorkflowError as error:
                # Accepted evidence/receipts stay successful even if the model is busy or out of allowance.
                self.followup.notice("Follow-up queued: " + str(error))

    def agent_state(self):
        self.resume_pending()
        with self.store.connection() as db:
            db.execute("BEGIN")
            latest = db.execute("SELECT id,status FROM web_runs ORDER BY rowid DESC LIMIT 1").fetchone()
            return {"latest_run_id": latest["id"] if latest else None,
                    "status": latest["status"] if latest else "READY", "followup": self.followup.state_in(db),
                    "event_count": db.execute("SELECT count(*) FROM events").fetchone()[0]}

    def _run(self, request_id):
        try:
            report = self.agent_runner(self.store)
        except Exception:
            LOG.exception("Agent run failed: %s", request_id)
            report = {"status": "FAILED", "message": "Agent request failed; inspect service logs. No human actions were confirmed."}
        with self.store.transaction() as db:
            db.execute("UPDATE web_runs SET status=?, report=? WHERE id=?", (report["status"], encoded(report), request_id))
        if self.budget:
            self.budget.finish(self.session_id, request_id, report["status"])
        if report["status"] != "COMPLETE":
            self.followup.notice("Last briefing: " + report["status"] + ". The original report is retained; start a new run to retry.")
        if self.budget:
            self.budget.resume_pending()
        else:
            self.resume_pending()

    def run(self, request_id):
        with self.store.connection() as db:
            db.execute("BEGIN")
            row = db.execute("SELECT * FROM web_runs WHERE id=?", (request_id,)).fetchone()
            if not row:
                raise WorkflowError("UNKNOWN_RUN", "Agent run does not exist")
            result = dict(row)
            result["report"] = json.loads(result["report"]) if result["report"] else None
            result["current"] = row["inventory_version"] == self.store._meta(db, "inventory_version") and row["event_count"] == db.execute("SELECT count(*) FROM events").fetchone()[0]
            # Preserve the raw report in storage; serve prose only after validation.
            if result["report"] and (row["status"] != "COMPLETE" or not result["current"]):
                result["report"].pop("agent_explanation_unverified", None)
                result["report"].pop("briefing", None)
            with_context = db.execute("SELECT context FROM web_run_context WHERE run_id=?", (request_id,)).fetchone()
            result["trigger"] = json.loads(with_context["context"]) if with_context else {"kind": "manual"}
            return result

    def post(self, path, body):
        if self.budget and path in ("/api/evidence", "/api/confirm-hold"):
            if self.store.overview()["event_count"] >= 150:
                raise WorkflowError("DEMO_STEP_LIMIT", "This replay is full. Restart the demo for a fresh pantry.")
        if path == "/api/agent":
            return self.start_agent(body["request_id"])
        if path == "/api/follow-up":
            self.followup.enable(body["enabled"])
            return self.agent_state()
        if path == "/api/evidence":
            result = self.store.supply_evidence(body["inventory_id"], body["expected_version"], body["new_version"],
                                               body["changes"], body["actor"], channel="human_evidence_web")
            self.resume_pending()
            return result
        if path == "/api/confirm-hold":
            result = record_human_confirmation(self.store, HoldConfirmation(**body), channel="human_confirmation_web")
            self.resume_pending()
            return result
        raise WorkflowError("NOT_FOUND", "Unknown operation")


class Handler(BaseHTTPRequestHandler):
    server_version = "PantryReviewer/1"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        # Avoid logging user evidence, passwords, cookies, and URL query strings.
        LOG.info("HTTP request completed")

    @property
    def app(self):
        return getattr(self, "visitor_app", self.server.app)

    def visitor(self, create=False, fresh=False):
        if isinstance(self.server.app, DemoHost):
            self.visitor_app, self.pending_cookie = self.server.app.resolve(self.headers.get("Cookie"), create, fresh)
            return True
        return False

    def respond(self, status, value, mime="application/json; charset=utf-8", cookie=None):
        if cookie is None:
            cookie = getattr(self, "pending_cookie", None)
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if self.app.secure:
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        if cookie is not None:
            duration = 604800 if isinstance(self.server.app, DemoHost) else 28800
            self.send_header("Set-Cookie", f"pantry_session={cookie}; Path=/; HttpOnly; SameSite=Strict; Max-Age={duration if cookie else 0}" + ("; Secure" if self.app.secure else ""))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlsplit(self.path).path
        assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css"), "/polish.css": ("polish.css", "text/css")}
        if path in assets:
            filename, mime = assets[path]
            return self.respond(200, (STATIC / filename).read_bytes(), mime + "; charset=utf-8")
        if path == "/health":
            return self.respond(200, {"status": "ok"})
        try:
            if not self.visitor(create=path == "/api/state") and not self.app.authenticated(self.headers.get("Cookie")):
                return self.respond(401, {"error": "AUTH_REQUIRED", "message": "Sign in to the reviewer workspace"})
            if path == "/api/state":
                return self.respond(200, self.app.state())
            if path == "/api/agent-status":
                return self.respond(200, self.app.agent_state())
            if path.startswith("/api/agent/"):
                return self.respond(200, self.app.run(path.rsplit("/", 1)[-1]))
            if path == "/api/history":
                return self.respond(200, self.app.store.history(parse_qs(urlsplit(self.path).query)["id"][0]))
            if path == "/api/source":
                name = parse_qs(urlsplit(self.path).query)["name"][0]
                with self.app.store.connection() as db:
                    source = db.execute("SELECT content FROM sources WHERE name=?", (name,)).fetchone()
                if source is None:
                    raise WorkflowError("NOT_FOUND", "Pinned source does not exist")
                # Render even original HTML as inert plain text, not executable source content.
                return self.respond(200, source["content"], "text/plain; charset=utf-8")
            return self.respond(404, {"error": "NOT_FOUND"})
        except (WorkflowError, KeyError, ValueError) as error:
            self.respond(400, {"error": getattr(error, "code", "INVALID_REQUEST"), "message": str(error)})

    def do_POST(self):
        path = urlsplit(self.path).path
        if self.headers.get("Origin") != self.app.public_url or self.headers.get("X-Pantry-Request") != "reviewer":
            return self.respond(403, {"error": "INVALID_ORIGIN", "message": "Use the reviewer interface on this site"})
        if self.headers.get_content_type() != "application/json":
            return self.respond(415, {"error": "JSON_REQUIRED"})
        try:
            public = self.visitor(create=path == "/api/session", fresh=path == "/api/session")
            if not public and path != "/api/login" and not self.app.authenticated(self.headers.get("Cookie")):
                return self.respond(401, {"error": "AUTH_REQUIRED", "message": "Sign in again"})
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                return self.respond(413, {"error": "REQUEST_SIZE"})
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object")
            if public and path == "/api/session":
                return self.respond(200, {"fresh": True})
            if not public and path == "/api/login":
                # CloudFront forwards this header; local connections use peer address.
                address = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[-1].strip()
                cookie = self.app.login(body.get("password"), address)
                return self.respond(200, {"authenticated": True}, cookie=cookie)
            if not public and path == "/api/logout":
                return self.respond(200, {"authenticated": False}, cookie="")
            return self.respond(200, self.app.post(path, body))
        except WorkflowError as error:
            self.respond(409, {"error": error.code, "message": str(error)})
        except (ValueError, KeyError, TypeError):
            self.respond(400, {"error": "INVALID_REQUEST", "message": "Check the required fields and value types"})
        except Exception:
            LOG.exception("Reviewer request failed")
            self.respond(500, {"error": "SERVER_ERROR", "message": "Request failed. Refresh before retrying with the same request ID."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--db", type=Path, default=Path("outputs/web/pantry.sqlite3"))
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--private", action="store_true", help="Use the original shared reviewer password instead of anonymous demo sessions")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    store = Store(args.db)
    store.initialize(args.fixture)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    public_url = os.getenv("PANTRY_PUBLIC_URL", f"http://127.0.0.1:{args.port}")
    if not args.private:
        server.app = DemoHost(store, public_url, args.fixture)
        server.app.resume_pending(load_saved=True)
        print(f"Public synthetic demo listening on {args.host}:{args.port}", flush=True)
        server.serve_forever()
        return
    password = os.getenv("PANTRY_REVIEWER_PASSWORD", "")
    password_file = os.getenv("PANTRY_PASSWORD_FILE")
    if password_file:
        password = Path(password_file).read_text().strip()
    if not password and args.host in ("127.0.0.1", "localhost"):
        password_path = args.db.parent / "reviewer-password.txt"
        if not password_path.exists():
            password_path.write_text(secrets.token_urlsafe(30), encoding="utf-8")
        password = password_path.read_text().strip()
        print(f"Local reviewer password file: {password_path.resolve()}", flush=True)
    server.app = Application(store, password, public_url)
    server.app.resume_pending()
    print(f"Reviewer server listening on {args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
