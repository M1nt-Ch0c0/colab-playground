#!/usr/bin/env python3
"""Composable Long-Video Agent Workflow Engine for Colab Studio.

Drives multi-step AI pipelines directly atop Studio's existing CPA LLM, Image Gen
(Diffusers / ComfyUI), MiniMax-H3 Video Gen, and FFmpeg stitching — without
mutating the user's interactive Tab 1/2 reference slots.

Persistence layout (under ``<root>/workflows``):
    definitions.json           user-saved custom workflow definitions
    runs/<run_id>/run.json     run state, step configs, outputs, logs
    runs/<run_id>/assets/*     uploaded sheets, web-fetched refs, stitched temp files
"""

from __future__ import annotations

import copy
import html
import ipaddress
import json
import os
import random
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

from jobs import DEFAULTS, GPUS, LIMITS, VIDEO_WORKFLOWS, normalize_job
from store import Store, probe_image_dimensions

WORKFLOWS_MAX = 40
RUNS_MAX = 40
STEPS_MAX = 16
MAX_WEB_HTML_BYTES = 2 * 1024 * 1024
MAX_WEB_IMAGE_BYTES = 12 * 1024 * 1024
ASSET_NAME_RE = re.compile(r"[A-Za-z0-9._-]{1,120}")
WF_ID_RE = re.compile(r"(?:builtin:|wf_)[A-Za-z0-9._-]{2,64}")
RUN_ID_RE = re.compile(r"wr_[A-Za-z0-9_-]{4,48}")
STEP_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,48}")
VAR_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")

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
        "hint": "调用 CPA 大模型撰写结构化分镜脚本（每镜含检索词、关键帧描述、视频动作与声音）",
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
STEP_TYPES = {s["type"] for s in STEP_CATALOG}


BUILTIN_WORKFLOWS: list[dict[str, Any]] = [
    {
        "id": "builtin:agent-long-video",
        "builtin": True,
        "name": "完整长视频 Agent 流水线（白模找图 + 人设融合）",
        "description": (
            "人设图资产 → AI 写分镜脚本 → 轻量网页 Agent 搜索/抓取白模参考图到本地 → "
            "白模 + 人设融合生关键帧（暂停审核）→ 多模态写 H3 提示词 → 逐镜生成音画视频 → FFmpeg 剪辑合成成品。"
        ),
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
                    "note": "上传主角人设图（可不传，仅靠白模或纯文生图）",
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
        "name": "极速多镜故事短片（4 步直出）",
        "description": "跳过网页找图：人设图 → AI 分镜 → 批量关键帧 → H3 提示词 → 逐镜生视频 → FFmpeg 拼片。",
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
        "name": "角色多景别设定集（找参考 + 批量出图）",
        "description": "上传人设图 + 网页找姿态/服装参考 → AI 扩展 4 组景别提示词 → 批量生图（纯图片工作流）。",
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


# ── SSRF-safe web fetch & HTML image extraction ──────────────────────────


def _is_forbidden_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str.strip("[]"))
    except ValueError:
        return True
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_forbidden_ip(str(ip.ipv4_mapped))
    return False


def validate_public_url(raw_url: str, *, resolve_dns: bool = True) -> str:
    """Validate that a URL is public HTTP(S) and does not point to internal/private networks."""
    url = str(raw_url or "").strip()
    if not url or len(url) > 2048 or any(ch in url for ch in ("\r", "\n", "\t")):
        raise ValueError("URL 格式无效")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("仅支持 http:// 或 https:// 公开链接")
    host = parsed.hostname.lower().strip(".")
    if host in {"localhost", "localhost.localdomain", "host.docker.internal", "gateway.docker.internal"} or host.endswith(
        (".local", ".internal", ".localhost")
    ):
        raise ValueError(f"安全拦截：禁止访问本地或内网地址 ({host})")
    # Check if host is a literal IP
    try:
        ipaddress.ip_address(host.strip("[]"))
        is_literal_ip = True
    except ValueError:
        is_literal_ip = False
    if is_literal_ip and _is_forbidden_ip(host):
        raise ValueError(f"安全拦截：禁止访问内网/回环 IP ({host})")
    if resolve_dns:
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError(f"无法解析域名 {host}：{exc}") from exc
        if not infos:
            raise ValueError(f"域名 {host} 无有效解析记录")
        for info in infos:
            addr = info[4][0]
            if _is_forbidden_ip(addr):
                raise ValueError(f"安全拦截：{host} 解析到受限地址 ({addr})")
    return url


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        joined = urllib.parse.urljoin(req.full_url, newurl)
        validate_public_url(joined, resolve_dns=True)
        return super().redirect_request(req, fp, code, msg, headers, joined)


def _fetch_public_bytes(url: str, *, max_bytes: int, timeout: int = 25, accept: str = "*/*") -> tuple[bytes, str, str]:
    clean = validate_public_url(url, resolve_dns=True)
    req = urllib.request.Request(
        clean,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ColabStudioAgent/3.0; +https://draw.m1ntch0c0.com)",
            "Accept": accept,
        },
    )
    opener = urllib.request.build_opener(_SafeRedirectHandler())
    with opener.open(req, timeout=timeout) as resp:
        final_url = resp.geturl()
        validate_public_url(final_url, resolve_dns=False)
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"远端文件超过限制（>{max_bytes // 1048576} MB）")
            chunks.append(chunk)
    return b"".join(chunks), ctype, final_url


def _image_magic_ext(data: bytes) -> str | None:
    if len(data) < 32:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8"):
        return ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return None


class _PageImageExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self.text_parts: list[str] = []
        self.images: list[dict[str, str]] = []
        self._seen_urls: set[str] = set()

    def _add_image(self, raw_url: str, alt: str = "", source: str = "img") -> None:
        u = str(raw_url or "").strip()
        if not u or u.startswith(("data:", "javascript:", "blob:")):
            return
        full = urllib.parse.urljoin(self.base_url, u)
        low = full.lower()
        if not low.startswith(("http://", "https://")):
            return
        if any(bad in low for bad in (".svg", ".ico", "favicon", "sprite", "1x1", "pixel.gif", "blank.gif")):
            return
        if full in self._seen_urls:
            return
        self._seen_urls.add(full)
        self.images.append({"url": full, "alt": (alt or "").strip()[:160], "source": source})

    @staticmethod
    def _best_from_srcset(srcset: str) -> str:
        best_url, best_w = "", -1
        for part in srcset.split(","):
            tokens = part.strip().split()
            if not tokens:
                continue
            u = tokens[0]
            w = 0
            if len(tokens) > 1 and tokens[1].endswith("w"):
                try:
                    w = int(tokens[1][:-1])
                except ValueError:
                    w = 0
            if w >= best_w:
                best_w = w
                best_url = u
        return best_url

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        ad = {k.lower(): (v or "") for k, v in attrs}
        if t in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if t == "title":
            self._in_title = True
        elif t == "meta":
            prop = (ad.get("property") or ad.get("name") or "").lower()
            if prop in {"og:image", "twitter:image", "twitter:image:src"} and ad.get("content"):
                self._add_image(ad["content"], alt=self.title or prop, source="meta")
        elif t == "img":
            alt = ad.get("alt") or ad.get("title") or ""
            src = (
                ad.get("data-original")
                or ad.get("data-src")
                or ad.get("data-lazy-src")
                or self._best_from_srcset(ad.get("srcset") or "")
                or ad.get("src")
                or ""
            )
            self._add_image(src, alt=alt, source="img")
        elif t == "a":
            href = ad.get("href") or ""
            if re.search(r"\.(?:png|jpe?g|webp)(?:\?|$)", href, re.I):
                self._add_image(href, alt=ad.get("title") or "", source="link")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1
        elif t == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        txt = " ".join(data.split())
        if not txt:
            return
        if self._in_title:
            self.title = (self.title + " " + txt).strip()[:200]
        elif len(self.text_parts) < 120:
            self.text_parts.append(txt[:200])


