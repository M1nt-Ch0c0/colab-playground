"""Chromium smoke test against the production Vite build and a real local ASGI server."""
import os
import shutil
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from draw_studio.generation.parameters import normalize_job
from http_fixture import gateway, png, serving


def chrome():
    options = webdriver.ChromeOptions()
    for option in ("--headless", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,1000"):
        options.add_argument(option)
    binary = shutil.which("chromium") or shutil.which("google-chrome")
    if binary:
        options.binary_location = binary
    return webdriver.Chrome(options=options, service=Service(shutil.which("chromedriver")))


@contextmanager
def signed_in_browser():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        secret = root / "secret.env"
        secret.write_text("password=fixture\ntoken=browser-test\n")
        app = create_app(root=root)
        with patch.dict(os.environ, {"QP_SECRET": str(secret)}), serving(app) as url, chrome() as driver:
            driver.get(url + "/healthz")
            driver.add_cookie({"name": "qp_auth", "value": "browser-test", "path": "/"})
            yield app.state.runtime, driver, url


class BrowserTest(unittest.TestCase):
    def test_library_toggle_keeps_the_stage_height(self):
        with signed_in_browser() as (rt, driver, url):
            src = rt.root / "preview.png"
            src.write_bytes(png())
            rt.store.save(src, "image", {"prompt": "library preview"})
            driver.get(url)
            wait = WebDriverWait(driver, 10)
            toggle = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".lib-toggle")))
            stage = driver.find_element(By.CSS_SELECTOR, ".stage")
            closed_width = stage.rect["width"]
            # The height drop used to occur between the close click and the dock's removal.
            driver.execute_script("""
                const stage = arguments[0], heights = [stage.clientHeight];
                const observer = new ResizeObserver(() => heights.push(stage.clientHeight));
                observer.observe(stage);
                window.finishStageMeasurement = () => { observer.disconnect(); return heights };
            """, stage)
            toggle.click()
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".tile"))).click()
            image = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".viewer img")))
            self.assertLess(stage.rect["width"], closed_width)
            dock = driver.find_element(By.CSS_SELECTOR, ".lib-dock")
            driver.find_element(By.TAG_NAME, "body").send_keys("g")
            wait.until(EC.staleness_of(dock))
            self.assertTrue(image.is_displayed())
            self.assertAlmostEqual(stage.rect["width"], closed_width, delta=1)
            heights = driver.execute_script("return window.finishStageMeasurement()")
            self.assertLessEqual(max(heights) - min(heights), 1, heights)

    def test_grab_failure_is_reported_once_per_attempt(self):
        with signed_in_browser() as (rt, driver, url):
            message = "A100 暂无空闲库存（HTTP 503），可换卡、换出口或稍后重试。"
            status = {**rt.colab.status_report(), "authed": True}
            rt.studio.set_phase("error", message)
            posting, accept = threading.Event(), threading.Event()
            grab_card = rt.studio.grab_card

            def delayed_post(**spec):
                posting.set()
                if not accept.wait(10):
                    raise RuntimeError("test grab request timed out")
                return grab_card(**spec)

            with patch.object(rt.colab, "status_report", return_value=status), \
                 patch.object(rt.colab, "has_credentials", return_value=True), \
                 patch.object(rt.studio, "grab_card", side_effect=delayed_post), \
                 patch.object(rt.studio, "_acquire_session", side_effect=RuntimeError(message)) as acquire:
                wait = WebDriverWait(driver, 10)
                error = (By.CSS_SELECTOR, ".toast.err")
                settings = (By.CSS_SELECTOR, 'button[title="设置"]')
                driver.get(url)
                first = wait.until(EC.visibility_of_element_located(error))
                self.assertEqual(first.text, message)
                wait.until(EC.staleness_of(first))  # allow the notification to expire naturally
                wait.until(EC.element_to_be_clickable(settings)).click()
                idle = (By.XPATH, "//button[normalize-space(.)='20 分钟']")
                wait.until(EC.element_to_be_clickable(idle)).click()
                wait.until(lambda d: "on" in d.find_element(*idle).get_attribute("class").split())
                self.assertFalse(driver.find_elements(*error), "A new status poll replayed the old error")

                driver.refresh()
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f'.status-pill[title="{message}"]')))
                self.assertFalse(driver.find_elements(*error), "Reload replayed the same failure")
                wait.until(EC.element_to_be_clickable(settings)).click()
                retry = (By.XPATH, "//button[normalize-space(.)='开始抢卡']")
                button = wait.until(EC.element_to_be_clickable(retry))
                try:
                    button.click()
                    self.assertTrue(posting.wait(3))
                    self.assertFalse(button.is_enabled())
                    self.assertIn("正在抢卡", button.text)
                finally:
                    accept.set()
                second = wait.until(EC.visibility_of_element_located(error))
                self.assertEqual(second.text, message)
                self.assertEqual(acquire.call_count, 1)
                second.find_element(By.CSS_SELECTOR, 'button[aria-label="关闭提示"]').click()
                wait.until(EC.staleness_of(second))
                idle = (By.XPATH, "//button[normalize-space(.)='30 分钟']")
                driver.find_element(*idle).click()
                wait.until(lambda d: "on" in d.find_element(*idle).get_attribute("class").split())
                self.assertFalse(driver.find_elements(*error), "A dismissed error returned")

    def test_grab_order_moves_persists_and_reaches_the_backend(self):
        with signed_in_browser() as (rt, driver, url):
            status = {**rt.colab.status_report(), "authed": True}
            with patch.object(rt.colab, "status_report", return_value=status), \
                 patch.object(rt.colab, "has_credentials", return_value=True), \
                 patch.object(rt.studio, "grab_card") as grab:
                driver.execute_script("localStorage.setItem('cs.grab', JSON.stringify(['G4', 'H100', 'A100']))")
                driver.get(url)
                wait = WebDriverWait(driver, 10)
                g4 = "G4 · RTX PRO 6000"

                def open_settings():
                    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[title="设置"]'))).click()
                    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".grab-row")))

                def labels():
                    return [e.text for e in driver.find_elements(By.CSS_SELECTOR, ".grab-row .gpu-main b")]

                def arrow(gpu, direction):
                    selector = f'.grab-row:has([aria-label="选择 {gpu}"]) button[aria-label="{direction}"]'
                    return driver.find_element(By.CSS_SELECTOR, selector)

                open_settings()
                self.assertEqual(labels(), [g4, "H100", "A100", "L4", "T4"])
                self.assertFalse(arrow(g4, "上移").is_enabled())
                self.assertFalse(arrow("A100", "下移").is_enabled())
                arrow(g4, "下移").click()
                self.assertEqual(labels(), ["H100", g4, "A100", "L4", "T4"])
                driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
                    "width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True,
                })
                arrow("A100", "上移").click()
                expected = ["H100", "A100", g4, "L4", "T4"]
                self.assertEqual(labels(), expected)
                driver.refresh()
                open_settings()
                self.assertEqual(labels(), expected)
                self.assertEqual([e.text for e in driver.find_elements(By.CSS_SELECTOR, ".grab-row .ord")], ["1", "2", "3"])
                driver.find_element(By.XPATH, "//button[normalize-space(.)='开始抢卡']").click()
                wait.until(lambda _: grab.called)
                self.assertEqual(grab.call_args.kwargs["gpu_pool"], ["H100", "A100", "G4"])

    def test_theme_toggle_uses_the_displayed_scheme(self):
        with signed_in_browser() as (_, driver, url):
            wait = WebDriverWait(driver, 10)
            toggle = (By.CSS_SELECTOR, 'button[title="切换亮色 / 暗色"]')

            def system_scheme(value):
                driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {
                    "features": [{"name": "prefers-color-scheme", "value": value}],
                })

            def scheme():
                return driver.execute_script("return getComputedStyle(document.documentElement).colorScheme")

            system_scheme("dark")
            driver.get(url)
            button = wait.until(EC.element_to_be_clickable(toggle))
            self.assertEqual(scheme(), "dark")
            button.click()
            self.assertEqual(scheme(), "light")
            driver.refresh()
            button = wait.until(EC.element_to_be_clickable(toggle))
            self.assertEqual(scheme(), "light")
            button.click()
            self.assertEqual(scheme(), "dark")

            driver.find_element(By.CSS_SELECTOR, 'button[title="设置"]').click()
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space(.)='跟随系统']"))).click()
            driver.find_element(By.CSS_SELECTOR, 'button[aria-label="关闭"]').click()
            wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".scrim")))
            system_scheme("light")
            wait.until(lambda _: scheme() == "light" and button.get_attribute("aria-label") == "切换到暗色")
            button.click()
            self.assertEqual(scheme(), "dark")

    def test_studio(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            secret = root / "secret.env"
            secret.write_text("password=browser-password\ntoken=browser-token\n")
            (root/"good.png").write_bytes(png())
            (root/"broken.png").write_bytes(b"broken image")
            app = create_app(root=root)
            with patch.dict(os.environ, {"QP_SECRET": str(secret)}), serving(app) as url, gateway() as (upstream, key, _):
                engine = app.state.runtime.workflows
                engine.save_workflow({"name": "浏览器素材审核", "steps": [
                    {"id": "first", "type": "asset_input", "pause_after": True},
                    {"id": "second", "type": "asset_input"},
                ]})
                with chrome() as driver:
                    driver.get(url)
                    wait = WebDriverWait(driver, 15)
                    def css(selector):
                        return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)), selector)
                    def click(selector):
                        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)), selector).click()
                    def text_click(tag, text):
                        wait.until(EC.element_to_be_clickable((By.XPATH, f"//{tag}[normalize-space(.)='{text}']"))).click()

                    pwd = css(".login input")
                    pwd.send_keys("incorrect", Keys.ENTER)
                    wait.until(lambda d: "密码不对" in css(".login").text)
                    pwd.clear()
                    pwd.send_keys("browser-password", Keys.ENTER)
                    click('button[title="设置"]')
                    text_click("button", "添加线路")
                    css("#proxy-label").send_keys("浏览器代理")
                    css("#proxy-url").send_keys("http://demo:fixture-pass@127.0.0.1:19080")
                    text_click("button", "保存线路")
                    box = 'section[aria-label="出口线路"]'
                    wait.until(lambda d: "http://***@127.0.0.1:19080" in css(box).text)
                    self.assertNotIn("fixture-pass", css(box).text)
                    click(box+' button[title="编辑线路"]')
                    css("#proxy-label").send_keys(Keys.CONTROL, "a", Keys.NULL, "代理已改名")
                    self.assertEqual(css("#proxy-url").get_attribute("value"), "")
                    text_click("button", "保存线路")
                    wait.until(lambda d: "代理已改名" in css(box).text)
                    text_click("button", "使用系统网络")
                    driver.refresh()
                    click('button[title="设置"]')
                    self.assertIn("代理已改名", css(box).text)
                    self.assertIn("当前使用系统网络", css(box).text)
                    text_click("button", "使用")
                    wait.until(lambda d: "使用中" in css(box).text)
                    click(box+' button[title="删除线路"]')
                    text_click("button", "删除")
                    wait.until(lambda d: "代理已改名" not in css(box).text and "当前使用系统网络" in css(box).text)
                    text_click("button", "添加服务商")
                    css("#llm-name").send_keys("测试网关")
                    css("#llm-base").send_keys(Keys.CONTROL, "a", Keys.NULL, upstream+"/open/v1")
                    css("#llm-key").send_keys(key)
                    switch = css('.llm-form button[role="switch"]')
                    self.assertEqual(switch.get_attribute("aria-checked"), "false")
                    switch.click()
                    text_click("button", "添加")
                    click('button[title="拉取模型列表"]')
                    wait.until(lambda _: "open-model" in css('.llm-row:has(button[title="拉取模型列表"])').text)
                    click('button[title="编辑"]')
                    self.assertEqual(css('.llm-form button[role="switch"]').get_attribute("aria-checked"), "true")
                    click('button[aria-label="关闭"]')
                    css("textarea[rows='2']").send_keys("画山")
                    click(".btn.rewrite")
                    wait.until(lambda d: d.find_element(By.CSS_SELECTOR, "textarea[rows='4']").get_property("value") == "open result")

                    text_click("button", "工作流")
                    text_click("b", "浏览器素材审核")
                    click(".step-h")
                    css('.step-cfg input[type=file]').send_keys(str(root/"good.png") + "\n" + str(root/"broken.png"))
                    css('img[alt="good.png"]')
                    self.assertEqual(engine.list_runs(), [])
                    text_click("button", "运行")
                    wait.until(lambda d: "图片" in css(".toasts").text and len(engine.list_runs()) == 1)
                    rid = engine.list_runs()[0]["id"]
                    self.assertEqual(engine.get_run(rid)["status"], "draft")
                    remove = css('button[aria-label="移除 broken.png"]')
                    driver.execute_script("arguments[0].click()", remove)
                    text_click("button", "运行")
                    wait.until(lambda d: "待审核" in css(".nav-badge").text)
                    self.assertEqual([r["id"] for r in engine.list_runs()], [rid])
                    run = engine.get_run(rid)
                    self.assertEqual(len(run["assets"]), 1)
                    self.assertEqual(run["workflow"]["steps"][0]["config"]["asset_files"], [run["assets"][0]["filename"]])
                    if not driver.find_elements(By.CSS_SELECTOR, ".step img[src*='thumb=1']"):
                        click(".step-h")
                    wait.until(lambda d: any(i.get_property("naturalWidth") == 480 for i in d.find_elements(By.CSS_SELECTOR, ".step img[src*='thumb=1']")))
                    text_click("button", "继续")
                    wait.until(lambda d: engine.get_run(rid)["status"] == "done")

                    driver.get(url + "/legacy")
                    click("#settingsBtn")
                    css("#proxyLabel").send_keys("兼容页面线路")
                    css("#customProxyUrl").send_keys("http://user:fixture-pass@127.0.0.1:18080")
                    click("#saveCustomProxyBtn")
                    wait.until(lambda d: "兼容页面线路" in css("#proxyChips").text)
                    Select(css("#proxyEditTarget")).select_by_visible_text("兼容页面线路")
                    self.assertEqual(css("#customProxyUrl").get_attribute("value"), "")
                    css("#proxyLabel").send_keys(Keys.CONTROL, "a", Keys.NULL, "已编辑线路")
                    click("#saveCustomProxyBtn")
                    wait.until(lambda d: "已编辑线路" in css("#proxyChips").text)
                    Select(css("#proxyEditTarget")).select_by_visible_text("已编辑线路")
                    click("#removeProxyBtn")
                    click("#cOk")
                    wait.until(lambda d: "已编辑线路" not in css("#proxyChips").text)
                    driver.get(url + "/")
                    click('button[title="退出登录"]')
                    css(".login input")
                    self.assertIsNone(driver.get_cookie("qp_auth"))


    def test_workflow_step_controls(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            secret = root / "secret.env"
            secret.write_text("password=fixture\ntoken=browser-test\n")
            app = create_app(root=root)
            with patch.dict(os.environ, {"QP_SECRET": str(secret)}), serving(app) as url, chrome() as driver:
                engine = app.state.runtime.workflows
                engine.save_workflow({"name": "表单参数测试", "steps": [
                    {"id": "gate", "type": "asset_input", "pause_after": True},
                    {"id": "image", "name": "测试生图", "type": "image_gen"},
                    {"id": "video", "name": "测试视频", "type": "video_gen"},
                    {"id": "join", "name": "测试拼接", "type": "video_stitch"},
                ]})
                driver.get(url + "/healthz")
                driver.add_cookie({"name": "qp_auth", "value": "browser-test", "path": "/"})
                driver.get(url)
                wait = WebDriverWait(driver, 12)

                def click_text(tag, label):
                    wait.until(EC.element_to_be_clickable((By.XPATH, f"//{tag}[normalize-space(.)='{label}']"))).click()

                def open_step(name):
                    row = wait.until(EC.presence_of_element_located((By.XPATH, f"//li[.//b[normalize-space(.)='{name}']]")))
                    row.find_element(By.CSS_SELECTOR, ".step-h").click()
                    def expanded(d):
                        panels = row.find_elements(By.CSS_SELECTOR, ".step-b")
                        return panels and d.execute_script("""
                            const panel = arguments[0];
                            return Number(getComputedStyle(panel).opacity) === 1
                                && panel.clientHeight >= panel.scrollHeight - 1;
                        """, panels[0])
                    wait.until(expanded, f"Step panel did not finish expanding: {name}")
                    return row

                def dropdown(row, label):
                    locator = (By.XPATH, f".//label[span[normalize-space(.)='{label}']]/select")
                    return Select(wait.until(lambda _: EC.element_to_be_clickable(locator)(row)))

                def toggle(row, label):
                    return row.find_element(By.XPATH, f".//button[@role='switch' and normalize-space(.)='{label}']")

                click_text("button", "工作流")
                click_text("b", "表单参数测试")
                image = open_step("测试生图")
                dropdown(image, "首选 GPU").select_by_value("L4")
                backups = image.find_element(By.CSS_SELECTOR, "[role=group]")
                self.assertFalse(backups.find_elements(By.CSS_SELECTOR, "[aria-pressed=true]"))
                backups.find_element(By.CSS_SELECTOR, '[aria-label=H100]').click()
                backups.find_element(By.CSS_SELECTOR, '[aria-label=A100]').click()
                toggle(image, "每轮使用全部代理").click()
                toggle(image, "每轮使用全部代理").click()
                clip = open_step("测试视频")
                dropdown(clip, "首选 GPU").select_by_value("T4")
                toggle(clip, "每轮使用全部代理").click()
                toggle(clip, "自动显存卸载").click()
                join = open_step("测试拼接")
                ids = join.find_element(By.XPATH, ".//label[span[normalize-space(.)='追加作品编号']]/input")
                ids.send_keys("001,")
                self.assertEqual(ids.get_property("value"), "001,")
                ids.send_keys("002，003 004")
                ids.send_keys(Keys.CONTROL, "a", Keys.NULL, Keys.CONTROL, "x", Keys.NULL)
                self.assertEqual(ids.get_property("value"), "")
                ids.send_keys(Keys.CONTROL, "v", Keys.NULL)
                wait.until(lambda _: ids.get_property("value") == "001,002，003 004")
                transition = dropdown(join, "转场")
                transition.select_by_visible_text("硬切")
                self.assertEqual(transition.first_selected_option.get_property("value"), "cut")
                # Inspect the JSON body before server normalisation can conceal a form regression.
                with patch.object(engine, "create_run", wraps=engine.create_run) as create:
                    click_text("button", "运行")
                    wait.until(lambda _: create.called)
                    configs = {step["id"]: step["config"] for step in create.call_args.args[0]["workflow"]["steps"]}
                self.assertEqual((configs["image"]["gpu"], configs["image"]["gpu_pool"]), ("L4", ["L4", "H100", "A100"]))
                self.assertIs(configs["image"]["poll_all_proxies"], False)
                self.assertEqual((configs["video"]["gpu"], configs["video"]["gpu_pool"]), ("T4", ["T4"]))
                self.assertIs(configs["video"]["poll_all_proxies"], True)
                self.assertIs(configs["video"]["auto_offload"], False)
                self.assertEqual(configs["join"]["transition"], "cut")
                self.assertEqual(configs["join"]["clip_round_ids"], ["001", "002", "003", "004"])
                wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".run-head .tag"), "待审核"))
                # The persisted run uses the same controls and autosaves without re-stringifying them.
                image = open_step("测试生图")
                with patch.object(engine, "update_run_config", wraps=engine.update_run_config) as update:
                    dropdown(image, "首选 GPU").select_by_value("G4")
                    toggle(image, "每轮使用全部代理").click()
                    wait.until(lambda _: update.called and update.call_args.args[1]["workflow"]["steps"][1]["config"]["poll_all_proxies"] is True)
                    config = update.call_args.args[1]["workflow"]["steps"][1]["config"]
                self.assertEqual((config["gpu"], config["gpu_pool"]), ("G4", ["G4"]))

    def test_cleanup_refreshes_preview_in_both_clients(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy), signed_in_browser() as (rt, driver, url):
                src = rt.root / "cleanup-fixture.png"
                src.write_bytes(png())
                rid = rt.store.save(src, "image", {"prompt": "cleanup fixture"})
                driver.get(url + ("/legacy" if legacy else "/"))
                wait = WebDriverWait(driver, 12)
                if legacy:
                    wait.until(EC.element_to_be_clickable((By.ID, "galleryToggleBtn"))).click()
                    trigger = (By.ID, "cleanBtn")
                    selector = ".modal #cGo"
                    age = (By.ID, "cDays")
                    kind = (By.ID, "cKind")
                else:
                    driver.execute_script("localStorage.setItem('cs.libopen', 'true')")
                    driver.refresh()
                    trigger = (By.CSS_SELECTOR, 'button[title="清理旧作品"]')
                    selector = '[role=dialog][aria-label="清理旧作品"] button.solid-danger'
                    age = (By.CSS_SELECTOR, '[role=dialog][aria-label="清理旧作品"] input[type=number]')
                    kind = (By.CSS_SELECTOR, '[role=dialog][aria-label="清理旧作品"] select')
                wait.until(EC.element_to_be_clickable(trigger)).click()
                wait.until(EC.element_to_be_clickable(age)).send_keys(Keys.CONTROL, "a", Keys.NULL, "0")
                button = (By.CSS_SELECTOR, selector)
                wait.until(EC.element_to_be_clickable(button))
                Select(driver.find_element(*kind)).select_by_value("video")
                self.assertFalse(driver.find_element(*button).is_enabled())
                wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".modal .preview-box"), "没有符合条件"))
                self.assertIsNotNone(rt.store.media_path(rid))
                Select(driver.find_element(*kind)).select_by_value("image")
                wait.until(EC.element_to_be_clickable(button)).click()
                wait.until(lambda _: bool(rt.store.trash_list()["count"]))
                self.assertIsNone(rt.store.media_path(rid))
                self.assertEqual(rt.store.trash_list()["items"][0]["id"], rid)

    def test_reuse_comfy_round_submits_stored_combination(self):
        with signed_in_browser() as (rt, driver, url):
            src = rt.root / "fixture.png"
            src.write_bytes(png())
            combo = {"template": "flux", "sampler": "heun", "scheduler": "karras", "clip_type": "flux2", "denoise": 0.65,
                     "diffusion": "fixture/history :: diffusion.safetensors", "text_encoder": "fixture/history :: clip.safetensors",
                     "vae": "fixture/history :: vae.safetensors"}
            meta = normalize_job({"engine": "comfyui", "prompt": "saved combo", "comfy": combo, "steps": 22, "seed": 0})
            # Cover parsed links with raw + url, older url-only objects, and plain strings.
            url_only = meta["comfy"]["text_encoder"]["url"]
            meta["comfy"]["text_encoder"] = {"url": url_only}
            meta["comfy"]["vae"] = combo["vae"]
            rt.store.save(src, "image", meta)
            rt.store.save(src, "image", {"prompt": "missing combo", "engine": "comfyui"})
            driver.execute_script("""localStorage.setItem('cs.libopen', 'true');
                localStorage.setItem('cs.draft', JSON.stringify({comfyDiff: 'wrong', comfyTe: 'wrong', comfyVae: 'wrong'}))""")
            # Accept the generation request locally and inspect exactly what the queue receives.
            status = rt.colab.status_report()
            with patch.object(rt.colab, "status_report", return_value=status), patch.object(rt.colab, "has_credentials", return_value=True), \
                 patch.object(rt.studio, "enqueue", return_value=[{"id": "fixture"}]) as enqueue:
                driver.get(url)
                wait = WebDriverWait(driver, 10)

                def reuse(title):
                    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'.tile[title="{title}"]'))).click()
                    # A toast from the previous submit can temporarily cover the toolbar.
                    wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space(.)='复用参数']"))).send_keys(Keys.ENTER)
                    wait.until(lambda d: d.find_element(By.CSS_SELECTOR, 'textarea[rows="4"]').get_property("value") == title)

                def generate():
                    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.go"))).click()

                for count in (1, 2):
                    reuse("saved combo")
                    generate()
                    wait.until(lambda _: enqueue.call_count == count)
                    job = enqueue.call_args.args[0]
                    self.assertEqual((job["engine"], job["steps"], job["seed"]), ("comfyui", 22, 0))
                    for key in ("template", "sampler", "scheduler", "clip_type", "denoise"):
                        self.assertEqual(job["comfy"][key], combo[key])
                    self.assertEqual([job["comfy"][key]["raw"] for key in ("diffusion", "text_encoder", "vae")],
                                     [combo["diffusion"], url_only, combo["vae"]])
                    if count == 1:
                        reuse("missing combo")
                        generate()
                        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".toasts"), "填齐"))
                        self.assertEqual(enqueue.call_count, 1)

    def test_review_edits_finish_before_resume_and_retry(self):
        cases = [("llm_script", "scenes", "keyframe_prompt", "image_gen", "关键帧提示词"),
                 ("h3_prompt", "items", "video_prompt", "video_gen", "视频提示词")]
        for source, group, field, downstream, label in cases:
            with self.subTest(source=source), signed_in_browser() as (rt, driver, url):
                engine = rt.workflows
                is_retry = downstream == "video_gen"
                run = engine.create_run({"topic": "fixture", "workflow": {"name": "审核保存", "steps": [
                    {"id": "review", "name": "审核产出", "type": source, "pause_after": True},
                    {"id": "generate", "name": "使用审核结果", "type": downstream,
                     "config": {"scenes_from": "review", "prompts_from": "review", "ref_sources": [], "workflow": "t2va"}},
                ]}})
                rid = run["id"]
                output = {group: [{"title": f"shot {n}", field: f"old {n}"} for n in (1, 2)]}
                wait = WebDriverWait(driver, 12)
                with patch.object(engine, "_run_step", return_value=output):
                    engine.start_run(rid)
                    wait.until(lambda _: engine.get_run(rid)["status"] == "paused")
                driver.get(url)
                wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'工作流')]"))).click()

                def open_step(name):
                    row = wait.until(EC.presence_of_element_located((By.XPATH, f"//li[.//b[normalize-space(.)='{name}']]")))
                    row.find_element(By.CSS_SELECTOR, ".step-h").click()
                    def expanded(d):
                        panels = row.find_elements(By.CSS_SELECTOR, ".step-b")
                        return panels and d.execute_script("""
                            const panel = arguments[0];
                            return Number(getComputedStyle(panel).opacity) === 1
                                && panel.clientHeight >= panel.scrollHeight - 1;
                        """, panels[0])
                    wait.until(expanded, f"Step panel did not finish expanding: {name}")
                    return row

                if is_retry:
                    target = open_step("使用审核结果")
                    go = target.find_element(By.XPATH, ".//button[normalize-space(.)='只跑这一步']")
                else:
                    go = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space(.)='继续']")))
                row = open_step("审核产出")
                fields = row.find_elements(By.CSS_SELECTOR, f'textarea[aria-label="{label}"]')
                began, release = threading.Event(), threading.Event()
                save = engine.update_step_output

                def delayed_write(*args):
                    if not began.is_set():
                        began.set()
                        if not release.wait(12):
                            raise RuntimeError("test save timed out")
                        if is_retry:
                            raise ValueError("模拟产出保存失败")
                    return save(*args)

                with patch.object(engine, "update_step_output", side_effect=delayed_write), \
                     patch.object(engine, "start_run", wraps=engine.start_run) as start, \
                     patch.object(rt.studio, "colab", SimpleNamespace(has_credentials=lambda: True)), \
                     patch.object(rt.studio, "enqueue_with_refs", return_value=[{"id": "job"}]) as enqueue, \
                     patch.object(rt.studio, "wait_for_job", return_value={"status": "done", "round_id": "001"}):
                    try:
                        fields[0].send_keys(Keys.CONTROL, "a", Keys.NULL, "edited 1")
                        fields[1].click()  # blur starts the first save
                        self.assertTrue(began.wait(3))
                        if not is_retry:
                            topic = driver.find_element(By.CSS_SELECTOR, ".run-head textarea")
                            topic.send_keys(Keys.CONTROL, "a", Keys.NULL, "edited topic")
                        fields[1].send_keys(Keys.CONTROL, "a", Keys.NULL, "edited 2")
                        go.click()
                        wait.until(lambda d: d.find_element(By.CSS_SELECTOR, ".run").get_property("inert"))
                        self.assertFalse(start.called)
                    finally:
                        release.set()
                    if is_retry:
                        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".toasts"), "模拟产出保存失败"))
                        wait.until(lambda d: not d.find_element(By.CSS_SELECTOR, ".run").get_property("inert"))
                        self.assertFalse(start.called)
                        self.assertFalse(enqueue.called)
                        self.assertEqual(engine.get_run(rid)["status"], "paused")
                        self.assertEqual([box.get_property("value") for box in fields], ["edited 1", "edited 2"])
                        go.click()  # retry the save and execution without having to retype either edit
                    wait.until(lambda _: engine.get_run(rid)["status"] == "done")
                    self.assertEqual(start.call_count, 1)
                    self.assertEqual([call.args[0]["prompt"] for call in enqueue.call_args_list], ["edited 1", "edited 2"])
                    finished = engine.get_run(rid)
                    if not is_retry:
                        self.assertEqual(finished["topic"], "edited topic")
                    saved = finished["step_states"]["review"]["output"][group]
                    self.assertEqual([item[field] for item in saved], ["edited 1", "edited 2"])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=2)
