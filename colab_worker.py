#!/usr/bin/env python3
"""Remote Colab worker executed inside a persistent Jupyter kernel.

Models stay cached in module-level `_CACHE` across consecutive generations on the same
Colab runtime so follow-up edits/renders skip re-downloading and re-loading weights.
Supports:
- Image generation & editing:
  * qwen-2.1-bf16  : Qwen/Qwen-Image-2.1 (full BF16)
  * qwen-2.1-q5    : Qwen/Qwen-Image-2.1 + GGUF Q5_K_M transformer
  * flux2-dev      : black-forest-labs/FLUX.2-dev (32B)
- Video + synchronized audio generation:
  * minimax-h3     : MiniMaxAI/MiniMax-H3 (33B ModularPipeline: t2va / fl2va / ref2va)
- Generic Hugging Face LoRA adapter loading (multi-slot repo_id + weight_name + scale).
"""

from __future__ import annotations

import gc
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ENV_MARKER = Path("/content/.playground_env_v2")
COMFY_DIR = Path("/content/ComfyUI")
COMFY_ENV_MARKER = Path("/content/.comfy_env_v1")
COMFY_CACHE_DIR = Path("/content/comfy_cache")
COMFY_LOG_PATH = Path("/content/comfyui.log")
COMFY_PORT = 8188
COMFY_BASE_URL = f"http://127.0.0.1:{COMFY_PORT}"
MODELS_DIR = Path("/content/models")
LORAS_DIR = Path("/content/loras")

_CACHE: dict[str, Any] = {
    "key": None,
    "pipe": None,
    "manager": None,
    "loras": [],
}
_COMFY_PROC: subprocess.Popen | None = None


def _sh(cmd: list[str]) -> None:
    print("$ " + " ".join(cmd), flush=True)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        text = line.rstrip()
        if text:
            print(text, flush=True)
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"Command failed ({code}): {' '.join(cmd)}")


def ensure_env() -> None:
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    if ENV_MARKER.exists():
        return
    print("正在初始化 Colab Python 依赖（首次约 1–2 分钟）…", flush=True)
    pkgs = [
        "huggingface_hub",
        "hf_xet",
        "accelerate",
        "safetensors",
        "sentencepiece",
        "protobuf",
        "gguf",
        "transformers",
        "peft",
        "imageio[ffmpeg]",
        "av",
        "scipy",
        "soundfile",
    ]
    _sh([sys.executable, "-m", "pip", "install", "-q", "-U", *pkgs])
    _sh(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-q",
            "git+https://github.com/huggingface/diffusers.git",
        ]
    )
    ENV_MARKER.write_text("ok\n", encoding="utf-8")
    print("Colab 依赖准备完成", flush=True)


def _clear_cache() -> None:
    import torch

    if _CACHE["pipe"] is not None:
        print("切换模型/工作流，释放旧显存…", flush=True)
        _CACHE["pipe"] = None
        _CACHE["manager"] = None
        _CACHE["key"] = None
        _CACHE["loras"] = []
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def _normalize_loras(raw_loras: list[dict] | None) -> list[dict]:
    items = []
    for item in raw_loras or []:
        repo = str(item.get("repo_id") or "").strip()
        weight = str(item.get("weight_name") or "").strip()
        if not repo:
            continue
        try:
            scale = float(item.get("scale", 1.0))
        except (TypeError, ValueError):
            scale = 1.0
        scale = max(0.0, min(2.5, scale))
        items.append({"repo_id": repo, "weight_name": weight, "scale": scale})
    return items


def _apply_loras(pipe: Any, loras: list[dict], hf_token: str | None) -> None:
    if loras == _CACHE["loras"]:
        return

    # Always unload previous LoRAs cleanly before applying a new set
    if _CACHE["loras"]:
        print("卸载上一轮 LoRA 权重…", flush=True)
        for target in _lora_targets(pipe):
            if hasattr(target, "unload_lora_weights"):
                try:
                    target.unload_lora_weights()
                except Exception:
                    pass
            elif hasattr(target, "delete_adapters"):
                try:
                    target.delete_adapters()
                except Exception:
                    pass
        _CACHE["loras"] = []

    if not loras:
        return

    from huggingface_hub import hf_hub_download

    LORAS_DIR.mkdir(parents=True, exist_ok=True)
    loaded_names: list[str] = []
    loaded_scales: list[float] = []

    for idx, item in enumerate(loras):
        repo_id = item["repo_id"]
        weight_name = item["weight_name"]
        scale = item["scale"]
        adapter_name = f"lora_{idx}"
        print(
            f"加载 LoRA [{idx + 1}/{len(loras)}]: {repo_id}"
            + (f" :: {weight_name}" if weight_name else "")
            + f" (scale={scale})",
            flush=True,
        )
        local_dir = LORAS_DIR / repo_id.replace("/", "__")
        local_dir.mkdir(parents=True, exist_ok=True)
        local_file: str | None = None
        if weight_name:
            local_file = hf_hub_download(
                repo_id=repo_id,
                filename=weight_name,
                local_dir=str(local_dir),
                token=hf_token or None,
            )

        loaded = False
        last_err: Exception | None = None
        for target in _lora_targets(pipe):
            if hasattr(target, "load_lora_weights"):
                try:
                    kwargs: dict[str, Any] = {"adapter_name": adapter_name}
                    if local_file:
                        p = Path(local_file)
                        target.load_lora_weights(
                            str(p.parent), weight_name=p.name, **kwargs
                        )
                    else:
                        target.load_lora_weights(repo_id, token=hf_token or None, **kwargs)
                    loaded = True
                    break
                except TypeError:
                    # Fallback if adapter_name is not accepted
                    try:
                        if local_file:
                            p = Path(local_file)
                            target.load_lora_weights(str(p.parent), weight_name=p.name)
                        else:
                            target.load_lora_weights(repo_id, token=hf_token or None)
                        loaded = True
                        break
                    except Exception as exc:
                        last_err = exc
                except Exception as exc:
                    last_err = exc
            elif hasattr(target, "load_lora_adapter") and local_file:
                try:
                    p = Path(local_file)
                    target.load_lora_adapter(
                        str(p.parent), weight_name=p.name, adapter_name=adapter_name
                    )
                    loaded = True
                    break
                except Exception as exc:
                    last_err = exc

        if not loaded:
            raise RuntimeError(
                f"LoRA 加载失败（{repo_id} / {weight_name}）：{last_err}. "
                "请确认该权重与当前模型架构及 Diffusers/PEFT 格式兼容。"
            )
        loaded_names.append(adapter_name)
        loaded_scales.append(scale)

    # Set adapter weights if supported
    for target in _lora_targets(pipe):
        if hasattr(target, "set_adapters") and loaded_names:
            try:
                target.set_adapters(loaded_names, adapter_weights=loaded_scales)
                print(
                    "已启用 LoRA adapters: "
                    + ", ".join(f"{n}={s}" for n, s in zip(loaded_names, loaded_scales)),
                    flush=True,
                )
                break
            except Exception as exc:
                print(f"提示：set_adapters 跳过（{exc}），使用默认权重", flush=True)

    _CACHE["loras"] = loras