def _search_wikimedia_images(query: str, limit: int = 10) -> list[dict[str, str]]:
    """Query Wikimedia Commons public API (no API key, no CAPTCHA, reliable thumbnails)."""
    q = str(query or "").strip()
    if not q:
        return []
    params = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",  # File:
        "gsrsearch": f"{q} filetype:bitmap",
        "gsrlimit": str(max(4, min(20, limit))),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1280",
    })
    url = f"https://commons.wikimedia.org/w/api.php?{params}"
    raw, _, _ = _fetch_public_bytes(url, max_bytes=MAX_WEB_HTML_BYTES, timeout=25, accept="application/json")
    data = json.loads(raw.decode("utf-8", errors="replace"))
    pages = (data.get("query") or {}).get("pages") or {}
    out: list[dict[str, str]] = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        ii = infos[0]
        mime = str(ii.get("mime") or "").lower()
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        img_url = str(ii.get("thumburl") or ii.get("url") or "").strip()
        if not img_url:
            continue
        title = str(page.get("title") or "").replace("File:", "").strip()
        desc = ""
        ext = ii.get("extmetadata") or {}
        if isinstance(ext.get("ImageDescription"), dict):
            desc = re.sub(r"<[^>]+>", " ", str(ext["ImageDescription"].get("value") or ""))
            desc = html.unescape(" ".join(desc.split()))[:180]
        out.append({
            "url": img_url,
            "alt": f"{title} — {desc}".strip(" —")[:200],
            "page_url": str(ii.get("descriptionurl") or url),
            "source": "wikimedia",
        })
    return out


