"""Normalize generation requests, model links and preset values before enqueueing."""
from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from .catalog import (
    COMFY_CLIP_TYPES, COMFY_SAMPLERS, COMFY_SCHEDULERS, COMFY_TEMPLATES,
    DEFAULTS, GPUS, IMAGE_MODELS, LIMITS, VIDEO_WORKFLOWS,
)


REPO_RE = re.compile(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")
ALLOWED_MODEL_EXTS = frozenset({".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin"})
_WILDCARD_RE = re.compile(r"(?<!\\)\{([^{}]+)\}")


def expand_prompt_wildcards(prompt: str, seed: int) -> str:
    """Expand SwarmUI-style `{option A|option B|option C}` wildcards deterministically per seed.

    Single-option braces without `|` (such as JSON fragments) are left untouched.
    Escaped `\\{` / `\\}` are unescaped to literal braces.
    """
    text = str(prompt or "")
    if "{" not in text or "|" not in text:
        return text.replace(r"\{", "{").replace(r"\}", "}")
    rng = random.Random(int(seed) & 0x7FFFFFFF)

    def _pick(match: re.Match[str]) -> str:
        inner = match.group(1)
        if "|" not in inner:
            return match.group(0)
        choices = [part.strip() for part in inner.split("|")]
        non_empty = [c for c in choices if c]
        if len(choices) < 2 or not non_empty:
            return match.group(0)
        return rng.choice(choices)

    expanded = _WILDCARD_RE.sub(_pick, text)
    return expanded.replace(r"\{", "{").replace(r"\}", "}")


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def snap_size(v: int) -> int:
    step = LIMITS["size_step"]
    v = int(round(v / step) * step)
    return int(clamp(v, LIMITS["size_min"], LIMITS["size_max"]))


def as_int(v: Any, default: int) -> int:
    if v in (None, ""):
        return default
    if isinstance(v, bool):
        raise ValueError("参数格式不对")
    return int(v)


def as_float(v: Any, default: float) -> float:
    if v in (None, ""):
        return default
    if isinstance(v, bool):
        raise ValueError("参数格式不对")
    return float(v)


def _detect_weight_format(path_text: str) -> str:
    low = path_text.lower()
    for tag, label in (
        ("nvfp4", "NVFP4"),
        ("fp8", "FP8"),
        ("int8", "INT8"),
        ("nf4", "NF4"),
        ("bf16", "BF16"),
        ("fp16", "FP16"),
        ("fp32", "FP32"),
        ("q8_0", "Q8_0"),
        ("q6_k", "Q6_K"),
        ("q5_k_m", "Q5_K_M"),
        ("q4_k_m", "Q4_K_M"),
        ("q4_0", "Q4_0"),
    ):
        if tag in low:
            return label
    if low.endswith(".gguf"):
        return "GGUF"
    if low.endswith(".safetensors"):
        return "SAFETENSORS"
    return "WEIGHT"


def _validate_rel_filename(filename: str, label: str) -> tuple[str, str]:
    clean = unquote(filename).strip().lstrip("/")
    if not clean or len(clean) > 360:
        raise ValueError(f"{label}缺少具体文件路径")
    parts = [p for p in clean.split("/") if p]
    if any(p in {".", ".."} for p in parts) or "\\" in clean:
        raise ValueError(f"{label}路径非法：{clean}")
    clean = "/".join(parts)
    ext = Path(clean).suffix.lower()
    if ext not in ALLOWED_MODEL_EXTS:
        raise ValueError(
            f"{label}需指向具体的模型权重文件（如 .safetensors / .gguf），当前：{parts[-1]}"
        )
    return clean, ext


def parse_model_link(raw: Any, label: str = "模型链接") -> dict[str, Any]:
    """Parse a Hugging Face file URL, shorthand `owner/repo :: path/file`, or direct HTTPS URL."""
    if isinstance(raw, dict):
        if raw.get("repo_id") and raw.get("filename"):
            repo = str(raw["repo_id"]).strip().strip("/")
            if not REPO_RE.fullmatch(repo):
                raise ValueError(f"{label}仓库格式无效：{repo}")
            rev = str(raw.get("revision") or "main").strip() or "main"
            if not re.fullmatch(r"[A-Za-z0-9._/-]{1,80}", rev) or ".." in rev:
                raise ValueError(f"{label}分支名无效：{rev}")
            fn, ext = _validate_rel_filename(str(raw["filename"]), label)
            base = fn.rsplit("/", 1)[-1]
            url = f"https://huggingface.co/{repo}/resolve/{rev}/{fn}"
            return {
                "raw": str(raw.get("raw") or url),
                "source": "hf",
                "repo_id": repo,
                "filename": fn,
                "revision": rev,
                "url": url,
                "basename": base,
                "ext": ext,
                "format": _detect_weight_format(fn),
            }
        raw = raw.get("url") or raw.get("raw") or ""

    text = str(raw or "").strip()
    if not text:
        raise ValueError(f"请填写{label}")
    if len(text) > 500:
        raise ValueError(f"{label}过长（最多 500 字符）")

    # 1. HTTP(S) URL
    if text.startswith(("http://", "https://")):
        u = urlsplit(text)
        if u.scheme not in {"http", "https"} or not u.netloc:
            raise ValueError(f"{label} URL 格式无效")
        host = u.hostname.lower() if u.hostname else ""
        path_parts = [unquote(p) for p in u.path.split("/") if p]
        if host in {"huggingface.co", "www.huggingface.co", "hf-mirror.com", "hf.co"}:
            # Formats:
            # /owner/repo/(blob|resolve|raw)/rev/path/to/file.safetensors
            # /models/owner/repo/... (rare)
            if len(path_parts) >= 5 and path_parts[2] in {"blob", "resolve", "raw"}:
                repo = f"{path_parts[0]}/{path_parts[1]}"
                rev = path_parts[3]
                rel = "/".join(path_parts[4:])
                if not REPO_RE.fullmatch(repo):
                    raise ValueError(f"{label} Hugging Face 仓库格式无效：{repo}")
                fn, ext = _validate_rel_filename(rel, label)
                base = fn.rsplit("/", 1)[-1]
                return {
                    "raw": text,
                    "source": "hf",
                    "repo_id": repo,
                    "filename": fn,
                    "revision": rev,
                    "url": f"https://huggingface.co/{repo}/resolve/{rev}/{fn}",
                    "basename": base,
                    "ext": ext,
                    "format": _detect_weight_format(fn),
                }
            raise ValueError(
                f"{label}请粘贴到具体文件页的 Hugging Face 链接（包含 /blob/main/... 或 /resolve/main/...）"
            )
        # Direct HTTPS file link
        if not path_parts:
            raise ValueError(f"{label} URL 缺少文件名")
        fn, ext = _validate_rel_filename(path_parts[-1], label)
        return {
            "raw": text,
            "source": "url",
            "repo_id": "",
            "filename": fn,
            "revision": "",
            "url": text,
            "basename": fn,
            "ext": ext,
            "format": _detect_weight_format(u.path),
        }

    # 2. Shorthand: `owner/repo :: path/file.safetensors` or `owner/repo:path/file.safetensors`
    if "::" in text:
        repo_part, file_part = text.split("::", 1)
        repo = repo_part.strip().strip("/")
        if not REPO_RE.fullmatch(repo):
            raise ValueError(f"{label}仓库格式无效：{repo}")
        fn, ext = _validate_rel_filename(file_part, label)
        base = fn.rsplit("/", 1)[-1]
        return {
            "raw": text,
            "source": "hf",
            "repo_id": repo,
            "filename": fn,
            "revision": "main",
            "url": f"https://huggingface.co/{repo}/resolve/main/{fn}",
            "basename": base,
            "ext": ext,
            "format": _detect_weight_format(fn),
        }
    if ":" in text and not text.startswith("/"):
        repo_part, file_part = text.split(":", 1)
        repo = repo_part.strip().strip("/")
        if REPO_RE.fullmatch(repo):
            fn, ext = _validate_rel_filename(file_part, label)
            base = fn.rsplit("/", 1)[-1]
            return {
                "raw": text,
                "source": "hf",
                "repo_id": repo,
                "filename": fn,
                "revision": "main",
                "url": f"https://huggingface.co/{repo}/resolve/main/{fn}",
                "basename": base,
                "ext": ext,
                "format": _detect_weight_format(fn),
            }

    # 3. Path shorthand: `owner/repo/path/to/file.safetensors`
    segs = [p for p in text.strip("/").split("/") if p]
    if len(segs) >= 3:
        repo = f"{segs[0]}/{segs[1]}"
        if REPO_RE.fullmatch(repo):
            fn, ext = _validate_rel_filename("/".join(segs[2:]), label)
            base = fn.rsplit("/", 1)[-1]
            return {
                "raw": text,
                "source": "hf",
                "repo_id": repo,
                "filename": fn,
                "revision": "main",
                "url": f"https://huggingface.co/{repo}/resolve/main/{fn}",
                "basename": base,
                "ext": ext,
                "format": _detect_weight_format(fn),
            }

    raise ValueError(
        f"{label}格式无法识别，请粘贴 Hugging Face 文件链接或填写 owner/repo :: 路径/文件名"
    )


def normalize_loras(raw_list: Any) -> list[dict]:
    loras = []
    for item in (raw_list or [])[: LIMITS["loras_max"]]:
        if isinstance(item, str) and item.strip():
            spec = parse_model_link(item, "LoRA 链接")
            if spec["source"] != "hf":
                raise ValueError("LoRA 链接目前仅支持 Hugging Face 仓库文件")
            loras.append({"repo_id": spec["repo_id"], "weight_name": spec["filename"], "scale": 1.0})
            continue
        if not isinstance(item, dict):
            continue
        url_val = str(item.get("url") or "").strip()
        repo = str(item.get("repo_id") or "").strip()
        weight = str(item.get("weight_name") or "").strip()
        if url_val or repo.startswith(("http://", "https://")) or "::" in repo:
            spec = parse_model_link(url_val or repo, "LoRA 链接")
            if spec["source"] != "hf":
                raise ValueError("LoRA 链接目前仅支持 Hugging Face 仓库文件")
            repo = spec["repo_id"]
            weight = weight or spec["filename"]
        else:
            repo = repo.strip("/")
            if not repo:
                continue
            if not REPO_RE.fullmatch(repo):
                raise ValueError(f"LoRA 仓库格式无效：{repo}")
        try:
            scale = as_float(item.get("scale"), 1.0)
        except (TypeError, ValueError):
            scale = 1.0
        loras.append({
            "repo_id": repo,
            "weight_name": weight[:300],
            "scale": round(clamp(scale, 0.0, LIMITS["lora_scale_max"]), 3),
        })
    return loras


def comfy_template_by_id(template_id: str) -> dict:
    for t in COMFY_TEMPLATES:
        if t["id"] == template_id:
            return t
    return COMFY_TEMPLATES[0]


def normalize_comfy_config(raw: Any, top: dict | None = None) -> dict[str, Any]:
    """Validate and normalize ComfyUI three-component configuration."""
    top = top or {}
    cfg = raw if isinstance(raw, dict) else {}
    template_id = str(cfg.get("template") or top.get("comfy_template") or "qwen-image-2.1").strip()
    if template_id not in {t["id"] for t in COMFY_TEMPLATES}:
        raise ValueError(f"不支持的 ComfyUI 模板：{template_id}")
    tpl = comfy_template_by_id(template_id)
    tpl_def = tpl["defaults"]

    raw_diff = cfg.get("diffusion") or top.get("diffusion") or ""
    raw_te = cfg.get("text_encoder") or top.get("text_encoder") or tpl_def.get("text_encoder") or ""
    raw_vae = cfg.get("vae") or top.get("vae") or tpl_def.get("vae") or ""

    diffusion = parse_model_link(raw_diff, "扩散模型")
    text_encoder = parse_model_link(raw_te, "文本编码器")
    vae = parse_model_link(raw_vae, "VAE")

    sampler = str(cfg.get("sampler") or top.get("sampler") or tpl_def.get("sampler") or "euler").strip()
    if sampler not in COMFY_SAMPLERS:
        raise ValueError(f"不支持的采样器：{sampler}")
    scheduler = str(cfg.get("scheduler") or top.get("scheduler") or tpl_def.get("scheduler") or "simple").strip()
    if scheduler not in COMFY_SCHEDULERS:
        raise ValueError(f"不支持的调度器：{scheduler}")
    clip_type = str(cfg.get("clip_type") or top.get("clip_type") or tpl["clip_type"]).strip()
    if clip_type not in COMFY_CLIP_TYPES:
        raise ValueError(f"不支持的文本编码器类型：{clip_type}")
    try:
        denoise = round(clamp(as_float(cfg.get("denoise", top.get("denoise")), 1.0), 0.05, 1.0), 3)
    except (TypeError, ValueError) as exc:
        raise ValueError("denoise 参数格式不对") from exc

    return {
        "template": template_id,
        "clip_type": clip_type,
        "diffusion": diffusion,
        "text_encoder": text_encoder,
        "vae": vae,
        "sampler": sampler,
        "scheduler": scheduler,
        "denoise": denoise,
    }


def validate_image_model(raw: Any) -> str:
    """Validate a built-in image model ID or a Hugging Face repo ID (owner/repo)."""
    model = str(raw or "").strip().strip("/")
    if not model:
        return DEFAULTS["image"]["model"]
    if model in {m["id"] for m in IMAGE_MODELS}:
        return model
    if len(model) <= 160 and REPO_RE.fullmatch(model):
        return model
    raise ValueError("生图模型应填写内置名或 Hugging Face 仓库 ID（格式：owner/repo）")


def boolean_input(value: Any) -> Any:
    """Decode known wire values, leaving unrecognised stored values available for editing."""
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
    elif type(value) is int and value in (0, 1):
        return bool(value)
    return value


def as_bool(value: Any, field: str) -> bool:
    result = boolean_input(value)
    if not isinstance(result, bool):
        raise ValueError(f"{field} 必须是布尔值 true 或 false")
    return result


def normalize_video_offload_mode(raw: Any, auto_offload: Any = True) -> str:
    m = str(raw or "").strip().lower()
    if m in {"auto", "component", "group", "none"}:
        return m
    return "auto" if as_bool(auto_offload, "auto_offload") else "none"


def normalize_job(body: dict) -> dict:
    """Validate a /api/generate body. Raises ValueError with a user-facing message."""
    mode = "video" if body.get("mode") == "video" else "image"
    d = DEFAULTS[mode]
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("提示词不能为空")
    if len(prompt) > LIMITS["prompt_max"]:
        raise ValueError(f"提示词超过 {LIMITS['prompt_max']} 字")
    valid_gpus = {g["id"] for g in GPUS}
    raw_pool = body.get("gpu_pool")
    gpu_pool: list[str] = []
    if isinstance(raw_pool, list):
        for item in raw_pool:
            gid = str(item or "").upper().strip()
            if gid not in valid_gpus:
                raise ValueError(f"不支持的 GPU 类型：{gid}")
            if gid not in gpu_pool:
                gpu_pool.append(gid)
    if gpu_pool:
        gpu = gpu_pool[0]
    else:
        gpu = str(body.get("gpu") or DEFAULTS["gpu"]).upper().strip()
        if gpu not in valid_gpus:
            raise ValueError("不支持的 GPU 类型")
        gpu_pool = [gpu]

    try:
        width = snap_size(as_int(body.get("width"), d["width"]) or d["width"])
        height = snap_size(as_int(body.get("height"), d["height"]) or d["height"])
        steps = int(clamp(as_int(body.get("steps"), d["steps"]), LIMITS["steps_min"], LIMITS["steps_max"]))
        cfg = round(clamp(as_float(body.get("cfg"), d["cfg"]), LIMITS["cfg_min"], LIMITS["cfg_max"]), 2)
        seed = as_int(body.get("seed"), -1)
        count = int(clamp(as_int(body.get("count"), 1), 1, LIMITS["count_max"]))
        poll_rounds = int(
            clamp(
                as_int(body.get("poll_rounds"), 1),
                LIMITS["poll_rounds_min"],
                LIMITS["poll_rounds_max"],
            )
        )
        raw_idle = body.get("idle_minutes")
        idle_minutes = normalize_idle_minutes(raw_idle) if raw_idle not in (None, "") else None
    except (TypeError, ValueError) as exc:
        raise ValueError("参数格式不对") from exc

    loras = normalize_loras(body.get("loras"))

    job: dict[str, Any] = {
        "mode": mode,
        "gpu": gpu,
        "gpu_pool": gpu_pool,
        "poll_rounds": poll_rounds,
        "poll_all_proxies": as_bool(body.get("poll_all_proxies", False), "poll_all_proxies"),
        "auto_fallback": as_bool(body.get("auto_fallback", False), "auto_fallback"),
        "prompt": prompt,
        "negative": str(body.get("negative") or "")[: LIMITS["negative_max"]],
        "width": width,
        "height": height,
        "steps": steps,
        "cfg": cfg,
        "seed": seed,
        "count": count,
        "loras": loras,
        "has_image": as_bool(body.get("has_image", False), "has_image"),
        "idea": str(body.get("idea") or "")[:600],
    }
    if idle_minutes is not None:
        job["idle_minutes"] = idle_minutes
    if mode == "video":
        wf = str(body.get("workflow") or "t2va")
        job["workflow"] = wf if wf in {w["id"] for w in VIDEO_WORKFLOWS} else "t2va"
        try:
            frames = as_int(body.get("num_frames"), d["num_frames"])
        except (TypeError, ValueError) as exc:
            raise ValueError("帧数格式不对") from exc
        job["num_frames"] = int(clamp(frames, LIMITS["frames_min"], LIMITS["frames_max"]))
        offload_mode = normalize_video_offload_mode(body.get("offload_mode"), body.get("auto_offload", True))
        job["offload_mode"] = offload_mode
        job["auto_offload"] = offload_mode != "none"
        job["has_last_image"] = as_bool(body.get("has_last_image", False), "has_last_image") and job["workflow"] == "fl2va"
        if job["workflow"] != "t2va":
            job["has_image"] = True
    else:
        raw_engine = str(body.get("engine") or "").strip().lower()
        if not raw_engine and isinstance(body.get("comfy"), dict) and body["comfy"].get("diffusion"):
            raw_engine = "comfyui"
        engine = "comfyui" if raw_engine == "comfyui" else "diffusers"
        job["engine"] = engine
        job["chain"] = as_bool(body.get("chain", False), "chain")
        if job["chain"]:
            job["has_image"] = True
        if engine == "comfyui":
            comfy_cfg = normalize_comfy_config(body.get("comfy"), body)
            job["comfy"] = comfy_cfg
            job["model"] = f"comfyui:{comfy_cfg['template']}/{comfy_cfg['diffusion']['basename']}"
            job["custom_transformer_repo"] = ""
            job["custom_transformer_file"] = ""
        else:
            job["model"] = validate_image_model(body.get("model"))
            job["custom_transformer_repo"] = str(body.get("custom_transformer_repo") or "").strip()[:200]
            job["custom_transformer_file"] = str(body.get("custom_transformer_file") or "").strip()[:200]
    return job


def normalize_idle_minutes(raw: Any) -> int:
    """0 keeps the runtime forever. Any other value clamps to 5–60 minutes."""
    minutes = as_int(raw, DEFAULTS["idle_minutes"])
    if minutes <= 0:
        return 0
    return int(clamp(minutes, LIMITS["idle_minutes_min"], LIMITS["idle_minutes_max"]))


def normalize_grab(body: dict) -> dict:
    """Validate a settings grab-card request."""
    valid_gpus = {g["id"] for g in GPUS}
    raw_pool = body.get("gpu_pool")
    gpu_pool: list[str] = []
    if isinstance(raw_pool, list):
        for item in raw_pool:
            gid = str(item or "").upper().strip()
            if gid not in valid_gpus:
                raise ValueError(f"不支持的 GPU 类型：{gid}")
            if gid not in gpu_pool:
                gpu_pool.append(gid)
    if not gpu_pool:
        gpu = str(body.get("gpu") or "").upper().strip()
        if gpu not in valid_gpus:
            raise ValueError("请先选择要抢的 GPU")
        gpu_pool = [gpu]
    try:
        poll_rounds = int(
            clamp(
                as_int(body.get("poll_rounds"), DEFAULTS["poll_rounds"]),
                LIMITS["poll_rounds_min"],
                LIMITS["poll_rounds_max"],
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("轮询次数格式不对") from exc
    return {
        "gpu_pool": gpu_pool,
        "poll_rounds": poll_rounds,
        "poll_all_proxies": as_bool(body.get("poll_all_proxies", False), "poll_all_proxies"),
    }
