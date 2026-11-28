"""Creative only adapters for media, references, presets and generation."""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, model_validator

from .. import media
from ..errors import StateConflict
from ..generation.catalog import COMFY_BUILTIN_PRESETS, LIMITS, STUDIO_BUILTIN_PRESETS
from ..generation.parameters import normalize_job, normalize_loras, parse_model_link
from .harness_errors import HarnessError
from .operation_service import MaskId, MaskInput, round_media
from .shot_service import RoundId

Mode = Literal["image", "video"]
VideoMode = Literal["t2va", "fl2va", "ref2va"]
VideoTask = Literal["edit", "continue", "motion", "images"]
Offload = Literal["auto", "component", "group", "none"]
Link = Annotated[str, Field(max_length=500)]
JobId = Annotated[str, Field(pattern=r"^j[a-f0-9]{8,40}$")]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreativeLora(StrictInput):
    repo_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$", max_length=160)]
    weight_name: Annotated[str, Field(max_length=360)]
    scale: Annotated[StrictFloat, Field(ge=0, le=LIMITS["lora_scale_max"], allow_inf_nan=False)] = 1.0


class CreativeComfy(StrictInput):
    template: Annotated[str, Field(max_length=80)] | None = None
    diffusion: Link | None = None
    text_encoder: Link | None = None
    vae: Link | None = None
    sampler: Annotated[str, Field(max_length=80)] | None = None
    scheduler: Annotated[str, Field(max_length=80)] | None = None
    clip_type: Annotated[str, Field(max_length=80)] | None = None
    denoise: Annotated[StrictFloat, Field(ge=.05, le=1, allow_inf_nan=False)] | None = None


class GenerationSpec(StrictInput):
    prompt: Annotated[str, Field(max_length=LIMITS["prompt_max"])] | None = None
    idea: Annotated[str, Field(max_length=600)] | None = None
    negative: Annotated[str, Field(max_length=LIMITS["negative_max"])] | None = None
    mode: Mode | None = None
    engine: Literal["diffusers", "comfyui"] | None = None
    model: Annotated[str, Field(max_length=160)] | None = None
    comfy: CreativeComfy | None = None
    loras: Annotated[list[CreativeLora], Field(max_length=LIMITS["loras_max"])] | None = None
    custom_transformer_repo: Annotated[str, Field(pattern=r"^(?:[A-Za-z0-9._-]+/[A-Za-z0-9._-]+)?$", max_length=160)] | None = None
    custom_transformer_file: Annotated[str, Field(max_length=200)] | None = None
    workflow: VideoMode | None = None
    video_task: VideoTask | None = None
    num_frames: Annotated[StrictInt, Field(ge=1, le=400)] | None = None
    offload_mode: Offload | None = None
    width: Annotated[StrictInt, Field(ge=1, le=4096)] | None = None
    height: Annotated[StrictInt, Field(ge=1, le=4096)] | None = None
    steps: Annotated[StrictInt, Field(ge=1, le=200)] | None = None
    cfg: Annotated[StrictFloat, Field(ge=0, le=100, allow_inf_nan=False)] | None = None
    seed: Annotated[StrictInt, Field(ge=-1, le=2**31 - 1)] | None = None
    count: Annotated[StrictInt, Field(ge=1, le=LIMITS["count_max"])] | None = None
    chain: StrictBool | None = None
    has_image: StrictBool | None = None
    has_last_image: StrictBool | None = None
    reference_round_ids: Annotated[list[RoundId], Field(min_length=1, max_length=LIMITS["refs_max"])] | None = None
    last_frame_round_id: RoundId | None = None
    video_round_id: RoundId | None = None
    video_reference_id: Annotated[str, Field(pattern=r"^v[0-9a-f]{32}$")] | None = None
    mask_id: MaskId | None = None


IMAGE_FIELDS = {"engine", "model", "comfy", "custom_transformer_repo", "custom_transformer_file", "chain", "mask_id"}
VIDEO_FIELDS = {"workflow", "video_task", "num_frames", "offload_mode", "has_last_image",
                "last_frame_round_id", "video_round_id", "video_reference_id"}
REFERENCE_FIELDS = {"reference_round_ids", "last_frame_round_id", "video_round_id", "video_reference_id", "has_last_image"}


_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