# ── FFmpeg helpers ───────────────────────────────────────────────────────


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _probe_video_info(path: Path) -> tuple[float, bool]:
    """Return (duration_seconds, has_audio) using ffprobe (or safe defaults)."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 5.0, True
    try:
        proc = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-show_entries", "format=duration:stream=codec_type",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=20,
        )
        if proc.returncode != 0:
            return 5.0, True
        info = json.loads(proc.stdout or "{}")
        dur = float((info.get("format") or {}).get("duration") or 5.0)
        streams = info.get("streams") or []
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        return max(0.2, dur), has_audio
    except Exception:
        return 5.0, True


def stitch_videos(
    clip_paths: list[Path],
    out_mp4: Path,
    out_thumb: Path | None = None,
    *,
    target_width: int = 1280,
    target_height: int = 768,
    fps: int = 24,
    transition: str = "fade",
    fade_s: float = 0.35,
) -> dict[str, Any]:
    """Normalize and stitch MP4 clips via FFmpeg (supports hard cut or smooth xfade + acrossfade)."""
    if not clip_paths:
        raise ValueError("没有可拼接的视频片段")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("当前环境未安装 ffmpeg，无法合成长视频（Docker 镜像已内置 ffmpeg）")

    w = max(256, int(target_width // 2 * 2))
    h = max(256, int(target_height // 2 * 2))
    fps = max(12, min(60, int(fps or 24)))
    trans = "cut" if transition == "cut" else "fade"
    fade = max(0.1, min(1.5, float(fade_s or 0.35)))

    with tempfile.TemporaryDirectory(prefix="qp-stitch-") as tmp:
        tmp_dir = Path(tmp)
        norm_clips: list[tuple[Path, float]] = []
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"fps={fps},format=yuv420p,setsar=1"
        )
        for idx, src in enumerate(clip_paths):
            if not src.exists():
                raise ValueError(f"视频片段不存在：{src.name}")
            dur, has_audio = _probe_video_info(src)
            norm = tmp_dir / f"norm_{idx:03d}.mp4"
            if has_audio:
                cmd = [
                    ffmpeg, "-y", "-i", str(src),
                    "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                    "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                    "-movflags", "+faststart", str(norm),
                ]
            else:
                cmd = [
                    ffmpeg, "-y", "-i", str(src),
                    "-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                    "-shortest",
                    "-vf", vf,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                    "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                    "-movflags", "+faststart", str(norm),
                ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg 标准化片段 #{idx + 1} 失败：{proc.stderr[-300:]}")
            ndur, _ = _probe_video_info(norm)
            norm_clips.append((norm, ndur))

        if len(norm_clips) == 1:
            shutil.copyfile(norm_clips[0][0], out_mp4)
            total_dur = norm_clips[0][1]
        elif trans == "cut" or any(d <= fade * 2.2 for _, d in norm_clips):
            lst = tmp_dir / "concat.txt"
            lst.write_text(
                "\n".join(f"file '{p.as_posix()}'" for p, _ in norm_clips) + "\n",
                encoding="utf-8",
            )
            cmd = [
                ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                "-c", "copy", "-movflags", "+faststart", str(out_mp4),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg 拼接失败：{proc.stderr[-300:]}")
            total_dur = sum(d for _, d in norm_clips)
            trans = "cut"
        else:
            cmd = [ffmpeg, "-y"]
            for p, _ in norm_clips:
                cmd.extend(["-i", str(p)])
            v_filters: list[str] = []
            a_filters: list[str] = []
            prev_v = "0:v"
            prev_a = "0:a"
            acc_dur = norm_clips[0][1]
            for idx in range(1, len(norm_clips)):
                offset = max(0.05, acc_dur - fade)
                out_v = f"v{idx}"
                out_a = f"a{idx}"
                v_filters.append(
                    f"[{prev_v}][{idx}:v]xfade=transition=fade:duration={fade:.3f}:offset={offset:.3f}[{out_v}]"
                )
                a_filters.append(f"[{prev_a}][{idx}:a]acrossfade=d={fade:.3f}:c1=tri:c2=tri[{out_a}]")
                prev_v = out_v
                prev_a = out_a
                acc_dur = acc_dur + norm_clips[idx][1] - fade
            fc = ";".join(v_filters + a_filters)
            cmd.extend([
                "-filter_complex", fc,
                "-map", f"[{prev_v}]", "-map", f"[{prev_a}]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                "-movflags", "+faststart", str(out_mp4),
            ])
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg 淡入淡出合成失败：{proc.stderr[-300:]}")
            total_dur = acc_dur

        if out_thumb is not None:
            subprocess.run(
                [
                    ffmpeg, "-y", "-i", str(out_mp4),
                    "-vf", "thumbnail,scale=512:-1", "-frames:v", "1", "-q:v", "4",
                    str(out_thumb),
                ],
                capture_output=True, timeout=30,
            )

    final_dur, _ = _probe_video_info(out_mp4)
    return {
        "duration_s": round(final_dur or total_dur, 2),
        "clip_count": len(clip_paths),
        "width": w,
        "height": h,
        "fps": fps,
        "transition": trans,
    }


# ── JSON & template helpers ──────────────────────────────────────────────


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    # Strip markdown code fences if present
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    candidates = [fence.group(1)] if fence else []
    candidates.append(text)
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        candidates.append(text[first : last + 1])
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _render_template(template: str, ctx: dict[str, Any]) -> str:
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


def _normalize_step(raw: Any, idx: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"第 {idx + 1} 个步骤格式无效")
    stype = str(raw.get("type") or "").strip()
    if stype not in STEP_TYPES:
        raise ValueError(f"不支持的步骤类型：{stype}")
    cat = next(s for s in STEP_CATALOG if s["type"] == stype)
    sid = str(raw.get("id") or f"step_{idx + 1}").strip()
    if not STEP_ID_RE.fullmatch(sid):
        sid = f"step_{idx + 1}"
    name = str(raw.get("name") or cat["label"]).strip()[:80] or cat["label"]
    cfg = copy.deepcopy(cat["default_config"])
    if isinstance(raw.get("config"), dict):
        cfg.update(raw["config"])
    return {
        "id": sid,
        "type": stype,
        "name": name,
        "enabled": bool(raw.get("enabled", True)),
        "pause_after": bool(raw.get("pause_after", False)),
        "config": cfg,
    }


def _normalize_workflow_def(body: dict[str, Any]) -> dict[str, Any]:
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
        used_ids.add(st["id"])
        steps.append(st)
    req_id = str(body.get("id") or "").strip()
    if req_id.startswith("builtin:"):
        req_id = ""
    if req_id and not re.fullmatch(r"wf_[A-Za-z0-9_-]{4,48}", req_id):
        raise ValueError("无效的工作流 ID")
    now = int(time.time())
    wf_id = req_id or f"wf_{now % 1000000:06d}_{random.randint(1000, 9999)}"
    return {
        "id": wf_id,
        "builtin": False,
        "name": name,
        "description": str(body.get("description") or "").strip()[:400],
        "default_topic": str(body.get("default_topic") or "").strip()[:600],
        "steps": steps,
        "updated_at": now,
    }


# ── Workflow Engine ──────────────────────────────────────────────────────


class WorkflowEngine:
    """Manages composable workflow definitions, persistent runs, and background execution."""

    def __init__(self, root: Path, studio: Any, store: Store, log: Callable[[str], None]) -> None:
        self.root = root
        self.studio = studio
        self.store = store
        self.log = log
        self.dir = root / "workflows"
        self.defs_path = self.dir / "definitions.json"
        self.runs_dir = self.dir / "runs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._definitions: list[dict[str, Any]] = self._load_definitions()
        self._active_run_id: str | None = None
        self._active_thread: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self._recover_interrupted_runs()

    # ── definitions ───────────────────────────────────────────────────

    def _load_definitions(self) -> list[dict[str, Any]]:
        if not self.defs_path.exists():
            return []
        try:
            data = json.loads(self.defs_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict) and d.get("id") and d.get("steps")][:WORKFLOWS_MAX]
        except (OSError, json.JSONDecodeError):
            pass
        return []

    def _save_definitions_locked(self) -> None:
        tmp = self.defs_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._definitions, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.defs_path)

    def list_workflows(self) -> dict[str, Any]:
        with self._lock:
            custom = copy.deepcopy(self._definitions)
        return {
            "builtin": copy.deepcopy(BUILTIN_WORKFLOWS),
            "custom": custom,
            "step_catalog": copy.deepcopy(STEP_CATALOG),
            "ffmpeg_available": ffmpeg_available(),
            "runs": self.list_runs(),
        }

    def get_workflow(self, wf_id: str) -> dict[str, Any] | None:
        for b in BUILTIN_WORKFLOWS:
            if b["id"] == wf_id:
                return copy.deepcopy(b)
        with self._lock:
            for d in self._definitions:
                if d["id"] == wf_id:
                    return copy.deepcopy(d)
        return None

    def save_workflow(self, body: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        entry = _normalize_workflow_def(body)
        with self._lock:
            self._definitions = [
                d for d in self._definitions if d.get("id") != entry["id"] and d.get("name") != entry["name"]
            ]
            self._definitions.insert(0, entry)
            del self._definitions[WORKFLOWS_MAX:]
            self._save_definitions_locked()
            return copy.deepcopy(entry), copy.deepcopy(self._definitions)

    def delete_workflow(self, wf_id: str) -> tuple[bool, list[dict[str, Any]]]:
        wid = str(wf_id or "").strip()
        if wid.startswith("builtin:"):
            raise ValueError("内置工作流模板不可删除")
        with self._lock:
            before = len(self._definitions)
            self._definitions = [d for d in self._definitions if d.get("id") != wid]
            removed = len(self._definitions) != before
            if removed:
                self._save_definitions_locked()
            return removed, copy.deepcopy(self._definitions)

    # ── run persistence ───────────────────────────────────────────────

    def _run_dir(self, run_id: str) -> Path:
        if not RUN_ID_RE.fullmatch(run_id or ""):
            raise ValueError("无效的运行 ID")
        return self.runs_dir / run_id

    def _run_file(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "run.json"

    def _assets_dir(self, run_id: str) -> Path:
        d = self._run_dir(run_id) / "assets"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _read_run_locked(self, run_id: str) -> dict[str, Any] | None:
        try:
            p = self._run_file(run_id)
        except ValueError:
            return None
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _write_run_locked(self, run: dict[str, Any]) -> None:
        run["updated_at"] = int(time.time())
        p = self._run_file(run["id"])
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p)

    def _recover_interrupted_runs(self) -> None:
        with self._lock:
            for d in self.runs_dir.iterdir():
                if not d.is_dir() or not RUN_ID_RE.fullmatch(d.name):
                    continue
                run = self._read_run_locked(d.name)
                if not run:
                    continue
                if run.get("status") == "running":
                    run["status"] = "paused"
                    run["pause_reason"] = "服务重启，工作流已暂停，可点击「继续」恢复执行"
                    for st in run.get("step_states", {}).values():
                        if st.get("status") == "running":
                            st["status"] = "pending"
                    self._write_run_locked(run)

    @staticmethod
    def _run_summary(run: dict[str, Any]) -> dict[str, Any]:
        steps = run.get("workflow", {}).get("steps") or []
        states = run.get("step_states") or {}
        done_n = sum(1 for s in steps if (states.get(s["id"]) or {}).get("status") in {"done", "skipped"})
        final_rid = None
        for s in reversed(steps):
            out = (states.get(s["id"]) or {}).get("output") or {}
            if out.get("final_round_id"):
                final_rid = out["final_round_id"]
                break
        return {
            "id": run["id"],
            "workflow_id": run.get("workflow", {}).get("id", ""),
            "workflow_name": run.get("workflow", {}).get("name", ""),
            "topic": str(run.get("topic") or "")[:120],
            "status": run.get("status", "draft"),
            "current_step_id": run.get("current_step_id"),
            "done_steps": done_n,
            "total_steps": len(steps),
            "final_round_id": final_rid,
            "created_at": run.get("created_at", 0),
            "updated_at": run.get("updated_at", 0),
            "error": run.get("error", ""),
        }

    def list_runs(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        with self._lock:
            for d in self.runs_dir.iterdir():
                if not d.is_dir() or not RUN_ID_RE.fullmatch(d.name):
                    continue
                run = self._read_run_locked(d.name)
                if run:
                    out.append(self._run_summary(run))
        out.sort(key=lambda r: r.get("updated_at") or 0, reverse=True)
        return out[:RUNS_MAX]

    def active_summary(self) -> dict[str, Any] | None:
        with self._lock:
            rid = self._active_run_id
            if not rid:
                return None
            run = self._read_run_locked(rid)
            return self._run_summary(run) if run else None

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._read_run_locked(run_id)
            if not run:
                return None
            run = copy.deepcopy(run)
            run["assets"] = self._list_assets_locked(run_id)
            return run

    def create_run(self, body: dict[str, Any]) -> dict[str, Any]:
        wf_obj: dict[str, Any] | None = None
        if isinstance(body.get("workflow"), dict) and body["workflow"].get("steps"):
            raw_wf = dict(body["workflow"])
            raw_wf.setdefault("name", "自定义工作流")
            norm = _normalize_workflow_def({**raw_wf, "id": ""})
            norm["id"] = str(raw_wf.get("id") or norm["id"])
            wf_obj = norm
        else:
            wf_id = str(body.get("workflow_id") or "builtin:agent-long-video").strip()
            wf_obj = self.get_workflow(wf_id)
            if not wf_obj:
                raise ValueError(f"未找到工作流：{wf_id}")

        topic = str(body.get("topic") if body.get("topic") is not None else wf_obj.get("default_topic") or "").strip()
        if len(topic) > 2000:
            raise ValueError("主题描述不超过 2000 字")

        now = int(time.time())
        run_id = f"wr_{now % 1000000:06d}_{random.randint(1000, 9999)}"
        step_states = {
            st["id"]: {
                "status": "pending",
                "started_at": None,
                "finished_at": None,
                "progress": "",
                "output": {},
                "error": "",
            }
            for st in wf_obj["steps"]
        }
        run: dict[str, Any] = {
            "id": run_id,
            "topic": topic,
            "workflow": wf_obj,
            "status": "draft",  # draft | running | paused | done | error | canceled
            "current_step_id": None,
            "pause_reason": "",
            "error": "",
            "step_states": step_states,
            "logs": [f"{time.strftime('%H:%M:%S')}  已创建工作流实例「{wf_obj['name']}」"],
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._assets_dir(run_id)
            self._write_run_locked(run)
            run["assets"] = []
        return copy.deepcopy(run)

    def update_run_config(self, run_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Update topic and/or workflow step definitions on a non-running run."""
        with self._lock:
            if self._active_run_id == run_id:
                raise RuntimeError("工作流正在运行，请先暂停或停止后再修改步骤配置")
            run = self._read_run_locked(run_id)
            if not run:
                raise ValueError("运行记录不存在")
            if "topic" in body:
                topic = str(body.get("topic") or "").strip()
                if len(topic) > 2000:
                    raise ValueError("主题描述不超过 2000 字")
                run["topic"] = topic
            if isinstance(body.get("workflow"), dict) and body["workflow"].get("steps"):
                raw_wf = dict(body["workflow"])
                raw_wf.setdefault("name", run["workflow"].get("name") or "工作流")
                norm = _normalize_workflow_def({**raw_wf, "id": ""})
                norm["id"] = str(raw_wf.get("id") or run["workflow"].get("id") or norm["id"])
                norm["builtin"] = bool(run["workflow"].get("builtin"))
                run["workflow"] = norm
                old_states = run.get("step_states") or {}
                new_states = {}
                for st in norm["steps"]:
                    sid = st["id"]
                    new_states[sid] = old_states.get(sid) or {
                        "status": "pending",
                        "started_at": None,
                        "finished_at": None,
                        "progress": "",
                        "output": {},
                        "error": "",
                    }
                run["step_states"] = new_states
            self._write_run_locked(run)
            run["assets"] = self._list_assets_locked(run_id)
            return copy.deepcopy(run)

    def delete_run(self, run_id: str) -> bool:
        with self._lock:
            if self._active_run_id == run_id:
                raise RuntimeError("该工作流正在运行，请先终止后再删除")
            d = self._run_dir(run_id)
            if not d.exists():
                return False
            shutil.rmtree(d, ignore_errors=True)
            return True

    # ── run assets (human uploads & agent downloads) ──────────────────

    def _list_assets_locked(self, run_id: str) -> list[dict[str, Any]]:
        adir = self._assets_dir(run_id)
        items: list[dict[str, Any]] = []
        for p in sorted(adir.iterdir(), key=lambda x: x.stat().st_mtime):
            if not p.is_file() or p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            w, h = probe_image_dimensions(p)
            items.append({
                "filename": p.name,
                "bytes": p.stat().st_size,
                "width": w,
                "height": h,
                "updated_at": int(p.stat().st_mtime),
            })
        return items

    def asset_path(self, run_id: str, filename: str) -> Path | None:
        if not ASSET_NAME_RE.fullmatch(filename or "") or ".." in filename or "/" in filename or "\\" in filename:
            return None
        try:
            p = self._assets_dir(run_id) / filename
        except ValueError:
            return None
        return p if p.exists() and p.is_file() else None

    def upload_asset(self, run_id: str, data: bytes, *, step_id: str = "", label: str = "upload") -> dict[str, Any]:
        if len(data) < 32 or len(data) > MAX_WEB_IMAGE_BYTES:
            raise ValueError(f"图片为空或超过 {MAX_WEB_IMAGE_BYTES // 1048576}MB")
        ext = _image_magic_ext(data)
        if not ext:
            raise ValueError("只接受 PNG、JPEG 或 WebP 图片")
        safe_prefix = re.sub(r"[^A-Za-z0-9_-]", "", label or "asset")[:24] or "asset"
        fname = f"{safe_prefix}_{int(time.time() * 1000) % 100000000:08d}_{random.randint(100, 999)}{ext}"
        with self._lock:
            run = self._read_run_locked(run_id)
            if not run:
                raise ValueError("运行记录不存在")
            dest = self._assets_dir(run_id) / fname
            tmp = dest.with_suffix(ext + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, dest)
            w, h = probe_image_dimensions(dest)
            entry = {"filename": fname, "bytes": len(data), "width": w, "height": h, "source": "upload"}
            # Auto-attach to specified step if applicable
            if step_id:
                for st in run["workflow"]["steps"]:
                    if st["id"] != step_id:
                        continue
                    if st["type"] == "asset_input":
                        files = list(st["config"].get("asset_files") or [])
                        if fname not in files:
                            files.append(fname)
                        st["config"]["asset_files"] = files
                    elif st["type"] == "web_asset_fetch":
                        ss = run["step_states"].setdefault(step_id, {"status": "done", "output": {}})
                        out = ss.setdefault("output", {})
                        imgs = list(out.get("images") or [])
                        imgs.append({
                            "filename": fname,
                            "source_url": "",
                            "page_url": "",
                            "title": "手动上传参考图",
                            "bytes": len(data),
                            "width": w,
                            "height": h,
                        })
                        out["images"] = imgs
                        out["count"] = len(imgs)
                        ss["status"] = "done"
                        ss["error"] = ""
                self._write_run_locked(run)
            assets = self._list_assets_locked(run_id)
        return {"asset": entry, "assets": assets}

    def delete_asset(self, run_id: str, filename: str) -> list[dict[str, Any]]:
        p = self.asset_path(run_id, filename)
        if not p:
            raise ValueError("未找到该资产文件")
        with self._lock:
            p.unlink(missing_ok=True)
            run = self._read_run_locked(run_id)
            if run:
                for st in run["workflow"]["steps"]:
                    if st["type"] == "asset_input":
                        files = [f for f in (st["config"].get("asset_files") or []) if f != filename]
                        st["config"]["asset_files"] = files
                    ss = run["step_states"].get(st["id"])
                    if ss and isinstance(ss.get("output"), dict) and isinstance(ss["output"].get("images"), list):
                        ss["output"]["images"] = [
                            img for img in ss["output"]["images"] if img.get("filename") != filename
                        ]
                self._write_run_locked(run)
            return self._list_assets_locked(run_id)

    # ── human-in-the-loop editing & step control ──────────────────────

    def update_step_output(self, run_id: str, step_id: str, output_patch: dict[str, Any]) -> dict[str, Any]:
        """Allow the user to edit a step's output (script scenes, H3 prompts, fetched images, etc.) while paused."""
        if not isinstance(output_patch, dict):
            raise ValueError("output 必须是对象")
        with self._lock:
            if self._active_run_id == run_id:
                raise RuntimeError("工作流正在运行，请先暂停再修改步骤输出")
            run = self._read_run_locked(run_id)
            if not run:
                raise ValueError("运行记录不存在")
            if step_id not in run.get("step_states", {}):
                raise ValueError(f"未找到步骤：{step_id}")
            ss = run["step_states"][step_id]
            cur_out = dict(ss.get("output") or {})
            cur_out.update(output_patch)
            ss["output"] = cur_out
            if ss.get("status") in {"pending", "error"}:
                ss["status"] = "done"
                ss["error"] = ""
            self._append_log_locked(run, f"人工已编辑步骤「{step_id}」的输出")
            self._write_run_locked(run)
            run["assets"] = self._list_assets_locked(run_id)
            return copy.deepcopy(run)

    def start_run(self, run_id: str, *, from_step_id: str | None = None, single_step: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._active_run_id and self._active_thread and self._active_thread.is_alive():
                raise RuntimeError(f"已有工作流正在执行（{self._active_run_id}），请等待或先终止")
            run = self._read_run_locked(run_id)
            if not run:
                raise ValueError("运行记录不存在")
            steps = run["workflow"]["steps"]
            start_idx = 0
            if from_step_id:
                idx = next((i for i, s in enumerate(steps) if s["id"] == from_step_id), -1)
                if idx < 0:
                    raise ValueError(f"未找到步骤：{from_step_id}")
                start_idx = idx
                # Reset target step (and downstream steps if running full pipeline from here)
                end_reset = idx + 1 if single_step else len(steps)
                for j in range(idx, end_reset):
                    sid = steps[j]["id"]
                    run["step_states"][sid] = {
                        "status": "pending",
                        "started_at": None,
                        "finished_at": None,
                        "progress": "",
                        "output": {},
                        "error": "",
                    }
            else:
                # Resume from first non-done step, or restart from 0 if already finished/canceled
                first_pending = next(
                    (
                        i for i, s in enumerate(steps)
                        if run["step_states"].get(s["id"], {}).get("status") not in {"done", "skipped"}
                    ),
                    -1,
                )
                if first_pending < 0:
                    for s in steps:
                        run["step_states"][s["id"]] = {
                            "status": "pending",
                            "started_at": None,
                            "finished_at": None,
                            "progress": "",
                            "output": {},
                            "error": "",
                        }
                    start_idx = 0
                else:
                    start_idx = first_pending

            run["status"] = "running"
            run["error"] = ""
            run["pause_reason"] = ""
            self._append_log_locked(
                run,
                f"开始执行（从第 {start_idx + 1} 步「{steps[start_idx]['name']}」起"
                + ("，仅单步重试）" if single_step else "）"),
            )
            self._write_run_locked(run)
            self._active_run_id = run_id
            self._cancel_event.clear()
            t = threading.Thread(
                target=self._execute_run_loop,
                args=(run_id, start_idx, single_step),
                daemon=True,
            )
            self._active_thread = t
            t.start()
            run["assets"] = self._list_assets_locked(run_id)
            return copy.deepcopy(run)

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            run = self._read_run_locked(run_id)
            if not run:
                raise ValueError("运行记录不存在")
            if self._active_run_id == run_id:
                self._cancel_event.set()
                self._append_log_locked(run, "已收到终止信号，正在停止当前步骤…")
                self._write_run_locked(run)
            elif run.get("status") in {"paused", "running"}:
                run["status"] = "canceled"
                self._append_log_locked(run, "工作流已终止")
                self._write_run_locked(run)
            run["assets"] = self._list_assets_locked(run_id)
            return copy.deepcopy(run)

    # ── execution loop ────────────────────────────────────────────────

    def _append_log_locked(self, run: dict[str, Any], msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')}  {msg}"
        logs = run.setdefault("logs", [])
        logs.append(line)
        if len(logs) > 200:
            del logs[:-200]
        self.log(f"[WF {run['id']}] {msg}")

    def _set_step_progress(self, run_id: str, step_id: str, text: str) -> None:
        with self._lock:
            run = self._read_run_locked(run_id)
            if not run:
                return
            ss = run["step_states"].setdefault(step_id, {})
            ss["progress"] = text
            self._write_run_locked(run)

    def _execute_run_loop(self, run_id: str, start_idx: int, single_step: bool) -> None:
        try:
            with self._lock:
                run = self._read_run_locked(run_id)
                if not run:
                    return
                steps = copy.deepcopy(run["workflow"]["steps"])

            end_idx = min(len(steps), start_idx + 1) if single_step else len(steps)
            for idx in range(start_idx, end_idx):
                if self._cancel_event.is_set():
                    with self._lock:
                        run = self._read_run_locked(run_id)
                        if run:
                            run["status"] = "canceled"
                            run["current_step_id"] = None
                            self._append_log_locked(run, "工作流已终止")
                            self._write_run_locked(run)
                    return

                step = steps[idx]
                sid = step["id"]
                if not step.get("enabled", True):
                    with self._lock:
                        run = self._read_run_locked(run_id)
                        if run:
                            ss = run["step_states"].setdefault(sid, {})
                            ss["status"] = "skipped"
                            ss["progress"] = "已禁用跳过"
                            self._write_run_locked(run)
                    continue

                with self._lock:
                    run = self._read_run_locked(run_id)
                    if not run:
                        return
                    run["current_step_id"] = sid
                    ss = run["step_states"].setdefault(sid, {})
                    ss["status"] = "running"
                    ss["started_at"] = int(time.time())
                    ss["finished_at"] = None
                    ss["error"] = ""
                    ss["progress"] = "准备中…"
                    self._append_log_locked(run, f"执行步骤：{step['name']} ({step['type']})")
                    self._write_run_locked(run)
                    run_snap = copy.deepcopy(run)

                try:
                    output = self._run_step(run_snap, step)
                except Exception as exc:
                    canceled = self._cancel_event.is_set() or "终止" in str(exc) or "取消" in str(exc)
                    with self._lock:
                        run = self._read_run_locked(run_id)
                        if run:
                            ss = run["step_states"].setdefault(sid, {})
                            ss["status"] = "canceled" if canceled else "error"
                            ss["finished_at"] = int(time.time())
                            ss["error"] = str(exc)[:500]
                            run["status"] = "canceled" if canceled else "error"
                            run["current_step_id"] = None
                            run["error"] = "" if canceled else f"步骤「{step['name']}」失败：{exc}"
                            self._append_log_locked(
                                run,
                                ("步骤已取消：" if canceled else f"步骤「{step['name']}」失败：") + str(exc),
                            )
                            if not canceled:
                                self._append_log_locked(run, traceback.format_exc().splitlines()[-1])
                            self._write_run_locked(run)
                    return

                with self._lock:
                    run = self._read_run_locked(run_id)
                    if not run:
                        return
                    ss = run["step_states"].setdefault(sid, {})
                    ss["status"] = "done"
                    ss["finished_at"] = int(time.time())
                    ss["progress"] = "已完成"
                    ss["output"] = output
                    ss["error"] = ""
                    self._append_log_locked(run, f"完成步骤：{step['name']}")
                    has_more = (idx + 1 < end_idx) and any(steps[k].get("enabled", True) for k in range(idx + 1, end_idx))
                    if step.get("pause_after") and has_more:
                        run["status"] = "paused"
                        run["current_step_id"] = None
                        run["pause_reason"] = f"已在「{step['name']}」后暂停，请检查或编辑结果后点击「继续下一步」"
                        self._append_log_locked(run, run["pause_reason"])
                        self._write_run_locked(run)
                        return
                    self._write_run_locked(run)

            with self._lock:
                run = self._read_run_locked(run_id)
                if run:
                    all_done = all(
                        (run["step_states"].get(s["id"]) or {}).get("status") in {"done", "skipped"}
                        for s in steps
                    )
                    run["status"] = "done" if all_done else "paused"
                    run["current_step_id"] = None
                    if all_done:
                        self._append_log_locked(run, "工作流全部步骤执行完成！")
                    else:
                        run["pause_reason"] = "单步重试已完成，可点击「继续」执行后续步骤"
                        self._append_log_locked(run, run["pause_reason"])
                    self._write_run_locked(run)
        finally:
            with self._lock:
                if self._active_run_id == run_id:
                    self._active_run_id = None
                    self._active_thread = None

    # ── step resolvers & helpers ──────────────────────────────────────

    def _template_ctx(self, run: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx: dict[str, Any] = {"topic": run.get("topic") or ""}
        for sid, ss in (run.get("step_states") or {}).items():
            out = ss.get("output") or {}
            ctx[sid] = out
        if extra:
            ctx.update(extra)
        return ctx

    def _collect_ref_blobs_from_sources(
        self, run: dict[str, Any], source_ids: list[str], *, scene_index: int | None = None
    ) -> list[bytes]:
        """Collect image bytes from referenced steps (asset_input, web_asset_fetch, image_gen)."""
        blobs: list[bytes] = []
        run_id = run["id"]
        states = run.get("step_states") or {}
        steps_by_id = {s["id"]: s for s in run["workflow"]["steps"]}

        for src_id in source_ids or []:
            st = steps_by_id.get(src_id)
            ss = states.get(src_id) or {}
            out = ss.get("output") or {}
            if not st:
                continue
            if st["type"] == "asset_input":
                files = out.get("asset_files") or st["config"].get("asset_files") or []
                for fn in files:
                    p = self.asset_path(run_id, fn)
                    if p:
                        blobs.append(p.read_bytes())
                for rid in (out.get("round_ids") or st["config"].get("round_ids") or []):
                    found = self.store.media_path(str(rid))
                    if found and found[0] == "image":
                        blobs.append(found[1].read_bytes())
            elif st["type"] == "web_asset_fetch":
                imgs = out.get("images") or []
                if scene_index is not None:
                    matched = [im for im in imgs if im.get("scene_index") == scene_index]
                    pick = matched or imgs
                else:
                    pick = imgs
                for im in pick:
                    p = self.asset_path(run_id, str(im.get("filename") or ""))
                    if p:
                        blobs.append(p.read_bytes())
            elif st["type"] == "image_gen":
                items = out.get("items") or []
                if scene_index is not None:
                    matched = [it for it in items if it.get("scene_index") == scene_index]
                    pick_rids = [it.get("round_id") for it in matched if it.get("round_id")]
                else:
                    pick_rids = [it.get("round_id") for it in items if it.get("round_id")]
                for rid in pick_rids:
                    found = self.store.media_path(str(rid))
                    if found and found[0] == "image":
                        blobs.append(found[1].read_bytes())
        return blobs[: LIMITS["refs_max"]]

    def _get_scenes(self, run: dict[str, Any], scenes_from: str) -> list[dict[str, Any]]:
        if not scenes_from:
            return []
        ss = (run.get("step_states") or {}).get(scenes_from) or {}
        out = ss.get("output") or {}
        scenes = out.get("scenes")
        if isinstance(scenes, list) and scenes:
            return [s for s in scenes if isinstance(s, dict)]
        return []

    # ── 7 step executors ──────────────────────────────────────────────

    def _run_step(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        stype = step["type"]
        if stype == "asset_input":
            return self._exec_asset_input(run, step)
        if stype == "llm_script":
            return self._exec_llm_script(run, step)
        if stype == "web_asset_fetch":
            return self._exec_web_asset_fetch(run, step)
        if stype == "image_gen":
            return self._exec_image_gen(run, step)
        if stype == "h3_prompt":
            return self._exec_h3_prompt(run, step)
        if stype == "video_gen":
            return self._exec_video_gen(run, step)
        if stype == "video_stitch":
            return self._exec_video_stitch(run, step)
        raise ValueError(f"未知步骤类型：{stype}")

    def _exec_asset_input(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        cfg = step["config"]
        files: list[str] = []
        assets_meta: list[dict[str, Any]] = []
        for fn in cfg.get("asset_files") or []:
            p = self.asset_path(run["id"], str(fn))
            if p:
                w, h = probe_image_dimensions(p)
                files.append(p.name)
                assets_meta.append({"filename": p.name, "bytes": p.stat().st_size, "width": w, "height": h})
        rids: list[str] = []
        for rid in cfg.get("round_ids") or []:
            found = self.store.media_path(str(rid))
            if found and found[0] == "image":
                rids.append(str(rid))
        return {
            "role": str(cfg.get("role") or "character"),
            "asset_files": files,
            "assets": assets_meta,
            "round_ids": rids,
            "count": len(files) + len(rids),
        }

    def _exec_llm_script(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        cfg = step["config"]
        scene_count = max(1, min(8, int(cfg.get("scene_count") or 3)))
        out_fmt = "text" if cfg.get("output_format") == "text" else "storyboard"
        ctx = self._template_ctx(run, {"scene_count": scene_count})
        instruction = _render_template(cfg.get("instruction") or "请围绕 {{topic}} 编写分镜。", ctx)
        self._set_step_progress(run["id"], step["id"], "正在调用 AI 导演撰写分镜脚本…")

        if out_fmt == "text":
            raw, model = self.studio.call_cpa_chat(
                [
                    {"role": "system", "content": "你是资深电影导演与分镜策划，输出清晰、可直接执行的创作文本。"},
                    {"role": "user", "content": instruction},
                ],
                temperature=0.5,
                max_tokens=4096,
            )
            return {"format": "text", "model": model, "text": raw.strip(), "scenes": []}

        sys_prompt = (
            "你是专业 AI 长视频导演与分镜设计师。"
            "请严格输出一个合法 JSON 对象（不要包含任何额外解释文字），结构如下：\n"
            "{\n"
            '  "title": "短片标题",\n'
            '  "style_bible": "统一视觉风格、光影色调与角色服装规范",\n'
            '  "scenes": [\n'
            "    {\n"
            '      "index": 1,\n'
            '      "title": "镜头标题",\n'
            '      "duration_s": 5,\n'
            '      "search_query": "short English search keywords for white-model pose or scene layout reference",\n'
            '      "keyframe_prompt": "详尽的中文生图关键帧提示词（融合参考构图与角色特征、光线材质、景别）",\n'
            '      "video_prompt": "该镜头的动态运镜、人物动作与情绪变化描述",\n'
            '      "audio_notes": "环境音、拟音、对白或配乐设计"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            f"scenes 数组长度必须严格为 {scene_count}，每镜内容连贯、细节具体。"
        )
        raw, model = self.studio.call_cpa_chat(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": instruction},
            ],
            temperature=0.45,
            max_tokens=8192,
        )
        parsed = _extract_json_object(raw)
        if not parsed or not isinstance(parsed.get("scenes"), list) or not parsed["scenes"]:
            raise RuntimeError("AI 未返回合法的分镜 JSON，请重试或调整指令")
        scenes: list[dict[str, Any]] = []
        for idx, sc in enumerate(parsed["scenes"][:8], start=1):
            if not isinstance(sc, dict):
                continue
            scenes.append({
                "index": idx,
                "title": str(sc.get("title") or f"镜头 {idx}").strip()[:120],
                "duration_s": max(3, min(15, int(sc.get("duration_s") or 5))),
                "search_query": str(sc.get("search_query") or "").strip()[:200],
                "keyframe_prompt": str(sc.get("keyframe_prompt") or sc.get("prompt") or "").strip()[:3000],
                "video_prompt": str(sc.get("video_prompt") or sc.get("motion") or "").strip()[:2000],
                "audio_notes": str(sc.get("audio_notes") or "").strip()[:800],
            })
        if not scenes:
            raise RuntimeError("分镜 JSON 中没有有效镜头")
        return {
            "format": "storyboard",
            "model": model,
            "title": str(parsed.get("title") or run.get("topic") or "未命名短片").strip()[:120],
            "style_bible": str(parsed.get("style_bible") or "").strip()[:1000],
            "scenes": scenes,
            "text": raw[:4000],
        }

    def _exec_web_asset_fetch(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        cfg = step["config"]
        ctx = self._template_ctx(run)
        direct_url = _render_template(cfg.get("url") or "", ctx).strip()
        search_query = _render_template(cfg.get("search_query") or "", ctx).strip()
        instruction = _render_template(cfg.get("instruction") or "选择最清晰契合的参考图", ctx).strip()
        max_images = max(1, min(6, int(cfg.get("max_images") or 2)))
        scenes_from = str(cfg.get("scenes_from") or "").strip()

        candidates: list[dict[str, str]] = []
        page_summary = ""

        if direct_url:
            self._set_step_progress(run["id"], step["id"], f"正在抓取网页：{direct_url[:60]}…")
            raw, ctype, final_url = _fetch_public_bytes(direct_url, max_bytes=MAX_WEB_HTML_BYTES, timeout=25)
            # If user pasted a direct image URL, download it directly
            if _image_magic_ext(raw) or ctype.startswith("image/"):
                candidates.append({"url": final_url, "alt": "direct image", "page_url": final_url, "source": "direct"})
            else:
                parser = _PageImageExtractor(final_url)
                parser.feed(raw.decode("utf-8", errors="replace"))
                page_summary = f"Title: {parser.title}\n" + " ".join(parser.text_parts)[:1200]
                for img in parser.images[:40]:
                    img["page_url"] = final_url
                    candidates.append(img)
        else:
            queries: list[str] = []
            if scenes_from:
                for sc in self._get_scenes(run, scenes_from):
                    q = str(sc.get("search_query") or "").strip()
                    if q and q not in queries:
                        queries.append(q)
            if search_query and search_query not in queries:
                queries.append(search_query)
            if not queries:
                queries = [str(run.get("topic") or "architecture studio reference")]
            for q in queries[:3]:
                if self._cancel_event.is_set():
                    raise RuntimeError("已取消")
                self._set_step_progress(run["id"], step["id"], f"轻量 Agent 检索图库：{q[:50]}…")
                try:
                    found = _search_wikimedia_images(q, limit=10)
                    candidates.extend(found)
                except Exception as exc:
                    self.log(f"[WF {run['id']}] 检索 '{q}' 警告：{exc}")

        if not candidates:
            raise RuntimeError("未从目标网页或检索词找到可用图片，请更换网页链接、修改关键词，或暂停后手动上传参考图")

        # Rank & select via CPA LLM (fallback to original order if LLM fails)
        chosen: list[dict[str, str]] = []
        if len(candidates) > max_images:
            self._set_step_progress(run["id"], step["id"], f"AI 正在从 {len(candidates)} 张候选图中筛选最佳参考图…")
            try:
                cand_lines = [
                    f"{i}. url={c['url']} | alt={c.get('alt', '')[:120]}"
                    for i, c in enumerate(candidates[:25])
                ]
                prompt = (
                    f"主题：{run.get('topic') or ''}\n"
                    f"筛选要求：{instruction}\n"
                    + (f"页面摘要：{page_summary[:600]}\n" if page_summary else "")
                    + "候选图片列表：\n"
                    + "\n".join(cand_lines)
                    + f"\n\n请选出最契合的 {max_images} 张图片，只输出 JSON：{{\"selected\": [0, 1], \"reason\": \"简短理由\"}}"
                )
                raw_sel, _ = self.studio.call_cpa_chat(
                    [
                        {"role": "system", "content": "你是精准的视觉参考图筛选 Agent，只输出合法 JSON。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=1024,
                    timeout=90,
                )
                obj = _extract_json_object(raw_sel) or {}
                idxs = obj.get("selected") if isinstance(obj.get("selected"), list) else []
                for i in idxs:
                    if isinstance(i, int) and 0 <= i < len(candidates) and candidates[i] not in chosen:
                        chosen.append(candidates[i])
            except Exception as exc:
                self.log(f"[WF {run['id']}] LLM 选图降级为顺序选取：{exc}")

        for c in candidates:
            if len(chosen) >= max_images * 2:
                break
            if c not in chosen:
                chosen.append(c)

        saved: list[dict[str, Any]] = []
        adir = self._assets_dir(run["id"])
        for idx, cand in enumerate(chosen):
            if len(saved) >= max_images:
                break
            if self._cancel_event.is_set():
                raise RuntimeError("已取消")
            self._set_step_progress(run["id"], step["id"], f"下载参考图 {len(saved) + 1}/{max_images}…")
            try:
                img_bytes, _, final_img_url = _fetch_public_bytes(
                    cand["url"], max_bytes=MAX_WEB_IMAGE_BYTES, timeout=30, accept="image/*"
                )
                ext = _image_magic_ext(img_bytes)
                if not ext:
                    continue
                fname = f"web_{step['id']}_{int(time.time() * 1000) % 100000000:08d}_{idx}{ext}"
                dest = adir / fname
                dest.write_bytes(img_bytes)
                w, h = probe_image_dimensions(dest)
                # Skip tiny icons
                if (w and w < 128) or (h and h < 128):
                    dest.unlink(missing_ok=True)
                    continue
                saved.append({
                    "filename": fname,
                    "source_url": final_img_url,
                    "page_url": cand.get("page_url") or direct_url,
                    "title": cand.get("alt") or f"参考图 #{len(saved) + 1}",
                    "bytes": len(img_bytes),
                    "width": w,
                    "height": h,
                })
            except Exception as exc:
                self.log(f"[WF {run['id']}] 跳过无效图片 {cand['url'][:80]}：{exc}")

        if not saved:
            raise RuntimeError("候选图片全部下载或校验失败，请换一个公开网页 URL 或手动上传参考图")

        return {
            "source_url": direct_url,
            "search_query": search_query,
            "page_summary": page_summary[:600],
            "images": saved,
            "count": len(saved),
        }

    def _exec_image_gen(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        if not self.studio.colab.has_credentials():
            raise RuntimeError("尚未完成 Google Colab 授权，无法执行生图步骤")
        cfg = step["config"]
        scenes_from = str(cfg.get("scenes_from") or "").strip()
        scenes = self._get_scenes(run, scenes_from)
        max_scenes = max(1, min(8, int(cfg.get("max_scenes") or 6)))
        if scenes:
            scenes = scenes[:max_scenes]
        else:
            scenes = [{"index": 1, "title": "单张关键帧", "keyframe_prompt": run.get("topic") or ""}]

        ref_sources = cfg.get("ref_sources") or []
        prompt_tpl = str(cfg.get("prompt_template") or "{{scene.keyframe_prompt}}")
        prefix = str(cfg.get("prompt_prefix") or "").strip()
        items: list[dict[str, Any]] = []
        round_ids: list[str] = []

        for pos, sc in enumerate(scenes, start=1):
            if self._cancel_event.is_set():
                raise RuntimeError("已取消")
            sc_idx = int(sc.get("index") or pos)
            self._set_step_progress(run["id"], step["id"], f"正在生成关键帧 {pos}/{len(scenes)}：{sc.get('title', '')}")
            ctx = self._template_ctx(run, {"scene": sc})
            prompt = _render_template(prompt_tpl, ctx).strip()
            if prefix:
                prompt = f"{prefix}, {prompt}" if prompt else prefix
            if not prompt:
                prompt = str(sc.get("keyframe_prompt") or run.get("topic") or "").strip()
            ref_blobs = self._collect_ref_blobs_from_sources(run, ref_sources, scene_index=sc_idx)

            raw_body: dict[str, Any] = {
                "mode": "image",
                "engine": cfg.get("engine") or "diffusers",
                "model": cfg.get("model") or DEFAULTS["image"]["model"],
                "prompt": prompt,
                "negative": cfg.get("negative") or "",
                "width": cfg.get("width") or 1280,
                "height": cfg.get("height") or 768,
                "steps": cfg.get("steps") or 35,
                "cfg": cfg.get("cfg") or 5.0,
                "seed": cfg.get("seed", -1),
                "gpu": cfg.get("gpu") or DEFAULTS["gpu"],
                "gpu_pool": cfg.get("gpu_pool") or [cfg.get("gpu") or DEFAULTS["gpu"]],
                "poll_rounds": cfg.get("poll_rounds") or 2,
                "poll_all_proxies": bool(cfg.get("poll_all_proxies")),
                "loras": cfg.get("loras") or [],
                "has_image": bool(ref_blobs),
                "idea": f"[工作流 {run['id']}] {sc.get('title', '')}",
            }
            if cfg.get("comfy"):
                raw_body["comfy"] = cfg["comfy"]
            payload = normalize_job(raw_body)
            payload["workflow_run_id"] = run["id"]
            payload["workflow_step_id"] = step["id"]
            created = self.studio.enqueue_with_refs(payload, ref_blobs=ref_blobs)
            job_id = created[0]["id"]
            done = self.studio.wait_for_job(job_id, cancel_check=self._cancel_event.is_set)
            if done.get("status") != "done" or not done.get("round_id"):
                raise RuntimeError(f"第 {pos} 镜关键帧生成失败：{done.get('error') or done.get('status')}")
            rid = str(done["round_id"])
            round_ids.append(rid)
            items.append({
                "scene_index": sc_idx,
                "title": sc.get("title") or f"镜头 {sc_idx}",
                "prompt": prompt,
                "round_id": rid,
                "ref_count": len(ref_blobs),
                "seed": done.get("seed"),
            })

        return {"items": items, "round_ids": round_ids, "count": len(items)}

    def _exec_h3_prompt(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        cfg = step["config"]
        wf = str(cfg.get("workflow") or "fl2va")
        if wf not in {w["id"] for w in VIDEO_WORKFLOWS}:
            wf = "fl2va"
        num_frames = int(cfg.get("num_frames") or DEFAULTS["video"]["num_frames"])
        scenes_from = str(cfg.get("scenes_from") or "").strip()
        keyframe_from = str(cfg.get("keyframe_from") or "").strip()
        extra_refs = cfg.get("extra_ref_sources") or []
        ctx_base = self._template_ctx(run)
        extra_inst = _render_template(cfg.get("instruction") or "", ctx_base).strip()

        scenes = self._get_scenes(run, scenes_from)
        kf_items = ((run.get("step_states") or {}).get(keyframe_from) or {}).get("output", {}).get("items") or []
        total = max(len(scenes), len(kf_items), 1)
        items: list[dict[str, Any]] = []

        for idx in range(total):
            if self._cancel_event.is_set():
                raise RuntimeError("已取消")
            sc = scenes[idx] if idx < len(scenes) else {"index": idx + 1, "title": f"镜头 {idx + 1}"}
            kf = kf_items[idx] if idx < len(kf_items) else {}
            sc_idx = int(sc.get("index") or idx + 1)
            self._set_step_progress(run["id"], step["id"], f"正在看图写 H3 视频提示词 {idx + 1}/{total}…")

            override_images: list[tuple[str, bytes]] = []
            kf_rid = str(kf.get("round_id") or "")
            if kf_rid:
                found = self.store.media_path(kf_rid)
                if found and found[0] == "image":
                    lbl = "<Picture 1> (First Frame at 0.00s)" if wf == "fl2va" else "<Picture 1>"
                    override_images.append((lbl, found[1].read_bytes()))
            if wf == "ref2va" and extra_refs:
                for blob in self._collect_ref_blobs_from_sources(run, extra_refs, scene_index=sc_idx):
                    if len(override_images) < LIMITS["refs_max"]:
                        override_images.append((f"<Picture {len(override_images) + 1}>", blob))

            brief_parts = [
                f"Shot title: {sc.get('title') or f'Shot {sc_idx}'}",
                f"Action & camera: {sc.get('video_prompt') or sc.get('keyframe_prompt') or run.get('topic') or ''}",
            ]
            if sc.get("audio_notes"):
                brief_parts.append(f"Audio & dialogue notes: {sc['audio_notes']}")
            if extra_inst:
                brief_parts.append(f"Director guidance: {extra_inst}")
            brief = "\n".join(brief_parts)

            res = self.studio.write_prompt_rich(
                brief,
                mode="video",
                workflow=wf,
                num_frames=num_frames,
                ref_count=len(override_images),
                override_images=override_images,
            )
            items.append({
                "scene_index": sc_idx,
                "title": sc.get("title") or f"镜头 {sc_idx}",
                "keyframe_round_id": kf_rid,
                "video_prompt": res["prompt"],
                "format": res.get("format") or "",
                "images_used": res.get("images_used") or 0,
            })

        return {"workflow": wf, "num_frames": num_frames, "items": items, "count": len(items)}

    def _exec_video_gen(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        if not self.studio.colab.has_credentials():
            raise RuntimeError("尚未完成 Google Colab 授权，无法执行生视频步骤")
        cfg = step["config"]
        wf = str(cfg.get("workflow") or "fl2va")
        if wf not in {w["id"] for w in VIDEO_WORKFLOWS}:
            wf = "fl2va"
        scenes = self._get_scenes(run, str(cfg.get("scenes_from") or ""))
        kf_items = ((run.get("step_states") or {}).get(str(cfg.get("keyframe_from") or "")) or {}).get("output", {}).get("items") or []
        pr_items = ((run.get("step_states") or {}).get(str(cfg.get("prompts_from") or "")) or {}).get("output", {}).get("items") or []
        extra_refs = cfg.get("extra_ref_sources") or []

        total = max(len(pr_items), len(kf_items), len(scenes), 1)
        items: list[dict[str, Any]] = []
        round_ids: list[str] = []

        for idx in range(total):
            if self._cancel_event.is_set():
                raise RuntimeError("已取消")
            sc = scenes[idx] if idx < len(scenes) else {"index": idx + 1, "title": f"镜头 {idx + 1}"}
            kf = kf_items[idx] if idx < len(kf_items) else {}
            pr = pr_items[idx] if idx < len(pr_items) else {}
            sc_idx = int(pr.get("scene_index") or sc.get("index") or idx + 1)
            title = pr.get("title") or sc.get("title") or f"镜头 {sc_idx}"
            self._set_step_progress(run["id"], step["id"], f"正在生成视频片段 {idx + 1}/{total}：{title}")

            prompt = str(pr.get("video_prompt") or sc.get("video_prompt") or sc.get("keyframe_prompt") or run.get("topic") or "").strip()
            if not prompt:
                raise RuntimeError(f"第 {idx + 1} 镜缺少视频提示词")

            ref_blobs: list[bytes] = []
            kf_rid = str(pr.get("keyframe_round_id") or kf.get("round_id") or "")
            if kf_rid:
                found = self.store.media_path(kf_rid)
                if found and found[0] == "image":
                    ref_blobs.append(found[1].read_bytes())
            if wf == "ref2va" and extra_refs:
                ref_blobs.extend(self._collect_ref_blobs_from_sources(run, extra_refs, scene_index=sc_idx))

            eff_wf = wf if (wf == "t2va" or ref_blobs) else "t2va"
            raw_body: dict[str, Any] = {
                "mode": "video",
                "workflow": eff_wf,
                "prompt": prompt,
                "negative": cfg.get("negative") or "",
                "width": cfg.get("width") or 1280,
                "height": cfg.get("height") or 768,
                "num_frames": cfg.get("num_frames") or 124,
                "steps": cfg.get("steps") or 30,
                "cfg": cfg.get("cfg") or 5.0,
                "seed": cfg.get("seed", -1),
                "auto_offload": bool(cfg.get("auto_offload", True)),
                "gpu": cfg.get("gpu") or "H100",
                "gpu_pool": cfg.get("gpu_pool") or [cfg.get("gpu") or "H100"],
                "poll_rounds": cfg.get("poll_rounds") or 2,
                "poll_all_proxies": bool(cfg.get("poll_all_proxies")),
                "loras": cfg.get("loras") or [],
                "has_image": bool(ref_blobs) and eff_wf != "t2va",
                "idea": f"[工作流 {run['id']}] {title}",
            }
            payload = normalize_job(raw_body)
            payload["workflow_run_id"] = run["id"]
            payload["workflow_step_id"] = step["id"]
            created = self.studio.enqueue_with_refs(payload, ref_blobs=ref_blobs if eff_wf != "t2va" else [])
            job_id = created[0]["id"]
            done = self.studio.wait_for_job(job_id, cancel_check=self._cancel_event.is_set)
            if done.get("status") != "done" or not done.get("round_id"):
                raise RuntimeError(f"第 {idx + 1} 镜视频生成失败：{done.get('error') or done.get('status')}")
            rid = str(done["round_id"])
            round_ids.append(rid)
            items.append({
                "scene_index": sc_idx,
                "title": title,
                "keyframe_round_id": kf_rid,
                "prompt": prompt[:400],
                "round_id": rid,
                "seed": done.get("seed"),
            })

        return {"items": items, "round_ids": round_ids, "count": len(items)}

    def _exec_video_stitch(self, run: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        cfg = step["config"]
        clip_rids: list[str] = []
        manual = cfg.get("clip_round_ids") or []
        if manual:
            clip_rids = [str(r).strip() for r in manual if str(r).strip()]
        else:
            src_id = str(cfg.get("clips_from") or "").strip()
            src_out = ((run.get("step_states") or {}).get(src_id) or {}).get("output") or {}
            clip_rids = [str(r) for r in (src_out.get("round_ids") or [])]

        clip_paths: list[Path] = []
        valid_rids: list[str] = []
        for rid in clip_rids:
            found = self.store.media_path(rid)
            if found and found[0] == "video":
                clip_paths.append(found[1])
                valid_rids.append(rid)
        if not clip_paths:
            raise RuntimeError("没有找到可拼接的视频作品（请确认上一步视频生成已完成或手动填入作品 ID）")

        self._set_step_progress(run["id"], step["id"], f"FFmpeg 正在剪辑合成 {len(clip_paths)} 段视频…")
        adir = self._assets_dir(run["id"])
        out_mp4 = adir / f"stitched_{step['id']}_{int(time.time())}.mp4"
        out_thumb = adir / f"stitched_{step['id']}_thumb.jpg"

        info = stitch_videos(
            clip_paths,
            out_mp4,
            out_thumb,
            target_width=int(cfg.get("target_width") or 1280),
            target_height=int(cfg.get("target_height") or 768),
            fps=int(cfg.get("fps") or 24),
            transition=str(cfg.get("transition") or "fade"),
            fade_s=float(cfg.get("fade_s") or 0.35),
        )
        meta = {
            "prompt": f"[长视频工作流成片] {run.get('topic') or run['workflow'].get('name')}",
            "model": "Workflow Studio · FFmpeg",
            "workflow": "stitch",
            "width": info["width"],
            "height": info["height"],
            "duration_s": info["duration_s"],
            "workflow_run_id": run["id"],
            "workflow_step_id": step["id"],
            "source_rounds": valid_rids,
            "transition": info["transition"],
        }
        final_rid = self.store.save(out_mp4, "video", meta, out_thumb if out_thumb.exists() else None)
        out_mp4.unlink(missing_ok=True)
        out_thumb.unlink(missing_ok=True)
        return {
            "final_round_id": final_rid,
            "source_rounds": valid_rids,
            **info,
        }
