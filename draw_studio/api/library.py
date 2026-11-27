import math
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field

from ..generation.catalog import LIMITS
from ..media import image_crop, import_media, video_clip, video_frame
from .core import IMAGE_BODY, IMMUTABLE, Raw, State, flag, image_type, media_file, media_route, readable

router = APIRouter(prefix="/api", tags=["作品库与参考图"])


def ids(body: dict) -> list[str]:
    values = body.get("ids")
    if not isinstance(values, list) or not 1 <= len(values) <= 2000:
        raise ValueError("ids 必须是非空数组，一次最多处理 2000 个")
    return [str(i) for i in values]


@readable(router, "/storage")
def storage(s: State):
    return s.store.storage_stats()


@readable(router, "/rounds")
def rounds(s: State, kind: str = "", starred: bool | None = None, q: str = "", order: str = "desc",
           offset: int = 0, limit: int = 0):
    return s.store.list(kind=kind, starred=starred, q=q.strip(), order=order,
                        offset=max(0, offset), limit=max(0, min(1000, limit)))


class FrameRequest(BaseModel):
    position: Literal["first", "last", "time"] = "first"
    time_s: float = 0


class ClipRequest(BaseModel):
    start_s: float
    end_s: float
    mute: bool = False


class CropRequest(BaseModel):
    x: int = Field(ge=0, strict=True)
    y: int = Field(ge=0, strict=True)
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)


@router.post("/rounds/import", openapi_extra={"requestBody": {"required": True, "content": {
    mime: {"schema": {"type": "string", "format": "binary"}} for mime in ("image/png", "image/jpeg", "image/webp", "video/mp4")
}}})
def import_round(raw: Raw, s: State, kind: Literal["image", "video"], name: str = ""):
    limit = LIMITS["video_upload_max_mb" if kind == "video" else "upload_max_mb"]
    if not raw or len(raw) > limit * 1048576:
        raise HTTPException(413, f"素材为空或超过 {limit} MB")
    return {"id": import_media(s.store, raw, kind, name)}


def source_media(s, rid: str, kind: Literal["image", "video"]) -> Path:
    found = s.store.media_path(rid)
    if not found:
        raise HTTPException(404, "原素材已移除")
    if found[0] != kind:
        raise ValueError("请选择一个图片作品" if kind == "image" else "请选择一个视频作品")
    return found[1]


@router.post("/rounds/{rid}/crop")
def crop_round(rid: str, body: CropRequest, s: State):
    return {"id": image_crop(s.store, rid, source_media(s, rid, "image"), **body.model_dump())}


@router.post("/rounds/{rid}/frame")
def extract_frame(rid: str, body: FrameRequest, s: State):
    return {"id": video_frame(s.store, rid, source_media(s, rid, "video"), body.position, body.time_s)}


@router.post("/rounds/{rid}/clip")
def extract_clip(rid: str, body: ClipRequest, s: State):
    return {"id": video_clip(s.store, rid, source_media(s, rid, "video"), body.start_s, body.end_s, body.mute)}


@router.post("/rounds/delete")
def delete_rounds(body: dict, s: State):
    return s.store.delete(ids(body), permanent=flag(body.get("permanent")))


@router.post("/rounds/star")
def star_rounds(body: dict, s: State):
    starred = flag(body.get("starred", True))
    return {"ok": True, "updated": [i for i in ids(body) if s.store.set_star(i, starred)], "starred": starred}


@router.post("/rounds/cleanup")
def cleanup(body: dict, s: State):
    try:
        days, keep, mb = [cast(body[k]) if body.get(k) not in (None, "") else None for k, cast in
                          (("older_than_days", float), ("keep_latest", int), ("max_mb", float))]
    except (TypeError, ValueError) as exc:
        raise ValueError("older_than_days / keep_latest / max_mb 必须是数字") from exc
    values = [v for v in (days, keep, mb) if v is not None]
    if not values or any(v < 0 or not math.isfinite(v) for v in values):
        raise ValueError("至少指定一个有效的非负清理条件")
    if mb is not None and (days is not None or keep is not None):
        raise ValueError("空间上限不能和时间或保留数量条件同时使用")
    filters = dict(older_than_days=days, keep_latest=keep, kind=body.get("kind") or "",
                   include_starred=flag(body.get("include_starred")), max_mb=mb)
    dry_run = flag(body.get("dry_run"))
    if dry_run:
        plan = s.store.cleanup_plan(**filters)
        deleted = {}
    else:
        expected = body.get("expected_ids")
        if not isinstance(expected, list) or not all(isinstance(i, str) and s.store.valid_id(i) for i in expected):
            raise ValueError("请先预览，并提交预览返回的 expected_ids")
        plan, applied = s.store.apply_cleanup(expected, **filters, permanent=flag(body.get("permanent")))
        deleted = {"deleted": applied["deleted"], "permanent": applied["permanent"]}
    return {"dry_run": dry_run, "matched": [item["id"] for item in plan], "count": len(plan),
            "bytes": sum(item["bytes"] for item in plan), **deleted}


def serve_round(request: Request, found: tuple[str, Path] | None, **options):
    if not found:
        raise HTTPException(404, "作品不存在")
    kind, path = found
    return media_file(request, path, "video/mp4" if kind == "video" else "image/png", **options)


@media_route(router, "/rounds/{rid}", "image/png", "video/mp4")
def round_media(rid: str, request: Request, s: State, download: bool = False):
    found = s.store.media_path(rid)
    filename = f"colab-studio-{rid}{found[1].suffix}" if found and download else None
    return serve_round(request, found, cache=IMMUTABLE, download=filename)