class ComposerContext(GenerationSpec):
    revision: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")] | None = None

    @model_validator(mode="before")
    @classmethod
    def _sanitize_draft(cls, data):
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if isinstance(out.get("idea"), str):
            out["idea"] = out["idea"][:600]
        if isinstance(out.get("prompt"), str):
            out["prompt"] = out["prompt"][:LIMITS["prompt_max"]]
        if isinstance(out.get("negative"), str):
            out["negative"] = out["negative"][:LIMITS["negative_max"]]
        if isinstance(out.get("model"), str):
            out["model"] = out["model"].strip()[:160]
        if isinstance(out.get("custom_transformer_repo"), str):
            repo = out["custom_transformer_repo"].strip().strip("/")
            out["custom_transformer_repo"] = repo if _REPO_RE.fullmatch(repo) and len(repo) <= 160 else ""
        if isinstance(out.get("custom_transformer_file"), str):
            out["custom_transformer_file"] = out["custom_transformer_file"].strip()[:200]
        if isinstance(out.get("loras"), list):
            cleaned = []
            for item in out["loras"]:
                if len(cleaned) >= LIMITS["loras_max"]:
                    break
                try:
                    rows = normalize_loras([item])
                except ValueError:
                    continue
                if rows and len(rows[0]["repo_id"]) <= 160:
                    cleaned.append({
                        "repo_id": rows[0]["repo_id"],
                        "weight_name": rows[0]["weight_name"][:360],
                        "scale": float(rows[0]["scale"]),
                    })
            out["loras"] = cleaned
        return out


class ComposerPatch(BaseModel):
    workspace: Mode
    base_revision: str | None
    changes: GenerationSpec


class MaskEditorHint(BaseModel):
    source_id: RoundId
    mask_id: MaskId | None = None


class MediaEdit(StrictInput):
    op: Literal["crop", "extract_frame", "clip_video"]
    round_id: RoundId
    x: Annotated[StrictInt, Field(ge=0)] | None = None
    y: Annotated[StrictInt, Field(ge=0)] | None = None
    width: Annotated[StrictInt, Field(gt=0)] | None = None
    height: Annotated[StrictInt, Field(gt=0)] | None = None
    position: Literal["first", "time", "last"] | None = None
    time_s: Annotated[StrictFloat, Field(ge=0, allow_inf_nan=False)] | None = None
    start_s: Annotated[StrictFloat, Field(ge=0, allow_inf_nan=False)] | None = None
    end_s: Annotated[StrictFloat, Field(gt=0, allow_inf_nan=False)] | None = None
    mute: StrictBool | None = None


def edit_media(runtime, data: MediaEdit):
    args = data.model_dump(exclude_unset=True, exclude_none=True)
    op, rid = args.pop("op"), args.pop("round_id")
    kind = "image" if op == "crop" else "video"
    with runtime.store._lock:
        source = round_media(runtime.store, rid, kind)
        try:
            if op == "crop" and set(args) == {"x", "y", "width", "height"}:
                new_id = media.image_crop(runtime.store, rid, source, **args)
            elif op == "extract_frame" and set(args) <= {"position", "time_s"}:
                position = args.get("position", "time" if "time_s" in args else "first")
                if position == "time" and "time_s" not in args:
                    raise HarnessError("invalid_argument")
                new_id = media.video_frame(runtime.store, rid, source, position, args.get("time_s", 0))
            elif op == "clip_video" and {"start_s", "end_s"} <= set(args) <= {"start_s", "end_s", "mute"}:
                new_id = media.video_clip(runtime.store, rid, source, args["start_s"], args["end_s"], args.get("mute", False))
            else:
                raise HarnessError("invalid_argument")
        except (ValueError, OSError) as exc:
            raise HarnessError("media_invalid") from exc
    return {"round_id": new_id}


class ReferencesAction(StrictInput):
    op: Literal["read", "use_round", "remove", "clear"]
    slot: Literal["first", "last", "video"] | None = None
    round_id: RoundId | None = None
    reference_id: Annotated[str, Field(pattern=r"^(?:legacy|r[A-Za-z0-9_-]{4,32}|v[a-f0-9]{32})$")] | None = None
    append: StrictBool | None = None


