"""Publish private dsh profiles for the trusted in-app plugin."""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from deepseek_harness_runtime import resolve_bundled_launch_args

from .harness_errors import HarnessError

PACKAGE = "studio-shot-timing"
TOOL = "studio_shot_timing"
LABEL = "镜头计时尺"
SOURCE = Path(__file__).resolve().parent / "plugins" / "shot-timing"
MINIMAL_BUNDLE = "@deepseek-ai/dsh-sdk-minimal"
VERSION = re.compile(r"v-\d+-[a-f0-9]+")
PROFILE_LOCK = threading.Lock()
CHANGE_LOCK = threading.Lock()
_references: Counter[Path] = Counter()


@dataclass(frozen=True)
class Profile:
    version: str
    installed: bool
    enabled: bool


def profile_home(root):
    return Path(root).resolve() / "private" / "workflow-harness"


def private_dir(path: Path):
    path.mkdir(mode=0o700, exist_ok=True)
    path.chmod(0o700)
    return path


def write_private(path: Path, text: str):
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as pending:
        temporary = Path(pending.name)
        try:
            pending.write(text)
            pending.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def _directory(home, version):
    return home / "profiles" / version


def _read_active(home):
    try:
        raw = json.loads((home / "active.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise HarnessError("plugin_unavailable") from exc
    if (not isinstance(raw, dict) or not isinstance(raw.get("version"), str) or not VERSION.fullmatch(raw["version"])
            or type(raw.get("installed")) is not bool or type(raw.get("enabled")) is not bool):
        raise HarnessError("plugin_unavailable")
    return Profile(raw["version"], raw["installed"], raw["enabled"])


def _bundles(directory):
    path = directory / "package.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("dsh", {}).get("profile", {}).get("bundles", [])


def _legacy(home):
    installed = PACKAGE in _bundles(_directory(home, "sdk-minimal"))
    return Profile("", installed, installed and not (home / "timing.disabled").exists())


def _publish(home, profile):
    write_private(home / "active.json", json.dumps({
        "version": profile.version, "installed": profile.installed, "enabled": profile.enabled,
    }))


def _new_profile(home, installed, enabled):
    profile = Profile(f"v-{time.time_ns()}-{secrets.token_hex(4)}", installed, enabled)
    private_dir(_directory(home, profile.version))
    return profile


def _seed(directory, installed=False):
    manifest = {
        "name": "colabreel-workflow-profile", "private": True,
        "dependencies": {PACKAGE: f"file:{SOURCE}"} if installed else {},
        "dsh": {"profile": {"bundles": [MINIMAL_BUNDLE, PACKAGE] if installed else [MINIMAL_BUNDLE]}},
    }
    write_private(directory / "package.json", json.dumps(manifest))
    if installed:
        # This bundled package has no dependencies. Give each version a private copy.
        modules = private_dir(directory / "node_modules")
        package = private_dir(modules / PACKAGE)
        for file in ("index.mjs", "package.json", "cordis.patch.yml"):
            write_private(package / file, (SOURCE / file).read_text(encoding="utf-8"))


def _ensure_active(home):
    current = _read_active(home)
    if current is None:
        home.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        private_dir(home)
        private_dir(home / "profiles")
        legacy = _legacy(home)
        current = _new_profile(home, legacy.installed, legacy.enabled)
        directory = _directory(home, current.version)
        try:
            _seed(directory, legacy.installed)
            _publish(home, current)
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            raise
    return current


def inventory(root):
    from .agent_tools import TOOL_LABELS

    home = profile_home(root)
    current = _read_active(home) or _legacy(home)
    return {"builtin_tools": TOOL_LABELS, "plugin": {
        "id": PACKAGE, "name": LABEL, "version": "1.0.0", "description": "按镜头数和帧数算出片长",
        "tool": TOOL, "installed": current.installed, "enabled": current.enabled,
    }}


def active_version(root):
    current = _read_active(profile_home(root))
    return current.version if current else None


@contextmanager
def acquire_profile(root):
    home = profile_home(root)
    with PROFILE_LOCK:
        current = _ensure_active(home)
        directory = _directory(home, current.version)
        if not directory.is_dir():
            raise HarnessError("plugin_unavailable")
        _references[directory] += 1
    try:
        yield current
    finally:
        with PROFILE_LOCK:
            _references[directory] -= 1
            unused = not _references[directory]
            if unused:
                del _references[directory]
            retired = unused and active_version(root) != current.version
        if retired:
            shutil.rmtree(directory, ignore_errors=True)


def prune_profiles(root):
    home = profile_home(root)
    with CHANGE_LOCK:
        with PROFILE_LOCK:
            version = active_version(root)
            unused = [d for d in (home / "profiles").glob("v-*")
                      if VERSION.fullmatch(d.name) and d.name != version and not _references[d]]
        for directory in unused:
            shutil.rmtree(directory, ignore_errors=True)


def _install(home, profile):
    if not shutil.which("pnpm"):
        raise HarnessError("plugin_unavailable")
    store = private_dir(home / "pnpm-store")
    try:
        subprocess.run(
            [*resolve_bundled_launch_args(), "plugin", "--profile", profile.version, "add", "--offline", f"file:{SOURCE}"],
            cwd=home, env={**os.environ, "DSH_HOME": str(home), "npm_config_offline": "true",
                           "npm_config_store_dir": str(store), "npm_config_cache": str(home / "npm-cache"),
                           "npm_config_package_import_method": "copy"},
            stdin=subprocess.DEVNULL, capture_output=True, timeout=50, check=True, umask=0o077,
        )
        if PACKAGE not in _bundles(_directory(home, profile.version)):
            raise HarnessError("plugin_unavailable")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise HarnessError("plugin_unavailable") from exc


def change_plugin(root, package, action):
    if package != PACKAGE or action not in ("install", "enable", "disable", "remove"):
        raise HarnessError("invalid_argument")
    home = profile_home(root)
    with CHANGE_LOCK, acquire_profile(root) as current:
        if action in ("enable", "disable") and not current.installed:
            raise HarnessError("plugin_unavailable")
        installed = action != "remove"
        enabled = action in ("install", "enable")
        if (action == "install" and current.installed) or (installed, enabled) == (current.installed, current.enabled):
            return inventory(root)

        new = _new_profile(home, installed, enabled)
        directory = _directory(home, new.version)
        try:
            _seed(directory, installed and action != "install")
            if action == "install":
                _install(home, new)
            with PROFILE_LOCK:
                _publish(home, new)
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        return inventory(root)
