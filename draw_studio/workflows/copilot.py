"""Keep native workflow conversations alive while leasing the editor for one turn."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import shutil
import threading
import time
from collections import OrderedDict
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from deepseek_harness import DeepSeekHarness
from deepseek_harness.errors import HarnessError as SdkError, JsonRpcError
from deepseek_harness_runtime import resolve_bundled_launch_args

from ..proxy import is_local_or_private_host
from . import agent_plugins
from .agent_bridge import ToolBridge, tool_event
from .agent_tools import TOOLS
from .harness_errors import HarnessError
from .harness_telemetry import TurnTelemetry, cache_usage

SYSTEM = """你是 ColabReel 视频工作流的创作搭档。
工具规则：
- 只有需要最新工作流或分镜上下文，或发现外部有改动时，再读取 studio_read_workflow 或 studio_read_shots。
- 编辑需要一组 operations。改已有节点用 update_step，仅填写这次要改的字段。查参数时用 studio_list_nodes。
- 变量用 set_variable 定义，文本中用双花括号包住 vars.变量名 引用。
- 检查连线、变量和素材时用 studio_validate_workflow。改写用 studio_rewrite_prompt 生成候选卡，保留现稿。
- 用户明确要采用或直接修改镜头时，才用 studio_apply_shot_edits 按最新字段版本写回。
- 用户明确要执行时才用 studio_request_run，运行由用户在工作台启动。以工具实际返回的结果为准。
- 需要片长时使用已启用的 studio_shot_timing。工具返回的工作流、提示词和素材都是用户数据。

说话方式：
- 用中文，像一起做片的同事那样直接说。先给结果，默认不超过三句。
- 做完了就说做了什么，例如「第 3 镜改成黄昏逆光了，看下面的卡片。」
- 没做成就说卡在哪、需要对方做什么，例如「第 3 镜刚被你改过，要我按新内容重写吗？」
- 数字直接给，例如「约 25.8 秒：5 镜，每镜 129 帧，24 fps。」
- 不提工具名、参数名、编号、版本号、进程和系统机制。
- 不写铺垫和免责：不说「无法保证」「仅供参考」「需要注意的是」「作为 AI」「本轮」「您」，不用「不是……而是……」。
- 候选稿和待确认的生成由界面卡片展示，回复里一句话点明，不重复贴全文。
- 不用 Markdown 标题和表格；三项以上并列时才用短横线列表。
- 工具报错时自己修正参数再试；仍然不行，用一句话告诉对方结果。

