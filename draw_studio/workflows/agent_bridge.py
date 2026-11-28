"""Authenticated loopback channel to the editor snapshot for one active turn."""
from __future__ import annotations

import hmac
import json
import logging
import secrets
import threading
from contextlib import contextmanager
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Literal

from .agent_tools import TOOLS
from .harness_errors import HarnessError

StopState = Literal["cancelled", "idle", "unconfirmed"]
log = logging.getLogger(__name__)


def tool_event(name, args, call_id, ok):
    event = {"type": "tool", "name": name, "call_id": call_id, "ok": ok}
    if isinstance(args, dict) and "op" in args:
        event["op"] = args["op"] if isinstance(args["op"], str) else None
    return event


class ToolBridge:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self.active = None
        self.control_port = None
        self.pid = None
        self.lock = threading.Lock()

    @contextmanager
    def bind(self, editor, emit, cancel):
        with self.lock:
            self.active = editor, emit, cancel
        try:
            yield
        finally:
            with self.lock:
                self.active = None

    def handle(self, path, body):
        if not isinstance(body, dict):
            raise HarnessError("invalid_argument")
        with self.lock:
            if path == "/ready":
                port, pid = body.get("port"), body.get("pid")
                if self.control_port or type(port) is not int or not 0 < port < 65536 or type(pid) is not int or pid <= 0:
                    raise HarnessError("invalid_argument")
                self.control_port, self.pid = port, pid
                return {"ok": True}
            active = self.active
        if path not in ("/tool", "/context"):
            raise HarnessError("not_found")
        if not active or active[2].is_set():
            raise HarnessError("busy")
        editor, emit, _ = active
        if path == "/context":
            return editor.context()
        name, args = body.get("name"), body.get("args")
        if not isinstance(name, str) or name not in TOOLS:
            raise HarnessError("invalid_argument")
        call_id = secrets.token_hex(8)
        emit(tool_event(name, args, call_id, None))
        ok = False
        try:
            value = editor.call(name, args)
            ok = True
            return value
        finally:
            emit(tool_event(name, args, call_id, ok))

    def interrupt(self) -> StopState:
        if not self.control_port:
            return "unconfirmed"
        conn = HTTPConnection("127.0.0.1", self.control_port, timeout=2)
        try:
            conn.request("POST", "/stop", body=b"", headers={"Authorization": "Bearer " + self.token})
            response = conn.getresponse()
            body = response.read(1024)
            if response.status == 204:
                return "cancelled"
            if response.status == 200 and json.loads(body) == {"state": "idle"}:
                return "idle"
        except (OSError, HTTPException, ValueError):
            pass
        finally:
            conn.close()
        return "unconfirmed"

    @contextmanager
    def serve(self):
        bridge = self
        authorization = ("Bearer " + self.token).encode()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), authorization):
                    self.reply(403, HarnessError("invalid_argument").body())
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 100_000:
                        raise ValueError("body length")
                    self.connection.settimeout(5)
                    payload = self.rfile.read(length)
                    body = json.loads(payload, parse_constant=reject_constant)
                except (ValueError, OSError):
                    self.reply(400, HarnessError("invalid_argument").body())
                    return
                try:
                    result = bridge.handle(self.path, body)
                    raw = json.dumps(result, ensure_ascii=False, allow_nan=False).encode()
                except HarnessError as exc:
                    self.reply(exc.status, exc.body())
                except Exception:
                    log.exception("Workflow tool bridge failed")
                    self.reply(500, HarnessError("internal_error").body())
                else:
                    self.send_json(200, raw)

            def reply(self, status, body):
                self.send_json(status, json.dumps(body, ensure_ascii=False).encode())

            def send_json(self, status, raw):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.1), daemon=True)
            thread.start()
            try:
                yield {"STUDIO_TOOL_URL": f"http://127.0.0.1:{server.server_port}/tool", "STUDIO_TOOL_TOKEN": self.token}
            finally:
                server.shutdown()
                thread.join()


def reject_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")