def _lora_targets(pipe: Any) -> list[Any]:
    targets = [pipe]
    for attr in ("transformer", "transformer_ref", "unet"):
        comp = getattr(pipe, attr, None)
        if comp is not None:
            targets.append(comp)
    components = getattr(pipe, "components", None)
    if isinstance(components, dict):
        for key in ("transformer", "transformer_ref", "unet"):
            comp = components.get(key)
            if comp is not None and comp not in targets:
                targets.append(comp)
    return targets


# ── Image pipelines ───────────────────────────────────────────────────


def _load_image_pipeline(model_key: str, job: dict, hf_token: str | None) -> Any:
    import torch

    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    cache_id = f"image:{model_key}:{job.get('custom_transformer_repo') or ''}:{job.get('custom_transformer_file') or ''}"
    if _CACHE["key"] == cache_id and _CACHE["pipe"] is not None:
        print(f"命中常驻显存模型：{model_key}", flush=True)
        return _CACHE["pipe"]

    _clear_cache()
    t0 = time.time()

    if model_key in {"qwen-2.1-bf16", "Qwen/Qwen-Image-2.1"}:
        from diffusers import QwenImage21Pipeline

        print("加载 Qwen/Qwen-Image-2.1 满血 BF16…", flush=True)
        pipe = QwenImage21Pipeline.from_pretrained(
            "Qwen/Qwen-Image-2.1",
            torch_dtype=torch.bfloat16,
            token=hf_token or None,
        )
        if vram_gb >= 45:
            pipe.to("cuda")
            print(f"显存 {vram_gb:.1f} GB 充裕，全模型常驻 GPU", flush=True)
        else:
            pipe.enable_model_cpu_offload()
            print(f"显存 {vram_gb:.1f} GB，开启 model_cpu_offload", flush=True)

    elif model_key == "qwen-2.1-q5":
        from diffusers import (
            GGUFQuantizationConfig,
            QwenImage21Pipeline,
            QwenImage21Transformer2DModel,
        )
        from huggingface_hub import hf_hub_download, snapshot_download

        gguf_repo = (
            str(job.get("custom_transformer_repo") or "").strip()
            or "unsloth/Qwen-Image-2.1-GGUF"
        )
        gguf_file = (
            str(job.get("custom_transformer_file") or "").strip()
            or "qwen-image-2.1-Q5_K_M.gguf"
        )
        qdir = MODELS_DIR / "quant"
        bdir = MODELS_DIR / "Qwen-Image-2.1"
        print(f"下载/检查 GGUF 权重：{gguf_repo} :: {gguf_file}", flush=True)
        gguf_path = hf_hub_download(
            gguf_repo,
            gguf_file,
            local_dir=str(qdir),
            token=hf_token or None,
        )
        print("下载/检查 Qwen/Qwen-Image-2.1 基础组件…", flush=True)
        snapshot_download(
            "Qwen/Qwen-Image-2.1",
            local_dir=str(bdir),
            ignore_patterns=["transformer/*.safetensors", "transformer/*.index.json", "assets/*"],
            token=hf_token or None,
        )
        transformer = QwenImage21Transformer2DModel.from_single_file(
            gguf_path,
            quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
            config=str(bdir),
            subfolder="transformer",
            torch_dtype=torch.bfloat16,
        )
        pipe = QwenImage21Pipeline.from_pretrained(
            str(bdir),
            transformer=transformer,
            torch_dtype=torch.bfloat16,
        )
        if vram_gb >= 38:
            pipe.to("cuda")
        else:
            pipe.enable_model_cpu_offload()

    elif model_key in {"flux2-dev", "black-forest-labs/FLUX.2-dev"}:
        from diffusers import DiffusionPipeline

        print("加载 black-forest-labs/FLUX.2-dev (32B)…", flush=True)
        pipe = DiffusionPipeline.from_pretrained(
            "black-forest-labs/FLUX.2-dev",
            torch_dtype=torch.bfloat16,
            token=hf_token or None,
        )
        if vram_gb >= 76:
            pipe.to("cuda")
            print(f"显存 {vram_gb:.1f} GB，FLUX.2-dev 全常驻 GPU", flush=True)
        else:
            pipe.enable_model_cpu_offload()
            print(f"显存 {vram_gb:.1f} GB，开启 model_cpu_offload", flush=True)

    elif "/" in model_key:
        from diffusers import DiffusionPipeline

        print(f"加载自定义 Hugging Face Diffusers 模型：{model_key}…", flush=True)
        try:
            pipe = DiffusionPipeline.from_pretrained(
                model_key,
                torch_dtype=torch.bfloat16,
                token=hf_token or None,
            )
        except Exception as exc:
            print(f"bfloat16 加载提示（{exc}），尝试 float16…", flush=True)
            pipe = DiffusionPipeline.from_pretrained(
                model_key,
                torch_dtype=torch.float16,
                token=hf_token or None,
            )
        if vram_gb >= 76:
            try:
                pipe.to("cuda")
                print(f"显存 {vram_gb:.1f} GB 充裕，全模型常驻 GPU", flush=True)
            except torch.OutOfMemoryError:
                torch.cuda.empty_cache()
                pipe.enable_model_cpu_offload()
                print("全驻显存不足，已自动切换 model_cpu_offload", flush=True)
        else:
            pipe.enable_model_cpu_offload()
            print(f"显存 {vram_gb:.1f} GB，开启 model_cpu_offload", flush=True)
    else:
        raise RuntimeError(f"未知生图模型：{model_key}")

    _CACHE["key"] = cache_id
    _CACHE["pipe"] = pipe
    print(f"模型加载完成，耗时 {time.time() - t0:.1f}s", flush=True)
    return pipe