def references(runtime, data: ReferencesAction):
    studio = runtime.studio
    op, slot = data.op, data.slot
    if op == "read":
        if data.model_fields_set != {"op"}:
            raise HarnessError("invalid_argument")
        return studio.refs_report()
    if not slot:
        raise HarnessError("invalid_argument")
    with studio._lock:
        try:
            if op == "use_round" and data.round_id:
                with runtime.store._lock:
                    if data.reference_id:
                        if slot != "first" or data.append is not None:
                            raise HarnessError("invalid_argument")
                        path = round_media(runtime.store, data.round_id, "image")
                        studio.replace_ref(data.reference_id, path.read_bytes(), f"round:{data.round_id}")
                    else:
                        if slot != "first" and data.append is not None:
                            raise HarnessError("invalid_argument")
                        studio.use_round(data.round_id, slot, append=bool(data.append))
            elif op in ("remove", "clear") and not data.round_id and data.append is None:
                if slot == "video":
                    entry = studio.refs_report().get("video")
                    if op == "remove" and (not data.reference_id or not entry):
                        raise HarnessError("not_found")
                    if op == "clear" and data.reference_id:
                        raise HarnessError("invalid_argument")
                    if entry:
                        studio.clear_video_ref(data.reference_id or entry["id"])
                elif op == "remove" and slot == "first":
                    if not data.reference_id:
                        raise HarnessError("invalid_argument")
                    if not studio.remove_ref(data.reference_id):
                        raise HarnessError("not_found")
                elif not data.reference_id and (op == "clear" or slot == "last"):
                    studio.clear_ref(slot)
                else:
                    raise HarnessError("invalid_argument")
            else:
                raise HarnessError("invalid_argument")
        except StateConflict as exc:
            raise HarnessError("revision_conflict") from exc
        except (RuntimeError, ValueError, OSError) as exc:
            raise HarnessError("media_invalid") from exc
        return studio.refs_report()


class LibraryAction(StrictInput):
    op: Literal["star", "trash", "list_trash", "restore"]
    round_id: RoundId | None = None
    starred: StrictBool | None = None
    offset: Annotated[StrictInt, Field(ge=0, le=10_000)] = 0
    limit: Annotated[StrictInt, Field(ge=1, le=24)] = 12


def library_action(store, data: LibraryAction):
    op, rid = data.op, data.round_id
    if op == "list_trash" and not rid and data.starred is None:
        page = store.trash_list()["items"]
        return {"rounds": [{key: item.get(key) for key in ("id", "kind", "deleted_at", "starred")}
                           for item in page[data.offset:data.offset + data.limit]], "total": len(page)}
    if not rid or data.model_fields_set & {"offset", "limit"}:
        raise HarnessError("invalid_argument")
    if op == "star":
        starred = data.starred is not False
        if store.set_star(rid, starred):
            return {"round_id": rid, "starred": starred}
    elif data.starred is None:
        if op == "trash" and store.delete([rid])["deleted"]:
            return {"round_id": rid, "state": "trashed"}
        if op == "restore" and store.restore([rid])["restored"]:
            return {"round_id": rid, "state": "restored"}
    else:
        raise HarnessError("invalid_argument")
    raise HarnessError("not_found")


class PresetInput(GenerationSpec):
    id: Annotated[str, Field(pattern=r"^(?:sp|cp)_[A-Za-z0-9_-]{4,40}$")] | None = None
    name: Annotated[str, Field(min_length=1, max_length=60)]


def presets(runtime, args):
    studio = runtime.studio
    op, group = args["op"], args.get("kind", "studio")
    extra = set(args) - {"op", "kind"}
    if op == "parse_comfy_link" and extra == {"url"} and isinstance(args["url"], str):
        return {"spec": parse_model_link(args["url"])}
    if group not in ("studio", "comfy") or op not in ("list", "save", "delete"):
        raise HarnessError("invalid_argument")
    builtin, read, save, remove = (
        (STUDIO_BUILTIN_PRESETS, studio.studio_presets, studio.save_studio_preset, studio.delete_studio_preset)
        if group == "studio" else (COMFY_BUILTIN_PRESETS, studio.comfy_presets, studio.save_comfy_preset, studio.delete_comfy_preset)
    )
    if op == "list" and not extra:
        return {"builtin": builtin, "custom": read()}
    if op == "save" and extra == {"preset"}:
        p = PresetInput.model_validate(args["preset"]).model_dump(exclude_none=True)
        allowed = {"id", "name", "mode", "width", "height", "steps", "cfg", "loras", "negative", "engine",
                   "model", "comfy", "workflow", "video_task", "num_frames", "offload_mode"}
        if p.keys() - allowed:
            raise HarnessError("invalid_argument")
        if "id" in p and not any(item["id"] == p["id"] for item in read()):
            raise HarnessError("not_found")
        return {"preset": save(p)[0]}
    if op == "delete" and extra == {"preset_id"}:
        pid = args["preset_id"]
        prefix = "sp" if group == "studio" else "cp"
        if not isinstance(pid, str) or not re.fullmatch(prefix + r"_[A-Za-z0-9_-]{4,40}", pid):
            raise HarnessError("invalid_argument")
        if not remove(pid)[0]:
            raise HarnessError("not_found")
        return {"deleted": pid}
    raise HarnessError("invalid_argument")


