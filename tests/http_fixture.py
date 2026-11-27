"""Loopback ASGI and model servers and image data used by HTTP and browser tests."""
import io
import json
import socket
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import uvicorn
from PIL import Image


@contextmanager
def serving(app):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                if not thread.is_alive() or time.monotonic() >= deadline:
                    raise RuntimeError("HTTP test server failed to start")
                time.sleep(.01)
            yield f"http://127.0.0.1:{sock.getsockname()[1]}"
        finally:
            server.should_exit = True
            thread.join(10)
            if thread.is_alive():
                raise RuntimeError("HTTP test server failed to stop")


def png(size=(900, 600), color="navy"):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


@contextmanager
def gateway():
    """Native endpoints with two paginated providers, real auth checks and captured image parts."""
    calls = []
    key = "local-test-credential"
    class Gateway(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_doc(self, value, code=200):
            raw = json.dumps(value).encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(raw)

        def handle_api(self):
            path = urlsplit(self.path).path
            query = urlsplit(self.path).query
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"]))) if self.command == "POST" else {}
            calls.append((path, dict((k.lower(), v) for k, v in self.headers.items()), body))
            if path.startswith("/bad/"):
                return self.send_doc({"error": key}, 403)
            if path.startswith("/open/v1/") and self.headers.get("Authorization") == "Bearer " + key:
                if path.endswith("/models"):
                    return self.send_doc({"data": [{"id": "open-model"}]})
                if path.endswith("/chat/completions"):
                    return self.send_doc({"choices": [{"message": {"content": [{"type": "text", "text": "open result"}]}}]})
            if self.headers.get("x-api-key") == key and self.headers.get("anthropic-version") == "2023-06-01":
                if path == "/claude/v1/models":
                    return self.send_doc({"data": [{"id": "anthropic-alt"}], "has_more": False} if query == "after_id=a" else
                                         {"data": [{"id": "anthropic-model"}], "has_more": True, "last_id": "a"})
                if path == "/claude/v1/messages":
                    return self.send_doc({"content": [{"type": "text", "text": "anthropic "}, {"type": "text", "text": "result"}]})
            if self.headers.get("x-goog-api-key") == key:
                if path == "/google/v1beta/models":
                    if query == "pageToken=next":
                        return self.send_doc({"models": [{"name": "models/gemini-model", "supportedGenerationMethods": ["generateContent"]}]})
                    return self.send_doc({"models": [{"name": "models/embed", "supportedGenerationMethods": ["embedContent"]}], "nextPageToken": "next"})
                if path == "/google/v1beta/models/gemini-model:generateContent":
                    guide = body.get("systemInstruction", {}).get("parts", [{}])[0].get("text", "")
                    answer = '{"selected":[1]}' if "筛选" in guide else "gemini result"
                    return self.send_doc({"candidates": [{"content": {"parts": [{"thought": True, "text": "hidden"}, {"text": answer}]}}]})
            self.send_doc({"error": "unexpected endpoint"}, 404)

        do_POST = do_GET = handle_api

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Gateway)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{srv.server_port}", key, calls
    finally:
        srv.shutdown()
        srv.server_close()
        t.join()