def _run_image_job(job: dict, hf_token: str | None) -> None:
    import torch
    from PIL import Image

    model_key = str(job.get("model") or "qwen-2.1-bf16")
    pipe = _load_image_pipeline(model_key, job, hf_token)
    loras = _normalize_loras(job.get("loras"))
    _apply_loras(pipe, loras, hf_token)

    is_qwen = model_key.startswith("qwen") or model_key.lower() == "qwen/qwen-image-2.1"
    ref = None
    ref_path = Path("/content/reference.bin")
    if job.get("has_image") and ref_path.exists():
        ref = Image.open(ref_path).convert("RGBA" if is_qwen else "RGB")
        print(f"启用参考图编辑：{ref.size}", flush=True)

    width = int(job.get("width") or 768)
    height = int(job.get("height") or 1152)
    steps = int(job.get("steps") or 35)
    cfg = float(job.get("cfg") or 5.0)
    seed = int(job["seed"]) if job.get("seed") is not None else 42
    prompt = str(job["prompt"])
    negative = str(job.get("negative") or " ")

    def call_once(w: int, h: int):
        sig = inspect.signature(pipe.__call__)
        params = set(sig.parameters.keys())
        has_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "width": w,
            "height": h,
            "num_inference_steps": steps,
            "generator": torch.Generator(device="cuda").manual_seed(seed),
        }
        if is_qwen:
            kwargs["negative_prompt"] = negative
            kwargs["true_cfg_scale"] = cfg
            kwargs["use_kv_cache"] = True
            if ref is not None:
                kwargs["image"] = [ref]
                kwargs["output_resolution"] = max(w, h)
        else:
            if "guidance_scale" in params or has_var_kw:
                kwargs["guidance_scale"] = cfg
            if negative.strip() and ("negative_prompt" in params):
                kwargs["negative_prompt"] = negative
            if ref is not None and ("image" in params or has_var_kw):
                kwargs["image"] = ref

        try:
            return pipe(**kwargs).images[0]
        except TypeError:
            kwargs.pop("output_resolution", None)
            kwargs.pop("use_kv_cache", None)
            return pipe(**kwargs).images[0]

    torch.cuda.reset_peak_memory_stats()
    try:
        image = call_once(width, height)
    except torch.OutOfMemoryError:
        print("显存不足，自动降分辨率到 512x768 重试…", flush=True)
        torch.cuda.empty_cache()
        image = call_once(512, 768)

    out_path = Path("/content/generated.png")
    image.save(out_path)
    _save_thumb(image)
    peak = round(torch.cuda.max_memory_allocated() / 1024**3, 2)
    print(f"saved_image {image.size} peak_mem_gb={peak}", flush=True)
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _save_thumb(img: Any) -> None:
    """Write a small JPEG preview used by the gallery; never fails the job."""
    thumb_path = Path("/content/generated_thumb.jpg")
    thumb_path.unlink(missing_ok=True)
    try:
        import numpy as np
        from PIL import Image

        if not isinstance(img, Image.Image):
            if hasattr(img, "detach"):
                arr = img.detach().cpu().float().numpy()
            else:
                arr = np.asarray(img)
            arr = np.squeeze(arr)
            if arr.ndim == 3 and arr.shape[0] in (1, 3, 4) and arr.shape[-1] not in (1, 3, 4):
                arr = np.transpose(arr, (1, 2, 0))
            if arr.dtype != np.uint8:
                if arr.min() < 0.0:
                    arr = (arr + 1.0) * 0.5
                if arr.max() <= 1.0:
                    arr = arr * 255.0
                arr = np.clip(arr, 0.0, 255.0).astype(np.uint8)
            img = Image.fromarray(arr)
        thumb = img.convert("RGB")
        thumb.thumbnail((480, 480))
        thumb.save(thumb_path, "JPEG", quality=82, optimize=True)
    except Exception as exc:
        print(f"缩略图生成跳过：{exc}", flush=True)


# ── Video + Audio pipeline (MiniMax-H3 33B) ───────────────────────────


