"""Built-in workflows, editable step definitions and template substitution."""
from __future__ import annotations

import copy
import json
import random
import re
import time
from typing import Any

from ..generation.parameters import as_bool, boolean_input
from ..generation.video_reference import VIDEO_TASKS
from .video import TRANSITIONS, normalize_transition

STEPS_MAX = 16


STEP_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,48}")
VAR_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")

VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,47}")


def workflow_variables(raw):
    import math
    if not isinstance(raw, dict) or len(raw) > 32:
        raise ValueError("一个工作流最多定义 32 个变量")
    for key, value in raw.items():
        if not isinstance(key, str) or not VARIABLE_NAME.fullmatch(key):
            raise ValueError("变量名须以英文字母或下划线开头，最多 48 个字符")
        if (type(value) not in (str, bool, int, float) or isinstance(value, str) and len(value) > 2000
                or isinstance(value, float) and not math.isfinite(value)):
            raise ValueError(f"变量 {key} 需要文本（最多 2000 字）、数字或布尔值")
    return dict(raw)


def step_position(raw):
    if not isinstance(raw, dict) or any(type(raw.get(k)) not in (int, float) or not 0 <= raw[k] <= 8000
                                       for k in ("x", "y")):
        raise ValueError("画布坐标必须在 0–8000 之间")
    return {k: round(raw[k]) for k in ("x", "y")}

STEP_CATALOG: list[dict[str, Any]] = [
    {
        "type": "asset_input",
        "label": "视觉资产输入",
        "icon": "🎭",
        "category": "输入",
        "hint": "绑定人设图、风格参考图或画廊历史作品，供后续步骤按需引用",
        "default_config": {
            "role": "character",
            "asset_files": [],
            "round_ids": [],
            "note": "上传角色人设图或从画廊挑选参考图",
        },
    },
    {
        "type": "llm_script",
        "label": "AI 脚本与分镜",
        "icon": "📝",
        "category": "规划",
        "hint": "使用当前选择的模型撰写分镜脚本（每镜含检索词、关键帧描述、视频动作与声音）",
        "default_config": {
            "scene_count": 3,
            "output_format": "storyboard",
            "instruction": (
                "请根据主题「{{topic}}」拆解为 {{scene_count}} 个连贯镜头，适合长视频制作。"
                "为每个镜头规划清晰的景别构图、适合找参考白模的英文/中文检索词、关键帧融合生图描述、"
                "视频动态镜头动作以及声音/环境音设计。"
            ),
        },
    },
    {
        "type": "web_asset_fetch",
        "label": "网页 Agent 找图",
        "icon": "🌐",
        "category": "检索",
        "hint": "轻量 Agent 访问目标网页或公开图库检索，AI 筛选最契合的白模/参考图并下载到本地",
        "default_config": {
            "url": "",
            "search_query": "{{topic}} 3d white clay model reference",
            "scenes_from": "",
            "instruction": "优先选择轮廓清晰、构图干净、无大水印的白模/造型/场景参考图",
            "max_images": 2,
        },
    },
    {
        "type": "image_gen",
        "label": "关键帧融合生图",
        "icon": "🎨",
        "category": "生图",
        "hint": "将白模参考图 + 角色人设图一起送入生图模型，按分镜批量生成高一致性关键帧",
        "default_config": {
            "scenes_from": "script",
            "ref_sources": ["web_refs", "character_assets"],
            "prompt_template": "{{scene.keyframe_prompt}}",
            "prompt_prefix": "",
            "engine": "diffusers",
            "model": "qwen-2.1-bf16",
            "gpu": "A100",
            "gpu_pool": ["A100", "H100"],
            "poll_rounds": 2,
            "poll_all_proxies": False,
            "width": 1280,
            "height": 768,
            "steps": 35,
            "cfg": 5.0,
            "max_scenes": 6,
            "loras": [],
        },
    },
    {
        "type": "h3_prompt",
        "label": "H3 多模态写视频词",
        "icon": "✨",
        "category": "提示词",
        "hint": "看图 + 官方 MiniMax-H3 Skill 自动把每个关键帧改写为三段式/六段式音画同步视频提示词",
        "default_config": {
            "scenes_from": "script",
            "keyframe_from": "keyframes",
            "extra_ref_sources": [],
            "workflow": "fl2va",
            "video_from": "",
            "video_round_id": "",
            "video_task": "edit",
            "last_frame_round_id": "",
            "num_frames": 124,
            "instruction": "保持画面风格与角色外观严格一致，加入自然镜头运动与真实环境音效。",
        },
    },
    {
        "type": "video_gen",
        "label": "逐镜生成视频+音频",
        "icon": "🎬",
        "category": "视频",
        "hint": "将每镜关键帧（及可选参考图）+ H3 提示词送入 MiniMax-H3 队列逐段生成音画视频",
        "default_config": {
            "scenes_from": "script",
            "keyframe_from": "keyframes",
            "prompts_from": "h3_prompts",
            "extra_ref_sources": [],
            "workflow": "fl2va",
            "video_from": "",
            "video_round_id": "",
            "video_task": "edit",
            "last_frame_round_id": "",
            "gpu": "H100",
            "gpu_pool": ["H100", "G4", "A100"],
            "poll_rounds": 2,
            "poll_all_proxies": False,
            "width": 1280,
            "height": 768,
            "num_frames": 124,
            "steps": 30,
            "cfg": 5.0,
            "auto_offload": True,
            "loras": [],
        },
    },
    {
        "type": "video_stitch",
        "label": "FFmpeg 剪辑合成",
        "icon": "🎞️",
        "category": "成片",
        "hint": "统一分辨率、帧率与立体声音轨，用硬切或交叉淡入淡出把全部视频片段合成为长视频并存入画廊",
        "default_config": {
            "clips_from": "clips",
            "clip_round_ids": [],
            "transition": "fade",
            "fade_s": 0.35,
            "target_width": 1280,
            "target_height": 768,
            "fps": 24,
        },
    },
]
_STEP_BY_TYPE = {s["type"]: s for s in STEP_CATALOG}


