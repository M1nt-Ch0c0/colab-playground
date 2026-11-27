"""Saved outbound proxy routes and private network handling for model requests."""
from __future__ import annotations

import ipaddress
import json
import os
import re
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import requests

PROXY_ENV = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
BYPASS_ENV = ("NO_PROXY", "no_proxy")


def is_local_or_private_host(host: str) -> bool:
    h = host.strip().lower().strip("[]")
    if h in {"localhost", "host.docker.internal", "gateway.docker.internal"} or h.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


class ProxyNotFound(ValueError):
    pass


@dataclass(frozen=True)
class Route:
    id: str
    label: str
    url: str = field(repr=False)

    def __post_init__(self):
        try:
            u = urlsplit(self.url)
            valid = (u.scheme in {"http", "https", "socks5", "socks5h"} and u.hostname and
                     u.path in ("", "/") and not u.query and not u.fragment and
                     not any(ch.isspace() or ord(ch) < 32 for ch in self.url))
            _ = u.port
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("请输入有效的 HTTP、HTTPS、SOCKS5 或 SOCKS5H 代理地址")
        if not self.label.strip() or len(self.label) > 80 or not self.label.isprintable():
            raise ValueError("代理名称须为 1 到 80 个字符")

    def public(self) -> dict:
        u = urlsplit(self.url)
        host = f"[{u.hostname}]" if ":" in u.hostname else u.hostname
        auth = "***@" if u.username is not None or u.password is not None else ""
        port = f":{u.port}" if u.port is not None else ""
        return {"id": self.id, "label": self.label, "configured": True, "hint": "",
                "masked": f"{u.scheme}://{auth}{host}{port}"}


