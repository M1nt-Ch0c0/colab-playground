"""Record bounded tool metadata. Arguments and tool results stay outside telemetry."""
from __future__ import annotations

import re
import sqlite3
import threading
import time

from .agent_plugins import TOOL
from .agent_tools import TOOLS
from .harness_errors import HARNESS_ERROR_CODES


def safe_model(name, secrets=()):
    if (isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}", name)
            and "://" not in name and not name.lower().startswith(("sk-", "hf_", "bearer", "ghp_", "xoxb-"))
            and not any(isinstance(secret, str) and secret and secret in name for secret in secrets)):
        return name
    return ""


def cache_usage(usage):
    """Normalize aggregate usage supplied by the pinned SDK and compatible model providers."""
    if not isinstance(usage, dict):
        return None

    def number(source, *names):
        return next((source[name] for name in names if type(source.get(name)) is int and 0 <= source[name] <= 10**9), None)

    hit = number(usage, "cacheReadTokens", "prompt_cache_hit_tokens", "cache_hit_tokens", "cacheRead",
                 "cache_read_input_tokens", "cachedContentTokenCount")
    miss = number(usage, "prompt_cache_miss_tokens", "cache_miss_tokens")
    details = usage.get("prompt_tokens_details")
    if hit is None and isinstance(details, dict):
        hit = number(details, "cached_tokens")
    total = number(usage, "prompt_tokens", "promptTokenCount")
    uncached = number(usage, "inputTokens", "input", "input_tokens")
    if miss is None and total is not None:
        miss = max(0, total - (hit or 0))
    if miss is None and uncached is not None:
        miss = uncached + (number(usage, "cacheWriteTokens", "cacheWrite", "cache_creation_input_tokens") or 0)
    return None if hit is None and miss is None else (hit or 0, miss or 0)


class TurnTelemetry:
    def __init__(self, runtime, turn_id, scope, model, *, secrets=()):
        self.store = getattr(runtime, "harness_store", None)
        self.log = runtime.log if hasattr(runtime, "log") else lambda _: None
        self.secrets = (*getattr(runtime, "secret", {}).values(), *secrets)
        self.turn_id = safe_model(turn_id, self.secrets)
        self.scope = safe_model(scope, self.secrets)
        self.record_model(model)
        self.started = {}
        self.failed = set()
        self.sequence = 0
        self.last_metric_id = None
        self.hit = self.miss = 0
        self.closed = False
        self.lock = threading.Lock()

    def observe(self, event):
        if not self.store:
            return
        with self.lock:
            if self.closed:
                return
            if event["type"] == "_usage":
                self.hit += event["hit"]
                self.miss += event["miss"]
                return
            call_id = event["call_id"]
            if event["ok"] is None:
                name = event["name"]
                allowed = TOOLS.get(name, (None, {}))[1].get("properties", {}).get("op", {}).get("enum", ())
                op = event.get("op")
                op = op if op in allowed else None
                name = name if name in TOOLS or name == TOOL else "plugin"
                self.sequence += 1
                self.started[call_id] = (self.sequence, name, op, time.monotonic(), (name, op) in self.failed)
            else:
                self._complete(call_id, event["ok"], event.get("code"), event.get("_proposal_id"))

    def _complete(self, call_id, ok, code, proposal_id=None):
        if (call := self.started.pop(call_id, None)) is None:
            return
        sequence, name, op, started_at, retry = call
        if ok:
            self.failed.discard((name, op))
        else:
            self.failed.add((name, op))
        try:
            self.last_metric_id = self.store.tool_metric(
                turn_id=self.turn_id, conversation_key=self.scope, call_seq=sequence, model=self.model,
                tool_name=name, op=op, ok=ok, error_code=None if ok else code if code in HARNESS_ERROR_CODES else "internal_error",
                retry_in_turn=int(retry), latency_ms=max(0, round(1000 * (time.monotonic() - started_at))),
                proposal_id=proposal_id,
            )
        except sqlite3.Error as exc:
            self.log(f"助手统计写入失败 ({type(exc).__name__})")

    def record_model(self, model, key=None):
        self.model = safe_model(model, (*self.secrets, key))

    def finish(self, error_code=None):
        if not self.store:
            return
        with self.lock:
            for call_id in list(self.started):
                self._complete(call_id, False, error_code)
            if self.last_metric_id is not None and (self.hit or self.miss):
                try:
                    self.store.tool_usage(self.last_metric_id, self.hit, self.miss)
                except sqlite3.Error as exc:
                    self.log(f"助手统计写入失败 ({type(exc).__name__})")
            self.closed = True
