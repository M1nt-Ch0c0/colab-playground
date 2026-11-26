#!/usr/bin/env python3
"""Gallery storage for Colab Studio.

Layout (all under ``<root>/out``):

    rounds/<id>.png | <id>.mp4     generated media (id = zero padded, monotonic, never reused)
    rounds/<id>.json               metadata (prompt, model, params, starred, created_at ...)
    rounds/<id>.thumb.jpg          optional thumbnail produced on the Colab side
    rounds/.seq                    last allocated id
    trash/<same files>             soft-deleted rounds, auto purged after TRASH_DAYS

Deleting a round moves it to ``trash/`` first; it can be restored until it is purged.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import struct
import threading
import time
from pathlib import Path
from typing import Callable, Iterable

ID_RE = re.compile(r"\d{3,7}")
MEDIA_RE = re.compile(r"(\d{3,7})\.(png|mp4)")
TRASH_DAYS = int(os.environ.get("QP_TRASH_DAYS", "7"))
META_KEEP = (
    "prompt", "prompt_template", "negative", "engine", "model", "comfy", "workflow", "gpu", "width", "height", "steps",
    "cfg", "seed", "num_frames", "loras", "has_image", "has_last_image", "chain",
    "duration_s", "boot_s", "infer_s", "job_id", "idea", "chain_from",
    "workflow_run_id", "workflow_step_id", "source_rounds", "transition",
)


def _size(n: int) -> str:
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{max(1, n // 1024)} KB"


def probe_image_dimensions(path: Path) -> tuple[int | None, int | None]:
    """Read pixel dimensions from PNG / JPEG / WebP headers using stdlib only."""
    try:
        with path.open("rb") as fh:
            head = fh.read(32)
            if len(head) < 12:
                return None, None
            if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 24:
                w, h = struct.unpack(">II", head[16:24])
                return int(w), int(h)
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                chunk = head[12:16]
                if chunk == b"VP8X" and len(head) >= 30:
                    return 1 + int.from_bytes(head[24:27], "little"), 1 + int.from_bytes(head[27:30], "little")
                if chunk == b"VP8L" and len(head) >= 25:
                    b0, b1, b2, b3 = head[21:25]
                    return 1 + (((b1 & 0x3F) << 8) | b0), 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
                if chunk == b"VP8 " and len(head) >= 30:
                    return int(struct.unpack("<H", head[26:28])[0] & 0x3FFF), int(struct.unpack("<H", head[28:30])[0] & 0x3FFF)
            if head[:2] == b"\xff\xd8":
                fh.seek(2)
                while True:
                    prefix = fh.read(1)
                    if not prefix:
                        break
                    if prefix != b"\xff":
                        continue
                    marker = fh.read(1)
                    while marker == b"\xff":
                        marker = fh.read(1)
                    if not marker:
                        break
                    m = marker[0]
                    if m in {0xD8, 0xD9, 0x01} or 0xD0 <= m <= 0xD7:
                        continue
                    seg_b = fh.read(2)
                    if len(seg_b) < 2:
                        break
                    seg_len = struct.unpack(">H", seg_b)[0]
                    if seg_len < 2:
                        break
                    if m in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                        sof = fh.read(5)
                        if len(sof) == 5:
                            h, w = struct.unpack(">HH", sof[1:5])
                            return int(w), int(h)
                        break
                    fh.seek(seg_len - 2, os.SEEK_CUR)
    except OSError:
        return None, None
    return None, None


class Store:
    def __init__(self, out_dir: Path, logger: Callable[[str], None]) -> None:
        self.out = out_dir
        self.rounds = out_dir / "rounds"
        self.trash = out_dir / "trash"
        self.log = logger
        self._lock = threading.RLock()
        self.rev = 1  # bumps on every gallery mutation; UI uses it to know when to reload
        self.rounds.mkdir(parents=True, exist_ok=True)
        self.trash.mkdir(parents=True, exist_ok=True)

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def valid_id(rid: str) -> bool:
        return bool(ID_RE.fullmatch(rid or ""))

    def _bump(self) -> None:
        self.rev += 1

    @staticmethod
    def _media_in(folder: Path) -> dict[str, Path]:
        found: dict[str, Path] = {}
        if not folder.exists():
            return found
        for p in folder.iterdir():
            m = MEDIA_RE.fullmatch(p.name)
            if m:
                found[m.group(1)] = p
        return found

    @staticmethod
    def _files_for(folder: Path, rid: str) -> list[Path]:
        names = [f"{rid}.png", f"{rid}.mp4", f"{rid}.json", f"{rid}.thumb.jpg"]
        return [folder / n for n in names if (folder / n).exists()]

    @staticmethod
    def _read_meta(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _write_meta(path: Path, meta: dict) -> None:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def _item(self, folder: Path, rid: str, media: Path) -> dict:
        meta = self._read_meta(folder / f"{rid}.json")
        st = media.stat()
        kind = "video" if media.suffix == ".mp4" else "image"
        thumb = folder / f"{rid}.thumb.jpg"
        size_bytes = st.st_size + (thumb.stat().st_size if thumb.exists() else 0)
        item = {
            "id": rid,
            "kind": kind,
            "prompt": str(meta.get("prompt") or ""),
            "model": meta.get("model") or ("MiniMaxAI/MiniMax-H3" if kind == "video" else ""),
            "created_at": int(meta.get("created_at") or st.st_mtime),
            "bytes": size_bytes,
            "starred": bool(meta.get("starred")),
            "has_thumb": thumb.exists(),
            "mtime": int(st.st_mtime),
        }
        for key in META_KEEP:
            if key in meta and key not in item:
                item[key] = meta[key]
        if kind == "image" and (not item.get("width") or not item.get("height")):
            pw, ph = probe_image_dimensions(media)
            if pw and ph:
                item["width"] = pw
                item["height"] = ph
        if "deleted_at" in meta:
            item["deleted_at"] = int(meta["deleted_at"])
        return item

    # ── id allocation ─────────────────────────────────────────────────

    def _next_id(self) -> str:
        seq_file = self.rounds / ".seq"
        last = 0
        try:
            last = int(seq_file.read_text(encoding="utf-8").strip() or 0)
        except (OSError, ValueError):
            last = 0
        existing = [int(r) for r in self._media_in(self.rounds)] + [
            int(r) for r in self._media_in(self.trash)
        ]
        nxt = max([last, *existing]) + 1
        tmp = seq_file.with_name(".seq.tmp")
        tmp.write_text(str(nxt), encoding="utf-8")
        os.replace(tmp, seq_file)
        return f"{nxt:03d}"

    # ── queries ───────────────────────────────────────────────────────

    def list(
        self,
        kind: str = "",
        starred: bool | None = None,
        q: str = "",
        order: str = "desc",
        offset: int = 0,
        limit: int = 0,
    ) -> dict:
        with self._lock:
            items = [self._item(self.rounds, rid, p) for rid, p in self._media_in(self.rounds).items()]
        stats = {
            "count": len(items),
            "images": sum(1 for i in items if i["kind"] == "image"),
            "videos": sum(1 for i in items if i["kind"] == "video"),
            "starred": sum(1 for i in items if i["starred"]),
            "bytes": sum(i["bytes"] for i in items),
        }
        if kind in {"image", "video"}:
            items = [i for i in items if i["kind"] == kind]
        if starred is not None:
            items = [i for i in items if i["starred"] == starred]
        if q:
            ql = q.lower()
            ql_num = ql.lstrip("0")
            items = [
                i for i in items
                if ql in i["prompt"].lower()
                or ql in str(i.get("model") or "").lower()
                or ql in i["id"]
                or (ql_num and ql_num == i["id"].lstrip("0"))
            ]
        items.sort(key=lambda i: int(i["id"]), reverse=(order != "asc"))
        total = len(items)
        if offset:
            items = items[offset:]
        if limit:
            items = items[:limit]
        return {"rounds": items, "total": total, "stats": stats, "rev": self.rev}

    def get(self, rid: str) -> dict | None:
        if not self.valid_id(rid):
            return None
        media = self.media_path(rid)
        if not media:
            return None
        item = self._item(self.rounds, rid, media[1])
        item["meta"] = self._read_meta(self.rounds / f"{rid}.json")
        return item

    def media_path(self, rid: str, trash: bool = False) -> tuple[str, Path] | None:
        if not self.valid_id(rid):
            return None
        folder = self.trash if trash else self.rounds
        for ext, kind in ((".mp4", "video"), (".png", "image")):
            p = folder / f"{rid}{ext}"
            if p.exists():
                return kind, p
        return None

    def thumb_path(self, rid: str, trash: bool = False) -> Path | None:
        if not self.valid_id(rid):
            return None
        p = (self.trash if trash else self.rounds) / f"{rid}.thumb.jpg"
        return p if p.exists() else None

    def latest(self, kind: str = "") -> dict | None:
        with self._lock:
            media = self._media_in(self.rounds)
            for rid in sorted(media, key=int, reverse=True):
                p = media[rid]
                k = "video" if p.suffix == ".mp4" else "image"
                if not kind or k == kind:
                    return self._item(self.rounds, rid, p)
        return None

    def storage_stats(self) -> dict:
        with self._lock:
            rounds = self.list()["stats"]
            trash = self.trash_list()
            disk = shutil.disk_usage(self.out)
        return {
            "rounds": rounds,
            "trash": {
                "count": trash["count"],
                "bytes": trash["bytes"],
                "retention_days": trash["retention_days"],
            },
            "total_bytes": rounds["bytes"] + trash["bytes"],
            "disk_free_bytes": int(disk.free),
            "disk_total_bytes": int(disk.total),
        }

    # ── mutations ─────────────────────────────────────────────────────

    def save(self, src: Path, kind: str, meta: dict, thumb: Path | None = None) -> str:
        with self._lock:
            rid = self._next_id()
            ext = ".mp4" if kind == "video" else ".png"
            dest = self.rounds / f"{rid}{ext}"
            shutil.copyfile(src, dest)
            if thumb is not None and thumb.exists() and thumb.stat().st_size > 64:
                shutil.copyfile(thumb, self.rounds / f"{rid}.thumb.jpg")
            data = {k: v for k, v in meta.items() if v is not None}
            data["kind"] = kind
            data["created_at"] = int(time.time())
            data.setdefault("starred", False)
            if kind == "image" and (not data.get("width") or not data.get("height")):
                pw, ph = probe_image_dimensions(dest)
                if pw and ph:
                    data["width"] = pw
                    data["height"] = ph
            self._write_meta(self.rounds / f"{rid}.json", data)
            latest = self.out / ("latest.mp4" if kind == "video" else "latest.png")
            shutil.copyfile(dest, latest)
            self._bump()
        return rid

    def set_star(self, rid: str, starred: bool) -> bool:
        with self._lock:
            if not self.media_path(rid):
                return False
            path = self.rounds / f"{rid}.json"
            meta = self._read_meta(path)
            meta["starred"] = bool(starred)
            self._write_meta(path, meta)
            self._bump()
            return True

    def _refresh_latest(self) -> None:
        for kind, ext, fname in (("image", ".png", "latest.png"), ("video", ".mp4", "latest.mp4")):
            latest = self.latest(kind)
            target = self.out / fname
            if latest:
                src = self.rounds / f"{latest['id']}{ext}"
                if src.exists():
                    shutil.copyfile(src, target)
            else:
                target.unlink(missing_ok=True)

    def delete(self, ids: Iterable[str], permanent: bool = False) -> dict:
        deleted, missing, freed = [], [], 0
        with self._lock:
            for rid in dict.fromkeys(ids):
                rid = str(rid)
                files = self._files_for(self.rounds, rid) if self.valid_id(rid) else []
                if not any(f.suffix in {".png", ".mp4"} for f in files):
                    missing.append(rid)
                    continue
                for f in files:
                    freed += f.stat().st_size
                if permanent:
                    for f in files:
                        f.unlink(missing_ok=True)
                else:
                    meta_path = self.rounds / f"{rid}.json"
                    meta = self._read_meta(meta_path)
                    meta["deleted_at"] = int(time.time())
                    self._write_meta(meta_path, meta)
                    for f in self._files_for(self.rounds, rid):
                        os.replace(f, self.trash / f.name)
                deleted.append(rid)
            if deleted:
                self._refresh_latest()
                self._bump()
        if deleted:
            self.log(
                f"{'永久删除' if permanent else '已移入回收站'} {len(deleted)} 个作品："
                + "、".join(deleted[:12]) + ("…" if len(deleted) > 12 else "")
                + f"（{_size(freed)}）"
            )
        return {"deleted": deleted, "missing": missing, "bytes": freed, "permanent": permanent}

    def cleanup_plan(
        self,
        older_than_days: float | None,
        keep_latest: int | None,
        kind: str = "",
        include_starred: bool = False,
        max_mb: float | None = None,
    ) -> list[dict]:
        items = self.list(kind=kind)["rounds"]  # newest first
        protected: set[str] = set()
        if keep_latest is not None and keep_latest > 0:
            protected = {i["id"] for i in items[:keep_latest]}
        cutoff = time.time() - older_than_days * 86400 if older_than_days is not None else None

        if max_mb is not None and older_than_days is None and keep_latest is None:
            limit_bytes = int(max(0.0, max_mb) * 1048576)
            used = 0
            if not include_starred:
                used = sum(i["bytes"] for i in items if i["starred"])
            plan = []
            for it in items:
                if it["starred"] and not include_starred:
                    continue
                if used + it["bytes"] <= limit_bytes:
                    used += it["bytes"]
                else:
                    plan.append(it)
            return plan

        plan = []
        for it in items:
            if it["id"] in protected:
                continue
            if it["starred"] and not include_starred:
                continue
            if cutoff is not None and it["created_at"] >= cutoff:
                continue
            plan.append(it)
        return plan

    # ── trash ─────────────────────────────────────────────────────────

    def trash_list(self) -> dict:
        with self._lock:
            items = [self._item(self.trash, rid, p) for rid, p in self._media_in(self.trash).items()]
        now = time.time()
        for it in items:
            deleted_at = it.get("deleted_at") or it["mtime"]
            it["deleted_at"] = int(deleted_at)
            it["purge_at"] = int(deleted_at + TRASH_DAYS * 86400)
        items.sort(key=lambda i: i["deleted_at"], reverse=True)
        return {
            "items": items,
            "count": len(items),
            "bytes": sum(i["bytes"] for i in items),
            "retention_days": TRASH_DAYS,
            "now": int(now),
        }

    def restore(self, ids: Iterable[str]) -> dict:
        restored, missing = [], []
        with self._lock:
            for rid in dict.fromkeys(ids):
                rid = str(rid)
                files = self._files_for(self.trash, rid) if self.valid_id(rid) else []
                if not any(f.suffix in {".png", ".mp4"} for f in files):
                    missing.append(rid)
                    continue
                for f in files:
                    os.replace(f, self.rounds / f.name)
                meta_path = self.rounds / f"{rid}.json"
                meta = self._read_meta(meta_path)
                meta.pop("deleted_at", None)
                self._write_meta(meta_path, meta)
                restored.append(rid)
            if restored:
                self._refresh_latest()
                self._bump()
        if restored:
            self.log(f"已从回收站恢复 {len(restored)} 个作品：" + "、".join(restored[:12]))
        return {"restored": restored, "missing": missing}

    def purge(self, ids: Iterable[str] | None = None, older_than_days: float | None = None) -> dict:
        purged, freed = [], 0
        with self._lock:
            listing = self.trash_list()["items"]
            wanted = None if ids is None else {str(i) for i in ids}
            cutoff = time.time() - older_than_days * 86400 if older_than_days is not None else None
            for it in listing:
                if wanted is not None and it["id"] not in wanted:
                    continue
                if cutoff is not None and it["deleted_at"] > cutoff:
                    continue
                for f in self._files_for(self.trash, it["id"]):
                    freed += f.stat().st_size
                    f.unlink(missing_ok=True)
                purged.append(it["id"])
        if purged:
            self.log(f"回收站已彻底删除 {len(purged)} 个作品（释放 {_size(freed)}）")
        return {"purged": purged, "bytes": freed}

    def auto_purge(self) -> None:
        try:
            self.purge(older_than_days=TRASH_DAYS)
        except Exception as exc:  # never let housekeeping crash the server
            self.log(f"回收站自动清理失败：{exc}")
