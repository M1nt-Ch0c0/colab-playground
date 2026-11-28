"""Shared shot and prompt operations for the workflow API and the model tools."""
from __future__ import annotations

import copy
import json
import secrets
import time
from collections import defaultdict
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from ..errors import LlmError
from ..gallery import Store
from ..generation.catalog import LIMITS, VIDEO_WORKFLOWS
from ..generation.video_reference import VIDEO_TASKS
from .harness_errors import HarnessError
from .harness_store import PROPOSAL_TTL, SHOT_FIELDS, SHOT_LISTS, UNDO_TTL, dump, shot_seq

ShotId = Annotated[str, Field(pattern=r"^sh_[a-f0-9]{12}$")]
RoundId = Annotated[str, Field(pattern=r"^[0-9]{3,7}$")]
Atomicity = Literal["all", "per_shot"]
ProposalField = Literal["keyframe_prompt", "video_prompt", "prompt"]
TextField = Literal["keyframe_prompt", "video_prompt", "prompt", "audio_notes", "search_query"]


class ShotVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shot_id: ShotId
    field: TextField
    generation: Annotated[StrictInt, Field(ge=1)]
    expected_version: Annotated[StrictInt, Field(ge=1)]


class ShotEdit(ShotVersion):
    value: str = Field(max_length=LIMITS["prompt_max"])


class Shot(BaseModel):
    run_id: str
    step_id: str
    shot_id: ShotId
    generation: int
    seq: int
    title: str
    fields: dict[str, str]
    field_versions: dict[str, int]
    keyframe_round_id: str | None
    clip_round_id: str | None


class Shots(BaseModel):
    shots: list[Shot]


class ShotConflict(BaseModel):
    shot_id: ShotId
    field: TextField
    expected_version: int
    current_version: int | None
    expected_generation: int
    current_generation: int | None
    n: int | None = None


class ShotChange(BaseModel):
    shot_id: ShotId
    n: int
    field: TextField
    generation: int
    version: int
    value: str


class RunShotUpdate(BaseModel):
    run_id: str
    step_id: str
    changes: list[ShotChange]


class ProposalText(BaseModel):
    shot_id: ShotId | None
    n: int
    text: str


class ReferenceUsed(BaseModel):
    id: str
    thumb: str
    label: str


class RewriteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shot_ids: list[ShotId] = Field(default_factory=list, max_length=8)
    field: ProposalField | None = None
    instruction: str = Field(min_length=1, max_length=3000)
    reference_round_ids: list[RoundId] = Field(default_factory=list, max_length=LIMITS["refs_max"])


class ProposalTarget(BaseModel):
    shot_ids: list[ShotId]
    field: ProposalField
    instruction: str
    reference_round_ids: list[RoundId]
    conflicts: list[ShotConflict] = Field(default_factory=list)
    workspace: Literal["image", "video"] | None = None


class Proposal(BaseModel):
    proposal_id: str
    scope_key: str
    kind: Literal["shots", "composer"]
    run_id: str | None
    step_id: str | None
    target: ProposalTarget
    readset: list[ShotVersion]
    writeset: list[ShotEdit]
    before: list[ProposalText]
    after: list[ProposalText]
    references_used: list[ReferenceUsed]
    model: str
    status: Literal["pending", "applied", "rejected", "undone", "expired"]
    undo_id: str | None
    created_at: int
    expires_at: int


class ProposalAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    atomicity: Atomicity = "all"


class ComposerPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace: Literal["image", "video"]
    prompt: str = Field(max_length=LIMITS["prompt_max"])


class ComposerWriteResult(ComposerPrompt):
    proposal: Proposal


class ShotWriteResult(BaseModel):
    applied: list[ShotChange]
    conflicts: list[ShotConflict]
    undo_id: str | None
    step_output: dict
    run_updated: RunShotUpdate
    proposal: Proposal | None = None


class ToolStats(BaseModel):
    total: int
    success_rate: float
    p50_ms: int
    p95_ms: int
    retries: int


class Telemetry(ToolStats):
    by_tool: dict[str, ToolStats]
    by_error: dict[str, int]
    cache_hit_tokens: int
    cache_miss_tokens: int
    proposal_outcomes: dict[str, int]
    proposal_adoption_rate: float


def _steps(run):
    return {step["id"]: step for step in run["workflow"]["steps"]}


def _output(run, step_id):
    return run["step_states"].get(step_id, {}).get("output") or {}


