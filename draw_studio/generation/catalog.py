"""Models, GPU choices, built-in presets, defaults and limits exposed by /api/config."""


QUEUE_MAX = 12
RECENT_MODELS_MAX = 16
COMFY_PRESETS_MAX = 32
STUDIO_PRESETS_MAX = 32


STUDIO_BUILTIN_PRESETS = [
    {
        "id": "builtin:img-portrait-qwen",
        "builtin": True,
        "name": "写实人像 2:3 · Qwen BF16",
        "mode": "image",
        "engine": "diffusers",
        "model": "qwen-2.1-bf16",
        "gpu": "A100",
        "width": 768,
        "height": 1152,
        "steps": 35,
        "cfg": 5.0,
        "hint": "人像/角色立绘默认最佳比例与步数",
    },
    {
        "id": "builtin:img-cinematic-169",
        "builtin": True,
        "name": "电影分镜 16:9 · 关键帧",
        "mode": "image",
        "engine": "diffusers",
        "model": "qwen-2.1-bf16",
        "gpu": "A100",
        "width": 1280,
        "height": 768,
        "steps": 35,
        "cfg": 5.0,
        "hint": "对齐 MiniMax-H3 横屏视频比例，出图可直接转首帧",
    },
    {
        "id": "builtin:img-hd-portrait",
        "builtin": True,
        "name": "高清精绘 2:3 · 1024×1536",
        "mode": "image",
        "engine": "diffusers",
        "model": "qwen-2.1-bf16",
        "gpu": "A100",
        "width": 1024,
        "height": 1536,
        "steps": 40,
        "cfg": 5.0,
        "hint": "1.57 MP 高细节精绘",
    },
    {
        "id": "builtin:img-flux2-square",
        "builtin": True,
        "name": "FLUX.2 [dev] · 1:1 精绘",
        "mode": "image",
        "engine": "diffusers",
        "model": "flux2-dev",
        "gpu": "H100",
        "width": 1024,
        "height": 1024,
        "steps": 28,
        "cfg": 3.5,
        "hint": "32B 满血模型，推荐 H100 / G4",
    },
    {
        "id": "builtin:vid-h3-fl2va-5s",
        "builtin": True,
        "name": "H3 首帧动态 · 5.2s 电影感",
        "mode": "video",
        "workflow": "fl2va",
        "gpu": "H100",
        "width": 1280,
        "height": 768,
        "num_frames": 124,
        "steps": 30,
        "cfg": 5.0,
        "auto_offload": True,
        "hint": "单张关键帧驱动 5.2 秒音画同步镜头",
    },
    {
        "id": "builtin:vid-h3-ref2va-7s",
        "builtin": True,
        "name": "H3 多图角色参考 · 7.5s",
        "mode": "video",
        "workflow": "ref2va",
        "gpu": "H100",
        "width": 1280,
        "height": 768,
        "num_frames": 180,
        "steps": 30,
        "cfg": 5.0,
        "auto_offload": True,
        "hint": "锁定多张人设/场景图保持角色一致性",
    },
]

