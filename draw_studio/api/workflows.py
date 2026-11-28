import json
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..errors import LlmError
from ..workflows import agent_plugins
from ..workflows.agent_tools import EditorTools, editor_revision, editor_value
from ..workflows.copilot import recent_exchanges, turn_events
from ..workflows.definitions import normalize_workflow_def, workflow_variables
from ..workflows.engine import RUN_ID_RE
from ..workflows.harness_errors import HarnessError
from ..workflows.harness_telemetry import TurnTelemetry
from ..workflows.shot_service import (
    Proposal, ProposalAction, RewriteInput, ShotEdit, ShotId, Shots, ShotWriteResult, Telemetry,
    apply_shot_edits, read_shots, reject_proposal, rewrite_prompt, undo_change,
)

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


class AgentMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=3000)


class ComposerContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(default="", max_length=12000)
    model: str | None = Field(default=None, max_length=128)
    workflow: Literal["t2va", "fl2va", "ref2va"] | None = None
    num_frames: int | None = Field(default=None, ge=1, le=400)
    video_task: Literal["edit", "continue", "motion"] | None = None


class AgentTurn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[AgentMessage] = Field(default_factory=list, max_length=12)
    workflow: dict
    topic: str = Field(default="", max_length=2000)
    selected_step: str = Field(default="", max_length=48)
    selected_shot: ShotId | None = None
    workspace: Literal["workflow", "image", "video"] = "workflow"
    composer: ComposerContext | None = None
    run_id: str | None = Field(default=None, max_length=80)
    draft_id: str | None = Field(default=None, pattern="^[a-f0-9]{32}$")
    turn_id: str | None = Field(default=None, pattern="^[a-f0-9]{32}$")
    reload_plugins: bool = False

    @model_validator(mode="before")
    @classmethod
    def composer_workflow(cls, value):
        if isinstance(value, dict) and value.get("workspace") in ("image", "video") and "workflow" not in value:
            return {**value, "workflow": {"steps": []}}
        return value


class AgentExchange(BaseModel):
    id: str
    user: str
    answer: str
    tools: list[dict]
    state: Literal["done"]
    proposals: list[Proposal] = Field(default_factory=list)


class AgentConversation(BaseModel):
    exchanges: list[AgentExchange]


class InterruptTurn(BaseModel):
    turn_id: str = Field(pattern="^[a-f0-9]{32}$")


class StopResult(BaseModel):
    stopped: bool


class PluginAction(BaseModel):
    action: Literal["install", "enable", "disable", "remove"]


class AgentPlugin(BaseModel):
    id: str
    name: str
    version: str
    description: str
    tool: str
    installed: bool
    enabled: bool


class AgentInventory(BaseModel):
    builtin_tools: dict[str, str]
    plugin: AgentPlugin


@readable(router, "/agent/plugins", response_model=AgentInventory)
def agent_plugin_list(s: State):
    return agent_plugins.inventory(s.root)


@router.post("/agent/plugins/{package}", response_model=AgentInventory)
def agent_plugin_action(package: str, body: PluginAction, s: State):
    return agent_plugins.change_plugin(s.root, package, body.action)


@readable(router, "/agent/conversations/{key}", response_model=AgentConversation)
def agent_conversation(key: str, s: State):
    if not RUN_ID_RE.fullmatch(key):
        raise HarnessError("invalid_argument")
    store = s.harness_store
    exchanges = recent_exchanges(s.root, key)
    for row in exchanges:
        ids = row.get("proposal_ids")
        row["proposals"] = [store.public_proposal(proposal) for pid in ids[-2:] if isinstance(pid, str)
                            and (proposal := store.get_proposal(pid)) and proposal["scope_key"] == key] if isinstance(ids, list) else []
    return {"exchanges": exchanges}


@router.post("/agent/conversations/{key}/stop", response_model=StopResult)
def interrupt_turn(key: str, body: InterruptTurn, s: State):
    if not RUN_ID_RE.fullmatch(key):
        raise HarnessError("invalid_argument")
    return {"stopped": s.harness_sessions.interrupt(key, body.turn_id)}