def _load_minimax_h3(workflow: str, auto_offload: bool, hf_token: str | None) -> Any:
    import torch
    from diffusers import ComponentsManager, ModularPipeline

    cache_id = f"video:minimax-h3:{workflow}:offload={int(auto_offload)}"
    if _CACHE["key"] == cache_id and _CACHE["pipe"] is not None:
        print(f"命中常驻 MiniMax-H3（workflow={workflow}）", flush=True)
        return _CACHE["pipe"]

    _clear_cache()
    t0 = time.time()
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(
        f"加载 MiniMaxAI/MiniMax-H3（33B，workflow={workflow}，VRAM={vram_gb:.1f} GB）…",
        flush=True,
    )

    manager = None
    if auto_offload or vram_gb < 76:
        manager = ComponentsManager()
        manager.enable_auto_cpu_offload(device="cuda")
        print("已启用 ComponentsManager.enable_auto_cpu_offload(device='cuda')", flush=True)

    # ModularPipeline supports two slightly different calling conventions across dev commits
    try:
        load_kwargs: dict[str, Any] = {"token": hf_token or None}
        if manager is not None:
            load_kwargs["components_manager"] = manager
        pipe = ModularPipeline.from_pretrained("MiniMaxAI/MiniMax-H3", **load_kwargs)
        pipe.load_components(workflow=workflow, dtype=torch.bfloat16)
    except TypeError:
        load_kwargs = {"workflow": workflow, "token": hf_token or None}
        if manager is not None:
            load_kwargs["components_manager"] = manager
        pipe = ModularPipeline.from_pretrained("MiniMaxAI/MiniMax-H3", **load_kwargs)
        pipe.load_components(dtype=torch.bfloat16)

    if manager is None:
        pipe.to("cuda")

    _CACHE["key"] = cache_id
    _CACHE["pipe"] = pipe
    _CACHE["manager"] = manager
    print(f"MiniMax-H3 加载完成，耗时 {time.time() - t0:.1f}s", flush=True)
    return pipe


def _save_video_with_audio(
    frames: Any, audio: Any, sample_rate: int | None, out_path: Path, fps: int = 24
) -> None:
    # 1. Preferred: diffusers built-in encode_video (handles video + synchronized audio)
    try:
        from diffusers.utils.export_utils import encode_video

        kwargs: dict[str, Any] = {
            "video": frames,
            "fps": fps,
            "output_path": str(out_path),
        }
        if audio is not None and sample_rate:
            kwargs["audio"] = audio
            kwargs["audio_sample_rate"] = int(sample_rate)
        encode_video(**kwargs)
        if out_path.exists() and out_path.stat().st_size > 1024:
            print(f"encode_video 封装成功（含音轨={audio is not None}）", flush=True)
            return
    except Exception as exc:
        print(f"encode_video 回退到 ffmpeg 封装：{exc}", flush=True)

    # 2. Fallback: export_to_video + ffmpeg audio mux
    from diffusers.utils import export_to_video

    silent_mp4 = out_path.with_suffix(".silent.mp4")
    export_to_video(frames, str(silent_mp4), fps=fps)

    if audio is not None and sample_rate:
        import numpy as np
        import scipy.io.wavfile as wavfile

        wav_path = out_path.with_suffix(".wav")
        arr = audio.detach().cpu().float().numpy() if hasattr(audio, "detach") else np.asarray(audio)
        arr = np.squeeze(arr)
        if arr.ndim == 2 and arr.shape[0] <= 2 and arr.shape[1] > arr.shape[0]:
            arr = arr.T
        arr = np.clip(arr, -1.0, 1.0)
        wavfile.write(str(wav_path), int(sample_rate), (arr * 32767.0).astype(np.int16))
        _sh(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(silent_mp4),
                "-i",
                str(wav_path),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(out_path),
            ]
        )
        silent_mp4.unlink(missing_ok=True)
        wav_path.unlink(missing_ok=True)
    else:
        os.replace(silent_mp4, out_path)


