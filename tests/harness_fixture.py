"""Deterministic streaming model and a real dsh plugin for session-lifetime tests."""
import json
import threading
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

from draw_studio.workflows import copilot


@contextmanager
def stateful_model(directory):
    plugin = directory / "session-counter.mjs"
    plugin.write_text("""
export const name = 'session-counter'
export const inject = ['tools']
export function apply(ctx) {
  let count = 0
  ctx.tools.register({
    name: 'test_counter', description: 'Inspect this plugin instance and the current editor',
    parameters: {type:'object',properties:{op:{type:'string'}},additionalProperties:false},
    output: {schema:{type:'string'},render:(_,value)=>[{type:'text',text:value}]},
    async execute(_args, exec) {
      const response = await fetch(new URL('/context', process.env.STUDIO_TOOL_URL), {method:'POST',signal:exec.signal,
        headers:{Authorization:'Bearer '+process.env.STUDIO_TOOL_TOKEN,'Content-Type':'application/json'},
        body:'{}'})
      const editor = await response.json()
      return JSON.stringify({count:++count,pid:process.pid,selected:editor.selected_step,topic:editor.topic})
    },
  })
}
""", encoding="utf-8")
    state = SimpleNamespace(held=threading.Event(), release=threading.Event(), requests=[], tools=[])
    original = copilot._patch

    def with_plugin(provider, model, budgets):
        return [*original(provider, model, budgets), {"insert": [{"id": "session-counter", "name": str(plugin)}]}]

    class Model(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            rows = payload["messages"]
            state.requests.append(rows)
            state.tools.append([tool["function"]["name"] for tool in payload.get("tools", [])])
            last = rows[-1]
            content = last.get("content", "")
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content)
            if "MODEL_FAIL" in content:
                self.send_response(400)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            if last["role"] == "tool":
                delta, reason = {"role": "assistant", "content": content}, "stop"
            elif "HOLD_ACTIVE_TURN" in content:
                state.held.set()
                state.release.wait(12)
                delta, reason = {"role": "assistant", "content": "late"}, "stop"
            else:
                tool = "studio_shot_timing" if "USE_TIMING" in content else "test_counter"
                args = '{}' if tool == "studio_shot_timing" else '{"op":"inspect"}'
                delta = {"role": "assistant", "tool_calls": [{"index": 0, "id": "call_" + uuid.uuid4().hex,
                         "type": "function", "function": {"name": tool, "arguments": args}}]}
                reason = "tool_calls"
            try:
                for fragment, finish in [(delta, None), ({}, reason)]:
                    chunk = {"id": "chat-test", "model": payload["model"], "object": "chat.completion.chunk",
                             "created": 1, "choices": [{"index": 0, "delta": fragment, "finish_reason": finish}]}
                    self.wfile.write(b"data: " + json.dumps(chunk).encode() + b"\n\n")
                self.wfile.write(b"data: [DONE]\n\n")
            except (BrokenPipeError, ConnectionResetError):
                pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Model) as server, patch.object(copilot, "_patch", with_plugin):
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/v1", state
        finally:
            state.release.set()
            server.shutdown()
            thread.join()