BUILTIN_WORKFLOWS: list[dict[str, Any]] = [
    {
        "id": "builtin:agent-long-video",
        "builtin": True,
        "name": "长视频 Agent 流水线",
        "description": "人设资产 → AI 分镜 → 网页找白模 → 融合生关键帧 → H3 提示词 → 逐镜生视频 → FFmpeg 剪辑。",
        "default_topic": "赛博雨夜街头，主角手持机械伞走过霓虹巷口并回头凝望远处飞船升空，3 镜头短片",
        "steps": [
            {
                "id": "character_assets",
                "type": "asset_input",
                "name": "1. 角色人设图资产",
                "enabled": True,
                "pause_after": False,
                "config": {
                    "role": "character",
                    "asset_files": [],
                    "round_ids": [],
                    "note": "上传主角人设图",
                },
            },
            {
                "id": "script",
                "type": "llm_script",
                "name": "2. AI 导演分镜脚本",
                "enabled": True,
                "pause_after": True,
                "config": {
                    "scene_count": 3,
                    "output_format": "storyboard",
                    "instruction": (
                        "请将主题「{{topic}}」拆解为 {{scene_count}} 个连贯电影镜头。"
                        "每个镜头给出：title、duration_s、适合检索参考构图/白模的英文 search_query、"
                        "结合白模构图与人设外观的中文 keyframe_prompt（清晰注明 图1 参考构图/白模、图2 保持角色人设）、"
                        "video_prompt（镜头运动与表演）以及 audio_notes（环境音/对白/配乐）。"
                    ),
                },
            },
            {
                "id": "web_refs",
                "type": "web_asset_fetch",
                "name": "3. 轻量网页 Agent 抓白模/参考图",
                "enabled": True,
                "pause_after": True,
                "config": {
                    "url": "",
                    "search_query": "{{topic}}",
                    "scenes_from": "script",
                    "instruction": "优先挑选构图清晰、主体明确、适合作为白模姿态或场景布局参考的高清图片",
                    "max_images": 2,
                },
            },
            {
                "id": "keyframes",
                "type": "image_gen",
                "name": "4. 白模 + 人设融合生关键帧",
                "enabled": True,
                "pause_after": True,
                "config": {
                    "scenes_from": "script",
                    "ref_sources": ["web_refs", "character_assets"],
                    "prompt_template": "{{scene.keyframe_prompt}}",
                    "prompt_prefix": "",
                    "engine": "diffusers",
                    "model": "qwen-2.1-bf16",
                    "gpu": "A100",
                    "gpu_pool": ["A100", "H100"],
                    "poll_rounds": 2,
                    "poll_all_proxies": False,
                    "width": 1280,
                    "height": 768,
                    "steps": 35,
                    "cfg": 5.0,
                    "max_scenes": 6,
                    "loras": [],
                },
            },
            {
                "id": "h3_prompts",
                "type": "h3_prompt",
                "name": "5. 多模态写 MiniMax-H3 视频提示词",
                "enabled": True,
                "pause_after": True,
                "config": {
                    "scenes_from": "script",
                    "keyframe_from": "keyframes",
                    "extra_ref_sources": [],
                    "workflow": "fl2va",
                    "num_frames": 124,
                    "instruction": "结合关键帧构图与分镜动作，生成专业电影运镜与沉浸式环境音效。",
                },
            },
            {
                "id": "clips",
                "type": "video_gen",
                "name": "6. 逐镜生成音画视频片段",
                "enabled": True,
                "pause_after": False,
                "config": {
                    "scenes_from": "script",
                    "keyframe_from": "keyframes",
                    "prompts_from": "h3_prompts",
                    "extra_ref_sources": [],
                    "workflow": "fl2va",
                    "gpu": "H100",
                    "gpu_pool": ["H100", "G4", "A100"],
                    "poll_rounds": 2,
                    "poll_all_proxies": False,
                    "width": 1280,
                    "height": 768,
                    "num_frames": 124,
                    "steps": 30,
                    "cfg": 5.0,
                    "auto_offload": True,
                    "loras": [],
                },
            },
            {
                "id": "final_cut",
                "type": "video_stitch",
                "name": "7. FFmpeg 剪辑合成长视频",
                "enabled": True,
                "pause_after": False,
                "config": {
                    "clips_from": "clips",
                    "clip_round_ids": [],
                    "transition": "fade",
                    "fade_s": 0.35,
                    "target_width": 1280,
                    "target_height": 768,
                    "fps": 24,
                },
            },
        ],
    },
    {
        "id": "builtin:storyboard-short",
        "builtin": True,
        "name": "多镜故事短片",
        "description": "人设图 → AI 分镜 → 批量关键帧 → H3 提示词 → 逐镜生视频 → FFmpeg 拼片。",
        "default_topic": "清晨海边灯塔，少女推开木窗看到海鸥掠过金色海面，然后沿着礁石阶梯奔向沙滩",
        "steps": [
            {
                "id": "character_assets",
                "type": "asset_input",
                "name": "1. 人设 / 风格参考图",
                "enabled": True,
                "pause_after": False,
                "config": {"role": "character", "asset_files": [], "round_ids": [], "note": "可选上传 1-3 张人设图"},
            },
            {
                "id": "script",
                "type": "llm_script",
                "name": "2. AI 拆解 3 镜分镜",
                "enabled": True,
                "pause_after": True,
                "config": {
                    "scene_count": 3,
                    "output_format": "storyboard",
                    "instruction": "将「{{topic}}」拆成 {{scene_count}} 个情绪递进的镜头，保证服饰、光线与色调前后统一。",
                },
            },
            {
                "id": "keyframes",
                "type": "image_gen",
                "name": "3. 批量生成镜头关键帧",
                "enabled": True,
                "pause_after": True,
                "config": {
                    "scenes_from": "script",
                    "ref_sources": ["character_assets"],
                    "prompt_template": "{{scene.keyframe_prompt}}",
                    "prompt_prefix": "",
                    "engine": "diffusers",
                    "model": "qwen-2.1-bf16",
                    "gpu": "A100",
                    "gpu_pool": ["A100", "H100"],
                    "poll_rounds": 2,
                    "poll_all_proxies": False,
                    "width": 1280,
                    "height": 768,
                    "steps": 35,
                    "cfg": 5.0,
                    "max_scenes": 6,
                    "loras": [],
                },
            },
            {
                "id": "h3_prompts",
                "type": "h3_prompt",
                "name": "4. 生成 H3 视频提示词",
                "enabled": True,
                "pause_after": False,
                "config": {
                    "scenes_from": "script",
                    "keyframe_from": "keyframes",
                    "extra_ref_sources": [],
                    "workflow": "fl2va",
                    "num_frames": 124,
                    "instruction": "突出电影感镜头推进与细腻的环境声景。",
                },
            },
            {
                "id": "clips",
                "type": "video_gen",
                "name": "5. 逐镜生视频",
                "enabled": True,
                "pause_after": False,
                "config": {
                    "scenes_from": "script",
                    "keyframe_from": "keyframes",
                    "prompts_from": "h3_prompts",
                    "extra_ref_sources": [],
                    "workflow": "fl2va",
                    "gpu": "H100",
                    "gpu_pool": ["H100", "G4", "A100"],
                    "poll_rounds": 2,
                    "poll_all_proxies": False,
                    "width": 1280,
                    "height": 768,
                    "num_frames": 124,
                    "steps": 30,
                    "cfg": 5.0,
                    "auto_offload": True,
                    "loras": [],
                },
            },
            {
                "id": "final_cut",
                "type": "video_stitch",
                "name": "6. FFmpeg 拼接成片",
                "enabled": True,
                "pause_after": False,
                "config": {
                    "clips_from": "clips",
                    "clip_round_ids": [],
                    "transition": "fade",
                    "fade_s": 0.35,
                    "target_width": 1280,
                    "target_height": 768,
                    "fps": 24,
                },
            },
        ],
    },
    {
        "id": "builtin:multi-shot-concept",
        "builtin": True,
        "name": "角色多景别设定集",
        "description": "人设图 + 网页参考 → AI 扩展 4 组景别 → 批量生图。",
        "default_topic": "未来机能风女骑士，四套不同光影与机位的人物定妆照",
        "steps": [
            {
                "id": "character_assets",
                "type": "asset_input",
                "name": "1. 基础人设图",
                "enabled": True,
                "pause_after": False,
                "config": {"role": "character", "asset_files": [], "round_ids": [], "note": "上传角色人设原图"},
            },
            {
                "id": "web_refs",
                "type": "web_asset_fetch",
                "name": "2. 网页找姿态/白模参考",
                "enabled": True,
                "pause_after": True,
                "config": {
                    "url": "",
                    "search_query": "{{topic}}",
                    "scenes_from": "",
                    "instruction": "寻找干净的服装材质或姿态参考图",
                    "max_images": 2,
                },
            },
            {
                "id": "script",
                "type": "llm_script",
                "name": "3. AI 规划 4 组景别变体",
                "enabled": True,
                "pause_after": True,
                "config": {
                    "scene_count": 4,
                    "output_format": "storyboard",
                    "instruction": "围绕「{{topic}}」设计 {{scene_count}} 个不同景别（全身、半身、特写、背影回眸）的出图方案。",
                },
            },
            {
                "id": "keyframes",
                "type": "image_gen",
                "name": "4. 批量生成定妆照",
                "enabled": True,
                "pause_after": False,
                "config": {
                    "scenes_from": "script",
                    "ref_sources": ["character_assets", "web_refs"],
                    "prompt_template": "{{scene.keyframe_prompt}}",
                    "prompt_prefix": "",
                    "engine": "diffusers",
                    "model": "qwen-2.1-bf16",
                    "gpu": "A100",
                    "gpu_pool": ["A100", "H100"],
                    "poll_rounds": 2,
                    "poll_all_proxies": False,
                    "width": 768,
                    "height": 1152,
                    "steps": 35,
                    "cfg": 5.0,
                    "max_scenes": 6,
                    "loras": [],
                },
            },
        ],
    },
]


