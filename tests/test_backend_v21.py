#!/usr/bin/env python3
"""Comprehensive unit & integration tests for ColabReel v2.1 backend."""

from __future__ import annotations

import json
import os
import shutil
import struct
import sys
import tempfile
import threading
import time
import zlib
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))


def make_png(w: int, h: int, color=(40, 120, 200)) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(color) * w
    raw = zlib.compress(row * h)
    # Pad PNG to >1024 bytes via tEXt chunk so the generation job size check passes
    pad = b"comment\x00" + (b"x" * 1100)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"tEXt", pad) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def test_tqdm_and_redaction() -> None:
    from draw_studio.colab import client as cb

    samples = [
        (" 40%|████      | 14/35 [00:08<00:12, 1.65it/s]", "", 40, "14/35"),
        ("100%|██████████| 35/35 [00:22<00:00,  1.56it/s]", "", 100, "35/35"),
        ("Fetching 12 files:  50%|█████     | 6/12 [00:03<00:03,  1.92it/s]", "Fetching 12 files", 50, "6/12"),
        ("\x1b[32mLoading checkpoint shards:\x1b[0m 100%|██████████| 3/3 [00:04<00:00, 1.34s/it]", "Loading checkpoint shards", 100, "3/3"),
        ("diffusion_pytorch_model.safetensors:  42%|####      | 1.23G/2.95G [00:15<00:21, 80.1MB/s]", "diffusion_pytorch_model.safetensors", 42, "1.23G/2.95G"),
        ("  0%|          | 0/35 [00:00<?, ?it/s]", "", 0, "0/35"),
    ]
    for line, exp_label, exp_pct, exp_detail in samples:
        parsed = cb.parse_tqdm_line(line)
        assert parsed is not None, f"Failed to parse: {line!r}"
        assert parsed["pct"] == exp_pct, (line, parsed)
        assert parsed["label"] == exp_label, (line, parsed)
        assert parsed["detail"] == exp_detail, (line, parsed)

    assert cb.parse_tqdm_line("normal log line without bar") is None
    fake_hf = "hf_" + "a" * 24
    assert cb.redact_secrets(f"Authorization: Bearer {fake_hf}") == "Authorization: Bearer hf_***"
    assert cb.redact_secrets("socks5h://user:p%40ss@proxy.example:1080") == "socks5h://***@proxy.example:1080"
    print("OK test_tqdm_and_redaction")