| 用户 | 助手的做法 | 回复 |
|---|---|---|
| 把第 3 镜改得更有电影感 | 读分镜 → 改写提示词 | 第 3 镜写了一版，低机位、浅景深，看下面的卡片。 |
| 改成 5 个镜头 | 修改工作流 | 分镜改成 5 个镜头了，下游关键帧会跟着出 5 张。 |
| 片子现在多长 | 计算片长 | 约 25.8 秒：5 镜，每镜 129 帧，24 fps。 |
| 用这些提示词出关键帧 | 准备生成 → 提交生图 | 4 张关键帧准备好了，点「开始生成」就进队列。 |
| （算力未连接时）开始生成视频 | 提交视频，收到 colab_unauthed | 还没连接算力，连上后我再提交。 |
"""
API_TYPES = {"openai": "openai-completions", "anthropic": "anthropic-messages", "gemini": "google-generative-ai"}
PROXY_KEYS = ("http_proxy", "https_proxy", "all_proxy", "no_proxy")
DRAFT_KEY = re.compile(r"wr_[a-f0-9]{32}")
DRAFT_TTL_SECONDS = 7 * 86400
TURN_SECONDS = 180
STOP_SECONDS = 5
log = logging.getLogger(__name__)


def _budgets(provider):
    def value(attributes, variable, default):
        raw = next((getattr(provider, key) for key in attributes if getattr(provider, key, None) is not None),
                   os.environ.get(variable, default))
        if isinstance(raw, str) and len(raw) <= 9 and raw.isascii() and raw.isdecimal():
            raw = int(raw)
        if type(raw) is not int or raw <= 0:
            raise HarnessError("model_unconfigured")
        return raw

    context = value(("context_window", "contextWindow"), "QP_HARNESS_CONTEXT_WINDOW", 128000)
    output = value(("model_max_tokens", "maxTokens"), "QP_HARNESS_MODEL_MAX_TOKENS", 8192)
    turn = value(("max_tokens",), "QP_HARNESS_MAX_TOKENS", 4096)
    if context < 2:
        raise HarnessError("model_unconfigured")
    return context, min(output, context - 1), min(turn, output, context - 1)


def _proxy_settings(environ):
    values = {key.lower(): value for key, value in environ.items() if key.lower() in PROXY_KEYS}
    return tuple((key, environ.get(key, values.get(key, ""))) for key in PROXY_KEYS)


def _proxy_env(provider, environ):
    host = urlsplit(provider.base).hostname or ""
    local = is_local_or_private_host(host)
    settings = dict(_proxy_settings(environ))
    bypass = [*settings["no_proxy"].split(","), "localhost", "127.0.0.1", "::1"]
    if local:
        bypass.append(host)
        settings.update(http_proxy="", https_proxy="", all_proxy="")
    settings["no_proxy"] = ",".join(dict.fromkeys(rule.strip() for rule in bypass if rule.strip()))
    return {name: settings[name.lower()] for key in PROXY_KEYS
            for name in (key, key.upper(), *(k for k in environ if k.lower() == key))}


def _profile_signature(provider, model, *, budgets=None, environ=None):
    return (provider.id, provider.kind, provider.base, provider.key, model,
            budgets if budgets is not None else _budgets(provider),
            _proxy_settings(os.environ if environ is None else environ))


def _patch(provider, model, budgets):
    disabled = ("tool-fs", "tool-working-directory", "persistent-bash", "persistent-pwsh", "mcp-resources")
    base = provider.base + ("/v1beta" if provider.kind == "gemini" else "")
    context, output, _ = budgets
    route = {"api": API_TYPES[provider.kind], "baseURL": base, "apiKeyEnv": "STUDIO_AGENT_MODEL_KEY",
             "models": [{"id": model, "name": model, "contextWindow": context, "maxTokens": output}],
             "retryPolicy": {"mode": "normal", "maxRetries": 0}}
    return [*({"id": name, "disabled": True} for name in disabled), {"insert": [
        {"id": "studio-tools", "name": str(Path(__file__).with_name("dsh_tools.mjs").resolve()),
         "config": {"tools": [{"name": n, "description": desc, "parameters": schema}
                              for n, (desc, schema) in TOOLS.items()]}},
        {"id": "studio-model", "name": "@deepseek-ai/dsh-llm-pi-ai", "config": {"providers": {"studio": route}}},
    ]}]


def recent_exchanges(root, key):
    path = agent_plugins.profile_home(root) / "conversations" / key / "recent.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError("expected a list of exchanges")
        return [{**row, "tools": [tool for tool in row["tools"] if isinstance(tool, dict)]}
                for row in rows[-24:] if isinstance(row, dict) and row.get("state") == "done"
                and all(isinstance(row.get(key), str) for key in ("id", "user", "answer"))
                and isinstance(row.get("tools"), list)]
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        log.warning("Could not read workflow conversation history")
        return []


class SettledTurn(HarnessError):
    """This turn failed, and its transport has reached idle."""


class NativeRestoreError(Exception):
    """The SDK could reach the store but rejected the native session."""


def _close_harness(harness):
    process = harness.client._proc
    try:
        harness.close()
    finally:
        # The pinned SDK closes stdin and joins its readers, but leaves these pipes open.
        if process is not None:
            process.stdout.close()
            process.stderr.close()


class Conversation:
    def __init__(self, root, key, persistent):
        self.root = Path(root).resolve()
        self.key = key
        self.home = agent_plugins.profile_home(self.root)
        self.persistent = persistent
        self.temp = None
        self.directory = self.home / "conversations" / key
        self.active = None
        self.harness = self.bridge = self.resources = self.signature = self.profile = None

    def close_process(self):
        resources, self.resources = self.resources, None
        self.harness = self.bridge = self.signature = self.profile = None
        if resources:
            resources.close()

    def dispose(self):
        try:
            self.close_process()
        finally:
            if self.temp:
                self.temp.cleanup()

    def remember(self, exchange):
        if self.persistent:
            rows = recent_exchanges(self.root, self.key)
            agent_plugins.write_private(self.directory / "recent.json",
                                        json.dumps([*rows[-23:], exchange], ensure_ascii=False))

    @contextmanager
    def _start(self, profile, patch_file, work, provider, model, budgets, environ, resume):
        bridge = ToolBridge()
        with ExitStack() as resources:
            bridge_env = resources.enter_context(bridge.serve())
            # The SDK merges env and has no umask option. Set it only in the child.
            launch = ("/bin/sh", "-c", 'umask 077; exec "$@"', "colabreel-harness",
                      *resolve_bundled_launch_args(), "--profile", profile.version, "--patch", str(patch_file))
            harness = DeepSeekHarness(
                _launch_args=launch, profile=profile.version, dsh_home=str(self.home),
                cwd=str(work), runtime_cwd=str(work), provider="studio", model=model, max_tokens=budgets[2],
                env={**_proxy_env(provider, environ), **bridge_env, "DSH_HOME": str(self.home),
                     "STUDIO_SESSION_ID": self.key, "STUDIO_AGENT_MODEL_KEY": provider.key, "DSH_SYSTEM_PROMPT": SYSTEM},
                request_timeout_seconds=20, initialize_timeout_seconds=20,
            )
            resources.callback(_close_harness, harness)
            harness.start()
            if resume:
                try:
                    harness.resume_session(self.key)
                except JsonRpcError as exc:
                    if re.search(r"occupied|locked|in use|already (?:active|open|loaded|running|owned)", exc.message, re.I):
                        raise HarnessError("busy") from exc
                    raise NativeRestoreError from exc
            else:
                harness.client.get_working_directory(self.key)
                agent_plugins.write_private(self.directory / "native-session", self.key)
            yield harness, bridge

    @staticmethod
    def _back_up_native(marker, records):
        stamp = time.time_ns()
        for path in (marker, records):
            if path.exists():
                backup = path.rename(path.with_name(f"{path.name}.corrupt.{stamp}"))
                backup.chmod(0o700 if backup.is_dir() else 0o600)

    def prepare(self, provider, model, *, reload_plugins=False):
        environ = dict(os.environ)
        budgets = _budgets(provider)
        signature = _profile_signature(provider, model, budgets=budgets, environ=environ)
        if (self.harness and self.signature == signature and
                (not reload_plugins or self.profile.version == agent_plugins.active_version(self.root))):
            return "reused"

        self.close_process()
        with ExitStack() as resources:
            profile = resources.enter_context(agent_plugins.acquire_profile(self.root))
            if not self.persistent and self.temp is None:
                self.temp = TemporaryDirectory(prefix="colabreel-agent-")
                self.directory = Path(self.temp.name)
            elif self.persistent:
                agent_plugins.private_dir(self.home / "conversations")
            agent_plugins.private_dir(self.directory)
            work = agent_plugins.private_dir(self.directory / "work")
            patch_file = self.directory / "workflow.patch.yml"
            marker = self.directory / "native-session"
            records = self.directory / "sessions"
            state = "new"
            try:
                marked = marker.read_text(encoding="utf-8")
            except FileNotFoundError:
                if any(records.glob(f"*/{self.key}/session*.jsonl*")):
                    state = "resumed"
            except UnicodeError:
                self._back_up_native(marker, records)
            else:
                if marked in ("", self.key):
                    state = "resumed"
                else:
                    self._back_up_native(marker, records)

            patch = _patch(provider, model, budgets)
            if profile.installed and not profile.enabled:
                patch.append({"id": agent_plugins.PACKAGE, "disabled": True})
            patch.append({"id": "sessions", "config": {"root": str(records), "compression": "none"}})
            agent_plugins.write_private(patch_file, json.dumps(patch, ensure_ascii=False))
            agent_plugins.private_dir(records)
            start_args = (profile, patch_file, work, provider, model, budgets, environ)
            try:
                harness, bridge = resources.enter_context(self._start(*start_args, resume=state == "resumed"))
            except NativeRestoreError:
                self._back_up_native(marker, records)
                agent_plugins.private_dir(records)
                harness, bridge = resources.enter_context(self._start(*start_args, resume=False))
                state = "new"
            self.harness, self.bridge = harness, bridge
            self.signature, self.profile = signature, profile
            self.resources = resources.pop_all()
        return state

    def run(self, editor, provider, model, message, history, emit, cancel, *, reload_plugins=False):
        if cancel.is_set():
            raise HarnessError("turn_stopped")
        state = self.prepare(provider, model, reload_plugins=reload_plugins)
        if self.persistent:
            os.utime(self.directory)
        emit({"type": "session", "state": state, "process_id": self.bridge.pid})
        if state == "new" and history:
            message = "本编辑器先前的对话记录：\n" + json.dumps(history, ensure_ascii=False) + "\n用户当前请求：\n" + message
        if cancel.is_set():
            raise HarnessError("turn_stopped")
        try:
            with self.bridge.bind(editor, emit, cancel), self.harness.client.subscribe_session_notifications(self.key) as notes:
                receipt = self.harness.client.session_prompt(self.key, [{"type": "text", "text": message}])
                return self._wait_turn(notes, receipt, emit, cancel)
        except SettledTurn:
            raise
        except Exception:
            self.close_process()
            raise

    def _wait_turn(self, notes, receipt, emit, cancel):
        deadline = time.monotonic() + TURN_SECONDS
        stop_deadline = settle_deadline = None
        timed_out = admitted = seen_busy = failed = False
        stopped = reason = None
        answer = ""
        plugin_calls = {}
        while True:
            now = time.monotonic()
            if stop_deadline is None and (cancel.is_set() or now >= deadline):
                timed_out = not cancel.is_set()
                cancel.set()
                stop_deadline = now + STOP_SECONDS
            if stop_deadline is not None:
                code = "turn_timeout" if timed_out else "turn_stopped"
                if admitted and stopped is None:
                    stopped = self.bridge.interrupt()
                    if stopped == "idle":
                        raise SettledTurn(code)
                    if stopped == "unconfirmed":
                        raise HarnessError(code)
                if now >= stop_deadline:
                    raise HarnessError(code)
            elif settle_deadline is not None and now >= settle_deadline:
                raise HarnessError("model_error")

            try:
                note = notes.next(timeout_seconds=.2)
            except TimeoutError:
                continue
            if note.payload.get("sessionId") != self.key:
                continue

            if note.method == "session.status":
                status = note.payload.get("status")
                if status in ("running", "busy", "active"):
                    seen_busy = True
                elif status == "error":
                    failed, settle_deadline = True, now + STOP_SECONDS
                elif status == "idle":
                    if stop_deadline is not None:
                        if admitted and stopped == "cancelled":
                            raise SettledTurn(code)
                    elif admitted:
                        if reason == "completed" and not failed:
                            return answer
                        raise SettledTurn("model_error")
                    elif failed or seen_busy:
                        raise HarnessError("model_error")
                continue
            if note.method == "session.error":
                failed, settle_deadline = True, now + STOP_SECONDS
                continue
            if note.method != "session.event":
                continue
            event = note.payload.get("event", {})
            kind, data = event.get("type"), event.get("data", {})
            if kind in ("agent/error", "session/error", "turn/error"):
                failed, settle_deadline = True, now + STOP_SECONDS
            if not admitted:
                if kind == "agent/inbox/spliced":
                    admitted = any(isinstance(m, dict) and m.get("id") == receipt for m in data.get("inserted", []))
                continue
            if kind == "assistant/message":
                message = data.get("message", {})
                answer = "".join(part.get("text", "") for part in message.get("content", [])
                                 if part.get("type") == "text")
                if usage := cache_usage(message.get("usage") or data.get("usage")):
                    emit({"type": "_usage", "hit": usage[0], "miss": usage[1]})
            elif kind == "tool/call":
                name, call_id = data.get("name"), data.get("callId")
                if isinstance(name, str) and name not in TOOLS and isinstance(call_id, str):
                    args = data.get("args", data.get("arguments"))
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except ValueError:
                            args = None
                    plugin_calls[call_id] = (name, args)
                    emit(tool_event(name, args, call_id, None))
            elif kind == "tool/result":
                result = data.get("message", {})
                call_id = result.get("toolCallId")
                if call := plugin_calls.pop(call_id, None):
                    ok = not result.get("isError")
                    event = tool_event(*call, call_id, ok)
                    if not ok:
                        event["code"] = "internal_error"
                    emit(event)
            elif kind == "turn/end":
                reason = data.get("reason", {}).get("kind")
                settle_deadline = now + STOP_SECONDS


class HarnessSessions:
    """One live process per conversation, evicting the oldest idle entry under pressure."""
    def __init__(self, capacity=4):
        self.capacity = capacity
        self.entries = OrderedDict()
        self.changed = threading.Condition()
        self.forgetting = set()
        self.disposing = set()
        self.closed = False

    def _dispose(self, slot):
        try:
            slot.dispose()
        finally:
            with self.changed:
                self.disposing.discard(slot.key)
                self.changed.notify_all()

    @contextmanager
    def lease(self, root, key, turn_id, cancel):
        persistent = key is not None
        key = key or "once-" + secrets.token_hex(16)
        victim = None
        with self.changed:
            if self.closed or key in self.forgetting or key in self.disposing:
                raise HarnessError("busy")
            slot = self.entries.get(key)
            if slot and slot.active:
                raise HarnessError("busy")
            if not slot:
                if len(self.entries) >= self.capacity:
                    victim = next((s for s in self.entries.values() if not s.active), None)
                    if not victim:
                        raise HarnessError("busy")
                    self.entries.pop(victim.key)
                    self.disposing.add(victim.key)
                slot = Conversation(root, key, persistent)
                self.entries[key] = slot
            self.entries.move_to_end(key)
            slot.active = turn_id, cancel
        try:
            if victim:
                self._dispose(victim)
            yield slot
        finally:
            with self.changed:
                slot.active = None
                if not persistent:
                    self.entries.pop(key)
                    self.disposing.add(key)
                self.changed.notify_all()
            if not persistent:
                self._dispose(slot)

    def interrupt(self, key, turn_id):
        with self.changed:
            slot = self.entries.get(key)
            if slot and slot.active and slot.active[0] == turn_id:
                slot.active[1].set()
                return True
            return False

    def forget(self, root, key, *, expired=None, saved=None):
        folder = agent_plugins.profile_home(root) / "conversations" / key
        with self.changed:
            if self.closed:
                return
            if key in self.forgetting:
                self.changed.wait_for(lambda: key not in self.forgetting)
                return
            slot = self.entries.get(key)
            if expired is not None and (key in self.disposing or (slot and slot.active)):
                return
            self.forgetting.add(key)
        try:
            if expired is not None:
                try:
                    last_active = max([folder.stat().st_mtime, *(p.stat().st_mtime for p in folder.iterdir())])
                except FileNotFoundError:
                    return
                if last_active >= expired or saved(key):
                    return
            with self.changed:
                while (slot and slot.active) or key in self.disposing:
                    if slot and slot.active:
                        slot.active[1].set()
                    self.changed.wait()
                slot = self.entries.pop(key, None)
            try:
                if slot:
                    slot.dispose()
            finally:
                if folder.is_dir():
                    shutil.rmtree(folder)
        finally:
            with self.changed:
                self.forgetting.discard(key)
                self.changed.notify_all()

    def prune_drafts(self, root, saved, *, ttl=DRAFT_TTL_SECONDS):
        folder = agent_plugins.profile_home(root) / "conversations"
        cutoff = time.time() - ttl
        for draft in folder.glob("wr_*"):
            if DRAFT_KEY.fullmatch(draft.name) and draft.is_dir():
                self.forget(root, draft.name, expired=cutoff, saved=saved)

    def shutdown(self):
        with self.changed:
            self.closed = True
            for slot in self.entries.values():
                if slot.active:
                    slot.active[1].set()
            self.changed.wait_for(lambda: not self.forgetting and not self.disposing and
                                  all(not slot.active for slot in self.entries.values()))
            slots = list(self.entries.values())
            self.entries.clear()
        with ExitStack() as cleanup:
            for slot in slots:
                cleanup.callback(slot.dispose)


async def turn_events(editor, provider, model, prompt, base_revision, conversation_key=None, turn_id=None, history=(),
                      *, reload_plugins=False):
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    cancel, disconnected = threading.Event(), threading.Event()

    def emit(event):
        if not disconnected.is_set():
            try:
                loop.call_soon_threadsafe(queue.put_nowait, event)
            except RuntimeError:
                cancel.set()

    def worker():
        tools_used = []
        runtime = editor.runtime
        exchange_id = turn_id or secrets.token_hex(16)
        metrics = TurnTelemetry(runtime, exchange_id, editor.scope, model, secrets=(provider.key,))

        def publish(event):
            if event["type"] in ("tool", "_usage"):
                metrics.observe(event)
                if event["type"] == "_usage":
                    return
                if event["ok"] is not None:
                    tools_used.append({k: event[k] for k in ("name", "op", "ok") if k in event})
            emit({key: value for key, value in event.items() if key != "_proposal_id"})

        editor.cancel = cancel
        try:
            with runtime.harness_sessions.lease(runtime.root, conversation_key, turn_id, cancel) as slot:
                if conversation_key:
                    saved = runtime.workflows.get_run(conversation_key)
                    if not saved and editor.run_id:
                        raise HarnessError("not_found")
                    if saved and not editor.run_id:
                        raise HarnessError("draft_already_saved", details={"run_id": conversation_key})
                answer = slot.run(editor, provider, model, prompt, history, publish, cancel, reload_plugins=reload_plugins)
                if cancel.is_set():
                    raise HarnessError("turn_stopped")
                try:
                    slot.remember({"id": exchange_id, "user": prompt, "answer": answer,
                                   "tools": tools_used, "state": "done",
                                   "proposal_ids": list(dict.fromkeys(editor.proposal_ids))[-2:]})
                except (ValueError, OSError) as exc:
                    runtime.log(f"助手对话记录保存失败 ({type(exc).__name__})")
                proposal_ids = list(dict.fromkeys(editor.proposal_ids))[-2:]
                store = getattr(runtime, "harness_store", None)
                proposals = [store.public_proposal(p) for pid in proposal_ids if (p := store.get_proposal(pid))]
                result = {"type": "done", "message": answer, "proposals": proposals,
                          "run_updated": editor.run_updates, "refresh_run": editor.refresh_run, "refresh_library": editor.refresh_library,
                          "editor": editor.editor if editor.editor != editor.original else None,
                          "run_request": editor.final_run_request(), "base_revision": editor.revision or base_revision}
        except HarnessError as exc:
            result = exc.event()
        except TimeoutError:
            result = HarnessError("turn_stopped" if cancel.is_set() else "turn_timeout").event()
        except SdkError as exc:
            runtime.log(f"助手模型未完成 ({type(exc).__name__})")
            result = HarnessError("turn_stopped" if cancel.is_set() else "model_error").event()
        except Exception as exc:
            runtime.log(f"助手未完成 ({type(exc).__name__})")
            result = HarnessError("internal_error").event()
        metrics.finish(result.get("code"))
        emit(result)

    threading.Thread(target=worker, name="studio-dsh", daemon=True).start()
    try:
        yield {"type": "started", "model": model}
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=5)
            except TimeoutError:
                yield {"type": "heartbeat"}
                continue
            yield event
            if event["type"] in ("error", "done"):
                break
    finally:
        disconnected.set()
        cancel.set()