COMFY_TEMPLATES = [
    {
        "id": "qwen-image-2.1",
        "label": "Qwen-Image 2.1（文生图 / 修图）",
        "clip_type": "qwen_image",
        "defaults": {
            "diffusion": "https://huggingface.co/chatrlabs/Qwen-Image-2.1-Uncensored-Omni-Quantized/blob/main/qwen-image-2.1-step90000-BF16/diffusion_pytorch_model.safetensors",
            "text_encoder": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/text_encoders/qwen3vl_8b_bf16.safetensors",
            "vae": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/vae/qwen_image_2.1_vae_bf16.safetensors",
            "sampler": "euler",
            "scheduler": "simple",
            "steps": 35,
            "cfg": 5.0,
            "width": 1024,
            "height": 1536,
        },
    },
    {
        "id": "flux",
        "label": "FLUX（单文本编码器 + UNET + VAE）",
        "clip_type": "flux",
        "defaults": {
            "diffusion": "",
            "text_encoder": "",
            "vae": "",
            "sampler": "euler",
            "scheduler": "simple",
            "steps": 28,
            "cfg": 3.5,
            "width": 1024,
            "height": 1024,
        },
    },
    {
        "id": "sd-generic",
        "label": "通用三件套（UNET + CLIP + VAE）",
        "clip_type": "stable_diffusion",
        "defaults": {
            "diffusion": "",
            "text_encoder": "",
            "vae": "",
            "sampler": "euler",
            "scheduler": "normal",
            "steps": 28,
            "cfg": 5.0,
            "width": 1024,
            "height": 1024,
        },
    },
]
COMFY_SAMPLERS = [
    "euler",
    "er_sde",
    "euler_ancestral",
    "dpmpp_2m",
    "dpmpp_2m_sde",
    "dpmpp_3m_sde",
    "uni_pc",
    "heun",
    "res_multistep",
]
COMFY_SCHEDULERS = [
    "simple",
    "normal",
    "karras",
    "exponential",
    "sgm_uniform",
    "beta",
    "ddim_uniform",
]
COMFY_CLIP_TYPES = [
    "qwen_image",
    "flux",
    "flux2",
    "sd3",
    "stable_diffusion",
    "lumina2",
    "wan",
    "chroma",
    "hidream",
]
COMFY_BUILTIN_PRESETS = [
    {
        "id": "builtin:omni-bf16-35",
        "builtin": True,
        "name": "Omni BF16 · 35步精细",
        "template": "qwen-image-2.1",
        "diffusion": "https://huggingface.co/chatrlabs/Qwen-Image-2.1-Uncensored-Omni-Quantized/blob/main/qwen-image-2.1-step90000-BF16/diffusion_pytorch_model.safetensors",
        "text_encoder": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/text_encoders/qwen3vl_8b_bf16.safetensors",
        "vae": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/vae/qwen_image_2.1_vae_bf16.safetensors",
        "loras": [],
        "sampler": "euler",
        "scheduler": "simple",
        "steps": 35,
        "cfg": 5.0,
        "width": 1024,
        "height": 1536,
    },
    {
        "id": "builtin:omni-nvfp4-35",
        "builtin": True,
        "name": "Omni NVFP4 · Blackwell 极速",
        "template": "qwen-image-2.1",
        "diffusion": "https://huggingface.co/chatrlabs/Qwen-Image-2.1-Uncensored-Omni-Quantized/blob/main/qwen-image-2.1-step90000-NVFP4-comfy.safetensors",
        "text_encoder": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/text_encoders/qwen3vl_8b_bf16.safetensors",
        "vae": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/vae/qwen_image_2.1_vae_bf16.safetensors",
        "loras": [],
        "sampler": "euler",
        "scheduler": "simple",
        "steps": 35,
        "cfg": 5.0,
        "width": 1024,
        "height": 1536,
    },
    {
        "id": "builtin:omni-bf16-turbo8",
        "builtin": True,
        "name": "Omni BF16 + Turbo · 8步加速",
        "template": "qwen-image-2.1",
        "diffusion": "https://huggingface.co/chatrlabs/Qwen-Image-2.1-Uncensored-Omni-Quantized/blob/main/qwen-image-2.1-step90000-BF16/diffusion_pytorch_model.safetensors",
        "text_encoder": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/text_encoders/qwen3vl_8b_bf16.safetensors",
        "vae": "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/vae/qwen_image_2.1_vae_bf16.safetensors",
        "loras": [
            {
                "repo_id": "chatrlabs/Qwen-Image-2.1-Uncensored-Omni-LoRA-v0.1",
                "weight_name": "chatrlabs-omni-turbo-8step-fp32.safetensors",
                "scale": 1.0,
            }
        ],
        "sampler": "euler",
        "scheduler": "simple",
        "steps": 8,
        "cfg": 1.0,
        "width": 1024,
        "height": 1536,
    },
]


GPUS = [
    {"id": "A100", "label": "A100", "hint": "推荐，生图/视频主力"},
    {"id": "H100", "label": "H100", "hint": "高算力，适合 FLUX.2 / 视频"},
    {"id": "G4", "label": "G4 · RTX PRO 6000", "hint": "大显存新卡，适合视频"},
    {"id": "L4", "label": "L4", "hint": "适合 Q5 量化生图"},
    {"id": "T4", "label": "T4", "hint": "仅轻量测试"},
]
IMAGE_MODELS = [
    {"id": "qwen-2.1-bf16", "label": "Qwen-Image-2.1 · BF16", "hint": "满血 ~33GB，支持参考图改图"},
    {"id": "qwen-2.1-q5", "label": "Qwen-Image-2.1 · Q5 GGUF", "hint": "~23GB，L4 可跑，可换自定义 GGUF"},
    {"id": "flux2-dev", "label": "FLUX.2 [dev] · 32B", "hint": "~70GB，建议 H100 / G4"},
]
VIDEO_WORKFLOWS = [
    {"id": "t2va", "label": "文生视频 + 音频", "needs": []},
    {"id": "fl2va", "label": "首帧 / 首尾帧生视频 + 音频", "needs": ["first"]},
    {"id": "ref2va", "label": "参考图生视频 + 音频", "needs": ["first"]},
]
VIDEO_OFFLOAD_MODES = [
    {"id": "auto", "label": "自动", "hint": "按显存自动选择组件级或逐层卸载"},
    {"id": "component", "label": "组件级", "hint": "适合 H100 / G4"},
    {"id": "group", "label": "逐层", "hint": "无损 BF16，适配 A100 / L4"},
    {"id": "none", "label": "关闭", "hint": "全常驻显存"},
]


LIMITS = {
    "size_min": 512, "size_max": 1536, "size_step": 64,
    "steps_min": 2, "steps_max": 60,
    "cfg_min": 1.0, "cfg_max": 12.0,
    "frames_min": 120, "frames_max": 360,
    "count_max": 4, "loras_max": 4, "lora_scale_max": 2.5, "refs_max": 6,
    "idle_minutes_min": 5, "idle_minutes_max": 60,
    "poll_rounds_min": 1, "poll_rounds_max": 10,
    "prompt_max": 12000, "negative_max": 1200, "upload_max_mb": 12,
    "queue_max": QUEUE_MAX,
}
DEFAULTS = {
    "image": {"width": 768, "height": 1152, "steps": 35, "cfg": 5.0, "model": "qwen-2.1-bf16"},
    "video": {"width": 1280, "height": 768, "steps": 30, "cfg": 5.0, "num_frames": 124, "workflow": "t2va", "offload_mode": "auto"},
    "gpu": "A100",
    "gpu_pool": ["A100"],
    "poll_rounds": 2,
    "poll_all_proxies": False,
    "idle_minutes": 10,
}
