"""Runtime regressions across the native adapter, profiles, and the loopback bridge."""
import asyncio
import json
import os
import shutil
import stat
import subprocess
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from draw_studio.workflows import agent_plugins as plugins, copilot
from draw_studio.workflows.agent_bridge import ToolBridge
from draw_studio.workflows.harness_errors import HarnessError
from tests.harness_fixture import stateful_model
from tests.test_harness_tools import editor, step

KEY = "wr_" + "a" * 32


def notification(method, **fields):
    return SimpleNamespace(method=method, payload={"sessionId": KEY, **fields})


def event(kind, **data):
    return notification("session.event", event={"type": kind, "data": data})


ADMISSION = event("agent/inbox/spliced", inserted=[{"id": "current"}])
IDLE = notification("session.status", status="idle")
COMPLETE = event("turn/end", reason={"kind": "completed"})


def provider(base="https://model.example/v1", **attrs):
    return SimpleNamespace(id="llm_a", kind="openai", base=base, key="fixture-key", **attrs)


class HarnessRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def wait_turn(self, *notes, cancel=None, state="cancelled", clock=None):
        conversation = copilot.Conversation(self.root, KEY, True)
        conversation.bridge = Mock()
        conversation.bridge.interrupt.return_value = state
        updates = []
        if clock is None:
            clock = iter(range(100))
        with patch.object(copilot.time, "monotonic", side_effect=clock):
            try:
                answer = conversation._wait_turn(SimpleNamespace(next=Mock(side_effect=notes)),
                                                 "current", updates.append, cancel or threading.Event())
            except HarnessError as error:
                answer = error
        return answer, updates, conversation.bridge.interrupt.call_count

    def test_cancel_waits_for_the_current_receipt(self):
        cancel = threading.Event()
        cancel.set()
        result, _, calls = self.wait_turn(IDLE, event("agent/inbox/spliced", inserted=[{"id": "older"}]),
                                          IDLE, ADMISSION, IDLE, cancel=cancel, clock=iter([0, 0, 0, 0, 0, 0]))
        self.assertIsInstance(result, copilot.SettledTurn)
        self.assertEqual(result.code, "turn_stopped")
        self.assertEqual(calls, 1)

        result, _, calls = self.wait_turn(IDLE, cancel=cancel, clock=iter([0, 0, 6]))
        self.assertIs(type(result), HarnessError)
        self.assertEqual(result.code, "turn_stopped")
        self.assertEqual(calls, 0)

    def test_stop_results_and_timeout_control_reuse(self):
        cancel = threading.Event()
        cancel.set()
        result, _, calls = self.wait_turn(ADMISSION, cancel=cancel, state="idle")
        self.assertIsInstance(result, copilot.SettledTurn)
        self.assertEqual((result.code, calls), ("turn_stopped", 1))
        result, _, calls = self.wait_turn(ADMISSION, cancel=cancel, state="unconfirmed")
        self.assertIs(type(result), HarnessError)
        self.assertEqual((result.code, calls), ("turn_stopped", 1))
        result, _, _ = self.wait_turn(ADMISSION, IDLE, clock=iter([0, 1, 181]))
        self.assertEqual(result.code, "turn_timeout")

    def test_error_followed_by_idle_finishes_without_a_turn_end(self):
        result, _, _ = self.wait_turn(IDLE, ADMISSION, IDLE)
        self.assertIsInstance(result, copilot.SettledTurn)
        self.assertEqual(result.code, "model_error")
        result, _, _ = self.wait_turn(IDLE, notification("session.error"), IDLE)
        self.assertIs(type(result), HarnessError)
        self.assertEqual(result.code, "model_error")
        result, _, _ = self.wait_turn(IDLE, notification("session.status", status="running"), IDLE)
        self.assertEqual(result.code, "model_error")
        result, _, _ = self.wait_turn(ADMISSION, event("turn/end", reason={"kind": "error"}), IDLE)
        self.assertEqual(result.code, "model_error")

    def test_plugin_events_keep_all_names_and_ops_without_duplicate_builtins(self):
        result, events, _ = self.wait_turn(
            IDLE, ADMISSION,
            event("tool/call", name="studio_read_workflow", callId="builtin"),
            event("tool/result", message={"toolCallId": "builtin"}),
            event("tool/call", name="studio_shot_timing", callId="timing", arguments="{}"),
            event("tool/call", name="another_plugin", callId="plugin", arguments='{"op":"inspect"}'),
            event("tool/result", message={"toolCallId": "plugin", "isError": True}),
            event("tool/result", message={"toolCallId": "timing"}),
            event("tool/result", message={"toolCallId": "plugin"}),
            event("assistant/message", message={"content": [{"type": "text", "text": "Done"}]}),
            COMPLETE, IDLE,
        )
        self.assertEqual(result, "Done")
        self.assertEqual([(e["name"], e.get("op"), e["ok"]) for e in events], [
            ("studio_shot_timing", None, None), ("another_plugin", "inspect", None),
            ("another_plugin", "inspect", False), ("studio_shot_timing", None, True),
        ])
        self.assertNotIn("op", events[0])
        self.assertEqual(events[1]["call_id"], events[2]["call_id"])

    def test_bridge_auth_limits_ready_context_and_failure_events(self):
        bridge = ToolBridge()
        tools = editor(step("script", "llm_script"))
        events = []
        cancel = threading.Event()
        with bridge.serve() as env, requests.Session() as http:
            http.trust_env = False
            url = env["STUDIO_TOOL_URL"].removesuffix("/tool")
            token = env["STUDIO_TOOL_TOKEN"]

            def post(path, *, expected=200, authenticated=True, **kwargs):
                headers = {"Authorization": "Bearer " + token} if authenticated else {}
                res = http.post(url + path, timeout=3, headers=headers, **kwargs)
                self.assertEqual(res.status_code, expected, res.text[:160])
                return res.json()

            self.assertEqual(post("/context", expected=403, authenticated=False, json={})["code"], "invalid_argument")
            post("/context", expected=400, data=b"x" * 100001)
            post("/context", expected=400, data=b'{"n":NaN}')
            post("/ready", json={"port": 12345, "pid": 1})
            post("/ready", expected=400, json={"port": 12345, "pid": 1})
            self.assertEqual(post("/tool", expected=409,
                                  json={"name": "studio_read_workflow", "args": {}})["code"], "busy")
            with bridge.bind(tools, events.append, cancel):
                for _ in range(33):
                    self.assertEqual(post("/context", json={})["selected_step"], "script")
                self.assertEqual(events, [])
                self.assertEqual(tools.calls, [])
                call = {"name": "studio_read_workflow", "args": {"op": "inspect"}}
                post("/tool", expected=400, json=call)
                self.assertEqual([(e["op"], e["ok"]) for e in events], [("inspect", None), ("inspect", False)])
                with patch.object(tools, "call", side_effect=RuntimeError("fixture")), self.assertLogs(
                    "draw_studio.workflows.agent_bridge", level="ERROR",
                ):
                    self.assertEqual(post("/tool", expected=500, json=call)["code"], "internal_error")
                self.assertFalse(events[-1]["ok"])
                cancel.set()
                post("/context", expected=409, json={})
                post("/tool", expected=409, json=call)

    @unittest.skipUnless(shutil.which("node"), "Node is required for the JavaScript bridge contract")
    def test_real_js_stop_bridge_has_three_states(self):
        path = Path(copilot.__file__).with_name("dsh_tools.mjs").as_uri()
        js = """
          const { apply } = await import(process.argv[1])
          const states = ['running', 'idle', undefined]
          let cancellations = 0
          await apply({
            agents: { get() {
              const status = states.shift()
              return status && { status, cancel() { cancellations++ } }
            } },
            on() {}, tools: { register() {} },
          }, { tools: [] })
          process.on('SIGTERM', () => process.exit(cancellations === 1 ? 0 : 1))
          console.log('ready')
        """
        bridge = ToolBridge()
        with bridge.serve() as env, subprocess.Popen(
            ["node", "--input-type=module", "-e", js, path], env={**os.environ, **env, "STUDIO_SESSION_ID": KEY},
            stdout=subprocess.PIPE, text=True,
        ) as process:
            try:
                self.assertEqual(process.stdout.readline().strip(), "ready")
                with requests.Session() as http:
                    http.trust_env = False
                    response = http.post(f"http://127.0.0.1:{bridge.control_port}/stop",
                                         headers={"Authorization": "Bearer wrong"}, timeout=3)
                    self.assertEqual(response.status_code, 403)
                self.assertEqual([bridge.interrupt() for _ in range(3)], ["cancelled", "idle", "unconfirmed"])
            finally:
                process.terminate()
                self.assertEqual(process.wait(timeout=5), 0)

    def test_corrupt_native_session_backup_and_private_files(self):
        conversation = copilot.Conversation(self.root, KEY, True)
        conversation.directory.mkdir(parents=True)
        marker = conversation.directory / "native-session"
        records = conversation.directory / "sessions"
        records.mkdir()
        marker.write_text(KEY)
        (records / "retained.log").write_text("recoverable data")
        resumes = []

        @contextmanager
        def start(*args, resume):
            resumes.append(resume)
            if resume:
                raise copilot.NativeRestoreError()
            plugins.write_private(marker, KEY)
            yield object(), object()

        self.addCleanup(conversation.dispose)
        with patch.object(conversation, "_start", side_effect=start):
            self.assertEqual(conversation.prepare(provider(), "demo"), "new")
        self.assertEqual(resumes, [True, False])
        self.assertEqual(next(conversation.directory.glob("native-session.corrupt.*")).read_text(), KEY)
        self.assertEqual((next(conversation.directory.glob("sessions.corrupt.*")) / "retained.log").read_text(),
                         "recoverable data")
        recent = conversation.directory / "recent.json"
        recent.write_text("{broken")
        with self.assertLogs(copilot.__name__, level="WARNING"):
            self.assertEqual(copilot.recent_exchanges(self.root, KEY), [])
        with self.assertLogs(copilot.__name__, level="WARNING"):
            conversation.remember({"id": "one", "user": "hi", "answer": "ok", "tools": [], "state": "done"})
        self.assertEqual([row["id"] for row in copilot.recent_exchanges(self.root, KEY)], ["one"])
        recent.write_text('{"bad":"shape"}')
        with self.assertLogs(copilot.__name__, level="WARNING"):
            self.assertEqual(copilot.recent_exchanges(self.root, KEY), [])
        for path in (conversation.home, conversation.directory.parent, conversation.directory, records):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        for path in (marker, recent, conversation.directory / "workflow.patch.yml", conversation.home / "active.json"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_native_restore_leaves_an_occupied_record_in_place(self):
        first = copilot.Conversation(self.root, KEY, True)
        second = copilot.Conversation(self.root, KEY, True)
        self.addCleanup(first.dispose)
        self.addCleanup(second.dispose)
        with stateful_model(self.root) as (gateway, _):
            model = provider(gateway)
            first.run(editor(), model, "test", "seed", (), lambda _: None, threading.Event())
            record = next((first.directory / "sessions").rglob("session.*.jsonl"))
            self.assertEqual(stat.S_IMODE(record.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(record.parent.stat().st_mode), 0o700)
            with self.assertRaises(HarnessError) as caught:
                second.prepare(model, "test")
            self.assertEqual(caught.exception.code, "busy")
            self.assertTrue(record.is_file())
            self.assertEqual(list(first.directory.glob("*.corrupt.*")), [])

    def test_proxy_signature_private_bypass_and_model_budgets(self):
        p = provider()
        self.assertEqual(copilot._profile_signature(p, "a", environ={"HTTP_PROXY": "http://a"}),
                         copilot._profile_signature(p, "a", environ={"hTtP_pRoXy": "http://a"}))
        self.assertNotEqual(copilot._profile_signature(p, "a", environ={"http_proxy": "http://a"}),
                            copilot._profile_signature(p, "a", environ={"http_proxy": "http://b"}))
        outside = copilot._proxy_env(p, {"HTTPS_PROXY": "http://exit", "NO_PROXY": "example.local"})
        self.assertEqual(outside["https_proxy"], "http://exit")
        self.assertIn("127.0.0.1", outside["no_proxy"])
        for host in ("127.0.0.1", "192.168.1.1", "localhost", "host.docker.internal", "[::1]"):
            with self.subTest(host=host):
                env = copilot._proxy_env(provider(f"http://{host}:8080/v1"),
                                         {"HTTP_PROXY": "http://exit", "all_proxy": "http://exit", "hTtPs_PrOxY": "http://exit"})
                self.assertEqual([env[name] for name in ("HTTP_PROXY", "all_proxy", "hTtPs_PrOxY")], ["", "", ""])
                self.assertIn(host.strip("[]"), env["NO_PROXY"])
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(copilot._budgets(p), (128000, 8192, 4096))
        with patch.dict(os.environ, {"QP_HARNESS_CONTEXT_WINDOW": "40000", "QP_HARNESS_MODEL_MAX_TOKENS": "6000",
                                     "QP_HARNESS_MAX_TOKENS": "5500"}):
            self.assertEqual(copilot._budgets(p), (40000, 6000, 5500))
            budgets = copilot._budgets(provider(context_window=1200, model_max_tokens=900, max_tokens=1000))
            self.assertEqual(budgets, (1200, 900, 900))
            route = copilot._patch(p, "a", budgets)[-1]["insert"][1]["config"]["providers"]["studio"]["models"][0]
            self.assertEqual((route["contextWindow"], route["maxTokens"]), (1200, 900))

    def test_closed_event_loop_stops_the_worker(self):
        stopped = threading.Event()

        @contextmanager
        def lease(root, key, turn_id, cancel):
            class Slot:
                def run(self, *args, **kwargs):
                    args[-2]({"type": "session", "state": "new", "process_id": 1})
                    if cancel.is_set():
                        stopped.set()
                    raise HarnessError("turn_stopped")
            yield Slot()

        async def check():
            tools = editor()
            tools.runtime.harness_sessions = SimpleNamespace(lease=lease)
            tools.runtime.root = self.root
            loop = asyncio.get_running_loop()
            with patch.object(loop, "call_soon_threadsafe", side_effect=RuntimeError("closed")):
                stream = copilot.turn_events(tools, provider(), "test", "hello", None)
                self.assertEqual((await anext(stream))["type"], "started")
                self.assertTrue(stopped.wait(2))
                await stream.aclose()
        asyncio.run(check())

    def test_forget_blocks_same_key_and_disposes_without_the_lock(self):
        sessions = copilot.HarnessSessions()
        cancel, leased, finish, disposing, release = [threading.Event() for _ in range(5)]

        def hold():
            with sessions.lease(self.root, KEY, "turn", cancel) as slot:
                def dispose():
                    disposing.set()
                    if not release.wait(3):
                        raise TimeoutError
                    raise RuntimeError("fixture dispose error")
                slot.dispose = dispose
                leased.set()
                if not finish.wait(3):
                    raise TimeoutError

        with ThreadPoolExecutor(3) as pool:
            current = pool.submit(hold)
            try:
                self.assertTrue(leased.wait(2))
                removing = pool.submit(sessions.forget, self.root, KEY)
                self.assertTrue(cancel.wait(2))
                with self.assertRaises(HarnessError) as rejected:
                    with sessions.lease(self.root, KEY, "second", threading.Event()):
                        self.fail("forgetting key leased")
                self.assertEqual(rejected.exception.code, "busy")
                finish.set()
                self.assertTrue(disposing.wait(2))
                repeated = pool.submit(sessions.forget, self.root, KEY)
                with sessions.lease(self.root, "wr_other", "available", threading.Event()):
                    self.assertIn(KEY, sessions.forgetting)
                release.set()
                with self.assertRaisesRegex(RuntimeError, "fixture dispose error"):
                    removing.result(2)
                repeated.result(2)
                current.result(2)
                with sessions.lease(self.root, KEY, "third", threading.Event()):
                    self.assertNotIn(KEY, sessions.forgetting)
            finally:
                finish.set()
                release.set()
        sessions.shutdown()

    def test_eviction_and_ephemeral_cleanup_dont_hold_pool_lock(self):
        sessions = copilot.HarnessSessions(capacity=1)
        disposing, release = threading.Event(), threading.Event()
        with sessions.lease(self.root, KEY, "one", threading.Event()) as old:
            def dispose():
                disposing.set()
                if not release.wait(3):
                    raise TimeoutError
            old.dispose = dispose

        def next_turn(cancel):
            with sessions.lease(self.root, "wr_next", "two", cancel):
                return cancel.is_set()

        cancel = threading.Event()
        with ThreadPoolExecutor(1) as pool:
            pending = pool.submit(next_turn, cancel)
            try:
                self.assertTrue(disposing.wait(2))
                self.assertTrue(sessions.interrupt("wr_next", "two"))
            finally:
                release.set()
            self.assertTrue(pending.result(2))
        with self.assertRaisesRegex(RuntimeError, "fixture cleanup error"):
            with sessions.lease(self.root, None, "temporary", threading.Event()) as temporary:
                temporary.dispose = Mock(side_effect=RuntimeError("fixture cleanup error"))
        self.assertFalse(sessions.disposing)
        sessions.shutdown()

    def test_ttl_only_reaps_expired_orphan_drafts(self):
        recent_key, saved_key, active_key = ("wr_" + x * 32 for x in "bcd")
        other = "wr_unrelated"
        sessions = copilot.HarnessSessions()
        folder = plugins.profile_home(self.root) / "conversations"
        for key in (KEY, recent_key, saved_key, active_key, other):
            draft = folder / key
            draft.mkdir(parents=True)
            if key != recent_key:
                old = time.time() - 30
                os.utime(draft, (old, old))
        with sessions.lease(self.root, active_key, "held", threading.Event()):
            sessions.prune_drafts(self.root, lambda key: key == saved_key, ttl=20)
        self.assertEqual(set(p.name for p in folder.iterdir()), {recent_key, saved_key, active_key, other})
        sessions.shutdown()

    def test_versioned_profiles_publish_without_touching_pinned_modules(self):
        home = plugins.profile_home(self.root)
        def install(_, profile):
            plugins._seed(home / "profiles" / profile.version, True)

        with patch.object(plugins, "_install", side_effect=install):
            plugins.change_plugin(self.root, plugins.PACKAGE, "install")
        with plugins.acquire_profile(self.root) as active:
            modules = home / "profiles" / active.version / "node_modules" / plugins.PACKAGE
            installed_script = (modules / "index.mjs").read_bytes()
            self.assertTrue(plugins.inventory(self.root)["plugin"]["enabled"])
            self.assertFalse(plugins.change_plugin(self.root, plugins.PACKAGE, "disable")["plugin"]["enabled"])
            disabled = plugins.active_version(self.root)
            self.assertNotEqual(active.version, disabled)
            self.assertTrue(plugins.change_plugin(self.root, plugins.PACKAGE, "enable")["plugin"]["enabled"])
            self.assertFalse((home / "profiles" / disabled).exists())
            self.assertFalse(plugins.change_plugin(self.root, plugins.PACKAGE, "remove")["plugin"]["installed"])
            self.assertEqual((modules / "index.mjs").read_bytes(), installed_script)
            plugins.prune_profiles(self.root)
            self.assertTrue(modules.exists())
        self.assertFalse(modules.exists())

        current = plugins.active_version(self.root)
        with patch.object(plugins.shutil, "which", return_value=None), self.assertRaises(HarnessError) as unavailable:
            plugins.change_plugin(self.root, plugins.PACKAGE, "install")
        self.assertEqual(unavailable.exception.code, "plugin_unavailable")
        self.assertEqual(plugins.active_version(self.root), current)
        self.assertEqual([path.name for path in (home / "profiles").iterdir()], [current])

    def test_inventory_and_acquisition_continue_during_plugin_install(self):
        home = plugins.profile_home(self.root)
        installing, release = threading.Event(), threading.Event()

        def install(_, profile):
            installing.set()
            if not release.wait(3):
                raise TimeoutError
            plugins._seed(home / "profiles" / profile.version, True)

        with patch.object(plugins, "_install", side_effect=install), ThreadPoolExecutor(1) as pool:
            pending = pool.submit(plugins.change_plugin, self.root, plugins.PACKAGE, "install")
            try:
                self.assertTrue(installing.wait(2))
                self.assertFalse(plugins.inventory(self.root)["plugin"]["installed"])
                with plugins.acquire_profile(self.root) as current:
                    self.assertFalse(current.installed)
            finally:
                release.set()
            self.assertTrue(pending.result(2)["plugin"]["installed"])