def test_non_blocking_colab_status() -> None:
    from draw_studio.colab import client as cb

    tmp = Path(tempfile.mkdtemp(prefix="qp-test-cb-"))
    try:
        logs: list[str] = []
        backend = cb.ColabBackend(tmp, logs.append)
        # No credentials -> immediate unauthed report
        rep0 = backend.status_report(blocking=False)
        assert rep0["authed"] is False and rep0["refreshing"] is False

        # Fake credentials file so has_credentials() is True
        backend.token_path.write_text("{}", encoding="utf-8")
        fetch_calls = {"n": 0}

        def slow_fetch():
            fetch_calls["n"] += 1
            time.sleep(0.25)
            rep = {
                "authed": True, "ok": True, "email": "u@example.com", "error": "",
                "checked_at": int(time.time()), "balance": 88.5, "rate_per_hour": 0.0,
                "assignments_count": 0, "sessions": [], "any_running": False,
                "hf_token_set": False, "refreshing": False,
            }
            with backend._status_lock:
                backend._status_cache = rep
                backend._status_at = time.time()
            return rep

        backend._fetch_status_sync = slow_fetch  # type: ignore[method-assign]

        t0 = time.time()
        r1 = backend.status_report(blocking=False)
        r2 = backend.status_report(blocking=False)
        elapsed = time.time() - t0
        assert elapsed < 0.1, f"Non-blocking call stalled for {elapsed:.3f}s"
        assert r1["refreshing"] is True and r2["refreshing"] is True
        time.sleep(0.35)
        assert fetch_calls["n"] == 1, f"Expected coalesced 1 fetch, got {fetch_calls['n']}"
        r3 = backend.status_report(blocking=False)
        assert r3["balance"] == 88.5 and r3["refreshing"] is False
        print("OK test_non_blocking_colab_status")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_store_features() -> None:
    from draw_studio.gallery import Store

    tmp = Path(tempfile.mkdtemp(prefix="qp-test-store-"))
    try:
        logs: list[str] = []
        st = Store(tmp / "out", logs.append)
        img_src = tmp / "in.png"
        img_src.write_bytes(make_png(640, 960))
        vid_src = tmp / "in.mp4"
        vid_src.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"0" * 2048)

        # Save legacy-style image (no width/height in meta) -> probed automatically
        r1 = st.save(img_src, "image", {"prompt": "sunset fox"})
        r2 = st.save(img_src, "image", {"prompt": "neon rain"})
        r3 = st.save(vid_src, "video", {"prompt": "ocean waves"})
        assert (r1, r2, r3) == ("001", "002", "003")

        item1 = st.get("001")
        assert item1 is not None and item1["width"] == 640 and item1["height"] == 960
        assert (tmp / "out" / "latest.png").exists()
        assert (tmp / "out" / "latest.mp4").exists()

        # Search by zero-padded ID "002" AND stripped "2"
        assert [i["id"] for i in st.list(q="002")["rounds"]] == ["002"]
        assert [i["id"] for i in st.list(q="2")["rounds"]] == ["002"]

        # Star 001 and test cleanup_plan with older_than_days=0 (must match unstarred)
        assert st.set_star("001", True)
        time.sleep(0.05)
        plan_zero = st.cleanup_plan(older_than_days=0, keep_latest=None, kind="image", include_starred=False)
        assert [i["id"] for i in plan_zero] == ["002"], plan_zero

        # max_mb=0 should target unstarred items while respecting starred
        plan_mb = st.cleanup_plan(older_than_days=None, keep_latest=None, kind="image", include_starred=False, max_mb=0)
        assert [i["id"] for i in plan_mb] == ["002"], plan_mb

        # Delete video -> latest.mp4 should disappear; restore -> latest.mp4 returns
        st.delete(["003"])
        assert not (tmp / "out" / "latest.mp4").exists()
        st.restore(["003"])
        assert (tmp / "out" / "latest.mp4").exists()

        # storage_stats check
        ss = st.storage_stats()
        assert ss["rounds"]["count"] == 3 and ss["disk_free_bytes"] > 0
        print("OK test_store_features")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_queue_persistence_and_recovery() -> None:
    from draw_studio.generation.parameters import normalize_job
    from draw_studio.generation.studio import Studio
    from draw_studio.logs import LogBuffer
    from draw_studio.gallery import Store

    # Validation edge cases (including custom HF repo models)
    j0 = normalize_job({"prompt": "hi", "seed": 0, "idle_minutes": 0})
    assert j0["seed"] == 0 and j0["idle_minutes"] == 0
    j_hf = normalize_job({"prompt": "hi", "model": "black-forest-labs/FLUX.1-dev"})
    assert j_hf["model"] == "black-forest-labs/FLUX.1-dev"
    try:
        normalize_job({"prompt": "hi", "model": "bad model name"})
        raise AssertionError("invalid custom model should fail")
    except ValueError:
        pass
    try:
        normalize_job({"prompt": "hi", "steps": True})
        raise AssertionError("bool steps should fail")
    except ValueError:
        pass

    tmp = Path(tempfile.mkdtemp(prefix="qp-test-jobs-"))
    try:
        png = make_png(512, 512)
        (tmp / "reference.bin").write_bytes(png)

        class Sess:
            accelerator = "A100"
            machine_shape = "HIGH_RAM"

        class GateColab:
            def __init__(self, authed: bool = True):
                self.authed = authed
                self.gate = threading.Event()
                self.started = threading.Event()
                self.uploaded_refs = 0

            def has_credentials(self):
                return self.authed

            def status_report(self, force=False, blocking=True):
                return {"authed": self.authed, "ok": True, "sessions": [], "any_running": False}

            def ensure_session(self, **kw):
                return Sess()

            def upload_file(self, s, local, remote):
                if remote == "content/reference.bin":
                    self.uploaded_refs += 1

            def get_hf_token(self, fb=""):
                return ""

            def execute_code(self, s, code, cancel_check=None, idle_timeout=0, progress_cb=None):
                self.started.set()
                self.gate.wait(timeout=3.0)

            def download_file(self, s, remote, local):
                if remote.endswith("thumb.jpg"):
                    raise RuntimeError("no thumb")
                Path(local).write_bytes(png)

            def invalidate_status(self):
                pass

            def interrupt_active(self):
                self.gate.set()

            def release_all(self):
                return []

        log1 = LogBuffer()
        store1 = Store(tmp / "out", log1)
        colab1 = GateColab(authed=True)
        st1 = Studio(tmp, {}, colab1, store1, log1, 600)
        st1.set_idle_minutes(25)
        st1.add_recent_model("black-forest-labs/FLUX.1-dev")
        assert st1.recent_models() == ["black-forest-labs/FLUX.1-dev"]

        jobs = st1.enqueue(normalize_job({"prompt": "persist me", "count": 2, "seed": 7, "has_image": True}))
        assert colab1.started.wait(timeout=2.0), "Job 1 never started"
        # Snapshot queue.json right now (job 1 is running, job 2 is queued with ref blob!)
        qjson = json.loads((tmp / "out" / "queue.json").read_text(encoding="utf-8"))
        assert qjson["idle_minutes"] == 25
        assert qjson["current"]["id"] == jobs[0]["id"]
        assert len(qjson["queue"]) == 1 and qjson["queue"][0]["id"] == jobs[1]["id"]
        assert (tmp / "out" / "queue_refs" / f"{jobs[1]['id']}_first.bin").exists()

        # Simulate hard crash: copy out/ to a fresh dir and boot a brand new Studio
        tmp2 = Path(tempfile.mkdtemp(prefix="qp-test-jobs-recover-"))
        try:
            shutil.copytree(tmp / "out", tmp2 / "out")
            # Add an orphan ref blob to verify pruning
            (tmp2 / "out" / "queue_refs" / "j99999999_first.bin").write_bytes(b"orphan")

            log2 = LogBuffer()
            store2 = Store(tmp2 / "out", log2)
            colab2 = GateColab(authed=True)
            colab2.gate.set()  # let recovered job 2 run straight through!
            st2 = Studio(tmp2, {}, colab2, store2, log2, 600)
            rec = st2.recover()
            assert rec["interrupted"] == jobs[0]["id"]
            assert rec["queued"] == 1
            assert st2.idle_seconds == 25 * 60
            assert st2.recent_models() == ["qwen-2.1-bf16", "black-forest-labs/FLUX.1-dev"], st2.recent_models()
            assert st2.remove_recent_model("black-forest-labs/FLUX.1-dev") == ["qwen-2.1-bf16"]
            assert not (tmp2 / "out" / "queue_refs" / "j99999999_first.bin").exists()

            # Wait for recovered job 2 to complete
            deadline = time.time() + 5.0
            while st2.busy() and time.time() < deadline:
                time.sleep(0.05)
            snap2 = st2.snapshot()
            assert not st2.busy()
            assert colab2.uploaded_refs == 1, "Recovered job 2 should have uploaded its persisted reference snapshot"
            statuses = {h["id"]: h["status"] for h in snap2["history"]}
            assert statuses[jobs[0]["id"]] == "error"
            assert statuses[jobs[1]["id"]] == "done"
            assert store2.list()["total"] == 1
            assert not (tmp2 / "out" / "queue_refs" / f"{jobs[1]['id']}_first.bin").exists()
            print("OK test_queue_persistence_and_recovery")
        finally:
            runner = st1._runner
            colab1.gate.set()
            if runner:
                runner.join(5)
                assert not runner.is_alive()
            st1.shutdown()
            shutil.rmtree(tmp2, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_gpu_shape_and_retry_cancel() -> None:
    from draw_studio.colab import client as cb

    tmp = Path(tempfile.mkdtemp(prefix="qp-test-gpu-"))
    try:
        logs: list[str] = []
        backend = cb.ColabBackend(tmp, logs.append)
        seen_shapes: list[tuple[str, object]] = []

        class FakeProxy:
            token = "tok"
            url = "https://example.invalid"

            def expires_at(self):
                return None

        class FakeAssignResp:
            token = "xsrf"

        class FakePostResp:
            endpoint = "m-s-test"
            runtime_proxy_info = FakeProxy()

        class FakeClient:
            def list_assignments(self):
                return []

            def _get_assignment(self, nbh, variant, acc, shape):
                seen_shapes.append((acc.value, shape))
                return FakeAssignResp()

            def _post_assignment(self, nbh, tok, variant, acc, shape):
                return FakePostResp()

        backend._client = lambda: FakeClient()  # type: ignore[method-assign]

        for gpu_name, exp_shape in [("H100", None), ("G4", None), ("L4", None), ("A100", cb.Shape.HIGH_RAM)]:
            seen_shapes.clear()
            sess = backend.ensure_session(gpu=gpu_name, high_mem=True, session_name="s-" + gpu_name)
            assert seen_shapes == [(gpu_name, exp_shape)], (gpu_name, seen_shapes)
            assert sess.accelerator == gpu_name

        # Test cancel during 503 retry backoff
        class Resp503:
            status_code = 503
            text = "<html>Error 503 (Service Unavailable)!!1</html>"

        class Client503(FakeClient):
            def _post_assignment(self, nbh, tok, variant, acc, shape):
                raise cb.ColabRequestError("Service Unavailable", request=None, response=Resp503())

        backend._client = lambda: Client503()  # type: ignore[method-assign]
        cancel_flag = {"v": False}

        def trip():
            time.sleep(0.25)
            cancel_flag["v"] = True

        threading.Thread(target=trip, daemon=True).start()
        t0 = time.time()
        try:
            backend.ensure_session(gpu="A100", high_mem=True, session_name="s-cancel", cancel_check=lambda: cancel_flag["v"])
            raise AssertionError("expected cancel")
        except RuntimeError as exc:
            assert "取消" in str(exc), str(exc)
        assert time.time() - t0 < 2.0, "cancel took too long"
        assert any("503" in ln for ln in logs), logs

        with patch.dict(os.environ, {"COLAB_CLI_ASSIGN_RETRIES": "0"}):
            for gpu in ("A100", "H100"):  # High-RAM fallback and single-shape allocation
                logs.clear()
                try:
                    backend.ensure_session(gpu=gpu, high_mem=True, session_name="s-no-stock-" + gpu)
                except RuntimeError as exc:
                    assert str(exc) == f"{gpu} 暂无空闲库存（HTTP 503），可换卡、换出口或稍后重试。", str(exc)
                else:
                    raise AssertionError("expected allocation to fail")
                assert any("Service Unavailable" in line for line in logs), logs

        # Test auto-fallback: A100 returns 503, L4 succeeds immediately, gpu_health records both!
        class FallbackClient(FakeClient):
            def _post_assignment(self, nbh, tok, variant, acc, shape):
                if acc.value == "A100":
                    raise cb.ColabRequestError("Service Unavailable", request=None, response=Resp503())
                return FakePostResp()

        backend._client = lambda: FallbackClient()  # type: ignore[method-assign]
        sess_fb = backend.ensure_session(
            gpu="A100", high_mem=True, session_name="s-fb", fallback_gpus=["A100", "L4"]
        )
        assert sess_fb.accelerator == "L4"
        gh = backend.gpu_health_snapshot()
        assert gh["A100"]["status"] == "unavailable" and gh["L4"]["status"] == "ok", gh
        print("OK test_gpu_shape_and_retry_cancel")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_multi_refs_and_local_gateway_proxy_bypass() -> None:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from draw_studio.generation.catalog import LIMITS
    from draw_studio.generation.parameters import normalize_job
    from draw_studio.generation.studio import Studio
    from draw_studio.logs import LogBuffer
    from draw_studio.proxy import is_local_or_private_host
    from draw_studio.gallery import Store

    assert is_local_or_private_host("127.0.0.1")
    assert is_local_or_private_host("172.16.4.5")
    assert is_local_or_private_host("192.168.3.4")
    assert is_local_or_private_host("host.docker.internal")
    assert is_local_or_private_host("10.0.1.5")
    assert not is_local_or_private_host("api.openai.com")

    tmp = Path(tempfile.mkdtemp(prefix="qp-test-multi-"))
    try:
        png1 = make_png(64, 64, (10, 20, 30))
        png2 = make_png(64, 64, (40, 50, 60))
        png3 = make_png(64, 64, (70, 80, 90))
        # Seed legacy reference.bin to verify seamless promotion
        (tmp / "reference.bin").write_bytes(png1)

        uploaded: list[str] = []

        class FakeColab:
            def has_credentials(self):
                return True

            def status_report(self, force=False, blocking=True):
                return {"authed": True, "ok": True, "sessions": [], "any_running": False}

            def ensure_session(self, **kw):
                class S:
                    accelerator = "A100"
                    machine_shape = "HIGH_RAM"

                return S()

            def upload_file(self, s, local, remote):
                uploaded.append(remote)

            def get_hf_token(self, fb=""):
                return ""

            def execute_code(self, s, code, cancel_check=None, idle_timeout=0, progress_cb=None):
                pass

            def download_file(self, s, remote, local):
                if remote.endswith("thumb.jpg"):
                    raise RuntimeError("no thumb")
                Path(local).write_bytes(png1)

            def invalidate_status(self):
                pass

            def release_all(self):
                return []

        # Local OpenAI-compatible server on 127.0.0.1; set a broken HTTP_PROXY to prove bypass works!
        seen_bodies: list[dict] = []

        class LocalModelServer(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                seen_bodies.append(body)
                resp = json.dumps({"choices": [{"message": {"content": "```text\nclean enhanced prompt\n```"}}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, fmt, *args):
                pass

        srv = HTTPServer(("127.0.0.1", 0), LocalModelServer)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        old_env = {k: os.environ.get(k) for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy")}
        try:
            log = LogBuffer()
            store = Store(tmp / "out", log)
            st = Studio(
                tmp,
                {
                    "proxy_url_primary": "http://198.51.100.1:1",  # unreachable proxy!
                },
                FakeColab(),
                store,
                log,
                600,
            )
            assert "localhost" in os.environ.get("NO_PROXY", "")
            st.llm.save(kind="openai", name="Local fixture", base_url_value=f"http://127.0.0.1:{port}/v1",
                        api_key="test-key", models=["fixture-model"])
            # The selected model receives the existing reference image.
            rich_img = st.write_prompt_rich("两张图融合", mode="image", editing=True, ref_count=2)
            assert rich_img["prompt"] == "clean enhanced prompt"
            assert rich_img["model"] == "fixture-model"
            assert rich_img["images_used"] == 1
            last_body = seen_bodies[-1]
            assert last_body["model"] == "fixture-model"
            user_content = last_body["messages"][-1]["content"]
            assert isinstance(user_content, list)
            assert any(p.get("type") == "image_url" for p in user_content)

            # Multi-ref add / promote legacy / remove / upload
            rep0 = st.refs_report()
            assert len(rep0["items"]) == 1 and rep0["first"]["set"] is True
            it2 = st.add_ref(png2, "upload")
            it3 = st.add_ref(png3, "upload")
            rep1 = st.refs_report()
            assert len(rep1["items"]) == 3 and rep1["max"] == LIMITS["refs_max"]
            assert len(st.ref_blobs()) == 3

            # Video Ref2VA: must attach all 3 reference images and use 6-section official H3 guide
            rich_ref2va = st.write_prompt_rich("赛博街头漫步", mode="video", workflow="ref2va", num_frames=175)
            assert rich_ref2va["images_used"] == 3
            assert "六段式" in rich_ref2va["format"]
            sys_ref = seen_bodies[-1]["messages"][0]["content"]
            assert "# Full-Reference Mode Rewrite Output Format Guide" in sys_ref
            assert "subject_definitions" in sys_ref and "retention_analysis" in sys_ref and "non_diegetic_music" in sys_ref
            img_parts = [p for p in seen_bodies[-1]["messages"][-1]["content"] if p.get("type") == "image_url"]
            assert len(img_parts) == 3

            # Video T2VA: text-only official H3 guide with the standard rewrite settings
            rich_t2va = st.write_prompt_rich("雨夜城市", mode="video", workflow="t2va", num_frames=124)
            assert rich_t2va["images_used"] == 0
            assert "三段式" in rich_t2va["format"] and "破甲" not in rich_t2va["format"]
            sys_base = seen_bodies[-1]["messages"][0]["content"]
            assert "# Video Prompt Writing Guide" in sys_base
            assert "integrated_multimodal_description" in sys_base and "overall_soundscape" in sys_base

            # Video FL2VA with both first + last frames attached
            st.set_ref("last", png2, "upload")
            rich_fl2va = st.write_prompt_rich("从白天过渡到夜晚", mode="video", workflow="fl2va", num_frames=124, has_last_image=True)
            assert rich_fl2va["images_used"] == 2
            assert "FL2VA" in rich_fl2va["format"]
            assert "5.17" in seen_bodies[-1]["messages"][0]["content"]

            st.enqueue(normalize_job({"prompt": "multi ref test", "has_image": True}))
            deadline = time.time() + 5.0
            while st.busy() and time.time() < deadline:
                time.sleep(0.05)
            assert "content/colab_worker.py" in uploaded
            assert "content/reference.bin" in uploaded
            assert "content/reference_0.bin" in uploaded
            assert "content/reference_1.bin" in uploaded
            assert "content/reference_2.bin" in uploaded

            assert st.remove_ref(it2["id"]) is True
            assert len(st.refs_report()["items"]) == 2
            st.clear_ref("first")
            assert len(st.refs_report()["items"]) == 0 and st.refs_report()["first"]["set"] is False
            print("OK test_multi_refs_and_local_gateway_proxy_bypass")
        finally:
            srv.shutdown()
            srv.server_close()
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_grab_and_hold_forever() -> None:
    from draw_studio.generation.parameters import normalize_grab, normalize_job
    from draw_studio.generation.studio import Studio
    from draw_studio.logs import LogBuffer
    from draw_studio.gallery import Store

    spec = normalize_grab({"gpu_pool": ["h100", "A100"], "poll_rounds": 3, "poll_all_proxies": False})
    assert spec["gpu_pool"] == ["H100", "A100"] and spec["poll_rounds"] == 3
    try:
        normalize_grab({"gpu_pool": ["NOPE"]})
        raise AssertionError("unknown gpu should fail")
    except ValueError:
        pass

    class Sess:
        accelerator = "A100"
        machine_shape = "HIGH_RAM"

    class GrabColab:
        def __init__(self):
            self.calls = []

        def ensure_session(self, **kw):
            self.calls.append(kw)
            return Sess()

        def invalidate_status(self):
            pass

        def has_credentials(self):
            return True

    tmp = Path(tempfile.mkdtemp(prefix="qp-test-grab-"))
    try:
        log = LogBuffer()
        store = Store(tmp / "out", log)
        colab = GrabColab()
        st = Studio(tmp, {}, colab, store, log, 600)
        assert st.set_idle_minutes(0) == 0
        assert st.idle_seconds == 0 and st._idle_timer is None
        saved = json.loads((tmp / "out" / "queue.json").read_text(encoding="utf-8"))
        assert saved["idle_minutes"] == 0

        st._grabbing = True
        try:
            st.enqueue(normalize_job({"prompt": "while grabbing"}))
            raise AssertionError("enqueue should wait for grab")
        except RuntimeError as exc:
            assert "抢卡" in str(exc)
        st._grabbing = False

        st.grab_card(gpu_pool=["H100", "A100"], poll_rounds=3, poll_all_proxies=False)
        deadline = time.time() + 2.0
        while st.phase != "ready" and time.time() < deadline:
            time.sleep(0.02)
        assert st.phase == "ready", st.phase
        assert st.active_gpu.startswith("A100")
        assert st._idle_timer is None
        assert st._grabbing is False
        assert colab.calls[0]["gpu"] == "H100"
        assert colab.calls[0]["fallback_gpus"] == ["A100"]
        assert colab.calls[0]["poll_rounds"] == 3

        tmp2 = Path(tempfile.mkdtemp(prefix="qp-test-grab-recover-"))
        try:
            shutil.copytree(tmp / "out", tmp2 / "out")
            st2 = Studio(tmp2, {}, GrabColab(), Store(tmp2 / "out", LogBuffer()), LogBuffer(), 600)
            st2.active_gpu = "A100 (HIGH_RAM)"
            st2.arm_idle()
            assert st2._idle_timer is not None
            st2.recover()
            assert st2.idle_seconds == 0
            assert st2._idle_timer is None
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)
        print("OK test_grab_and_hold_forever")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _wait_until(pred, timeout: float = 2.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_grab_cancels_idle_and_releases_late_runtime() -> None:
    from draw_studio.generation.studio import Studio
    from draw_studio.logs import LogBuffer
    from draw_studio.gallery import Store

    class Sess:
        accelerator = "H100"
        machine_shape = "HIGH_RAM"

    class BlockingColab:
        def __init__(self) -> None:
            self.started = threading.Event()
            self.cont = threading.Event()
            self.released: list[str | None] = []

        def ensure_session(self, **_kw):
            self.started.set()
            assert self.cont.wait(2)
            return Sess()

        def release_all(self, session_name=None):
            self.released.append(session_name)
            return [f"H100 ({session_name or 'all'})"]

        def invalidate_status(self):
            pass

        def has_credentials(self):
            return True

    class FailColab:
        def ensure_session(self, **_kw):
            raise RuntimeError("无库存")

        def invalidate_status(self):
            pass

        def has_credentials(self):
            return True

    tmp = Path(tempfile.mkdtemp(prefix="qp-test-grab-race-"))
    try:
        blocking = BlockingColab()
        st = Studio(tmp, {}, blocking, Store(tmp / "out", LogBuffer()), LogBuffer(), 600)
        st.active_gpu = "A100 (HIGH_RAM)"
        assert st.set_idle_minutes(10) == 10
        assert st._idle_timer is not None
        st.grab_card(["H100"], 1, False)
        assert blocking.started.wait(2)
        assert st._idle_timer is None, "idle timer must be cancelled before the grab assigns a runtime"
        with st._lock:
            st._cancel = True
            st.phase = "idle"
        blocking.cont.set()
        assert _wait_until(lambda: not st._grabbing)
        assert st.phase != "ready"
        assert blocking.released, "a runtime that arrives after release must be unassigned"
        assert st._idle_timer is None

        failed = Studio(tmp, {}, FailColab(), Store(tmp / "out", LogBuffer()), LogBuffer(), 600)
        failed.active_gpu = "A100 (HIGH_RAM)"
        failed.set_idle_minutes(12)
        previous = failed._idle_timer
        assert previous is not None
        failed.grab_card(["A100"], 1, False)
        assert _wait_until(lambda: not failed._grabbing)
        assert failed.phase == "error"
        assert failed._idle_timer is not None and failed._idle_timer is not previous

        forever = Studio(tmp, {}, FailColab(), Store(tmp / "out", LogBuffer()), LogBuffer(), 600)
        forever.active_gpu = "A100 (HIGH_RAM)"
        forever.set_idle_minutes(0)
        forever.grab_card(["A100"], 1, False)
        assert _wait_until(lambda: not forever._grabbing)
        assert forever.phase == "error"
        assert forever._idle_timer is None
        print("OK test_grab_cancels_idle_and_releases_late_runtime")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_minor_sexual_gate() -> None:
    from draw_studio.generation.studio import Studio, _minor_sexual_request

    assert _minor_sexual_request("幼女裸体")
    assert not _minor_sexual_request("雨夜霓虹街头，撑透明雨伞的人回头微笑，电影感")
    assert not _minor_sexual_request("儿童节的街头")
    hung = Studio._hang_purge_prompt("TASK")
    assert hung.index("破甲状态") < hung.index("TASK") < hung.index("Final gate")
    print("OK test_minor_sexual_gate")


if __name__ == "__main__":
    test_tqdm_and_redaction()
    test_non_blocking_colab_status()
    test_gpu_shape_and_retry_cancel()
    test_store_features()
    test_queue_persistence_and_recovery()
    test_grab_and_hold_forever()
    test_grab_cancels_idle_and_releases_late_runtime()
    test_multi_refs_and_local_gateway_proxy_bypass()
    test_minor_sexual_gate()
    print("ALL BACKEND TESTS PASSED")