def render_template(template: str, ctx: dict[str, Any]) -> str:
    def _lookup(match: re.Match[str]) -> str:
        key = match.group(1)
        cur: Any = ctx
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return match.group(0)
        if cur is None:
            return ""
        if isinstance(cur, (dict, list)):
            return json.dumps(cur, ensure_ascii=False)
        return str(cur)

    return VAR_RE.sub(_lookup, str(template or ""))


def _align_options(stype: str, cfg: dict, defaults: dict) -> None:
    for key, default in defaults.items():
        if isinstance(default, bool) and key in cfg:
            cfg[key] = boolean_input(cfg[key])
    if stype == "video_stitch" and isinstance(cfg.get("transition"), str):
        value = cfg["transition"]
        cfg["transition"] = TRANSITIONS.get(value, value)
    if stype in {"image_gen", "video_gen"}:
        gpu = str(cfg.get("gpu") or "").strip().upper()
        pool = cfg.get("gpu_pool")
        if isinstance(pool, list) and pool and all(isinstance(item, str) for item in pool):
            pool = list(dict.fromkeys(item.strip().upper() for item in pool))
            # Old forms changed the dropdown but left the catalog's default pool in place.
            if gpu and gpu != pool[0] and pool == defaults["gpu_pool"]:
                pool = [gpu]
            cfg["gpu"], cfg["gpu_pool"] = pool[0], pool
        elif not pool and (gpu or "gpu_pool" in cfg):
            primary = gpu or defaults["gpu"]
            cfg["gpu"], cfg["gpu_pool"] = primary, [primary]
        if stype == "video_gen" and cfg.get("offload_mode") in ("auto", "component", "group", "none"):
            cfg["auto_offload"] = cfg["offload_mode"] != "none"


