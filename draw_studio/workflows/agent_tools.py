"""The editor actions available to the workflow copilot during one conversation turn."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import threading

from ..gallery import Store
from ..generation.catalog import GPUS, LIMITS, VIDEO_OFFLOAD_MODES, VIDEO_WORKFLOWS
from ..generation.parameters import normalize_loras
from ..generation.video_reference import VIDEO_TASKS
from .definitions import STEP_CATALOG, STEP_ID_RE, STEPS_MAX, normalize_workflow_def, step_position, workflow_variables
from .harness_errors import HarnessError


def obj(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, "required": list(required),
            "additionalProperties": False}


TEXT = {"type": "string"}
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
    "studio_read_workflow": ("读取当前工作流的主题、变量、步骤、选择和运行状态。", obj()),
    "studio_list_nodes": ("列出可编排的节点。指定 step_type 可取得参数和默认值。", obj({"step_type": TEXT})),
    "studio_find_assets": ("在本 Studio 作品库中按关键词和媒体类型查找可引用的作品编号。", obj({
        "query": TEXT, "kind": {"type": "string", "enum": ["image", "video"]}})),
    "studio_edit_workflow": ("编辑当前草稿的主题、名称、变量、步骤和连线。改步骤参数用 update_step 的 step_id 和 config。", obj({
        "operations": {"type": "array", "items": OP_SCHEMA, "minItems": 1, "maxItems": 32}}, ["operations"])),
    "studio_request_run": ("用户要求执行时向编辑器提交运行操作。已有运行可指定 step_id 和 single_step。", obj({
        "step_id": TEXT, "single_step": {"type": "boolean"}})),
}
TOOL_LABELS = dict(zip(TOOLS, ["读取工作流", "查看节点", "查找作品", "修改工作流", "准备运行"], strict=True))
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


class EditorTools:
    def __init__(self, runtime, snapshot: dict, *, selected: str = "", run_id: str | None = None):
        self.runtime = runtime
        self.original = copy.deepcopy(snapshot)
        self.editor = copy.deepcopy(snapshot)
        self.selected = selected
        self.run_id = run_id
        self.run_request = None
        self.calls: list[str] = []
        self.lock = threading.RLock()

    def _run(self):
        run = self.runtime.workflows.get_run(self.run_id) if self.run_id else None
        if self.run_id and not run:
            raise HarnessError("not_found")
        return run

    def context(self):
        with self.lock:
            return self._context(self._run())

    def _context(self, run):
        states = (run or {}).get("step_states", {})
        stages = {key: {"status": state.get("status"), "error": str(state.get("error") or "")[:500]}
                  for key, state in states.items()}
        output = states.get(self.selected, {}).get("output")
        return {**copy.deepcopy(editor_value(self.editor)), "selected_step": self.selected,
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
        except ValueError as exc:
            raise HarnessError("invalid_argument", details={"reason": str(exc)}) from exc

    def _call(self, name: str, args: dict):
        with self.lock:
            if name not in TOOLS:
                raise ValueError("未知工具")
            if len(self.calls) >= 32:
                raise HarnessError("tool_limit_reached")
            self.calls.append(name)
            if not isinstance(args, dict) or args.keys() - TOOLS[name][1]["properties"].keys():
                raise ValueError("工具参数无效")
            run = self._run()
            if name == "studio_read_workflow":
                return self._context(run)
            if name == "studio_list_nodes":
                if "step_type" in args:
                    kind = args["step_type"]
                    if not isinstance(kind, str) or kind not in STEP_TYPES:
                        raise ValueError("节点类型不存在")
                    return STEP_TYPES[kind]
                return [{"type": s["type"], "name": s["label"]} for s in STEP_CATALOG]
            if name == "studio_find_assets":
                k = args.get("kind", "")
                if k not in ("", "image", "video"):
                    raise ValueError("不支持的素材类型")
                query = _text(args.get("query", ""), "检索词", 200, empty=True)
                found = self.runtime.store.list(kind=k, q=query, limit=8)["rounds"]
                return [{"id": a["id"], "kind": a["kind"], "prompt": str(a.get("prompt") or "")[:180]} for a in found]
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
