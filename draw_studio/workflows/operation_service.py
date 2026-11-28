"""Approval, frozen job inputs and reconciliation with the Studio queue."""
from __future__ import annotations

import hashlib
import json
import random
import re
import secrets
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Annotated, Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from ..errors import StateConflict
from ..generation.catalog import GPUS, IMAGE_MODELS, LIMITS
from ..generation.video_reference import probe_reference_video
from ..media import image_thumbnail
from .agent_plugins import private_dir
from .harness_errors import HarnessError, HarnessErrorCode
from .harness_store import dump
from .shot_service import ReferenceUsed, RoundId

OPERATION_ID = r"op_[a-f0-9]{24}"
SCOPE_KEY = r"(?:wr_[A-Za-z0-9_-]{4,48}|cr_[a-f0-9]{32}|once-[a-f0-9]{32})"
OperationState = Literal["awaiting_approval", "queued", "running", "partial", "done", "failed", "canceled", "unknown"]
ItemState = Literal["awaiting_approval", "queued", "running", "done", "failed", "canceled", "unknown"]
JOB_STATES = {"queued": "queued", "running": "running", "done": "done", "error": "failed", "canceled": "canceled"}
TERMINAL = {"done", "failed", "canceled"}
ACTIVE = {"queued", "running", "unknown"}
OPERATION_TOOLS = {"image": "submit_image", "video": "submit_video"}


class OperationItem(BaseModel):
    item_key: str
    seq: int
    job_id: str | None
    state: ItemState
    round_id: str | None
    error_code: HarnessErrorCode | None = None


class Operation(BaseModel):
    operation_id: str
    scope_key: str
    kind: Literal["image", "video"]
    state: OperationState
    total: int
    done: int
    model: str
    width: int
    height: int
    num_frames: int | None = None
    references: list[ReferenceUsed]
    results: list[ReferenceUsed]
    items: list[OperationItem]
    needs_compute: bool
    created_at: int
    updated_at: int


class OperationList(BaseModel):
    operations: list[Operation]


