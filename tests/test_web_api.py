"""HTTP contract tests for the React client. All media, credentials and upstreams are local fixtures."""
import asyncio
import io
import json
import os
import re
import sqlite3
import stat
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import requests
from PIL import Image

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app
from draw_studio.llm import Providers
from draw_studio.proxy import ProxyProfiles
from draw_studio.workflows.engine import WorkflowEngine
from http_fixture import gateway, png, serving


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