def upgrade_stored_workflow(workflow: dict) -> dict:
    """Repair old form values in memory, preserving run IDs, outputs and timestamps."""
    steps = workflow.get("steps")
    if not isinstance(steps, list):
        return workflow
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("type"), str):
            continue
        cat = _STEP_BY_TYPE.get(step["type"])
        if cat and isinstance(step.get("config"), dict):
            _align_options(step["type"], step["config"], cat["default_config"])
        for key in ("enabled", "pause_after"):
            if key in step:
                step[key] = boolean_input(step[key])
    return workflow


def _normalize_step(raw: Any, idx: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"第 {idx + 1} 个步骤格式无效")
    stype = str(raw.get("type") or "").strip()
    cat = _STEP_BY_TYPE.get(stype)
    if cat is None:
        raise ValueError(f"不支持的步骤类型：{stype}")
    sid = str(raw.get("id") or f"step_{idx + 1}").strip()
    if not STEP_ID_RE.fullmatch(sid):
        sid = f"step_{idx + 1}"
    name = str(raw.get("name") or cat["label"]).strip()[:80] or cat["label"]
    cfg = copy.deepcopy(cat["default_config"])
    if isinstance(raw.get("config"), dict):
        supplied = dict(raw["config"])
        _align_options(stype, supplied, cat["default_config"])
        cfg.update(supplied)
    for key, default in cat["default_config"].items():
        if isinstance(default, bool):
            cfg[key] = as_bool(cfg[key], key)
    if stype == "video_stitch":
        cfg["transition"] = normalize_transition(cfg["transition"])
    if stype in ("video_gen", "h3_prompt") and (cfg.get("video_round_id") or cfg.get("video_from")):
        source, rid = cfg.get("video_from"), cfg.get("video_round_id")
        if source and (not isinstance(source, str) or not STEP_ID_RE.fullmatch(source) or rid):
            raise ValueError("参考视频请选择一个上游视频步骤，或一件作品库视频")
        if rid and (not isinstance(rid, str) or not re.fullmatch(r"\d{3,7}", rid)):
            raise ValueError("参考视频需要一个作品库视频编号")
        if not isinstance(cfg.get("video_task"), str) or cfg["video_task"] not in VIDEO_TASKS:
            raise ValueError("参考视频用途无效")
    return {
        "id": sid,
        "type": stype,
        "name": name,
        "enabled": as_bool(raw.get("enabled", True), "enabled"),
        "pause_after": as_bool(raw.get("pause_after", False), "pause_after"),
        "config": cfg,
        **({"position": step_position(raw["position"])} if "position" in raw else {}),
    }