def merge_spec(*layers):
    merged = {}
    for layer in layers:
        if not layer:
            continue
        for key, value in layer.items():
            if key == "comfy" and isinstance(value, dict) and isinstance(merged.get("comfy"), dict):
                merged["comfy"] = {**merged["comfy"], **{k: v for k, v in value.items() if v is not None}}
            else:
                merged[key] = value
    return merged


def generation(editor, args):
    op = args["op"]
    if op not in ("edit_composer", "prepare", "submit_image", "submit_video"):
        raise HarnessError("invalid_argument")
    raw_spec = args.get("spec", {})
    clear_mask = isinstance(raw_spec, dict) and "mask_id" in raw_spec and raw_spec["mask_id"] is None
    changes = GenerationSpec.model_validate(raw_spec).model_dump(exclude_none=True)
    context = editor.composer or {}
    base = {k: v for k, v in context.items() if k != "revision"}
    mode = changes.get("mode") or (editor.workspace if editor.workspace in ("image", "video") else "image")
    if op in ("submit_image", "submit_video"):
        mode = op.removeprefix("submit_")
        if changes.get("mode", mode) != mode:
            raise HarnessError("invalid_argument")
    checked_fields = set(changes) | ({"mask_id"} if clear_mask else set())
    if checked_fields & (VIDEO_FIELDS if mode == "image" else IMAGE_FIELDS):
        raise HarnessError("invalid_argument")
    service = editor.runtime.operations
    if op == "edit_composer":
        if editor.workspace not in ("image", "video") or mode != editor.workspace or "idempotency_key" in args or not (changes or clear_mask):
            raise HarnessError("invalid_argument")
        if changes.keys() & REFERENCE_FIELDS:
            raise HarnessError("invalid_argument")
        if mask_id := changes.get("mask_id"):
            service.get_mask(mask_id)
        prev_changes = (editor.composer_patch or {}).get("changes") or {}
        if mode == "image" and "mask_id" not in changes and (changes.get("chain") is True or changes.get("has_image") is False):
            if prev_changes.get("mask_id") or ("mask_id" not in prev_changes and base.get("mask_id")):
                clear_mask = True
        clear_chain = (
            mode == "image" and bool(changes.get("mask_id")) and "chain" not in changes
            and (prev_changes.get("chain") is True or ("chain" not in prev_changes and base.get("chain") is True))
        )
        # Reuse the generation validator for supported enums/models. Preserve empty draft prompts.
        view = merge_spec(base, prev_changes, changes)
        if clear_mask:
            view.pop("mask_id", None)
        if clear_chain:
            view["chain"] = False
        normalized = _normalize(view | {"mode": mode, "prompt": view.get("prompt") or "Draft"}, transient=True)
        for key in ("width", "height", "steps", "cfg", "num_frames"):
            if key in changes and key in normalized:
                changes[key] = normalized[key]
        emitted = {
            **changes,
            **({"mask_id": None} if clear_mask else {}),
            **({"chain": False} if clear_chain else {}),
        }
        patch = {"workspace": mode, "base_revision": context.get("revision"), "changes": emitted}
        if editor.composer_patch:
            patch["changes"] = merge_spec(editor.composer_patch["changes"], emitted)
        editor.composer_patch = patch
        return {"composer_patch": patch}

    active = editor.composer_patch["changes"] if editor.composer_patch else {}
    draft = merge_spec(base, active) if editor.workspace == mode else {}
    raw = merge_spec(draft, changes, {"mode": mode})
    if (clear_mask or ("mask_id" not in changes and (
            ("mask_id" in active and active["mask_id"] is None)
            or changes.get("chain") is True
            or "reference_round_ids" in changes
            or changes.get("has_image") is False
            or (not active.get("mask_id") and (active.get("chain") is True or active.get("has_image") is False))))):
        raw.pop("mask_id", None)
    if "chain" not in changes and (changes.get("mask_id") or "reference_round_ids" in changes
                                   or (active.get("mask_id") and active.get("chain") is not True)):
        raw.pop("chain", None)
    if "video_round_id" in changes and "video_reference_id" not in changes:
        raw.pop("video_reference_id", None)
    if changes.keys() & {"video_round_id", "video_reference_id"}:
        if raw.get("workflow") != "ref2va" or changes.get("video_task") == "images":
            raise HarnessError("invalid_argument")
        if raw.get("video_task") == "images":
            raw["video_task"] = "edit"
    implicit_video = (raw.get("video_task") in ("edit", "continue", "motion") and mode == "video"
                      and raw.get("workflow") == "ref2va" and not raw.get("video_reference_id") and not raw.get("video_round_id"))
    if implicit_video:
        # The current slot is resolved after looking up the idempotency key.
        raw["video_reference_id"] = "v" + "0" * 32
    mask_id = raw.pop("mask_id", None)
    normalized = _normalize(raw)
    if implicit_video:
        normalized.pop("video_reference_id")
    if op == "prepare":
        if "idempotency_key" in args:
            raise HarnessError("invalid_argument")
        p, refs, last, video = service.prepare(normalized, mask_id)
        return {"parameters": {k: v for k, v in p.items() if k not in {"gpu", "gpu_pool", "auto_fallback", "poll_rounds", "poll_all_proxies", "edit_mask"}},
                "references": {"images": len(refs), "last": bool(last), "video": bool(video), "mask": bool(mask_id)}}
    operation = service.create(editor.scope, args.get("idempotency_key"), normalized, mask_id)
    editor.operation_ids.append(operation["operation_id"])
    return {"operation": operation, "operation_id": operation["operation_id"]}


