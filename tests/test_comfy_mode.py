#!/usr/bin/env python3
"""Unit tests for ComfyUI mode: link parsing, job normalization, preset persistence, and workflow graph building."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from draw_studio.colab import worker
from draw_studio.gallery import Store
from draw_studio.generation.parameters import normalize_job, parse_model_link
from draw_studio.generation.studio import Studio
from draw_studio.logs import LogBuffer


class DummyColab:
    def has_credentials(self):
        return False

    def status_report(self, force=False, blocking=False):
        return {"authed": False, "eligible_gpus": [], "gpu_health": {}}


def test_parse_model_link():
    u1 = "https://huggingface.co/chatrlabs/Qwen-Image-2.1-Uncensored-Omni-Quantized/blob/main/qwen-image-2.1-step90000-BF16/diffusion_pytorch_model.safetensors"
    s1 = parse_model_link(u1, "扩散模型")
    assert s1["source"] == "hf"
    assert s1["repo_id"] == "chatrlabs/Qwen-Image-2.1-Uncensored-Omni-Quantized"
    assert s1["filename"] == "qwen-image-2.1-step90000-BF16/diffusion_pytorch_model.safetensors"
    assert s1["format"] == "BF16"
    assert s1["basename"] == "diffusion_pytorch_model.safetensors"

    u2 = "https://huggingface.co/chatrlabs/Qwen-Image-2.1-Uncensored-Omni-Quantized/resolve/main/qwen-image-2.1-step90000-NVFP4-comfy.safetensors?download=true"
    s2 = parse_model_link(u2)
    assert s2["format"] == "NVFP4"
    assert s2["filename"] == "qwen-image-2.1-step90000-NVFP4-comfy.safetensors"

    u3 = "Comfy-Org/Qwen-Image-2.1 :: text_encoders/qwen3vl_8b_bf16.safetensors"
    s3 = parse_model_link(u3)
    assert s3["repo_id"] == "Comfy-Org/Qwen-Image-2.1"
    assert s3["filename"] == "text_encoders/qwen3vl_8b_bf16.safetensors"

    u4 = "Comfy-Org/Qwen-Image-2.1/vae/qwen_image_2.1_vae_bf16.safetensors"
    s4 = parse_model_link(u4)
    assert s4["repo_id"] == "Comfy-Org/Qwen-Image-2.1"
    assert s4["filename"] == "vae/qwen_image_2.1_vae_bf16.safetensors"

    u5 = "https://example.com/weights/custom-q5.gguf"
    s5 = parse_model_link(u5)
    assert s5["source"] == "url"
    assert s5["ext"] == ".gguf"

    # Reject bad inputs
    for bad in [
        "",
        "file:///etc/passwd.safetensors",
        "owner/repo :: ../secret.safetensors",
        "https://huggingface.co/owner/repo/blob/main/README.md",
        "https://huggingface.co/owner/repo",
    ]:
        try:
            parse_model_link(bad)
            raise AssertionError(f"Expected ValueError for {bad!r}")
        except ValueError:
            pass


def test_normalize_job_comfy_and_loras():
    j = normalize_job({
        "mode": "image",
        "engine": "comfyui",
        "gpu": "G4",
        "prompt": "a portrait in warm sunlight",
        "width": 1024,
        "height": 1536,
        "steps": 8,
        "cfg": 1.0,
        "comfy": {
            "template": "qwen-image-2.1",
            "diffusion": "https://huggingface.co/chatrlabs/Qwen-Image-2.1-Uncensored-Omni-Quantized/blob/main/qwen-image-2.1-step90000-NVFP4-comfy.safetensors",
            "text_encoder": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/text_encoders/qwen3vl_8b_bf16.safetensors",
            "vae": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/vae/qwen_image_2.1_vae_bf16.safetensors",
            "sampler": "euler",
            "scheduler": "simple",
        },
        "loras": [
            {
                "repo_id": "https://huggingface.co/chatrlabs/Qwen-Image-2.1-Uncensored-Omni-LoRA-v0.1/blob/main/chatrlabs-omni-turbo-8step-fp32.safetensors",
                "scale": 1.0,
            }
        ],
    })
    assert j["engine"] == "comfyui"
    assert j["comfy"]["diffusion"]["format"] == "NVFP4"
    assert j["loras"][0]["repo_id"] == "chatrlabs/Qwen-Image-2.1-Uncensored-Omni-LoRA-v0.1"
    assert j["loras"][0]["weight_name"] == "chatrlabs-omni-turbo-8step-fp32.safetensors"

    # Backward-compatible diffusers job still works identically
    j2 = normalize_job({"mode": "image", "prompt": "hello"})
    assert j2["engine"] == "diffusers"
    assert j2["model"] == "qwen-2.1-bf16"


def test_comfy_presets_persistence():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        log = LogBuffer()
        store = Store(root / "out", log)
        studio = Studio(root, {}, DummyColab(), store, log, 600)

        saved, all_p = studio.save_comfy_preset({
            "name": "测试组合 NVFP4",
            "template": "qwen-image-2.1",
            "diffusion": "https://huggingface.co/chatrlabs/Qwen-Image-2.1-Uncensored-Omni-Quantized/blob/main/qwen-image-2.1-step90000-NVFP4-comfy.safetensors",
            "text_encoder": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/text_encoders/qwen3vl_8b_bf16.safetensors",
            "vae": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/vae/qwen_image_2.1_vae_bf16.safetensors",
            "sampler": "euler",
            "scheduler": "simple",
            "steps": 35,
            "cfg": 5.0,
            "width": 1024,
            "height": 1536,
        })
        assert len(all_p) == 1
        pid = saved["id"]

        # Recover into a fresh Studio instance
        studio2 = Studio(root, {}, DummyColab(), store, log, 600)
        studio2.recover()
        assert len(studio2.comfy_presets()) == 1
        assert studio2.comfy_presets()[0]["id"] == pid

        removed, after = studio2.delete_comfy_preset(pid)
        assert removed and after == []


def test_build_comfy_prompt_graphs():
    base_job = normalize_job({
        "mode": "image",
        "engine": "comfyui",
        "prompt": "a smiling girl",
        "negative": "blurry",
        "width": 1024,
        "height": 1536,
        "steps": 8,
        "cfg": 1.0,
        "seed": 12345,
        "comfy": {
            "template": "qwen-image-2.1",
            "diffusion": "chatrlabs/Qwen-Image-2.1-Uncensored-Omni-Quantized :: qwen-image-2.1-step90000-BF16/diffusion_pytorch_model.safetensors",
            "text_encoder": "Comfy-Org/Qwen-Image-2.1 :: text_encoders/qwen3vl_8b_bf16.safetensors",
            "vae": "Comfy-Org/Qwen-Image-2.1 :: vae/qwen_image_2.1_vae_bf16.safetensors",
        },
    })
    files = {
        "diffusion": "diff.safetensors",
        "text_encoder": "te.safetensors",
        "vae": "vae.safetensors",
        "loras": [{"filename": "turbo.safetensors", "scale": 1.0}],
    }
    # 1. Qwen-Image 2.1 t2i + Turbo LoRA
    g, _ = worker._build_comfy_prompt(base_job, files, has_ref=False)
    assert g["1"]["class_type"] == "UNETLoader"
    assert g["2"]["inputs"]["type"] == "qwen_image"
    assert g["10"]["class_type"] == "LoraLoaderModelOnly"
    assert g["20"]["class_type"] == "QwenImage21Cache"
    assert g["20"]["inputs"]["model"] == ["10", 0]
    assert g["25"]["class_type"] == "TextEncodeQwenImage21"
    assert "images.image_1" not in g["25"]["inputs"]
    assert g["26"]["inputs"]["steps"] == 8 and g["26"]["inputs"]["cfg"] == 1.0

    # 2. Qwen-Image 2.1 i2i + GGUF
    files_gguf = dict(files, diffusion="model.gguf", loras=[])
    g2, _ = worker._build_comfy_prompt(base_job, files_gguf, has_ref=True, ref_image_name="ref1.png")
    assert g2["1"]["class_type"] == "UnetLoaderGGUF"
    assert g2["23"]["class_type"] == "LoadImage"
    assert g2["24"]["class_type"] == "JoinImageWithAlpha"
    assert g2["25"]["inputs"]["images.image_1"] == ["24", 0]
    assert g2["25"]["inputs"]["vae"] == ["3", 0]

    # 2b. Qwen-Image 2.1 multi-ref i2i (3 images -> images.image_1..3)
    g_multi, _ = worker._build_comfy_prompt(
        base_job,
        files_gguf,
        has_ref=True,
        ref_image_names=["r0.png", "r1.png", "r2.png"],
    )
    assert g_multi["25"]["inputs"]["images.image_1"] == ["24", 0]
    assert g_multi["25"]["inputs"]["images.image_2"] == ["33", 0]
    assert g_multi["25"]["inputs"]["images.image_3"] == ["35", 0]
    assert g_multi["32"]["inputs"]["image"] == "r1.png"
    assert g_multi["34"]["inputs"]["image"] == "r2.png"

    # 3. Flux & sd-generic templates
    for tpl in ("flux", "sd-generic"):
        j_tpl = json.loads(json.dumps(base_job))
        j_tpl["comfy"]["template"] = tpl
        gt, _ = worker._build_comfy_prompt(j_tpl, files, has_ref=False)
        assert gt["26"]["class_type"] == "KSampler"
        assert gt["27"]["class_type"] == "VAEDecode"
        assert gt["28"]["class_type"] == "SaveImage"


def test_minimax_h3_comfy_lora_conversion():
    class TinyArr:
        """Minimal array wrapper so unit tests run with zero numpy/torch dependency."""

        def __init__(self, rows: list[list[float]]):
            self.rows = rows
            self.shape = (len(rows), len(rows[0]) if rows else 0)

        def __getitem__(self, slc):
            return TinyArr(self.rows[slc])

        def __mul__(self, scalar: float):
            return TinyArr([[x * scalar for x in r] for r in self.rows])

    orig_cat = worker._cat_dim0
    worker._cat_dim0 = lambda parts: TinyArr([r for p in parts for r in p.rows])
    try:
        sd = {
            "diffusion_model.audio_patch_proj.lora_A.weight": TinyArr([[1.0] * 4 for _ in range(2)]),
            "diffusion_model.audio_patch_proj.lora_B.weight": TinyArr([[2.0, 3.0] for _ in range(6)]),
            "diffusion_model.final_layer.audio_out.lora_A.weight": TinyArr([[1.0] * 6 for _ in range(2)]),
            "diffusion_model.final_layer.audio_out.lora_B.weight": TinyArr([[4.0, 5.0] for _ in range(4)]),
            "diffusion_model.blocks.0.attn.qkv_proj.lora_A.weight": TinyArr([[1.0] * 4 for _ in range(2)]),
            "diffusion_model.blocks.0.attn.qkv_proj.lora_B.weight": TinyArr(
                [[10.0, 10.0], [11.0, 11.0], [20.0, 20.0], [21.0, 21.0], [30.0, 30.0], [31.0, 31.0]]
            ),
            "diffusion_model.blocks.0.attn.out_proj.lora_A.weight": TinyArr([[1.0] * 4 for _ in range(2)]),
            "diffusion_model.blocks.0.attn.out_proj.lora_B.weight": TinyArr([[7.0, 8.0] for _ in range(4)]),
            "diffusion_model.blocks.0.mlp.fc1.lora_A.weight": TinyArr([[1.0] * 4 for _ in range(2)]),
            "diffusion_model.blocks.0.mlp.fc1.lora_B.weight": TinyArr(
                [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0], [4.0, 4.0]]  # [gate; value]
            ),
            "diffusion_model.blocks.0.mlp.fc2.lora_A.weight": TinyArr([[1.0] * 4 for _ in range(2)]),
            "diffusion_model.blocks.0.mlp.fc2.lora_B.weight": TinyArr([[9.0, 9.0] for _ in range(4)]),
            "diffusion_model.token_refiner.blocks.1.attn.qkv_proj.lora_A.weight": TinyArr([[1.0] * 4 for _ in range(2)]),
            "diffusion_model.token_refiner.blocks.1.attn.qkv_proj.lora_B.weight": TinyArr(
                [[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]]
            ),
        }
        assert worker._is_minimax_h3_comfy_lora(sd.keys()) is True
        conv = worker._convert_minimax_h3_comfy_lora(sd)
        assert conv["transformer.audio_proj_in.lora_A.weight"].shape == (2, 4)
        assert conv["transformer.audio_proj_out.lora_B.weight"].shape == (4, 2)
        # QKV split exact check
        assert conv["transformer.transformer_blocks.0.attn.to_q.lora_B.weight"].rows == [[10.0, 10.0], [11.0, 11.0]]
        assert conv["transformer.transformer_blocks.0.attn.to_k.lora_B.weight"].rows == [[20.0, 20.0], [21.0, 21.0]]
        assert conv["transformer.transformer_blocks.0.attn.to_v.lora_B.weight"].rows == [[30.0, 30.0], [31.0, 31.0]]
        assert conv["transformer.transformer_blocks.0.attn.to_out.0.lora_B.weight"].shape == (4, 2)
        # SwiGLU [gate; value] -> [value; gate] exact swap check
        assert conv["transformer.transformer_blocks.0.ff.net.0.proj.lora_B.weight"].rows == [
            [3.0, 3.0], [4.0, 4.0], [1.0, 1.0], [2.0, 2.0]
        ]
        assert conv["transformer.transformer_blocks.0.ff.net.2.lora_B.weight"].shape == (4, 2)
        assert conv["transformer.token_refiner.refiner_blocks.1.attn.to_k.lora_B.weight"].rows == [[2.0, 0.0]]
    finally:
        worker._cat_dim0 = orig_cat


if __name__ == "__main__":
    test_parse_model_link()
    test_normalize_job_comfy_and_loras()
    test_comfy_presets_persistence()
    test_build_comfy_prompt_graphs()
    test_minimax_h3_comfy_lora_conversion()
    print("ALL_COMFY_UNIT_TESTS_PASSED")
