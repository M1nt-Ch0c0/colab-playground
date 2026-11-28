"""HTTP contract tests for the React client. All media, credentials and upstreams are local fixtures."""
import asyncio
import io
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests
from PIL import Image

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app
from draw_studio.llm import Providers
from draw_studio.proxy import ProxyProfiles
from draw_studio.workflows.engine import WorkflowEngine
from http_fixture import gateway, mp4, png, serving


class WebTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        secret = self.root / "secret.env"
        secret.write_text("password=fixture-password\ntoken=fixture-token\n")
        self.stack.enter_context(patch.dict(os.environ, {"QP_SECRET": str(secret)}))
        self.app = create_app(root=self.root)
        self.url = self.stack.enter_context(serving(self.app))
        self.s = self.app.state.runtime
        self.http = self.stack.enter_context(requests.Session())
        self.http.trust_env = False

    def req(self, method, path, *, expected=200, auth=True, **kw):
        headers = kw.pop("headers", {})
        if auth:
            headers = {"Authorization": "Bearer fixture-token", **headers}
        response = self.http.request(method, self.url + path, headers=headers, timeout=5, allow_redirects=False, **kw)
        self.assertEqual(response.status_code, expected, (method, path, response.status_code, response.text[:160]))
        return response

    def test_login_assets_and_private_api(self):
        index = self.req("GET", "/", auth=False)
        self.assertIn('id="root"', index.text)
        self.assertEqual(index.headers["Cache-Control"], "no-store")
        for asset in re.findall(r'(?:src|href)="\./(assets/[^"]+)"', index.text):
            self.assertIn("immutable", self.req("GET", "/" + asset, auth=False).headers["Cache-Control"])
        self.assertTrue(re.search(r'src="\./assets/[^"]+\.js"', index.text))
        self.req("GET", "/assets/missing.js", auth=False, expected=404)
        self.req("GET", "/assets/%2e%2e%2findex.html", auth=False, expected=404)
        self.req("GET", "/api/llm", auth=False, expected=401)
        self.req("GET", "/api/openapi.json", auth=False, expected=401)
        self.assertEqual(self.req("GET", "/legacy", auth=False, expected=302).headers["Location"], "login")
        self.req("GET", "/legacy")
        self.req("GET", "/api/missing", expected=404)
        cookie = self.req("POST", "/api/login", auth=False, json={"password": "fixture-password"}).headers["Set-Cookie"]
        for field in ("qp_auth=", "httponly", "secure", "samesite=lax", "max-age=2592000", "path=/"):
            self.assertIn(field, cookie.lower())
        self.req("GET", "/api/config", auth=False, headers={"Cookie": cookie.split(";")[0]})
        self.assertIn("Max-Age=0", self.req("POST", "/api/logout").headers["Set-Cookie"])
        self.req("POST", "/login", auth=False, data={"password": "fixture-password"}, expected=302)
        for n in range(8):
            if n % 2:
                self.req("POST", "/login", auth=False, data={"password": "bad"}, expected=401)
            else:
                self.assertEqual(self.req("POST", "/api/login", auth=False, json={"password": "bad"}, expected=401).json()["error"], "密码不对")
        self.req("POST", "/api/login", auth=False, json={"password": "fixture-password"}, expected=429)
        self.req("POST", "/api/llm/providers", json={"kind": "unknown"}, expected=400)
        spec = self.req("GET", "/api/openapi.json").json()
        self.assertIn("ProviderInput", spec["components"]["schemas"])
        self.assertIn({"cookie": []}, spec["paths"]["/api/llm"]["get"]["security"])

    def test_bulk_cleanup_rejects_a_changed_preview_without_deleting(self):
        source = self.root / "cleanup.png"
        source.write_bytes(png())
        original = self.s.store.save(source, "image", {"prompt": "original"})
        replacement = self.s.store.save(source, "image", {"prompt": "replacement"})
        self.s.store.set_star(replacement, True)
        path = "/api/rounds/cleanup"
        criteria = {"max_mb": 0, "permanent": True}
        self.req("POST", path, json={**criteria, "keep_latest": 0, "dry_run": True}, expected=400)
        preview = self.req("POST", path, json={**criteria, "dry_run": True}).json()
        self.assertEqual(preview["matched"], [original])
        self.req("POST", path, json=criteria, expected=400)
        self.s.store.set_star(original, True)
        self.s.store.set_star(replacement, False)
        self.req("POST", path, json={**criteria, "expected_ids": preview["matched"]}, expected=409)
        for rid in (original, replacement):
            self.assertEqual(self.req("GET", "/api/rounds/" + rid).content, source.read_bytes())
        self.assertEqual(self.req("GET", "/api/trash").json()["count"], 0)

        soft = {"max_mb": 0, "permanent": False}
        fresh = self.req("POST", path, json={**soft, "dry_run": True}).json()
        self.assertEqual(fresh["matched"], [replacement])
        applied = self.req("POST", path, json={**soft, "expected_ids": fresh["matched"]}).json()
        self.assertEqual(applied["deleted"], [replacement])
        self.req("GET", "/api/rounds/" + original)
        self.req("GET", "/api/trash/" + replacement)

    def test_health_identifies_the_running_build(self):
        for configured, expected in (("", None), ("12345-2", "12345-2")):
            with self.subTest(configured=configured), patch.dict(os.environ, {"QP_BUILD_ID": configured}):
                health = self.req("GET", "/healthz", auth=False).json()
                self.assertTrue(health["ok"])
                self.assertEqual(health["build_id"], expected)

    def test_existing_clients_and_media_contract(self):
        preset = self.req("POST", "/api/presets", json={"mode": "image", "name": "我的预设", "model": "qwen-2.1-bf16"}).json()
        self.assertEqual(preset["custom"], [preset["preset"]])
        self.assertEqual(self.req("GET", "/api/status").json()["studio_presets"], preset["custom"])
        self.assertEqual(self.req("DELETE", "/api/presets/"+preset["preset"]["id"]).json()["custom"], [])
        raw = png()
        source = self.root / "fixture.png"
        source.write_bytes(raw)
        rid = self.s.store.save(source, "image", {"prompt": "fixture"})
        path = "/api/rounds/" + rid
        self.assertEqual(self.req("GET", "/api/rounds?limit=0").json()["rounds"][0]["id"], rid)
        self.assertIn("attachment", self.req("GET", path+"?download=1").headers["Content-Disposition"])
        self.req("GET", path, headers={"If-None-Match": self.req("HEAD", path).headers["ETag"]}, expected=304)
        for value in ["bytes=7-2", "bytes=broken", "bytes=-0"]:
            self.assertEqual(self.req("GET", path, headers={"Range": value}, expected=416).headers["Content-Range"], f"bytes */{len(raw)}")
        self.assertTrue(self.req("POST", path+"/use", json={"slot": "first"}).json()["references"]["first"]["set"])
        self.assertEqual(self.req("GET", "/api/reference").content, raw)
        self.req("DELETE", "/api/reference?slot=first")
        self.req("POST", "/api/last-frame", data=raw)
        self.assertEqual(self.req("GET", "/api/reference?slot=last").content, raw)
        self.req("DELETE", "/api/last-frame")
        self.assertEqual(self.req("POST", "/api/rounds/star", json={"ids": [rid], "starred": True}).json()["updated"], [rid])
        self.assertEqual(self.req("POST", "/api/rounds/cleanup", json={"keep_latest": 0, "dry_run": True}).json()["count"], 0)
        self.req("POST", "/api/rounds/delete", json={"ids": [rid]})
        self.assertEqual(self.req("GET", "/api/trash/"+rid).content, raw)
        self.req("POST", "/api/trash/restore", json={"ids": [rid]})
        self.assertEqual(self.req("GET", path+"/meta").json()["id"], rid)
        self.assertEqual(self.req("GET", "/api/storage").json()["rounds"]["count"], 1)
        self.req("DELETE", path+"?permanent=0", json={"permanent": True})
        self.assertEqual(self.req("GET", "/api/trash/"+rid).content, raw)
        self.req("POST", "/api/models/recent", json={"model": "owner/model"})
        self.req("DELETE", "/api/models/recent?model=owner%2Fmodel")
        self.req("POST", "/api/generate", json={"prompt": "test"}, expected=400)
        self.req("POST", "/api/colab/grab", json={}, expected=400)
        self.assertEqual(self.req("GET", "/api/queue").json()["queue"], [])
        self.req("GET", "/api/comfy/presets")
        self.req("POST", "/api/comfy/parse-link", json={"url": "owner/repo :: file.safetensors"})
        self.req("GET", "/api/proxy")
        self.req("POST", "/api/settings", json={"idle_minutes": 0})
        self.assertEqual(self.req("GET", "/api/status").json()["idle_minutes"], 0)

    def test_video_reference_validation_and_replacement(self):
        api = "/api/video-reference"
        raw = mp4(self.root / "silent.mp4").read_bytes()
        clip = self.req("POST", api, data=raw).json()["references"]["video"]
        self.assertEqual((clip["duration_s"], clip["source"]), (2, "upload"))
        path = api + "?id=" + clip["id"]
        self.assertEqual(self.req("GET", path, headers={"Range": "bytes=0-15"}, expected=206).content, raw[:16])
        self.req("POST", api, data=png(), expected=400)
        for seconds in (1, 16):
            self.req("POST", api, data=mp4(self.root / "invalid.mp4", seconds).read_bytes(), expected=400)
        self.assertEqual(self.req("GET", path).content, raw)
        replacement = self.req("POST", api, data=raw).json()["references"]["video"]
        self.req("DELETE", path, expected=409)
        self.req("GET", path, expected=404)
        self.assertIsNone(self.req("DELETE", api + "?id=" + replacement["id"]).json()["references"]["video"])

    def test_import_trim_mute_and_extract_displayed_frames(self):
        route = "/api/rounds"
        src = mp4(self.root / "source.mp4", 3, audio=True)
        rid = self.req("POST", route + "/import?kind=video&name=blocking.mp4", data=src.read_bytes()).json()["id"]
        base = f"{route}/{rid}"
        record = self.req("GET", base + "/meta").json()
        self.assertEqual((record["prompt"], record["width"], record["height"], record["media_duration_s"]), ("blocking.mp4", 64, 48, 3))
        self.assertNotIn("duration_s", record)
        raw = subprocess.check_output(["ffmpeg", "-loglevel", "error", "-i", str(src), "-an", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
        size = 64 * 48 * 3
        for position, t, index in [("first", 0, 0), ("time", 1.228, 36), ("last", 0, 89), ("time", 3, 89)]:
            result = self.req("POST", base + "/frame", json={"position": position, "time_s": t}).json()["id"]
            with Image.open(io.BytesIO(self.req("GET", f"{route}/{result}").content)) as frame:
                self.assertEqual(frame.convert("RGB").tobytes(), raw[size*index:size*(index+1)])
            meta = self.req("GET", f"{route}/{result}/meta").json()
            self.assertEqual((meta["kind"], meta["source_rounds"], meta["has_thumb"]), ("image", [rid], True))
        for mute in [False, True]:
            result = self.req("POST", base + "/clip", json={"start_s": .5, "end_s": 2.5, "mute": mute}).json()["id"]
            meta = self.req("GET", f"{route}/{result}/meta").json()
            self.assertEqual((meta["media_duration_s"], meta["source_rounds"], meta["muted"]), (2, [rid], mute))
            found = self.s.store.media_path(result)[1]
            streams = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(found)]).decode().splitlines()
            self.assertEqual(streams, ["h264"] if mute else ["h264", "aac"])
            self.req("POST", f"{route}/{result}/use", json={"slot": "video"})
        short = self.req("POST", base + "/clip", json={"start_s": 2.7, "end_s": 3}).json()["id"]
        self.req("POST", f"{route}/{short}/use", json={"slot": "video"}, expected=400)
        self.req("POST", base + "/clip", json={"start_s": 2, "end_s": 1}, expected=400)
        self.req("POST", base + "/frame", json={"time_s": 9, "position": "time"}, expected=400)
        self.req("POST", route + "/import?kind=image", data=b"bad", expected=400)
        self.req("POST", route + "/import?kind=video", data=png(), expected=400)

    def test_crop_character_sheet_preserves_pixels_and_alpha(self):
        picture = Image.new("RGBA", (60, 40), (10, 20, 60, 0))
        picture.paste((130, 30, 90, 180), (19, 8, 48, 32))
        buf = io.BytesIO()
        picture.save(buf, "PNG")
        rid = self.req("POST", "/api/rounds/import?kind=image", data=buf.getvalue()).json()["id"]
        path = f"/api/rounds/{rid}/crop"
        body = {"x": 17, "y": 5, "width": 18, "height": 24}
        crop = self.req("POST", path, json=body).json()["id"]
        meta = self.req("GET", f"/api/rounds/{crop}/meta").json()
        self.assertEqual((meta["media_operation"], meta["source_rounds"], meta["meta"]["source_crop"]), ("crop", [rid], body))
        self.assertEqual((meta["width"], meta["height"]), (18, 24))
        with Image.open(io.BytesIO(self.req("GET", f"/api/rounds/{crop}").content)) as actual:
            self.assertEqual(actual.mode, "RGBA")
            self.assertEqual(actual.tobytes(), picture.crop((17, 5, 35, 29)).tobytes())
        with Image.open(io.BytesIO(self.req("GET", f"/api/rounds/{rid}").content)) as original:
            self.assertEqual(original.tobytes(), picture.tobytes())
        self.req("POST", path, json={**body, "x": 50}, expected=400)
        self.req("POST", path, json={**body, "width": 0}, expected=400)
        self.assertEqual(self.s.store.list()["total"], 2)

    def test_mask_and_retries_use_original_pixels_after_restart(self):
        route = "/api/rounds"
        src = png((321, 157), "navy")
        rid = self.req("POST", route + "/import?kind=image&name=original.png", data=src).json()["id"]
        self.req("POST", "/api/reference", data=png(color="green"))
        mask = {"source_id": rid, "strokes": [{"size": .001, "points": [[.5, .5]]},
                                              {"size": 2 / 157, "points": [[0, 0]]}]}
        body = {"prompt": "red {dot|spot}", "seed": 0, "edit_mask": mask}
        studio = self.s.studio
        with patch.object(self.s.colab, "has_credentials", return_value=True), patch.object(studio, "_run_loop"):
            jid = self.req("POST", "/api/generate", json=body, expected=202).json()["jobs"][0]["id"]
            self.req("POST", "/api/generate", json={**body, "edit_mask": {**mask, "strokes": []}}, expected=400)
            self.req("POST", "/api/generate", json={**body, "reference_round_ids": [rid]}, expected=400)
        self.req("DELETE", route + "/" + rid)
        self.req("POST", "/api/reference", data=png(color="yellow"))
        with patch.object(studio, "_acquire_session", side_effect=RuntimeError("temporary failure")):
            studio._run_loop()
        self.assertTrue(studio.find_job(jid)["retryable"])
        studio.recover()
        with patch.object(self.s.colab, "has_credentials", return_value=True), patch.object(studio, "_run_loop"):
            api = f"/api/queue/{jid}/retry"
            with ThreadPoolExecutor(2) as pool:
                retries = list(pool.map(lambda _: self.req("POST", api, json={}, expected=202).json()["id"], range(2)))
            self.assertEqual(retries[0], retries[1])
            self.assertEqual(len(studio.snapshot()["queue"]), 1)
            self.req("POST", "/api/generate", json=body, expected=400)
        with patch.object(self.s.colab, "has_credentials", return_value=False):
            self.assertEqual(studio.recover()["queued"], 1)
        uploads = {}
        session = SimpleNamespace(accelerator="A100", machine_shape="test")
        with patch.object(studio, "_acquire_session", return_value=session), \
             patch.object(self.s.colab, "upload_file", side_effect=lambda s, p, dest: uploads.update({dest: p.read_bytes()})), \
             patch.object(self.s.colab, "execute_code"), \
             patch.object(self.s.colab, "download_file", side_effect=lambda s, r, p: p.write_bytes(png((700, 700), "red"))):
            studio._run_loop()
        self.assertEqual(studio.find_job(retries[0])["status"], "done")
        self.assertEqual(json.loads(uploads["content/job.json"])["seed"], 0)
        with Image.open(io.BytesIO(uploads["content/reference.bin"])) as crop:
            self.assertLess(crop.width, 321)
            self.assertEqual(crop.getpixel((0, 0)), (0, 0, 128))
        out = self.s.store.latest("image")
        self.assertEqual((out["width"], out["height"], out["source_rounds"], out["edit_source_id"]), (321, 157, [rid], rid))
        self.assertEqual(self.s.store.get(out["id"])["meta"]["edit_mask"], mask)
        expected = Image.open(io.BytesIO(src))
        expected.putpixel((160, 78), (255, 0, 0))
        expected.putpixel((0, 0), (255, 0, 0))
        with Image.open(self.s.store.media_path(out["id"])[1]) as actual:
            self.assertEqual(actual.tobytes(), expected.tobytes())
        self.assertFalse(list(studio.queue_refs_dir.iterdir()))

    def test_gallery_references_and_tail_frame_survive_a_failed_job(self):
        studio = self.s.studio
        images = [self.req("POST", "/api/rounds/import?kind=image", data=png(color=c)).json()["id"] for c in ("red", "blue")]
        originals = [self.s.store.media_path(rid)[1].read_bytes() for rid in images]
        video = mp4(self.root / "blocking.mp4").read_bytes()
        rid = self.req("POST", "/api/rounds/import?kind=video", data=video).json()["id"]
        base = {"mode": "video", "prompt": "follow", "seed": 17}
        with patch.object(self.s.colab, "has_credentials", return_value=True), patch.object(studio, "_run_loop"):
            def submit(**fields):
                return self.req("POST", "/api/generate", json={**base, **fields}, expected=202).json()["jobs"][0]["id"]
            motion = submit(workflow="ref2va", video_round_id=rid, video_task="motion", reference_round_ids=images[::-1])
            frame = submit(workflow="fl2va", reference_round_ids=[images[0]], last_frame_round_id=images[1])
            self.req("POST", "/api/generate", json={**base, "workflow": "ref2va", "video_round_id": images[0]}, expected=400)
        with patch.object(studio, "_acquire_session", side_effect=RuntimeError("fixture offline")):
            studio._run_loop()
        self.req("POST", "/api/rounds/delete", json={"ids": [rid, *images], "permanent": True})
        studio.recover()
        with patch.object(self.s.colab, "has_credentials", return_value=True), patch.object(studio, "_run_loop"):
            def retry(jid):
                return self.req("POST", f"/api/queue/{jid}/retry", json={}, expected=202).json()["id"]
            m, f = retry(motion), retry(frame)
            self.assertEqual(studio._ref_snapshot_path(m, "video").read_bytes(), video)
            self.assertEqual(studio._ref_snapshot_path(m, "first").read_bytes(), originals[1])
            self.assertEqual(studio._ref_snapshot_path(m, "ref_1").read_bytes(), originals[0])
            self.assertEqual(studio._ref_snapshot_path(f, "last").read_bytes(), originals[1])
        # Losing an explicitly requested tail frame must never turn the job into a first-frame-only render.
        studio._ref_snapshot_path(f, "last").unlink()
        with patch.object(self.s.colab, "has_credentials", return_value=False):
            self.assertEqual(studio.recover()["queued"], 1)
        self.assertEqual(studio.find_job(f)["status"], "error")
        self.assertFalse(studio.find_job(f)["retryable"])
        self.assertEqual(studio.refs_report()["items"], [])

    def test_last_frame_only_rewrite_and_generation(self):
        raw = png(color="purple")
        rid = self.req("POST", "/api/rounds/import?kind=image", data=raw).json()["id"]
        self.req("POST", f"/api/rounds/{rid}/use", json={"slot": "last"})
        self.req("POST", "/api/reference", data=png(color="green"))
        with gateway() as (url, key, calls):
            provider = self.s.studio.llm.save(kind="openai", name="fixture", base_url_value=url+"/open/v1",
                                              api_key=key, models=["open-model"])
            self.s.studio.llm.active(provider["providers"][0]["id"], "open-model")
            rewrite = self.req("POST", "/api/prompt", json={"text": "arrive at the gate", "mode": "video",
                               "workflow": "fl2va", "has_image": False, "has_last_image": True}).json()
            self.assertIn("L2VA", rewrite["format"])
            self.assertEqual(rewrite["images_used"], 1)
            self.assertIn("Last Frame at end", str(calls[-1][2]))
            self.assertNotIn("(First Frame at 0.00s)", str(calls[-1][2]))
        with patch.object(self.s.colab, "has_credentials", return_value=True), patch.object(self.s.studio, "_run_loop"):
            data = {"mode": "video", "workflow": "fl2va", "last_frame_round_id": rid, "prompt": "approach"}
            job = self.req("POST", "/api/generate", json=data, expected=202).json()["jobs"][0]
            payload = self.s.studio._queue[0]["payload"]
            self.assertFalse(payload["has_image"])
            self.assertTrue(payload["has_last_image"])
            self.assertTrue(self.s.studio._ref_snapshot_path(job["id"], "last").is_file())
            self.assertFalse(self.s.studio._ref_snapshot_path(job["id"], "first").exists())

    def test_video_edits_keep_the_submitted_clip_across_recovery(self):
        source = mp4(self.root / "previous.mp4", 3, audio=True)
        rid = self.s.store.save(source, "video", {"prompt": "previous", "duration_s": 240})
        studio = self.s.studio
        clip = self.req("POST", f"/api/rounds/{rid}/use", json={"slot": "video"}).json()["references"]["video"]
        self.assertEqual((clip["source"], clip["duration_s"]), (f"round:{rid}", 3))
        body = dict(mode="video", workflow="ref2va", video_reference_id=clip["id"], prompt="follow the turn")
        with patch.object(self.s.colab, "has_credentials", return_value=True), patch.object(studio, "_run_loop"):
            self.req("POST", "/api/generate", json={**body, "workflow": "fl2va"}, expected=400)
            self.req("POST", "/api/generate", json={**body, "video_task": "continue", "num_frames": 360}, expected=202)
            self.req("POST", "/api/generate", json={**body, "video_task": "motion"}, expected=400)
            self.req("POST", "/api/reference", data=png())
            self.req("POST", "/api/generate", json={**body, "video_task": "motion"}, expected=202)
            self.req("POST", "/api/video-reference", data=mp4(self.root / "next.mp4").read_bytes())
            self.req("POST", "/api/generate", json=body, expected=409)
        self.req("DELETE", "/api/rounds/" + rid)
        self.req("DELETE", "/api/reference")
        with patch.object(self.s.colab, "has_credentials", return_value=False):
            self.assertEqual(studio.recover()["queued"], 2)
        uploads, configs = [], []
        def capture(session, path, remote):
            if remote == "content/job.json":
                configs.append(json.loads(path.read_text()))
            elif remote == "content/reference_video.mp4":
                uploads.append(path.read_bytes())
        session = SimpleNamespace(accelerator="A100", machine_shape="HIGH_RAM")
        with patch.object(studio, "_acquire_session", return_value=session), \
             patch.object(self.s.colab, "upload_file", side_effect=capture), patch.object(self.s.colab, "execute_code"), \
             patch.object(self.s.colab, "download_file", side_effect=lambda s, r, p: p.write_bytes(source.read_bytes()) if r.endswith(".mp4") else None):
            studio._run_loop()
        self.assertEqual(uploads, [source.read_bytes()] * 2)
        self.assertEqual([c["ref_count"] for c in configs], [0, 1])
        self.assertEqual(configs[0]["num_frames"], 345)
        self.assertIn("[video continuation]", configs[0]["prompt"])
        self.assertIn("<Picture 1>", configs[1]["prompt"])
        outputs = self.s.store.list(kind="video")["rounds"]
        self.assertEqual([r["video_task"] for r in outputs], ["motion", "continue"])
        self.assertTrue(all(r["chain_from"] == rid for r in outputs))
        self.assertFalse(list(studio.queue_refs_dir.iterdir()))

    def test_proxy_crud_and_effective_network(self):
        base = "/api/proxy"
        create = base + "/profiles"
        previous = os.environ.get("HTTPS_PROXY")
        self.assertEqual(self.req("GET", base).json(), {"active": "", "profiles": [], "last_test": None})
        self.req("POST", create, json={"label": "test"}, expected=400)
        self.req("POST", create, json={"label": "bad", "url": "http://proxy.example:invalid"}, expected=400)
        url = "socks5h://test-user:fixture-password@[::1]:1080"
        created = self.req("POST", create, json={"label": "Primary", "url": url})
        self.assertNotIn("fixture-password", created.text)
        self.assertNotIn("test-user", created.text)
        first = created.json()["active"]
        self.assertEqual(created.json()["profiles"][0]["masked"], "socks5h://***@[::1]:1080")
        self.assertEqual(os.environ["HTTPS_PROXY"], url)
        self.assertEqual(stat.S_IMODE(self.s.studio.proxies.path.stat().st_mode), 0o600)
        added = self.req("POST", create, json={"label": "Backup", "url": "http://backup.example:8080"}).json()
        second = added["profiles"][1]["id"]
        self.assertEqual(added["active"], first)
        self.req("POST", base, json={"active": second})
        self.req("POST", create, json={"id": first, "label": "Renamed", "url": ""})
        self.assertEqual(os.environ["HTTP_PROXY"], "http://backup.example:8080")
        response = requests.Response()
        response.status_code = 200
        response._content = b"loc=US\ncolo=EWR"
        response._content_consumed = True
        with patch("draw_studio.proxy.requests.Session.get", return_value=response) as probe:
            result = self.req("POST", base+"/test", json={"profile": first}).json()
            self.assertEqual(probe.call_args.kwargs["proxies"], {"http": url, "https": url})
        self.assertTrue(result["ok"])
        self.assertEqual(result["profile"], first)
        self.assertEqual(self.req("GET", base).json()["active"], second)
        with patch("draw_studio.proxy.requests.Session.get", side_effect=requests.exceptions.ProxyError(url)):
            failed = self.req("POST", base+"/test", json={"profile": first})
            self.assertFalse(failed.json()["ok"])
            self.assertNotIn("fixture-password", failed.text)

        self.req("POST", base, json={"active": ""})
        self.assertTrue(os.environ.get("HTTPS_PROXY") == previous)
        self.req("POST", create, json={"id": second, "label": "Backup edited"})
        self.assertEqual(self.req("GET", base).json()["active"], "")
        self.req("POST", base, json={"active": second})
        hooks = self.s.studio._proxy_hooks(["A100"], 1, True)
        self.assertEqual([label for label, _ in hooks], ["Backup edited", "Renamed"])
        hooks[1][1]()
        self.assertEqual(os.environ["HTTP_PROXY"], url)
        self.assertEqual(self.req("GET", base).json()["active"], first)
        self.req("DELETE", create+"/"+first)
        self.assertEqual(os.environ["HTTPS_PROXY"], "http://backup.example:8080")
        self.req("DELETE", create+"/"+second)
        self.assertTrue(os.environ.get("HTTP_PROXY") == self.s.studio.proxies._environment["HTTP_PROXY"])
        self.req("DELETE", create+"/"+first, expected=404)
        self.req("POST", base, json={"active": first}, expected=404)

    def test_proxy_migration_and_durable_selection(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"HTTP_PROXY": "http://system.example:8080"}):
            root = Path(td)
            queue = root/"queue.json"
            queue.write_text(json.dumps({"proxy_profile": "backup"}))
            (root/"proxy_custom.txt").write_text("socks5://custom.example:1080")
            config = {"proxy_url_primary": "http://first.example", "proxy_url_backup": "http://second.example"}
            def reopen():
                return ProxyProfiles(root, config, queue, on_change=lambda: None, log=self.s.log)

            routes = reopen()
            self.assertEqual(routes.state()["active"], "backup")
            self.assertEqual([p["id"] for p in routes.state()["profiles"]], ["primary", "backup", "custom"])
            routes.save("Renamed", "https://replacement.example", "primary")
            routes.configure("primary")
            routes.delete("custom")
            routes.close()
            restarted = reopen()
            self.assertEqual(restarted.state(), routes.state())
            self.assertEqual(os.environ["HTTP_PROXY"], "https://replacement.example")
            with patch("draw_studio.proxy.os.replace", side_effect=OSError("disk full")), self.assertRaises(OSError):
                restarted.delete("primary")
            self.assertEqual(restarted.state()["active"], "primary")
            self.assertFalse(list(restarted.path.parent.glob(".proxies-*")))
            restarted.delete("backup")
            restarted.delete("primary")
            self.assertEqual(os.environ["HTTP_PROXY"], "http://system.example:8080")
            self.assertEqual(reopen().state()["profiles"], [])
            self.assertTrue((root/"proxy_custom.txt").exists())

    def test_volume_owner_and_chunked_body_limit(self):
        async def open_second():
            other = create_app(root=self.root)
            async with other.router.lifespan_context(other):
                self.fail("second worker acquired the data volume")
        with self.assertRaisesRegex(RuntimeError, "一个 worker"):
            asyncio.run(open_second())
        chunk = b"x" * 1048576
        # Stream a request without Content-Length, as a reverse proxy can do.
        self.req("POST", "/api/reference", data=(chunk for _ in range(17)), expected=413)

    def test_fetch_conflict_preserves_concurrent_edit(self):
        args = {"kind": "openai", "name": "local", "base_url": "http://127.0.0.1/v1", "models": ["old"], "api_key": "test"}
        pid = self.req("POST", "/api/llm/providers", json=args).json()["active"]["provider_id"]
        started, finish = threading.Event(), threading.Event()
        def slow_list(provider):
            started.set()
            if not finish.wait(4):
                raise RuntimeError("timed out")
            return ["stale"]
        with patch("draw_studio.llm.list_models", side_effect=slow_list), ThreadPoolExecutor(1) as pool:
            response = pool.submit(self.req, "POST", f"/api/llm/providers/{pid}/models", expected=409)
            try:
                self.assertTrue(started.wait(3))
                self.req("POST", "/api/llm/providers", json={**args, "id": pid, "models": ["new"]})
            finally:
                finish.set()
            self.assertIn("变化", response.result().json()["error"])
        self.assertEqual(self.req("GET", "/api/llm").json()["active"]["model"], "new")

    def test_native_llm_models_images_selection_and_errors(self):
        self.assertEqual(self.req("GET", "/api/llm").json(), {"active": None, "providers": []})
        self.req("POST", "/api/prompt", json={"text": "画山"}, expected=400)
        self.req("POST", "/api/reference", data=png(), headers={"Content-Type": "image/png"})
        broken_proxy = "http://127.0.0.1:1"
        proxy_env = {"HTTP_PROXY": broken_proxy, "http_proxy": broken_proxy, "HTTPS_PROXY": broken_proxy,
                     "https_proxy": broken_proxy, "NO_PROXY": "", "no_proxy": ""}
        with gateway() as (base, key, calls), patch.dict(os.environ, proxy_env):
            ids = []
            for kind, prefix, model in (("openai", "/open/v1", "open-model"), ("anthropic", "/claude", "anthropic-model"), ("gemini", "/google", "gemini-model")):
                args = dict(kind=kind, base_url=base+prefix+"/", name=kind, api_key=key)
                state = self.req("POST", "/api/llm/providers", json=args).json()
                self.assertNotIn(key, json.dumps(state))
                p = state["providers"][-1]
                self.assertTrue(p["key_set"])
                self.assertIsNone(p["models_fetched_at"])
                self.assertEqual(p["base_url"], base+prefix)
                pid = p["id"]
                ids.append(pid)
                state = self.req("POST", f"/api/llm/providers/{pid}/models", json={}).json()
                self.assertEqual(state["providers"][-1]["models"], [model, "anthropic-alt"] if kind == "anthropic" else [model])
                self.assertIsInstance(state["providers"][-1]["models_fetched_at"], int)
                probe = self.req("POST", f"/api/llm/providers/{pid}/test", json={}).json()
                self.assertTrue(probe["ok"], probe)
                self.assertEqual(probe["model"], model)
                result = self.req("POST", "/api/prompt", json={"text": "画山", "editing": True, "provider_id": pid, "model": model}).json()
                self.assertEqual(result["images_used"], 1)
                self.assertEqual(result["prompt"], {"openai": "open result", "anthropic": "anthropic result", "gemini": "gemini result"}[kind])
                _, _, wire = calls[-1]
                if kind == "openai":
                    self.assertEqual(wire["messages"][0]["role"], "system")
                    self.assertTrue(wire["messages"][1]["content"][-1]["image_url"]["url"].startswith("data:image/"))
                elif kind == "anthropic":
                    self.assertTrue(wire["system"] and wire["max_tokens"])
                    self.assertEqual(wire["messages"][0]["content"][-1]["source"]["type"], "base64")
                else:
                    self.assertTrue(wire["systemInstruction"] and wire["generationConfig"]["maxOutputTokens"])
                    self.assertTrue(wire["contents"][0]["parts"][-1]["inlineData"]["data"])
            active = {"provider_id": ids[2], "model": "gemini-model"}
            self.assertEqual(self.req("POST", "/api/llm/active", json=active).json()["active"], active)
            self.assertEqual(self.req("POST", "/api/prompt", json={"text": "画山"}).json()["model"], "gemini-model")
            self.req("POST", "/api/prompt", json={"text": "画山", "provider_id": ids[0]}, expected=400)
            self.req("POST", "/api/llm/active", json={**active, "model": "unknown"}, expected=400)
            self.req("POST", "/api/llm/providers", json={"id": ids[0], "kind": "openai", "name": "empty", "base_url": base, "models": []})
            state = self.req("DELETE", "/api/llm/providers/"+ids[2]).json()
            self.assertEqual(state["active"]["provider_id"], ids[1])
            edit = {"id": ids[1], "kind": "anthropic", "name": "bad", "base_url": base+"/bad", "api_key": ""}
            state = self.req("POST", "/api/llm/providers", json=edit).json()
            self.assertTrue(state["providers"][-1]["key_set"])
            err = self.req("POST", f"/api/llm/providers/{ids[1]}/models", json={}, expected=502).json()["error"]
            self.assertNotIn(key, err)
            self.assertIn("403", err)
            self.assertEqual(self.req("GET", "/api/llm").json(), state)
            self.assertFalse(self.req("POST", f"/api/llm/providers/{ids[1]}/test", json={}).json()["ok"])
            self.req("POST", "/api/prompt", json={"text": "画山"}, expected=502)
            self.req("POST", "/api/llm/providers", json={**edit, "id": "unknown"}, expected=404)
            self.req("POST", "/api/llm/providers", json={**edit, "base_url": "file:///tmp"}, expected=400)
            self.assertNotIn(key, "\n".join(self.s.log.since(0)[0]))
            self.assertEqual(Providers(self.root).state(), state)

    def test_workflow_uses_selected_model_across_review(self):
        def public_asset(url, **kwargs):
            if url.endswith(".png"):
                return png((320, 240)), "image/png", url
            return b'<img src="/first.png"><img src="/second.png">', "text/html", url

        def wait_for(path, status):
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                run = self.req("GET", path).json()["run"]
                if run["status"] == status:
                    return run
                if run["status"] == "error":
                    self.fail(run["error"])
                time.sleep(.02)
            self.fail(f"工作流没有进入 {status}")

        with gateway() as (upstream, key, calls), patch("draw_studio.workflows.web_assets.fetch_public_bytes", side_effect=public_asset):
            for kind, prefix, model in [("openai", "/open/v1", "open-model"), ("gemini", "/google", "gemini-model")]:
                state = self.req("POST", "/api/llm/providers", json={"kind": kind, "name": kind,
                                 "base_url": upstream+prefix, "api_key": key, "models": [model]}).json()
            r = self.req("POST", "/api/workflows/runs", expected=201, json={"topic": "mountains", "workflow": {
                "name": "模型审核", "steps": [
                    {"id": "script", "type": "llm_script", "pause_after": True, "config": {"output_format": "text"}},
                    {"id": "refs", "type": "web_asset_fetch", "config": {"url": "https://images.example/gallery", "max_images": 1}},
                    {"id": "prompt", "type": "h3_prompt", "config": {"workflow": "ref2va", "extra_ref_sources": ["refs"]}},
                ]}}).json()["run"]
            path = "/api/workflows/runs/"+r["id"]
            self.req("POST", path+"/start", json={}, expected=202)
            script = wait_for(path, "paused")["step_states"]["script"]["output"]
            self.assertEqual((script["model"], script["text"]), ("open-model", "open result"))
            self.req("POST", "/api/llm/active", json={"provider_id": state["providers"][1]["id"], "model": "gemini-model"})
            self.req("POST", path+"/resume", json={}, expected=202)
            end = wait_for(path, "done")["step_states"]
            image = end["refs"]["output"]["images"][0]
            self.assertTrue(image["source_url"].endswith("/second.png"))
            self.req("GET", path+"/assets/"+image["filename"]+"?thumb=1")
            shot = end["prompt"]["output"]["items"][0]
            self.assertEqual((shot["video_prompt"], shot["images_used"]), ("gemini result", 1))
            self.assertEqual(len([c for c in calls if c[0].endswith(":generateContent")]), 2)

    def test_rewrite_preference_and_existing_database(self):
        with gateway() as (base, key, calls):
            payload = {"kind": "openai", "name": "Fixture", "base_url": base+"/open/v1", "api_key": key, "models": ["open-model"]}
            p = self.req("POST", "/api/llm/providers", json=payload).json()["providers"][0]
            self.assertFalse(p["enhanced_rewrite"])
            self.assertFalse(p["legacy_template"])
            self.req("POST", "/api/prompt", json={"text": "高山"})
            normal = calls[-1][2]["messages"][0]["content"]
            payload.update(id=p["id"], enhanced_rewrite=True)
            self.req("POST", "/api/llm/providers", json=payload)
            result = self.req("POST", "/api/prompt", json={"text": "高山"}).json()
            self.assertIn("增强改写", result["format"])
            self.assertTrue(calls[-1][2]["messages"][0]["content"].startswith(normal))
            self.assertNotEqual(calls[-1][2]["messages"][0]["content"], normal)
            registry = Providers(self.root)
            self.assertTrue(registry.state()["providers"][0]["enhanced_rewrite"])
            self.assertEqual(stat.S_IMODE(registry.path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(registry.path.parent.stat().st_mode), 0o700)
            # Simulate the previous schema without the preference column.
            with sqlite3.connect(registry.path) as db:
                db.execute("ALTER TABLE providers DROP COLUMN enhanced_rewrite")
                db.execute("UPDATE providers SET legacy=1")
            registry = Providers(self.root)
            existing = registry.state()["providers"][0]
            self.assertEqual(existing["id"], p["id"])
            self.assertTrue(existing["enhanced_rewrite"] and existing["legacy_template"])
            for enabled in (False, True):
                self.req("POST", "/api/llm/providers", json={**payload, "enhanced_rewrite": enabled})
                updated = registry.state()["providers"][0]
                self.assertEqual(updated["enhanced_rewrite"], enabled)
                self.assertTrue(updated["legacy_template"])
            registry.delete(p["id"])
            self.assertEqual(Providers(self.root).state(), {"providers": [], "active": None})

    def test_running_summary_and_multiple_paused_runs(self):
        engine = self.s.workflows
        body = {"workflow": {"name": "审核", "steps": [
            {"id": "one", "type": "asset_input", "pause_after": True}, {"id": "two", "type": "asset_input"}]}}
        def wait_paused(rid):
            thread = engine._active_thread
            if thread:
                thread.join(3)
            self.assertEqual(engine.get_run(rid)["status"], "paused")
        first = engine.create_run(body)["id"]
        engine.start_run(first)
        wait_paused(first)
        second = engine.create_run(body)["id"]
        entered, finish = threading.Event(), threading.Event()
        def step(run, task):
            entered.set()
            if not finish.wait(4):
                raise RuntimeError("timed out")
            return {}
        with patch.object(engine, "_run_step", side_effect=step):
            engine.start_run(second)
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.req("GET", "/api/status").json()["workflow_active"]["id"], second)
                self.assertTrue(self.req("GET", "/healthz", auth=False).json()["workflow_running"])
            finally:
                finish.set()
            wait_paused(second)
        self.assertEqual(engine.active_summary()["id"], second)
        self.req("POST", f"/api/workflows/runs/{second}/cancel", json={})
        self.assertEqual(engine.active_summary()["id"], first)
        self.req("DELETE", f"/api/workflows/runs/{first}")
        self.assertIsNone(engine.active_summary())

    def test_recover_interrupted_workflow_at_step_boundary(self):
        engine = self.s.workflows
        run = engine.create_run({"workflow": {"name": "重启恢复", "steps": [
            {"id": "one", "type": "asset_input"}, {"id": "two", "type": "asset_input"}]}})
        path = self.root / "workflows" / "runs" / run["id"] / "run.json"
        on_disk = json.loads(path.read_text())
        on_disk.update(status="running", current_step_id="two")
        on_disk["step_states"]["one"].update(status="done", output={"note": "已审核"})
        on_disk["step_states"]["two"]["status"] = "running"
        path.write_text(json.dumps(on_disk))
        recovered = WorkflowEngine(self.root, self.s.studio, self.s.store, self.s.log)
        self.assertEqual(recovered.active_summary()["done_steps"], 1)
        state = recovered.get_run(run["id"])
        self.assertEqual(state["status"], "paused")
        self.assertIsNone(state["current_step_id"])
        self.assertEqual(state["step_states"]["two"]["status"], "pending")
        self.assertEqual(state["step_states"]["one"]["output"], {"note": "已审核"})

    def test_draft_upload_thumbnail_pause_resume(self):
        create = {"request_id": "b"*32, "workflow": {"name": "审核素材", "steps": [
            {"id": "first", "type": "asset_input", "pause_after": True}, {"id": "second", "type": "asset_input"}]}}
        run = self.req("POST", "/api/workflows/runs", json=create, expected=201).json()["run"]
        rid = run["id"]
        self.assertEqual(self.req("POST", "/api/workflows/runs", json=create, expected=201).json()["run"]["id"], rid)
        self.assertEqual(len(self.req("GET", "/api/workflows/runs").json()["runs"]), 1)
        base = "/api/workflows/runs/"+rid
        raw = png()
        upload = base+"/assets?step_id=first"
        response = self.req("POST", upload, data=raw).json()
        name = response["asset"]["filename"]
        self.assertEqual(response["filename"], name)
        self.assertEqual(self.req("POST", upload, data=raw).json()["filename"], name)
        self.req("POST", upload, data=b"not an image", expected=400)
        self.req("POST", base+"/assets?step_id=missing", data=raw, expected=400)
        full = self.req("GET", base).json()["run"]
        self.assertEqual(full["status"], "draft")
        self.assertEqual(full["workflow"]["steps"][0]["config"]["asset_files"], [name])
        url = base+"/assets/"+name
        self.assertEqual(self.req("GET", url).content, raw)
        thumb = self.req("GET", url+"?thumb=1")
        self.assertEqual(Image.open(io.BytesIO(thumb.content)).size, (480, 320))
        self.assertEqual(thumb.headers["Content-Type"], "image/jpeg")
        self.assertIn("private", thumb.headers["Cache-Control"])
        self.req("GET", url+"?thumb=1", headers={"If-None-Match": thumb.headers["etag"]}, expected=304)
        self.req("GET", url+"?thumb=1", auth=False, expected=401)
        self.assertEqual(self.req("GET", url, headers={"Range": "bytes=2-6"}, expected=206).content, raw[2:7])
        self.req("GET", url, headers={"Range": "bytes=9999999-"}, expected=416)
        self.assertEqual(self.req("HEAD", url).content, b"")
        self.req("POST", base+"/start", json={"draft_only": True}, expected=202)
        def wait(status):
            end = time.monotonic() + 3
            while time.monotonic() < end:
                state = self.req("GET", base).json()["run"]
                if state["status"] == status:
                    return
                time.sleep(.02)
            self.fail(state)
        wait("paused")
        summary = self.req("GET", "/api/status").json()["workflow_active"]
        self.assertEqual((summary["id"], summary["done_steps"], summary["total_steps"]), (rid, 1, 2))
        self.assertFalse(self.req("GET", "/healthz", auth=False).json()["busy"])
        recovered = WorkflowEngine(self.root, self.s.studio, self.s.store, self.s.log)
        self.assertEqual(recovered.active_summary(), summary)
        self.req("POST", base+"/start", json={"draft_only": True}, expected=409)
        self.req("POST", base+"/resume", json={}, expected=202)
        wait("done")
        self.assertIsNone(self.req("GET", "/api/status").json()["workflow_active"])
        self.req("DELETE", url)
        self.req("GET", url+"?thumb=1", expected=404)
        self.assertFalse((self.root/"workflows"/"runs"/rid/"thumbs"/(name+".jpg")).exists())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=2)