class ProxyProfiles:
    def __init__(self, root: Path, secret: dict, queue_path: Path, *, on_change: Callable[[], None],
                 log: Callable[[str], None]):
        directory = root / "private"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = directory / "proxies.json"
        self._lock = threading.RLock()
        self._on_change = on_change
        self._log = log
        self._environment = {name: os.environ.get(name) for name in (*PROXY_ENV, *BYPASS_ENV)}
        self._last_test: dict | None = None
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._routes = {row["id"]: Route(**row) for row in data["profiles"]}
            self._active = data["active"]
            if self._active and self._active not in self._routes:
                raise ValueError("代理配置中的当前线路不存在")
            self.path.chmod(0o600)
        else:
            self._routes, self._active = self._import_routes(root, secret, queue_path)
            self._write(self._routes, self._active)
        if self._active:
            self._apply(self._routes[self._active].url)

    def _import_routes(self, root: Path, secret: dict, queue_path: Path) -> tuple[dict[str, Route], str]:
        routes = {}
        for key, raw in secret.items():
            if not raw or (key != "proxy_url" and not key.startswith("proxy_url_")):
                continue
            pid = "default" if key == "proxy_url" else key.removeprefix("proxy_url_")
            if not re.fullmatch(r"[a-z0-9_-]{1,64}", pid) or pid in routes:
                raise ValueError("旧代理配置中有重复或无效的线路 ID")
            routes[pid] = Route(pid, "默认代理" if pid == "default" else pid, raw.strip())
        previous = root / "proxy_custom.txt"
        if previous.is_file() and (value := previous.read_text(encoding="utf-8").strip()):
            routes["custom"] = Route("custom", "自定义代理", value)
        selected = ""
        if routes and queue_path.is_file():
            try:
                state = json.loads(queue_path.read_text(encoding="utf-8"))
                if isinstance(state, dict):
                    selected = state.get("proxy_profile") or ""
            except (OSError, ValueError):
                self._log("旧代理选择读取失败，使用第一条已导入线路")
        return routes, selected if selected in routes else next(iter(routes), "")

    def _write(self, routes: dict[str, Route], active: str) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".proxies-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"profiles": [asdict(r) for r in routes.values()], "active": active}, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            Path(tmp).unlink(missing_ok=True)

    def _apply(self, url: str) -> None:
        if not url:
            for name, value in self._environment.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            return
        for name in PROXY_ENV:
            os.environ[name] = url
        bypass = self._environment["NO_PROXY"] or self._environment["no_proxy"] or ""
        hosts = [s.strip() for s in bypass.split(",") if s.strip()]
        hosts.extend(("localhost", "127.0.0.1", "::1", "host.docker.internal", "gateway.docker.internal"))
        for name in BYPASS_ENV:
            os.environ[name] = ",".join(dict.fromkeys(hosts))

    def close(self) -> None:
        with self._lock:
            if self._active:
                self._apply("")

    def state(self) -> dict:
        with self._lock:
            return {"active": self._active, "profiles": [r.public() for r in self._routes.values()],
                    "last_test": dict(self._last_test) if self._last_test else None}

    def _commit(self, routes: dict[str, Route], active: str, *, notify: bool = True) -> dict:
        if active and active not in routes:
            raise ProxyNotFound("所选代理线路不存在")
        before = self._routes.get(self._active)
        after = routes.get(active)
        if self._active == active and self._routes == routes:
            return self.state()
        self._write(routes, active)
        if self._last_test:
            pid = self._last_test["profile"]
            if self._routes.get(pid) != routes.get(pid):
                self._last_test = None
        self._routes, self._active = routes, active
        if (before.url if before else None) != (after.url if after else None):
            self._apply(after.url if after else "")
            if notify:
                self._on_change()
                self._log(f"出站线路已切换为{after.label if after else '系统网络'}")
        return self.state()

    def save(self, label: str, url: str, profile_id: str | None = None) -> dict:
        with self._lock:
            if profile_id is None:
                pid = "px_" + uuid.uuid4().hex
            else:
                pid = profile_id
                if pid not in self._routes:
                    raise ProxyNotFound("要编辑的代理线路不存在")
            value = url.strip()
            if not value and pid in self._routes:
                value = self._routes[pid].url
            route = Route(pid, label.strip(), value)
            return self._commit({**self._routes, pid: route}, self._active if self._routes else pid)

    def delete(self, profile_id: str) -> dict:
        with self._lock:
            if profile_id not in self._routes:
                raise ProxyNotFound("要删除的代理线路不存在")
            routes = dict(self._routes)
            del routes[profile_id]
            active = next(iter(routes), "") if self._active == profile_id else self._active
            return self._commit(routes, active)

    def configure(self, active: str | None, custom_url: str | None = None) -> dict:
        """Select a route; accept the original single-custom-URL request from existing clients."""
        with self._lock:
            routes = dict(self._routes)
            if custom_url is not None:
                if custom_url.strip():
                    routes["custom"] = Route("custom", "自定义代理", custom_url.strip())
                else:
                    routes.pop("custom", None)
            target = active if active is not None else self._active
            if active is None and target and target not in routes:
                target = next(iter(routes), "")
            return self._commit(routes, target)

    def polling_routes(self, *, all_routes: bool) -> list[tuple[str, str]]:
        with self._lock:
            if not all_routes:
                return [(self._active, self._routes[self._active].label)] if self._active else []
            rows = sorted(self._routes.values(), key=lambda r: r.id != self._active)
            return [(r.id, r.label) for r in rows]

    def use_for_polling(self, pid: str) -> None:
        with self._lock:
            self._commit(self._routes, pid, notify=False)

    def test(self, profile_id: str | None = None) -> dict:
        with self._lock:
            pid = profile_id or self._active
            route = self._routes.get(pid)
            if not route:
                raise ProxyNotFound("请先选择已保存的代理线路")
        start = time.monotonic()
        loc, colo, error = "", "", ""
        try:
            with requests.Session() as session:
                session.trust_env = False
                with session.get("https://www.cloudflare.com/cdn-cgi/trace", timeout=12, allow_redirects=False,
                                 proxies={"http": route.url, "https": route.url}) as response:
                    if response.status_code != 200:
                        error = f"代理测试返回 HTTP {response.status_code}"
                    else:
                        trace = dict(line.split("=", 1) for line in response.text.splitlines() if "=" in line)
                        loc, colo = trace.get("loc", ""), trace.get("colo", "")
                        if not (re.fullmatch(r"[A-Z]{2}", loc) and re.fullmatch(r"[A-Z0-9]{3,6}", colo)):
                            loc, colo, error = "", "", "代理测试响应格式无效"
        except requests.RequestException:
            error = "代理连接失败或超时，请检查地址与凭据"
        result = {"profile": pid, "ok": not error, "loc": loc, "colo": colo,
                  "ms": round((time.monotonic() - start) * 1000), "at": int(time.time()), "error": error}
        with self._lock:
            if self._routes.get(pid) == route:
                self._last_test = result
        return result