def _normalize(raw, *, transient=False):
    payload = dict(raw)
    mode = payload["mode"]
    payload.pop("mask_id", None)
    if mode == "image":
        for field in ("video_task", "video_reference_id", "video_round_id", "last_frame_round_id", "has_last_image"):
            payload.pop(field, None)
    elif payload.get("workflow") != "ref2va" or payload.get("video_task") == "images":
        for field in ("video_task", "video_reference_id", "video_round_id"):
            payload.pop(field, None)
    if transient:
        for field in ("video_task", "video_reference_id", "video_round_id"):
            payload.pop(field, None)
        if payload.get("engine") == "comfyui" and not (payload.get("comfy") or {}).get("diffusion"):
            payload.pop("engine")
    return normalize_job(payload)


class JobAction(StrictInput):
    op: Literal["list", "read", "cancel", "retry"]
    job_id: JobId | None = None
    operation_id: Annotated[str, Field(pattern=r"^op_[a-f0-9]{24}$")] | None = None


def jobs(editor, args: JobAction):
    runtime = editor.runtime
    studio, operations = runtime.studio, runtime.operations

    def summary(job):
        return {k: job[k] for k in ("id", "status", "mode", "model", "round_id", "progress", "created_at") if k in job}

    op, job_id, operation_id = args.op, args.job_id, args.operation_id
    if op == "list" and not job_id and not operation_id:
        state = studio.snapshot()
        return {"current": summary(state["current"]) if state["current"] else None, "queue": [summary(row) for row in state["queue"]],
                "history": [summary(row) for row in state["history"]], "operations": operations.list(editor.scope, 12)}
    if op == "cancel" and job_id and not operation_id:
        if not studio.cancel_job(job_id):
            raise HarnessError("not_found")
        return {"job_id": job_id, "cancel_requested": True}
    if op not in ("read", "retry") or bool(operation_id) == bool(job_id):
        raise HarnessError("invalid_argument")
    operation = operations.get(operation_id, scope=editor.scope) if operation_id else operations.for_job(job_id, scope=editor.scope)
    if op == "retry":
        if not operation:
            raise HarnessError("approval_required")
        if not any(item["state"] == "failed" and (not job_id or item["job_id"] == job_id) for item in operation["items"]):
            raise HarnessError("invalid_argument")
        editor.operation_ids.append(operation["operation_id"])
        return {"operation": operation, "retry_requires_approval": True}
    if operation:
        return {"operation": operation}
    if job := studio.find_job(job_id):
        return {"job": summary(job)}
    raise HarnessError("not_found")


def prepare_mask(editor, args):
    rid = args["source_id"]
    if not editor.runtime.store.valid_id(rid):
        raise HarnessError("invalid_argument")
    if "strokes" in args:
        mask = editor.runtime.operations.create_mask(MaskInput.model_validate(args))
        editor.mask_editor = {"source_id": rid, "mask_id": mask["mask_id"]}
        return mask
    round_media(editor.runtime.store, rid, "image")
    editor.mask_editor = {"source_id": rid, "mask_id": None}
    return {"mask_editor": editor.mask_editor}
