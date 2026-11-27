#!/usr/bin/env python3
"""Unit & integration tests for Studio v3 features:
- SwarmUI-style prompt wildcard expansion
- General parameter presets persistence & recovery
- SSRF guard on web_asset_fetch (public URL validation & HTML image extractor)
- End-to-end 7-step Long-Video Agent Workflow (asset_input -> llm_script ->
  web_asset_fetch -> image_gen [pause_after] -> human edit -> resume ->
  h3_prompt -> video_gen -> video_stitch)
- Single-step retry & strict isolation from Tab 1/2 user references
- Real FFmpeg stitching when ffmpeg is present in PATH
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import types
import unittest
import zlib
from pathlib import Path
from unittest import mock

REPO = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Stub colab_backend ONLY when running on a dev workstation without google-colab-cli installed
try:
    from draw_studio.colab import client  # noqa: F401
except ImportError:
    cb_mod = types.ModuleType("draw_studio.colab.client")

    class _StubColabBackend:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def has_credentials(self) -> bool:
            return False

        def status_report(self, force: bool = False, blocking: bool = True) -> dict:
            return {"authed": False, "ok": True, "sessions": []}

    cb_mod.ColabBackend = _StubColabBackend
    sys.modules[cb_mod.__name__] = cb_mod

from draw_studio.gallery import Store
from draw_studio.generation.parameters import expand_prompt_wildcards, normalize_grab, normalize_job
from draw_studio.generation.studio import Studio
from draw_studio.logs import LogBuffer
from draw_studio.workflows import video, web_assets
from draw_studio.workflows.engine import WorkflowEngine


def make_png(width: int = 256, height: int = 256, color: tuple[int, int, int] = (80, 140, 220)) -> bytes:
    """Create a valid minimal RGB PNG image of given dimensions using stdlib only."""
    raw = bytearray()
    row = bytes(color) * width
    for _ in range(height):
        raw.append(0)
        raw.extend(row)

    def chunk(ctype: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 1))
        + chunk(b"IEND", b"")
    )


def make_mp4_via_ffmpeg(path: Path, color: str = "blue", dur_s: float = 1.0, with_audio: bool = True) -> None:
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg, "ffmpeg required"
    if with_audio:
        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s=320x240:r=24:d={dur_s}",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur_s}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(path),
        ]
    else:
        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s=320x240:r=24:d={dur_s}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(path),
        ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-300:]


class FakeSession:
    accelerator = "H100"
    machine_shape = "hm"


class FakeColab:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.uploaded_jobs: list[dict] = []
        self.uploaded_ref_counts: list[int] = []
        self._png = make_png(256, 256)
        self._mp4 = b"\x00\x00\x00\x20ftypisom" + (b"\x00" * 4096)

    def has_credentials(self) -> bool:
        return True

    def get_hf_token(self, fallback: str = "") -> str:
        return fallback

    def invalidate_status(self) -> None:
        pass

    def status_report(self, force: bool = False, blocking: bool = True) -> dict:
        return {"authed": True, "ok": True, "balance": 100.0, "sessions": [], "eligible_gpus": ["A100", "H100"]}

    def ensure_session(self, **kwargs):
        return FakeSession()

    def upload_file(self, session, local_path: Path, remote_path: str) -> None:
        if remote_path == "content/job.json":
            data = json.loads(Path(local_path).read_text(encoding="utf-8"))
            self.uploaded_jobs.append(data)
            self.uploaded_ref_counts.append(int(data.get("ref_count") or 0))

    def execute_code(self, session, code: str, **kwargs) -> None:
        cb = kwargs.get("progress_cb")
        if cb:
            cb({"pct": 50, "label": "mock", "detail": "1/2"})

    def download_file(self, session, remote_path: str, local_path: Path) -> None:
        if remote_path.endswith(".mp4"):
            Path(local_path).write_bytes(self._mp4)
        elif remote_path.endswith(".png"):
            Path(local_path).write_bytes(self._png)
        else:
            raise FileNotFoundError(remote_path)

    def interrupt_active(self) -> None:
        pass

    def release_all(self) -> list[str]:
        return []


class StudioV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="qp-wf-test-"))
        self.log = LogBuffer()
        self.store = Store(self.tmp / "out", self.log)
        self.colab = FakeColab(self.tmp)
        self.secret = {"password": "pw", "token": "tok"}
        self.studio = Studio(self.tmp, self.secret, self.colab, self.store, self.log, 600)
        self.wf = WorkflowEngine(self.tmp, self.studio, self.store, self.log)

    def tearDown(self) -> None:
        self.studio.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── 1. SwarmUI-style wildcards ────────────────────────────────────

    def test_expand_prompt_wildcards(self) -> None:
        tpl = "A cyberpunk {girl|samurai|android} in {rainy night|golden sunset}, {json_kept}"
        a = expand_prompt_wildcards(tpl, 42)
        b = expand_prompt_wildcards(tpl, 42)
        self.assertEqual(a, b)
        self.assertIn("{json_kept}", a)
        self.assertNotIn("|", a)
        # Across multiple seeds, we observe multiple variants
        seen = {expand_prompt_wildcards(tpl, s) for s in range(1, 30)}
        self.assertGreaterEqual(len(seen), 3)
        # Escaped braces stay literal
        self.assertEqual(expand_prompt_wildcards(r"literal \{a|b\} text", 7), "literal {a|b} text")

    # ── 2. General Studio Parameter Presets ───────────────────────────

    def test_studio_presets_crud_and_recovery(self) -> None:
        entry, all_p = self.studio.save_studio_preset({
            "name": "我的电影人像",
            "mode": "image",
            "model": "qwen-2.1-bf16",
            "gpu": "A100",
            "width": 1024,
            "height": 1536,
            "steps": 40,
            "cfg": 5.0,
        })
        self.assertTrue(entry["id"].startswith("sp_"))
        self.assertEqual(len(all_p), 1)

        # Recover in a fresh Studio instance
        studio2 = Studio(self.tmp, self.secret, self.colab, self.store, self.log, 600)
        studio2.recover()
        recovered = studio2.studio_presets()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["name"], "我的电影人像")
        self.assertEqual(recovered[0]["width"], 1024)

        removed, rest = studio2.delete_studio_preset(entry["id"])
        self.assertTrue(removed)
        self.assertEqual(rest, [])
        studio2.shutdown()

    # ── 3. SSRF Guard & HTML Image Extractor ──────────────────────────

    def test_ssrf_guard_blocks_internal_and_non_http(self) -> None:
        for bad in (
            "file:///etc/passwd",
            "http://127.0.0.1:8080/v1/models",
            "http://localhost:8787/api/status",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/secret",
            "http://172.16.4.5:8080/",
            "http://192.168.1.1/",
            "http://[::1]/",
            "http://host.docker.internal:8080/",
        ):
            with self.assertRaises(ValueError, msg=f"Expected SSRF block for {bad}"):
                web_assets.validate_public_url(bad, resolve_dns=False)

        self.assertEqual(
            web_assets.validate_public_url("https://example.com/gallery/page.html", resolve_dns=False),
            "https://example.com/gallery/page.html",
        )

    def test_html_image_extractor(self) -> None:
        sample = """
        <html><head><title>White Clay Models</title>
        <meta property="og:image" content="/assets/hero-clay.jpg">
        </head><body>
          <img src="/assets/favicon.ico">
          <img data-src="https://cdn.example.org/clay_pose_1.png" alt="Standing clay figure">
          <img srcset="/small.jpg 200w, /large_pose.webp 1200w" alt="Dynamic pose">
          <a href="/downloads/extra_model.png" title="Extra">Download</a>
        </body></html>
        """
        p = web_assets.PageImageExtractor("https://models.example.org/pack/1")
        p.feed(sample)
        urls = [im["url"] for im in p.images]
        self.assertIn("https://models.example.org/assets/hero-clay.jpg", urls)
        self.assertIn("https://cdn.example.org/clay_pose_1.png", urls)
        self.assertIn("https://models.example.org/large_pose.webp", urls)
        self.assertIn("https://models.example.org/downloads/extra_model.png", urls)
        self.assertFalse(any("favicon" in u for u in urls))

    # ── 4. Workflow Definition CRUD ───────────────────────────────────

    def test_workflow_definition_crud(self) -> None:
        listed = self.wf.list_workflows()
        self.assertGreaterEqual(len(listed["builtin"]), 3)
        self.assertEqual(len(listed["step_catalog"]), 7)

        saved, custom = self.wf.save_workflow({
            "name": "测试自定义流程",
            "description": "测试用",
            "steps": [
                {"id": "s1", "type": "llm_script", "name": "脚本", "config": {"scene_count": 2}},
                {"id": "s2", "type": "image_gen", "name": "出图", "config": {"scenes_from": "s1"}},
            ],
        })
        self.assertTrue(saved["id"].startswith("wf_"))
        self.assertEqual(len(custom), 1)
        with self.assertRaises(ValueError):
            self.wf.delete_workflow("builtin:agent-long-video")
        removed, rest = self.wf.delete_workflow(saved["id"])
        self.assertTrue(removed)
        self.assertEqual(rest, [])

    # ── 5. Full 7-Step End-to-End Pipeline + Pause/Edit/Resume + Isolation ──

    def test_workflow_step_option_contract(self):
        steps = [
            {"id": "single", "type": "image_gen", "config": {"gpu": "L4"}},
            {"id": "ordered", "type": "image_gen", "config": {"gpu_pool": ["G4", "T4", "G4"]}},
            {"id": "custom", "type": "video_gen", "config": {"gpu": "A100", "gpu_pool": ["L4", "H100"]}},
            {"id": "default", "type": "image_gen"},
            {"id": "join", "type": "video_stitch", "config": {"transition": "none"}},
        ]
        wf, _ = self.wf.save_workflow({"name": "参数契约", "steps": steps})
        single, ordered, custom, default, join = [s["config"] for s in wf["steps"]]
        for cfg, expected in [(single, ["L4"]), (ordered, ["G4", "T4"]), (custom, ["L4", "H100"]), (default, ["A100", "H100"])]:
            self.assertEqual((cfg["gpu"], cfg["gpu_pool"]), (expected[0], expected))
        self.assertEqual(join["transition"], "cut")
        for kind, config in [("image_gen", {"poll_all_proxies": "flase"}), ("video_stitch", {"transition": "unknown"})]:
            with self.assertRaises(ValueError):
                self.wf.create_run({"workflow": {"name": "无效配置", "steps": [{"type": kind, "config": config}]}})
        # Direct API callers can still explicitly order candidates, independent of the editor's dropdown.
        job = normalize_job({"prompt": "fixture", "gpu": "L4", "gpu_pool": ["A100", "H100"], "poll_all_proxies": "false"})
        self.assertEqual(job["gpu"], "A100")
        self.assertIs(job["poll_all_proxies"], False)
        self.assertIs(normalize_grab({"gpu_pool": ["L4"], "poll_all_proxies": "false"})["poll_all_proxies"], False)

    def test_legacy_workflow_options_reach_worker(self):
        wf, _ = self.wf.save_workflow({"name": "旧版参数", "steps": [
            {"id": "image", "type": "image_gen"}, {"id": "video", "type": "video_gen"},
            {"id": "join", "type": "video_stitch", "enabled": False},
        ]})
        run = self.wf.create_run({"workflow_id": wf["id"], "topic": "fixture"})
        # Write exactly what the previous React form could leave on disk.
        image, clip, join = [s["config"] for s in wf["steps"]]
        image.update(gpu="L4", poll_all_proxies="false")
        clip.update(gpu="G4", poll_all_proxies="true", auto_offload="false", workflow="t2va")
        join["transition"] = "none"
        self.wf.defs_path.write_text(json.dumps([wf]))
        path = self.wf.runs_dir / run["id"] / "run.json"
        stored = json.loads(path.read_text())
        stored["workflow"] = wf
        path.write_text(json.dumps(stored))

        self.wf = WorkflowEngine(self.tmp, self.studio, self.store, self.log)
        for definition in [self.wf.list_workflows()["custom"][0], self.wf.get_run(run["id"])["workflow"]]:
            image, clip, join = [s["config"] for s in definition["steps"]]
            self.assertEqual(image["gpu_pool"], ["L4"])
            self.assertIs(image["poll_all_proxies"], False)
            self.assertEqual(clip["gpu_pool"], ["G4"])
            self.assertIs(clip["auto_offload"], False)
            self.assertEqual(join["transition"], "cut")
        self.wf.start_run(run["id"])
        finished = self._wait_run_not_running(run["id"])
        self.assertEqual(finished["status"], "done", finished["error"])
        image_job, video_job = self.colab.uploaded_jobs
        self.assertEqual((image_job["gpu"], image_job["gpu_pool"]), ("L4", ["L4"]))
        self.assertIs(image_job["poll_all_proxies"], False)
        self.assertEqual((video_job["gpu"], video_job["gpu_pool"]), ("G4", ["G4"]))
        self.assertIs(video_job["poll_all_proxies"], True)
        self.assertIs(video_job["auto_offload"], False)
        self.assertEqual(video_job["offload_mode"], "none")

    def _wait_run_not_running(self, run_id: str, timeout: float = 20.0) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self.wf.get_run(run_id)
            if r and r["status"] != "running":
                return r
            time.sleep(0.05)
        raise AssertionError("Workflow run timed out")

    def test_full_7_step_agent_pipeline_and_tab_ref_isolation(self) -> None:
        # Put a sentinel user reference in Tab 1/2 to guarantee workflows NEVER touch it!
        tab1_sentinel = make_png(64, 64, (255, 0, 0))
        self.studio.set_ref("first", tab1_sentinel, "user-tab1")

        # Create run from the full 7-step built-in template
        run = self.wf.create_run({
            "workflow_id": "builtin:agent-long-video",
            "topic": "雨夜街头机械伞短片",
        })
        run_id = run["id"]

        # Upload character sheet asset to step 1 (character_assets)
        char_png = make_png(256, 256, (10, 200, 120))
        up = self.wf.upload_asset(run_id, char_png, step_id="character_assets", label="char")
        self.assertTrue(up["asset"]["filename"].startswith("char_"))

        # Customize workflow: 2 scenes, direct webpage URL on web_refs, pause ONLY after script & keyframes
        run = self.wf.get_run(run_id)
        for st in run["workflow"]["steps"]:
            if st["id"] == "script":
                st["config"]["scene_count"] = 2
                st["pause_after"] = True
            elif st["id"] == "web_refs":
                st["config"]["url"] = "https://mock-models.example/clay"
                st["config"]["max_images"] = 1
                st["pause_after"] = False
            elif st["id"] == "keyframes":
                st["pause_after"] = True
            elif st["id"] == "h3_prompts":
                st["pause_after"] = False
        self.wf.update_run_config(run_id, {"workflow": run["workflow"]})

        # Mock model gateway, web fetch, and stitch_videos (unless real ffmpeg tested separately)
        fake_storyboard = json.dumps({
            "title": "雨夜霓虹",
            "style_bible": "赛博朋克胶片质感",
            "scenes": [
                {
                    "index": 1, "title": "巷口登场", "duration_s": 5,
                    "search_query": "white clay standing pose",
                    "keyframe_prompt": "图1姿态白模融合图2人设，雨夜霓虹巷口",
                    "video_prompt": "缓慢推镜头，雨滴落在透明伞面",
                    "audio_notes": "淅沥雨声与霓虹电流声",
                },
                {
                    "index": 2, "title": "回头凝望", "duration_s": 5,
                    "search_query": "white clay look back pose",
                    "keyframe_prompt": "图1回眸白模融合图2人设，远处飞船升空",
                    "video_prompt": "镜头环绕至侧面特写，主角回头微笑",
                    "audio_notes": "远处飞船低鸣与柔和合成器配乐",
                },
            ],
        }, ensure_ascii=False)

        white_model_png = make_png(320, 320, (230, 230, 230))
        mock_html = b'<html><title>Clay</title><body><img src="https://mock-models.example/clay_01.png" alt="white clay pose"></body></html>'

        def fake_fetch(url: str, **kwargs):
            if url.endswith(".png"):
                return white_model_png, "image/png", url
            return mock_html, "text/html", url

        def fake_model_chat(messages, **kwargs):
            sys_txt = messages[0]["content"]
            if "分镜" in sys_txt:
                return fake_storyboard, "fixture-model"
            if "筛选" in sys_txt:
                return '{"selected": [0]}', "fixture-model"
            # MiniMax-H3 prompt rewriter
            return (
                "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.\n\n"
                "integrated_multimodal_description: [Shot 1] Cinematic rain scene.\n"
                "overall_soundscape: Gentle rain hitting umbrella.\n"
                "non_diegetic_music: Soft ambient synth."
            ), "fixture-model"

        def fake_stitch(clip_paths, out_mp4: Path, out_thumb: Path | None = None, **kwargs):
            self.assertEqual(len(clip_paths), 2)
            out_mp4.write_bytes(b"\x00\x00\x00\x20ftypisom" + (b"\x01" * 4096))
            if out_thumb:
                out_thumb.write_bytes(b"\xff\xd8\xff" + (b"\x00" * 200))
            return {"duration_s": 9.65, "clip_count": 2, "width": 1280, "height": 768, "fps": 24, "transition": "fade"}

        def fake_write_prompt_rich(text, **kwargs):
            imgs = kwargs.get("override_images") or []
            return {
                "prompt": (
                    "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.\n\n"
                    "integrated_multimodal_description: [Shot 1] Cinematic rain scene.\n"
                    "overall_soundscape: Gentle rain hitting umbrella.\n"
                    "non_diegetic_music: Soft ambient synth."
                ),
                "model": "fixture-model",
                "format": "H3 三段式 (I2VA · 看首帧)",
                "images_used": len(imgs),
            }

        with mock.patch.object(self.studio, "call_llm", side_effect=fake_model_chat), \
             mock.patch.object(self.studio, "write_prompt_rich", side_effect=fake_write_prompt_rich), \
             mock.patch.object(web_assets, "fetch_public_bytes", side_effect=fake_fetch), \
             mock.patch.object(video, "stitch_videos", side_effect=fake_stitch):

            # Phase 1: Start -> pauses after `script`
            self.wf.start_run(run_id)
            r1 = self._wait_run_not_running(run_id)
            self.assertEqual(r1["status"], "paused")
            self.assertEqual(r1["step_states"]["character_assets"]["status"], "done")
            self.assertEqual(r1["step_states"]["script"]["status"], "done")
            self.assertEqual(len(r1["step_states"]["script"]["output"]["scenes"]), 2)

            # Human edits Scene 1 keyframe_prompt while paused!
            edited_scenes = list(r1["step_states"]["script"]["output"]["scenes"])
            edited_scenes[0]["keyframe_prompt"] = "人工微调：图1白模姿态 + 图2人设，特写雨夜霓虹"
            self.wf.update_step_output(run_id, "script", {"scenes": edited_scenes})

            # Phase 2: Resume -> runs web_refs + keyframes (2 scenes) -> pauses after keyframes
            self.wf.start_run(run_id)
            r2 = self._wait_run_not_running(run_id)
            self.assertEqual(r2["status"], "paused")
            self.assertEqual(r2["step_states"]["web_refs"]["output"]["count"], 1)
            kf_out = r2["step_states"]["keyframes"]["output"]
            self.assertEqual(kf_out["count"], 2)
            self.assertIn("人工微调", kf_out["items"][0]["prompt"])
            # Each keyframe job received BOTH web white-model image + character sheet (2 refs!)
            self.assertEqual(kf_out["items"][0]["ref_count"], 2)
            self.assertEqual(self.colab.uploaded_ref_counts[:2], [2, 2])

            # Phase 3: Resume -> runs h3_prompts -> clips (2 videos) -> final_cut (stitch) -> DONE!
            self.wf.start_run(run_id)
            r3 = self._wait_run_not_running(run_id)
            self.assertEqual(r3["status"], "done")
            self.assertEqual(r3["step_states"]["h3_prompts"]["output"]["count"], 2)
            self.assertEqual(r3["step_states"]["h3_prompts"]["output"]["items"][0]["images_used"], 1)
            self.assertEqual(r3["step_states"]["clips"]["output"]["count"], 2)
            final_rid = r3["step_states"]["final_cut"]["output"]["final_round_id"]
            self.assertTrue(self.store.valid_id(final_rid))
            final_meta = self.store.get(final_rid)
            self.assertEqual(final_meta["kind"], "video")
            self.assertEqual(final_meta["workflow_run_id"], run_id)
            self.assertEqual(len(final_meta["source_rounds"]), 2)

            # Single-step retry on `h3_prompts` should only re-run `h3_prompts`, preserving `script` & `keyframes`
            self.wf.start_run(run_id, from_step_id="h3_prompts", single_step=True)
            r4 = self._wait_run_not_running(run_id)
            self.assertEqual(r4["step_states"]["h3_prompts"]["status"], "done")
            self.assertEqual(r4["step_states"]["keyframes"]["output"]["count"], 2)

        # Verify Tab 1/2 user sentinel reference is 100% untouched!
        self.assertEqual(self.studio.ref_blobs(), [tab1_sentinel])

    # ── 6. Real FFmpeg Stitch Integration Test (when ffmpeg is installed) ─

    def test_real_ffmpeg_stitch_if_available(self) -> None:
        if not video.ffmpeg_available():
            self.skipTest("ffmpeg not installed in this local test environment")
        c1 = self.tmp / "c1.mp4"
        c2 = self.tmp / "c2.mp4"
        out_mp4 = self.tmp / "stitched.mp4"
        out_thumb = self.tmp / "stitched.jpg"
        # Clip 1 has audio, Clip 2 has NO audio — verify auto silent-track normalization + xfade!
        make_mp4_via_ffmpeg(c1, color="red", dur_s=1.2, with_audio=True)
        make_mp4_via_ffmpeg(c2, color="green", dur_s=1.2, with_audio=False)
        info = video.stitch_videos(
            [c1, c2], out_mp4, out_thumb,
            target_width=320, target_height=240, fps=24, transition="fade", fade_s=0.3,
        )
        self.assertTrue(out_mp4.exists() and out_mp4.stat().st_size > 2048)
        self.assertTrue(out_thumb.exists() and out_thumb.stat().st_size > 200)
        self.assertEqual(info["clip_count"], 2)
        self.assertGreater(info["duration_s"], 1.5)
        self.assertEqual(info["transition"], "fade")
        cuts = []
        for value in ("cut", "none"):
            cut = video.stitch_videos([c1, c2], self.tmp / f"{value}.mp4", target_width=320, target_height=240,
                                      fps=24, transition=value, fade_s=0.3)
            self.assertEqual(cut["transition"], "cut")
            self.assertGreater(cut["duration_s"], info["duration_s"] + 0.2)
            cuts.append(cut["duration_s"])
        self.assertAlmostEqual(*cuts, delta=1 / 24)

    # ── 7. Live HTTP API Integration Test (app.Handler) ───────────────

    def test_http_api_presets_and_workflows(self) -> None:
        import urllib.request
        from app import create_app
        from http_fixture import serving
        from draw_studio.runtime import Runtime

        runtime = Runtime(self.tmp, self.secret, self.log, self.colab, self.store, self.studio, self.wf)
        with serving(create_app(root=self.tmp, services=runtime)) as base:
            def req(method: str, path: str, body: dict | bytes | None = None, ctype: str = "application/json"):
                headers = {"Authorization": "Bearer " + self.secret["token"]}
                raw = None
                if isinstance(body, dict):
                    raw = json.dumps(body).encode("utf-8")
                    headers["Content-Type"] = "application/json"
                elif isinstance(body, bytes):
                    raw = body
                    headers["Content-Type"] = ctype
                r = urllib.request.Request(base + path, data=raw, method=method, headers=headers)
                with urllib.request.urlopen(r, timeout=10) as resp:
                    return resp.status, resp.read(), resp.headers.get("Content-Type", "")

            # /healthz exposes busy / queue_len / workflow_running (non-sensitive deploy guard)
            r_hz = urllib.request.urlopen(base + "/healthz", timeout=10)
            hz = json.loads(r_hz.read())
            self.assertEqual(hz["ok"], True)
            self.assertEqual(hz["version"], "3.1")
            self.assertEqual(hz["busy"], False)
            self.assertEqual(hz["queue_len"], 0)
            self.assertEqual(hz["workflow_running"], False)

            # /api/config exposes studio_presets, workflow_step_catalog, video_offload_modes, ffmpeg_available
            code, raw, _ = req("GET", "/api/config")
            self.assertEqual(code, 200)
            cfg = json.loads(raw)
            self.assertEqual(cfg["version"], "3.1")
            self.assertIn("studio_presets", cfg)
            self.assertEqual(len(cfg["video_offload_modes"]), 4)
            self.assertEqual(len(cfg["workflow_step_catalog"]), 7)

            # /api/presets CRUD
            code, raw, _ = req("POST", "/api/presets", {"name": "API 测试预设", "mode": "image", "width": 768, "height": 1152})
            self.assertEqual(code, 200)
            pid = json.loads(raw)["preset"]["id"]
            code, raw, _ = req("DELETE", f"/api/presets/{pid}")
            self.assertEqual(code, 200)

            # /api/workflows + runs + asset upload/fetch/delete
            code, raw, _ = req("GET", "/api/workflows")
            self.assertEqual(code, 200)
            self.assertGreaterEqual(len(json.loads(raw)["builtin"]), 3)

            code, raw, _ = req("POST", "/api/workflows/runs", {"workflow_id": "builtin:agent-long-video", "topic": "API 测试短片"})
            self.assertEqual(code, 201)
            rid = json.loads(raw)["run"]["id"]

            png = make_png(128, 128)
            code, raw, _ = req("POST", f"/api/workflows/runs/{rid}/assets?step_id=character_assets", png, ctype="image/png")
            self.assertEqual(code, 200)
            fname = json.loads(raw)["asset"]["filename"]

            code, img_raw, img_ct = req("GET", f"/api/workflows/runs/{rid}/assets/{fname}")
            self.assertEqual(code, 200)
            self.assertEqual(img_ct, "image/png")
            self.assertEqual(img_raw, png)

            code, _, _ = req("DELETE", f"/api/workflows/runs/{rid}/assets/{fname}")
            self.assertEqual(code, 200)

            code, _, _ = req("DELETE", f"/api/workflows/runs/{rid}")
            self.assertEqual(code, 200)

    # ── 8. Universal Model-Agnostic Memory & Offload Planner ──────────

    def test_video_offload_mode_and_worker_resolver(self) -> None:
        from draw_studio.colab import worker

        hook = mock.Mock()
        module = types.SimpleNamespace(requires_grad_=mock.Mock())
        with mock.patch.dict(sys.modules, {
            "torch": types.SimpleNamespace(device=str),
            "diffusers.hooks": types.SimpleNamespace(apply_group_offloading=hook),
        }), mock.patch.object(worker, "Path", return_value=self.tmp):
            worker._apply_module_group_offload("unet/main", module, "group_disk")
        self.assertEqual(hook.call_args.kwargs["offload_to_disk_path"], str(self.tmp / "unet_main"))
        self.assertTrue((self.tmp / "unet_main").is_dir())

        j_auto = normalize_job({"mode": "video", "prompt": "test"})
        self.assertEqual(j_auto["offload_mode"], "auto")
        self.assertTrue(j_auto["auto_offload"])

        j_group = normalize_job({"mode": "video", "prompt": "test", "offload_mode": "group"})
        self.assertEqual(j_group["offload_mode"], "group")
        self.assertTrue(j_group["auto_offload"])

        j_legacy_off = normalize_job({"mode": "video", "prompt": "test", "auto_offload": False})
        self.assertEqual(j_legacy_off["offload_mode"], "none")
        self.assertFalse(j_legacy_off["auto_offload"])

        # Case A: ~33GB image model (e.g. Qwen BF16) on 80GB VRAM -> full GPU ('none'), on 40GB -> 'component'
        img_33g = {"transformer": 22.0, "text_encoder": 10.5, "vae": 0.5}
        p_img_80 = worker.plan_memory_strategy(img_33g, vram_gb=79.3, ram_gb=167.0)
        self.assertEqual(p_img_80["mode"], "none")
        p_img_40 = worker.plan_memory_strategy(img_33g, vram_gb=40.0, ram_gb=83.5)
        self.assertEqual(p_img_40["mode"], "component")

        # Case B: ~70GB model (e.g. FLUX.2) on 96GB -> 'none', on 80GB -> 'component', on 40GB -> 'group' in CPU RAM
        flux_70g = {"transformer": 58.0, "text_encoder": 11.5, "vae": 0.5}
        self.assertEqual(worker.plan_memory_strategy(flux_70g, vram_gb=95.0, ram_gb=167.0)["mode"], "none")
        self.assertEqual(worker.plan_memory_strategy(flux_70g, vram_gb=79.3, ram_gb=167.0)["mode"], "component")
        p_flux_40 = worker.plan_memory_strategy(flux_70g, vram_gb=40.0, ram_gb=83.5)
        self.assertEqual(p_flux_40["mode"], "group")
        self.assertEqual(p_flux_40["placements"]["transformer"], "group_cpu")
        self.assertEqual(p_flux_40["placements"]["vae"], "cuda")

        # Case C: ~132GB video model (MiniMax-H3) across 80G / 40G / 24G
        h3_132g = {"transformer": 66.0, "text_encoder": 64.0, "vae": 1.2, "audio_vae": 0.8}
        # On 80GB VRAM / 167GB RAM -> fast component offload
        p_h3_80 = worker.plan_memory_strategy(h3_132g, vram_gb=79.3, ram_gb=167.0)
        self.assertEqual(p_h3_80["mode"], "component")
        # On 40GB VRAM / 83.5GB RAM -> group offload; one-shot text_encoder evicted to disk, transformer stays in CPU RAM!
        p_h3_40 = worker.plan_memory_strategy(h3_132g, vram_gb=40.0, ram_gb=83.5)
        self.assertEqual(p_h3_40["mode"], "group")
        self.assertEqual(p_h3_40["placements"]["text_encoder"], "group_disk")
        self.assertEqual(p_h3_40["placements"]["transformer"], "group_cpu")
        self.assertEqual(p_h3_40["placements"]["vae"], "cuda")
        # On 24GB VRAM / 53GB RAM -> both text_encoder & transformer evicted to disk so host RAM never OOMs
        p_h3_24 = worker.plan_memory_strategy(h3_132g, vram_gb=24.0, ram_gb=53.0)
        self.assertEqual(p_h3_24["mode"], "group")
        self.assertEqual(p_h3_24["placements"]["text_encoder"], "group_disk")
        self.assertEqual(p_h3_24["placements"]["transformer"], "group_disk")

        # Explicit override is always respected
        self.assertEqual(
            worker.plan_memory_strategy(h3_132g, vram_gb=79.3, ram_gb=167.0, requested_mode="group")["mode"],
            "group",
        )
        self.assertEqual(
            worker.plan_memory_strategy(h3_132g, vram_gb=40.0, ram_gb=83.5, requested_mode="none")["mode"],
            "none",
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StudioV3Tests)
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
