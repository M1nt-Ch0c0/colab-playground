"""ColabReel ASGI application. Run python app.py to serve the built web client."""
from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, SecretStr
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from . import __version__
from .api import generation, library, llm, proxies, workflows
from .api.core import COOKIE, HttpBoundary, LoginAttempts, State, authenticated, media_file, readable
from .errors import LlmError, StateConflict
from .legacy_ui import LOGIN_HTML, PAGE_HTML
from .logs import redact_secrets
from .proxy import ProxyNotFound
from .runtime import Runtime, open_runtime
from .workflows.harness_errors import HarnessError, HarnessErrorBody, is_agent_path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Password(BaseModel):
    password: SecretStr


class Ok(BaseModel):
    ok: bool


class Assets(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code in {200, 206, 304} and re.search(r"-[\w-]{8,}\.\w+$", path):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def create_app(*, root: Path | None = None, dist: Path | None = None, services: Runtime | None = None) -> FastAPI:
    data = root or (services.root if services else Path(os.environ.get("QP_ROOT", PROJECT_ROOT)))
    web = dist or PROJECT_ROOT / "web" / "dist"
    attempts = LoginAttempts()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with open_runtime(data, services) as runtime:
            app.state.runtime = runtime
            yield

    app = FastAPI(title="ColabReel", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url="/api/openapi.json")
    app.add_middleware(HttpBoundary)

    @app.exception_handler(HarnessError)
    async def harness_error(request, exc):
        return JSONResponse(exc.body(), exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        if is_agent_path(request.scope["path"].removeprefix(request.scope.get("root_path", ""))):
            fields = list(dict.fromkeys(".".join(str(k) for k in e["loc"][1:]) for e in exc.errors()))
            return await harness_error(request, HarnessError("invalid_argument", details={"fields": fields}))
        fields = "、".join(dict.fromkeys(".".join(str(k) for k in e["loc"][1:]) or "请求体" for e in exc.errors()))
        return JSONResponse({"error": f"请求参数无效（{fields}）"}, 400)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        if is_agent_path(request.scope["path"].removeprefix(request.scope.get("root_path", ""))):
            code = "not_found" if exc.status_code == 404 else "invalid_argument"
            return JSONResponse(HarnessError(code, status=exc.status_code).body(), exc.status_code, headers=exc.headers)
        message = {404: "接口或文件不存在", 405: "请求方法不支持"}.get(exc.status_code, "请求失败")
        if exc.detail not in ("Not Found", "Method Not Allowed"):
            message = str(exc.detail)
        return JSONResponse({"error": message}, exc.status_code, headers=exc.headers)

    @app.exception_handler(LlmError)
    async def provider_error(request, exc):
        return JSONResponse({"error": str(exc)}, exc.status)

    @app.exception_handler(ProxyNotFound)
    async def proxy_missing(request, exc):
        return JSONResponse({"error": str(exc)}, 404)

    @app.exception_handler(ValueError)
    async def invalid_value(request, exc):
        if is_agent_path(request.scope["path"].removeprefix(request.scope.get("root_path", ""))):
            return await harness_error(request, HarnessError("invalid_argument"))
        return JSONResponse({"error": redact_secrets(str(exc))}, 400)

    @app.exception_handler(StateConflict)
    async def conflict(request, exc):
        return JSONResponse({"error": redact_secrets(str(exc))}, 409)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        request.app.state.runtime.log(f"接口异常 {request.method} {request.url.path} ({type(exc).__name__})")
        if is_agent_path(request.scope["path"].removeprefix(request.scope.get("root_path", ""))):
            return await harness_error(request, HarnessError("internal_error"))
        return JSONResponse({"error": "服务器内部错误"}, 500)

    @readable(app, "/healthz")
    def health(s: State):
        active = s.workflows.active_summary()
        running = bool(active and active["status"] == "running")
        snap = s.studio.snapshot()
        return {"ok": True, "backend": "colab", "version": __version__, "build_id": os.getenv("QP_BUILD_ID") or None,
                "workflow_running": running,
                "queue_len": len(snap["queue"]), "busy": bool(snap["current"] or snap["queue"] or running
                                                               or snap["phase"] in {"starting", "stopping"})}

    @readable(app, "/", include_in_schema=False)
    def index(request: Request):
        path = web / "index.html"
        if not path.is_file():
            raise HTTPException(503, "前端尚未构建，请在 web 目录运行 npm ci 和 npm run build")
        return media_file(request, path, "text/html")

    @readable(app, "/legacy", include_in_schema=False)
    def legacy(request: Request):
        return HTMLResponse(PAGE_HTML) if authenticated(request) else RedirectResponse("login", 302)

    def check_password(request, password, secret):
        # Uvicorn resolves forwarded client addresses only for trusted proxy peers.
        ip = request.client.host if request.client else "local"
        attempts.check(ip, password, secret["password"])

    def cookie(response, value, age):
        response.set_cookie(COOKIE, value, max_age=age, path="/", secure=True, httponly=True, samesite="lax")
        return response

    @app.post("/api/login", response_model=Ok)
    def login(body: Password, request: Request, s: State):
        check_password(request, body.password.get_secret_value(), s.secret)
        return cookie(JSONResponse({"ok": True}), s.secret["token"], 2592000)

    @app.post("/api/logout", response_model=Ok)
    def logout():
        return cookie(JSONResponse({"ok": True}), "", 0)

    @readable(app, "/login", include_in_schema=False)
    def login_page():
        return HTMLResponse(LOGIN_HTML % "")

    @app.post("/login", include_in_schema=False)
    async def legacy_login(request: Request):
        secret = request.app.state.runtime.secret
        raw = (await request.body()).decode(errors="replace")
        try:
            check_password(request, parse_qs(raw).get("password", [""])[0], secret)
        except HTTPException as exc:
            return HTMLResponse(LOGIN_HTML % exc.detail, status_code=exc.status_code)
        return cookie(RedirectResponse("./", 302), secret["token"], 2592000)

    @readable(app, "/logout", include_in_schema=False)
    def legacy_logout():
        return cookie(RedirectResponse("login", 302), "", 0)

    for module in (generation, llm, proxies, library, workflows):
        app.include_router(module.router)
    app.mount("/assets", Assets(directory=web / "assets", check_dir=False), name="assets")
    default_schema = app.openapi

    def openapi():
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = default_schema()
        components = schema["components"]
        # Request validation errors are serialized by invalid_request() above.
        for unused in ("HTTPValidationError", "ValidationError"):
            components["schemas"].pop(unused, None)
        components["securitySchemes"] = {
            "cookie": {"type": "apiKey", "in": "cookie", "name": COOKIE},
            "bearer": {"type": "http", "scheme": "bearer"},
        }
        components["schemas"]["ApiError"] = {
            "type": "object", "required": ["error"], "properties": {"error": {"type": "string"}},
        }
        components["schemas"]["HarnessError"] = HarnessErrorBody.model_json_schema()
        error = {"description": "中文错误说明", "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}},
        }}
        agent_error = {"description": "助手错误码", "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/HarnessError"}},
        }}
        for path, methods in schema["paths"].items():
            path_error = agent_error if is_agent_path(path) else error
            for method, op in methods.items():
                responses = op["responses"]
                if "422" in responses:
                    del responses["422"]
                    responses["400"] = path_error
                if path == "/api/workflows/runs/{run_id}" and method == "patch":
                    responses["409"] = {"description": "工作流状态或版本冲突", "content": {"application/json": {"schema": {
                        "anyOf": [{"$ref": "#/components/schemas/ApiError"}, {"$ref": "#/components/schemas/HarnessError"}],
                    }}}}
                if path.startswith("/api/"):
                    responses["default"] = path_error
                    if path != "/api/login":
                        op["security"] = [{"cookie": []}, {"bearer": []}]
        return schema

    app.openapi = openapi
    return app