def _rows(run, step_id):
    step = _steps(run).get(step_id)
    key = SHOT_LISTS.get(step["type"]) if step else None
    rows = _output(run, step_id).get(key) if key else None
    return {row["shot_id"]: (shot_seq(row, index), row) for index, row in enumerate(rows or [], 1)
            if isinstance(row, dict) and "shot_id" in row} if isinstance(rows, list) else {}


def _matching_round(run, step, kind, seq):
    config = step["config"]
    source = config.get("scenes_from") if step["type"] == "h3_prompt" else step["id"]
    for candidate in reversed(run["workflow"]["steps"]):
        options = candidate["config"]
        if candidate["type"] != kind:
            continue
        if kind == "image_gen":
            matches = candidate["id"] == config.get("keyframe_from") if config.get("keyframe_from") else (
                bool(source) and options.get("scenes_from") == source)
        else:
            prompts = options.get("prompts_from")
            matches = prompts == step["id"] if step["type"] == "h3_prompt" else (
                options.get("scenes_from") == step["id"] or
                _steps(run).get(prompts, {}).get("config", {}).get("scenes_from") == step["id"])
        if matches:
            for item in _output(run, candidate["id"]).get("items") or []:
                if isinstance(item, dict) and item.get("scene_index") == seq and Store.valid_id(item.get("round_id")):
                    return item["round_id"]
    return None


def _shot(run, step, seq, row):
    keyframe = row.get("keyframe_round_id")
    clip = row.get("clip_round_id")
    versions = row["field_versions"]
    return {"run_id": run["id"], "step_id": step["id"], "shot_id": row["shot_id"], "generation": row["generation"],
            "seq": seq, "title": str(row.get("title") or ""),
            "fields": {field: str(row.get(field) or "") for field in versions}, "field_versions": dict(versions),
            "keyframe_round_id": keyframe if Store.valid_id(keyframe) else _matching_round(run, step, "image_gen", seq),
            "clip_round_id": clip if Store.valid_id(clip) else _matching_round(run, step, "video_gen", seq)}


def read_shots(runtime, run_id, step_id=None):
    with runtime.workflows.shot_run(run_id) as run:
        steps = _steps(run)
        if step_id is not None and step_id not in steps:
            raise HarnessError("not_found")
        selected = (steps[step_id],) if step_id is not None else steps.values()
        return [_shot(run, step, seq, row) for step in selected for seq, row in _rows(run, step["id"]).values()]


def _reference(runtime, rid, *, required=False):
    found = runtime.store.media_path(rid)
    if found and found[0] == "image":
        path = found[1]
        try:
            if path.stat().st_size <= LIMITS["upload_max_mb"] * 1048576:
                asset = runtime.store.get(rid) or {}
                return ({"id": rid, "thumb": f"api/rounds/{rid}" + ("/thumb" if asset.get("has_thumb") else ""),
                         "label": str(asset.get("prompt") or "")[:80]}, path.read_bytes())
        except FileNotFoundError:
            pass
    if required:
        raise HarnessError("media_invalid")
    return None


