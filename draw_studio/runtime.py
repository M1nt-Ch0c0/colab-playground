"""Create the services and own one execution lifecycle per data volume."""
from __future__ import annotations

import asyncio
import os
import sqlite3
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, closing
from dataclasses import dataclass, field
from pathlib import Path

from .colab.client import ColabBackend
from .gallery import Store
from .generation.studio import Studio
from .logs import LogBuffer
from .workflows.engine import WorkflowEngine


@dataclass
class Runtime:
    root: Path
    secret: dict[str, str] = field(repr=False)
    log: LogBuffer
    colab: ColabBackend
    store: Store
    studio: Studio
    workflows: WorkflowEngine

    @classmethod
    def open(cls, root: Path) -> Runtime:
        secret_path = Path(os.environ.get("QP_SECRET", root / "secret.env"))
        secret = {}
        for line in secret_path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                secret[key.strip()] = value.strip()
        if not secret.get("password") or not secret.get("token"):
            raise ValueError("secret.env 需要 password 和 token")
        log = LogBuffer()
        colab = ColabBackend(root, log)
        store = Store(root / "out", log)
        studio = Studio(root, secret, colab, store, log, int(os.environ.get("QP_IDLE_SECONDS", "600")))
        return cls(root, secret, log, colab, store, studio, WorkflowEngine(root, studio, store, log))

    def recover(self) -> None:
        rep = self.colab.status_report(force=True)
        if rep.get("authed") and rep.get("ok"):
            self.log(f"Colab 已授权（{rep.get('email') or 'ok'}），余额 {rep.get('balance')} CU，当前运行实例 {len(rep.get('sessions') or [])} 台")
            if rep.get("any_running"):
                self.studio.active_gpu = ", ".join(s["gpu"] for s in rep.get("sessions") or [])
                self.studio.set_phase("ready")
                self.studio.arm_idle()
        else:
            self.log("尚未授权 Google Colab，打开网页右上角「设置」完成授权")
        self.studio.recover()


@asynccontextmanager
async def open_runtime(data: Path, services: Runtime | None = None) -> AsyncIterator[Runtime]:
    data.mkdir(parents=True, exist_ok=True)
    # Recovery and queue ownership must happen once per data volume, including during a rollout.
    with closing(sqlite3.connect(data / ".studio.lock", timeout=0)) as owner:
        try:
            owner.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            if exc.sqlite_errorcode not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise
            raise RuntimeError("数据卷已有 ColabReel 执行进程，请使用一个 worker") from exc
        s = services or Runtime.open(data)
        await asyncio.to_thread(s.recover)
        stop = threading.Event()

        def housekeeping():
            while not stop.is_set():
                s.store.auto_purge()
                stop.wait(3600)

        cleaner = threading.Thread(target=housekeeping, daemon=True)
        cleaner.start()
        try:
            yield s
        finally:
            stop.set()
            await asyncio.to_thread(cleaner.join)
            s.studio.shutdown()