@router.post("/agent/turn", response_class=StreamingResponse, responses={200: {
    "description": "逐行 JSON 事件（started、session、tool、heartbeat、done 或 error）",
    "content": {"application/x-ndjson": {}},
}})
def agent_turn(body: AgentTurn, s: State):
    if not body.message.strip() or len(json.dumps(body.workflow, ensure_ascii=False, allow_nan=False)) > 90000:
        raise HarnessError("invalid_argument")
    if body.run_id is not None and (not RUN_ID_RE.fullmatch(body.run_id) or body.draft_id is not None):
        raise HarnessError("invalid_argument")
    key = body.run_id or (f"wr_{body.draft_id}" if body.draft_id else None)
    raw = body.workflow
    if raw.get("steps") == [] and not body.run_id:
        wf = {"name": str(raw.get("name") or "工作流")[:80], "steps": [],
              "description": str(raw.get("description") or "")[:400],
              "default_topic": str(raw.get("default_topic") or "")[:600],
              "variables": workflow_variables(raw.get("variables", {}))}
    else:
        wf = normalize_workflow_def({**raw, "id": ""})
    wf.update(id=str(raw.get("id") or "")[:80], builtin=bool(raw.get("builtin")))
    snapshot = {"workflow": wf, "topic": body.topic}
    revision = None
    if body.run_id:
        saved = s.workflows.get_run(body.run_id)
        if not saved:
            raise HarnessError("not_found")
        revision = editor_revision(saved)
        stored = saved["workflow"]
        normalized = normalize_workflow_def({**stored, "id": ""})
        if editor_value({"topic": body.topic.strip(), "workflow": wf}) != editor_value({
            "topic": saved["topic"], "workflow": normalized,
        }):
            raise HarnessError("revision_conflict", details={"current_revision": revision})
        normalized.update(id=stored["id"], builtin=bool(stored.get("builtin")))
        snapshot = {"workflow": normalized, "topic": saved["topic"]}
    elif key and s.workflows.get_run(key):
        raise HarnessError("draft_already_saved", details={"run_id": key})

    try:
        provider, model = s.studio.llm.resolve()
    except (ValueError, LlmError) as exc:
        raise HarnessError("model_unconfigured") from exc
    if body.workspace != "workflow" and (body.run_id or body.selected_step or body.selected_shot):
        raise HarnessError("invalid_argument")
    editor = EditorTools(s, snapshot, selected=body.selected_step, run_id=body.run_id, scope=key, revision=revision,
                         workspace=body.workspace, selected_shot=body.selected_shot,
                         composer=body.composer.model_dump(exclude_none=True) if body.composer else None)

    async def stream():
        async for event in turn_events(editor, provider, model, body.message.strip(), revision, key, body.turn_id,
                                       [message.model_dump() for message in body.history],
                                       reload_plugins=body.reload_plugins):
            yield json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@readable(router, "/runs/{run_id}/shots", response_model=Shots)
def run_shots(run_id: str, s: State, step_id: Annotated[str | None, Query(max_length=48)] = None):
    return {"shots": read_shots(s, run_id, step_id)}


@router.post("/runs/{run_id}/steps/{step_id}/shots/rewrite", response_model=Proposal)
def rewrite_shots(run_id: str, step_id: str, body: RewriteInput, s: State):
    call = {"type": "tool", "call_id": "rewrite", "name": "studio_rewrite_prompt"}
    metrics = TurnTelemetry(s, uuid.uuid4().hex, run_id if RUN_ID_RE.fullmatch(run_id) else "", "")
    metrics.observe({**call, "ok": None})
    code = "internal_error"
    try:
        proposal = rewrite_prompt(s, body, scope=run_id, run_id=run_id, step_id=step_id, record_model=metrics.record_model)
        metrics.observe({**call, "ok": True, "_proposal_id": proposal["proposal_id"]})
        return proposal
    except HarnessError as exc:
        code = exc.code
        raise
    finally:
        metrics.finish(code)


ProposalId = Annotated[str, Path(pattern=r"^pr_[a-f0-9]{24}$")]
UndoId = Annotated[str, Path(pattern=r"^un_[a-f0-9]{24}$")]


@router.post("/agent/proposals/{proposal_id}/apply", response_model=ShotWriteResult)
def adopt_proposal(proposal_id: ProposalId, s: State, body: ProposalAction = Body(default_factory=ProposalAction)):
    return apply_shot_edits(s, proposal_id=proposal_id, atomicity=body.atomicity)


@router.post("/agent/proposals/{proposal_id}/reject", response_model=Proposal)
def discard_proposal(proposal_id: ProposalId, s: State):
    return reject_proposal(s, proposal_id)


@router.post("/agent/undo/{undo_id}", response_model=ShotWriteResult)
def undo_proposal(undo_id: UndoId, s: State):
    return undo_change(s, undo_id)


@readable(router, "/agent/telemetry", response_model=Telemetry)
def agent_telemetry(s: State):
    return s.harness_store.telemetry()


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
    s.harness_sessions.forget(s.root, run_id)
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
    if "shot_edits" in body:
        if body.keys() != {"shot_edits"} or not isinstance(body["shot_edits"], list) or not 1 <= len(body["shot_edits"]) <= 32:
            raise HarnessError("invalid_argument")
        try:
            edits = [ShotEdit.model_validate(row).model_dump() for row in body["shot_edits"]]
        except ValidationError as exc:
            raise HarnessError("invalid_argument") from exc
        return apply_shot_edits(s, run_id=run_id, step_id=step_id, patches=edits, record_undo=False)
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
