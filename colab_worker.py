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

if "_CACHE" not in globals():
    _CACHE: dict[str, Any] = {
        "key": None,
        "pipe": None,
        "manager": None,
        "loras": [],
    }
if "_COMFY_PROC" not in globals():
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
    # High-performance Xet concurrency aggressively hammers HF CAS from shared Colab GCP IPs
    # and triggers 429 Too Many Requests on 30B+ models like MiniMax-H3.
    os.environ.pop("HF_XET_HIGH_PERFORMANCE", None)
    os.environ.setdefault("HF_XET_NUM_CONCURRENT_RANGE_GETS", "8")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
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


_MINIMAX_H3_COMFY_RENAME = (
    ("token_refiner.blocks.", "token_refiner.refiner_blocks."),
    ("time_embedder.proj_in.", "time_embedder.linear_1."),
    ("time_embedder.proj_out.", "time_embedder.linear_2."),
    ("video_patch_proj.", "proj_in."),
    ("audio_patch_proj.", "audio_proj_in."),
    ("condition_proj.", "context_embedder."),
    ("final_layer.norm.", "norm_out.norm."),
    ("final_layer.adaln_proj.linear.", "norm_out.linear."),
    ("final_layer.video_out.", "proj_out."),
    ("final_layer.audio_out.", "audio_proj_out."),
    (".attn.q_norm.", ".attn.norm_q."),
    (".attn.k_norm.", ".attn.norm_k."),
    (".attn.out_proj.", ".attn.to_out.0."),
    (".mlp.fc1.", ".ff.net.0.proj."),
    (".mlp.fc2.", ".ff.net.2."),
)


def _split_dim0(tensor: Any, chunks: int) -> list[Any]:
    size = tensor.shape[0]
    if size % chunks != 0:
        raise ValueError(f"tensor dim0 {size} not divisible by {chunks}")
    step = size // chunks
    return [tensor[i * step : (i + 1) * step] for i in range(chunks)]


def _cat_dim0(parts: list[Any]) -> Any:
    try:
        import torch

        if isinstance(parts[0], torch.Tensor):
            return torch.cat(parts, dim=0)
    except ImportError:
        pass
    import numpy as np

    return np.concatenate(parts, axis=0)


def _is_minimax_h3_comfy_lora(keys: Any) -> bool:
    for k in keys:
        s = str(k)
        if any(
            marker in s
            for marker in (
                "diffusion_model.blocks.",
                "diffusion_model.token_refiner.blocks.",
                "diffusion_model.audio_patch_proj.",
                ".attn.qkv_proj.",
                ".mlp.fc1.",
                ".mlp.fc2.",
            )
        ):
            return True
        if s.startswith(("blocks.", "token_refiner.blocks.", "audio_patch_proj.")):
            return True
    return False


