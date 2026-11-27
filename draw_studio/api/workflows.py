from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from .core import IMAGE_BODY, Raw, State, flag, image_type, media_file, media_route, readable

router = APIRouter(prefix="/api/workflows", tags=["工作流"])


class AssetInfo(BaseModel):
    model_config = ConfigDict(extra="allow")
    filename: str
    bytes: int


class AssetUpload(BaseModel):
    ok: bool
    filename: str
    asset: AssetInfo
    assets: list[AssetInfo]


@readable(router, "")
def workflows(s: State):
    return s.workflows.list_workflows()


@router.post("")
def save_template(body: dict, s: State):
    workflow, custom = s.workflows.save_workflow(body)
    return {"ok": True, "workflow": workflow, "custom": custom}


@readable(router, "/runs")
def list_runs(s: State):
    return {"runs": s.workflows.list_runs()}


@router.post("/runs", status_code=201)
def create_run(body: dict, s: State):
    return {"ok": True, "run": s.workflows.create_run(body)}


@readable(router, "/runs/{run_id}")
def get_run(run_id: str, s: State):
    run = s.workflows.get_run(run_id)
    if not run:
        raise HTTPException(404, "工作流运行记录不存在")
    return {"run": run}


@router.patch("/runs/{run_id}")
def update_run(run_id: str, body: dict, s: State):
    return {"ok": True, "run": s.workflows.update_run_config(run_id, body)}


@router.delete("/runs/{run_id}")
def delete_run(run_id: str, s: State):
    if not s.workflows.delete_run(run_id):
        raise HTTPException(404, "工作流运行记录不存在")
    return {"ok": True}


@router.post("/runs/{run_id}/start", status_code=202)
@router.post("/runs/{run_id}/resume", status_code=202)
def start(run_id: str, s: State, body: dict = Body(default_factory=dict)):
    run = s.workflows.start_run(run_id, from_step_id=body.get("from_step_id") or None,
                                single_step=flag(body.get("single_step")), draft_only=flag(body.get("draft_only")))
    return {"ok": True, "run": run}


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, s: State):
    try:
        return {"ok": True, "run": s.workflows.cancel_run(run_id)}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/runs/{run_id}/steps/{step_id}/retry", status_code=202)
def retry(run_id: str, step_id: str, s: State, body: dict = Body(default_factory=dict)):
    run = s.workflows.start_run(run_id, from_step_id=step_id, single_step=flag(body.get("single_step")))
    return {"ok": True, "run": run}


@router.post("/runs/{run_id}/steps/{step_id}/output")
@router.patch("/runs/{run_id}/steps/{step_id}/output")
def save_output(run_id: str, step_id: str, body: dict, s: State):
    patch = body["output"] if isinstance(body.get("output"), dict) else body
    return {"ok": True, "run": s.workflows.update_step_output(run_id, step_id, patch)}


@router.post("/runs/{run_id}/assets", openapi_extra=IMAGE_BODY, response_model=AssetUpload)
def upload_asset(run_id: str, raw: Raw, s: State, step_id: str = "", label: str = "upload"):
    return {"ok": True, **s.workflows.upload_asset(run_id, raw, step_id=step_id, label=label)}


@media_route(router, "/runs/{run_id}/assets/{filename}", "image/png", "image/jpeg", "image/webp")
def asset(run_id: str, filename: str, request: Request, s: State, thumb: bool = False):
    if thumb:
        path = s.workflows.asset_thumbnail(run_id, filename)
        return media_file(request, path, "image/jpeg", "private, max-age=86400")
    path = s.workflows.asset_path(run_id, filename)
    if path is None:
        raise HTTPException(404, "素材图片不存在")
    return media_file(request, path, image_type(path), "private, max-age=86400")


@router.delete("/runs/{run_id}/assets/{filename}")
def delete_asset(run_id: str, filename: str, s: State):
    try:
        return {"ok": True, "assets": s.workflows.delete_asset(run_id, filename)}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete("/{workflow_id}")
def delete_template(workflow_id: str, s: State):
    removed, custom = s.workflows.delete_workflow(workflow_id)
    if not removed:
        raise HTTPException(404, "未找到该工作流模板")
    return {"ok": True, "custom": custom}