def _run_video_job(job: dict, hf_token: str | None) -> None:
    import torch
    from PIL import Image

    workflow = str(job.get("workflow") or "t2va").strip()
    if workflow not in {"t2va", "fl2va", "ref2va"}:
        workflow = "t2va"

    first_path = Path("/content/reference.bin")
    last_path = Path("/content/last_frame.bin")
    has_first = bool(job.get("has_image")) and first_path.exists()
    has_last = bool(job.get("has_last_image")) and last_path.exists()

    if workflow == "fl2va" and not has_first:
        print("未上传首帧图，自动切换为文生视频工作流 t2va", flush=True)
        workflow = "t2va"
    elif workflow == "ref2va" and not has_first:
        print("未上传参考图，自动切换为文生视频工作流 t2va", flush=True)
        workflow = "t2va"

    auto_offload = bool(job.get("auto_offload", True))
    pipe = _load_minimax_h3(workflow, auto_offload, hf_token)

    loras = _normalize_loras(job.get("loras"))
    _apply_loras(pipe, loras, hf_token)

    width = int(job.get("width") or 768)
    height = int(job.get("height") or 1280)
    num_frames = int(job.get("num_frames") or 121)
    steps = int(job.get("steps") or 30)
    cfg = float(job.get("cfg") or 5.0)
    seed = int(job["seed"]) if job.get("seed") is not None else 42
    prompt = str(job["prompt"])
    negative = str(job.get("negative") or "").strip()

    # Inspect ModularPipeline accepted inputs so kwargs always align with current diffusers
    input_names: set[str] = set()
    try:
        if hasattr(pipe, "input_names"):
            input_names = set(pipe.input_names)
        elif hasattr(pipe, "blocks") and hasattr(pipe.blocks, "input_names"):
            input_names = set(pipe.blocks.input_names)
    except Exception:
        pass
    if input_names:
        print("pipeline input_names: " + ", ".join(sorted(input_names)), flush=True)

    kwargs: dict[str, Any] = {
        "prompt": prompt,
        "num_frames": num_frames,
        "generator": torch.Generator(device="cuda").manual_seed(seed),
    }

    if not input_names or "width" in input_names:
        kwargs["width"] = width
    if not input_names or "height" in input_names:
        kwargs["height"] = height
    if not input_names or "num_inference_steps" in input_names:
        kwargs["num_inference_steps"] = steps
    if not input_names or "guidance_scale" in input_names:
        kwargs["guidance_scale"] = cfg
    if negative and (not input_names or "negative_prompt" in input_names):
        kwargs["negative_prompt"] = negative

    if workflow in {"fl2va", "ref2va"} and has_first:
        first_img = Image.open(first_path).convert("RGB")
        print(f"加载首帧/参考图：{first_img.size}", flush=True)
        if workflow == "ref2va" and "reference_images" in input_names:
            kwargs["reference_images"] = [first_img]
        elif workflow == "ref2va" and "images" in input_names:
            kwargs["images"] = [first_img]
        else:
            kwargs["image"] = first_img
        if workflow == "fl2va" and has_last:
            last_img = Image.open(last_path).convert("RGB")
            print(f"加载尾帧图：{last_img.size}", flush=True)
            if not input_names or "last_image" in input_names:
                kwargs["last_image"] = last_img

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    print(
        f"开始 MiniMax-H3 生成：workflow={workflow}, {width}x{height}, frames={num_frames}, steps={steps}, cfg={cfg}",
        flush=True,
    )

    try:
        try:
            results = pipe(**kwargs, output=["videos", "audio", "sampling_rate"])
        except TypeError:
            # Fallback if output=[...] kwarg isn't supported
            results = pipe(**kwargs)
    finally:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Extract frames + audio across ModularPipeline return variants
    frames = None
    audio = None
    sample_rate = 24000

    if isinstance(results, dict):
        vids = results.get("videos") or results.get("frames")
        frames = vids[0] if isinstance(vids, (list, tuple)) and len(vids) > 0 else vids
        auds = results.get("audio")
        audio = auds[0] if isinstance(auds, (list, tuple)) and len(auds) > 0 else auds
        sample_rate = results.get("sampling_rate") or results.get("audio_sample_rate") or 24000
    elif isinstance(results, tuple):
        frames = results[0][0] if isinstance(results[0], (list, tuple)) else results[0]
        if len(results) > 1:
            audio = results[1][0] if isinstance(results[1], (list, tuple)) else results[1]
    else:
        vids = getattr(results, "videos", None) or getattr(results, "frames", None) or getattr(results, "images", None)
        frames = vids[0] if isinstance(vids, (list, tuple)) and len(vids) > 0 else vids
        auds = getattr(results, "audio", None)
        audio = auds[0] if isinstance(auds, (list, tuple)) and len(auds) > 0 else auds
        sample_rate = getattr(results, "sampling_rate", None) or 24000

    if frames is None:
        raise RuntimeError(f"MiniMax-H3 未返回视频帧（返回类型：{type(results).__name__}）")

    out_path = Path("/content/generated.mp4")
    _save_video_with_audio(frames, audio, int(sample_rate), out_path, fps=24)
    try:
        _save_thumb(frames[0])
    except Exception as exc:
        print(f"视频缩略图跳过：{exc}", flush=True)
    size_kb = out_path.stat().st_size // 1024
    peak = round(torch.cuda.max_memory_allocated() / 1024**3, 2)
    print(f"saved_video {size_kb}KB peak_mem_gb={peak}", flush=True)


# ── ComfyUI engine ────────────────────────────────────────────────────


def _comfy_http(path: str, data: dict | None = None, timeout: float = 20.0) -> Any:
    url = COMFY_BASE_URL + path
    body = None
    headers = {"Accept": "application/json"}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return raw.decode("utf-8", "replace")


def _comfy_is_up() -> bool:
    try:
        _comfy_http("/system_stats", timeout=2.5)
        return True
    except Exception:
        return False


def _comfy_free_vram() -> None:
    if not _comfy_is_up():
        return
    try:
        _comfy_http("/free", {"unload_models": True, "free_memory": True}, timeout=10.0)
        print("已通知 ComfyUI 释放显存以便切换到 Diffusers…", flush=True)
    except Exception:
        pass


def ensure_comfy_env() -> None:
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    if COMFY_ENV_MARKER.exists() and (COMFY_DIR / "main.py").exists():
        return
    print("正在初始化 ComfyUI 运行环境（首次约 1–2 分钟）…", flush=True)
    if not (COMFY_DIR / "main.py").exists():
        if COMFY_DIR.exists():
            shutil.rmtree(COMFY_DIR, ignore_errors=True)
        _sh(["git", "clone", "--depth", "1", "https://github.com/Comfy-Org/ComfyUI.git", str(COMFY_DIR)])

    # Filter out torch/torchvision/torchaudio so Colab's preinstalled CUDA/Blackwell PyTorch stays intact
    req_in = COMFY_DIR / "requirements.txt"
    req_filtered = Path("/content/.comfy_requirements_filtered.txt")
    if req_in.exists():
        lines = []
        for raw in req_in.read_text(encoding="utf-8").splitlines():
            s = raw.strip()
            low = s.lower()
            if not s or s.startswith("#"):
                continue
            if low.startswith(("torch", "torchvision", "torchaudio")):
                # Keep torchsde etc., only skip exact torch/torchvision/torchaudio packages
                pkg_name = low.split("=")[0].split(">")[0].split("<")[0].split("~")[0].split("[")[0].strip()
                if pkg_name in {"torch", "torchvision", "torchaudio"}:
                    continue
            lines.append(s)
        req_filtered.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _sh([sys.executable, "-m", "pip", "install", "-q", "-r", str(req_filtered)])

    _sh([
        sys.executable, "-m", "pip", "install", "-q", "-U",
        "huggingface_hub", "hf_xet", "websocket-client", "safetensors", "gguf",
    ])

    gguf_node_dir = COMFY_DIR / "custom_nodes" / "ComfyUI-GGUF"
    if not gguf_node_dir.exists():
        print("安装 ComfyUI-GGUF 扩展以支持 .gguf 权重…", flush=True)
        try:
            _sh(["git", "clone", "--depth", "1", "https://github.com/city96/ComfyUI-GGUF.git", str(gguf_node_dir)])
        except Exception as exc:
            print(f"提示：ComfyUI-GGUF 安装跳过（{exc}），safetensors 权重不受影响", flush=True)

    COMFY_ENV_MARKER.write_text("ok\n", encoding="utf-8")
    print("ComfyUI 运行环境准备完成", flush=True)