def normalize_workflow_def(body: dict[str, Any]) -> dict[str, Any]:
    name = str(body.get("name") or "").strip()
    if not name or len(name) > 80:
        raise ValueError("工作流名称不能为空且不超过 80 字")
    raw_steps = body.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("工作流至少需要 1 个步骤")
    if len(raw_steps) > STEPS_MAX:
        raise ValueError(f"工作流最多包含 {STEPS_MAX} 个步骤")
    steps: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for idx, rs in enumerate(raw_steps):
        st = _normalize_step(rs, idx)
        base_id = st["id"]
        n = 2
        while st["id"] in used_ids:
            st["id"] = f"{base_id}_{n}"
            n += 1
        cfg = st["config"]
        if st["type"] in ("h3_prompt", "video_gen") and cfg["workflow"] == "ref2va" and (source := cfg["video_from"]):
            if not any(s["id"] == source and s["type"] in ("video_gen", "video_stitch") for s in steps):
                raise ValueError(f"「{st['name']}」引用的上游视频步骤 {source} 不存在、类型不符或位于本步骤之后")
        used_ids.add(st["id"])
        steps.append(st)
    req_id = str(body.get("id") or "").strip()
    if req_id.startswith("builtin:"):
        req_id = ""
    if req_id and not re.fullmatch(r"wf_[A-Za-z0-9_-]{4,48}", req_id):
        raise ValueError("无效的工作流 ID")
    now = int(time.time())
    wf_id = req_id or f"wf_{now % 1000000:06d}_{random.randint(1000, 9999)}"
    variables = workflow_variables(body.get("variables", {}))
    if variables and "vars" in used_ids:
        raise ValueError("使用工作流变量时，步骤 ID 不能为 vars")
    return {
        "id": wf_id,
        "builtin": False,
        "name": name,
        "description": str(body.get("description") or "").strip()[:400],
        "default_topic": str(body.get("default_topic") or "").strip()[:600],
        "steps": steps,
        **({"variables": variables} if variables else {}),
        "updated_at": now,
    }
