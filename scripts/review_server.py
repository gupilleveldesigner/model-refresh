#!/usr/bin/env python3
"""Show the Phase 3 report and receive the user's decisions without any file handling.

Serves report.html on a loopback port, opens it in the browser, and waits. When
the user presses "submit" in the page, the decisions are validated against
report.json and written to <RUN_DIR>/decisions.json. Nothing is downloaded or
uploaded by hand.

Run it in the background where the host reports a finished background command
(Claude Code), or with --detach where it does not (the server keeps running and
the agent reads decisions.json when the user returns to the chat).

Events are printed as JSON lines. Exit code 0 = decisions received (or nothing
needed approval), 3 = nobody submitted before the timeout, 1 = error.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from record_decisions import approval_findings, write_packet
from render_report import canonical_hash, load_saved, render
from validate_decisions import DECISIONS_NAME, validate

STATE_NAME = "review-server.json"
LOG_NAME = "review-server.log"
MAX_BODY = 256 * 1024
EXIT_TIMEOUT = 3


def emit(event: str, **fields) -> None:
    print(json.dumps({"event": event, **fields}, ensure_ascii=False), flush=True)


class ReviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, report: dict, page: str, decisions_path: Path):
        super().__init__(("127.0.0.1", port), Handler)
        self.report = report
        self.page = page.encode("utf-8")
        self.decisions_path = decisions_path
        self.token = secrets.token_urlsafe(18)
        self.result: dict | None = None
        self.done = threading.Event()
        self.lock = threading.Lock()

    @property
    def origins(self) -> set[str]:
        port = self.server_address[1]
        return {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/?t={self.token}"


class Handler(BaseHTTPRequestHandler):
    server: ReviewServer

    def log_message(self, *args) -> None:  # keep stdout for JSON events only
        return

    def reply(self, status: int, body: bytes = b"", content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def reply_json(self, status: int, payload: dict) -> None:
        self.reply(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def trusted_host(self) -> bool:
        # A page on another site cannot forge the Host header, so this stops DNS rebinding.
        return f"http://{self.headers.get('Host', '')}" in self.server.origins

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if not self.trusted_host():
            return self.reply_json(403, {"ok": False, "errors": ["untrusted host"]})
        if parsed.path != "/":
            return self.reply(404)
        token = (parse_qs(parsed.query).get("t") or [""])[0]
        if not hmac.compare_digest(token, self.server.token):
            return self.reply_json(403, {"ok": False, "errors": ["missing or wrong token"]})
        self.reply(200, self.server.page, "text/html; charset=utf-8")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/submit":
            return self.reply(404)
        origin = self.headers.get("Origin")
        if not self.trusted_host() or (origin is not None and origin not in self.server.origins):
            return self.reply_json(403, {"ok": False, "errors": ["untrusted origin"]})
        if not hmac.compare_digest(self.headers.get("X-Review-Token", ""), self.server.token):
            return self.reply_json(403, {"ok": False, "errors": ["missing or wrong token"]})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.reply_json(411, {"ok": False, "errors": ["content length required"]})
        if not 0 < length <= MAX_BODY:
            return self.reply_json(413, {"ok": False, "errors": ["body too large"]})
        try:
            packet = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return self.reply_json(400, {"ok": False, "errors": ["body is not JSON"]})
        if not isinstance(packet, dict):
            return self.reply_json(400, {"ok": False, "errors": ["body must be an object"]})
        packet["source"] = "review_server"
        packet["received_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.server.lock:
            if self.server.result is not None:
                return self.reply_json(409, {"ok": False, "errors": ["decisions were already submitted"]})
            result = validate(self.server.report, packet)
            if not result["valid"] or not result["executable"]:
                errors = result["errors"] or ["undecided items remain"]
                return self.reply_json(400, {"ok": False, "errors": errors})
            write_packet(self.server.decisions_path, packet)
            result["decisions"] = str(self.server.decisions_path)
            self.server.result = result
        self.reply_json(200, {"ok": True, "approved": result["approved"], "rejected": result["rejected"], "deferred": result["deferred"]})
        self.server.done.set()


def bind(report: dict, page: str, decisions_path: Path, port: int | None) -> ReviewServer:
    if port is None:
        # A stable port per report keeps the page's draft choices (localStorage is
        # per origin) if the server is restarted for the same report.
        port = 49152 + int(canonical_hash(report)[:8], 16) % 16000
        try:
            return ReviewServer(port, report, page, decisions_path)
        except OSError:
            port = 0
    return ReviewServer(port, report, page, decisions_path)


def serve(args: argparse.Namespace, report_path: Path, report: dict) -> int:
    run_dir = report_path.parent
    decisions_path = run_dir / DECISIONS_NAME
    state_path = run_dir / STATE_NAME
    html_path = report_path.with_suffix(".html")
    page = render(report, canonical_hash(report), load_saved(report_path, report))
    html_path.write_text(page, encoding="utf-8")

    if not approval_findings(report):
        opened = False if args.no_open else webbrowser.open(html_path.as_uri())
        emit("no_approvals", report=str(html_path), browser_opened=bool(opened))
        return 0

    server = bind(report, page, decisions_path, args.port)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    thread.start()
    state = {"url": server.url, "pid": os.getpid(), "report": str(html_path), "decisions": str(decisions_path),
             "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "timeout_seconds": args.timeout}
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        opened = False if args.no_open else webbrowser.open(server.url)
        emit("serving", **state, browser_opened=bool(opened))
        submitted = server.done.wait(args.timeout)
        time.sleep(0.3)  # let the page receive its response before the port closes
    finally:
        server.shutdown()
        server.server_close()
        try:
            state_path.unlink()
        except OSError:
            pass
    if not submitted or server.result is None:
        emit("timeout", report=str(html_path),
             hint="No submission arrived. Ask for the decisions in chat and record them with record_decisions.py.")
        return EXIT_TIMEOUT
    emit("submitted", **server.result)
    return 0


def detach(args: argparse.Namespace, report_path: Path) -> int:
    """Start the server as an independent process and return once it is listening."""
    run_dir = report_path.parent
    state_path = run_dir / STATE_NAME
    try:
        state_path.unlink()
    except OSError:
        pass
    command = [sys.executable, str(Path(__file__).resolve()), str(report_path), "--no-open", "--timeout", str(args.timeout)]
    if args.port is not None:
        command += ["--port", str(args.port)]
    options: dict = {"stdin": subprocess.DEVNULL, "cwd": str(run_dir)}
    if os.name == "nt":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    with (run_dir / LOG_NAME).open("ab") as log:
        child = subprocess.Popen(command, stdout=log, stderr=log, **options)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if state_path.is_file():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except ValueError:
                state = None
            if state:
                opened = False if args.no_open else webbrowser.open(state["url"])
                emit("serving", **state, detached=True, browser_opened=bool(opened))
                return 0
        if child.poll() is not None:
            break
        time.sleep(0.1)
    if child.poll() == 0:  # nothing needed approval, so the child rendered the page and left
        html_path = report_path.with_suffix(".html")
        opened = False if args.no_open else webbrowser.open(html_path.as_uri())
        emit("no_approvals", report=str(html_path), browser_opened=bool(opened))
        return 0
    raise ValueError(f"review server did not start; see {run_dir / LOG_NAME}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report_json")
    parser.add_argument("--timeout", type=int, default=1500, help="seconds to wait for a submission (default 1500)")
    parser.add_argument("--port", type=int, help="loopback port; default is derived from the report")
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    parser.add_argument("--detach", action="store_true", help="return immediately and keep serving in an independent process")
    args = parser.parse_args()
    report_path = Path(args.report_json).expanduser().resolve()
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    if args.detach:
        return detach(args, report_path)
    return serve(args, report_path, report)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
