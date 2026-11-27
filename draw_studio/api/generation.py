import re
import threading
import time

from fastapi import APIRouter, Body, HTTPException

from .. import __version__
from ..gallery import TRASH_DAYS
from ..generation.catalog import (
    COMFY_BUILTIN_PRESETS, COMFY_CLIP_TYPES, COMFY_SAMPLERS, COMFY_SCHEDULERS, COMFY_TEMPLATES,
    DEFAULTS, GPUS, IMAGE_MODELS, LIMITS, STUDIO_BUILTIN_PRESETS, VIDEO_OFFLOAD_MODES, VIDEO_WORKFLOWS,
)
from ..generation.parameters import normalize_grab, normalize_job, parse_model_link
from ..logs import redact_secrets
from ..workflows.definitions import STEP_CATALOG
from ..workflows.video import ffmpeg_available
from .core import State, flag, readable

router = APIRouter(prefix="/api", tags=["工作台与算力"])


@readable(router, "/config")
def config(s: State):
    return {
        "version": __version__, "gpus": GPUS, "image_models": IMAGE_MODELS, "recent_models": s.studio.recent_models(),
        "video_workflows": VIDEO_WORKFLOWS, "video_offload_modes": VIDEO_OFFLOAD_MODES,
        "comfy": {"templates": COMFY_TEMPLATES, "samplers": COMFY_SAMPLERS, "schedulers": COMFY_SCHEDULERS,
                  "clip_types": COMFY_CLIP_TYPES, "builtin_presets": COMFY_BUILTIN_PRESETS, "presets": s.studio.comfy_presets()},
        "studio_presets": {"builtin": STUDIO_BUILTIN_PRESETS, "custom": s.studio.studio_presets()},
        "workflow_step_catalog": STEP_CATALOG, "ffmpeg_available": ffmpeg_available(), "proxy": s.studio.proxies.state(),
        "limits": LIMITS, "defaults": DEFAULTS, "trash_retention_days": TRASH_DAYS,
    }


@readable(router, "/status")
def status(s: State, log_since: int = 0):
    logs, seq = s.log.since(log_since)
    return {**s.studio.snapshot(), "logs": logs, "log_seq": seq,
            "gallery_rev": s.store.rev, "latest": s.store.latest(), "references": s.studio.refs_report(),
            "recent_models": s.studio.recent_models(), "comfy_presets": s.studio.comfy_presets(),
            "studio_presets": s.studio.studio_presets(), "workflow_active": s.workflows.active_summary(),
            "proxy": s.studio.proxies.state(), "colab": s.colab.status_report(blocking=False), "server_time": int(time.time())}


@readable(router, "/presets")
def presets(s: State):
    return {"builtin": STUDIO_BUILTIN_PRESETS, "custom": s.studio.studio_presets()}


@router.post("/presets")
def save_preset(body: dict, s: State):
    preset, custom = s.studio.save_studio_preset(body)
    return {"ok": True, "preset": preset, "custom": custom}


@router.delete("/presets/{preset_id}")
def delete_preset(preset_id: str, s: State):
    removed, custom = s.studio.delete_studio_preset(preset_id)
    if not removed:
        raise HTTPException(404, "未找到该参数预设")
    return {"ok": True, "custom": custom}


@readable(router, "/models/recent")
def recent_models(s: State):
    return {"recent_models": s.studio.recent_models()}


@router.post("/models/recent")
def add_recent(body: dict, s: State):
    name = str(body.get("model") or "").strip()
    if not name:
        raise ValueError("请先填写模型名称或 Hugging Face 仓库 ID")
    return {"ok": True, "recent_models": s.studio.add_recent_model(name)}


@router.delete("/models/recent")
def delete_recent(s: State, model: str = "", body: dict = Body(default_factory=dict)):
    name = str(body.get("model") or model).strip()
    if not name:
        raise ValueError("缺少要移除的 model")
    return {"ok": True, "recent_models": s.studio.remove_recent_model(name)}


