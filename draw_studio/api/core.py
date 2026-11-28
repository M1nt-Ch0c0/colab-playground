from __future__ import annotations

import hmac
import re
import threading
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import FileResponse, JSONResponse, Response

from ..runtime import Runtime
from ..generation.catalog import LIMITS
from ..workflows.harness_errors import HarnessError, is_agent_path

COOKIE = "qp_auth"
MAX_BODY = 16 * 1024 * 1024
IMMUTABLE = "private, max-age=31536000, immutable"


def runtime(request: Request) -> Runtime:
    return request.app.state.runtime


State = Annotated[Runtime, Depends(runtime)]


class LoginAttempts:
    def __init__(self):
        self.failures: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    def check(self, ip: str, password: str, expected: str):
        now = time.monotonic()
        with self.lock:
            hits = [at for at in self.failures.get(ip, []) if at > now - 600]
            if len(hits) >= 8:
                raise HTTPException(429, "尝试次数过多，请 10 分钟后再试")
            if not hmac.compare_digest(password.encode(), expected.encode()):
                self.failures[ip] = [*hits, now]
                raise HTTPException(401, "密码不对")
            if hits:
                self.failures[ip] = hits
            else:
                self.failures.pop(ip, None)


def authenticated(request: Request) -> bool:
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else request.cookies.get(COOKIE, "")
    return hmac.compare_digest(token.encode(), runtime(request).secret["token"].encode())


class HttpBoundary:
    """Apply authentication and byte limits before the framework parses the body."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        path = scope["path"].removeprefix(scope.get("root_path", "")).rstrip("/") or "/"

        def failure(message, status):
            body = HarnessError("invalid_argument", status, message).body() if is_agent_path(path) else {"error": message}
            return JSONResponse(body, status)

        async def send_headers(message):
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers.setdefault("Cache-Control", "no-store")
                response_headers["X-Content-Type-Options"] = "nosniff"
                response_headers["Referrer-Policy"] = "same-origin"
                response_headers["X-Frame-Options"] = "DENY"
            await send(message)

        if path.startswith("/api/") and path != "/api/login" and not authenticated(Request(scope)):
            return await failure("需要登录", 401)(scope, receive, send_headers)
        if scope["method"] in {"POST", "PATCH", "DELETE"}:
            media_upload = path in ("/api/video-reference", "/api/rounds/import") and scope["method"] == "POST"
            limit = LIMITS["video_upload_max_mb"] * 1048576 if media_upload else MAX_BODY
            try:
                length = int(headers.get("content-length", 0))
                if length < 0:
                    raise ValueError
            except ValueError:
                return await failure("无效的 Content-Length", 400)(scope, receive, send_headers)
            if length > limit:
                return await failure(f"请求体超过 {limit // 1048576}MB", 413)(scope, receive, send_headers)
            # Enforce the same limit for chunked requests as for Content-Length.
            received = 0
            async def bounded_receive():
                nonlocal received
                message = await receive()
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(413, f"请求体超过 {limit // 1048576}MB")
                return message
            return await self.app(scope, bounded_receive, send_headers)
        await self.app(scope, receive, send_headers)


def readable(router: APIRouter, path: str, **options):
    """GET with the same representation headers on HEAD, one OpenAPI operation."""
    def register(endpoint):
        router.head(path, include_in_schema=False)(endpoint)
        return router.get(path, **options)(endpoint)
    return register


IMAGE_BODY = {"requestBody": {"required": True, "content": {
    mime: {"schema": {"type": "string", "format": "binary"}} for mime in ("image/png", "image/jpeg", "image/webp")
}}}


def media_route(router: APIRouter, path: str, *types: str):
    content = {mime: {"schema": {"type": "string", "format": "binary"}} for mime in types}
    return readable(router, path, response_class=Response, responses={
        200: {"description": "媒体内容", "content": content},
        206: {"description": "请求的字节范围", "content": content},
        304: {"description": "缓存命中"}, 416: {"description": "无效的字节范围"},
    })


async def raw_body(request: Request) -> bytes:
    return await request.body()


Raw = Annotated[bytes, Depends(raw_body)]


def media_file(request: Request, path: Path | None, ctype: str, cache: str = "no-store",
              download: str | None = None) -> Response:
    if not path or not path.is_file():
        raise HTTPException(404, "文件不存在")
    stat = path.stat()
    etag = f'W/"{stat.st_size}-{stat.st_mtime_ns}"'
    headers = {"Cache-Control": cache, "ETag": etag}
    if not download and cache != "no-store" and etag in request.headers.get("if-none-match", "").split(", "):
        return Response(status_code=304, headers=headers)
    requested = request.headers.get("range", "")
    if requested.startswith("bytes="):
        # The public media API reports malformed and unsatisfiable byte ranges as 416.
        for spec in requested[6:].split(","):
            match = re.fullmatch(r"(\d*)-(\d*)", spec.strip())
            if match:
                first, last = match.groups()
                if first and int(first) < stat.st_size and (not last or int(first) <= int(last)):
                    continue
                if not first and last and int(last) > 0 and stat.st_size:
                    continue
            return Response(status_code=416, headers={"Content-Range": f"bytes */{stat.st_size}"})
    return FileResponse(path, media_type=ctype, headers=headers, filename=download, stat_result=stat)


def image_type(path: Path) -> str:
    with path.open("rb") as f:
        head = f.read(12)
    if head.startswith(b"\x89PNG"):
        return "image/png"
    return "image/webp" if head.startswith(b"RIFF") else "image/jpeg"


def flag(v) -> bool:
    return v.lower() in {"1", "true", "yes", "on"} if isinstance(v, str) else bool(v)