def _ensure_comfy_server(vram_gb: float) -> None:
    global _COMFY_PROC
    if _comfy_is_up():
        return
    cmd = [
        sys.executable,
        str(COMFY_DIR / "main.py"),
        "--listen", "127.0.0.1",
        "--port", str(COMFY_PORT),
        "--disable-auto-launch",
    ]
    if vram_gb >= 60:
        cmd.append("--highvram")
    print(f"启动常驻 ComfyUI 服务（{'--highvram' if vram_gb >= 60 else 'auto'}）…", flush=True)
    log_fh = COMFY_LOG_PATH.open("ab")
    _COMFY_PROC = subprocess.Popen(
        cmd,
        cwd=str(COMFY_DIR),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
    )
    deadline = time.time() + 180.0
    while time.time() < deadline:
        if _comfy_is_up():
            print("ComfyUI 服务已就绪（模型将常驻显存复用）", flush=True)
            return
        if _COMFY_PROC.poll() is not None:
            tail = ""
            try:
                tail = "\n".join(COMFY_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-30:])
            except Exception:
                pass
            raise RuntimeError(f"ComfyUI 启动退出（code={_COMFY_PROC.returncode}）：\n{tail}")
        time.sleep(1.5)
    raise RuntimeError("等待 ComfyUI 启动超时（180s）")


def _comfy_asset_name(spec: dict) -> str:
    if spec.get("source") == "hf":
        repo = str(spec["repo_id"]).replace("/", "__")
        fn = str(spec["filename"]).replace("/", "__")
        return f"{repo}__{fn}"
    h = hashlib.sha256(str(spec.get("url") or "").encode("utf-8")).hexdigest()[:10]
    base = Path(str(spec.get("basename") or "model.safetensors")).name
    return f"url_{h}__{base}"