def _convert_minimax_h3_comfy_lora(
    state_dict: dict[str, Any],
    valid_modules: set[str] | None = None,
) -> dict[str, Any]:
    """Losslessly convert ComfyUI / native MiniMax-H3 LoRA tensors to Diffusers PEFT layout.

    Handles:
    - Stripping `model.diffusion_model.` / `diffusion_model.` prefix
    - Splitting fused `attn.qkv_proj` (`[q; k; v]`) LoRA B into 3 contiguous chunks for
      `attn.to_q`, `attn.to_k`, `attn.to_v` sharing the same LoRA A (mathematically exact)
    - Swapping `[gate; value]` halves of `mlp.fc1` LoRA B to Diffusers SwiGLU `[value; gate]`
      layout for `ff.net.0.proj` (mathematically exact)
    - Renaming `blocks.` -> `transformer_blocks.`, `token_refiner.blocks.` -> `token_refiner.refiner_blocks.`,
      `attn.out_proj` -> `attn.to_out.0`, `mlp.fc2` -> `ff.net.2`, `audio_patch_proj` -> `audio_proj_in`, etc.
    - Folding explicit `.alpha` tensors into `lora_B` so PEFT's default `alpha == rank` stays exact
    """
    grouped: dict[str, dict[str, Any]] = {}
    for raw_key, val in state_dict.items():
        k = str(raw_key)
        for pref in ("model.diffusion_model.", "diffusion_model.", "transformer."):
            if k.startswith(pref):
                k = k[len(pref) :]
                break
        if k.endswith(".lora_A.weight"):
            mod, kind = k[: -len(".lora_A.weight")], "A"
        elif k.endswith(".lora_B.weight"):
            mod, kind = k[: -len(".lora_B.weight")], "B"
        elif k.endswith(".lora_down.weight"):
            mod, kind = k[: -len(".lora_down.weight")], "A"
        elif k.endswith(".lora_up.weight"):
            mod, kind = k[: -len(".lora_up.weight")], "B"
        elif k.endswith(".alpha"):
            mod, kind = k[: -len(".alpha")], "alpha"
        else:
            continue
        grouped.setdefault(mod, {})[kind] = val

    converted: dict[str, Any] = {}
    for raw_mod, entry in grouped.items():
        a_t = entry.get("A")
        b_t = entry.get("B")
        if a_t is None or b_t is None:
            continue
        alpha_t = entry.get("alpha")
        if alpha_t is not None:
            rank = int(a_t.shape[0])
            alpha_val = float(alpha_t.item() if hasattr(alpha_t, "item") else alpha_t)
            if rank > 0 and abs(alpha_val - rank) > 1e-6:
                b_t = b_t * (alpha_val / rank)

        mod_dot = raw_mod + "."
        if mod_dot.startswith("blocks."):
            mod_dot = "transformer_blocks." + mod_dot[len("blocks.") :]
        for old, new in _MINIMAX_H3_COMFY_RENAME:
            mod_dot = mod_dot.replace(old, new)
        mod = mod_dot[:-1]

        if mod.endswith(".attn.qkv_proj"):
            base_mod = mod[: -len("qkv_proj")]
            bq, bk, bv = _split_dim0(b_t, 3)
            for proj, b_part in (("to_q", bq), ("to_k", bk), ("to_v", bv)):
                target_mod = base_mod + proj
                if valid_modules is not None and target_mod not in valid_modules:
                    continue
                converted[f"transformer.{target_mod}.lora_A.weight"] = a_t
                converted[f"transformer.{target_mod}.lora_B.weight"] = b_part
        elif mod.endswith(".ff.net.0.proj"):
            gate_b, val_b = _split_dim0(b_t, 2)
            b_swapped = _cat_dim0([val_b, gate_b])
            if valid_modules is not None and mod not in valid_modules:
                continue
            converted[f"transformer.{mod}.lora_A.weight"] = a_t
            converted[f"transformer.{mod}.lora_B.weight"] = b_swapped
        else:
            if valid_modules is not None and mod not in valid_modules:
                continue
            converted[f"transformer.{mod}.lora_A.weight"] = a_t
            converted[f"transformer.{mod}.lora_B.weight"] = b_t

    return converted


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
                    existing = list(getattr(target, "peft_config", {}).keys())
                    if existing:
                        target.delete_adapters(existing)
                except Exception:
                    pass
        _CACHE["loras"] = []

    if not loras:
        return

    from huggingface_hub import hf_hub_download, list_repo_files

    LORAS_DIR.mkdir(parents=True, exist_ok=True)
    loaded_names: list[str] = []
    loaded_scales: list[float] = []

    for idx, item in enumerate(loras):
        repo_id = item["repo_id"]
        weight_name = item["weight_name"]
        scale = item["scale"]
        adapter_name = f"lora_{idx}"
        if not weight_name:
            try:
                cands = [
                    f for f in list_repo_files(repo_id, token=hf_token or None)
                    if f.endswith(".safetensors")
                ]
                if len(cands) == 1:
                    weight_name = cands[0]
            except Exception:
                pass
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
            elif hasattr(target, "load_lora_adapter"):
                try:
                    if local_file and local_file.endswith(".safetensors") and "MiniMaxH3" in type(target).__name__:
                        from safetensors.torch import load_file as _st_load

                        raw_sd = _st_load(local_file)
                        if _is_minimax_h3_comfy_lora(raw_sd.keys()):
                            valid_mods = {name for name, _ in target.named_modules() if name}
                            conv_sd = _convert_minimax_h3_comfy_lora(raw_sd, valid_modules=valid_mods)
                            if not conv_sd:
                                raise RuntimeError("未能将 ComfyUI MiniMax-H3 LoRA 映射到当前 transformer 模块")
                            print(
                                f"检测到 ComfyUI 格式 MiniMax-H3 LoRA，已无损转换 {len(conv_sd) // 2} 个目标层权重",
                                flush=True,
                            )
                            target.load_lora_adapter(
                                conv_sd, prefix="transformer", adapter_name=adapter_name
                            )
                            loaded = True
                            break
                        # Diffusers-format safetensors on MiniMax-H3
                        has_pref = any(k.startswith("transformer.") for k in raw_sd)
                        target.load_lora_adapter(
                            raw_sd,
                            prefix="transformer" if has_pref else None,
                            adapter_name=adapter_name,
                        )
                        loaded = True
                        break
                    if local_file:
                        p = Path(local_file)
                        target.load_lora_adapter(
                            str(p.parent), weight_name=p.name, adapter_name=adapter_name
                        )
                    else:
                        target.load_lora_adapter(repo_id, token=hf_token or None, adapter_name=adapter_name)
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


