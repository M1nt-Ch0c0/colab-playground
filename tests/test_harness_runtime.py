"""Runtime regressions across the native adapter, profiles, and the loopback bridge."""
import asyncio
import json
import os
import shutil
import sqlite3
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
from draw_studio.workflows.agent_tools import TOOLS, EditorTools
from draw_studio.workflows.harness_errors import HarnessError
from draw_studio.workflows.harness_store import TELEMETRY_MAX, TELEMETRY_TTL, UNDO_TTL
from draw_studio.workflows.harness_telemetry import TurnTelemetry
from draw_studio.workflows.shot_service import RewriteInput, apply_shot_edits, read_shots, rewrite_prompt, undo_change
from tests.harness_fixture import local_runtime, stateful_model
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

    def test_fixed_tool_registration_order_and_system_voice(self):
        config = copilot._patch(provider(), "model", (128000, 8192, 4096))[-1]["insert"][0]["config"]
        self.assertEqual([tool["name"] for tool in config["tools"]], list(TOOLS))
        spec = (Path(__file__).resolve().parents[1] / "docs/harness/ui-motion-spec.md").read_text(encoding="utf-8")
        voice, examples = spec.split("### 4.5", 1)[1].split("```text\n", 1)[1].split("```", 1)
        table = examples[examples.index("| 用户"):].split("\n\n", 1)[0]
        self.assertTrue(copilot.SYSTEM.endswith(voice + "\n" + table + "\n"))

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
            post("/context", expected=400, data=b"x" * 1_000_001)
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


class ShotPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.runtime = self.enterContext(local_runtime(self.root))
        self.engine = self.runtime.workflows
        self.store = self.runtime.harness_store
        self.run = self.engine.create_run({"workflow": {"name": "Cut", "steps": [step("script", "llm_script")]}})
        self.run_id = self.run["id"]
        self.scenes = [{"index": n, "title": f"Shot {n}", "keyframe_prompt": f"Original frame {n}",
                        "video_prompt": f"Original movement {n}"} for n in range(1, 6)]

    def seed(self):
        self.engine.update_step_output(self.run_id, "script", {"scenes": self.scenes})
        return self.shots()

    def shots(self):
        return read_shots(self.runtime, self.run_id, "script")

    def proposal(self, shots, *, instruction="Warm light", text="Candidate"):
        with patch.object(self.runtime.studio.llm, "resolve", return_value=(provider(), "fixture-model")), \
             patch.object(self.runtime.studio, "write_prompt_rich", return_value={"prompt": text}):
            return rewrite_prompt(self.runtime, RewriteInput(shot_ids=[shot["shot_id"] for shot in shots], instruction=instruction),
                                  scope=self.run_id, run_id=self.run_id, step_id="script")

    def adopt(self, proposal, **options):
        return apply_shot_edits(self.runtime, proposal_id=proposal["proposal_id"], **options)

    def edit(self, shot, field, value):
        return {"shot_id": shot["shot_id"], "generation": shot["generation"], "field": field,
                "expected_version": shot["field_versions"][field], "value": value}

    def patch_fields(self, *edits, **options):
        return apply_shot_edits(self.runtime, run_id=self.run_id, step_id="script", patches=list(edits), **options)

    def test_legacy_ids_sync_to_sqlite_and_survive_restart(self):
        legacy = self.run
        legacy["step_states"]["script"]["output"] = {"scenes": self.scenes}
        path = self.engine._run_file(self.run_id)
        path.write_text(json.dumps(legacy), encoding="utf-8")
        shots = self.shots()
        self.assertEqual([shot["seq"] for shot in shots], [1, 2, 3, 4, 5])
        self.assertEqual(len({shot["shot_id"] for shot in shots}), 5)
        for shot in shots:
            self.assertRegex(shot["shot_id"], r"^sh_[a-f0-9]{12}$")
            self.assertEqual(shot["generation"], 1)
            self.assertEqual(set(shot["field_versions"].values()), {1})
        raw = json.loads(path.read_text(encoding="utf-8"))["step_states"]["script"]["output"]["scenes"]
        self.assertEqual([row["shot_id"] for row in raw], [shot["shot_id"] for shot in shots])
        self.assertEqual(self.store.path, self.root / "private/workflow-harness/state.sqlite3")
        self.assertEqual(stat.S_IMODE(self.store.path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.store.path.stat().st_mode), 0o600)
        with self.store.transaction() as db:
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual({row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")},
                             {"shots", "proposals", "undo_records", "tool_telemetry", "masks", "operations", "operation_items"})
            self.assertEqual([row[0] for row in db.execute("SELECT shot_id FROM shots ORDER BY seq")], [shot["shot_id"] for shot in shots])
        proposal = self.proposal(shots[:1])
        self.runtime.shutdown()
        with self.assertRaises(sqlite3.ProgrammingError):
            self.store.db.execute("SELECT 1")
        with local_runtime(self.root) as reopened:
            self.assertEqual(read_shots(reopened, self.run_id), shots)
            result = apply_shot_edits(reopened, proposal_id=proposal["proposal_id"])
            self.assertEqual(result["applied"][0]["version"], 2)
            self.assertEqual(undo_change(reopened, result["undo_id"])["applied"][0]["value"], "Original frame 1")

    def test_concurrent_rewrites_of_shots_three_and_five_merge(self):
        shots = self.seed()
        both = threading.Barrier(2)

        def write(brief, **_):
            both.wait(3)
            index = 3 if "Original frame 3" in brief else 5
            return {"prompt": f"Rewritten frame {index}"}

        def rewrite(shot):
            return rewrite_prompt(self.runtime, RewriteInput(shot_ids=[shot["shot_id"]], instruction="Low camera"),
                                  scope=self.run_id, run_id=self.run_id, step_id="script")

        with ThreadPoolExecutor(2) as pool, patch.object(self.runtime.studio.llm, "resolve", return_value=(provider(), "test")), \
             patch.object(self.runtime.studio, "write_prompt_rich", side_effect=write):
            third, fifth = [job.result(5) for job in (pool.submit(rewrite, shots[2]), pool.submit(rewrite, shots[4]))]
            writes = [job.result(5) for job in (pool.submit(self.adopt, third), pool.submit(self.adopt, fifth))]
        self.assertEqual([item["applied"][0]["n"] for item in writes], [3, 5])
        result = self.shots()
        for old, current in zip(shots, result, strict=True):
            n = current["seq"]
            self.assertEqual(current["shot_id"], old["shot_id"])
            self.assertEqual(current["fields"]["keyframe_prompt"], f"Rewritten frame {n}" if n in (3, 5) else f"Original frame {n}")
            self.assertEqual(current["field_versions"]["keyframe_prompt"], 2 if n in (3, 5) else 1)
            self.assertEqual(current["field_versions"]["video_prompt"], 1)

    def test_atomic_conflicts_skip_whole_shots_in_partial_mode(self):
        first, second, *_ = self.seed()
        proposal = self.proposal([first, second])
        self.patch_fields(self.edit(first, "keyframe_prompt", "Manual cut"))
        with self.assertRaises(HarnessError) as all_error:
            self.adopt(proposal, atomicity="all")
        conflicts = all_error.exception.details["conflicts"]
        self.assertEqual(all_error.exception.code, "shot_conflict")
        self.assertEqual(conflicts, [{"shot_id": first["shot_id"], "field": "keyframe_prompt", "expected_version": 1,
                                      "current_version": 2, "expected_generation": 1, "current_generation": 1, "n": 1}])
        self.assertEqual(self.shots()[1]["fields"]["keyframe_prompt"], "Original frame 2")
        adopted = self.adopt(proposal, atomicity="per_shot")
        self.assertEqual(adopted["conflicts"], conflicts)
        self.assertEqual([item["n"] for item in adopted["applied"]], [2])
        self.assertEqual(adopted["step_output"]["scenes"][0]["keyframe_prompt"], "Manual cut")
        self.assertEqual(self.adopt(proposal)["undo_id"], adopted["undo_id"])

        result = self.patch_fields(self.edit(first, "keyframe_prompt", "Stale"), self.edit(first, "video_prompt", "Skipped"),
                                   self.edit(second, "video_prompt", "New movement"), atomicity="per_shot")
        self.assertEqual([item["n"] for item in result["applied"]], [2])
        self.assertEqual(self.shots()[0]["fields"]["video_prompt"], "Original movement 1")
        result = self.patch_fields(self.edit(first, "video_prompt", "A turn inside the same shot"))
        self.assertEqual(result["applied"][0]["version"], 2)

    def test_engine_rerun_increments_generation_and_rejects_old_proposal(self):
        first, *_ = self.seed()
        self.patch_fields(self.edit(first, "video_prompt", "Hand edit"))
        proposal = self.proposal([first])
        with patch.object(self.engine, "_run_step", return_value={"scenes": self.scenes}):
            with self.engine._lock:
                self.engine.start_run(self.run_id, from_step_id="script", single_step=True)
                thread = self.engine._active_thread
            thread.join(5)
            self.assertFalse(thread.is_alive())
        current = self.shots()[0]
        self.assertEqual(current["generation"], 2)
        self.assertNotEqual(current["shot_id"], first["shot_id"])
        self.assertEqual(set(current["field_versions"].values()), {1})
        with self.assertRaises(HarnessError) as caught:
            self.adopt(proposal)
        self.assertEqual(caught.exception.code, "shot_conflict")
        self.assertEqual(caught.exception.details["conflicts"][0]["shot_id"], first["shot_id"])
        self.assertIsNone(caught.exception.details["conflicts"][0]["current_version"])
        self.assertEqual(self.shots()[0], current)

    def test_undo_rejects_consumed_expired_and_edited_versions(self):
        initial, *_ = self.seed()
        proposal = self.proposal([initial])
        adopted = self.adopt(proposal)
        undo_id = adopted["undo_id"]
        reversed = undo_change(self.runtime, undo_id)
        self.assertEqual((reversed["applied"][0]["value"], reversed["applied"][0]["version"]), ("Original frame 1", 3))
        with self.assertRaises(HarnessError) as consumed:
            undo_change(self.runtime, undo_id)
        self.assertEqual((consumed.exception.code, consumed.exception.details["status"]), ("shot_conflict", "expired"))

        updated = self.patch_fields(self.edit(self.shots()[0], "keyframe_prompt", "New frame"))
        self.patch_fields(self.edit(self.shots()[0], "keyframe_prompt", "One more change"), record_undo=False)
        with self.assertRaises(HarnessError) as blocked:
            undo_change(self.runtime, updated["undo_id"])
        self.assertEqual(blocked.exception.code, "shot_conflict")
        conflict, = blocked.exception.details["conflicts"]
        self.assertEqual((conflict["expected_version"], conflict["current_version"]), (4, 5))

        updated = self.patch_fields(self.edit(self.shots()[0], "keyframe_prompt", "Another frame"))
        with self.store.transaction() as db:
            db.execute("UPDATE undo_records SET created_at = ? WHERE undo_id = ?", (int(time.time()) - UNDO_TTL - 1, updated["undo_id"]))
        with self.assertRaises(HarnessError) as expired:
            undo_change(self.runtime, updated["undo_id"])
        self.assertEqual((expired.exception.code, expired.exception.details["status"]), ("shot_conflict", "expired"))
        self.assertEqual(self.shots()[0]["fields"]["keyframe_prompt"], "Another frame")

    def test_committed_write_and_undo_survive_a_failed_json_mirror(self):
        initial, *_ = self.seed()
        proposal = self.proposal([initial])
        with patch.object(self.engine, "_write_run_locked", side_effect=OSError):
            adopted = self.adopt(proposal)
        self.assertEqual(self.shots()[0]["fields"]["keyframe_prompt"], "Candidate")
        self.assertEqual(self.store.get_proposal(proposal["proposal_id"])["status"], "applied")
        self.assertEqual(undo_change(self.runtime, adopted["undo_id"])["applied"][0]["value"], "Original frame 1")

    def test_telemetry_metadata_retry_percentiles_redaction_and_retention(self):
        turn = TurnTelemetry(self.runtime, "turn-a", self.run_id, "shared-cookie-string", secrets=("shared-cookie-string",))
        info = {"type": "tool", "name": "studio_run_status", "op": "watch", "args": {
            "api_key": "MY-API-KEY", "token": "MY-TOKEN", "cookie": "MY-COOKIE", "prompt": "Full shot description", "image": b"media-bytes",
        }}
        with patch("draw_studio.workflows.harness_telemetry.time.monotonic", side_effect=[0, .01, 1, 1.05, 2, 2.1]):
            turn.observe({**info, "call_id": "one", "ok": None})
            turn.observe({**info, "call_id": "one", "ok": False, "code": "invalid_argument"})
            turn.observe({**info, "call_id": "two", "ok": None})
            turn.observe({**info, "call_id": "two", "ok": True})
            turn.observe({**info, "call_id": "three", "name": "plugin-MY-COOKIE", "op": "MY-TOKEN", "ok": None})
            turn.observe({**info, "call_id": "three", "ok": True})
        turn.observe({"type": "_usage", "hit": 32, "miss": 10})
        turn.finish()
        summary = self.store.telemetry()
        self.assertEqual((summary["total"], summary["p50_ms"], summary["p95_ms"], summary["retries"]), (3, 50, 100, 1))
        self.assertEqual(summary["by_error"], {"invalid_argument": 1})
        self.assertEqual(summary["by_tool"]["plugin"]["total"], 1)
        self.assertEqual((summary["cache_hit_tokens"], summary["cache_miss_tokens"]), (32, 10))
        with self.store.transaction() as db:
            metrics = json.dumps([dict(row) for row in db.execute("SELECT * FROM tool_telemetry")])
            for text in ("MY-TOKEN", "MY-COOKIE", "MY-API-KEY", "Full shot description", "media-bytes", "shared-cookie-string"):
                self.assertNotIn(text, metrics)
            now = int(time.time())
            db.execute("UPDATE tool_telemetry SET created_at=? WHERE call_seq=1", (now - TELEMETRY_TTL - 1,))
        self.store.prune_telemetry()
        self.assertEqual(self.store.telemetry()["total"], 2)
        with self.store.transaction() as db:
            db.executemany("""INSERT INTO tool_telemetry (turn_id, conversation_key, call_seq, model, tool_name, op, ok,
                            retry_in_turn, latency_ms, created_at) VALUES ('cap', '', ?, '', 'studio_read_context', NULL, 1, 0, 0, ?)""",
                           ((i, now) for i in range(TELEMETRY_MAX + 3)))
        self.store.prune_telemetry()
        with self.store.transaction() as db:
            row = db.execute("SELECT COUNT(*) AS kept, MIN(call_seq) AS first FROM tool_telemetry").fetchone()
            self.assertEqual((row["kept"], row["first"]), (TELEMETRY_MAX, 3))


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.runtime = self.enterContext(local_runtime(self.root))
        self.studio = self.runtime.studio
        self.ops = self.runtime.operations
        self.scope = "cr_" + "f" * 32
        self.enterContext(patch.object(self.studio, "_runner", SimpleNamespace(is_alive=lambda: True)))
        self.enterContext(patch.object(self.runtime.colab, "has_credentials", return_value=True))

    def ready_image(self, count=1, **fields):
        from draw_studio.generation.parameters import normalize_job
        return normalize_job({"mode": "image", "prompt": "Evening exterior", "count": count, "seed": 43, **fields})

    def image_asset(self, color):
        from tests.http_fixture import png
        source = self.root / (color + ".png")
        source.write_bytes(png((32, 24), color))
        return self.runtime.store.save(source, "image", {}), source.read_bytes()

    def finish(self, job_id, state, rid=None):
        with self.studio._lock:
            job = next(j for j in self.studio._queue if j["id"] == job_id)
            self.studio._queue.remove(job)
            job.update(status=state, round_id=rid)
            self.studio._remember_job(job)
            self.studio._save_state_locked()

    def test_idempotent_submit_freezes_video_and_ordered_images(self):
        from tests.http_fixture import mp4

        first, first_bytes = self.image_asset("navy")
        second, second_bytes = self.image_asset("gold")
        source = mp4(self.root / "clip.mp4", 2.5)
        video_bytes = source.read_bytes()
        video = self.runtime.store.save(source, "video", {})
        self.studio.use_round(first)
        self.studio.use_round(second, append=True)
        self.studio.use_round(video, "video")
        tools = EditorTools(self.runtime, {"topic": "", "workflow": {"steps": [], "name": "Cut"}}, scope=self.scope)
        payload = {"mode": "video", "workflow": "ref2va", "video_task": "motion",
                   "video_reference_id": self.studio.refs_report()["video"]["id"], "prompt": "Follows the turn"}
        submitted = {"op": "submit_video", "spec": payload, "idempotency_key": "video-1"}
        op = tools.call("studio_generation", submitted)["operation"]
        oid = op["operation_id"]
        self.assertEqual((op["state"], op["total"], len(op["references"])), ("awaiting_approval", 1, 2))
        self.assertTrue(self.studio.ref_count())
        self.assertFalse(self.studio.snapshot()["queue"])
        self.studio.clear_ref("first")
        self.studio.clear_video_ref(payload["video_reference_id"])
        self.runtime.store.delete([first, second, video])
        self.assertEqual(tools.call("studio_generation", submitted)["operation_id"], oid)
        with self.assertRaises(HarnessError) as collision:
            tools.call("studio_generation", {**submitted, "spec": {**payload, "prompt": "Different request"}})
        self.assertEqual(collision.exception.code, "invalid_argument")
        with ThreadPoolExecutor(2) as pool:
            copies = list(pool.map(self.ops.approve, [oid, oid]))
        job_id = copies[0]["items"][0]["job_id"]
        self.assertEqual(copies[1]["items"][0]["job_id"], job_id)
        self.assertEqual(len(self.studio.snapshot()["queue"]), 1)
        self.assertEqual([self.studio._ref_snapshot_path(job_id, slot).read_bytes() for slot in ("first", "ref_1", "video")],
                         [first_bytes, second_bytes, video_bytes])
        thumb = self.ops.ref_thumb(oid, "image0")
        self.assertEqual(stat.S_IMODE(thumb.stat().st_mode), 0o600)

    def test_mask_and_tail_snapshots_survive_changes_before_approval(self):
        from draw_studio.generation.parameters import normalize_job
        from draw_studio.workflows.operation_service import MaskInput

        rid, original = self.image_asset("navy")
        strokes = [{"points": [[.2, .4], [.3, .5]], "size": .08}]
        mask = self.ops.create_mask(MaskInput(source_id=rid, strokes=strokes))
        saved = self.ops.create(self.scope, "masked", self.ready_image(), mask["mask_id"])
        self.studio.use_round(rid, "last")
        video = self.ops.create(self.scope, "tail", normalize_job({
            "mode": "video", "workflow": "fl2va", "has_last_image": True, "has_image": False, "prompt": "A turn",
        }))
        self.studio.clear_ref("last")
        self.runtime.store.delete([rid])
        with self.ops.store.transaction() as db:
            db.execute("UPDATE masks SET expires_at=0 WHERE mask_id=?", (mask["mask_id"],))
        a, b = (self.ops.approve(item["operation_id"])["items"][0]["job_id"] for item in (saved, video))
        self.assertEqual(self.studio._ref_snapshot_path(a, "first").read_bytes(), original)
        self.assertEqual(self.studio._queue[0]["payload"]["edit_mask"]["strokes"], strokes)
        self.assertEqual(self.studio._ref_snapshot_path(b, "last").read_bytes(), original)

    def test_partial_retry_keeps_success_and_survives_shutdown(self):
        op = self.ops.create(self.scope, "batch", self.ready_image(3))
        oid = op["operation_id"]
        job_ids = [i["job_id"] for i in self.ops.approve(oid)["items"]]
        rid, _ = self.image_asset("navy")
        self.finish(job_ids[0], "done", rid)
        for jid in job_ids[1:]:
            self.finish(jid, "error")
        self.assertEqual((self.ops.get(oid)["state"], self.ops.get(oid)["done"]), ("partial", 1))
        tools = EditorTools(self.runtime, {"topic": "", "workflow": {"steps": [], "name": "Cut"}}, scope=self.scope)
        self.assertTrue(tools.call("studio_jobs", {"op": "retry", "job_id": job_ids[1]})["retry_requires_approval"])
        self.assertFalse(self.studio.snapshot()["queue"])
        retried = self.ops.retry(oid, ["1", "2"])
        current = [i["job_id"] for i in retried["items"]]
        self.assertEqual((current[0], current[2]), (job_ids[0], job_ids[2]))
        self.assertNotEqual(current[1], job_ids[1])
        self.assertEqual(retried["items"][0]["round_id"], rid)
        self.assertEqual(self.studio._queue[0]["payload"]["seed"], 44)
        self.assertEqual(self.ops.retry(oid, ["2"])["items"][1]["job_id"], current[1])
        self.runtime.shutdown()
        with local_runtime(self.root) as restarted:
            restarted.studio.recover()
            recovered, = restarted.operations.list(self.scope)
            self.assertEqual([i["job_id"] for i in recovered["items"]], current)
            self.assertEqual([i["state"] for i in recovered["items"]], ["done", "queued", "failed"])

    def test_approval_failures_and_precise_cancellation(self):
        import collections
        from draw_studio.generation.catalog import QUEUE_MAX

        pending = self.ops.create(self.scope, "cancel", self.ready_image(2))["operation_id"]
        with patch.object(self.runtime.colab, "has_credentials", return_value=False), self.assertRaises(HarnessError) as unauthed:
            self.ops.approve(pending)
        self.assertEqual(unauthed.exception.code, "colab_unauthed")
        with patch.object(self.studio, "_queue", collections.deque([None] * QUEUE_MAX)), self.assertRaises(HarnessError) as full:
            self.ops.approve(pending)
        self.assertEqual(full.exception.code, "queue_full")
        with patch.object(self.studio, "_save_state_locked", side_effect=OSError), self.assertRaises(HarnessError) as failed:
            self.ops.approve(pending)
        self.assertEqual(failed.exception.code, "internal_error")
        self.assertEqual(self.ops.get(pending)["state"], "awaiting_approval")
        self.assertFalse(self.studio.snapshot()["queue"])
        aborted = self.ops.create(self.scope, "future", self.ready_image(1))["operation_id"]
        self.assertEqual(self.ops.cancel(aborted)["state"], "canceled")
        self.assertEqual(self.ops.approve(aborted)["state"], "canceled")
        running = self.ops.approve(pending)
        target, queued = (row["job_id"] for row in running["items"])
        with self.studio._lock:
            self.studio._current = self.studio._queue.popleft()
            self.studio._current["status"] = "running"
        def interrupt():
            self.assertTrue(self.studio._lock._is_owned())
            self.assertEqual(self.studio._current["id"], target)
        with patch.object(self.runtime.colab, "interrupt_active", side_effect=interrupt) as interrupted:
            self.assertFalse(self.studio.cancel_job("j00000000"))
            self.assertTrue(self.studio.cancel_job(queued))
            interrupted.assert_not_called()
            self.assertTrue(self.studio.cancel_job(target))
            interrupted.assert_called_once()

    def test_operation_jobs_are_not_retryable_from_global_queue(self):
        from draw_studio.errors import StateConflict

        op = self.ops.create(self.scope, "no-global-retry", self.ready_image(2))
        oid = op["operation_id"]
        approved = self.ops.approve(oid)
        first_jid, second_jid = (row["job_id"] for row in approved["items"])
        with self.studio._lock:
            first_job = self.studio._queue.popleft()
            second_job = self.studio._queue.popleft()
        self.assertEqual(first_job["payload"]["operation_id"], oid)
        with patch.object(self.studio, "_acquire_session", side_effect=RuntimeError("boom")):
            self.studio._run_job(first_job)
        with self.studio._lock:
            self.studio._remember_job(first_job)
            self.studio._current = second_job
            self.studio._save_state_locked()
        self.assertFalse(self.studio.find_job(first_jid)["retryable"])
        with self.assertRaises(StateConflict):
            self.studio.retry_job(first_jid)

        self.runtime.shutdown()
        with local_runtime(self.root) as restarted, \
             patch.object(restarted.colab, "has_credentials", return_value=True), \
             patch.object(restarted.studio, "_runner", SimpleNamespace(is_alive=lambda: True)):
            restarted.studio.recover()
            self.assertFalse(restarted.studio.find_job(second_jid)["retryable"])
            with self.assertRaises(StateConflict):
                restarted.studio.retry_job(second_jid)
            retried = restarted.operations.retry(oid, ["1"])
            self.assertEqual(retried["items"][0]["state"], "queued")
            self.assertEqual(retried["items"][1]["state"], "failed")

    def test_unknown_items_preserve_completed_state_and_support_cancel_and_failed_retry(self):
        op = self.ops.create(self.scope, "partial-unknown", self.ready_image(3))
        oid = op["operation_id"]
        j1, j2, j3 = (row["job_id"] for row in self.ops.approve(oid)["items"])
        rid, _ = self.image_asset("navy")
        self.finish(j1, "done", rid)
        self.finish(j2, "error")
        with self.studio._lock:
            self.studio._queue.clear()
            self.studio._history.clear()
            self.studio._save_state_locked()
        reconciled = self.ops.get(oid)
        self.assertEqual(reconciled["state"], "partial")
        self.assertEqual([i["state"] for i in reconciled["items"]], ["done", "failed", "unknown"])
        self.assertEqual([r["id"] for r in reconciled["results"]], [rid])
        retried = self.ops.retry(oid)
        self.assertEqual([i["state"] for i in retried["items"]], ["done", "queued", "unknown"])
        self.assertEqual(retried["items"][2]["job_id"], j3)
        canceled = self.ops.cancel(oid)
        self.assertEqual(canceled["state"], "partial")
        self.assertEqual([i["state"] for i in canceled["items"]], ["done", "canceled", "canceled"])
        self.assertEqual([r["id"] for r in canceled["results"]], [rid])

        only_unknown = self.ops.create(self.scope, "only-unknown", self.ready_image(1))["operation_id"]
        self.ops.approve(only_unknown)
        with self.studio._lock:
            self.studio._queue.clear()
            self.studio._history.clear()
            self.studio._save_state_locked()
        self.assertEqual(self.ops.get(only_unknown)["state"], "unknown")
        self.assertEqual(self.ops.cancel(only_unknown)["state"], "canceled")

    def test_new_session_falls_back_to_client_history_or_saved_exchanges(self):
        conversation = copilot.Conversation(self.root, KEY, True)
        prompts = []
        fake_client = SimpleNamespace(
            subscribe_session_notifications=lambda _: contextmanager(lambda: (yield SimpleNamespace()))(),
            session_prompt=lambda _key, blocks: prompts.append(blocks[0]["text"]) or "receipt",
        )
        conversation.harness = SimpleNamespace(client=fake_client)
        conversation.bridge = SimpleNamespace(pid=42, bind=lambda *_: contextmanager(lambda: (yield))())
        conversation.directory.mkdir(parents=True, exist_ok=True)
        conversation.remember({"id": "turn1", "user": "saved user", "answer": "saved reply", "tools": [], "state": "done"})
        with patch.object(conversation, "prepare", return_value="new"), \
             patch.object(conversation, "_wait_turn", return_value="ok"):
            conversation.run(editor(), provider(), "demo", "follow up", [{"role": "user", "text": "client turn"}],
                             lambda _: None, threading.Event())
            conversation.run(editor(), provider(), "demo", "after reload", (), lambda _: None, threading.Event())
        with patch.object(conversation, "prepare", return_value="reused"), \
             patch.object(conversation, "_wait_turn", return_value="ok"):
            conversation.run(editor(), provider(), "demo", "steady turn", [{"role": "user", "text": "client turn"}],
                             lambda _: None, threading.Event())
        self.assertIn("client turn", prompts[0])
        self.assertIn("saved user", prompts[1])
        self.assertIn("saved reply", prompts[1])
        self.assertEqual(prompts[2], "steady turn")

    def test_approve_inherits_held_gpu_and_cleans_frozen_binaries_on_done(self):
        rid, _ = self.image_asset("navy")
        self.studio.use_round(rid)
        op = self.ops.create(self.scope, "held-gpu", self.ready_image(1, has_image=True))
        oid = op["operation_id"]
        with patch.object(self.runtime.colab, "status_report",
                          return_value={"authed": True, "sessions": [{"gpu": "H100"}]}):
            approved = self.ops.approve(oid)
        jid = approved["items"][0]["job_id"]
        queued = self.studio._queue[0]
        self.assertEqual((queued["payload"]["gpu"], queued["payload"]["gpu_pool"]), ("H100", ["H100"]))
        self.assertTrue((self.ops.inputs / oid / "image0.bin").is_file())
        out_rid, _ = self.image_asset("gold")
        self.finish(jid, "done", out_rid)
        self.assertEqual(self.ops.get(oid)["state"], "done")
        self.assertFalse((self.ops.inputs / oid / "image0.bin").exists())
        self.assertTrue((self.ops.inputs / oid / "image0.jpg").is_file())

    def test_mask_id_can_be_cleared_and_not_inherited_on_ref_or_t2i(self):
        from draw_studio.workflows.operation_service import MaskInput

        rid, _ = self.image_asset("navy")
        mask = self.ops.create_mask(MaskInput(source_id=rid, strokes=[{"points": [[.2, .4], [.3, .5]], "size": .08}]))
        composer = {"mode": "image", "prompt": "Night street", "has_image": True, "mask_id": mask["mask_id"], "revision": "a" * 32}
        tools = EditorTools(self.runtime, {"topic": "", "workflow": {"steps": [], "name": "生图"}},
                            scope=self.scope, workspace="image", composer=composer)
        # Explicit has_image=False must not inherit old mask_id.
        prep = tools.call("studio_generation", {"op": "prepare", "spec": {"has_image": False, "prompt": "Pure t2i"}})
        self.assertFalse(prep["references"]["mask"])
        self.assertFalse(prep["parameters"]["has_image"])
        # Explicit reference_round_ids must not fail due to inherited mask_id.
        prep_ref = tools.call("studio_generation", {"op": "prepare", "spec": {"reference_round_ids": [rid], "prompt": "Ref edit"}})
        self.assertFalse(prep_ref["references"]["mask"])
        self.assertEqual(prep_ref["references"]["images"], 1)
        # Explicit mask_id: None via edit_composer clears mask_id in composer_patch and subsequent prepare.
        patched = tools.call("studio_generation", {"op": "edit_composer", "spec": {"mask_id": None}})
        self.assertIsNone(patched["composer_patch"]["changes"]["mask_id"])
        prep_after = tools.call("studio_generation", {"op": "prepare", "spec": {"has_image": False}})
        self.assertFalse(prep_after["references"]["mask"])

    def test_reconcile_recovers_restart_interrupted_job_from_gallery_and_explicit_forget_waits(self):
        from tests.http_fixture import png

        op = self.ops.create(self.scope, "restart-gallery", self.ready_image(1))
        oid = op["operation_id"]
        jid = self.ops.approve(oid)["items"][0]["job_id"]
        source = self.root / "recovered.png"
        source.write_bytes(png((32, 24), "navy"))
        rid = self.runtime.store.save(source, "image", {"job_id": jid})
        with self.studio._lock:
            job = self.studio._queue.popleft()
            job.update(status="error", error="服务重启，任务已中断", round_id=None)
            self.studio._history.appendleft(job)
            self.studio._save_state_locked()
        reconciled = self.ops.get(oid)
        self.assertEqual((reconciled["state"], reconciled["items"][0]["round_id"]), ("done", rid))

        # Explicit forget(expired=None) racing with prune_drafts(expired=cutoff) must still dispose & delete.
        sessions = copilot.HarnessSessions()
        conv = copilot.Conversation(self.root, KEY, True)
        conv.directory.mkdir(parents=True, exist_ok=True)
        conv.dispose = Mock()
        sessions.entries[KEY] = conv
        entered, release = threading.Event(), threading.Event()

        def slow_saved(k):
            entered.set()
            release.wait(5)
            return True

        t_prune = threading.Thread(target=sessions.forget, args=(self.root, KEY), kwargs={"expired": time.time(), "saved": slow_saved})
        t_delete = threading.Thread(target=sessions.forget, args=(self.root, KEY))
        t_prune.start()
        self.assertTrue(entered.wait(3))
        t_delete.start()
        time.sleep(0.05)
        release.set()
        t_prune.join(5)
        t_delete.join(5)
        self.assertNotIn(KEY, sessions.entries)
        self.assertFalse(conv.directory.exists())
        conv.dispose.assert_called_once()

    def test_partial_comfy_spec_preserves_existing_and_staged_fields(self):
        comfy = {
            "template": "qwen-image-2.1",
            "diffusion": "https://huggingface.co/owner/repo/resolve/main/diff.safetensors",
            "text_encoder": "https://huggingface.co/owner/repo/resolve/main/te.safetensors",
            "vae": "https://huggingface.co/owner/repo/resolve/main/vae.safetensors",
            "sampler": "euler",
            "scheduler": "simple",
        }
        composer = {"mode": "image", "engine": "comfyui", "prompt": "Neon rain", "comfy": comfy, "revision": "a" * 32}
        tools = EditorTools(self.runtime, {"topic": "", "workflow": {"steps": [], "name": "生图"}},
                            scope=self.scope, workspace="image", composer=composer)
        first = tools.call("studio_generation", {"op": "edit_composer", "spec": {"comfy": {"sampler": "heun"}}})
        second = tools.call("studio_generation", {"op": "edit_composer", "spec": {"comfy": {"scheduler": "karras"}}})
        self.assertEqual(first["composer_patch"]["changes"]["comfy"], {"sampler": "heun"})
        self.assertEqual(second["composer_patch"]["changes"]["comfy"], {"sampler": "heun", "scheduler": "karras"})
        prep = tools.call("studio_generation", {"op": "prepare", "spec": {"comfy": {"denoise": 0.75}}})
        self.assertEqual(prep["parameters"]["comfy"]["diffusion"]["basename"], "diff.safetensors")
        self.assertEqual(prep["parameters"]["comfy"]["sampler"], "heun")
        self.assertEqual(prep["parameters"]["comfy"]["scheduler"], "karras")
        self.assertEqual(prep["parameters"]["comfy"]["denoise"], 0.75)
        op = tools.call("studio_generation", {"op": "submit_image", "idempotency_key": "comfy-partial",
                                              "spec": {"comfy": {"sampler": "dpmpp_2m"}}})["operation"]
        self.assertEqual(op["model"], "diff.safetensors")

    def test_composer_rewrite_includes_active_refs_mask_chain_and_fl2va_roles(self):
        from draw_studio.workflows.operation_service import MaskInput
        from tests.http_fixture import png

        uploaded_first = png((32, 24), "navy")
        uploaded_last = png((32, 24), "gold")
        self.studio.set_ref("first", uploaded_first, "upload")
        self.studio.set_ref("last", uploaded_last, "upload")
        provider = SimpleNamespace(id="fixture", key="secret")

        # 1. Uploaded image ref with has_image=True.
        tools = EditorTools(self.runtime, {"topic": "", "workflow": {"steps": [], "name": "生图"}},
                            scope=self.scope, workspace="image",
                            composer={"mode": "image", "prompt": "Portrait", "has_image": True, "revision": "a" * 32})
        with patch.object(self.studio.llm, "resolve", return_value=(provider, "demo")), \
             patch.object(self.studio, "write_prompt_rich", return_value={"prompt": "Refined"}) as writer:
            prop = tools.call("studio_rewrite_prompt", {"instruction": "Match lighting"})
        kwargs = writer.call_args.kwargs
        self.assertTrue(kwargs["editing"])
        self.assertEqual(kwargs["override_images"], [("图1", uploaded_first)])
        self.assertEqual(len(prop["references_used"]), 1)

        # 2. Mask source image.
        rid, mask_bytes = self.image_asset("teal")
        mask = self.ops.create_mask(MaskInput(source_id=rid, strokes=[{"points": [[.2, .4], [.3, .5]], "size": .08}]))
        mask_tools = EditorTools(self.runtime, {"topic": "", "workflow": {"steps": [], "name": "生图"}},
                                 scope=self.scope, workspace="image",
                                 composer={"mode": "image", "prompt": "Swap coat", "has_image": True, "mask_id": mask["mask_id"]})
        with patch.object(self.studio.llm, "resolve", return_value=(provider, "demo")), \
             patch.object(self.studio, "write_prompt_rich", return_value={"prompt": "Masked"}) as writer:
            mask_tools.call("studio_rewrite_prompt", {"instruction": "Red wool coat"})
        self.assertEqual(writer.call_args.kwargs["override_images"], [("局部改图原图", mask_bytes)])
        self.assertTrue(writer.call_args.kwargs["editing"])

        # 3. Chain latest image.
        chain_tools = EditorTools(self.runtime, {"topic": "", "workflow": {"steps": [], "name": "生图"}},
                                  scope=self.scope, workspace="image",
                                  composer={"mode": "image", "prompt": "Next frame", "chain": True})
        with patch.object(self.studio.llm, "resolve", return_value=(provider, "demo")), \
             patch.object(self.studio, "write_prompt_rich", return_value={"prompt": "Chained"}) as writer:
            chain_tools.call("studio_rewrite_prompt", {"instruction": "Pan left"})
        self.assertEqual(writer.call_args.kwargs["override_images"], [("图1（最新生成作品）", mask_bytes)])
        self.assertTrue(writer.call_args.kwargs["chain"])

        # 4. FL2VA first + last frame roles, and L2VA tail-only role.
        fl_tools = EditorTools(self.runtime, {"topic": "", "workflow": {"steps": [], "name": "视频"}},
                               scope=self.scope, workspace="video",
                               composer={"mode": "video", "workflow": "fl2va", "prompt": "Dawn to dusk",
                                         "has_image": True, "has_last_image": True})
        with patch.object(self.studio.llm, "resolve", return_value=(provider, "demo")), \
             patch.object(self.studio, "write_prompt_rich", return_value={"prompt": "FL2VA"}) as writer:
            fl_tools.call("studio_rewrite_prompt", {"instruction": "Smooth pan"})
        self.assertEqual(writer.call_args.kwargs["override_images"], [
            ("<Picture 1> (First Frame at 0.00s)", uploaded_first),
            ("<Picture 2> (Last Frame at end)", uploaded_last),
        ])
        self.assertTrue(writer.call_args.kwargs["has_last_image"])
        self.assertTrue(writer.call_args.kwargs["has_image"])

        tail_tools = EditorTools(self.runtime, {"topic": "", "workflow": {"steps": [], "name": "视频"}},
                                 scope=self.scope, workspace="video",
                                 composer={"mode": "video", "workflow": "fl2va", "prompt": "Arrive at dusk",
                                           "has_image": False, "has_last_image": True})
        with patch.object(self.studio.llm, "resolve", return_value=(provider, "demo")), \
             patch.object(self.studio, "write_prompt_rich", return_value={"prompt": "L2VA"}) as writer:
            tail_tools.call("studio_rewrite_prompt", {"instruction": "Slow reveal"})
        self.assertEqual(writer.call_args.kwargs["override_images"], [
            ("<Picture 1> (Last Frame at end)", uploaded_last),
        ])
        self.assertTrue(writer.call_args.kwargs["has_last_image"])
        self.assertFalse(writer.call_args.kwargs["has_image"])
