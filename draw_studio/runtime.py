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
from .workflows.agent_plugins import prune_profiles
from .workflows.copilot import HarnessSessions
from .workflows.engine import WorkflowEngine
from .workflows.harness_errors import HarnessError
from .workflows.harness_store import HarnessStore
from .workflows.operation_service import Operations


@dataclass
class Runtime:
    root: Path
    secret: dict[str, str] = field(repr=False)
    log: LogBuffer
    colab: ColabBackend
    store: Store
    studio: Studio
    workflows: WorkflowEngine
    harness_sessions: HarnessSessions = field(default_factory=HarnessSessions, repr=False)
    harness_store: HarnessStore = field(init=False, repr=False)
    operations: Operations = field(init=False, repr=False)

    def __post_init__(self):
        self.harness_store = HarnessStore(self.root)
        self.workflows.harness_store = self.harness_store
        self.operations = Operations(self.harness_store, self.studio)
        self.studio.on_job_finished = self.operations.record_terminal

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

    def shutdown(self) -> None:
        try:
            self.harness_sessions.shutdown()
        finally:
            try:
                with self.studio._lock:
                    self.studio.on_job_finished = None
                self.workflows.detach_harness()
            finally:
                self.studio.shutdown()


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
        try:
            await asyncio.to_thread(s.recover)
        except BaseException:
            await asyncio.to_thread(s.shutdown)
            raise
        stop = threading.Event()

        def housekeeping():
            try:
                prune_profiles(s.root)
            except (OSError, HarnessError) as exc:
                s.log(f"助手插件目录未能清理 ({type(exc).__name__})")
            while not stop.is_set():
                s.store.auto_purge()
                try:
                    s.harness_sessions.prune_drafts(s.root, lambda key: (s.workflows.runs_dir / key / "run.json").is_file())
                except OSError as exc:
                    s.log(f"助手草稿对话未能清理 ({type(exc).__name__})")
                try:
                    s.harness_store.prune_telemetry()
                    s.harness_store.prune_expired()
                except sqlite3.Error as exc:
                    s.log(f"助手统计未能清理 ({type(exc).__name__})")
                stop.wait(3600)

        cleaner = threading.Thread(target=housekeeping, daemon=True)
        cleaner.start()
        try:
            yield s
        finally:
            stop.set()
            await asyncio.to_thread(cleaner.join)
            await asyncio.to_thread(s.shutdown)
