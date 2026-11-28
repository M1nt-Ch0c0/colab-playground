"""Persistent workflow runs, review checkpoints and step dispatch."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import re
import shutil
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable

from ..errors import StateConflict
from ..gallery import Store, probe_image_dimensions
from ..generation.catalog import DEFAULTS, LIMITS, VIDEO_WORKFLOWS
from ..generation.parameters import normalize_job
from ..generation.masked_edit import source_image
from ..generation.video_reference import VIDEO_TASKS, probe_reference_video
from . import video, web_assets
from .definitions import BUILTIN_WORKFLOWS, STEP_CATALOG, normalize_workflow_def, render_template, upgrade_stored_workflow


WORKFLOWS_MAX = 40
RUNS_MAX = 40
ASSET_NAME_RE = re.compile(r"[A-Za-z0-9._-]{1,120}")
RUN_ID_RE = re.compile(r"wr_[A-Za-z0-9_-]{4,48}")


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    # Strip markdown code fences if present
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    candidates = [fence.group(1)] if fence else []
    candidates.append(text)
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        candidates.append(text[first : last + 1])
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


class WorkflowEngine:
    """Manages composable workflow definitions, persistent runs, and background execution."""

    def __init__(self, root: Path, studio: Any, store: Store, log: Callable[[str], None]) -> None:
        self.root = root
        self.studio = studio
        self.store = store
        self.log = log
        self.dir = root / "workflows"
        self.defs_path = self.dir / "definitions.json"
        self.runs_dir = self.dir / "runs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._definitions: list[dict[str, Any]] = self._load_definitions()
        self._active_run_id: str | None = None
        self._active_thread: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self._paused: dict[str, tuple[int, dict]] = {}
        self._recover_interrupted_runs()

    # ── definitions ───────────────────────────────────────────────────

    def _load_definitions(self) -> list[dict[str, Any]]:
        if not self.defs_path.exists():
            return []
        try:
            data = json.loads(self.defs_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                saved = [d for d in data if isinstance(d, dict) and d.get("id") and d.get("steps")][:WORKFLOWS_MAX]
                return [upgrade_stored_workflow(d) for d in saved]
        except (OSError, json.JSONDecodeError):
            pass
        return []

    def _save_definitions_locked(self) -> None:
        tmp = self.defs_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._definitions, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.defs_path)

    def list_workflows(self) -> dict[str, Any]:
        with self._lock:
            custom = copy.deepcopy(self._definitions)
        return {
            "builtin": copy.deepcopy(BUILTIN_WORKFLOWS),
            "custom": custom,
            "step_catalog": copy.deepcopy(STEP_CATALOG),
            "ffmpeg_available": video.ffmpeg_available(),
            "runs": self.list_runs(),
        }

    def get_workflow(self, wf_id: str) -> dict[str, Any] | None:
        for b in BUILTIN_WORKFLOWS:
            if b["id"] == wf_id:
                return copy.deepcopy(b)
        with self._lock:
            for d in self._definitions:
                if d["id"] == wf_id:
                    return copy.deepcopy(d)
        return None

    def save_workflow(self, body: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        entry = normalize_workflow_def(body)
        with self._lock:
            self._definitions = [
                d for d in self._definitions if d.get("id") != entry["id"] and d.get("name") != entry["name"]
            ]
            self._definitions.insert(0, entry)
            del self._definitions[WORKFLOWS_MAX:]
            self._save_definitions_locked()
            return copy.deepcopy(entry), copy.deepcopy(self._definitions)

    def delete_workflow(self, wf_id: str) -> tuple[bool, list[dict[str, Any]]]:
        wid = str(wf_id or "").strip()
        if wid.startswith("builtin:"):
            raise ValueError("内置工作流模板不可删除")
        with self._lock:
            before = len(self._definitions)
            self._definitions = [d for d in self._definitions if d.get("id") != wid]
            removed = len(self._definitions) != before
            if removed:
                self._save_definitions_locked()
            return removed, copy.deepcopy(self._definitions)

    # ── run persistence ───────────────────────────────────────────────

    def _run_dir(self, run_id: str) -> Path:
        if not RUN_ID_RE.fullmatch(run_id or ""):
            raise ValueError("无效的运行 ID")
        return self.runs_dir / run_id

    def _run_file(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "run.json"

    def _assets_dir(self, run_id: str) -> Path:
        d = self._run_dir(run_id) / "assets"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _read_run_locked(self, run_id: str) -> dict[str, Any] | None:
        try:
            p = self._run_file(run_id)
        except ValueError:
            return None
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("workflow"), dict):
                upgrade_stored_workflow(data["workflow"])
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _write_run_locked(self, run: dict[str, Any]) -> None:
        run["updated_at"] = int(time.time())
        p = self._run_file(run["id"])
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p)
        if run["status"] == "paused":
            self._paused[run["id"]] = (p.stat().st_mtime_ns, self._run_summary(run))
        else:
            self._paused.pop(run["id"], None)

    def _recover_interrupted_runs(self) -> None:
        with self._lock:
            for d in self.runs_dir.iterdir():
                if not d.is_dir() or not RUN_ID_RE.fullmatch(d.name):
                    continue
                run = self._read_run_locked(d.name)
                if not run:
                    continue
                if run.get("status") == "running":
                    run["status"] = "paused"
                    run["current_step_id"] = None
                    run["pause_reason"] = "服务重启，工作流已暂停，可点击「继续」恢复执行"
                    for st in run.get("step_states", {}).values():
                        if st.get("status") == "running":
                            st["status"] = "pending"
                    self._write_run_locked(run)
                elif run.get("status") == "paused":
                    self._paused[run["id"]] = (self._run_file(run["id"]).stat().st_mtime_ns, self._run_summary(run))

    @staticmethod
    def _run_summary(run: dict[str, Any]) -> dict[str, Any]:
        steps = run.get("workflow", {}).get("steps") or []
        states = run.get("step_states") or {}
        done_n = sum(1 for s in steps if (states.get(s["id"]) or {}).get("status") in {"done", "skipped"})
        final_rid = None
        for s in reversed(steps):
            out = (states.get(s["id"]) or {}).get("output") or {}
            if out.get("final_round_id"):
                final_rid = out["final_round_id"]
                break
        return {
            "id": run["id"],
            "workflow_id": run.get("workflow", {}).get("id", ""),
            "workflow_name": run.get("workflow", {}).get("name", ""),
            "topic": str(run.get("topic") or "")[:120],
            "status": run.get("status", "draft"),
            "current_step_id": run.get("current_step_id"),
            "done_steps": done_n,
            "total_steps": len(steps),
            "final_round_id": final_rid,
            "created_at": run.get("created_at", 0),
            "updated_at": run.get("updated_at", 0),
            "error": run.get("error", ""),
        }

    def list_runs(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        with self._lock:
            for d in self.runs_dir.iterdir():
                if not d.is_dir() or not RUN_ID_RE.fullmatch(d.name):
                    continue
                run = self._read_run_locked(d.name)
                if run:
                    out.append(self._run_summary(run))
        out.sort(key=lambda r: r.get("updated_at") or 0, reverse=True)
        return out[:RUNS_MAX]

    def active_summary(self) -> dict[str, Any] | None:
        with self._lock:
            if self._active_run_id:
                run = self._read_run_locked(self._active_run_id)
                if run and run["status"] == "running":
                    return self._run_summary(run)
            recent = max(self._paused.values(), key=lambda item: (item[0], item[1]["id"]), default=None)
            return dict(recent[1]) if recent else None

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._read_run_locked(run_id)
            if not run:
                return None
            run = copy.deepcopy(run)
            run["assets"] = self._list_assets_locked(run_id)
            return run

    def create_run(self, body: dict[str, Any]) -> dict[str, Any]:
        wf_obj: dict[str, Any] | None = None
        if isinstance(body.get("workflow"), dict) and body["workflow"].get("steps"):
            raw_wf = dict(body["workflow"])
            raw_wf.setdefault("name", "自定义工作流")
            norm = normalize_workflow_def({**raw_wf, "id": ""})
            norm["id"] = str(raw_wf.get("id") or norm["id"])
            norm["builtin"] = any(w["id"] == norm["id"] for w in BUILTIN_WORKFLOWS)
            wf_obj = norm
        else:
            wf_id = str(body.get("workflow_id") or "builtin:agent-long-video").strip()
            wf_obj = self.get_workflow(wf_id)
            if not wf_obj:
                raise ValueError(f"未找到工作流：{wf_id}")

        topic = str(body.get("topic") if body.get("topic") is not None else wf_obj.get("default_topic") or "").strip()
        if len(topic) > 2000:
            raise ValueError("主题描述不超过 2000 字")

        now = int(time.time())
        request_id = body.get("request_id")
        if request_id is not None and (not isinstance(request_id, str) or not re.fullmatch(r"[a-f0-9]{32}", request_id)):
            raise ValueError("无效的草稿请求 ID")
        run_id = "wr_" + (request_id or uuid.uuid4().hex)
        step_states = {
            st["id"]: {
                "status": "pending",
                "started_at": None,
                "finished_at": None,
                "progress": "",
                "output": {},
                "error": "",
            }
            for st in wf_obj["steps"]
        }
        run: dict[str, Any] = {
            "id": run_id,
            "topic": topic,
            "workflow": wf_obj,
            "status": "draft",  # draft | running | paused | done | error | canceled
            "current_step_id": None,
            "pause_reason": "",
            "error": "",
            "step_states": step_states,
            "logs": [f"{time.strftime('%H:%M:%S')}  已创建工作流实例「{wf_obj['name']}」"],
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            if request_id and self._run_file(run_id).exists():
                existing = self.get_run(run_id)
                if existing is None:
                    raise OSError("无法读取已创建的草稿")
                return existing
            self._assets_dir(run_id)
            self._write_run_locked(run)
            run["assets"] = []
        return copy.deepcopy(run)

    def update_run_config(self, run_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Update topic and/or workflow step definitions on a non-running run."""
        with self._lock:
            if self._active_run_id == run_id:
                raise StateConflict("工作流正在运行，请先暂停或停止后再修改步骤配置")
            run = self._read_run_locked(run_id)
            if not run:
                raise ValueError("运行记录不存在")
            if "topic" in body:
                topic = str(body.get("topic") or "").strip()
                if len(topic) > 2000:
                    raise ValueError("主题描述不超过 2000 字")
                run["topic"] = topic
            if isinstance(body.get("workflow"), dict) and body["workflow"].get("steps"):
                raw_wf = dict(body["workflow"])
                raw_wf.setdefault("name", run["workflow"].get("name") or "工作流")
                if "variables" not in raw_wf and run["workflow"].get("variables"):
                    raw_wf["variables"] = run["workflow"]["variables"]
                norm = normalize_workflow_def({**raw_wf, "id": ""})
                norm["id"] = str(raw_wf.get("id") or run["workflow"].get("id") or norm["id"])
                norm["builtin"] = bool(run["workflow"].get("builtin"))
                run["workflow"] = norm
                old_states = run.get("step_states") or {}
                new_states = {}
                for st in norm["steps"]:
                    sid = st["id"]
                    new_states[sid] = old_states.get(sid) or {
                        "status": "pending",
                        "started_at": None,
                        "finished_at": None,
                        "progress": "",
                        "output": {},
                        "error": "",
                    }
                run["step_states"] = new_states
            self._write_run_locked(run)
            run["assets"] = self._list_assets_locked(run_id)
            return copy.deepcopy(run)

    def delete_run(self, run_id: str) -> bool:
        with self._lock:
            if self._active_run_id == run_id:
                raise StateConflict("该工作流正在运行，请先终止后再删除")
            d = self._run_dir(run_id)
            if not d.exists():
                return False
            shutil.rmtree(d)
            self._paused.pop(run_id, None)
            return True

    # ── run assets (human uploads & agent downloads) ──────────────────

    def _list_assets_locked(self, run_id: str) -> list[dict[str, Any]]:
        adir = self._assets_dir(run_id)
        items: list[dict[str, Any]] = []
        for p in sorted(adir.iterdir(), key=lambda x: x.stat().st_mtime):
            if not p.is_file() or p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            w, h = probe_image_dimensions(p)
            items.append({
                "filename": p.name,
                "bytes": p.stat().st_size,
                "width": w,
                "height": h,
                "updated_at": int(p.stat().st_mtime),
            })
        return items

    def asset_path(self, run_id: str, filename: str) -> Path | None:
        if not ASSET_NAME_RE.fullmatch(filename or "") or ".." in filename or "/" in filename or "\\" in filename:
            return None
        try:
            p = self._run_dir(run_id) / "assets" / filename
        except ValueError:
            return None
        return p if p.is_file() and not p.is_symlink() else None

    def asset_thumbnail(self, run_id: str, filename: str) -> Path | None:
        from PIL import Image, ImageOps

        with self._lock:
            src = self.asset_path(run_id, filename)
            if src is None:
                return None
            dest = self._run_dir(run_id) / "thumbs" / (filename + ".jpg")
            if dest.is_file() and dest.stat().st_mtime_ns >= src.stat().st_mtime_ns:
                return dest
            dest.parent.mkdir(exist_ok=True)
            tmp = dest.with_suffix(".tmp")
            try:
                with Image.open(src) as original:
                    original.thumbnail((480, 480), Image.Resampling.LANCZOS)
                    thumb = ImageOps.exif_transpose(original).convert("RGBA")
                    background = Image.new("RGB", thumb.size, "white")
                    background.paste(thumb, mask=thumb.getchannel("A"))
            except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
                raise ValueError("素材无法解码为缩略图") from exc
            try:
                background.save(tmp, "JPEG", quality=82, optimize=True)
                os.replace(tmp, dest)
            finally:
                tmp.unlink(missing_ok=True)
            return dest

    def upload_asset(self, run_id: str, data: bytes, *, step_id: str = "", label: str = "upload") -> dict[str, Any]:
        if len(data) < 32 or len(data) > web_assets.MAX_WEB_IMAGE_BYTES:
            raise ValueError(f"图片为空或超过 {web_assets.MAX_WEB_IMAGE_BYTES // 1048576}MB")
        ext = web_assets.image_extension(data)
        if not ext:
            raise ValueError("只接受 PNG、JPEG 或 WebP 图片")
        from PIL import Image
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
        except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ValueError("图片数据损坏或尺寸过大") from exc
        safe_prefix = re.sub(r"[^A-Za-z0-9_-]", "", label or "asset")[:24] or "asset"
        digest = hashlib.sha256(step_id.encode() + b"\0" + data).hexdigest()
        fname = f"{safe_prefix}_{digest}{ext}"
        with self._lock:
            run = self._read_run_locked(run_id)
            if not run:
                raise ValueError("运行记录不存在")
            if self._active_run_id == run_id:
                raise StateConflict("请等待工作流暂停后再上传素材")
            if step_id and not any(s["id"] == step_id and s["type"] in {"asset_input", "web_asset_fetch"}
                                   for s in run["workflow"]["steps"]):
                raise ValueError("请选择可接收素材的步骤")
            dest = self._assets_dir(run_id) / fname
            if not dest.exists():
                tmp = dest.with_suffix(ext + ".tmp")
                tmp.write_bytes(data)
                os.replace(tmp, dest)
            w, h = probe_image_dimensions(dest)
            entry = {"filename": fname, "bytes": len(data), "width": w, "height": h, "source": "upload"}
            # Auto-attach to specified step if applicable
            if step_id:
                for st in run["workflow"]["steps"]:
                    if st["id"] != step_id:
                        continue
                    if st["type"] == "asset_input":
                        files = list(st["config"].get("asset_files") or [])
                        if fname not in files:
                            files.append(fname)
                        st["config"]["asset_files"] = files
                    elif st["type"] == "web_asset_fetch":
                        ss = run["step_states"].setdefault(step_id, {"status": "done", "output": {}})
                        out = ss.setdefault("output", {})
                        imgs = [img for img in out.get("images") or [] if img.get("filename") != fname]
                        imgs.append({
                            "filename": fname,
                            "source_url": "",
                            "page_url": "",
                            "title": "手动上传参考图",
                            "bytes": len(data),
                            "width": w,
                            "height": h,
                        })
                        out["images"] = imgs
                        out["count"] = len(imgs)
                        ss["status"] = "done"
                        ss["error"] = ""
                self._write_run_locked(run)
            assets = self._list_assets_locked(run_id)
        return {"asset": entry, "filename": fname, "assets": assets}

    def delete_asset(self, run_id: str, filename: str) -> list[dict[str, Any]]:
        p = self.asset_path(run_id, filename)
        if not p:
            raise ValueError("未找到该资产文件")
        with self._lock:
            if self._active_run_id == run_id:
                raise StateConflict("请等待工作流暂停后再删除素材")
            run = self._read_run_locked(run_id)
            if run:
                for st in run["workflow"]["steps"]:
                    if st["type"] == "asset_input":
                        files = [f for f in (st["config"].get("asset_files") or []) if f != filename]
                        st["config"]["asset_files"] = files
                    ss = run["step_states"].get(st["id"])
                    if ss and isinstance(ss.get("output"), dict) and isinstance(ss["output"].get("images"), list):
                        ss["output"]["images"] = [
                            img for img in ss["output"]["images"] if img.get("filename") != filename
                        ]
                        ss["output"]["count"] = len(ss["output"]["images"])
                self._write_run_locked(run)
            p.unlink(missing_ok=True)
            (self._run_dir(run_id) / "thumbs" / (filename + ".jpg")).unlink(missing_ok=True)
            return self._list_assets_locked(run_id)

    # ── human-in-the-loop editing & step control ──────────────────────

    def update_step_output(self, run_id: str, step_id: str, output_patch: dict[str, Any]) -> dict[str, Any]:
        """Allow the user to edit a step's output (script scenes, H3 prompts, fetched images, etc.) while paused."""
        if not isinstance(output_patch, dict):
            raise ValueError("output 必须是对象")
        with self._lock:
            if self._active_run_id == run_id:
                raise StateConflict("工作流正在运行，请先暂停再修改步骤输出")
            run = self._read_run_locked(run_id)
            if not run:
                raise ValueError("运行记录不存在")
            if step_id not in run.get("step_states", {}):
                raise ValueError(f"未找到步骤：{step_id}")
            ss = run["step_states"][step_id]
            cur_out = dict(ss.get("output") or {})
            cur_out.update(output_patch)
            ss["output"] = cur_out
            if ss.get("status") in {"pending", "error"}:
                ss["status"] = "done"
                ss["error"] = ""
            self._append_log_locked(run, f"人工已编辑步骤「{step_id}」的输出")
            self._write_run_locked(run)
            run["assets"] = self._list_assets_locked(run_id)
            return copy.deepcopy(run)

    def start_run(self, run_id: str, *, from_step_id: str | None = None, single_step: bool = False,
                  draft_only: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._active_run_id and self._active_thread and self._active_thread.is_alive():
                raise StateConflict(f"已有工作流正在执行（{self._active_run_id}），请等待或先终止")
            run = self._read_run_locked(run_id)
            if not run:
                raise ValueError("运行记录不存在")
            if draft_only and run["status"] != "draft":
                raise StateConflict("这份草稿已经启动，请查看运行记录")
            steps = run["workflow"]["steps"]
            start_idx = 0
            if from_step_id:
                idx = next((i for i, s in enumerate(steps) if s["id"] == from_step_id), -1)
                if idx < 0:
                    raise ValueError(f"未找到步骤：{from_step_id}")
                start_idx = idx
                # Reset target step (and downstream steps if running full pipeline from here)
                end_reset = idx + 1 if single_step else len(steps)
                for j in range(idx, end_reset):
                    sid = steps[j]["id"]
                    run["step_states"][sid] = {
                        "status": "pending",
                        "started_at": None,
                        "finished_at": None,
                        "progress": "",
                        "output": {},
                        "error": "",
                    }
            else:
                # Resume from first non-done step, or restart from 0 if already finished/canceled
                first_pending = next(
                    (
                        i for i, s in enumerate(steps)
                        if run["step_states"].get(s["id"], {}).get("status") not in {"done", "skipped"}
                    ),
                    -1,
                )
                if first_pending < 0:
                    for s in steps:
                        run["step_states"][s["id"]] = {
                            "status": "pending",
                            "started_at": None,
                            "finished_at": None,
                            "progress": "",
                            "output": {},
                            "error": "",
                        }
                    start_idx = 0
                else:
                    start_idx = first_pending

            run["status"] = "running"
            run["error"] = ""
            run["pause_reason"] = ""
            self._append_log_locked(
                run,
                f"开始执行（从第 {start_idx + 1} 步「{steps[start_idx]['name']}」起"
                + ("，仅单步重试）" if single_step else "）"),
            )
            self._write_run_locked(run)
            self._active_run_id = run_id
            self._cancel_event.clear()
            t = threading.Thread(
                target=self._execute_run_loop,
                args=(run_id, start_idx, single_step),
                daemon=True,
            )
            self._active_thread = t
            t.start()
            run["assets"] = self._list_assets_locked(run_id)
            return copy.deepcopy(run)

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            run = self._read_run_locked(run_id)
            if not run:
                raise ValueError("运行记录不存在")
            if self._active_run_id == run_id:
                self._cancel_event.set()
                self._append_log_locked(run, "已收到终止信号，正在停止当前步骤…")
                self._write_run_locked(run)
            elif run.get("status") in {"paused", "running"}:
                run["status"] = "canceled"
                self._append_log_locked(run, "工作流已终止")
                self._write_run_locked(run)
            run["assets"] = self._list_assets_locked(run_id)
            return copy.deepcopy(run)

    # ── execution loop ────────────────────────────────────────────────

    def _append_log_locked(self, run: dict[str, Any], msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')}  {msg}"
        logs = run.setdefault("logs", [])
        logs.append(line)
        if len(logs) > 200:
            del logs[:-200]
        self.log(f"[WF {run['id']}] {msg}")

    def _set_step_progress(self, run_id: str, step_id: str, text: str) -> None:
        with self._lock:
            run = self._read_run_locked(run_id)
            if not run:
                return
            ss = run["step_states"].setdefault(step_id, {})
            ss["progress"] = text
            self._write_run_locked(run)

    def _execute_run_loop(self, run_id: str, start_idx: int, single_step: bool) -> None:
        try:
            with self._lock:
                run = self._read_run_locked(run_id)
                if not run:
                    return
                steps = copy.deepcopy(run["workflow"]["steps"])

            end_idx = min(len(steps), start_idx + 1) if single_step else len(steps)
            for idx in range(start_idx, end_idx):
                if self._cancel_event.is_set():
                    with self._lock:
                        run = self._read_run_locked(run_id)
                        if run:
                            run["status"] = "canceled"
                            run["current_step_id"] = None
                            self._append_log_locked(run, "工作流已终止")
                            self._write_run_locked(run)
                    return

                step = steps[idx]
                sid = step["id"]
                if not step.get("enabled", True):
                    with self._lock:
                        run = self._read_run_locked(run_id)
                        if run:
                            ss = run["step_states"].setdefault(sid, {})
                            ss["status"] = "skipped"
                            ss["progress"] = "已禁用跳过"
                            self._write_run_locked(run)
                    continue

                with self._lock:
                    run = self._read_run_locked(run_id)
                    if not run:
                        return
                    run["current_step_id"] = sid
                    ss = run["step_states"].setdefault(sid, {})
                    ss["status"] = "running"
                    ss["started_at"] = int(time.time())
                    ss["finished_at"] = None
                    ss["error"] = ""
                    ss["progress"] = "准备中…"
                    self._append_log_locked(run, f"执行步骤：{step['name']} ({step['type']})")
                    self._write_run_locked(run)
                    run_snap = copy.deepcopy(run)

                try:
                    output = self._run_step(run_snap, step)
                except Exception as exc:
                    canceled = self._cancel_event.is_set() or "终止" in str(exc) or "取消" in str(exc)
                    with self._lock:
                        run = self._read_run_locked(run_id)
                        if run:
                            ss = run["step_states"].setdefault(sid, {})
                            ss["status"] = "canceled" if canceled else "error"
                            ss["finished_at"] = int(time.time())
                            ss["error"] = str(exc)[:500]
                            run["status"] = "canceled" if canceled else "error"
                            run["current_step_id"] = None
                            run["error"] = "" if canceled else f"步骤「{step['name']}」失败：{exc}"
                            self._append_log_locked(
                                run,
                                ("步骤已取消：" if canceled else f"步骤「{step['name']}」失败：") + str(exc),
                            )
                            if not canceled:
                                self._append_log_locked(run, traceback.format_exc().splitlines()[-1])
                            self._write_run_locked(run)
                    return

                with self._lock:
                    run = self._read_run_locked(run_id)
                    if not run:
                        return
                    ss = run["step_states"].setdefault(sid, {})
                    ss["status"] = "done"
                    ss["finished_at"] = int(time.time())
                    ss["progress"] = "已完成"
                    ss["output"] = output
                    ss["error"] = ""
                    self._append_log_locked(run, f"完成步骤：{step['name']}")
                    has_more = (idx + 1 < end_idx) and any(steps[k].get("enabled", True) for k in range(idx + 1, end_idx))
                    if step.get("pause_after") and has_more:
                        run["status"] = "paused"
                        run["current_step_id"] = None
                        run["pause_reason"] = f"已在「{step['name']}」后暂停，请检查或编辑结果后点击「继续下一步」"
                        self._append_log_locked(run, run["pause_reason"])
                        self._write_run_locked(run)
                        return
                    self._write_run_locked(run)

            with self._lock:
                run = self._read_run_locked(run_id)
                if run:
                    all_done = all(
                        (run["step_states"].get(s["id"]) or {}).get("status") in {"done", "skipped"}
                        for s in steps
                    )
                    run["status"] = "done" if all_done else "paused"
                    run["current_step_id"] = None
                    if all_done:
                        self._append_log_locked(run, "工作流全部步骤执行完成！")
                    else:
                        run["pause_reason"] = "单步重试已完成，可点击「继续」执行后续步骤"
                        self._append_log_locked(run, run["pause_reason"])
                    self._write_run_locked(run)
        finally:
            with self._lock:
                if self._active_run_id == run_id:
                    self._active_run_id = None
                    self._active_thread = None

    # ── step resolvers & helpers ──────────────────────────────────────

    def _template_ctx(self, run: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx: dict[str, Any] = {"topic": run.get("topic") or ""}
        for sid, ss in (run.get("step_states") or {}).items():
            out = ss.get("output") or {}
            ctx[sid] = out
        if extra:
            ctx.update(extra)
        if variables := run.get("workflow", {}).get("variables"):
            ctx["vars"] = variables
        return ctx

    def _collect_ref_blobs_from_sources(
        self, run: dict[str, Any], source_ids: list[str], *, scene_index: int | None = None
    ) -> list[bytes]:
        """Collect image bytes from referenced steps (asset_input, web_asset_fetch, image_gen)."""
        blobs: list[bytes] = []
        run_id = run["id"]
        states = run.get("step_states") or {}
        steps_by_id = {s["id"]: s for s in run["workflow"]["steps"]}

        for src_id in source_ids or []:
            st = steps_by_id.get(src_id)
            ss = states.get(src_id) or {}
            out = ss.get("output") or {}
            if not st:
                continue
            if st["type"] == "asset_input":
                files = out.get("asset_files") or st["config"].get("asset_files") or []
                for fn in files:
                    p = self.asset_path(run_id, fn)
                    if p:
                        blobs.append(p.read_bytes())
                for rid in (out.get("round_ids") or st["config"].get("round_ids") or []):
                    found = self.store.media_path(str(rid))
                    if found and found[0] == "image":
                        blobs.append(found[1].read_bytes())
            elif st["type"] == "web_asset_fetch":
                imgs = out.get("images") or []
                if scene_index is not None:
                    matched = [im for im in imgs if im.get("scene_index") == scene_index]
                    pick = matched or imgs
                else:
                    pick = imgs
                for im in pick:
                    p = self.asset_path(run_id, str(im.get("filename") or ""))
                    if p:
                        blobs.append(p.read_bytes())
            elif st["type"] == "image_gen":
                items = out.get("items") or []
                if scene_index is not None:
                    matched = [it for it in items if it.get("scene_index") == scene_index]
                    pick_rids = [it.get("round_id") for it in matched if it.get("round_id")]
                else:
                    pick_rids = [it.get("round_id") for it in items if it.get("round_id")]
                for rid in pick_rids:
                    found = self.store.media_path(str(rid))
                    if found and found[0] == "image":
                        blobs.append(found[1].read_bytes())
        return blobs[: LIMITS["refs_max"]]

    def _get_scenes(self, run: dict[str, Any], scenes_from: str) -> list[dict[str, Any]]:
        if not scenes_from:
            return []
        ss = (run.get("step_states") or {}).get(scenes_from) or {}
        out = ss.get("output") or {}
        scenes = out.get("scenes")
        if isinstance(scenes, list) and scenes:
            return [s for s in scenes if isinstance(s, dict)]
        return []

    # ── 7 step executors ──────────────────────────────────────────────

    def _run_step(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        stype = step["type"]
        if stype == "asset_input":
            return self._exec_asset_input(run, step)
        if stype == "llm_script":
            return self._exec_llm_script(run, step)
        if stype == "web_asset_fetch":
            return self._exec_web_asset_fetch(run, step)
        if stype == "image_gen":
            return self._exec_image_gen(run, step)
        if stype == "h3_prompt":
            return self._exec_h3_prompt(run, step)
        if stype == "video_gen":
            return self._exec_video_gen(run, step)
        if stype == "video_stitch":
            return self._exec_video_stitch(run, step)
        raise ValueError(f"未知步骤类型：{stype}")

    def _exec_asset_input(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        cfg = step["config"]
        files: list[str] = []
        assets_meta: list[dict[str, Any]] = []
        for fn in cfg.get("asset_files") or []:
            p = self.asset_path(run["id"], str(fn))
            if p:
                w, h = probe_image_dimensions(p)
                files.append(p.name)
                assets_meta.append({"filename": p.name, "bytes": p.stat().st_size, "width": w, "height": h})
        rids: list[str] = []
        for rid in cfg.get("round_ids") or []:
            found = self.store.media_path(str(rid))
            if found and found[0] == "image":
                rids.append(str(rid))
        return {
            "role": str(cfg.get("role") or "character"),
            "asset_files": files,
            "assets": assets_meta,
            "round_ids": rids,
            "count": len(files) + len(rids),
        }

    def _exec_llm_script(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        cfg = step["config"]
        scene_count = max(1, min(8, int(cfg.get("scene_count") or 3)))
        out_fmt = "text" if cfg.get("output_format") == "text" else "storyboard"
        ctx = self._template_ctx(run, {"scene_count": scene_count})
        instruction = render_template(cfg.get("instruction") or "请围绕 {{topic}} 编写分镜。", ctx)
        self._set_step_progress(run["id"], step["id"], "正在调用 AI 导演撰写分镜脚本…")

        if out_fmt == "text":
            raw, model = self.studio.call_llm(
                [
                    {"role": "system", "content": "你是资深电影导演与分镜策划，输出清晰、可直接执行的创作文本。"},
                    {"role": "user", "content": instruction},
                ],
                temperature=0.5,
                max_tokens=4096,
            )
            return {"format": "text", "model": model, "text": raw.strip(), "scenes": []}

        sys_prompt = (
            "你是专业 AI 长视频导演与分镜设计师。"
            "请严格输出一个合法 JSON 对象（不要包含任何额外解释文字），结构如下：\n"
            "{\n"
            '  "title": "短片标题",\n'
            '  "style_bible": "统一视觉风格、光影色调与角色服装规范",\n'
            '  "scenes": [\n'
            "    {\n"
            '      "index": 1,\n'
            '      "title": "镜头标题",\n'
            '      "duration_s": 5,\n'
            '      "search_query": "short English search keywords for white-model pose or scene layout reference",\n'
            '      "keyframe_prompt": "详尽的中文生图关键帧提示词（融合参考构图与角色特征、光线材质、景别）",\n'
            '      "video_prompt": "该镜头的动态运镜、人物动作与情绪变化描述",\n'
            '      "audio_notes": "环境音、拟音、对白或配乐设计"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            f"scenes 数组长度必须严格为 {scene_count}，每镜内容连贯、细节具体。"
        )
        raw, model = self.studio.call_llm(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": instruction},
            ],
            temperature=0.45,
            max_tokens=8192,
        )
        parsed = _extract_json_object(raw)
        if not parsed or not isinstance(parsed.get("scenes"), list) or not parsed["scenes"]:
            raise RuntimeError("AI 未返回合法的分镜 JSON，请重试或调整指令")
        scenes: list[dict[str, Any]] = []
        for idx, sc in enumerate(parsed["scenes"][:8], start=1):
            if not isinstance(sc, dict):
                continue
            scenes.append({
                "index": idx,
                "title": str(sc.get("title") or f"镜头 {idx}").strip()[:120],
                "duration_s": max(3, min(15, int(sc.get("duration_s") or 5))),
                "search_query": str(sc.get("search_query") or "").strip()[:200],
                "keyframe_prompt": str(sc.get("keyframe_prompt") or sc.get("prompt") or "").strip()[:3000],
                "video_prompt": str(sc.get("video_prompt") or sc.get("motion") or "").strip()[:2000],
                "audio_notes": str(sc.get("audio_notes") or "").strip()[:800],
            })
        if not scenes:
            raise RuntimeError("分镜 JSON 中没有有效镜头")
        return {
            "format": "storyboard",
            "model": model,
            "title": str(parsed.get("title") or run.get("topic") or "未命名短片").strip()[:120],
            "style_bible": str(parsed.get("style_bible") or "").strip()[:1000],
            "scenes": scenes,
            "text": raw[:4000],
        }

    def _exec_web_asset_fetch(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        cfg = step["config"]
        ctx = self._template_ctx(run)
        direct_url = render_template(cfg.get("url") or "", ctx).strip()
        search_query = render_template(cfg.get("search_query") or "", ctx).strip()
        instruction = render_template(cfg.get("instruction") or "选择最清晰契合的参考图", ctx).strip()
        max_images = max(1, min(6, int(cfg.get("max_images") or 2)))
        scenes_from = str(cfg.get("scenes_from") or "").strip()

        candidates: list[dict[str, str]] = []
        page_summary = ""

        if direct_url:
            self._set_step_progress(run["id"], step["id"], f"正在抓取网页：{direct_url[:60]}…")
            raw, ctype, final_url = web_assets.fetch_public_bytes(direct_url, max_bytes=web_assets.MAX_WEB_HTML_BYTES, timeout=25)
            # If user pasted a direct image URL, download it directly
            if web_assets.image_extension(raw) or ctype.startswith("image/"):
                candidates.append({"url": final_url, "alt": "direct image", "page_url": final_url, "source": "direct"})
            else:
                parser = web_assets.PageImageExtractor(final_url)
                parser.feed(raw.decode("utf-8", errors="replace"))
                page_summary = f"Title: {parser.title}\n" + " ".join(parser.text_parts)[:1200]
                for img in parser.images[:40]:
                    img["page_url"] = final_url
                    candidates.append(img)
        else:
            queries: list[str] = []
            if scenes_from:
                for sc in self._get_scenes(run, scenes_from):
                    q = str(sc.get("search_query") or "").strip()
                    if q and q not in queries:
                        queries.append(q)
            if search_query and search_query not in queries:
                queries.append(search_query)
            if not queries:
                queries = [str(run.get("topic") or "architecture studio reference")]
            for q in queries[:3]:
                if self._cancel_event.is_set():
                    raise RuntimeError("已取消")
                self._set_step_progress(run["id"], step["id"], f"轻量 Agent 检索图库：{q[:50]}…")
                try:
                    found = web_assets.search_wikimedia_images(q, limit=10)
                    candidates.extend(found)
                except Exception as exc:
                    self.log(f"[WF {run['id']}] 检索 '{q}' 警告：{exc}")

        if not candidates:
            raise RuntimeError("未从目标网页或检索词找到可用图片，请更换网页链接、修改关键词，或暂停后手动上传参考图")

        # Rank candidates with the selected model; keep source order if ranking fails.
        chosen: list[dict[str, str]] = []
        if len(candidates) > max_images:
            self._set_step_progress(run["id"], step["id"], f"AI 正在从 {len(candidates)} 张候选图中筛选最佳参考图…")
            try:
                cand_lines = [
                    f"{i}. url={c['url']} | alt={c.get('alt', '')[:120]}"
                    for i, c in enumerate(candidates[:25])
                ]
                prompt = (
                    f"主题：{run.get('topic') or ''}\n"
                    f"筛选要求：{instruction}\n"
                    + (f"页面摘要：{page_summary[:600]}\n" if page_summary else "")
                    + "候选图片列表：\n"
                    + "\n".join(cand_lines)
                    + f"\n\n请选出最契合的 {max_images} 张图片，只输出 JSON：{{\"selected\": [0, 1], \"reason\": \"简短理由\"}}"
                )
                raw_sel, _ = self.studio.call_llm(
                    [
                        {"role": "system", "content": "你是精准的视觉参考图筛选 Agent，只输出合法 JSON。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=1024,
                    timeout=90,
                )
                obj = _extract_json_object(raw_sel) or {}
                idxs = obj.get("selected") if isinstance(obj.get("selected"), list) else []
                for i in idxs:
                    if isinstance(i, int) and 0 <= i < len(candidates) and candidates[i] not in chosen:
                        chosen.append(candidates[i])
            except Exception as exc:
                self.log(f"[WF {run['id']}] LLM 选图降级为顺序选取：{exc}")

        for c in candidates:
            if len(chosen) >= max_images * 2:
                break
            if c not in chosen:
                chosen.append(c)

        saved: list[dict[str, Any]] = []
        adir = self._assets_dir(run["id"])
        for idx, cand in enumerate(chosen):
            if len(saved) >= max_images:
                break
            if self._cancel_event.is_set():
                raise RuntimeError("已取消")
            self._set_step_progress(run["id"], step["id"], f"下载参考图 {len(saved) + 1}/{max_images}…")
            try:
                img_bytes, _, final_img_url = web_assets.fetch_public_bytes(
                    cand["url"], max_bytes=web_assets.MAX_WEB_IMAGE_BYTES, timeout=30, accept="image/*"
                )
                ext = web_assets.image_extension(img_bytes)
                if not ext:
                    continue
                fname = f"web_{step['id']}_{int(time.time() * 1000) % 100000000:08d}_{idx}{ext}"
                dest = adir / fname
                dest.write_bytes(img_bytes)
                w, h = probe_image_dimensions(dest)
                # Skip tiny icons
                if (w and w < 128) or (h and h < 128):
                    dest.unlink(missing_ok=True)
                    continue
                saved.append({
                    "filename": fname,
                    "source_url": final_img_url,
                    "page_url": cand.get("page_url") or direct_url,
                    "title": cand.get("alt") or f"参考图 #{len(saved) + 1}",
                    "bytes": len(img_bytes),
                    "width": w,
                    "height": h,
                })
            except Exception as exc:
                self.log(f"[WF {run['id']}] 跳过无效图片 {cand['url'][:80]}：{exc}")

        if not saved:
            raise RuntimeError("候选图片全部下载或校验失败，请换一个公开网页 URL 或手动上传参考图")

        return {
            "source_url": direct_url,
            "search_query": search_query,
            "page_summary": page_summary[:600],
            "images": saved,
            "count": len(saved),
        }

    def _exec_image_gen(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        if not self.studio.colab.has_credentials():
            raise RuntimeError("尚未完成 Google Colab 授权，无法执行生图步骤")
        cfg = step["config"]
        scenes_from = str(cfg.get("scenes_from") or "").strip()
        scenes = self._get_scenes(run, scenes_from)
        max_scenes = max(1, min(8, int(cfg.get("max_scenes") or 6)))
        if scenes:
            scenes = scenes[:max_scenes]
        else:
            scenes = [{"index": 1, "title": "单张关键帧", "keyframe_prompt": run.get("topic") or ""}]

        ref_sources = cfg.get("ref_sources") or []
        prompt_tpl = str(cfg.get("prompt_template") or "{{scene.keyframe_prompt}}")
        prefix = str(cfg.get("prompt_prefix") or "").strip()
        items: list[dict[str, Any]] = []
        round_ids: list[str] = []

        for pos, sc in enumerate(scenes, start=1):
            if self._cancel_event.is_set():
                raise RuntimeError("已取消")
            sc_idx = int(sc.get("index") or pos)
            self._set_step_progress(run["id"], step["id"], f"正在生成关键帧 {pos}/{len(scenes)}：{sc.get('title', '')}")
            ctx = self._template_ctx(run, {"scene": sc})
            prompt = render_template(prompt_tpl, ctx).strip()
            if prefix:
                prompt = f"{prefix}, {prompt}" if prompt else prefix
            if not prompt:
                prompt = str(sc.get("keyframe_prompt") or run.get("topic") or "").strip()
            ref_blobs = self._collect_ref_blobs_from_sources(run, ref_sources, scene_index=sc_idx)

            raw_body: dict[str, Any] = {
                "mode": "image",
                "engine": cfg.get("engine") or "diffusers",
                "model": cfg.get("model") or DEFAULTS["image"]["model"],
                "prompt": prompt,
                "negative": cfg.get("negative") or "",
                "width": cfg.get("width") or 1280,
                "height": cfg.get("height") or 768,
                "steps": cfg.get("steps") or 35,
                "cfg": cfg.get("cfg") or 5.0,
                "seed": cfg.get("seed", -1),
                "gpu": cfg.get("gpu") or DEFAULTS["gpu"],
                "gpu_pool": cfg.get("gpu_pool") or [cfg.get("gpu") or DEFAULTS["gpu"]],
                "poll_rounds": cfg.get("poll_rounds") or 2,
                "poll_all_proxies": cfg.get("poll_all_proxies", False),
                "loras": cfg.get("loras") or [],
                "has_image": bool(ref_blobs),
                "idea": f"[工作流 {run['id']}] {sc.get('title', '')}",
            }
            if cfg.get("comfy"):
                raw_body["comfy"] = cfg["comfy"]
            payload = normalize_job(raw_body)
            payload["workflow_run_id"] = run["id"]
            payload["workflow_step_id"] = step["id"]
            created = self.studio.enqueue_with_refs(payload, ref_blobs=ref_blobs)
            job_id = created[0]["id"]
            done = self.studio.wait_for_job(job_id, cancel_check=self._cancel_event.is_set)
            if done.get("status") != "done" or not done.get("round_id"):
                raise RuntimeError(f"第 {pos} 镜关键帧生成失败：{done.get('error') or done.get('status')}")
            rid = str(done["round_id"])
            round_ids.append(rid)
            items.append({
                "scene_index": sc_idx,
                "title": sc.get("title") or f"镜头 {sc_idx}",
                "prompt": prompt,
                "round_id": rid,
                "ref_count": len(ref_blobs),
                "seed": done.get("seed"),
            })

        return {"items": items, "round_ids": round_ids, "count": len(items)}

    def _video_images(self, run: dict, workflow: str, keyframe: str, sources: list[str] | None,
                      scene_index: int, task: str | None) -> list[bytes]:
        if workflow == "t2va":
            return []
        frames = [source_image(self.store, keyframe)] if keyframe else []
        refs = self._collect_ref_blobs_from_sources(run, sources, scene_index=scene_index) if workflow == "ref2va" else []
        if task == "motion" and sources and not refs:
            raise ValueError("所选上游步骤没有可用的人设图，请检查素材")
        # In motion transfer Picture 1 supplies identity. Put selected character assets before the keyframe.
        images = refs + frames if task == "motion" else frames + refs
        if task == "motion" and not images:
            raise ValueError("白模动作参考需要人设图，请选择上游参考图或关键帧")
        return images[:LIMITS["refs_max"]]

    @staticmethod
    def _upstream_video_shots(run: dict, step: dict) -> dict[int, dict]:
        cfg = step["config"]
        source = cfg.get("video_from")
        if cfg.get("workflow") != "ref2va" or not source:
            return {}
        for upstream in run["workflow"]["steps"]:
            if upstream["id"] == step["id"]:
                break
            if upstream["id"] != source:
                continue
            state = run["step_states"].get(source) or {}
            output = state.get("output") or {}
            if state.get("status") == "done":
                if upstream["type"] == "video_stitch" and output.get("final_round_id"):
                    return {1: {"scene_index": 1, "title": upstream["name"], "round_id": output["final_round_id"]}}
                if upstream["type"] == "video_gen" and output.get("items"):
                    return {int(item["scene_index"]): item for item in output["items"]}
            break
        raise ValueError(f"上游步骤 {source} 没有可用的视频产出，请检查所选步骤及运行结果")

    @staticmethod
    def _video_reference(cfg: dict, shots: dict[int, dict], scene_index: int, inherited: dict | None = None) -> dict:
        if cfg.get("workflow") != "ref2va":
            return {}
        if not shots:
            return cfg if cfg.get("video_round_id") else (inherited or {})
        shot = next(iter(shots.values())) if len(shots) == 1 else shots.get(scene_index)
        if not shot or not shot.get("round_id"):
            raise ValueError(f"上游视频步骤没有镜头 {scene_index} 的片段")
        return {**cfg, "video_round_id": shot["round_id"]}

    def _exec_h3_prompt(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        cfg = step["config"]
        wf = str(cfg.get("workflow") or "fl2va")
        if wf not in {w["id"] for w in VIDEO_WORKFLOWS}:
            wf = "fl2va"
        num_frames = int(cfg.get("num_frames") or DEFAULTS["video"]["num_frames"])
        scenes_from = str(cfg.get("scenes_from") or "").strip()
        keyframe_from = str(cfg.get("keyframe_from") or "").strip()
        extra_refs = cfg.get("extra_ref_sources") or []
        upstream = self._upstream_video_shots(run, step)
        checked_clips = set()
        tail_id = cfg.get("last_frame_round_id") if wf == "fl2va" else None
        tail = source_image(self.store, tail_id) if tail_id else None
        ctx_base = self._template_ctx(run)
        extra_inst = render_template(cfg.get("instruction") or "", ctx_base).strip()

        kf_items = ((run.get("step_states") or {}).get(keyframe_from) or {}).get("output", {}).get("items") or []
        scenes = self._get_scenes(run, scenes_from) or kf_items or list(upstream.values())
        total = max(len(scenes), len(kf_items), 1)
        items: list[dict[str, Any]] = []

        for idx in range(total):
            if self._cancel_event.is_set():
                raise RuntimeError("已取消")
            sc = scenes[idx] if idx < len(scenes) else {"index": idx + 1, "title": f"镜头 {idx + 1}"}
            kf = kf_items[idx] if idx < len(kf_items) else {}
            sc_idx = int(sc.get("index") or sc.get("scene_index") or idx + 1)
            reference = self._video_reference(cfg, upstream, sc_idx)
            clip_id = reference.get("video_round_id")
            task = (reference.get("video_task") or "edit") if clip_id else None
            if clip_id and clip_id not in checked_clips:
                found = self.store.media_path(clip_id)
                if not found or found[0] != "video" or task not in VIDEO_TASKS:
                    raise ValueError("请在 H3 提示词步骤重新选择参考视频和用途")
                probe_reference_video(found[1])
                checked_clips.add(clip_id)
            self._set_step_progress(run["id"], step["id"], f"正在看图写 H3 视频提示词 {idx + 1}/{total}…")

            kf_rid = str(kf.get("round_id") or "")
            image_blobs = self._video_images(run, wf, kf_rid, extra_refs, sc_idx, task)
            override_images = [("<Picture 1> (First Frame at 0.00s)" if wf == "fl2va" else f"<Picture {i}>", blob)
                               for i, blob in enumerate(image_blobs, 1)]
            if tail:
                override_images.append((f"<Picture {len(override_images) + 1}> (Last Frame at end)", tail))

            brief_parts = [
                f"Shot title: {sc.get('title') or f'Shot {sc_idx}'}",
                f"Action & camera: {sc.get('video_prompt') or sc.get('keyframe_prompt') or run.get('topic') or ''}",
            ]
            if sc.get("audio_notes"):
                brief_parts.append(f"Audio & dialogue notes: {sc['audio_notes']}")
            if extra_inst:
                brief_parts.append(f"Director guidance: {extra_inst}")
            brief = "\n".join(brief_parts)

            res = self.studio.write_prompt_rich(
                brief,
                mode="video",
                workflow=wf,
                num_frames=num_frames,
                ref_count=len(override_images),
                override_images=override_images,
                **({"video_task": task} if task else {}),
                **({"has_last_image": True} if tail else {}),
            )
            items.append({
                "scene_index": sc_idx,
                "title": sc.get("title") or f"镜头 {sc_idx}",
                "keyframe_round_id": kf_rid,
                **({"video_round_id": clip_id, "video_task": task, "extra_ref_sources": extra_refs} if clip_id else {}),
                **({"last_frame_round_id": tail_id} if tail else {}),
                "video_prompt": res["prompt"],
                "format": res.get("format") or "",
                "images_used": res.get("images_used") or 0,
            })

        return {"workflow": wf, "num_frames": num_frames, "items": items, "count": len(items)}

    def _exec_video_gen(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        if not self.studio.colab.has_credentials():
            raise RuntimeError("尚未完成 Google Colab 授权，无法执行生视频步骤")
        cfg = step["config"]
        wf = str(cfg.get("workflow") or "fl2va")
        if wf not in {w["id"] for w in VIDEO_WORKFLOWS}:
            wf = "fl2va"
        upstream = self._upstream_video_shots(run, step)
        kf_items = ((run.get("step_states") or {}).get(str(cfg.get("keyframe_from") or "")) or {}).get("output", {}).get("items") or []
        pr_items = ((run.get("step_states") or {}).get(str(cfg.get("prompts_from") or "")) or {}).get("output", {}).get("items") or []
        scenes = self._get_scenes(run, str(cfg.get("scenes_from") or "")) or pr_items or kf_items or list(upstream.values())
        extra_refs = cfg.get("extra_ref_sources") or []

        total = max(len(pr_items), len(kf_items), len(scenes), 1)
        items: list[dict[str, Any]] = []
        round_ids: list[str] = []

        for idx in range(total):
            if self._cancel_event.is_set():
                raise RuntimeError("已取消")
            sc = scenes[idx] if idx < len(scenes) else {"index": idx + 1, "title": f"镜头 {idx + 1}"}
            kf = kf_items[idx] if idx < len(kf_items) else {}
            pr = pr_items[idx] if idx < len(pr_items) else {}
            sc_idx = int(pr.get("scene_index") or sc.get("index") or sc.get("scene_index") or idx + 1)
            title = pr.get("title") or sc.get("title") or f"镜头 {sc_idx}"
            self._set_step_progress(run["id"], step["id"], f"正在生成视频片段 {idx + 1}/{total}：{title}")

            prompt = str(pr.get("video_prompt") or sc.get("video_prompt") or sc.get("keyframe_prompt") or run.get("topic") or "").strip()
            if not prompt:
                raise RuntimeError(f"第 {idx + 1} 镜缺少视频提示词")

            kf_rid = str(pr.get("keyframe_round_id") or kf.get("round_id") or "")
            # A prompt step can hand off the same clip and character sources to each shot.
            reference = self._video_reference(cfg, upstream, sc_idx, pr)
            clip_id = reference.get("video_round_id")
            task = (reference.get("video_task") or "edit") if clip_id else None
            sources = extra_refs or (reference.get("extra_ref_sources") if clip_id else [])
            ref_blobs = self._video_images(run, wf, kf_rid, sources, sc_idx, task)
            tail_id = (cfg.get("last_frame_round_id") or pr.get("last_frame_round_id")) if wf == "fl2va" else None
            tail = source_image(self.store, tail_id) if tail_id else None
            if wf != "t2va" and not (ref_blobs or clip_id or tail):
                raise ValueError(f"第 {idx + 1} 镜缺少参考素材，请选择关键帧、参考素材或文生视频模式")
            raw_body: dict[str, Any] = {
                "mode": "video",
                "workflow": wf,
                **({"video_round_id": clip_id, "video_task": task} if clip_id else {}),
                **({"last_frame_round_id": tail_id} if tail else {}),
                "prompt": prompt,
                "negative": cfg.get("negative") or "",
                "width": cfg.get("width") or 1280,
                "height": cfg.get("height") or 768,
                "num_frames": cfg.get("num_frames") or 124,
                "steps": cfg.get("steps") or 30,
                "cfg": cfg.get("cfg") or 5.0,
                "seed": cfg.get("seed", -1),
                "auto_offload": cfg.get("auto_offload", True),
                "offload_mode": cfg.get("offload_mode"),
                "gpu": cfg.get("gpu") or "H100",
                "gpu_pool": cfg.get("gpu_pool") or [cfg.get("gpu") or "H100"],
                "poll_rounds": cfg.get("poll_rounds") or 2,
                "poll_all_proxies": cfg.get("poll_all_proxies", False),
                "loras": cfg.get("loras") or [],
                "has_image": bool(ref_blobs),
                "idea": f"[工作流 {run['id']}] {title}",
            }
            payload = normalize_job(raw_body)
            payload["workflow_run_id"] = run["id"]
            payload["workflow_step_id"] = step["id"]
            created = self.studio.enqueue_with_refs(payload, ref_blobs=ref_blobs, last_ref=tail)
            job_id = created[0]["id"]
            done = self.studio.wait_for_job(job_id, cancel_check=self._cancel_event.is_set)
            if done.get("status") != "done" or not done.get("round_id"):
                raise RuntimeError(f"第 {idx + 1} 镜视频生成失败：{done.get('error') or done.get('status')}")
            rid = str(done["round_id"])
            round_ids.append(rid)
            items.append({
                "scene_index": sc_idx,
                "title": title,
                "keyframe_round_id": kf_rid,
                "prompt": prompt[:400],
                "round_id": rid,
                "seed": done.get("seed"),
            })

        return {"items": items, "round_ids": round_ids, "count": len(items)}

    def _exec_video_stitch(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        cfg = step["config"]
        clip_rids: list[str] = []
        manual = cfg.get("clip_round_ids") or []
        if manual:
            clip_rids = [str(r).strip() for r in manual if str(r).strip()]
        else:
            src_id = str(cfg.get("clips_from") or "").strip()
            src_out = ((run.get("step_states") or {}).get(src_id) or {}).get("output") or {}
            clip_rids = [str(r) for r in (src_out.get("round_ids") or [])]

        clip_paths: list[Path] = []
        valid_rids: list[str] = []
        for rid in clip_rids:
            found = self.store.media_path(rid)
            if found and found[0] == "video":
                clip_paths.append(found[1])
                valid_rids.append(rid)
        if not clip_paths:
            raise RuntimeError("没有找到可拼接的视频作品（请确认上一步视频生成已完成或手动填入作品 ID）")

        self._set_step_progress(run["id"], step["id"], f"FFmpeg 正在剪辑合成 {len(clip_paths)} 段视频…")
        adir = self._assets_dir(run["id"])
        out_mp4 = adir / f"stitched_{step['id']}_{int(time.time())}.mp4"
        out_thumb = adir / f"stitched_{step['id']}_thumb.jpg"

        info = video.stitch_videos(
            clip_paths,
            out_mp4,
            out_thumb,
            target_width=int(cfg.get("target_width") or 1280),
            target_height=int(cfg.get("target_height") or 768),
            fps=int(cfg.get("fps") or 24),
            transition=cfg.get("transition", "fade"),
            fade_s=float(cfg.get("fade_s") or 0.35),
        )
        meta = {
            "prompt": f"[长视频工作流成片] {run.get('topic') or run['workflow'].get('name')}",
            "model": "Workflow Studio · FFmpeg",
            "workflow": "stitch",
            "width": info["width"],
            "height": info["height"],
            "duration_s": info["duration_s"],
            "workflow_run_id": run["id"],
            "workflow_step_id": step["id"],
            "source_rounds": valid_rids,
            "transition": info["transition"],
        }
        final_rid = self.store.save(out_mp4, "video", meta, out_thumb if out_thumb.exists() else None)
        out_mp4.unlink(missing_ok=True)
        out_thumb.unlink(missing_ok=True)
        return {
            "final_round_id": final_rid,
            "source_rounds": valid_rids,
            **info,
        }