def _load_ref_paths(job: dict) -> list[Path]:
    if not job.get("has_image"):
        return []
    paths: list[Path] = []
    ref_count = int(job.get("ref_count") or 0)
    if ref_count > 0:
        for idx in range(ref_count):
            p = Path(f"/content/reference_{idx}.bin")
            if p.exists():
                paths.append(p)
    if not paths:
        legacy = Path("/content/reference.bin")
        if legacy.exists():
            paths.append(legacy)
    return paths


def _run_image_job(job: dict, hf_token: str | None) -> None:
    import torch
    from PIL import Image

    model_key = str(job.get("model") or "qwen-2.1-bf16")
    pipe = _load_image_pipeline(model_key, job, hf_token)
    loras = _normalize_loras(job.get("loras"))
    _apply_loras(pipe, loras, hf_token)

    is_qwen = model_key.startswith("qwen") or model_key.lower() == "qwen/qwen-image-2.1"
    refs: list[Any] = []
    for rp in _load_ref_paths(job):
        refs.append(Image.open(rp).convert("RGBA" if is_qwen else "RGB"))
    if refs:
        sizes = ", ".join(str(im.size) for im in refs)
        print(f"启用参考图编辑（{len(refs)} 张）：{sizes}", flush=True)

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
            if refs:
                kwargs["image"] = refs
                kwargs["output_resolution"] = max(w, h)
        else:
            if "guidance_scale" in params or has_var_kw:
                kwargs["guidance_scale"] = cfg
            if negative.strip() and ("negative_prompt" in params):
                kwargs["negative_prompt"] = negative
            if refs and ("image" in params or has_var_kw):
                kwargs["image"] = refs if len(refs) > 1 else refs[0]

        try:
            return pipe(**kwargs).images[0]
        except TypeError:
            kwargs.pop("output_resolution", None)
            kwargs.pop("use_kv_cache", None)
            if not is_qwen and isinstance(kwargs.get("image"), list) and refs:
                kwargs["image"] = refs[0]
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


def _disable_hf_xet() -> None:
    """Disable huggingface_hub Xet backend at runtime (works even after import)."""
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ.pop("HF_XET_HIGH_PERFORMANCE", None)
    try:
        import huggingface_hub.constants as _hf_const

        _hf_const.HF_HUB_DISABLE_XET = True
    except Exception:
        pass
    try:
        import huggingface_hub.file_download as _hf_fd

        if hasattr(_hf_fd, "HF_HUB_DISABLE_XET"):
            _hf_fd.HF_HUB_DISABLE_XET = True
        if hasattr(_hf_fd, "constants") and hasattr(_hf_fd.constants, "HF_HUB_DISABLE_XET"):
            _hf_fd.constants.HF_HUB_DISABLE_XET = True
    except Exception:
        pass
    for mod_name in ("huggingface_hub.utils._xet", "huggingface_hub.utils"):
        try:
            mod = sys.modules.get(mod_name)
            fn = getattr(mod, "is_xet_available", None)
            if fn is not None and hasattr(fn, "cache_clear"):
                fn.cache_clear()
        except Exception:
            pass