@media_route(router, "/rounds/{rid}/thumb", "image/jpeg")
def round_thumb(rid: str, request: Request, s: State):
    return media_file(request, s.store.thumb_path(rid), "image/jpeg", IMMUTABLE)


@readable(router, "/rounds/{rid}/meta")
def round_meta(rid: str, s: State):
    item = s.store.get(rid)
    if not item:
        raise HTTPException(404, "作品不存在")
    return item


@router.delete("/rounds/{rid}")
@router.post("/rounds/{rid}/delete")
def delete_round(rid: str, request: Request, s: State, permanent: bool | None = None,
                 body: dict = Body(default_factory=dict)):
    purge = permanent if request.method == "DELETE" and permanent is not None else flag(body.get("permanent"))
    result = s.store.delete([rid], permanent=purge)
    if not result["deleted"]:
        raise HTTPException(404, "作品不存在")
    return result


@router.post("/rounds/{rid}/star")
@router.patch("/rounds/{rid}/star")
def star_round(rid: str, s: State, body: dict = Body(default_factory=dict)):
    starred = flag(body.get("starred", True))
    if not s.store.set_star(rid, starred):
        raise HTTPException(404, "作品不存在")
    return {"ok": True, "id": rid, "starred": starred}


@router.post("/rounds/{rid}/use")
def use_round(rid: str, s: State, slot: str = "first", body: dict = Body(default_factory=dict)):
    target = body.get("slot") or slot
    if target not in ("first", "last", "video"):
        raise ValueError("未知的参考素材位置")
    try:
        s.studio.use_round(rid, target, append=flag(body.get("append")))
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc
    return {"ok": True, "slot": target, "references": s.studio.refs_report()}


@readable(router, "/trash")
def trash(s: State):
    return s.store.trash_list()


@router.post("/trash/restore")
def restore(body: dict, s: State):
    return s.store.restore(ids(body))


@router.post("/trash/purge")
def purge(body: dict, s: State):
    return s.store.purge(None if flag(body.get("all")) else ids(body))


@media_route(router, "/trash/{rid}/thumb", "image/jpeg")
def trash_thumb(rid: str, request: Request, s: State):
    return media_file(request, s.store.thumb_path(rid, trash=True), "image/jpeg")


@media_route(router, "/trash/{rid}", "image/png", "video/mp4")
def trash_media(rid: str, request: Request, s: State):
    return serve_round(request, s.store.media_path(rid, trash=True))


def target_slot(request: Request, slot: str) -> str:
    return "last" if slot == "last" or request.url.path.endswith("/last-frame") else "first"


@media_route(router, "/video-reference", "video/mp4")
def video_reference(id: str, request: Request, s: State):
    return media_file(request, s.studio.video_ref_file(id), "video/mp4")


@router.post("/video-reference", openapi_extra={"requestBody": {"required": True, "content": {
    "video/mp4": {"schema": {"type": "string", "format": "binary"}},
}}})
def set_video_reference(raw: Raw, s: State):
    s.studio.set_video_ref(raw, "upload")
    return {"ok": True, "references": s.studio.refs_report()}


@router.delete("/video-reference")
def clear_video_reference(id: str, s: State):
    s.studio.clear_video_ref(id)
    return {"ok": True, "references": s.studio.refs_report()}


@media_route(router, "/reference", "image/png", "image/jpeg", "image/webp")
@media_route(router, "/last-frame", "image/png", "image/jpeg", "image/webp")
def reference(request: Request, s: State, slot: str = "first", id: str = ""):
    target = target_slot(request, slot)
    path = s.studio.ref_item_file(id) if id and target == "first" else s.studio.ref_file(target)
    if not path or not path.exists():
        raise HTTPException(404, "还没有设置")
    return media_file(request, path, image_type(path))


@router.delete("/reference")
@router.delete("/last-frame")
def clear_reference(request: Request, s: State, slot: str = "first", id: str = ""):
    target = target_slot(request, slot)
    if id and target == "first":
        if not s.studio.remove_ref(id):
            raise HTTPException(404, "未找到该参考图")
    else:
        s.studio.clear_ref(target)
    return {"ok": True, "references": s.studio.refs_report()}


@router.post("/reference", openapi_extra=IMAGE_BODY)
@router.post("/last-frame", openapi_extra=IMAGE_BODY)
def set_reference(request: Request, raw: Raw, s: State, slot: str = "first", id: str = "", append: bool = False):
    target = target_slot(request, slot)
    if not 32 <= len(raw) <= LIMITS["upload_max_mb"] * 1048576:
        raise ValueError(f"图片为空或超过 {LIMITS['upload_max_mb']}MB")
    if not (raw.startswith(b"\x89PNG") or raw.startswith(b"\xff\xd8") or (raw.startswith(b"RIFF") and raw[8:12] == b"WEBP")):
        raise ValueError("只接受 PNG、JPEG 或 WebP 图片")
    item_id = ""
    if target == "last":
        s.studio.set_ref(target, raw, "upload")
    elif append:
        item_id = s.studio.add_ref(raw, "upload")["id"]
    elif id:
        item_id = s.studio.replace_ref(id, raw, "upload")["id"]
    else:
        s.studio.set_ref(target, raw, "upload")
        item_id = s.studio.refs_report()["items"][0]["id"]
    return {"ok": True, "slot": target, "id": item_id, "bytes": len(raw), "references": s.studio.refs_report()}


@router.post("/use-latest-image")
def use_latest(s: State):
    latest = s.store.latest("image")
    if not latest:
        raise ValueError("还没有生成过图片")
    s.studio.use_round(latest["id"], "first")
    return {"ok": True, "id": latest["id"]}


@media_route(router, "/image", "image/png")
def latest(request: Request, s: State):
    return media_file(request, s.store.out / "latest.png", "image/png")