def _writer(runtime, text, mode, *, options, image_data, provider, model):
    frames = options.get("num_frames", 124)
    safe_frames = frames if type(frames) is int else 124
    video_mode = options.get("workflow", "t2va")
    if video_mode not in {row["id"] for row in VIDEO_WORKFLOWS}:
        video_mode = "t2va"
    video_task = options.get("video_task")
    try:
        result = runtime.studio.write_prompt_rich(
            text, mode=mode, workflow=video_mode, num_frames=safe_frames, ref_count=len(image_data),
            override_images=[(f"<Picture {number}>", data) for number, data in enumerate(image_data, 1)],
            provider_id=provider.id, model=model,
            video_task=video_task if isinstance(video_task, str) and video_task in VIDEO_TASKS else None,
            has_last_image=bool(options.get("has_last_image")),
        )
    except (LlmError, ValueError, RuntimeError, OSError) as exc:
        raise HarnessError("model_error") from exc
    prompt = result.get("prompt") if isinstance(result, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        raise HarnessError("model_error")
    return prompt[:LIMITS["prompt_max"]]


def rewrite_prompt(runtime, request: RewriteInput, *, scope, run_id=None, step_id=None, composer=None, cancel=None,
                   record_model=None):
    instruction = request.instruction.strip()
    if not instruction or len(set(request.shot_ids)) != len(request.shot_ids):
        raise HarnessError("invalid_argument")
    explicit = {rid: _reference(runtime, rid, required=True) for rid in dict.fromkeys(request.reference_round_ids)}
    if composer is not None:
        if run_id or step_id or request.shot_ids or request.field not in (None, "prompt"):
            raise HarnessError("invalid_argument")
        field = "prompt"
        targets = [({"shot_id": None, "seq": 0, "fields": {"prompt": composer.get("prompt", "")}}, composer)]
    else:
        if not run_id or not step_id:
            raise HarnessError("invalid_argument")
        with runtime.workflows.shot_run(run_id, write=True) as run:
            step = _steps(run).get(step_id)
            if step is None:
                raise HarnessError("not_found")
            step_type = step["type"]
            field = request.field or ("video_prompt" if step_type == "h3_prompt" else "keyframe_prompt")
            if field not in SHOT_FIELDS.get(step_type, ()):
                raise HarnessError("invalid_argument")
            rows = _rows(run, step_id)
            ids = request.shot_ids or list(rows)
            if not ids or any(sid not in rows for sid in ids):
                raise HarnessError("not_found")
            if len(ids) > 8:
                raise HarnessError("invalid_argument")
            targets = [(_shot(run, step, *rows[sid]), {**step["config"], **{
                key: rows[sid][1][key] for key in ("video_round_id", "video_task", "last_frame_round_id") if key in rows[sid][1]
            }}) for sid in ids]

    try:
        provider, model = runtime.studio.llm.resolve()
    except (LlmError, ValueError) as exc:
        raise HarnessError("model_unconfigured") from exc
    if record_model:
        record_model(model, provider.key)
    before, after, reads, writes = [], [], [], []
    refs = {}
    for shot, options in targets:
        if cancel and cancel.is_set():
            raise HarnessError("turn_stopped")
        sid, n = shot["shot_id"], shot["seq"]
        original = shot["fields"].get(field, "")
        reference_ids = list(explicit)
        keyframe = shot.get("keyframe_round_id")
        tail = options.get("last_frame_round_id") if options.get("workflow") == "fl2va" and field == "video_prompt" else None
        if keyframe:
            reference_ids.insert(0, keyframe)
        if Store.valid_id(tail):
            reference_ids.append(tail)
        references = []
        used = set()
        for rid in list(dict.fromkeys(reference_ids))[:LIMITS["refs_max"]]:
            reference = explicit.get(rid) or _reference(runtime, rid)
            if reference:
                item, data = reference
                refs.setdefault(rid, item)
                used.add(rid)
                references.append(data)
        brief = f"修改要求：{instruction}\n现有提示词：\n{original}"
        if title := shot.get("title"):
            brief = f"镜头：{title}\n{brief}"
        mode = "video" if field == "video_prompt" or composer and composer.get("mode") == "video" else "image"
        value = _writer(runtime, brief, mode, options={**options, "has_last_image": tail in used},
                        image_data=references, provider=provider, model=model)
        before.append({"shot_id": sid, "n": n, "text": original})
        after.append({"shot_id": sid, "n": n, "text": value})
        if sid:
            version = {"shot_id": sid, "field": field, "generation": shot["generation"],
                       "expected_version": shot["field_versions"][field]}
            reads.append(version)
            writes.append({**version, "value": value})
    if cancel and cancel.is_set():
        raise HarnessError("turn_stopped")
    now = int(time.time())
    proposal = {"proposal_id": "pr_" + secrets.token_hex(12), "scope_key": scope,
                "kind": "composer" if composer is not None else "shots", "run_id": run_id, "step_id": step_id,
                "target": {"shot_ids": [item["shot_id"] for item in reads], "field": field, "instruction": instruction,
                           **({"workspace": composer["mode"]} if composer is not None else {}),
                           "reference_round_ids": list(explicit), "conflicts": []},
                "readset": reads, "writeset": writes, "before": before, "after": after,
                "references_used": list(refs.values()), "model": model, "status": "pending", "undo_id": None,
                "created_at": now, "expires_at": now + PROPOSAL_TTL}
    runtime.harness_store.save_proposal(proposal)
    return proposal


def _diff(patches, rows, numbers=()):
    conflicts = []
    numbers = dict(numbers)
    for patch in patches:
        sid, field = patch["shot_id"], patch["field"]
        n, row = rows.get(sid, (numbers.get(sid), {}))
        generation = row.get("generation")
        version = row.get("field_versions", {}).get(field)
        if generation != patch["generation"] or version != patch["expected_version"]:
            conflicts.append({"shot_id": sid, "field": field, "expected_version": patch["expected_version"],
                              "current_version": version, "expected_generation": patch["generation"],
                              "current_generation": generation, "n": n})
    return conflicts


def _write(db, store, rows, patches):
    changed, inverse, expected = [], [], []
    for patch in patches:
        sid, field, value = patch["shot_id"], patch["field"], patch["value"]
        n, row = rows[sid]
        versions = row["field_versions"]
        old = str(row.get(field) or "")
        if old == value:
            continue
        versions[field] += 1
        row[field] = value
        store.store_fields(db, row)
        version = {"shot_id": sid, "field": field, "generation": row["generation"], "expected_version": versions[field]}
        expected.append(version)
        inverse.append({**version, "value": old})
        changed.append({"shot_id": sid, "n": n, "field": field, "generation": row["generation"],
                        "version": versions[field], "value": value})
    return changed, inverse, expected


def _result(run, step_id, changes, *, conflicts=(), undo_id=None, proposal=None):
    return {"applied": changes, "conflicts": list(conflicts), "undo_id": undo_id,
            "step_output": copy.deepcopy(_output(run, step_id)),
            "run_updated": {"run_id": run["id"], "step_id": step_id, "changes": changes},
            "proposal": proposal}


def _conflict(conflicts=(), *, status=None):
    return HarnessError("shot_conflict", details={"conflicts": list(conflicts), **({"status": status} if status else {})})


def apply_shot_edits(runtime, *, atomicity="all", proposal_id=None, run_id=None, step_id=None,
                     patches=(), scope=None, record_undo=True):
    store = runtime.harness_store
    if atomicity not in ("all", "per_shot"):
        raise HarnessError("invalid_argument")
    if proposal_id:
        p = store.get_proposal(proposal_id)
        if not p or (scope and p["scope_key"] != scope):
            raise HarnessError("not_found")
        if p["kind"] == "composer":
            raise HarnessError("approval_required")
        run_id, step_id = p["run_id"], p["step_id"]
    if not run_id or not step_id:
        raise HarnessError("invalid_argument")
    with runtime.workflows.shot_run(run_id, write=True) as run:
        rows = _rows(run, step_id)
        with store.transaction() as db:
            proposal = store.read_proposal(db, proposal_id) if proposal_id else None
            numbers = ()
            if proposal:
                status = proposal["status"]
                if status == "applied":
                    return _result(run, step_id, proposal["target"].get("applied", []),
                                   conflicts=proposal["target"].get("conflicts", ()), undo_id=proposal["undo_id"],
                                   proposal=store.public_proposal(proposal))
                if status != "pending" or proposal["expires_at"] <= time.time():
                    raise _conflict(status="expired" if status == "pending" else status)
                patches = proposal["writeset"]
                numbers = ((item["shot_id"], item["n"]) for item in proposal["before"])
            else:
                allowed = SHOT_FIELDS.get(_steps(run).get(step_id, {}).get("type"), ())
                if not allowed:
                    raise HarnessError("not_found")
                keys = {(patch["shot_id"], patch["field"]) for patch in patches}
                if not 1 <= len(patches) <= 32 or len(patches) != len(keys) or any(field not in allowed for _, field in keys):
                    raise HarnessError("invalid_argument")
            conflicts = _diff(patches, rows, numbers)
            if conflicts and atomicity == "all":
                raise _conflict(conflicts)
            skipped = {conflict["shot_id"] for conflict in conflicts}
            accepted = [patch for patch in patches if patch["shot_id"] not in skipped]
            if not accepted:
                raise _conflict(conflicts)
            changes, inverse, expected = _write(db, store, rows, accepted)
            undo_id = None
            if expected and record_undo:
                undo_id = "un_" + secrets.token_hex(12)
                db.execute("""INSERT INTO undo_records (undo_id, scope_key, run_id, step_id, inverse_json,
                           expected_versions_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                           (undo_id, scope or run_id, run_id, step_id, dump(inverse), dump(expected), int(time.time())))
            if proposal:
                proposal["target"].update(conflicts=conflicts, applied=changes)
                store.proposal_status(db, proposal, "applied", undo_id=undo_id)
        if changes:
            runtime.workflows.mirror_shot_write(run)
        return _result(run, step_id, changes, conflicts=conflicts, undo_id=undo_id,
                       proposal=store.public_proposal(proposal) if proposal else None)


def reject_proposal(runtime, proposal_id):
    store = runtime.harness_store
    with store.transaction() as db:
        proposal = store.read_proposal(db, proposal_id)
        if not proposal:
            raise HarnessError("not_found")
        if proposal["status"] == "rejected":
            return store.public_proposal(proposal)
        if proposal["status"] != "pending" or proposal["expires_at"] <= time.time():
            raise _conflict(status="expired" if proposal["status"] == "pending" else proposal["status"])
        store.proposal_status(db, proposal, "rejected")
        return store.public_proposal(proposal)


def apply_composer(runtime, proposal_id, current: ComposerPrompt):
    store = runtime.harness_store
    with store.transaction() as db:
        proposal = store.read_proposal(db, proposal_id)
        if not proposal or proposal["kind"] != "composer":
            raise HarnessError("not_found")
        before, after = proposal["before"][0]["text"], proposal["after"][0]["text"]
        workspace = proposal["target"].get("workspace", current.workspace)
        if workspace != current.workspace:
            raise _conflict()
        if proposal["status"] == "applied" and current.prompt in (before, after):
            return {"workspace": workspace, "prompt": after, "proposal": store.public_proposal(proposal)}
        if proposal["status"] != "pending" or proposal["expires_at"] <= time.time():
            raise _conflict(status="expired" if proposal["status"] == "pending" else proposal["status"])
        if before != current.prompt:
            raise _conflict()
        undo_id = "un_" + secrets.token_hex(12)
        db.execute("""INSERT INTO undo_records (undo_id,scope_key,run_id,step_id,inverse_json,expected_versions_json,created_at)
                      VALUES (?, ?, '', '', ?, ?, ?)""", (undo_id, proposal["scope_key"],
                   dump({"workspace": workspace, "prompt": before}), dump({"workspace": workspace, "prompt": after}), int(time.time())))
        store.proposal_status(db, proposal, "applied", undo_id=undo_id)
        return {"workspace": workspace, "prompt": after, "proposal": store.public_proposal(proposal)}


def undo_composer(runtime, undo_id, current: ComposerPrompt):
    store = runtime.harness_store
    with store.transaction() as db:
        record = db.execute("SELECT * FROM undo_records WHERE undo_id=? AND run_id=''", (undo_id,)).fetchone()
        proposal = store.decode_proposal(db.execute("SELECT * FROM proposals WHERE undo_id=?", (undo_id,)).fetchone())
        if not record or not proposal:
            raise HarnessError("not_found")
        if record["consumed"] or record["created_at"] + UNDO_TTL <= time.time():
            raise _conflict(status="expired")
        if json.loads(record["expected_versions_json"]) != current.model_dump():
            raise _conflict()
        db.execute("UPDATE undo_records SET consumed=1 WHERE undo_id=?", (undo_id,))
        store.proposal_status(db, proposal, "undone", undo_id=undo_id)
        return {**json.loads(record["inverse_json"]), "proposal": store.public_proposal(proposal)}


def undo_change(runtime, undo_id, *, scope=None):
    store = runtime.harness_store
    with store.transaction() as db:
        record = db.execute("SELECT * FROM undo_records WHERE undo_id=?", (undo_id,)).fetchone()
    if not record or (scope and record["scope_key"] != scope):
        raise HarnessError("not_found")
    run_id, step_id = record["run_id"], record["step_id"]
    with runtime.workflows.shot_run(run_id, write=True) as run:
        rows = _rows(run, step_id)
        with store.transaction() as db:
            record = db.execute("SELECT * FROM undo_records WHERE undo_id=?", (undo_id,)).fetchone()
            conflicts = _diff(json.loads(record["expected_versions_json"]), rows)
            if record["consumed"] or record["created_at"] + UNDO_TTL <= time.time():
                raise _conflict(conflicts, status="expired")
            if conflicts:
                raise _conflict(conflicts)
            changes, _, _ = _write(db, store, rows, json.loads(record["inverse_json"]))
            db.execute("UPDATE undo_records SET consumed=1 WHERE undo_id=?", (undo_id,))
            proposal = store.decode_proposal(db.execute("SELECT * FROM proposals WHERE undo_id=?", (undo_id,)).fetchone())
            if proposal:
                store.proposal_status(db, proposal, "undone", undo_id=undo_id)
        runtime.workflows.mirror_shot_write(run)
        return _result(run, step_id, changes, proposal=store.public_proposal(proposal) if proposal else None)