def _missing_minimax_components(pipe: Any) -> list[str]:
    """Return core MiniMax-H3 component names that failed to load (remained None).

    diffusers ModularPipeline.load_components() catches per-component ValueError (e.g. HF 429)
    and continues without raising, leaving the failed component as None.
    """
    core = ("text_encoder", "transformer", "vae", "audio_vae", "scheduler", "tokenizer", "processor")
    comps = getattr(pipe, "components", None)
    missing: list[str] = []
    if isinstance(comps, dict):
        for name in core:
            if name in comps and comps[name] is None:
                missing.append(name)
    else:
        for name in ("text_encoder", "transformer", "vae", "audio_vae", "scheduler"):
            if hasattr(pipe, name) and getattr(pipe, name) is None:
                missing.append(name)
    return missing


def _load_minimax_h3(workflow: str, auto_offload: bool, hf_token: str | None) -> Any:
    import torch
    from diffusers import ComponentsManager, ModularPipeline

    if hf_token:
        os.environ["HF_TOKEN"] = hf_token

    cache_id = f"video:minimax-h3:{workflow}:offload={int(auto_offload)}"
    if _CACHE["key"] == cache_id and _CACHE["pipe"] is not None:
        cached_missing = _missing_minimax_components(_CACHE["pipe"])
        if not cached_missing:
            print(f"命中常驻 MiniMax-H3（workflow={workflow}）", flush=True)
            return _CACHE["pipe"]
        print(
            f"检测到缓存的 MiniMax-H3 缺失组件（{', '.join(cached_missing)}），放弃旧缓存并重新加载…",
            flush=True,
        )

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

    missing = _missing_minimax_components(pipe)
    if missing:
        # Disable Xet CAS CDN (prone to 429 on shared Colab GCP IPs) and retry missing components via standard HTTP
        _disable_hf_xet()
        load_sig = inspect.signature(pipe.load_components).parameters
        for attempt, delay in enumerate((6, 15, 30), start=1):
            print(
                f"MiniMax-H3 组件下载不完整（缺失：{', '.join(missing)}），已关闭 Xet 加速，{delay}s 后第 {attempt}/3 次重试补拉…",
                flush=True,
            )
            time.sleep(delay)
            retry_kwargs: dict[str, Any] = {"dtype": torch.bfloat16}
            if "names" in load_sig:
                retry_kwargs["names"] = missing
            elif "workflow" in load_sig:
                retry_kwargs["workflow"] = workflow
            pipe.load_components(**retry_kwargs)
            missing = _missing_minimax_components(pipe)
            if not missing:
                print("MiniMax-H3 缺失组件补拉成功", flush=True)
                break

    if missing:
        _clear_cache()
        raise RuntimeError(
            f"MiniMax-H3 组件加载失败（缺失：{', '.join(missing)}），"
            "通常是 Hugging Face 对 Colab 共享 IP 限流 (429) 导致，请稍等 1 分钟后重试"
        )

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

    ref_paths = _load_ref_paths(job)
    last_path = Path("/content/last_frame.bin")
    has_first = bool(ref_paths)
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
        ref_imgs = [Image.open(p).convert("RGB") for p in ref_paths]
        first_img = ref_imgs[0]
        sizes = ", ".join(str(im.size) for im in ref_imgs)
        print(f"加载首帧/参考图（{len(ref_imgs)} 张）：{sizes}", flush=True)
        if workflow == "ref2va":
            if not input_names or "references" in input_names:
                try:
                    from diffusers.modular_pipelines.minimax_h3 import MiniMaxH3ImageReference

                    kwargs["references"] = [MiniMaxH3ImageReference(image=im) for im in ref_imgs]
                except ImportError:
                    kwargs["references"] = ref_imgs
            elif "reference_images" in input_names:
                kwargs["reference_images"] = ref_imgs
            elif "images" in input_names:
                kwargs["images"] = ref_imgs
            else:
                kwargs["image"] = first_img
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
    sample_rate = 32000

    if isinstance(results, dict):
        vids = results.get("videos") or results.get("frames")
        frames = vids[0] if isinstance(vids, (list, tuple)) and len(vids) > 0 else vids
        auds = results.get("audio")
        audio = auds[0] if isinstance(auds, (list, tuple)) and len(auds) > 0 else auds
        sample_rate = results.get("sampling_rate") or results.get("audio_sample_rate") or 32000
    elif isinstance(results, tuple):
        frames = results[0][0] if isinstance(results[0], (list, tuple)) else results[0]
        if len(results) > 1:
            audio = results[1][0] if isinstance(results[1], (list, tuple)) else results[1]
        if len(results) > 2 and results[2]:
            sample_rate = results[2]
    else:
        vids = getattr(results, "videos", None) or getattr(results, "frames", None) or getattr(results, "images", None)
        frames = vids[0] if isinstance(vids, (list, tuple)) and len(vids) > 0 else vids
        auds = getattr(results, "audio", None)
        audio = auds[0] if isinstance(auds, (list, tuple)) and len(auds) > 0 else auds
        sample_rate = getattr(results, "sampling_rate", None) or 32000

    # MiniMaxH3AudioDecodeStep returns shape (1, 2, num_samples); squeeze batch dim so encode_video keeps stereo
    if audio is not None and getattr(audio, "ndim", 0) == 3 and audio.shape[0] == 1:
        audio = audio[0]

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
    ref_image_names: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Build a ComfyUI /prompt API graph and human-readable node labels."""
    names = [n for n in (ref_image_names or []) if n]
    if not names and has_ref and ref_image_name:
        names = [ref_image_name]
    has_ref = bool(names)
    primary_ref = names[0] if names else ref_image_name
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
            enc_inputs["vae"] = ["3", 0]
            for idx, rname in enumerate(names[:16]):
                load_nid = "23" if idx == 0 else str(30 + idx * 2)
                join_nid = "24" if idx == 0 else str(31 + idx * 2)
                graph[load_nid] = {"class_type": "LoadImage", "inputs": {"image": rname}}
                labels[load_nid] = f"读取参考图 #{idx + 1}" if len(names) > 1 else "读取参考图"
                graph[join_nid] = {
                    "class_type": "JoinImageWithAlpha",
                    "inputs": {"image": [load_nid, 0], "alpha": [load_nid, 1]},
                }
                labels[join_nid] = f"准备参考图 #{idx + 1} 通道" if len(names) > 1 else "准备参考图通道"
                enc_inputs[f"images.image_{idx + 1}"] = [join_nid, 0]

        graph["25"] = {"class_type": "TextEncodeQwenImage21", "inputs": enc_inputs}
        labels["25"] = "编码提示词" + (f"与 {len(names)} 张参考图" if len(names) > 1 else "与参考图" if has_ref else "")

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
            graph["23"] = {"class_type": "LoadImage", "inputs": {"image": primary_ref}}
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
            graph["23"] = {"class_type": "LoadImage", "inputs": {"image": primary_ref}}
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

    ref_names: list[str] = []
    ref_paths = _load_ref_paths(job)
    if ref_paths:
        inp_dir = COMFY_DIR / "input"
        inp_dir.mkdir(parents=True, exist_ok=True)
        ts_tag = int(time.time() * 1000) % 1000000
        sizes: list[str] = []
        for idx, rp in enumerate(ref_paths):
            img = Image.open(rp)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            rname = f"colab_ref_{ts_tag}_{idx}.png"
            img.save(inp_dir / rname, format="PNG")
            ref_names.append(rname)
            sizes.append(str(img.size))
        print(f"启用 ComfyUI 参考图编辑（{len(ref_names)} 张）：{', '.join(sizes)}", flush=True)

    _ensure_comfy_server(vram_gb)

    graph, labels = _build_comfy_prompt(
        job,
        {"diffusion": diff_name, "text_encoder": te_name, "vae": vae_name, "loras": lora_files},
        has_ref=bool(ref_names),
        ref_image_name=ref_names[0] if ref_names else "colab_ref.png",
        ref_image_names=ref_names,
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