def _download_comfy_asset(spec: dict, subdir: str, label: str, hf_token: str | None) -> str:
    models_sub = COMFY_DIR / "models" / subdir
    models_sub.mkdir(parents=True, exist_ok=True)
    target_name = _comfy_asset_name(spec)
    target_path = models_sub / target_name
    if target_path.exists() and target_path.stat().st_size > 1024:
        print(f"命中本地缓存（{label}）：{spec.get('basename') or target_name}", flush=True)
        return target_name

    if spec.get("source") == "hf":
        from huggingface_hub import hf_hub_download

        repo_id = str(spec["repo_id"])
        filename = str(spec["filename"])
        revision = str(spec.get("revision") or "main")
        print(f"下载 {label}：{repo_id} :: {filename}", flush=True)
        cache_dir = COMFY_CACHE_DIR / repo_id.replace("/", "__")
        cache_dir.mkdir(parents=True, exist_ok=True)
        local_src = Path(
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                local_dir=str(cache_dir),
                token=hf_token or None,
            )
        )
        if target_path.exists() or target_path.is_symlink():
            target_path.unlink()
        try:
            target_path.symlink_to(local_src.resolve())
        except OSError:
            shutil.copy2(local_src, target_path)
    else:
        url = str(spec["url"])
        print(f"下载 {label}：{url}", flush=True)
        tmp = target_path.with_suffix(target_path.suffix + ".part")
        req = urllib.request.Request(url, headers={"User-Agent": "ColabStudio/2.1"})
        with urllib.request.urlopen(req, timeout=300) as resp, tmp.open("wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            last_pct = -10
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if total > 0:
                    pct = int(done * 100 / total)
                    if pct >= last_pct + 10:
                        last_pct = pct
                        print(f"下载 {label}: {pct}% ({done // 1048576}/{total // 1048576} MB)", flush=True)
        os.replace(tmp, target_path)

    # Touch directory mtime so ComfyUI's folder_paths picks up the new file immediately
    try:
        os.utime(models_sub, None)
    except OSError:
        pass
    return target_name


def _build_comfy_prompt(
    job: dict,
    files: dict[str, Any],
    has_ref: bool,
    ref_image_name: str = "colab_ref.png",
) -> tuple[dict[str, Any], dict[str, str]]:
    """Build a ComfyUI /prompt API graph and human-readable node labels."""
    comfy = job["comfy"]
    template = str(comfy.get("template") or "qwen-image-2.1")
    clip_type = str(comfy.get("clip_type") or "qwen_image")
    sampler = str(comfy.get("sampler") or "euler")
    scheduler = str(comfy.get("scheduler") or "simple")
    denoise = float(comfy.get("denoise", 1.0))

    width = int(job.get("width") or 1024)
    height = int(job.get("height") or 1536)
    steps = int(job.get("steps") or 35)
    cfg = float(job.get("cfg") or 5.0)
    seed = int(job["seed"]) if job.get("seed") is not None else 42
    prompt_text = str(job["prompt"])
    negative_text = str(job.get("negative") or "")

    diff_file = str(files["diffusion"])
    te_file = str(files["text_encoder"])
    vae_file = str(files["vae"])
    lora_files = list(files.get("loras") or [])

    graph: dict[str, Any] = {}
    labels: dict[str, str] = {}

    if diff_file.lower().endswith(".gguf"):
        graph["1"] = {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": diff_file}}
    else:
        graph["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": diff_file, "weight_dtype": "default"}}
    labels["1"] = "加载扩散模型"

    graph["2"] = {
        "class_type": "CLIPLoader",
        "inputs": {"clip_name": te_file, "type": clip_type, "device": "default"},
    }
    labels["2"] = "加载文本编码器"

    graph["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": vae_file}}
    labels["3"] = "加载 VAE"

    model_ref: list[Any] = ["1", 0]
    for idx, lf in enumerate(lora_files):
        nid = str(10 + idx)
        graph[nid] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": model_ref,
                "lora_name": lf["filename"],
                "strength_model": float(lf["scale"]),
            },
        }
        labels[nid] = f"加载 LoRA #{idx + 1}"
        model_ref = [nid, 0]

    if template == "qwen-image-2.1":
        graph["20"] = {
            "class_type": "QwenImage21Cache",
            "inputs": {"model": model_ref, "device": "auto", "dtype": "default"},
        }
        labels["20"] = "初始化 Qwen 2.1 KV Cache"

        graph["21"] = {
            "class_type": "ModelSamplingFlux",
            "inputs": {
                "model": ["20", 0],
                "max_shift": 0.6935483870967742,
                "base_shift": 0.5,
                "width": width,
                "height": height,
            },
        }
        labels["21"] = "配置采样偏移"

        graph["22"] = {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        }
        labels["22"] = "准备潜空间"

        enc_inputs: dict[str, Any] = {
            "clip": ["2", 0],
            "prompt": prompt_text,
            "negative_prompt": negative_text,
            "resolution": max(width, height),
        }
        if has_ref:
            graph["23"] = {"class_type": "LoadImage", "inputs": {"image": ref_image_name}}
            labels["23"] = "读取参考图"
            graph["24"] = {
                "class_type": "JoinImageWithAlpha",
                "inputs": {"image": ["23", 0], "alpha": ["23", 1]},
            }
            labels["24"] = "准备参考图通道"
            enc_inputs["vae"] = ["3", 0]
            enc_inputs["images.image_1"] = ["24", 0]

        graph["25"] = {"class_type": "TextEncodeQwenImage21", "inputs": enc_inputs}
        labels["25"] = "编码提示词" + ("与参考图" if has_ref else "")

        graph["26"] = {
            "class_type": "KSampler",
            "inputs": {
                "model": ["21", 0],
                "positive": ["25", 0],
                "negative": ["25", 1],
                "latent_image": ["22", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise,
            },
        }
        labels["26"] = "正在采样出图"

    elif template == "flux":
        graph["20"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt_text}}
        labels["20"] = "编码正向提示词"
        graph["21"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}}
        labels["21"] = "编码空负向提示词"
        graph["25"] = {
            "class_type": "FluxGuidance",
            "inputs": {"conditioning": ["20", 0], "guidance": cfg},
        }
        labels["25"] = "配置 Flux Guidance"
        if has_ref:
            graph["23"] = {"class_type": "LoadImage", "inputs": {"image": ref_image_name}}
            labels["23"] = "读取参考图"
            graph["22"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["23", 0], "vae": ["3", 0]}}
            labels["22"] = "编码参考图潜空间"
        else:
            graph["22"] = {
                "class_type": "EmptySD3LatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            }
            labels["22"] = "准备潜空间"
        graph["26"] = {
            "class_type": "KSampler",
            "inputs": {
                "model": model_ref,
                "positive": ["25", 0],
                "negative": ["21", 0],
                "latent_image": ["22", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise,
            },
        }
        labels["26"] = "正在采样出图"

    else:  # sd-generic
        graph["20"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt_text}}
        labels["20"] = "编码正向提示词"
        graph["21"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative_text}}
        labels["21"] = "编码负向提示词"
        if has_ref:
            graph["23"] = {"class_type": "LoadImage", "inputs": {"image": ref_image_name}}
            labels["23"] = "读取参考图"
            graph["22"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["23", 0], "vae": ["3", 0]}}
            labels["22"] = "编码参考图潜空间"
        else:
            graph["22"] = {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            }
            labels["22"] = "准备潜空间"
        graph["26"] = {
            "class_type": "KSampler",
            "inputs": {
                "model": model_ref,
                "positive": ["20", 0],
                "negative": ["21", 0],
                "latent_image": ["22", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise,
            },
        }
        labels["26"] = "正在采样出图"

    graph["27"] = {"class_type": "VAEDecode", "inputs": {"samples": ["26", 0], "vae": ["3", 0]}}
    labels["27"] = "VAE 解码图像"
    graph["28"] = {
        "class_type": "SaveImage",
        "inputs": {"images": ["27", 0], "filename_prefix": "colab_studio"},
    }
    labels["28"] = "保存输出图像"
    return graph, labels


def _run_comfy_image_job(job: dict, hf_token: str | None, vram_gb: float) -> None:
    import torch
    import websocket
    from PIL import Image

    _clear_cache()
    ensure_comfy_env()

    comfy = job["comfy"]
    diff_name = _download_comfy_asset(comfy["diffusion"], "diffusion_models", "扩散模型", hf_token)
    te_name = _download_comfy_asset(comfy["text_encoder"], "text_encoders", "文本编码器", hf_token)
    vae_name = _download_comfy_asset(comfy["vae"], "vae", "VAE", hf_token)

    lora_files = []
    for idx, item in enumerate(_normalize_loras(job.get("loras"))):
        repo_id = item["repo_id"]
        weight_name = item["weight_name"]
        if not weight_name:
            from huggingface_hub import list_repo_files

            cands = [f for f in list_repo_files(repo_id, token=hf_token or None) if f.endswith(".safetensors")]
            if not cands:
                raise RuntimeError(f"LoRA 仓库 {repo_id} 中未找到 .safetensors 文件")
            weight_name = cands[0]
        lspec = {
            "source": "hf",
            "repo_id": repo_id,
            "filename": weight_name,
            "revision": "main",
            "basename": weight_name.rsplit("/", 1)[-1],
        }
        local_lora = _download_comfy_asset(lspec, "loras", f"LoRA #{idx + 1}", hf_token)
        lora_files.append({"filename": local_lora, "scale": item["scale"]})

    has_ref = False
    ref_name = "colab_ref.png"
    ref_path = Path("/content/reference.bin")
    if job.get("has_image") and ref_path.exists():
        inp_dir = COMFY_DIR / "input"
        inp_dir.mkdir(parents=True, exist_ok=True)
        img = Image.open(ref_path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        ref_name = f"colab_ref_{int(time.time() * 1000) % 1000000}.png"
        img.save(inp_dir / ref_name, format="PNG")
        has_ref = True
        print(f"启用 ComfyUI 参考图编辑：{img.size}", flush=True)

    _ensure_comfy_server(vram_gb)

    graph, labels = _build_comfy_prompt(
        job,
        {"diffusion": diff_name, "text_encoder": te_name, "vae": vae_name, "loras": lora_files},
        has_ref=has_ref,
        ref_image_name=ref_name,
    )
    client_id = uuid.uuid4().hex
    ws = websocket.create_connection(f"ws://127.0.0.1:{COMFY_PORT}/ws?clientId={client_id}", timeout=60)
    prompt_id = ""
    try:
        try:
            resp = _comfy_http("/prompt", {"prompt": graph, "client_id": client_id}, timeout=30.0)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", "replace")[:800]
            raise RuntimeError(f"ComfyUI 校验工作流失败（HTTP {exc.code}）：{err_body}") from exc
        if isinstance(resp, dict) and resp.get("node_errors"):
            raise RuntimeError(f"ComfyUI 节点校验失败：{json.dumps(resp['node_errors'], ensure_ascii=False)[:600]}")
        prompt_id = str(resp.get("prompt_id") or "")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI 未返回 prompt_id：{resp}")

        step_t0 = 0.0
        last_node = ""
        while True:
            try:
                raw_msg = ws.recv()
            except websocket.WebSocketTimeoutException:
                # Check if prompt already finished in history
                hist = _comfy_http(f"/history/{prompt_id}", timeout=10.0)
                if isinstance(hist, dict) and prompt_id in hist:
                    break
                continue
            if not isinstance(raw_msg, str):
                continue
            msg = json.loads(raw_msg)
            mtype = msg.get("type")
            mdata = msg.get("data") or {}
            if mdata.get("prompt_id") and mdata.get("prompt_id") != prompt_id:
                continue
            if mtype == "executing":
                node = mdata.get("node")
                if node is None:
                    break
                if node != last_node:
                    last_node = str(node)
                    step_t0 = time.time()
                    print(f"ComfyUI：{labels.get(last_node, '执行节点 ' + last_node)}…", flush=True)
            elif mtype == "progress":
                val = int(mdata.get("value") or 0)
                mx = max(1, int(mdata.get("max") or 1))
                pct = int(round(val * 100 / mx))
                dt = max(0.05, time.time() - (step_t0 or time.time()))
                rate = val / dt if val > 0 else 0.0
                rem = int((mx - val) / rate) if rate > 0 else 0
                elap = int(dt)
                print(
                    f"ComfyUI 采样: {pct:3d}%|{'█' * (pct // 10)}{' ' * (10 - pct // 10)}| "
                    f"{val}/{mx} [{elap // 60:02d}:{elap % 60:02d}<{rem // 60:02d}:{rem % 60:02d}, {rate:.2f}it/s]",
                    flush=True,
                )
            elif mtype == "execution_error":
                ntype = mdata.get("node_type") or mdata.get("node_id") or "unknown"
                emsg = mdata.get("exception_message") or str(mdata)
                raise RuntimeError(f"ComfyUI 执行失败（{ntype}）：{emsg}")
    except KeyboardInterrupt:
        try:
            _comfy_http("/interrupt", {}, timeout=5.0)
        except Exception:
            pass
        raise
    finally:
        try:
            ws.close()
        except Exception:
            pass

    hist = _comfy_http(f"/history/{prompt_id}", timeout=15.0)
    entry = hist.get(prompt_id) if isinstance(hist, dict) else None
    outputs = (entry or {}).get("outputs") or {}
    saved_file: Path | None = None
    for node_out in outputs.values():
        imgs = node_out.get("images") if isinstance(node_out, dict) else None
        if imgs:
            info = imgs[0]
            sub = str(info.get("subfolder") or "").strip("/")
            fname = str(info.get("filename") or "")
            cand = (COMFY_DIR / "output" / sub / fname) if sub else (COMFY_DIR / "output" / fname)
            if cand.exists():
                saved_file = cand
                break
    if not saved_file:
        raise RuntimeError("ComfyUI 已完成但未找到输出图片")

    out_path = Path("/content/generated.png")
    img = Image.open(saved_file)
    img.save(out_path, format="PNG")
    _save_thumb(img)
    peak = round(torch.cuda.max_memory_allocated() / 1024**3, 2) if torch.cuda.is_available() else 0.0
    print(f"saved_image {img.size} engine=comfyui peak_mem_gb={peak}", flush=True)


def run_job(job_path: str = "/content/job.json") -> None:
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    hf_token = os.environ.get("HF_TOKEN") or ""
    mode = str(job.get("mode") or "image")
    engine = str(job.get("engine") or "diffusers")
    Path("/content/generated_thumb.jpg").unlink(missing_ok=True)

    if mode == "image" and engine == "comfyui":
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("当前 Colab 运行时没有检测到 CUDA GPU")
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"GPU: {gpu_name} ({vram_gb:.1f} GB VRAM) · 引擎=ComfyUI", flush=True)
        _run_comfy_image_job(job, hf_token, vram_gb)
        return

    _comfy_free_vram()
    ensure_env()
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("当前 Colab 运行时没有检测到 CUDA GPU")
    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU: {gpu_name} ({vram_gb:.1f} GB VRAM)", flush=True)

    if mode == "video":
        _run_video_job(job, hf_token)
    else:
        _run_image_job(job, hf_token)


if __name__ == "__main__":
    run_job()