class RetryItems(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_keys: list[str] | None = Field(default=None, min_length=1, max_length=4)


MaskId = Annotated[str, Field(pattern=r"^mk_[a-f0-9]{24}$")]
Unit = Annotated[float, Field(ge=0, le=1, strict=True, allow_inf_nan=False)]


class MaskStroke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    size: Annotated[float, Field(gt=0, le=1, strict=True, allow_inf_nan=False)]
    points: list[tuple[Unit, Unit]] = Field(min_length=1, max_length=12000)


class MaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: RoundId
    strokes: list[MaskStroke] = Field(min_length=1, max_length=256)


class MaskRecord(MaskInput):
    mask_id: MaskId
    created_at: int
    expires_at: int


def _now():
    return int(time.time())


def round_media(store, rid, kind):
    found = store.media_path(rid)
    if not found or found[0] != kind:
        raise HarnessError("media_invalid")
    return found[1]


def _image(path: Path):
    try:
        if not 0 < path.stat().st_size <= LIMITS["upload_max_mb"] * 1048576:
            raise ValueError("size")
        with Image.open(path, formats=("PNG", "JPEG", "WEBP")) as img:
            img.verify()
        return path.read_bytes()
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HarnessError("media_invalid") from exc


def _state(items):
    states = {item["state"] for item in items}
    for state in ("awaiting_approval", "running", "queued"):
        if state in states:
            return state
    if states == {"done"}:
        return "done"
    if "done" in states:
        return "partial"
    if "unknown" in states:
        return "unknown"
    return "failed" if "failed" in states else "canceled"


class Operations:
    def __init__(self, store, studio):
        self.store = store
        self.studio = studio
        self.gallery = studio.store
        self.inputs = store.path.parent / "operation-inputs"

    def create_mask(self, body: MaskInput):
        data = body.model_dump()
        if sum(len(stroke["points"]) for stroke in data["strokes"]) > 12000:
            raise HarnessError("invalid_argument")
        with self.gallery._lock:
            _image(round_media(self.gallery, data["source_id"], "image"))
        now = _now()
        record = dict(data, mask_id="mk_" + secrets.token_hex(12), created_at=now, expires_at=now + 7 * 86400)
        with self.store.transaction() as db:
            db.execute("INSERT INTO masks VALUES (?, ?, ?, ?, ?)", (
                record["mask_id"], body.source_id, dump(data["strokes"]), now, record["expires_at"],
            ))
        return record

    def get_mask(self, mask_id):
        with self.store.transaction() as db:
            row = db.execute("SELECT * FROM masks WHERE mask_id=? AND expires_at>?", (mask_id, _now())).fetchone()
        if not row:
            raise HarnessError("not_found")
        return {k: row[k] for k in ("mask_id", "source_id", "created_at", "expires_at")} | {
            "strokes": json.loads(row["strokes_json"]),
        }

    def prepare(self, payload, mask_id=None):
        with self.studio._lock, self.gallery._lock:
            p, refs, last, video = self._sources(payload, mask_id)
            return p, refs, last, video

    def _sources(self, payload, mask_id):
        studio, gallery = self.studio, self.gallery
        p = dict(payload)
        mode = p["mode"]
        if mask_id:
            if mode != "image" or p.get("chain") or p.get("reference_round_ids"):
                raise HarnessError("invalid_argument")
            mask = self.get_mask(mask_id)
            p.update(edit_mask={k: mask[k] for k in ("source_id", "strokes")}, has_image=True)
        refs = []
        last = video = None
        current = studio.refs_report()
        if p.get("edit_mask"):
            rid = p["edit_mask"]["source_id"]
            refs = [(rid, round_media(gallery, rid, "image"))]
            p["reference_round_ids"] = [rid]
        elif p.get("chain"):
            latest = gallery.latest("image")
            rid = latest["id"] if latest else None
            refs = [(rid, round_media(gallery, rid, "image"))] if rid else []
            p.update(chain_resolved=True, chain_from=rid)
        elif p["has_image"]:
            if ids := p.get("reference_round_ids"):
                refs = [(rid, round_media(gallery, rid, "image")) for rid in ids]
            else:
                refs = [(item.get("source", "").removeprefix("round:"), studio.ref_item_file(item["id"]))
                        for item in current["items"]]
                ids = [rid for rid, _ in refs if gallery.valid_id(rid)]
                if ids:
                    p["reference_round_ids"] = ids
            if not refs:
                raise HarnessError("media_invalid")
        if p.get("workflow") == "fl2va":
            refs = refs[:1]
            if "reference_round_ids" in p:
                p["reference_round_ids"] = p["reference_round_ids"][:1]
        if p.get("has_last_image"):
            rid = p.get("last_frame_round_id")
            last = (rid or current["last"]["source"].removeprefix("round:"),
                    round_media(gallery, rid, "image") if rid else studio.ref_file("last"))
        if task := p.get("video_task"):
            rid, slot = p.pop("video_round_id", None), p.pop("video_reference_id", None)
            if rid:
                path, source = round_media(gallery, rid, "video"), f"round:{rid}"
            else:
                report = current.get("video")
                slot = slot or (report and report["id"])
                path = studio.video_ref_file(slot)
                source = report["source"] if report and report["id"] == slot else ""
            try:
                if not path or not 0 < path.stat().st_size <= LIMITS["video_upload_max_mb"] * 1048576:
                    raise ValueError("size")
                probe_reference_video(path)
            except (OSError, ValueError) as exc:
                raise HarnessError("media_invalid") from exc
            if task == "motion" and not refs:
                raise HarnessError("media_invalid")
            p["video_reference_source"] = source
            video = path
        if len(refs) > 1 and p.get("engine") == "comfyui" and p["comfy"]["template"] != "qwen-image-2.1":
            raise HarnessError("media_invalid")
        if any(not path for _, path in refs):
            raise HarnessError("media_invalid")
        p.update(has_image=bool(refs), ref_count=len(refs))
        return p, [(rid, _image(path)) for rid, path in refs], (last[0], _image(last[1])) if last else None, video

    def _freeze(self, operation_id, refs, last, video):
        if not (refs or last or video):
            return {"count": 0, "last": False, "video": False, "references": []}
        base = private_dir(self.inputs)
        folder = private_dir(base / operation_id)
        pictures = []
        for slot, (rid, blob) in [*((f"image{n}", value) for n, value in enumerate(refs)), *([("last", last)] if last else [])]:
            file = folder / f"{slot}.bin"
            file.write_bytes(blob)
            file.chmod(0o600)
            thumb = folder / f"{slot}.jpg"
            with Image.open(file) as img:
                image_thumbnail(img, thumb)
            thumb.chmod(0o600)
            record = self.gallery.get(rid) if self.gallery.valid_id(rid) else None
            pictures.append({"id": slot, "label": str((record or {}).get("prompt") or "")[:80],
                             "thumb": f"api/workflows/agent/operations/{operation_id}/refs/{slot}"})
        if video:
            path = folder / "video.mp4"
            shutil.copyfile(video, path)
            path.chmod(0o600)
        return {"count": len(refs), "last": bool(last), "video": bool(video), "references": pictures}

    def ref_thumb(self, operation_id, slot):
        path = self.inputs / operation_id / (slot + ".jpg")
        if re.fullmatch(OPERATION_ID, operation_id) and re.fullmatch(r"image[0-5]|last", slot) and path.is_file():
            with self.store.transaction() as db:
                if db.execute("SELECT 1 FROM operations WHERE operation_id=?", (operation_id,)).fetchone():
                    return path
        raise HarnessError("not_found")

    def create(self, scope, key, payload, mask_id=None):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", key):
            raise HarnessError("invalid_argument")
        if not re.fullmatch(SCOPE_KEY, scope):
            raise HarnessError("invalid_argument")
        mode = payload["mode"]
        tool = OPERATION_TOOLS[mode]
        spec = dict(payload, mask_id=mask_id)
        fingerprint = hashlib.sha256(json.dumps(spec, sort_keys=True, allow_nan=False).encode()).hexdigest()
        with self.studio._lock, self.gallery._lock:
            with self.store.transaction() as db:
                existing = db.execute("SELECT operation_id,spec_hash FROM operations WHERE scope_key=? AND tool=? AND idempotency_key=?",
                                      (scope, tool, key)).fetchone()
            if existing:
                if existing["spec_hash"] != fingerprint:
                    raise HarnessError("invalid_argument")
                return self.get(existing["operation_id"])
            operation_id = "op_" + secrets.token_hex(12)
            p, refs, last, video = self._sources(payload, mask_id)
            try:
                frozen = self._freeze(operation_id, refs, last, video)
                count = p.pop("count")
                seed = p["seed"] if p["seed"] >= 0 else random.randint(0, 2**31 - 2)
                now = _now()
                with self.store.transaction() as db:
                    db.execute("INSERT INTO operations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                        operation_id, scope, tool, key, fingerprint, "awaiting_approval", dump(spec), dump(frozen), "[]", "[]", None, None, now, now,
                    ))
                    db.executemany("INSERT INTO operation_items VALUES (?, ?, ?, ?, NULL, ?, NULL, NULL, ?)", (
                        (operation_id, str(i + 1), i + 1, dump(dict(p, seed=(seed + i) % (2**31 - 1))), "awaiting_approval", now)
                        for i in range(count)
                    ))
            except Exception:
                shutil.rmtree(self.inputs / operation_id, ignore_errors=True)
                raise
            return self.get(operation_id)

    def _rows(self, db, operation_id):
        op = db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        if not op:
            raise HarnessError("not_found")
        items = [dict(row) for row in db.execute("SELECT * FROM operation_items WHERE operation_id=? ORDER BY seq", (operation_id,))]
        return dict(op), items

    def _item_update(self, db, job_id, state, round_id=None):
        return db.execute("""UPDATE operation_items SET state=?, round_id=?, error=?, updated_at=?
                            WHERE job_id=? AND state NOT IN ('done','failed','canceled') RETURNING operation_id""",
                          (state, round_id, "internal_error" if state == "failed" else None, _now(), job_id)).fetchone()

    def _aggregate(self, db, op, items):
        state = _state(items)
        jobs = [r["job_id"] for r in items if r["job_id"]]
        output = [r["round_id"] for r in items if r["round_id"]]
        error = "internal_error" if any(r["state"] == "failed" for r in items) else None
        updated = max(r["updated_at"] for r in items)
        db.execute("""UPDATE operations SET state=?,executor_ids_json=?,result_json=?,error_code=?,updated_at=?
                      WHERE operation_id=?""", (state, dump(jobs), dump(output), error, updated, op["operation_id"]))
        if state in {"done", "canceled"}:
            self._cleanup_frozen_binaries(op["operation_id"])
        return dict(op, state=state, updated_at=updated)

    def _cleanup_frozen_binaries(self, operation_id):
        folder = self.inputs / operation_id
        try:
            if not folder.is_dir():
                return
            for path in folder.iterdir():
                if path.suffix in (".bin", ".mp4"):
                    path.unlink(missing_ok=True)
        except OSError as exc:
            self.studio.log(f"冻结素材清理失败 ({type(exc).__name__})")

    def _held_gpus(self):
        valid = {gpu["id"] for gpu in GPUS}
        held = []
        report = self.studio.colab.status_report(blocking=False) if hasattr(self.studio.colab, "status_report") else {}
        for session in (report.get("sessions") if isinstance(report, dict) else None) or ():
            gpu = str(session.get("gpu") or "").split()[0].upper()
            if gpu in valid and gpu not in held:
                held.append(gpu)
        if not held and (active := str(getattr(self.studio, "active_gpu", "") or "")):
            for part in active.split(","):
                gpu = part.strip().split()[0].upper() if part.strip() else ""
                if gpu in valid and gpu not in held:
                    held.append(gpu)
        return held

    def record_terminal(self, job):
        state = JOB_STATES.get(job.get("status"))
        jid = job["id"]
        if state not in TERMINAL or not re.fullmatch(r"j[a-f0-9]{24}", jid):
            return
        try:
            with self.store.transaction() as db:
                rid = job.get("round_id")
                if state == "failed" and not rid and "服务重启" in job.get("error", ""):
                    if asset := self._gallery_result(jid):
                        state, rid = "done", asset["id"]
                if row := self._item_update(db, jid, state, rid):
                    op, items = self._rows(db, row["operation_id"])
                    self._aggregate(db, op, items)
        except (sqlite3.Error, OSError) as exc:
            self.studio.log(f"操作状态写入失败 ({type(exc).__name__})")

    def _gallery_result(self, job_id):
        return next((asset for asset in self.gallery.list()["rounds"] if asset.get("job_id") == job_id), None)

    def _reconcile(self, db, operation_id):
        op, items = self._rows(db, operation_id)
        for item in items:
            if item["state"] not in ACTIVE or not item["job_id"]:
                continue
            job = self.studio.find_job(item["job_id"])
            state = JOB_STATES.get(job["status"], "unknown") if job else "unknown"
            if not job or (state == "failed" and not job.get("round_id") and "服务重启" in (job.get("error") or "")):
                recovered = self._gallery_result(item["job_id"])
                if recovered:
                    job, state = {"round_id": recovered["id"]}, "done"
            rid = job.get("round_id") if job else None
            if state != item["state"] or rid != item["round_id"]:
                self._item_update(db, item["job_id"], state, rid)
                item.update(state=state, round_id=rid, error="internal_error" if state == "failed" else None, updated_at=_now())
        if any(item["updated_at"] > op["updated_at"] for item in items) or _state(items) != op["state"]:
            op = self._aggregate(db, op, items)
        return op, items

    def _public(self, op, items):
        p = json.loads(items[0]["frozen_input_json"])
        model = p.get("model")
        if p["mode"] == "video":
            model = "MiniMax-H3"
        elif p.get("comfy"):
            model = p["comfy"]["diffusion"]["basename"]
        else:
            model = next((item["label"] for item in IMAGE_MODELS if item["id"] == model), model)
        results = []
        for item in items:
            if rid := item["round_id"]:
                asset = self.gallery.get(rid)
                if asset:
                    suffix = "/thumb" if asset.get("has_thumb") else ""
                    results.append({"id": rid, "thumb": f"api/rounds/{rid}{suffix}", "label": str(asset.get("prompt") or "")[:80]})
        return {**{k: op[k] for k in ("operation_id", "scope_key", "state", "created_at", "updated_at")},
                "kind": p["mode"], "total": len(items), "done": sum(item["state"] == "done" for item in items),
                "model": model, "width": p["width"], "height": p["height"], "num_frames": p.get("num_frames"),
                "references": json.loads(op["frozen_refs_json"])["references"], "results": results,
                "items": [{k: item[k] for k in ("item_key", "seq", "job_id", "state", "round_id")} | {"error_code": item["error"]} for item in items],
                "needs_compute": not self.studio.colab.has_credentials()}

    def get(self, operation_id, *, scope=None):
        with self.studio._lock, self.store.transaction() as db:
            op, items = self._reconcile(db, operation_id)
            if scope is not None and scope != op["scope_key"]:
                raise HarnessError("not_found")
            return self._public(op, items)

    def list(self, scope=None, limit=24):
        with self.studio._lock, self.store.transaction() as db:
            rows = db.execute("""SELECT operation_id FROM operations WHERE (? IS NULL OR scope_key=?)
                              ORDER BY created_at DESC,rowid DESC LIMIT ?""", (scope, scope, limit)).fetchall()
            return [self._public(*self._reconcile(db, row["operation_id"])) for row in rows]

    def for_job(self, job_id, *, scope=None):
        with self.store.transaction() as db:
            row = db.execute("SELECT operation_id FROM operation_items WHERE job_id=?", (job_id,)).fetchone()
        return self.get(row["operation_id"], scope=scope) if row else None

    def approve(self, operation_id):
        return self._submit(operation_id)

    def retry(self, operation_id, item_keys=None):
        return self._submit(operation_id, retry=True, item_keys=item_keys)

    def _submit(self, operation_id, *, retry=False, item_keys=None):
        studio = self.studio
        with studio._lock:
            with self.store.transaction() as db:
                op, items = self._reconcile(db, operation_id)
            if item_keys is not None and (len(set(item_keys)) != len(item_keys) or set(item_keys) - {i["item_key"] for i in items}):
                raise HarnessError("invalid_argument")
            target_state = "failed" if retry else "awaiting_approval"
            targets = [i for i in items if i["state"] == target_state and (item_keys is None or i["item_key"] in item_keys)]
            if not targets:
                return self._public(op, items)
            if not studio.colab.has_credentials():
                raise HarnessError("colab_unauthed")
            if len(studio._queue) + len(targets) > LIMITS["queue_max"]:
                raise HarnessError("queue_full")
            if studio._grabbing:
                raise HarnessError("busy")
            frozen = json.loads(op["frozen_refs_json"])
            folder = self.inputs / operation_id
            try:
                refs = [(folder / f"image{i}.bin").read_bytes() for i in range(frozen["count"])]
                last = (folder / "last.bin").read_bytes() if frozen["last"] else None
                video = folder / "video.mp4" if frozen["video"] else None
                if video and not video.is_file():
                    raise FileNotFoundError
            except OSError as exc:
                raise HarnessError("media_invalid") from exc
            held = self._held_gpus()
            jobs = []
            for item in targets:
                payload = dict(json.loads(item["frozen_input_json"]), operation_id=operation_id)
                if held:
                    preferred = payload.get("gpu")
                    pool = [preferred, *(g for g in held if g != preferred)] if preferred in held else list(held)
                    payload.update(gpu=pool[0], gpu_pool=pool)
                jobs.append(("j" + secrets.token_hex(12), payload))
            # Commit the reserved IDs before crossing into the durable queue. An ambiguous
            # restart reconciles those IDs and leaves unverified items unknown.
            with self.store.transaction() as db:
                for item, (job_id, _) in zip(targets, jobs, strict=True):
                    db.execute("""UPDATE operation_items SET job_id=?,state='unknown',error=NULL,updated_at=?
                                  WHERE operation_id=? AND item_key=?""", (job_id, _now(), operation_id, item["item_key"]))
                self._aggregate(db, *self._rows(db, operation_id))
            try:
                studio.enqueue_frozen(jobs, refs, last, video)
            except (StateConflict, ValueError, OSError) as exc:
                # The batch writer rolls back on an unsuccessful durable enqueue.
                with self.store.transaction() as db:
                    for item in targets:
                        db.execute("""UPDATE operation_items SET job_id=?,state=?,error=?,updated_at=?
                                      WHERE operation_id=? AND item_key=?""", (
                            item["job_id"], item["state"], item["error"], _now(), operation_id, item["item_key"],
                        ))
                    self._aggregate(db, *self._rows(db, operation_id))
                code = "busy" if isinstance(exc, StateConflict) else "media_invalid" if isinstance(exc, ValueError) else "internal_error"
                raise HarnessError(code) from exc
            return self.get(operation_id)

    def cancel(self, operation_id):
        with self.studio._lock:
            with self.store.transaction() as db:
                op, items = self._reconcile(db, operation_id)
                cancelable = [item["item_key"] for item in items if item["state"] in {"awaiting_approval", "unknown"}]
                if cancelable:
                    now = _now()
                    db.executemany(
                        "UPDATE operation_items SET state='canceled',updated_at=? WHERE operation_id=? AND item_key=?",
                        ((now, operation_id, key) for key in cancelable),
                    )
                    self._aggregate(db, *self._rows(db, operation_id))
            for item in items:
                if item["state"] in {"queued", "running"} and item["job_id"]:
                    self.studio.cancel_job(item["job_id"])
            return self.get(operation_id)
