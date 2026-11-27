#!/usr/bin/env python3
"""Google Colab backend manager built directly on top of official google-colab-cli.

Handles headless OAuth2 (copy-paste flow, stored in a 0600 JSON file without requiring
a desktop Linux keyring), real-time Compute Unit queries with non-blocking background
refresh, GPU session provisioning, persistent Jupyter kernel execution with streaming
output and tqdm progress parsing, file upload/download, and clean teardown (unassign).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Optional

import requests
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from colab_cli.auth import PUBLIC_SCOPES, REMOTE_REDIRECT_URI
from colab_cli.client import (
    Accelerator,
    Client,
    ColabRequestError,
    Prod,
    Shape,
    TooManyAssignmentsError,
    Variant,
    resolve_assign_shape,
    shape_display_label,
)
from colab_cli.contents import ContentsClient
from colab_cli.runtime import ColabRuntime
from colab_cli.state import SessionState, StateStore

from ..logs import redact_secrets

TOKEN_REFRESH_MARGIN = timedelta(minutes=5)
STATUS_TTL_SECONDS = 15.0
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
TQDM_RE = re.compile(
    r"^(?:(?P<label>[^|\r\n]*?)\s*:?\s*)?(?P<pct>\d{1,3})%\|[^|\r\n]*\|\s*(?P<detail>[^\[\r\n]*?)\s*(?P<rate>\[[^\]\r\n]*\])?\s*$"
)

GPU_MAP: dict[str, Accelerator] = {
    "A100": Accelerator.A100,
    "H100": Accelerator.H100,
    "G4": Accelerator.G4,
    "L4": Accelerator.L4,
    "T4": Accelerator.T4,
}
# Google Colab rejects shape=hm (HTTP 400) for single-shape GPUs.
# colab_cli 0.8.0 only lists L4/TPUs in HIGH_MEM_ONLY_ACCELERATORS, missing H100 and G4.
SINGLE_SHAPE_GPUS: frozenset[str] = frozenset({"H100", "G4", "L4"})


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def parse_tqdm_line(raw: str) -> Optional[dict[str, Any]]:
    """Parse a single tqdm progress bar line (diffusers / huggingface_hub / hf_xet)."""
    clean = strip_ansi(raw).strip()
    if not clean or "%|" not in clean:
        return None
    m = TQDM_RE.match(clean)
    if not m:
        return None
    pct = max(0, min(100, int(m.group("pct"))))
    label = (m.group("label") or "").strip(" :\t")[:80]
    detail = (m.group("detail") or "").strip()[:80]
    rate = (m.group("rate") or "").strip("[] ")[:60]
    return {"label": label, "pct": pct, "detail": detail, "rate": rate}


def _short_error_body(exc: Exception, limit: int = 160) -> str:
    """Extract a concise, secret-redacted text snippet from a ColabRequestError response."""
    raw = getattr(exc, "response_body", None)
    if not raw:
        resp = getattr(exc, "response", None)
        raw = getattr(resp, "text", None) if resp is not None else None
    if not raw:
        return ""
    s = re.sub(r"<style[^>]*>.*?</style>", " ", str(raw), flags=re.S | re.I)
    s = re.sub(r"<script[^>]*>.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""
    return redact_secrets(s)[:limit]


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _load_bundled_oauth_config() -> dict:
    cfg = resources.files("colab_cli").joinpath("oauth_config.json")
    return json.loads(cfg.read_text(encoding="utf-8"))


class ColabBackend:
    """Thread-safe manager for headless Google Colab GPU sessions."""

    def __init__(self, root: Path, logger: Callable[[str], None]) -> None:
        self.root = root
        self.log = logger
        self.token_path = root / "colab_token.json"
        self.sessions_path = root / "colab_sessions.json"
        self.hf_token_path = root / "hf_token.txt"
        self._store = StateStore(str(self.sessions_path))
        self._auth_lock = threading.Lock()
        self._pending_flow: Optional[InstalledAppFlow] = None
        self._pending_flow_at: float = 0.0
        self._email_cache: str = ""
        self._status_lock = threading.Lock()
        self._status_cache: Optional[dict] = None
        self._status_at: float = 0.0
        self._refresh_in_flight: bool = False
        self._active_runtime: Optional[ColabRuntime] = None
        self._active_session: Optional[SessionState] = None
        self._gpu_health_lock = threading.Lock()
        self._gpu_health: dict[str, dict[str, Any]] = {}

    def _record_gpu_health(self, gpu_key: str, status: str, code: int = 200, msg: str = "") -> None:
        with self._gpu_health_lock:
            self._gpu_health[gpu_key.upper()] = {
                "status": status,  # ok | unavailable | error
                "code": code,
                "at": int(time.time()),
                "msg": msg[:120],
            }

    def gpu_health_snapshot(self) -> dict[str, dict[str, Any]]:
        now = time.time()
        with self._gpu_health_lock:
            # Keep recent observations for 30 minutes
            return {
                k: dict(v)
                for k, v in self._gpu_health.items()
                if now - float(v.get("at") or 0) < 1800
            }

    # ── HF Token helpers ──────────────────────────────────────────────

    def get_hf_token(self, fallback: str = "") -> str:
        if self.hf_token_path.exists():
            val = self.hf_token_path.read_text(encoding="utf-8").strip()
            if val:
                return val
        return fallback.strip()

    def set_hf_token(self, token: str) -> None:
        token = token.strip()
        if not token:
            self.hf_token_path.unlink(missing_ok=True)
            return
        _write_private(self.hf_token_path, token + "\n")

    # ── OAuth2 headless flow ──────────────────────────────────────────

    def has_credentials(self) -> bool:
        return self.token_path.exists()

    def start_oauth(self) -> str:
        with self._auth_lock:
            client_config = _load_bundled_oauth_config()
            flow = InstalledAppFlow.from_client_config(client_config, PUBLIC_SCOPES)
            flow.redirect_uri = REMOTE_REDIRECT_URI
            auth_url, _ = flow.authorization_url(
                prompt="consent",
                access_type="offline",
                token_usage="remote",
            )
            self._pending_flow = flow
            self._pending_flow_at = time.time()
            return auth_url

    def complete_oauth(self, code: str) -> dict:
        code = code.strip()
        if not code:
            raise RuntimeError("授权码不能为空")
        with self._auth_lock:
            if self._pending_flow is None or time.time() - self._pending_flow_at > 900:
                raise RuntimeError("授权会话已过期，请重新点击「生成授权链接」")
            flow = self._pending_flow
            try:
                flow.fetch_token(code=code)
            except Exception as exc:
                raise RuntimeError(f"换取 Google 凭据失败：{exc}") from exc
            creds = flow.credentials
            _write_private(self.token_path, creds.to_json())
            self._pending_flow = None
            self._email_cache = self._fetch_email(creds)
        self.invalidate_status()
        self.log(f"Google Colab 已授权：{self._email_cache or 'ok'}")
        return self.status_report(force=True, blocking=True)

    def logout(self) -> None:
        with self._auth_lock:
            self.token_path.unlink(missing_ok=True)
            self._pending_flow = None
            self._email_cache = ""
        with self._status_lock:
            self._status_cache = None
            self._status_at = 0.0
        self.log("已清除本机保存的 Google Colab 授权凭据")

    def _load_credentials(self) -> Credentials:
        with self._auth_lock:
            if not self.token_path.exists():
                raise RuntimeError("尚未连接 Google Colab，请先在「设置」里完成授权")
            try:
                data = json.loads(self.token_path.read_text(encoding="utf-8"))
                creds = Credentials.from_authorized_user_info(data, PUBLIC_SCOPES)
            except Exception as exc:
                raise RuntimeError(f"Colab 凭据文件损坏，请重新授权：{exc}") from exc
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        _write_private(self.token_path, creds.to_json())
                    except Exception as exc:
                        raise RuntimeError(
                            f"Colab 凭据刷新失败，请重新授权：{exc}"
                        ) from exc
                else:
                    raise RuntimeError("Colab 凭据已失效且无 refresh_token，请重新授权")
            if not self._email_cache:
                self._email_cache = self._fetch_email(creds)
            return creds

    @staticmethod
    def _fetch_email(creds: Credentials) -> str:
        try:
            resp = requests.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"access_token": creds.token},
                timeout=10,
            )
            if resp.ok:
                return str(resp.json().get("email") or "")
        except Exception:
            pass
        return ""

    def _client(self) -> Client:
        creds = self._load_credentials()
        return Client(Prod(), AuthorizedSession(creds))

    # ── Status & Compute Units (non-blocking background refresh) ──────

    def invalidate_status(self) -> None:
        with self._status_lock:
            self._status_at = 0.0

    def clear_gpu_health(self) -> None:
        with self._gpu_health_lock:
            self._gpu_health.clear()
        self.invalidate_status()

    def _unauthed_report(self) -> dict:
        return {
            "authed": False,
            "ok": True,
            "email": "",
            "error": "",
            "checked_at": int(time.time()),
            "balance": None,
            "rate_per_hour": None,
            "assignments_count": 0,
            "eligible_gpus": [],
            "eligible_tpus": [],
            "gpu_health": self.gpu_health_snapshot(),
            "sessions": [],
            "any_running": False,
            "hf_token_set": bool(self.get_hf_token()),
            "refreshing": False,
        }

    @staticmethod
    def _fetch_eligible_accelerators(client: Client) -> tuple[list[str], list[str]]:
        try:
            url = client.colab_domain.rstrip("/") + "/tun/m/ccu-info"
            resp = client.session.get(
                url,
                params={"authuser": "0"},
                headers={
                    "Accept": "application/json",
                    "X-Colab-Client-Agent": "cli",
                },
                timeout=10,
            )
            if not resp.ok:
                return [], []
            raw = client._strip_xssi_prefix(resp.text)
            data = json.loads(raw) if raw else {}
            gpus = [str(x).upper() for x in (data.get("eligibleGpus") or []) if x]
            tpus = [str(x).upper() for x in (data.get("eligibleTpus") or []) if x]
            return gpus, tpus
        except Exception:
            return [], []

    def _fetch_status_sync(self) -> dict:
        if not self.has_credentials():
            report = self._unauthed_report()
            with self._status_lock:
                self._status_cache = report
                self._status_at = time.time()
            return dict(report)

        try:
            client = self._client()
            usage = client.get_consumption_user_info()
            eligible_gpus, eligible_tpus = self._fetch_eligible_accelerators(client)
            assignments = client.list_assignments()
            local = self._store.list()
            name_by_ep = {s.endpoint: s.name for s in local.values()}
            live_eps = {a.endpoint for a in assignments}
            for lname, s in list(local.items()):
                if s.endpoint not in live_eps:
                    self._store.remove(lname)
            rows = []
            for a in assignments:
                rows.append(
                    {
                        "name": name_by_ep.get(a.endpoint, "external"),
                        "endpoint": a.endpoint,
                        "gpu": "CPU" if a.accelerator.value == "NONE" else a.accelerator.value,
                        "shape": shape_display_label(a.machine_shape),
                        "variant": a.variant.name,
                    }
                )
            report = {
                "authed": True,
                "ok": True,
                "email": self._email_cache,
                "error": "",
                "checked_at": int(time.time()),
                "balance": round(float(usage.paid_compute_units_balance), 2),
                "rate_per_hour": round(float(usage.consumption_rate_hourly), 2),
                "assignments_count": int(usage.assignments_count),
                "eligible_gpus": eligible_gpus,
                "eligible_tpus": eligible_tpus,
                "sessions": rows,
                "any_running": bool(rows),
                "hf_token_set": bool(self.get_hf_token()),
                "refreshing": False,
            }
        except Exception as exc:
            report = {
                "authed": self.has_credentials(),
                "ok": False,
                "email": self._email_cache,
                "error": redact_secrets(str(exc))[:260],
                "checked_at": int(time.time()),
                "balance": None,
                "rate_per_hour": None,
                "assignments_count": 0,
                "eligible_gpus": [],
                "eligible_tpus": [],
                "sessions": [],
                "any_running": False,
                "hf_token_set": bool(self.get_hf_token()),
                "refreshing": False,
            }
        with self._status_lock:
            self._status_cache = report
            self._status_at = time.time() - (0.0 if report["ok"] else 10.0)
        return dict(report)

    def _trigger_bg_refresh(self) -> None:
        with self._status_lock:
            if self._refresh_in_flight:
                return
            self._refresh_in_flight = True

        def worker() -> None:
            try:
                self._fetch_status_sync()
            finally:
                with self._status_lock:
                    self._refresh_in_flight = False

        threading.Thread(target=worker, daemon=True, name="colab-status-refresh").start()

    def status_report(self, force: bool = False, blocking: bool = True) -> dict:
        if not self.has_credentials():
            report = self._unauthed_report()
            with self._status_lock:
                self._status_cache = report
                self._status_at = time.time()
            return dict(report)

        now = time.time()
        with self._status_lock:
            cached = self._status_cache
            if cached is not None and not cached.get("authed"):
                cached = None
            fresh = cached is not None and (now - self._status_at) < STATUS_TTL_SECONDS
            in_flight = self._refresh_in_flight

        if not force and fresh and cached is not None:
            out = dict(cached)
            out["hf_token_set"] = bool(self.get_hf_token())
            out["gpu_health"] = self.gpu_health_snapshot()
            out["refreshing"] = in_flight
            return out

        if not blocking and not force:
            self._trigger_bg_refresh()
            if cached is not None:
                out = dict(cached)
                out["hf_token_set"] = bool(self.get_hf_token())
                out["gpu_health"] = self.gpu_health_snapshot()
                out["refreshing"] = True
                return out
            return {
                "authed": True,
                "ok": True,
                "email": self._email_cache,
                "error": "",
                "checked_at": 0,
                "balance": None,
                "rate_per_hour": None,
                "assignments_count": 0,
                "eligible_gpus": [],
                "eligible_tpus": [],
                "gpu_health": self.gpu_health_snapshot(),
                "sessions": [],
                "any_running": False,
                "hf_token_set": bool(self.get_hf_token()),
                "refreshing": True,
            }

        rep = self._fetch_status_sync()
        rep["gpu_health"] = self.gpu_health_snapshot()
        return rep

    # ── Session Lifecycle ─────────────────────────────────────────────

    def _assign_with_retries(
        self,
        client: Client,
        gpu_key: str,
        accelerator: Accelerator,
        shape: Optional[Shape],
        cancel_check: Optional[Callable[[], bool]] = None,
        retries_override: Optional[int] = None,
    ):
        nbh = uuid.uuid4()
        retries = (
            max(0, int(retries_override))
            if retries_override is not None
            else max(0, int(os.getenv("COLAB_CLI_ASSIGN_RETRIES", "3")))
        )
        backoff = max(0.0, float(os.getenv("COLAB_CLI_RETRY_BACKOFF", "10")))

        assignment = client._get_assignment(nbh, Variant.GPU, accelerator, shape)
        if not hasattr(assignment, "token"):
            return assignment

        for attempt in range(retries + 1):
            if cancel_check and cancel_check():
                raise RuntimeError("任务已取消")
            try:
                return client._post_assignment(
                    nbh, assignment.token, Variant.GPU, accelerator, shape
                )
            except (ColabRequestError, requests.exceptions.ReadTimeout) as exc:
                status = (
                    exc.response.status_code
                    if isinstance(exc, ColabRequestError) and exc.response is not None
                    else None
                )
                if status == 412:
                    raise TooManyAssignmentsError(str(exc)) from exc
                retryable = isinstance(exc, requests.exceptions.ReadTimeout) or status in (502, 503, 504)
                if not retryable or attempt >= retries:
                    raise
                delay = backoff * (2**attempt)
                detail = ""
                if isinstance(exc, ColabRequestError) and getattr(exc, "response_body", None):
                    raw_body = re.sub(r"<style[^>]*>.*?</style>", " ", str(exc.response_body), flags=re.S | re.I)
                    raw_body = re.sub(r"<script[^>]*>.*?</script>", " ", raw_body, flags=re.S | re.I)
                    raw_body = re.sub(r"<[^>]+>", " ", raw_body)
                    raw_body = re.sub(r"\s+", " ", raw_body).strip()
                    if raw_body:
                        detail = f" · {redact_secrets(raw_body)[:100]}"
                reason = "超时" if status is None else f"HTTP {status}（暂无空闲库存或服务繁忙{detail}）"
                self.log(
                    f"申请 {gpu_key} 遇到 {reason}，{int(delay)} 秒后进行第 {attempt + 2}/{retries + 1} 次尝试…"
                )
                slept = 0.0
                while slept < delay:
                    if cancel_check and cancel_check():
                        raise RuntimeError("任务已取消")
                    step = min(0.5, delay - slept)
                    time.sleep(step)
                    slept += step
                assignment = client._get_assignment(nbh, Variant.GPU, accelerator, shape)
                if not hasattr(assignment, "token"):
                    return assignment

    def ensure_session(
        self,
        gpu: str = "A100",
        high_mem: bool = True,
        session_name: str = "playground",
        cancel_check: Optional[Callable[[], bool]] = None,
        fallback_gpus: Optional[list[str]] = None,
        poll_rounds: int = 1,
        proxy_hooks: Optional[list[tuple[str, Optional[Callable[[], None]]]]] = None,
    ) -> SessionState:
        gpu_key = gpu.upper().strip()
        if gpu_key not in GPU_MAP:
            raise RuntimeError(f"不支持的 GPU 类型：{gpu}")

        candidates = [gpu_key]
        if fallback_gpus:
            for alt in fallback_gpus:
                ak = str(alt or "").upper().strip()
                if ak in GPU_MAP and ak not in candidates:
                    candidates.append(ak)

        accelerator = GPU_MAP[gpu_key]
        client = self._client()

        assignments = client.list_assignments()
        by_ep = {a.endpoint: a for a in assignments}
        existing = self._store.get(session_name)

        if existing and existing.endpoint in by_ep:
            live = by_ep[existing.endpoint]
            if live.accelerator == accelerator or (len(candidates) > 1 and live.accelerator.value in candidates):
                existing.token = live.runtime_proxy_info.token
                existing.url = live.runtime_proxy_info.url
                existing.token_expires_at = live.runtime_proxy_info.expires_at()
                self._store.add(existing)
                self._record_gpu_health(live.accelerator.value, "ok", 200, "运行中")
                self.log(
                    f"复用运行中的 Colab {live.accelerator.value}（{shape_display_label(live.machine_shape)}），"
                    "沿用常驻 Kernel 与已缓存模型"
                )
                self.invalidate_status()
                return existing
            self.log(
                f"切换 GPU：{existing.accelerator} → {'/'.join(candidates)}，先释放旧运行时 {existing.endpoint}"
            )
            self._unassign_endpoint(client, existing.endpoint, existing)
            self._store.remove(session_name)

        # Also check if there's an existing assignment with matching GPU we can adopt
        for a in assignments:
            if a.accelerator == accelerator or (len(candidates) > 1 and a.accelerator.value in candidates):
                s = SessionState(
                    name=session_name,
                    token=a.runtime_proxy_info.token,
                    url=a.runtime_proxy_info.url,
                    endpoint=a.endpoint,
                    token_expires_at=a.runtime_proxy_info.expires_at(),
                    variant=Variant.GPU.value,
                    accelerator=a.accelerator.value,
                    machine_shape=a.machine_shape.name,
                )
                self._store.add(s)
                self._record_gpu_health(a.accelerator.value, "ok", 200, "运行中")
                self.log(f"接管已有 Colab {a.accelerator.value} 实例 {a.endpoint}")
                self.invalidate_status()
                return s

        rounds = max(1, min(10, int(poll_rounds or 1)))
        proxies: list[tuple[str, Optional[Callable[[], None]]]] = (
            list(proxy_hooks) if proxy_hooks else [("", None)]
        )
        total_slots = rounds * len(proxies) * len(candidates)
        # Fail fast (1 attempt per slot) whenever polling across multiple GPUs, proxies, or rounds.
        per_gpu_retries = 0 if total_slots > 1 else None
        last_err: Optional[Exception] = None
        slot_idx = 0

        for r_idx in range(1, rounds + 1):
            for p_idx, (p_label, switch_fn) in enumerate(proxies):
                if cancel_check and cancel_check():
                    raise RuntimeError("任务已取消")
                if switch_fn is not None:
                    switch_fn()
                    client = self._client()
                    if len(proxies) > 1:
                        self.log(f"切换至出口线路：{p_label}（第 {r_idx}/{rounds} 轮 · 线路 {p_idx + 1}/{len(proxies)}）")

                for g_idx, cand_key in enumerate(candidates):
                    if cancel_check and cancel_check():
                        raise RuntimeError("任务已取消")
                    slot_idx += 1
                    has_more = slot_idx < total_slots
                    cand_acc = GPU_MAP[cand_key]
                    shape: Optional[Shape] = (
                        None if cand_key in SINGLE_SHAPE_GPUS else resolve_assign_shape(cand_acc, high_mem=high_mem)
                    )
                    ctx_parts = []
                    if rounds > 1:
                        ctx_parts.append(f"第 {r_idx}/{rounds} 轮")
                    if p_label:
                        ctx_parts.append(p_label)
                    if len(candidates) > 1:
                        ctx_parts.append(f"候选 {g_idx + 1}/{len(candidates)}")
                    ctx = f"（{' · '.join(ctx_parts)}）" if ctx_parts else ""
                    self.log(
                        f"正在向 Google Colab 申请 {cand_key}"
                        + ("（High-RAM）" if shape == Shape.HIGH_RAM else "")
                        + f" 运行时{ctx}…"
                    )
                    try:
                        res = self._assign_with_retries(
                            client, cand_key, cand_acc, shape, cancel_check=cancel_check, retries_override=per_gpu_retries
                        )
                    except TooManyAssignmentsError as exc:
                        self._record_gpu_health(cand_key, "error", 412, "活跃实例过多")
                        raise RuntimeError(
                            "Colab 拒绝分配（活跃实例过多或当前卡型暂时无库存）。请先点「释放算力」或换一档 GPU 重试。"
                        ) from exc
                    except ColabRequestError as exc:
                        code = exc.response.status_code if exc.response is not None else None
                        body_txt = _short_error_body(exc)
                        body_sfx = f" | 响应: {body_txt}" if body_txt else ""
                        if code in (400, 502, 503, 504) and shape == Shape.HIGH_RAM:
                            if code == 400:
                                self.log(f"{cand_key} 不接受 shape=hm 参数{body_sfx}，改用标准规格重试…")
                            else:
                                self.log(f"{cand_key}（High-RAM）返回 HTTP {code}{body_sfx}，自动降级尝试标准内存规格…")
                            shape = None
                            try:
                                res = self._assign_with_retries(
                                    client, cand_key, cand_acc, None, cancel_check=cancel_check, retries_override=per_gpu_retries
                                )
                            except (ColabRequestError, requests.exceptions.ReadTimeout) as exc2:
                                code2 = exc2.response.status_code if isinstance(exc2, ColabRequestError) and exc2.response is not None else 504
                                body2 = _short_error_body(exc2)
                                body2_sfx = f" | 响应: {body2}" if body2 else ""
                                self._record_gpu_health(cand_key, "unavailable" if code2 in (502, 503, 504) else "error", int(code2 or 0), f"HTTP {code2}")
                                last_err = exc2
                                if has_more:
                                    self.log(f"{cand_key} 标准规格返回 HTTP {code2}{body2_sfx}，继续下一轮询项…")
                                    continue
                                if code2 == 503:
                                    raise RuntimeError(
                                        f"Google Colab 当前暂无 {cand_key} 空闲库存（HTTP 503{body2_sfx}），请换用其他 GPU、切换出口线路或稍后重试。"
                                    ) from exc2
                                raise RuntimeError(f"账号暂不支持或暂无 {cand_key} 配额（HTTP {code2}{body2_sfx}），请切换其他 GPU。") from exc2
                        elif code in (502, 503, 504):
                            self._record_gpu_health(cand_key, "unavailable", int(code), f"HTTP {code} 无库存/超时")
                            last_err = exc
                            if has_more:
                                self.log(f"{cand_key} 返回 HTTP {code}{body_sfx}，继续下一轮询项…")
                                continue
                            raise RuntimeError(
                                f"Google Colab 当前暂无 {cand_key} 空闲库存（HTTP {code}{body_sfx}），请换用其他 GPU 或稍后重试。"
                            ) from exc
                        elif code == 400:
                            self._record_gpu_health(cand_key, "error", 400, "HTTP 400 不支持")
                            last_err = exc
                            if has_more:
                                self.log(f"{cand_key} 返回 HTTP 400{body_sfx}，继续下一轮询项…")
                                continue
                            raise RuntimeError(
                                f"Colab 拒绝了 {cand_key} 申请（HTTP 400{body_sfx}），请切换其他 GPU。"
                            ) from exc
                        else:
                            self._record_gpu_health(cand_key, "error", int(code or 0), f"HTTP {code}")
                            raise RuntimeError(f"Colab 申请运行时失败（HTTP {code}{body_sfx}）：{exc}") from exc
                    except requests.exceptions.ReadTimeout as exc:
                        self._record_gpu_health(cand_key, "unavailable", 504, "申请超时")
                        last_err = exc
                        if has_more:
                            self.log(f"{cand_key} 申请超时，继续下一轮询项…")
                            continue
                        raise RuntimeError(
                            f"向 Google Colab 申请 {cand_key} 多次超时，请稍后重试或切换其他 GPU。"
                        ) from exc

                    self._record_gpu_health(cand_key, "ok", 200, "已就绪")
                    s = SessionState(
                        name=session_name,
                        token=res.runtime_proxy_info.token,
                        url=res.runtime_proxy_info.url,
                        endpoint=res.endpoint,
                        token_expires_at=res.runtime_proxy_info.expires_at(),
                        variant=Variant.GPU.value,
                        accelerator=cand_acc.value,
                        machine_shape=(
                            Shape.HIGH_RAM.name
                            if (shape == Shape.HIGH_RAM or cand_key in SINGLE_SHAPE_GPUS)
                            else Shape.STANDARD.name
                        ),
                    )
                    self._store.add(s)
                    self.invalidate_status()
                    self.log(f"Colab {cand_key} 已就绪（{p_label + ' · ' if p_label else ''}{s.endpoint}）")
                    return s

            if r_idx < rounds:
                self.log(f"第 {r_idx}/{rounds} 轮未抢到空闲卡，5 秒后开始下一轮轮询…")
                slept = 0.0
                while slept < 5.0:
                    if cancel_check and cancel_check():
                        raise RuntimeError("任务已取消")
                    time.sleep(0.5)
                    slept += 0.5

        proxy_names = " / ".join(lbl for lbl, _ in proxies if lbl)
        raise RuntimeError(
            f"已完成 {rounds} 轮轮询（GPU：{' / '.join(candidates)}"
            + (f"，线路：{proxy_names}" if proxy_names else "")
            + f"），目前均无空闲库存（{last_err}）。请稍后重试或勾选更多 GPU。"
        )

    def refresh_session(self, session: SessionState) -> SessionState:
        if (
            session.token_expires_at
            and session.token_expires_at - datetime.now(timezone.utc) > TOKEN_REFRESH_MARGIN
        ):
            return session
        client = self._client()
        by_ep = {a.endpoint: a for a in client.list_assignments()}
        if session.endpoint not in by_ep:
            self._store.remove(session.name)
            raise RuntimeError("Colab 运行时已断开或被回收，请重新点击生成")
        live = by_ep[session.endpoint]
        session.token = live.runtime_proxy_info.token
        session.url = live.runtime_proxy_info.url
        session.token_expires_at = live.runtime_proxy_info.expires_at()
        self._store.add(session)
        return session

    def upload_file(self, session: SessionState, local: Path, remote: str) -> None:
        session = self.refresh_session(session)
        contents = ContentsClient(session)
        contents.upload(str(local), remote.lstrip("/"))

    def download_file(self, session: SessionState, remote: str, local: Path) -> None:
        session = self.refresh_session(session)
        local.parent.mkdir(parents=True, exist_ok=True)
        contents = ContentsClient(session)
        contents.download(remote.lstrip("/"), str(local))

    def _kernel_api(
        self, session: SessionState, method: str, suffix: str, timeout: float = 10.0
    ) -> Optional[requests.Response]:
        if not session or not session.url or not session.token:
            return None
        try:
            return requests.request(
                method,
                session.url.rstrip("/") + suffix,
                headers={
                    "X-Colab-Runtime-Proxy-Token": session.token,
                    "X-Colab-Client-Agent": "cli",
                },
                timeout=timeout,
            )
        except Exception:
            return None

    def _kernel_state(self, session: SessionState) -> Optional[str]:
        if not session or not session.kernel_id:
            return None
        resp = self._kernel_api(session, "GET", "/api/kernels", timeout=10.0)
        if resp is None or not resp.ok:
            return None
        try:
            for item in resp.json() or []:
                if isinstance(item, dict) and item.get("id") == session.kernel_id:
                    return str(item.get("execution_state") or "")
        except Exception:
            return None
        return None

    def _interrupt_kernel(self, session: SessionState) -> bool:
        if not session or not session.kernel_id:
            return False
        resp = self._kernel_api(session, "POST", f"/api/kernels/{session.kernel_id}/interrupt", timeout=10.0)
        return bool(resp is not None and resp.ok)

    def _restart_kernel(self, session: SessionState, wait_s: float = 15.0) -> bool:
        if not session or not session.kernel_id:
            return False
        resp = self._kernel_api(session, "POST", f"/api/kernels/{session.kernel_id}/restart", timeout=15.0)
        if resp is None or not resp.ok:
            return False
        deadline = time.time() + wait_s
        while time.time() < deadline:
            st = self._kernel_state(session)
            if st == "idle":
                return True
            time.sleep(0.8)
        return True

    def _ensure_kernel_idle(self, session: SessionState) -> None:
        """If a previous cancelled job left the Jupyter kernel busy, interrupt or restart it cleanly."""
        if not session.kernel_id:
            return
        state = self._kernel_state(session)
        if state != "busy":
            return
        self.log("检测到上次任务仍在 Colab Kernel 后台运行，正在发送中断信号…")
        self._interrupt_kernel(session)
        deadline = time.time() + 6.0
        while time.time() < deadline:
            time.sleep(0.8)
            if self._kernel_state(session) != "busy":
                self.log("Colab Kernel 已恢复空闲，继续执行新任务")
                return
        self.log("Kernel 未响应中断，自动重启 Python Kernel（保留当前 GPU 实例与已下载模型）…")
        self._restart_kernel(session, wait_s=15.0)

    def execute_code(
        self,
        session: SessionState,
        code: str,
        cancel_check: Optional[Callable[[], bool]] = None,
        idle_timeout: float = 0.0,
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> list[dict]:
        session = self.refresh_session(session)
        self._ensure_kernel_idle(session)

        def on_kernel(kid: str) -> None:
            session.kernel_id = kid
            self._store.add(session)

        def on_sess(sid: str) -> None:
            session.session_id = sid
            self._store.add(session)

        runtime = ColabRuntime(
            session.url,
            session.token,
            session_name=session.name,
            kernel_id=session.kernel_id,
            session_id=session.session_id,
            on_kernel_started=on_kernel,
            on_session_started=on_sess,
        )
        self._active_runtime = runtime
        self._active_session = session

        stream_buf = {"line": ""}
        errors: list[str] = []
        last_completed_tqdm = {"key": ""}

        def handle_line(raw_line: str) -> None:
            clean = strip_ansi(raw_line).strip()
            if not clean:
                return
            if "hf_" in clean.lower() and "token" in clean.lower():
                return
            info = parse_tqdm_line(clean)
            if info is not None:
                if progress_cb:
                    try:
                        progress_cb(info)
                    except Exception:
                        pass
                if info["pct"] >= 100:
                    key = f"{info['label']}|{info['detail']}"
                    if key != last_completed_tqdm["key"]:
                        last_completed_tqdm["key"] = key
                        self.log(redact_secrets(clean)[-300:])
                return
            self.log(redact_secrets(clean)[-400:])

        def emit_text(chunk: str) -> None:
            if not chunk:
                return
            text = chunk.replace("\r\n", "\n").replace("\r", "\n")
            lines = (stream_buf["line"] + text).split("\n")
            stream_buf["line"] = lines.pop()
            for ln in lines:
                handle_line(ln)
            # tqdm often writes a full progress bar without trailing \r/\n until next tick.
            tail = stream_buf["line"]
            if tail and "%|" in tail:
                info = parse_tqdm_line(tail)
                if info is not None:
                    handle_line(tail)
                    stream_buf["line"] = ""

        def hook(out: dict) -> None:
            if cancel_check and cancel_check():
                self._interrupt_kernel(session)
                runtime.stop(shutdown_kernel=False)
                raise RuntimeError("任务已取消")
            otype = out.get("output_type")
            if otype == "stream":
                emit_text(str(out.get("text") or ""))
            elif otype == "error":
                ename = out.get("ename", "Error")
                evalue = redact_secrets(str(out.get("evalue", "")))
                tb = out.get("traceback") or []
                summary = f"{ename}: {evalue}"
                errors.append(summary)
                self.log("ERR " + summary[:350])
                for tb_line in tb[-4:]:
                    for sub in strip_ansi(str(tb_line)).splitlines():
                        if sub.strip():
                            self.log("  " + redact_secrets(sub.strip())[-350:])

        try:
            runtime.execute_code(
                "import os; os.makedirs('/content', exist_ok=True); os.chdir('/content')",
                timeout=60.0,
            )
            outputs = runtime.execute_code(
                code,
                output_hook=hook,
                timeout=None if idle_timeout <= 0 else idle_timeout,
            )
            if stream_buf["line"].strip():
                handle_line(stream_buf["line"])
        finally:
            self._active_runtime = None
            self._active_session = None
            runtime.stop(shutdown_kernel=False)

        for out in outputs:
            if out.get("output_type") == "error":
                ename = out.get("ename", "Error")
                evalue = redact_secrets(str(out.get("evalue", "")))
                raise RuntimeError(f"Colab 执行报错：{ename}: {evalue}")
        if errors:
            raise RuntimeError(f"Colab 执行报错：{errors[-1]}")
        return outputs

    def interrupt_active(self) -> None:
        sess = self._active_session
        rt = self._active_runtime
        if sess is not None:
            try:
                self._interrupt_kernel(sess)
            except Exception:
                pass
        if rt is not None:
            try:
                rt.stop(shutdown_kernel=False)
            except Exception:
                pass

    def _unassign_endpoint(
        self, client: Client, endpoint: str, s: Optional[SessionState] = None
    ) -> None:
        if s is not None:
            try:
                rt = ColabRuntime(s.url, s.token, kernel_id=s.kernel_id)
                rt.stop(shutdown_kernel=True)
            except Exception:
                pass
        client.unassign(endpoint)

    def release_all(self, session_name: Optional[str] = None) -> list[str]:
        """Unassign active Colab runtime(s) so compute units stop burning immediately."""
        self.invalidate_status()
        if not self.has_credentials():
            return []
        client = self._client()
        local = self._store.list()
        assignments = client.list_assignments()
        released: list[str] = []

        if session_name:
            target = local.get(session_name)
            if target:
                try:
                    self._unassign_endpoint(client, target.endpoint, target)
                    released.append(f"{target.accelerator} ({target.endpoint})")
                except Exception as exc:
                    self.log(f"释放 {target.endpoint} 提示：{exc}")
                self._store.remove(session_name)
            self.invalidate_status()
            return released

        local_by_ep = {s.endpoint: s for s in local.values()}
        for a in assignments:
            try:
                self._unassign_endpoint(client, a.endpoint, local_by_ep.get(a.endpoint))
                released.append(f"{a.accelerator.value} ({a.endpoint})")
            except Exception as exc:
                self.log(f"释放 {a.endpoint} 失败：{exc}")
        for lname in list(local.keys()):
            self._store.remove(lname)
        self.invalidate_status()
        return released
