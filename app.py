#!/usr/bin/env python3
"""Colab Studio HTTP server (default 127.0.0.1:8787).

Image (Diffusers / ComfyUI three-component) + video/audio (MiniMax-H3) playground
on on-demand Google Colab GPUs. See README.md and docs/API.md for configuration.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from colab_backend import ColabBackend
from jobs import (
    COMFY_BUILTIN_PRESETS,
    COMFY_CLIP_TYPES,
    COMFY_SAMPLERS,
    COMFY_SCHEDULERS,
    COMFY_TEMPLATES,
    DEFAULTS,
    GPUS,
    IMAGE_MODELS,
    LIMITS,
    VIDEO_WORKFLOWS,
    LogBuffer,
    Studio,
    boot_message,
    normalize_job,
    parse_model_link,
)
from store import TRASH_DAYS, Store
from ui import LOGIN_HTML, PAGE_HTML

VERSION = "2.1"
ROOT = Path(os.environ.get("QP_ROOT", str(Path(__file__).resolve().parent)))
SECRET_PATH = Path(os.environ.get("QP_SECRET", ROOT / "secret.env"))
OUT_DIR = ROOT / "out"
HOST = os.environ.get("QP_HOST", "127.0.0.1")
PORT = int(os.environ.get("QP_PORT", "8787"))
DEFAULT_IDLE_SECONDS = int(os.environ.get("QP_IDLE_SECONDS", "600"))
MAX_BODY = 16 * 1024 * 1024
COOKIE = "qp_auth"


def load_secret() -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in SECRET_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    if not data.get("password") or not data.get("token"):
        raise SystemExit("secret.env needs password and token")
    return data


def configure_proxy(secret: dict[str, str], log_fn) -> None:
    proxy = (secret.get("proxy_url") or "").strip()
    if not proxy:
        return
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ[key] = proxy
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    parts = [p.strip() for p in no_proxy.split(",") if p.strip()]
    extras = ["127.0.0.1", "localhost", "::1", "host.docker.internal", "172.17.0.1", "172.19.0.1"]
    cpa_host = urlsplit((secret.get("cpa_base") or "").strip()).hostname
    if cpa_host:
        extras.append(cpa_host)
    for local in extras:
        if local not in parts:
            parts.append(local)
    merged = ",".join(parts)
    os.environ["NO_PROXY"] = merged
    os.environ["no_proxy"] = merged
    log_fn("已启用出站代理（来自 secret.env，本机与内网回环直连）")


SECRET = load_secret()
LOG = LogBuffer()
COLAB = ColabBackend(ROOT, LOG)
STORE = Store(OUT_DIR, LOG)
STUDIO = Studio(ROOT, SECRET, COLAB, STORE, LOG, DEFAULT_IDLE_SECONDS)

_fail_lock = threading.Lock()
_login_failures: dict[str, list[float]] = {}


def _login_blocked(ip: str) -> bool:
    now = time.time()
    with _fail_lock:
        hits = [t for t in _login_failures.get(ip, []) if now - t < 600]
        _login_failures[ip] = hits
        return len(hits) >= 8


def _login_failed(ip: str) -> None:
    with _fail_lock:
        _login_failures.setdefault(ip, []).append(time.time())


class ApiError(Exception):
    def __init__(self, code: int, msg: str) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg


def _ids(body: dict) -> list[str]:
    ids = body.get("ids")
    if not isinstance(ids, list) or not ids:
        raise ApiError(400, "ids 必须是非空数组")
    if len(ids) > 2000:
        raise ApiError(400, "一次最多处理 2000 个")
    return [str(i) for i in ids]


def _bool(v) -> bool:
    if isinstance(v, str):
        return v.lower() in {"1", "true", "yes", "on"}
    return bool(v)


def config_payload() -> dict:
    return {
        "version": VERSION,
        "gpus": GPUS,
        "image_models": IMAGE_MODELS,
        "recent_models": STUDIO.recent_models(),
        "video_workflows": VIDEO_WORKFLOWS,
        "comfy": {
            "templates": COMFY_TEMPLATES,
            "samplers": COMFY_SAMPLERS,
            "schedulers": COMFY_SCHEDULERS,
            "clip_types": COMFY_CLIP_TYPES,
            "builtin_presets": COMFY_BUILTIN_PRESETS,
            "presets": STUDIO.comfy_presets(),
        },
        "proxy": STUDIO.proxy_report(),
        "limits": LIMITS,
        "defaults": DEFAULTS,
        "trash_retention_days": TRASH_DAYS,
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ColabStudio/" + VERSION

    def log_message(self, fmt: str, *args) -> None:
        return

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    # ── response helpers ──────────────────────────────────────────────

    def send_bytes(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
        headers.update(extra or {})
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, code: int, payload: dict) -> None:
        self.send_bytes(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def send_html(self, code: int, html: str, extra: dict | None = None) -> None:
        extra = dict(extra or {})
        extra.setdefault("X-Frame-Options", "DENY")
        extra.setdefault("Referrer-Policy", "same-origin")
        self.send_bytes(code, html.encode("utf-8"), "text/html; charset=utf-8", extra)

    def redirect(self, location: str, extra: dict | None = None) -> None:
        hdr = {"Location": location}
        hdr.update(extra or {})
        self.send_bytes(302, b"", "text/plain", hdr)

    def send_file(self, path: Path, ctype: str, cache: str = "no-store", download: str = "") -> None:
        st = path.stat()
        size = st.st_size
        etag = f'W/"{size}-{st.st_mtime_ns}"'
        if not download and cache != "no-store" and self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", cache)
            self.send_header("Content-Length", "0")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return

        start, end, code = 0, max(0, size - 1), 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes=") and size > 0:
            spec = rng[6:].split(",")[0].strip()
            s, dash, e = spec.partition("-")
            try:
                if not dash:
                    raise ValueError("missing dash")
                if s:
                    start = int(s)
                    end = int(e) if e else size - 1
                else:  # suffix range: last N bytes
                    suffix = int(e)
                    if suffix <= 0:
                        raise ValueError("non-positive suffix")
                    start = max(0, size - suffix)
                    end = size - 1
            except ValueError:
                self.send_bytes(416, b"", "text/plain", {"Content-Range": f"bytes */{size}"})
                return
            if start < 0 or start >= size or end < start:
                self.send_bytes(416, b"", "text/plain", {"Content-Range": f"bytes */{size}"})
                return
            end = min(end, size - 1)
            code = 206
        length = 0 if size == 0 else (end - start + 1)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", cache)
        self.send_header("ETag", etag)
        self.send_header("X-Content-Type-Options", "nosniff")
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.end_headers()
        if self.command == "HEAD" or length == 0:
            return
        with path.open("rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(262144, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    # ── request helpers ───────────────────────────────────────────────

    def parts(self) -> tuple[str, dict[str, str]]:
        u = urlsplit(self.path)
        path = u.path.rstrip("/") or "/"
        q = {k: v[-1] for k, v in parse_qs(u.query).items()}
        return path, q

    def client_ip(self) -> str:
        return (
            self.headers.get("CF-Connecting-IP")
            or (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
            or self.client_address[0]
        )

    def authed(self) -> bool:
        token = ""
        auth = self.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        else:
            for part in (self.headers.get("Cookie") or "").split(";"):
                part = part.strip()
                if part.startswith(COOKIE + "="):
                    token = part.split("=", 1)[1]
        return bool(token) and hmac.compare_digest(token, SECRET["token"])

    def read_body(self) -> bytes:
        raw_len = self.headers.get("Content-Length")
        if not raw_len:
            return b""
        try:
            length = int(raw_len)
        except ValueError as exc:
            raise ApiError(400, "无效的 Content-Length") from exc
        if length < 0:
            raise ApiError(400, "无效的 Content-Length")
        if length > MAX_BODY:
            raise ApiError(413, f"请求体超过 {MAX_BODY // 1048576}MB")
        return self.rfile.read(length) if length else b""

    def json_body(self, raw: bytes) -> dict:
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ApiError(400, "请求体不是合法 JSON") from exc
        if not isinstance(data, dict):
            raise ApiError(400, "请求体必须是 JSON 对象")
        return data

    # ── dispatch ──────────────────────────────────────────────────────

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def do_PATCH(self) -> None:
        self._dispatch("PATCH")

    def _dispatch(self, method: str) -> None:
        path, q = self.parts()
        try:
            raw = self.read_body() if method in {"POST", "DELETE", "PATCH"} else b""
            if path == "/healthz":
                return self.send_json(200, {"ok": True, "backend": "colab", "version": VERSION})
            if path == "/login":
                return self.route_login(method, raw)
            if path == "/logout":
                return self.redirect("login", {"Set-Cookie": f"{COOKIE}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0"})
            if not self.authed():
                if path.startswith("/api/"):
                    return self.send_json(401, {"error": "需要登录"})
                return self.redirect("login")
            if path == "/" and method == "GET":
                return self.send_html(200, PAGE_HTML)
            if path.startswith("/api/"):
                return self.route_api(method, path, q, raw)
            raise ApiError(404, "not found")
        except ApiError as exc:
            self.send_json(exc.code, {"error": exc.msg})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # pragma: no cover - last resort
            LOG(f"接口异常 {method} {path}: {exc}")
            try:
                self.send_json(500, {"error": f"服务器内部错误：{exc}"})
            except Exception:
                pass

    def route_login(self, method: str, raw: bytes) -> None:
        if method == "GET":
            return self.send_html(200, LOGIN_HTML % "")
        ip = self.client_ip()
        if _login_blocked(ip):
            return self.send_html(429, LOGIN_HTML % "尝试次数过多，请 10 分钟后再试")
        form = parse_qs(raw.decode(errors="replace"))
        password = (form.get("password") or [""])[0]
        if not hmac.compare_digest(password.encode(), SECRET["password"].encode()):
            _login_failed(ip)
            return self.send_html(401, LOGIN_HTML % "密码不对")
        self.redirect("./", {"Set-Cookie": f"{COOKIE}={SECRET['token']}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000"})

    # ── API ───────────────────────────────────────────────────────────

    def route_api(self, method: str, path: str, q: dict, raw: bytes) -> None:
        seg = path.split("/")[2:]  # after /api
        head = seg[0] if seg else ""

        if head == "config" and method == "GET":
            return self.send_json(200, config_payload())

        if head == "storage" and method == "GET":
            return self.send_json(200, STORE.storage_stats())

        if head == "status" and method == "GET":
            try:
                since = int(q.get("log_since") or 0)
            except ValueError:
                since = 0
            logs, seq = LOG.since(since)
            payload = STUDIO.snapshot()
            try:
                colab_rep = COLAB.status_report(blocking=False)
            except TypeError:
                # Compatible with staging fake backends whose status_report only takes (force=False)
                colab_rep = COLAB.status_report()
            payload.update({
                "logs": logs,
                "log_seq": seq,
                "gallery_rev": STORE.rev,
                "latest": STORE.latest(),
                "references": STUDIO.refs_report(),
                "recent_models": STUDIO.recent_models(),
                "comfy_presets": STUDIO.comfy_presets(),
                "proxy": STUDIO.proxy_report(),
                "colab": colab_rep,
                "server_time": int(time.time()),
            })
            return self.send_json(200, payload)

        if head == "models" and seg[1:] == ["recent"]:
            if method == "GET":
                return self.send_json(200, {"recent_models": STUDIO.recent_models()})
            if method == "POST":
                body = self.json_body(raw)
                raw_model = str(body.get("model") or "").strip()
                if not raw_model:
                    raise ApiError(400, "请先填写模型名称或 Hugging Face 仓库 ID")
                try:
                    items = STUDIO.add_recent_model(raw_model)
                except ValueError as exc:
                    raise ApiError(400, str(exc)) from exc
                return self.send_json(200, {"ok": True, "recent_models": items})
            if method == "DELETE":
                body = self.json_body(raw)
                raw_model = str(body.get("model") or q.get("model") or "").strip()
                if not raw_model:
                    raise ApiError(400, "缺少要移除的 model")
                return self.send_json(200, {"ok": True, "recent_models": STUDIO.remove_recent_model(raw_model)})
            raise ApiError(405, "method not allowed")

        if head == "settings" and method == "POST":
            body = self.json_body(raw)
            out = {}
            if "idle_minutes" in body:
                try:
                    raw_idle = body["idle_minutes"]
                    if isinstance(raw_idle, bool):
                        raise ValueError("bool")
                    out["idle_minutes"] = STUDIO.set_idle_minutes(int(raw_idle))
                except (TypeError, ValueError) as exc:
                    raise ApiError(400, "idle_minutes 必须是整数") from exc
            return self.send_json(200, {"ok": True, **out})

        if head == "prompt" and method == "POST":
            body = self.json_body(raw)
            text = str(body.get("text") or "").strip()
            if not text or len(text) > 2000:
                raise ApiError(400, "请描述想生成的内容（不超过 2000 字）")
            mode = "video" if body.get("mode") == "video" else "image"
            try:
                ref_count = int(body.get("ref_count") or 0)
            except (TypeError, ValueError):
                ref_count = 0
            try:
                prompt = STUDIO.write_prompt(text, mode=mode, editing=_bool(body.get("editing")), ref_count=ref_count)
            except RuntimeError as exc:
                raise ApiError(502, str(exc)) from exc
            return self.send_json(200, {"prompt": prompt})

        if head == "generate" and method == "POST":
            if not COLAB.has_credentials():
                raise ApiError(400, "请先在「设置」里完成 Google Colab 授权")
            try:
                payload = normalize_job(self.json_body(raw))
                jobs = STUDIO.enqueue(payload)
            except ValueError as exc:
                raise ApiError(400, str(exc)) from exc
            except RuntimeError as exc:
                raise ApiError(409, str(exc)) from exc
            return self.send_json(202, {"ok": True, "jobs": jobs})

        if head == "queue":
            if len(seg) == 1 and method == "GET":
                snap = STUDIO.snapshot()
                return self.send_json(200, {"current": snap["current"], "queue": snap["queue"], "history": snap["history"]})
            if len(seg) == 2 and seg[1] == "clear" and method == "POST":
                return self.send_json(200, {"ok": True, "removed": STUDIO.clear_queue()})
            if len(seg) == 2 and method == "DELETE" or (len(seg) == 3 and seg[2] == "cancel" and method == "POST"):
                if not STUDIO.remove_queued(seg[1]):
                    raise ApiError(404, "队列里没有这个任务（可能已开始运行，请用 /api/stop）")
                return self.send_json(200, {"ok": True})

        if head == "stop" and method == "POST":
            body = self.json_body(raw)
            STUDIO.cancel_current(clear_queue=_bool(body.get("clear_queue")))
            return self.send_json(200, {"ok": True})

        if head == "release" and method == "POST":
            threading.Thread(target=STUDIO.release_all, daemon=True).start()
            return self.send_json(200, {"ok": True})

        if head == "rounds":
            return self.route_rounds(method, seg, q, raw)
        if head == "trash":
            return self.route_trash(method, seg, q, raw)

        if head in {"reference", "last-frame"}:
            slot = "last" if head == "last-frame" or q.get("slot") == "last" else "first"
            ref_id = str(q.get("id") or "").strip()
            if method == "GET":
                f = STUDIO.ref_item_file(ref_id) if (ref_id and slot != "last") else STUDIO.ref_file(slot)
                if not f or not f.exists():
                    raise ApiError(404, "还没有设置")
                head_bytes = f.read_bytes()[:12]
                ctype = "image/png" if head_bytes.startswith(b"\x89PNG") else "image/webp" if head_bytes.startswith(b"RIFF") else "image/jpeg"
                return self.send_file(f, ctype)
            if method == "DELETE":
                if ref_id and slot != "last":
                    if not STUDIO.remove_ref(ref_id):
                        raise ApiError(404, "未找到该参考图")
                else:
                    STUDIO.clear_ref(slot)
                return self.send_json(200, {"ok": True, "references": STUDIO.refs_report()})
            if method == "POST":
                if len(raw) < 32 or len(raw) > LIMITS["upload_max_mb"] * 1048576:
                    raise ApiError(400, f"图片为空或超过 {LIMITS['upload_max_mb']}MB")
                if not (raw.startswith(b"\x89PNG") or raw.startswith(b"\xff\xd8") or (raw.startswith(b"RIFF") and raw[8:12] == b"WEBP")):
                    raise ApiError(400, "只接受 PNG、JPEG 或 WebP 图片")
                try:
                    if slot == "last":
                        STUDIO.set_ref("last", raw, "upload")
                        item_id = ""
                    elif _bool(q.get("append")):
                        item = STUDIO.add_ref(raw, "upload")
                        item_id = item["id"]
                    elif ref_id:
                        item = STUDIO.replace_ref(ref_id, raw, "upload")
                        item_id = item["id"]
                    else:
                        STUDIO.set_ref("first", raw, "upload")
                        items = STUDIO.refs_report().get("items") or []
                        item_id = items[0]["id"] if items else ""
                except ValueError as exc:
                    raise ApiError(400, str(exc)) from exc
                return self.send_json(200, {
                    "ok": True,
                    "slot": slot,
                    "id": item_id,
                    "bytes": len(raw),
                    "references": STUDIO.refs_report(),
                })

        if head == "use-latest-image" and method == "POST":
            latest = STORE.latest("image")
            if not latest:
                raise ApiError(400, "还没有生成过图片")
            STUDIO.use_round(latest["id"], "first")
            return self.send_json(200, {"ok": True, "id": latest["id"]})

        if head == "image" and method == "GET":
            img = OUT_DIR / "latest.png"
            if not img.exists():
                raise ApiError(404, "还没有图片")
            return self.send_file(img, "image/png")

        if head == "colab":
            return self.route_colab(method, seg, raw)

        if head == "proxy":
            if len(seg) == 1:
                if method == "GET":
                    return self.send_json(200, STUDIO.proxy_report())
                if method == "POST":
                    body = self.json_body(raw)
                    try:
                        rep = STUDIO.set_proxy(
                            active=body.get("active") if "active" in body else None,
                            custom_url=body.get("custom_url") if "custom_url" in body else None,
                        )
                    except ValueError as exc:
                        raise ApiError(400, str(exc)) from exc
                    return self.send_json(200, {"ok": True, **rep})
                raise ApiError(405, "method not allowed")
            if seg[1:] == ["test"] and method == "POST":
                body = self.json_body(raw)
                try:
                    res = STUDIO.test_proxy(body.get("profile"))
                except ValueError as exc:
                    raise ApiError(400, str(exc)) from exc
                return self.send_json(200, res)
            raise ApiError(404, "not found")

        if head == "comfy":
            if seg[1:] == ["parse-link"] and method == "POST":
                body = self.json_body(raw)
                raw_url = body.get("url") if "url" in body else body
                label = str(body.get("label") or "模型链接").strip()[:30]
                try:
                    spec = parse_model_link(raw_url, label)
                except ValueError as exc:
                    raise ApiError(400, str(exc)) from exc
                return self.send_json(200, {"ok": True, "spec": spec})
            if seg[1:] == ["presets"]:
                if method == "GET":
                    return self.send_json(200, {
                        "presets": STUDIO.comfy_presets(),
                        "builtin_presets": COMFY_BUILTIN_PRESETS,
                    })
                if method == "POST":
                    try:
                        preset, all_presets = STUDIO.save_comfy_preset(self.json_body(raw))
                    except ValueError as exc:
                        raise ApiError(400, str(exc)) from exc
                    return self.send_json(200, {"ok": True, "preset": preset, "presets": all_presets})
                raise ApiError(405, "method not allowed")
            if len(seg) == 3 and seg[1] == "presets" and method == "DELETE":
                removed, all_presets = STUDIO.delete_comfy_preset(seg[2])
                if not removed:
                    raise ApiError(404, "未找到该 ComfyUI 组合方案")
                return self.send_json(200, {"ok": True, "presets": all_presets})
            raise ApiError(404, "not found")

        if head == "hf" and seg[1:] == ["list-loras"] and method == "POST":
            body = self.json_body(raw)
            try:
                files = STUDIO.list_hf_safetensors(str(body.get("repo_id") or ""))
            except RuntimeError as exc:
                raise ApiError(400, str(exc)) from exc
            return self.send_json(200, {"files": files})

        raise ApiError(404, "not found")

    def route_rounds(self, method: str, seg: list[str], q: dict, raw: bytes) -> None:
        # /api/rounds
        if len(seg) == 1:
            if method == "GET":
                starred = None
                if q.get("starred") in {"1", "true"}:
                    starred = True
                elif q.get("starred") in {"0", "false"}:
                    starred = False
                try:
                    offset = max(0, int(q.get("offset") or 0))
                    limit = max(0, min(1000, int(q.get("limit") or 0)))
                except ValueError as exc:
                    raise ApiError(400, "offset / limit 必须是整数") from exc
                return self.send_json(200, STORE.list(
                    kind=q.get("kind", ""), starred=starred, q=q.get("q", "").strip(),
                    order=q.get("order", "desc"), offset=offset, limit=limit,
                ))
            raise ApiError(405, "method not allowed")

        action = seg[1]
        # /api/rounds/delete  /api/rounds/star  /api/rounds/cleanup
        if action == "delete" and method == "POST":
            body = self.json_body(raw)
            return self.send_json(200, STORE.delete(_ids(body), permanent=_bool(body.get("permanent"))))
        if action == "star" and method == "POST":
            body = self.json_body(raw)
            starred = _bool(body.get("starred", True))
            done = [rid for rid in _ids(body) if STORE.set_star(rid, starred)]
            return self.send_json(200, {"ok": True, "updated": done, "starred": starred})
        if action == "cleanup" and method == "POST":
            body = self.json_body(raw)
            try:
                days = float(body["older_than_days"]) if body.get("older_than_days") not in (None, "") else None
                keep = int(body["keep_latest"]) if body.get("keep_latest") not in (None, "") else None
                max_mb = float(body["max_mb"]) if body.get("max_mb") not in (None, "") else None
            except (TypeError, ValueError) as exc:
                raise ApiError(400, "older_than_days / keep_latest / max_mb 必须是数字") from exc
            if days is None and keep is None and max_mb is None:
                raise ApiError(400, "至少指定 older_than_days、keep_latest 或 max_mb 之一")
            if (days is not None and days < 0) or (keep is not None and keep < 0) or (max_mb is not None and max_mb < 0):
                raise ApiError(400, "参数不能为负数")
            kind = body.get("kind") if body.get("kind") in {"image", "video"} else ""
            plan = STORE.cleanup_plan(days, keep, kind=kind, include_starred=_bool(body.get("include_starred")), max_mb=max_mb)
            ids = [i["id"] for i in plan]
            result = {
                "dry_run": _bool(body.get("dry_run")),
                "matched": ids,
                "count": len(ids),
                "bytes": sum(i["bytes"] for i in plan),
            }
            if not result["dry_run"] and ids:
                res = STORE.delete(ids, permanent=_bool(body.get("permanent")))
                result.update({"deleted": res["deleted"], "permanent": res["permanent"]})
            return self.send_json(200, result)

        rid = action
        if not STORE.valid_id(rid):
            raise ApiError(404, "作品不存在")
        sub = seg[2] if len(seg) > 2 else ""

        if method == "DELETE" and not sub:
            body = self.json_body(raw)
            res = STORE.delete([rid], permanent=_bool(q.get("permanent") or body.get("permanent")))
            if not res["deleted"]:
                raise ApiError(404, "作品不存在")
            return self.send_json(200, res)
        if sub == "delete" and method == "POST":
            body = self.json_body(raw)
            res = STORE.delete([rid], permanent=_bool(body.get("permanent")))
            if not res["deleted"]:
                raise ApiError(404, "作品不存在")
            return self.send_json(200, res)
        if method == "GET" and not sub:
            found = STORE.media_path(rid)
            if not found:
                raise ApiError(404, "作品不存在")
            kind, fpath = found
            ext = "mp4" if kind == "video" else "png"
            return self.send_file(
                fpath, "video/mp4" if kind == "video" else "image/png",
                cache="private, max-age=31536000, immutable",
                download=f"colab-studio-{rid}.{ext}" if _bool(q.get("download")) else "",
            )
        if method == "GET" and sub == "thumb":
            t = STORE.thumb_path(rid)
            if not t:
                raise ApiError(404, "没有缩略图")
            return self.send_file(t, "image/jpeg", cache="private, max-age=31536000, immutable")
        if method == "GET" and sub == "meta":
            item = STORE.get(rid)
            if not item:
                raise ApiError(404, "作品不存在")
            return self.send_json(200, item)
        if sub == "star" and method in {"POST", "PATCH"}:
            body = self.json_body(raw)
            if not STORE.set_star(rid, _bool(body.get("starred", True))):
                raise ApiError(404, "作品不存在")
            return self.send_json(200, {"ok": True, "id": rid, "starred": _bool(body.get("starred", True))})
        if sub == "use" and method == "POST":
            body = self.json_body(raw)
            slot = "last" if body.get("slot") == "last" or q.get("slot") == "last" else "first"
            append = _bool(body.get("append") or q.get("append"))
            try:
                STUDIO.use_round(rid, slot, append=append)
            except (RuntimeError, ValueError) as exc:
                raise ApiError(400, str(exc)) from exc
            return self.send_json(200, {"ok": True, "slot": slot, "references": STUDIO.refs_report()})
        raise ApiError(404, "not found")

    def route_trash(self, method: str, seg: list[str], q: dict, raw: bytes) -> None:
        if len(seg) == 1 and method == "GET":
            return self.send_json(200, STORE.trash_list())
        action = seg[1] if len(seg) > 1 else ""
        if action == "restore" and method == "POST":
            return self.send_json(200, STORE.restore(_ids(self.json_body(raw))))
        if action == "purge" and method == "POST":
            body = self.json_body(raw)
            if _bool(body.get("all")):
                return self.send_json(200, STORE.purge(None))
            return self.send_json(200, STORE.purge(_ids(body)))
        if STORE.valid_id(action) and method == "GET":
            sub = seg[2] if len(seg) > 2 else ""
            if sub == "thumb":
                t = STORE.thumb_path(action, trash=True)
                if not t:
                    raise ApiError(404, "没有缩略图")
                return self.send_file(t, "image/jpeg")
            found = STORE.media_path(action, trash=True)
            if not found:
                raise ApiError(404, "回收站里没有这个作品")
            return self.send_file(found[1], "video/mp4" if found[0] == "video" else "image/png")
        raise ApiError(404, "not found")

    def route_colab(self, method: str, seg: list[str], raw: bytes) -> None:
        sub = "/".join(seg[1:])
        if sub == "status" and method == "GET":
            try:
                return self.send_json(200, COLAB.status_report(force=True, blocking=True))
            except TypeError:
                return self.send_json(200, COLAB.status_report(force=True))
        if method != "POST":
            raise ApiError(405, "method not allowed")
        if sub == "auth/start":
            try:
                return self.send_json(200, {"auth_url": COLAB.start_oauth()})
            except Exception as exc:
                raise ApiError(500, str(exc)) from exc
        if sub == "auth/complete":
            body = self.json_body(raw)
            try:
                rep = COLAB.complete_oauth(str(body.get("code") or ""))
                STUDIO.resume_queue()
                return self.send_json(200, rep)
            except Exception as exc:
                raise ApiError(400, str(exc)) from exc
        if sub == "auth/logout":
            COLAB.logout()
            return self.send_json(200, {"ok": True})
        if sub == "hf-token":
            body = self.json_body(raw)
            tok = str(body.get("token") or "").strip()
            if tok and not re.fullmatch(r"hf_[A-Za-z0-9]{20,}", tok):
                raise ApiError(400, "HF Token 格式不对（应以 hf_ 开头）")
            COLAB.set_hf_token(tok)
            COLAB.invalidate_status()
            return self.send_json(200, {"ok": True, "set": bool(tok)})
        raise ApiError(404, "not found")


def housekeeping() -> None:
    while True:
        STORE.auto_purge()
        time.sleep(3600)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    boot_message(COLAB, STUDIO, LOG)
    threading.Thread(target=housekeeping, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True

    def _handle_stop(signum, _frame) -> None:
        LOG(f"收到停止信号 ({signum})，保存队列状态并退出…")
        STUDIO.shutdown()
        threading.Thread(target=server.shutdown, daemon=True).start()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handle_stop)
        except (ValueError, OSError):
            pass

    LOG(f"Colab Studio {VERSION} listening on {HOST}:{PORT}")
    try:
        server.serve_forever()
    finally:
        STUDIO.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
