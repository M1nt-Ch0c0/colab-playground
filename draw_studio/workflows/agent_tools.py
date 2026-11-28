"""The editor actions available to the workflow copilot during one conversation turn."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import threading
import uuid

from pydantic import ValidationError

from ..gallery import Store
from ..generation.catalog import (
    COMFY_CLIP_TYPES, COMFY_SAMPLERS, COMFY_SCHEDULERS, COMFY_TEMPLATES, DEFAULTS, GPUS, IMAGE_MODELS,
    LIMITS, VIDEO_OFFLOAD_MODES, VIDEO_WORKFLOWS,
)
from ..generation.parameters import normalize_loras
from ..generation.video_reference import VIDEO_TASKS
from ..logs import redact_secrets
from .definitions import STEP_CATALOG, STEP_ID_RE, STEPS_MAX, VAR_RE, normalize_workflow_def, step_position, workflow_variables
from .harness_errors import HarnessError
from .shot_service import RewriteInput, ShotEdit, apply_shot_edits, read_shots, rewrite_prompt, undo_change
from .engine import RUN_ID_RE


def obj(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, "required": list(required),
            "additionalProperties": False}


TEXT = {"type": "string"}
BOOL = {"type": "boolean"}


def enum(*options):
    return {"type": "string", "enum": list(options)}


def array(schema, limit, *, minimum=0):
    return {"type": "array", "items": schema, "minItems": minimum, "maxItems": limit}


def integer(low, high):
    return {"type": "integer", "minimum": low, "maximum": high}


STEP_TYPES = {item["type"]: item for item in STEP_CATALOG}
STEP_TYPES["video_gen"] = {**STEP_TYPES["video_gen"], "default_config": {
    **STEP_TYPES["video_gen"]["default_config"], "offload_mode": "auto",
}}
OPERATIONS = {
    "set_topic": {"op", "text"}, "rename_workflow": {"op", "name"},
    "add_step": {"op", "step_id", "step_type", "after", "name", "config", "enabled", "pause_after", "position"},
    "update_step": {"op", "step_id", "name", "config", "enabled", "pause_after", "position"},
    "move_step": {"op", "step_id", "after"}, "remove_step": {"op", "step_id"},
    "set_variable": {"op", "name", "value"}, "remove_variable": {"op", "name"},
}
OP_SCHEMA = obj({
    "op": {"type": "string", "enum": list(OPERATIONS)},
    "step_id": TEXT, "step_type": {"type": "string", "enum": list(STEP_TYPES)},
    "after": {"type": "string", "description": "Preceding step id. Empty means first. Omit on add to append."},
    "name": TEXT, "text": TEXT, "enabled": {"type": "boolean"}, "pause_after": {"type": "boolean"},
    "config": {"type": "object", "description": "Only the changed fields from this step's config."},
    "position": obj({"x": {"type": "number"}, "y": {"type": "number"}}, ["x", "y"]),
    "value": {"description": "Workflow variable value (text, number or boolean)."},
}, ["op"])
TOOLS = {
    "studio_read_context": ("读取当前工作区、工作流、选择与参考槽。", obj()),
    "studio_get_catalog": ("查询创作参数和节点目录。", obj({
        "section": enum("image", "video", "comfy", "limits", "nodes")}, ["section"])),
    "studio_list_templates": ("列出工作流模板。", obj()),
    "studio_manage_template": ("保存当前工作流为自定义模板，或删除自定义模板。", obj({
        "op": enum("save", "delete"), "template_id": TEXT, "name": TEXT}, ["op"])),
    "studio_list_runs": ("查看工作流运行记录和草稿。", obj({"limit": integer(1, 40)})),
    "studio_create_draft": ("从模板、工作流定义或当前草稿创建运行记录。", obj({
        "template_id": TEXT, "definition": {"type": "object"}, "topic": TEXT, "request_id": TEXT})),
    "studio_read_workflow": ("读取当前工作流的主题、变量、步骤、选择和运行状态。", obj()),
    "studio_list_nodes": ("列出可编排的节点。指定 step_type 可取得参数和默认值。", obj({"step_type": TEXT})),
    "studio_edit_workflow": ("编辑当前草稿的主题、名称、变量、步骤和连线。改步骤参数用 update_step 的 step_id 和 config。", obj({
        "operations": array(OP_SCHEMA, 32, minimum=1)}, ["operations"])),
    "studio_validate_workflow": ("检查当前草稿的连线、素材和变量引用。", obj()),
    "studio_manage_run_assets": ("查看运行素材、绑定作品库图片或移除该运行的素材和引用。", obj({
        "op": enum("list", "bind_rounds", "remove"), "run_id": TEXT, "step_id": TEXT,
        "round_ids": array(TEXT, 32, minimum=1), "filename": TEXT}, ["op"])),
    "studio_read_shots": ("读取分镜或视频提示词步骤的镜头、字段版本、关联画面和片段。", obj({
        "run_id": TEXT, "step_id": TEXT})),
    "studio_rewrite_prompt": ("为选定镜头或当前创作台生成待采用的提示词，保留已有内容。", obj({
        "target": enum("shots", "composer"), "run_id": TEXT, "step_id": TEXT,
        "shot_ids": array(TEXT, 8), "field": enum("keyframe_prompt", "video_prompt", "prompt"), "instruction": TEXT,
        "reference_round_ids": array(TEXT, LIMITS["refs_max"])}, ["instruction"])),
    "studio_apply_shot_edits": ("用户明确要求写回时，按提案或镜头字段版本采用修改。", obj({
        "proposal_id": TEXT, "run_id": TEXT, "step_id": TEXT, "atomicity": enum("all", "per_shot"),
        "edits": array(obj({"shot_id": TEXT, "field": enum("keyframe_prompt", "video_prompt", "prompt", "audio_notes", "search_query"),
                            "generation": {"type": "integer"}, "expected_version": {"type": "integer"}, "value": TEXT},
                           ["shot_id", "field", "generation", "expected_version", "value"]), 32, minimum=1)})),
    "studio_undo_change": ("撤销指定的镜头改动。", obj({"undo_id": TEXT}, ["undo_id"])),
    "studio_request_run": ("用户要求执行时向编辑器提交运行操作。已有运行可指定 step_id 和 single_step。", obj({
        "step_id": TEXT, "single_step": BOOL})),
    "studio_run_status": ("查看进度和日志，或停止一个明确指定的工作流运行。", obj({
        "op": enum("watch", "cancel"), "run_id": TEXT, "log_offset": integer(0, 2**31 - 1)}, ["op"])),
    "studio_find_assets": ("按关键词、媒体类型或收藏筛选作品库。", obj({
        "query": TEXT, "kind": enum("image", "video"), "starred": BOOL, "offset": integer(0, 10000), "limit": integer(1, 24)})),
    "studio_inspect_asset": ("读取单件作品的尺寸、时长、来源和生成参数。", obj({"round_id": TEXT}, ["round_id"])),
}
TOOL_LABELS = dict(zip(TOOLS, [
    "查看工作台", "查看模型参数", "浏览模板", "整理模板", "查看运行记录", "新建草稿",
    "读取工作流", "查看节点", "修改工作流", "检查工作流", "整理素材",
    "读取分镜", "改写提示词", "应用修改", "撤销修改", "准备运行", "查看进度", "查找作品", "查看作品信息",
], strict=True))
REF_TYPES = {"asset_input", "web_asset_fetch", "image_gen"}
REF_LISTS = ("ref_sources", "extra_ref_sources")
SOURCE_TYPES = {"scenes_from": {"llm_script"}, "keyframe_from": {"image_gen"},
                "prompts_from": {"h3_prompt"}, "clips_from": {"video_gen"},
                "video_from": {"video_gen", "video_stitch"},
                **dict.fromkeys(REF_LISTS, REF_TYPES)}
GPU_IDS = {gpu["id"] for gpu in GPUS}
CONFIG_OPTIONS = {
    "workflow": {item["id"] for item in VIDEO_WORKFLOWS},
    "video_task": VIDEO_TASKS,
    "offload_mode": {item["id"] for item in VIDEO_OFFLOAD_MODES},
}
BOUNDS = {
    "scene_count": (1, 8), "max_scenes": (1, 8), "max_images": (1, LIMITS["refs_max"]),
    "fps": (12, 60), "target_width": (256, 4096), "target_height": (256, 4096), "fade_s": (0.1, 1.5),
    **{key: (LIMITS[f"{limit}_min"], LIMITS[f"{limit}_max"]) for key, limit in (
        ("width", "size"), ("height", "size"), ("steps", "steps"), ("cfg", "cfg"),
        ("num_frames", "frames"), ("poll_rounds", "poll_rounds"),
    )},
}


def editor_value(record: dict) -> dict:
    wf = record["workflow"]
    return {"topic": record.get("topic", ""), "name": wf.get("name", ""),
            "description": wf.get("description", ""), "default_topic": wf.get("default_topic", ""),
            "variables": wf.get("variables", {}), "steps": wf["steps"]}


def editor_revision(record):
    value = {**editor_value(record), "status": record.get("status", "draft")}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _text(value, label, maximum, *, empty=False):
    if not isinstance(value, str) or len(value) > maximum or not empty and not value.strip():
        raise ValueError(f"{label}无效（最多 {maximum} 字）")
    return value.strip()


def _number(value, label, *, integer=False, bounds=None):
    if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)):
        raise ValueError(f"{label} 需要有限数字")
    if bounds and not bounds[0] <= value <= bounds[1]:
        raise ValueError(f"{label} 须在 {bounds[0]}–{bounds[1]} 之间")
    if integer:
        result = int(value)
        if result != value:
            raise ValueError(f"{label} 需要整数")
        return result
    return value


def _config_value(key, value, default):
    if type(default) in (int, float):
        return _number(value, key, integer=type(default) is int, bounds=BOUNDS.get(key))
    if default is not None and type(value) is not type(default):
        raise ValueError(f"{key} 类型错误")
    if key in CONFIG_OPTIONS and value not in CONFIG_OPTIONS[key]:
        raise ValueError(f"{key} 取值无效")
    if key in ("video_round_id", "last_frame_round_id") and value and not Store.valid_id(value):
        raise ValueError(f"{key} 需要作品编号")
    if key in ("round_ids", "clip_round_ids") and not all(Store.valid_id(item) for item in value):
        raise ValueError(f"{key} 需要作品编号列表")
    if key in REF_LISTS and not all(isinstance(item, str) and STEP_ID_RE.fullmatch(item) for item in value):
        raise ValueError(f"{key} 需要上游步骤列表")
    if key in SOURCE_TYPES and key not in REF_LISTS and value and not STEP_ID_RE.fullmatch(value):
        raise ValueError(f"{key} 需要上游步骤")
    if key in ("gpu", "gpu_pool"):
        ids = [value] if key == "gpu" else value
        if not all(isinstance(item, str) and item.strip().upper() in GPU_IDS for item in ids):
            raise ValueError(f"{key} 含无效选项")
    if key == "loras":
        if len(value) > LIMITS["loras_max"]:
            raise ValueError("LoRA 数量超出上限")
        for item in value:
            if isinstance(item, dict):
                if any(not isinstance(item[k], str) for k in ("url", "repo_id", "weight_name") if k in item):
                    raise ValueError("LoRA 地址和文件名需要文本")
                if "scale" in item:
                    _number(item["scale"], "LoRA 权重", bounds=(0, LIMITS["lora_scale_max"]))
        if len(normalize_loras(value)) != len(value):
            raise ValueError("LoRA 列表含无效项")
    return value


def _apply(editor, op):
    kind = op.get("op") if isinstance(op, dict) else None
    if not isinstance(kind, str) or kind not in OPERATIONS or op.keys() - OPERATIONS[kind]:
        raise ValueError("操作名称或参数无效")
    wf, steps = editor["workflow"], editor["workflow"]["steps"]
    if kind in ("set_variable", "remove_variable"):
        key = _text(op.get("name"), "变量名", 48)
        variables = dict(wf.get("variables", {}))
        if kind == "set_variable":
            variables[key] = op.get("value")
        elif key in variables:
            del variables[key]
        else:
            raise ValueError(f"找不到变量 {key}")
        wf["variables"] = workflow_variables(variables)
        return
    if kind == "set_topic":
        editor["topic"] = _text(op.get("text"), "主题", 2000, empty=True)
        return
    if kind == "rename_workflow":
        wf["name"] = _text(op.get("name"), "模板名称", 80)
        return
    sid = _text(op.get("step_id"), "步骤 ID", 48)
    if not STEP_ID_RE.fullmatch(sid):
        raise ValueError("步骤 ID 仅支持字母、数字、短横线和下划线")
    step = next((s for s in steps if s["id"] == sid), None)
    if kind == "add_step":
        stype = op.get("step_type")
        if step or not isinstance(stype, str) or stype not in STEP_TYPES:
            raise ValueError("新步骤需要未占用的 ID 和有效的 step_type")
        cat = STEP_TYPES[stype]
        step = {"id": sid, "type": stype, "name": cat["label"], "config": copy.deepcopy(cat["default_config"]),
                "enabled": True, "pause_after": False}
    elif step is None:
        raise HarnessError("not_found", details={"step_id": sid})
    if kind in ("move_step", "remove_step"):
        steps.remove(step)
    if kind == "remove_step":
        return
    if kind in ("add_step", "move_step"):
        if kind == "move_step" and "after" not in op:
            raise ValueError("移动步骤需要指定 after，可传空字符串移到最前")
        index = len(steps)
        if "after" in op:
            after = _text(op["after"], "上一步", 48, empty=True)
            previous = next((i for i, item in enumerate(steps) if item["id"] == after), None)
            if after != "" and previous is None:
                raise ValueError(f"找不到要插入的位置 {after}")
            index = 0 if after == "" else previous + 1
        steps.insert(index, step)
        if kind == "add_step":
            earlier = {s["id"]: s["type"] for s in steps[:index]}
            explicit = op.get("config", {})
            if not isinstance(explicit, dict):
                raise ValueError("config 需要对象")
            for key, types in SOURCE_TYPES.items():
                if key not in step["config"] or key in explicit:
                    continue
                default = step["config"][key]
                if key in REF_LISTS:
                    step["config"][key] = [ref for ref in default if earlier.get(ref) in types]
                elif default and earlier.get(default) not in types:
                    step["config"][key] = next((s for s in reversed(earlier) if earlier[s] in types), "")
    if "name" in op:
        step["name"] = _text(op["name"], "步骤名称", 80)
    if "position" in op:
        if not isinstance(op["position"], dict) or op["position"].keys() != {"x", "y"}:
            raise ValueError("position 需要 x 和 y")
        step["position"] = step_position(op["position"])
    for key in ("enabled", "pause_after"):
        if key in op:
            if type(op[key]) is not bool:
                raise ValueError(f"{key} 需要布尔值")
            step[key] = op[key]
    if "config" in op:
        cfg = op["config"]
        allowed = step["config"] | STEP_TYPES[step["type"]]["default_config"]
        if not isinstance(cfg, dict) or cfg.keys() - allowed.keys() or "asset_files" in cfg:
            raise ValueError(f"{sid} 的 config 含不支持的参数，请先查看该类节点")
        step["config"].update({key: _config_value(key, value, allowed[key]) for key, value in cfg.items()})


def _bad_sources(steps):
    errors, earlier = {}, {}
    for step in steps:
        for key, value in step["config"].items():
            if key not in SOURCE_TYPES:
                continue
            for ref in value if isinstance(value, list) else [value]:
                if not ref:
                    continue
                if not isinstance(ref, str) or earlier.get(ref) not in SOURCE_TYPES[key]:
                    errors[step["id"], key, str(ref)] = f"{step['id']}.{key} 的上游 {ref} 缺失、类型错误或位于本步骤之后"
        earlier[step["id"]] = step["type"]
    return errors


def _source_ids(step):
    for key, value in step["config"].items():
        if key in SOURCE_TYPES:
            yield from (ref for ref in (value if isinstance(value, list) else [value]) if isinstance(ref, str) and ref)


def _template_definition(workflow):
    result = copy.deepcopy(workflow)
    for step in result.get("steps", ()):
        step["config"].pop("asset_files", None)
    return result


def _new_definition(raw):
    if not isinstance(raw, dict) or raw.keys() - {"name", "description", "default_topic", "variables", "steps"}:
        raise ValueError("工作流定义无效")
    if not isinstance(raw.get("steps"), list) or not 1 <= len(raw["steps"]) <= STEPS_MAX:
        raise ValueError("工作流步骤数无效")
    definition = {**raw, "steps": []}
    candidate = {"workflow": definition}
    for step in raw["steps"]:
        if (not isinstance(step, dict) or not {"id", "type"} <= step.keys()
                or step.keys() - {"id", "type", "name", "config", "enabled", "pause_after", "position"}):
            raise ValueError("步骤定义无效")
        _apply(candidate, dict(op="add_step", step_id=step["id"], step_type=step["type"],
                               **{key: value for key, value in step.items() if key not in ("id", "type")}))
    if errors := _bad_sources(definition["steps"]):
        raise ValueError("。".join(sorted(errors.values())))
    return normalize_workflow_def(definition)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


CATALOG = {
    "image": {"models": IMAGE_MODELS, "defaults": DEFAULTS["image"]},
    "video": {"workflows": VIDEO_WORKFLOWS, "offload_modes": VIDEO_OFFLOAD_MODES, "video_tasks": list(VIDEO_TASKS),
              "defaults": DEFAULTS["video"]},
    "comfy": {"templates": COMFY_TEMPLATES, "samplers": COMFY_SAMPLERS, "schedulers": COMFY_SCHEDULERS,
              "clip_types": COMFY_CLIP_TYPES},
    "limits": {key: value for key, value in LIMITS.items() if not key.startswith("idle_")},
    "nodes": list(STEP_TYPES.values()),
}


class EditorTools:
    def __init__(self, runtime, snapshot: dict, *, selected: str = "", run_id: str | None = None,
                 scope=None, revision=None, workspace="workflow", selected_shot=None, composer=None):
        self.runtime = runtime
        self.original = copy.deepcopy(snapshot)
        self.editor = copy.deepcopy(snapshot)
        self.selected = selected
        self.run_id = run_id
        self.scope = scope or run_id or "once-" + uuid.uuid4().hex
        self.revision = revision
        self.workspace = workspace
        self.selected_shot = selected_shot
        self.composer = composer
        self.run_request = None
        self.calls: list[str] = []
        self.proposal_ids: list[str] = []
        self.run_updates: list[dict] = []
        self.refresh_run = False
        self.refresh_library = False
        self.cancel = None
        self.lock = threading.RLock()

    def _run(self):
        run = self.runtime.workflows.get_run(self.run_id) if self.run_id else None
        if self.run_id and not run:
            raise HarnessError("not_found")
        return run

    def context(self):
        with self.lock:
            return self._context(self._run())

    def _view(self, run):
        return run if run is not None and self.editor == self.original else self.editor

    def _context(self, run):
        states = (run or {}).get("step_states", {})
        stages = {key: {"status": state.get("status"), "error": str(state.get("error") or "")[:500]}
                  for key, state in states.items()}
        output = states.get(self.selected, {}).get("output")
        return {**copy.deepcopy(editor_value(self._view(run))), "selected_step": self.selected,
                "selected_shot": self.selected_shot, "revision": editor_revision(run or self.editor),
                "selected_output": json.dumps(output, ensure_ascii=False)[:4000] if output else "",
                "status": (run or {}).get("status", "draft"), "step_states": stages}

    def _valid_run_request(self, request):
        return any(step["enabled"] and request["step_id"] in ("", step["id"])
                   for step in self.editor["workflow"]["steps"])

    def final_run_request(self):
        with self.lock:
            if self.run_request and not self._valid_run_request(self.run_request):
                self.run_request = None
            return self.run_request

    def call(self, name: str, args: dict):
        try:
            return self._call(name, args)
        except ValidationError as exc:
            raise HarnessError("invalid_argument", details={"fields": [list(e["loc"]) for e in exc.errors()]}) from exc
        except ValueError as exc:
            raise HarnessError("invalid_argument", details={"reason": str(exc)}) from exc

    def _call(self, name: str, args: dict):
        with self.lock:
            if name not in TOOLS:
                raise ValueError("未知工具")
            if len(self.calls) >= 32:
                raise HarnessError("tool_limit_reached")
            self.calls.append(name)
            spec = TOOLS[name][1]
            if not isinstance(args, dict) or args.keys() - spec["properties"].keys() or set(spec["required"]) - args.keys():
                raise ValueError("工具参数无效")
            run = self._run()
            if name not in ("studio_read_workflow", "studio_list_nodes", "studio_edit_workflow", "studio_request_run"):
                return self._creative(name, args, run)
            if name == "studio_read_workflow":
                return self._context(run)
            if name == "studio_list_nodes":
                if "step_type" in args:
                    kind = args["step_type"]
                    if not isinstance(kind, str) or kind not in STEP_TYPES:
                        raise ValueError("节点类型不存在")
                    return STEP_TYPES[kind]
                return [{"type": s["type"], "name": s["label"]} for s in STEP_CATALOG]
            if run and run["status"] == "running":
                raise HarnessError("running_locked")
            if name == "studio_request_run":
                sid = _text(args.get("step_id", ""), "步骤", 48, empty=True)
                if sid and not self.run_id:
                    raise ValueError("指定步骤需要已保存的运行")
                if "single_step" in args and (not sid or type(args["single_step"]) is not bool):
                    raise ValueError("single_step 需要指定步骤")
                request = {"step_id": sid, "single_step": args.get("single_step", True)}
                if not self._valid_run_request(request):
                    raise ValueError("没有可运行的目标步骤")
                self.run_request = request
                return {"requested": True, "state": "awaiting_editor"}
            ops = args.get("operations")
            if not isinstance(ops, list) or not 1 <= len(ops) <= 32:
                raise ValueError("请提供 1–32 个编辑操作")
            candidate = copy.deepcopy(self.editor)
            for op in ops:
                _apply(candidate, op)
            wf = candidate["workflow"]
            if len(wf["steps"]) > STEPS_MAX or len(json.dumps(candidate, ensure_ascii=False, allow_nan=False)) > 90000:
                raise ValueError("草稿超过工作流大小限制")
            explicit = {(op["step_id"].strip(), key) for op in ops if "config" in op
                        for key in op["config"] if key in SOURCE_TYPES}
            old_errors = _bad_sources(self.editor["workflow"]["steps"])
            new_errors = [error for (sid, key, ref), error in _bad_sources(wf["steps"]).items()
                          if (sid, key, ref) not in old_errors or (sid, key) in explicit]
            if new_errors:
                raise ValueError("。".join(sorted(new_errors)))
            if wf["steps"]:
                normalized = normalize_workflow_def({**wf, "id": ""})
                wf["steps"] = normalized["steps"]
            elif self.run_id:
                raise ValueError("已保存的运行需要至少一个步骤")
            self.editor = candidate
            invalidated = self.run_request is not None and self.final_run_request() is None
            return {"staged": len(ops), "step_ids": [s["id"] for s in wf["steps"]], "state": "awaiting_editor",
                    **({"run_request_invalidated": True} if invalidated else {})}

    def _target_run(self, args):
        rid = args.get("run_id", self.run_id)
        if not isinstance(rid, str) or not RUN_ID_RE.fullmatch(rid):
            raise ValueError("需要有效的运行记录")
        return rid

    def _target_step(self, args, *, required=False):
        step = args.get("step_id", self.selected)
        if not step and not required and "step_id" not in args:
            return None
        if not isinstance(step, str) or not STEP_ID_RE.fullmatch(step):
            raise ValueError("需要有效的步骤")
        return step

    def _creative(self, name, args, run):
        runtime, engine = self.runtime, self.runtime.workflows
        if name == "studio_read_context":
            refs = runtime.studio.refs_report()
            view = self._view(run)
            return {"workspace": self.workspace, "run_id": self.run_id,
                    "draft_id": self.scope.removeprefix("wr_") if not self.run_id and RUN_ID_RE.fullmatch(self.scope) else None,
                    "selected_step": self.selected or None, "selected_shot": self.selected_shot,
                    "revision": editor_revision(run or self.editor),
                    "workflow": {"name": view["workflow"]["name"], "topic": view["topic"],
                                 "status": run["status"] if run else "draft"},
                    "composer": {**self.composer, "prompt": self.composer.get("prompt", "")[:280]} if self.composer else None,
                    "references": {
                        "image_count": len(refs.get("items", ())), "first": bool(refs.get("first", {}).get("set")),
                        "last": bool(refs.get("last", {}).get("set")), "video": bool(refs.get("video")),
                    }}
        if name == "studio_get_catalog":
            section = args["section"]
            if not isinstance(section, str) or section not in CATALOG:
                raise ValueError("目录分区无效")
            return CATALOG[section]
        if name == "studio_list_templates":
            data = engine.list_workflows()
            return [{key: item[key] for key in ("id", "name", "description", "builtin") if key in item}
                    | {"step_count": len(item["steps"])} for item in [*data["builtin"], *data["custom"]]]
        if name == "studio_manage_template":
            op = args["op"]
            identifier = _text(args["template_id"], "模板", 80) if "template_id" in args else None
            if identifier and not re.fullmatch(r"wf_[A-Za-z0-9_-]{4,48}", identifier):
                raise ValueError("仅可修改自定义模板")
            if identifier and not engine.get_workflow(identifier):
                raise HarnessError("not_found")
            if op == "delete" and identifier and "name" not in args:
                if not engine.delete_workflow(identifier)[0]:
                    raise HarnessError("not_found")
                self.refresh_library = True
                return {"deleted": identifier}
            if op != "save":
                raise ValueError("模板操作无效")
            wf = _template_definition(self.editor["workflow"])
            if "name" in args:
                wf["name"] = _text(args["name"], "模板名", 80)
            saved, _ = engine.save_workflow({**wf, "id": identifier or ""})
            self.refresh_library = True
            return {"template_id": saved["id"], "name": saved["name"], "step_count": len(saved["steps"])}
        if name == "studio_list_runs":
            limit = _number(args.get("limit", 20), "数量", integer=True, bounds=(1, 40))
            return [{key: item[key] for key in (
                "id", "workflow_name", "topic", "status", "current_step_id", "done_steps", "total_steps", "final_round_id", "updated_at",
            ) if key in item} for item in engine.list_runs()[:limit]]
        if name == "studio_create_draft":
            if "template_id" in args and "definition" in args:
                raise ValueError("请选择一个草稿来源")
            request_id = args.get("request_id", uuid.uuid4().hex)
            if not isinstance(request_id, str) or not re.fullmatch(r"[a-f0-9]{32}", request_id):
                raise ValueError("草稿请求编号无效")
            if "template_id" in args:
                wid = _text(args["template_id"], "模板", 80)
                if not (definition := engine.get_workflow(wid)):
                    raise HarnessError("not_found")
            elif "definition" in args:
                definition = _new_definition(args["definition"])
            else:
                definition = self.editor["workflow"]
            if not definition.get("steps"):
                raise ValueError("草稿至少需要一个步骤")
            topic = _text(args.get("topic", self.editor["topic"] if set(args).isdisjoint({"template_id", "definition"})
                                   else definition.get("default_topic", "")), "主题", 2000, empty=True)
            saved = engine.create_run({"workflow": _template_definition(definition), "topic": topic, "request_id": request_id})
            self.refresh_library = True
            return {"run_id": saved["id"], "name": saved["workflow"]["name"], "status": saved["status"]}
        if name == "studio_validate_workflow":
            return self._validate(self._view(run)["workflow"])
        if name == "studio_manage_run_assets":
            return self._assets(args)
        if name == "studio_read_shots":
            step = self._target_step(args) if "step_id" in args else None
            return {"shots": read_shots(runtime, self._target_run(args), step)}
        if name == "studio_rewrite_prompt":
            return self._rewrite(args)
        if name == "studio_apply_shot_edits":
            return self._apply_shots(args)
        if name == "studio_undo_change":
            undo_id = _text(args["undo_id"], "撤销", 48)
            if not re.fullmatch(r"un_[a-f0-9]{24}", undo_id):
                raise ValueError("撤销记录无效")
            return self._track_write(undo_change(runtime, undo_id, scope=self.scope))
        if name == "studio_run_status":
            op, rid = args["op"], self._target_run(args)
            if op not in ("watch", "cancel") or (op == "cancel" and "run_id" not in args):
                raise ValueError("停止需要指定运行")
            if op == "cancel" and "log_offset" in args:
                raise ValueError("停止运行无需填写日志偏移")
            offset = _number(args.get("log_offset", 0), "日志偏移", integer=True, bounds=(0, 2**31 - 1))
            if not (current := engine.get_run(rid)):
                raise HarnessError("not_found")
            if op == "cancel":
                current = engine.cancel_run(rid)
                self.refresh_run |= rid == self.run_id
                self.refresh_library = True
            summary = next((item for item in engine.list_runs() if item["id"] == rid), {})
            logs = current.get("logs", [])
            latest = current.get("log_count", len(logs))
            first = latest - len(logs)
            start = max(first, min(offset, latest))
            end = min(latest, start + 30)
            return {"run_id": rid, "status": current["status"], "done_steps": summary.get("done_steps"), "final_round_id": summary.get("final_round_id"),
                    "current_step_id": current["current_step_id"], "logs": [redact_secrets(line)[:400] for line in logs[start - first:end - first]],
                    "next_log_offset": end}
        if name == "studio_find_assets":
            kind, starred = args.get("kind", ""), args.get("starred")
            if kind not in ("", "image", "video") or ("starred" in args and type(starred) is not bool):
                raise ValueError("作品筛选参数无效")
            limit = _number(args.get("limit", 8), "数量", integer=True, bounds=(1, 24))
            offset = _number(args.get("offset", 0), "偏移", integer=True, bounds=(0, 10000))
            query = _text(args.get("query", ""), "检索词", 200, empty=True)
            page = runtime.store.list(kind=kind, q=query, starred=starred, offset=offset, limit=limit)
            rows = [{"id": item["id"], "kind": item["kind"], "starred": bool(item.get("starred")),
                     "prompt": str(item.get("prompt") or "")[:180]} for item in page["rounds"]]
            return rows
        rid = args["round_id"]
        if not Store.valid_id(rid):
            raise ValueError("作品编号无效")
        asset = runtime.store.get(rid)
        if not asset:
            raise HarnessError("not_found")
        fields = ("id", "kind", "model", "engine", "width", "height", "duration_s", "media_duration_s", "workflow",
                  "video_task", "steps", "cfg", "seed", "num_frames", "offload_mode", "starred", "created_at", "media_operation")
        result = {key: value[:160] if isinstance(value, str) else value for key in fields if
                  (value := asset.get(key)) is not None and type(value) in (str, bool, int, float)
                  and (type(value) is not float or math.isfinite(value))}
        result["prompt"] = str(asset.get("prompt") or "")[:180]
        result["source_rounds"] = [value for value in (asset.get("source_rounds") or []) if Store.valid_id(value)][:16]
        for key in ("chain_from", "edit_source_id"):
            if Store.valid_id(asset.get(key)):
                result[key] = asset[key]
        return result

    def _validate(self, workflow):
        steps = workflow["steps"]
        variables = workflow.get("variables", {})
        issues = [{"code": "upstream_invalid", "step_id": step_id, "field": field, "source": ref}
                  for step_id, field, ref in _bad_sources(steps)]
        for step in steps:
            if not step["enabled"]:
                continue
            config = step["config"]
            referenced = {match.group(1).removeprefix("vars.") for text in _strings(config) for match in VAR_RE.finditer(text)
                          if match.group(1).startswith("vars.")}
            issues.extend({"code": "variable_missing", "step_id": step["id"], "variable": key}
                          for key in sorted(referenced - variables.keys()))
            for field, kind in (("round_ids", "image"), ("last_frame_round_id", "image"),
                                ("video_round_id", "video"), ("clip_round_ids", "video")):
                values = config.get(field)
                if not values:
                    continue
                for rid in values if isinstance(values, list) else [values]:
                    media = self.runtime.store.media_path(rid) if Store.valid_id(rid) else None
                    if not media or media[0] != kind:
                        issues.append({"code": "media_invalid", "step_id": step["id"], "field": field, "round_id": rid})
            for filename in config.get("asset_files") or ():
                if not isinstance(filename, str) or not self.run_id or not self.runtime.workflows.asset_path(self.run_id, filename):
                    issues.append({"code": "media_invalid", "step_id": step["id"], "field": "asset_files"})
        if not any(step["enabled"] for step in steps):
            issues.append({"code": "no_enabled_steps"})
        affected = {issue["step_id"] for issue in issues if "step_id" in issue}
        for step in steps:
            if step["enabled"] and any(source in affected for source in _source_ids(step)):
                affected.add(step["id"])
        return {"valid": not issues, "issues": issues,
                "affected_steps": [step["id"] for step in steps if step["id"] in affected]}

    def _assets(self, args):
        engine = self.runtime.workflows
        op, rid = args["op"], self._target_run(args)
        if op not in ("list", "bind_rounds", "remove"):
            raise ValueError("素材操作无效")
        ids = args.get("round_ids")
        filename = args.get("filename")
        if op == "list":
            if "round_ids" in args or "filename" in args:
                raise ValueError("读取素材无需填写作品或文件")
            current = engine.get_run(rid)
            if not current:
                raise HarnessError("not_found")
            step_id = self._target_step(args) if "step_id" in args else None
            bindings = [{"step_id": step["id"], "round_ids": step["config"].get("round_ids", [])[:32],
                         "asset_files": step["config"].get("asset_files", [])[:32]} for step in current["workflow"]["steps"]
                        if step["type"] == "asset_input" and (not step_id or step["id"] == step_id)]
            if step_id and not bindings:
                raise HarnessError("not_found")
            return {"assets": current["assets"][:32], "bindings": bindings}
        if "filename" in args:
            if op != "remove" or "round_ids" in args or "step_id" in args:
                raise ValueError("移除运行文件需单独指定文件")
            filename = _text(filename, "素材文件", 120)
            def change(cfg):
                return {**cfg, "asset_files": [f for f in cfg.get("asset_files", []) if f != filename]}
            with engine.shot_run(rid, write=True) as record:
                if not engine.asset_path(rid, filename):
                    raise HarnessError("not_found")
                assets = engine.delete_asset(rid, filename)
                self._asset_snapshot(record, engine.get_run(rid), change)
            return {"assets": assets[:32]}
        if not isinstance(ids, list) or not 1 <= len(ids) <= 32 or not all(Store.valid_id(value) for value in ids):
            raise ValueError("需要有效的作品编号")
        sid = self._target_step(args, required=True)
        if op == "bind_rounds":
            for identifier in ids:
                media = self.runtime.store.media_path(identifier)
                if not media or media[0] != "image":
                    raise HarnessError("media_invalid")
        def change(cfg):
            prior = cfg.get("round_ids", [])
            values = list(dict.fromkeys([*prior, *ids])) if op == "bind_rounds" else [value for value in prior if value not in ids]
            if len(values) > 32:
                raise ValueError("绑定作品数量超出上限")
            return {**cfg, "round_ids": values}
        if rid == self.run_id:
            staged = next((item for item in self.editor["workflow"]["steps"] if item["id"] == sid and item["type"] == "asset_input"), None)
            if not staged:
                raise HarnessError("not_found")
            change(staged["config"])
        with engine.shot_run(rid, write=True) as record:
            definition = copy.deepcopy(record["workflow"])
            step = next((item for item in definition["steps"] if item["id"] == sid and item["type"] == "asset_input"), None)
            if not step:
                raise HarnessError("not_found")
            step["config"] = change(step["config"])
            saved = engine.update_run_config(rid, {"workflow": definition})
            self._asset_snapshot(record, saved, change, sid)
        return {"step_id": sid, "round_ids": step["config"]["round_ids"]}

    def _asset_snapshot(self, before, saved, change, step_id=None):
        if before["id"] != self.run_id:
            return
        # Only rebase a staged graph over the asset edit made by this turn.
        if self.revision is None or editor_revision(before) == self.revision:
            self.revision = editor_revision(saved)
        for snapshot in (self.original, self.editor):
            for step in snapshot["workflow"]["steps"]:
                if step["type"] == "asset_input" and (not step_id or step_id == step["id"]):
                    step["config"] = change(step["config"])
        self.refresh_run = True

    def _rewrite(self, args):
        target = args.get("target", "shots" if self.workspace == "workflow" else "composer")
        data = {key: value for key, value in args.items() if key not in ("target", "run_id", "step_id")}
        if target == "composer":
            if self.workspace not in ("image", "video") or self.composer is None or {"run_id", "step_id"} & args.keys():
                raise HarnessError("invalid_argument")
            kwargs = {"composer": {**self.composer, "mode": self.workspace}}
        elif target == "shots":
            kwargs = {"run_id": self._target_run(args), "step_id": self._target_step(args, required=True)}
            if self.selected_shot and "shot_ids" not in data and kwargs["step_id"] == self.selected and kwargs["run_id"] == self.run_id:
                data["shot_ids"] = [self.selected_shot]
        else:
            raise HarnessError("invalid_argument")
        result = rewrite_prompt(self.runtime, RewriteInput.model_validate(data), scope=self.scope, cancel=self.cancel, **kwargs)
        self.proposal_ids.append(result["proposal_id"])
        return result

    def _apply_shots(self, args):
        atomicity = args.get("atomicity", "all")
        if "proposal_id" in args:
            proposal_id = args["proposal_id"]
            if (not isinstance(proposal_id, str) or not re.fullmatch(r"pr_[a-f0-9]{24}", proposal_id)
                    or {"edits", "run_id", "step_id"} & args.keys()):
                raise HarnessError("invalid_argument")
            kwargs = {"proposal_id": proposal_id}
        else:
            values = args.get("edits")
            if not isinstance(values, list) or not 1 <= len(values) <= 32:
                raise HarnessError("invalid_argument")
            kwargs = {"run_id": self._target_run(args), "step_id": self._target_step(args, required=True),
                      "patches": [ShotEdit.model_validate(value).model_dump() for value in values]}
        return self._track_write(apply_shot_edits(self.runtime, scope=self.scope, atomicity=atomicity, **kwargs))

    def _track_write(self, result):
        if result["run_updated"]["changes"]:
            self.run_updates.append(result["run_updated"])
            self.refresh_run |= result["run_updated"]["run_id"] == self.run_id
        if result["proposal"]:
            self.proposal_ids.append(result["proposal"]["proposal_id"])
        return {key: result[key] for key in ("applied", "conflicts", "undo_id")}