@router.post("/settings")
def settings(body: dict, s: State):
    if "idle_minutes" not in body:
        return {"ok": True}
    try:
        raw = body["idle_minutes"]
        if isinstance(raw, bool):
            raise ValueError
        minutes = s.studio.set_idle_minutes(int(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError("idle_minutes 必须是整数，0 表示永不超期") from exc
    return {"ok": True, "idle_minutes": minutes}


@router.post("/generate", status_code=202)
def generate(body: dict, s: State):
    if not s.colab.has_credentials():
        raise ValueError("请先在「设置」里完成 Google Colab 授权")
    return {"ok": True, "jobs": s.studio.enqueue(normalize_job(body))}


@readable(router, "/queue")
def queue(s: State):
    snap = s.studio.snapshot()
    return {k: snap[k] for k in ("current", "queue", "history")}


@router.post("/queue/clear")
def clear_queue(s: State):
    return {"ok": True, "removed": s.studio.clear_queue()}


@router.delete("/queue/{job_id}")
@router.post("/queue/{job_id}/cancel")
def unqueue(job_id: str, s: State):
    if not s.studio.remove_queued(job_id):
        raise HTTPException(404, "队列里没有这个任务（可能已开始运行，请用 /api/stop）")
    return {"ok": True}


@router.post("/stop")
def stop(s: State, body: dict = Body(default_factory=dict)):
    s.studio.cancel_current(clear_queue=flag(body.get("clear_queue")))
    return {"ok": True}


@router.post("/release")
def release(s: State):
    threading.Thread(target=s.studio.release_all, daemon=True).start()
    return {"ok": True}


@router.post("/comfy/parse-link")
def parse_link(body: dict):
    return {"ok": True, "spec": parse_model_link(body.get("url", body), str(body.get("label") or "模型链接")[:30])}


@readable(router, "/comfy/presets")
def comfy_presets(s: State):
    return {"presets": s.studio.comfy_presets(), "builtin_presets": COMFY_BUILTIN_PRESETS}


@router.post("/comfy/presets")
def save_comfy(body: dict, s: State):
    preset, items = s.studio.save_comfy_preset(body)
    return {"ok": True, "preset": preset, "presets": items}


@router.delete("/comfy/presets/{preset_id}")
def delete_comfy(preset_id: str, s: State):
    removed, items = s.studio.delete_comfy_preset(preset_id)
    if not removed:
        raise HTTPException(404, "未找到该 ComfyUI 组合方案")
    return {"ok": True, "presets": items}


@router.post("/hf/list-loras")
def list_loras(body: dict, s: State):
    try:
        return {"files": s.studio.list_hf_safetensors(str(body.get("repo_id") or ""))}
    except RuntimeError as exc:
        raise HTTPException(400, redact_secrets(str(exc))) from exc


@readable(router, "/colab/status")
def colab_status(s: State):
    return s.colab.status_report(force=True, blocking=True)


@router.post("/colab/auth/start")
def colab_auth(s: State):
    return {"auth_url": s.colab.start_oauth()}


@router.post("/colab/auth/complete")
def colab_complete(body: dict, s: State):
    try:
        report = s.colab.complete_oauth(str(body.get("code") or ""))
    except Exception as exc:
        raise HTTPException(400, "Colab 授权失败，请重新获取授权码") from exc
    s.studio.resume_queue()
    return report


@router.post("/colab/auth/logout")
def colab_logout(s: State):
    s.colab.logout()
    return {"ok": True}


@router.post("/colab/grab", status_code=202)
def grab(body: dict, s: State):
    if not s.colab.has_credentials():
        raise ValueError("请先在「设置」里完成 Google Colab 授权")
    spec = normalize_grab(body)
    s.studio.grab_card(**spec)
    return {"ok": True, **spec}


@router.post("/colab/hf-token")
def hf_token(body: dict, s: State):
    token = str(body.get("token") or "").strip()
    if token and not re.fullmatch(r"hf_[A-Za-z0-9]{20,}", token):
        raise ValueError("HF Token 格式不对（应以 hf_ 开头）")
    s.colab.set_hf_token(token)
    s.colab.invalidate_status()
    return {"ok": True, "set": bool(token)}
