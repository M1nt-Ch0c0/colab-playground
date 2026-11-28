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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from draw_studio.api import workflows as workflow_api
from draw_studio.generation.parameters import normalize_job
from draw_studio.workflows.harness_errors import HarnessError
from http_fixture import gateway, mp4, png, serving

SHORTCUT = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL


def chrome():
    options = webdriver.ChromeOptions()
    for option in ("--headless", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,1000"):
        options.add_argument(option)
    # The hosted Ubuntu runner's Chromium lacks the H.264/AAC codecs used by the MP4 tests.
    binary = shutil.which("google-chrome") or shutil.which("chromium")
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

    def test_viewer_and_lightbox_fit_portrait_images(self):
        with signed_in_browser() as (rt, driver, url):
            portrait = rt.root / "portrait.png"
            portrait.write_bytes(png(size=(1024, 1536), color="teal"))
            square = rt.root / "square.png"
            square.write_bytes(png(size=(1024, 1024), color="coral"))
            rt.store.save(portrait, "image", {"prompt": "portrait preview", "width": 1024, "height": 1536})
            rt.store.save(square, "image", {"prompt": "square preview", "width": 1024, "height": 1024})
            driver.get(url)
            wait = WebDriverWait(driver, 10)
            if not driver.find_elements(By.CSS_SELECTOR, ".lib-dock"):
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".lib-toggle"))).click()
            wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, ".lib-grid .tile")) == 2)

            def measure_fit(box_sel, img_sel, bar_sel=None, prev_src=""):
                wait.until(lambda d: d.execute_script("""
                    const boxes = document.querySelectorAll(arguments[0]);
                    const img = document.querySelector(arguments[1]);
                    return boxes.length === 1 && !!img && img.complete && img.naturalWidth > 0
                        && (!arguments[2] || img.src !== arguments[2])
                        && getComputedStyle(boxes[0]).transform === 'none';
                """, box_sel, img_sel, prev_src))
                return driver.execute_script("""
                    const box = document.querySelector(arguments[0]).getBoundingClientRect();
                    const imgEl = document.querySelector(arguments[1]);
                    const img = imgEl.getBoundingClientRect();
                    const bar = arguments[2] ? document.querySelector(arguments[2]).getBoundingClientRect() : null;
                    return {
                        src: imgEl.src,
                        naturalWidth: imgEl.naturalWidth,
                        naturalHeight: imgEl.naturalHeight,
                        fits: img.top >= box.top - 1 && img.bottom <= box.bottom + 1
                              && img.left >= box.left - 1 && img.right <= box.right + 1,
                        centeredV: Math.abs((img.top - box.top) - (box.bottom - img.bottom)) <= 2,
                        centeredH: Math.abs((img.left - box.left) - (box.right - img.right)) <= 2,
                        aspectDiff: Math.abs((img.width / img.height) - (imgEl.naturalWidth / imgEl.naturalHeight)),
                        clearsBar: bar ? img.bottom <= bar.top + 1 : true,
                    };
                """, box_sel, img_sel, bar_sel)

            seen_dims = set()
            prev_src = ""
            for index in range(2):
                tiles = driver.find_elements(By.CSS_SELECTOR, ".lib-grid .tile")
                tiles[index].click()
                metrics = measure_fit(".viewer", ".viewer img", prev_src=prev_src)
                prev_src = metrics["src"]
                dims = (metrics["naturalWidth"], metrics["naturalHeight"])
                seen_dims.add(dims)
                self.assertTrue(metrics["fits"], (dims, metrics))
                self.assertTrue(metrics["centeredV"], (dims, metrics))
                self.assertTrue(metrics["centeredH"], (dims, metrics))
                self.assertLess(metrics["aspectDiff"], 0.02, (dims, metrics))
                if dims == (1024, 1536):
                    expand = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".viewer .vnav.expand")))
                    driver.execute_script("arguments[0].click()", expand)
                    lb_metrics = measure_fit(".lb-media", ".lb-media img", ".lb-bar")
                    self.assertEqual((lb_metrics["naturalWidth"], lb_metrics["naturalHeight"]), (1024, 1536))
                    self.assertTrue(lb_metrics["fits"], lb_metrics)
                    self.assertTrue(lb_metrics["centeredV"], lb_metrics)
                    self.assertTrue(lb_metrics["centeredH"], lb_metrics)
                    self.assertLess(lb_metrics["aspectDiff"], 0.02, lb_metrics)
                    self.assertTrue(lb_metrics["clearsBar"], lb_metrics)
                    driver.find_element(By.CSS_SELECTOR, '.lb-bar button[aria-label="关闭"]').click()
                    wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".lightbox")))
            self.assertEqual(seen_dims, {(1024, 1536), (1024, 1024)})

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
                driver.execute_script("localStorage.setItem('colabreel.grab', JSON.stringify(['G4', 'H100', 'A100']))")
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

    def test_old_storage_keys_migrate_before_first_render(self):
        with signed_in_browser() as (_, driver, url):
            wait = WebDriverWait(driver, 10)
            driver.execute_script("""localStorage.clear();
                localStorage.setItem('cs.draft', JSON.stringify({prompt: '旧版草稿'}));
                localStorage.setItem('cs.theme', JSON.stringify('dark'));""")
            driver.get(url)
            wait.until(lambda d: d.find_element(By.CSS_SELECTOR, 'textarea[rows="4"]').get_property("value") == "旧版草稿")
            self.assertEqual(driver.execute_script("return document.documentElement.dataset.theme"), "dark")
            self.assertEqual(driver.execute_script("return localStorage.getItem('cs.draft')"), '{"prompt":"旧版草稿"}')

            # 旧版页面用自己的主题 key，不能改写工作台的设置。
            driver.get(url + "/legacy")
            wait.until(EC.element_to_be_clickable((By.ID, "themeBtn")))
            self.assertEqual(driver.execute_script("return localStorage.getItem('colabreel.theme')"), '"dark"')
            self.assertEqual(driver.execute_script("return localStorage.getItem('colabreel.legacy.theme')"), "light")

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
                    css("#proxy-label").send_keys(SHORTCUT, "a", Keys.NULL, "代理已改名")
                    self.assertEqual(css("#proxy-url").get_attribute("value"), "")
                    text_click("button", "保存线路")
                    wait.until(lambda d: "代理已改名" in css(box).text)
                    text_click("button", "使用系统网络")
                    wait.until(lambda _: "当前使用系统网络" in css(box).text)
                    driver.refresh()
                    click('button[title="设置"]')
                    wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, box), "代理已改名"))
                    self.assertIn("当前使用系统网络", css(box).text)
                    text_click("button", "使用")
                    wait.until(lambda d: "使用中" in css(box).text)
                    click(box+' button[title="删除线路"]')
                    text_click("button", "删除")
                    wait.until(lambda d: "代理已改名" not in css(box).text and "当前使用系统网络" in css(box).text)
                    text_click("button", "添加服务商")
                    css("#llm-name").send_keys("测试网关")
                    css("#llm-base").send_keys(SHORTCUT, "a", Keys.NULL, upstream+"/open/v1")
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
                    css("#proxyLabel").send_keys(SHORTCUT, "a", Keys.NULL, "已编辑线路")
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
                source = app.state.runtime.store.save(mp4(root / "blocking.mp4"), "video", {"prompt": "white model"})
                engine.save_workflow({"name": "表单参数测试", "steps": [
                    {"id": "gate", "type": "asset_input", "pause_after": True},
                    {"id": "image", "name": "测试生图", "type": "image_gen"},
                    {"id": "video", "name": "测试视频", "type": "video_gen"},
                    {"id": "next", "name": "后续镜头", "type": "video_gen"},
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
                dropdown(clip, "视频模式").select_by_value("ref2va")
                click_text("button", "从作品库选视频")
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.trash-tile[title="white model"]'))).click()
                wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, '[role="dialog"]')))
                dropdown(clip, "参考视频用途").select_by_value("motion")
                dropdown(clip, "首选 GPU").select_by_value("T4")
                toggle(clip, "每轮使用全部代理").click()
                toggle(clip, "自动显存卸载").click()
                follow = open_step("后续镜头")
                dropdown(follow, "视频模式").select_by_value("ref2va")
                dropdown(follow, "上游参考视频").select_by_value("video")
                dropdown(follow, "参考视频用途").select_by_value("continue")
                join = open_step("测试拼接")
                ids = join.find_element(By.XPATH, ".//label[span[normalize-space(.)='追加作品编号']]/input")
                ids.send_keys("001,")
                self.assertEqual(ids.get_property("value"), "001,")
                ids.send_keys("002，003 004")
                ids.send_keys(SHORTCUT, "a", Keys.NULL, SHORTCUT, "x", Keys.NULL)
                self.assertEqual(ids.get_property("value"), "")
                ids.send_keys(SHORTCUT, "v", Keys.NULL)
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
                self.assertEqual((configs["video"]["video_round_id"], configs["video"]["video_task"]), (source, "motion"))
                self.assertEqual((configs["next"]["video_from"], configs["next"]["video_task"]), ("video", "continue"))
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
                    driver.execute_script("localStorage.setItem('colabreel.libopen', 'true')")
                    driver.refresh()
                    trigger = (By.CSS_SELECTOR, 'button[title="清理旧作品"]')
                    selector = '[role=dialog][aria-label="清理旧作品"] button.solid-danger'
                    age = (By.CSS_SELECTOR, '[role=dialog][aria-label="清理旧作品"] input[type=number]')
                    kind = (By.CSS_SELECTOR, '[role=dialog][aria-label="清理旧作品"] select')
                wait.until(EC.element_to_be_clickable(trigger)).click()
                wait.until(EC.element_to_be_clickable(age)).send_keys(SHORTCUT, "a", Keys.NULL, "0")
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

    def test_video_edit_continuation_and_motion_reference(self):
        with signed_in_browser() as (rt, driver, url):
            previous = mp4(rt.root / "previous.mp4", 3, audio=True)
            rid = rt.store.save(previous, "video", {"prompt": "previous shot", "width": 768, "height": 512})
            character = rt.root / "character.png"
            character.write_bytes(png((192, 256), "maroon"))
            character_id = rt.store.save(character, "image", {"prompt": "角色正面", "width": 192, "height": 256})
            rt.studio.set_ref("first", png(), "upload")
            rt.studio.add_ref(png(color="green"), "wardrobe")
            driver.execute_script("localStorage.setItem('colabreel.libopen', 'true')")
            status = rt.colab.status_report()
            with patch.object(rt.colab, "status_report", return_value=status), patch.object(rt.colab, "has_credentials", return_value=True), \
                 patch.object(rt.studio, "enqueue", return_value=[{"id": "fixture"}]) as enqueue:
                driver.get(url)
                wait = WebDriverWait(driver, 10)
                def button(label):
                    return wait.until(EC.element_to_be_clickable((By.XPATH, f"//button[normalize-space(.)='{label}']")))
                def submit(n):
                    driver.find_element(By.CSS_SELECTOR, "button.go").click()
                    wait.until(lambda _: enqueue.call_count == n)
                    return enqueue.call_args.args[0]
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.tile[title="previous shot"]'))).click()
                button("翻修视频").send_keys(Keys.ENTER)
                wait.until(lambda d: d.find_element(By.CSS_SELECTOR, "video.ref-video").get_property("duration") == 3)
                driver.find_element(By.CSS_SELECTOR, 'textarea[rows="4"]').send_keys("keep the camera movement")
                edit = submit(1)
                self.assertEqual((edit["video_task"], edit["has_image"]), ("edit", False))
                button("续拍下一段").click()
                self.assertEqual(submit(2)["video_reference_id"], edit["video_reference_id"])
                self.assertEqual(enqueue.call_args.args[0]["video_task"], "continue")
                button("白模 + 人设").click()
                button("从作品库选人设图").click()
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.trash-tile[title="角色正面"]'))).click()
                wait.until(lambda d: d.find_element(By.CSS_SELECTOR, 'img[alt="人设图"]').get_property("naturalWidth") == 192)
                self.assertEqual([item["source"] for item in rt.studio.refs_report()["items"]], [f"round:{character_id}", "wardrobe"])
                alternate = rt.root / "alternate.png"
                alternate.write_bytes(png((128, 256), "blue"))
                driver.find_element(By.CSS_SELECTOR, 'input[aria-label="上传替换人设图"]').send_keys(str(alternate))
                wait.until(lambda d: d.find_element(By.CSS_SELECTOR, 'img[alt="人设图"]').get_property("naturalWidth") == 128)
                self.assertEqual(rt.studio.ref_blobs(), [alternate.read_bytes(), png(color="green")])
                driver.find_element(By.CSS_SELECTOR, 'input[accept^="video/mp4"]').send_keys(str(mp4(rt.root / "blocking.mp4")))
                wait.until(lambda d: d.find_element(By.CSS_SELECTOR, "video.ref-video").get_property("duration") == 2)
                motion = submit(3)
                self.assertNotEqual(motion["video_reference_id"], edit["video_reference_id"])
                self.assertEqual((motion["video_task"], motion["has_image"]), ("motion", True))
                button("从作品库选视频").click()
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.trash-tile[title="previous shot"]'))).click()
                wait.until(lambda _: rt.studio.refs_report()["video"]["source"] == "round:" + rid)
                button("参考图").click()
                self.assertNotIn("video_reference_id", submit(4))

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
            driver.execute_script("""localStorage.setItem('colabreel.libopen', 'true');
                localStorage.setItem('colabreel.draft', JSON.stringify({comfyDiff: 'wrong', comfyTe: 'wrong', comfyVae: 'wrong'}))""")
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

    def test_import_mask_retry_and_video_tools(self):
        with signed_in_browser() as (rt, driver, url):
            held = {"gpu": "A100", "name": "local fixture", "shape": "test", "endpoint": ""}
            self.enterContext(patch.object(rt.colab, "status_report", return_value={
                **rt.colab.status_report(), "authed": True, "ok": True, "sessions": [held],
            }))
            picture = rt.root / "painting.png"
            picture.write_bytes(png((640, 480)))
            clip = mp4(rt.root / "movement.mp4", 3, audio=True)
            driver.execute_script("localStorage.setItem('colabreel.libopen','true')")
            driver.get(url)
            wait = WebDriverWait(driver, 12)
            def css(selector):
                return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            def button(label):
                return wait.until(EC.element_to_be_clickable((By.XPATH, f"//button[normalize-space(.)='{label}']")))
            css('input[aria-label="选择本地素材"]').send_keys(str(picture))
            button("局部改图").click()
            canvas = css(".mask-canvas")
            ActionChains(driver).move_to_element(canvas).click_and_hold().move_by_offset(20, 10).release().perform()
            button("使用这个选区").click()
            button("调整选区")
            css('textarea[rows="4"]').send_keys("red dot")
            with patch.object(rt.colab, "has_credentials", return_value=True), \
                 patch.object(rt.studio, "_acquire_session", side_effect=RuntimeError("fixture offline")):
                button("开始生成").click()
                retry = button("重试")
                original = rt.studio.snapshot()["history"][0]["id"]
                with patch.object(rt.studio, "_run_loop"):
                    retry.send_keys(Keys.ENTER)
                    wait.until(lambda _: rt.studio.find_job(original)["retried_as"])
                    mask = rt.studio._queue[0]["payload"]["edit_mask"]
                    self.assertEqual(mask["source_id"], "001")
                    self.assertGreaterEqual(len(mask["strokes"][0]["points"]), 2)
                rt.studio.clear_queue()
            css('input[aria-label="选择本地素材"]').send_keys(str(clip))
            button("取帧与裁段").click()
            wait.until(lambda _: css("video.clip-preview").get_property("duration") == 3)
            button("裁段").click()
            end = css('input[type="number"][max="3"][value="3"]')
            end.send_keys(SHORTCUT, "a", Keys.NULL, "2")
            css('.edit-toolbar input[type="checkbox"]').click()
            button("保存片段 · 2 秒").click()
            wait.until(lambda _: rt.store.latest()["prompt"].endswith("0–2 秒"))
            wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".clip-preview")))
            self.assertTrue(rt.store.latest()["muted"])
            driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
            css('button[aria-label="收起作品库"]').click()
            wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".lib-dock")))
            button("取帧与裁段").click()
            css("video.clip-preview")
            self.assertTrue(driver.execute_script("const b=document.querySelector('.modal').getBoundingClientRect();return innerWidth===390 && b.left>=0 && b.right<=innerWidth"))
            button("提取尾帧").click()
            wait.until(lambda _: rt.store.latest()["media_operation"] == "frame")
            self.assertEqual(rt.store.latest()["source_rounds"], ["003"])
            button("设为尾帧").send_keys(Keys.ENTER)
            wait.until(lambda _: rt.studio.refs_report()["last"]["set"])
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'img[alt="尾帧"]')))
            button("从作品库选首帧").send_keys(Keys.ENTER)
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.trash-tile[title="painting.png"]'))).click()
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'img[alt="首帧"]')))
            css('button[aria-label="本次不用首帧"]').send_keys(Keys.ENTER)
            wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, 'img[alt="首帧"]')))
            self.assertEqual(rt.studio.refs_report()["first"]["source"], "round:001")
            with patch.object(rt.colab, "has_credentials", return_value=True), patch.object(rt.studio, "_run_loop"):
                button("开始生成").click()
                wait.until(lambda _: len(rt.studio.snapshot()["queue"]) == 1)
                payload = rt.studio._queue[0]["payload"]
                self.assertEqual((payload["workflow"], payload["has_image"], payload["has_last_image"]), ("fl2va", False, True))

    def test_crop_with_desktop_preset_and_touch_selection(self):
        with signed_in_browser() as (rt, driver, url):
            source = rt.root / "character.png"
            source.write_bytes(png((800, 400)))
            rid = rt.store.save(source, "image", {"prompt": "人设三视图"})
            driver.get(f"{url}/?tool=crop&round={rid}")
            wait = WebDriverWait(driver, 8)
            def button(label):
                return wait.until(EC.element_to_be_clickable((By.XPATH, f"//*[@role='dialog']//button[normalize-space(.)='{label}']")))
            button("1:1").click()
            wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, 'output[aria-label="选区尺寸"]'), "400 × 400"))
            button("重选").click()
            driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
            driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {"enabled": True})
            canvas = driver.find_element(By.CSS_SELECTOR, ".crop-canvas")
            bounds = driver.execute_script("const r=arguments[0].getBoundingClientRect();return [r.x,r.y,r.width,r.height]", canvas)
            x, y, width, height = bounds
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + width, 390)
            for event, fraction in [("touchStart", .2), ("touchMove", .7), ("touchEnd", None)]:
                points = [{"x": x + width * fraction, "y": y + height * fraction}] if fraction else []
                driver.execute_cdp_cmd("Input.dispatchTouchEvent", {"type": event, "touchPoints": points})
            button("保存裁图").click()
            wait.until(lambda _: rt.store.latest()["id"] != rid)
            result = rt.store.latest()
            self.assertEqual((result["media_operation"], result["source_rounds"]), ("crop", [rid]))
            self.assertAlmostEqual(result["width"], 400, delta=2)
            self.assertAlmostEqual(result["height"], 200, delta=2)

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
                save = workflow_api.apply_shot_edits

                def delayed_write(*args, **kwargs):
                    if not began.is_set():
                        began.set()
                        if not release.wait(12):
                            raise RuntimeError("test save timed out")
                        if is_retry:
                            raise HarnessError("internal_error")
                    return save(*args, **kwargs)

                with patch.object(workflow_api, "apply_shot_edits", side_effect=delayed_write), \
                     patch.object(engine, "start_run", wraps=engine.start_run) as start, \
                     patch.object(rt.studio, "colab", SimpleNamespace(has_credentials=lambda: True)), \
                     patch.object(rt.studio, "enqueue_with_refs", return_value=[{"id": "job"}]) as enqueue, \
                     patch.object(rt.studio, "wait_for_job", return_value={"status": "done", "round_id": "001"}):
                    try:
                        fields[0].send_keys(SHORTCUT, "a", Keys.NULL, "edited 1")
                        fields[1].click()  # blur starts the first save
                        self.assertTrue(began.wait(3))
                        if not is_retry:
                            topic = driver.find_element(By.CSS_SELECTOR, ".run-head textarea")
                            topic.send_keys(SHORTCUT, "a", Keys.NULL, "edited topic")
                        fields[1].send_keys(SHORTCUT, "a", Keys.NULL, "edited 2")
                        go.click()
                        wait.until(lambda d: d.find_element(By.CSS_SELECTOR, ".run").get_property("inert"))
                        self.assertFalse(start.called)
                    finally:
                        release.set()
                    if is_retry:
                        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".toasts"), "出了点问题，再试一次"))
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

    def test_workflow_assistant_restores_the_right_dock(self):
        with signed_in_browser() as (rt, driver, url):
            run = rt.workflows.create_run({"workflow": {"name": "Docking", "steps": [{"id": "refs", "type": "asset_input"}]}})
            driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
                "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            driver.get(f"{url}/?workflow={run['id']}")
            wait = WebDriverWait(driver, 8)
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".agent-launch"))).click()

            def at_side(dock, padding, on_left=False):
                return driver.execute_script("""
                    const panel = document.querySelector('.workflow-agent');
                    if (panel?.dataset.dock !== arguments[0]) return false;
                    const box = panel.getBoundingClientRect();
                    const onLeft = box.left + box.width / 2 < innerWidth / 2;
                    return onLeft === arguments[2] && getComputedStyle(document.querySelector('.wf')).paddingRight === arguments[1];
                """, dock, padding, on_left)

            move = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".agent-head > button:nth-last-child(2)")))
            wait.until(lambda _: at_side("right", "382px"))
            move.click()
            wait.until(lambda _: at_side("free", "0px", on_left=True))
            move.click()
            wait.until(lambda _: at_side("right", "382px"))

    def test_operation_card_unknown_recovery_and_assistant_history_forwarding(self):
        with signed_in_browser() as (rt, driver, url):
            src = rt.root / "done.png"
            src.write_bytes(png((32, 24), "navy"))
            rid = rt.store.save(src, "image", {"prompt": "done frame"})
            run = rt.workflows.create_run({"workflow": {"name": "Recovery", "steps": [{"id": "refs", "type": "asset_input"}]}})
            scope = run["id"]
            op = rt.operations.create(scope, "mix", normalize_job({"mode": "image", "prompt": "Evening", "count": 2, "seed": 7}))
            oid = op["operation_id"]
            with patch.object(rt.colab, "has_credentials", return_value=True), \
                 patch.object(rt.studio, "_runner", SimpleNamespace(is_alive=lambda: True)):
                approved = rt.operations.approve(oid)
            j1, _ = (item["job_id"] for item in approved["items"])
            with rt.studio._lock:
                first = next(j for j in rt.studio._queue if j["id"] == j1)
                rt.studio._queue.clear()
                first.update(status="done", round_id=rid)
                rt.studio._remember_job(first)
                rt.studio._history.clear()
                rt.studio._save_state_locked()

            seen_histories = []

            async def fake_turn(editor, provider, model, prompt, revision, key, turn_id, history, *, reload_plugins=False):
                seen_histories.append(list(history))
                yield {"type": "started", "model": model}
                yield {"type": "done", "message": f"回复：{prompt}", "proposals": [], "operations": [],
                       "composer_patch": None, "mask_editor": None, "run_updated": [], "refresh_run": False,
                       "refresh_library": False, "editor": None, "run_request": None, "base_revision": revision}

            fake_provider = SimpleNamespace(id="llm_1", kind="openai", base="https://example.invalid/v1", key="k")
            with patch.object(rt.studio.llm, "resolve", return_value=(fake_provider, "demo")), \
                 patch.object(workflow_api, "turn_events", side_effect=fake_turn):
                driver.get(f"{url}/?workflow={scope}")
                wait = WebDriverWait(driver, 10)
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".agent-launch"))).click()

                card = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".op-card")))
                self.assertEqual(card.get_attribute("data-state"), "partial")
                self.assertTrue(card.find_elements(By.XPATH, ".//button[normalize-space(.)='查看作品']"))
                cancel_btn = card.find_element(By.XPATH, ".//button[normalize-space(.)='取消']")
                cancel_btn.click()
                wait.until(lambda _: not card.find_elements(By.XPATH, ".//button[normalize-space(.)='取消']"))
                self.assertTrue(card.find_elements(By.XPATH, ".//button[normalize-space(.)='查看作品']"))
                self.assertEqual([i["state"] for i in rt.operations.get(oid)["items"]], ["done", "canceled"])

                box = driver.find_element(By.CSS_SELECTOR, ".agent-compose textarea")
                box.send_keys("第一句")
                driver.find_element(By.CSS_SELECTOR, ".agent-send").click()
                wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".agent-log"), "回复：第一句"))

                # Close and reopen without server recent.json persistence: local done turn must survive and be forwarded.
                driver.find_element(By.CSS_SELECTOR, '.agent-head button[aria-label="收起"]').click()
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".agent-launch"))).click()
                wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".agent-log"), "回复：第一句"))
                box = driver.find_element(By.CSS_SELECTOR, ".agent-compose textarea")
                box.send_keys("第二句")
                driver.find_element(By.CSS_SELECTOR, ".agent-send").click()
                wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".agent-log"), "回复：第二句"))
                self.assertEqual(seen_histories[0], [])
                self.assertEqual(seen_histories[1], [
                    {"role": "user", "text": "第一句"},
                    {"role": "assistant", "text": "回复：第一句"},
                ])

    def test_composer_assistant_copy_and_colab_unauthed_unlock(self):
        with signed_in_browser() as (rt, driver, url):
            authed_state = {"ok": False}
            status_base = rt.colab.status_report()
            def status_report(force=False, blocking=True):
                return {**status_base, "authed": authed_state["ok"], "ok": authed_state["ok"], "sessions": []}
            scope = "cr_" + "b" * 32
            op = rt.operations.create(scope, "unauthed-unlock", normalize_job({"mode": "image", "prompt": "Sunset", "count": 1, "seed": 5}))
            with patch.object(rt.colab, "status_report", side_effect=status_report), \
                 patch.object(rt.colab, "has_credentials", side_effect=lambda: authed_state["ok"]), \
                 patch.object(rt.studio, "_runner", SimpleNamespace(is_alive=lambda: True)):
                driver.execute_script("localStorage.setItem('colabreel.composerScope', JSON.stringify(arguments[0]))", scope)
                driver.get(url)
                wait = WebDriverWait(driver, 10)
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".agent-launch"))).click()
                # Context label in image composer says 生图 (not 关键帧).
                wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".agent-context"), "生图"))
                card = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".op-card")))
                confirm = card.find_element(By.XPATH, ".//button[normalize-space(.)='开始生成']")
                self.assertFalse(confirm.is_enabled())
                # Now simulate Colab OAuth completion without grabbing a card (sessions still empty).
                authed_state["ok"] = True
                wait.until(lambda _: card.find_element(By.XPATH, ".//button[normalize-space(.)='开始生成']").is_enabled())
                card.find_element(By.XPATH, ".//button[normalize-space(.)='开始生成']").click()
                wait.until(lambda _: rt.operations.get(op["operation_id"])["state"] == "queued")

    def test_workflow_save_template_preserves_variables_and_positions(self):
        with signed_in_browser() as (rt, driver, url):
            engine = rt.workflows
            variables = {"tone": "冷调", "passes": 2, "fast": False}
            engine.create_run({"topic": "fixture", "workflow": {
                "name": "变量工作流",
                "description": "保留变量与坐标",
                "variables": variables,
                "steps": [{"id": "s1", "type": "asset_input", "position": {"x": 120, "y": 240}}],
            }})
            wait = WebDriverWait(driver, 12)
            driver.get(url)
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'工作流')]"))).click()
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space(.)='存为模板']"))).click()
            name_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#name-prompt")))
            name_input.send_keys(SHORTCUT, "a", Keys.NULL, "已保存的变量模板")
            wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'modal')]//button[normalize-space(.)='保存']"))).click()
            wait.until(lambda _: any(t["name"] == "已保存的变量模板" for t in engine.list_workflows()["custom"]))
            saved = next(t for t in engine.list_workflows()["custom"] if t["name"] == "已保存的变量模板")
            self.assertEqual(saved["variables"], variables)
            self.assertEqual(saved["steps"][0]["position"], {"x": 120, "y": 240})

            driver.get(url + "/legacy")
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#wsWorkflow"))).click()
            wf_name = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#wfName")))
            wait.until(lambda _: wf_name.get_property("value") == "变量工作流")
            wf_name.send_keys(SHORTCUT, "a", Keys.NULL, "旧版保存的变量模板")
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#wfSaveTplBtn"))).click()
            wait.until(lambda _: any(t["name"] == "旧版保存的变量模板" for t in engine.list_workflows()["custom"]))
            legacy_saved = next(t for t in engine.list_workflows()["custom"] if t["name"] == "旧版保存的变量模板")
            self.assertEqual(legacy_saved["variables"], variables)
            self.assertEqual(legacy_saved["steps"][0]["position"], {"x": 120, "y": 240})

    def test_composer_sanitization_mask_replacement_and_unknown_reconciliation(self):
        with signed_in_browser() as (rt, driver, url):
            src1 = rt.root / "base.png"
            src1.write_bytes(png((64, 64), "navy"))
            base_rid = rt.store.save(src1, "image", {"prompt": "base"})
            src2 = rt.root / "edited.png"
            src2.write_bytes(png((64, 64), "gold"))
            rt.store.save(src2, "image", {
                "prompt": "masked edit",
                "model": "qwen-2.1-bf16",
                "edit_source_id": base_rid,
                "edit_mask": {"source_id": base_rid, "strokes": [{"size": 0.08, "points": [[0.2, 0.2], [0.5, 0.5]]}]},
                "sampling_width": 768, "sampling_height": 1152,
            })

            scope = "cr_" + "c" * 32
            stale_mask_id = "mk_" + "a" * 24
            op = rt.operations.create(scope, "unknown-reconcile", normalize_job({"mode": "image", "prompt": "Fog", "count": 1, "seed": 9}))
            oid = op["operation_id"]
            with patch.object(rt.colab, "has_credentials", return_value=True), \
                 patch.object(rt.studio, "_runner", SimpleNamespace(is_alive=lambda: True)):
                approved = rt.operations.approve(oid)
            jid = approved["items"][0]["job_id"]
            with rt.studio._lock:
                rt.studio._queue.clear()
                rt.studio._history.clear()
                rt.studio._save_state_locked()

            seen_composers = []

            async def fake_turn(editor, provider, model, prompt, revision, key, turn_id, history, *, reload_plugins=False):
                seen_composers.append(dict(editor.composer or {}))
                yield {"type": "started", "model": model}
                yield {"type": "done", "message": f"收到：{prompt}", "proposals": [], "operations": [],
                       "composer_patch": None, "mask_editor": None, "run_updated": [], "refresh_run": False,
                       "refresh_library": False, "editor": None, "run_request": None, "base_revision": revision}

            dirty_draft = {
                "engine": "diffusers", "model": "  qwen-2.1-q5  ",
                "ggufRepo": "  unsloth/Qwen-Image-2.1-GGUF  ", "ggufFile": "  qwen.gguf  ",
                "idea": "i" * 750, "prompt": "Night street", "negative": "",
                "width": 768, "height": 1152, "steps": 28, "cfg": 4.5, "seed": "-1", "count": 1,
                "useRef": False, "chain": False,
                "editMask": {"source_id": base_rid, "strokes": [{"size": 0.1, "points": [[0.1, 0.1], [0.2, 0.2]]}]},
                "maskId": stale_mask_id,
                "loras": [
                    {"repo_id": "https://huggingface.co/alice/style/resolve/main/film.safetensors", "weight_name": "", "scale": 1.2},
                    {"repo_id": "  bob/light  ", "weight_name": "  glow.safetensors  ", "scale": 3.5},
                    {"repo_id": "typing-in-progress", "weight_name": "", "scale": 1},
                    {"repo_id": "c/one", "weight_name": "1.safetensors", "scale": 0.5},
                    {"repo_id": "d/two", "weight_name": "2.safetensors", "scale": 0.5},
                    {"repo_id": "e/three", "weight_name": "3.safetensors", "scale": 0.5},
                ],
                "gpu": "A100",
            }
            fake_provider = SimpleNamespace(id="llm_1", kind="openai", base="https://example.invalid/v1", key="k")
            with patch.object(rt.studio.llm, "resolve", return_value=(fake_provider, "demo")), \
                 patch.object(workflow_api, "turn_events", side_effect=fake_turn):
                driver.get(url)
                driver.execute_script(
                    "localStorage.setItem('colabreel.libopen', 'true');"
                    "localStorage.setItem('colabreel.composerScope', JSON.stringify(arguments[0]));"
                    "localStorage.setItem('colabreel.draft', JSON.stringify(arguments[1]));",
                    scope, dirty_draft,
                )
                driver.get(url)
                wait = WebDriverWait(driver, 12)
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".agent-launch"))).click()

                # 1. Open composer assistant: 'unknown' operation renders with spinner, and dirty draft is sanitized (no 400).
                card = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".op-card")))
                self.assertEqual(card.get_attribute("data-state"), "unknown")
                self.assertTrue(card.find_elements(By.CSS_SELECTOR, ".spinner"))
                box = driver.find_element(By.CSS_SELECTOR, ".agent-compose textarea")
                box.send_keys("帮我看看参数")
                driver.find_element(By.CSS_SELECTOR, ".agent-send").click()
                wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".agent-log"), "收到：帮我看看参数"))
                first = seen_composers[0]
                self.assertEqual(len(first["idea"]), 600)
                self.assertEqual(first["custom_transformer_repo"], "unsloth/Qwen-Image-2.1-GGUF")
                self.assertEqual(first["custom_transformer_file"], "qwen.gguf")
                self.assertEqual(len(first["loras"]), 4)
                self.assertEqual(first["loras"][0], {"repo_id": "alice/style", "weight_name": "film.safetensors", "scale": 1.2})
                self.assertEqual(first["loras"][1], {"repo_id": "bob/light", "weight_name": "glow.safetensors", "scale": 2.5})
                self.assertEqual(first["mask_id"], stale_mask_id)

                # 2. Reusing parameters from masked round replaces editMask without maskId -> clears stale maskId.
                driver.find_element(By.CSS_SELECTOR, '.agent-head button[aria-label="收起"]').click()
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.tile[title="masked edit"]'))).click()
                wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space(.)='复用参数']"))).click()
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".agent-launch"))).click()
                box = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".agent-compose textarea")))
                box.send_keys("复用后再看")
                driver.find_element(By.CSS_SELECTOR, ".agent-send").click()
                wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".agent-log"), "收到：复用后再看"))
                self.assertIsNone(seen_composers[1].get("mask_id"))
                self.assertTrue(seen_composers[1]["has_image"])

                # 3. Transient 'unknown' operation reconciles automatically via backoff polling while panel stays open.
                self.assertEqual(driver.find_element(By.CSS_SELECTOR, ".op-card").get_attribute("data-state"), "unknown")
                done_img = rt.root / "recovered-op.png"
                done_img.write_bytes(png((64, 64), "teal"))
                rt.store.save(done_img, "image", {"job_id": jid, "prompt": "Fog"})
                wait.until(lambda _: driver.find_element(By.CSS_SELECTOR, ".op-card").get_attribute("data-state") == "done")

    def test_queued_progress_bar_ref2va_context_and_mask_patch_error_isolation(self):
        with signed_in_browser() as (rt, driver, url):
            scope = "cr_" + "d" * 32
            op = rt.operations.create(scope, "queued-bar", normalize_job({"mode": "image", "prompt": "Cloud", "count": 2, "seed": 3}))
            with patch.object(rt.colab, "has_credentials", return_value=True), \
                 patch.object(rt.studio, "_runner", SimpleNamespace(is_alive=lambda: True)):
                rt.operations.approve(op["operation_id"])

            seen_composers = []

            async def fake_turn(editor, provider, model, prompt, revision, key, turn_id, history, *, reload_plugins=False):
                seen_composers.append(dict(editor.composer or {}))
                yield {"type": "started", "model": model}
                patch_obj = (
                    {"workspace": "image", "base_revision": revision, "changes": {"mask_id": "mk_" + "e" * 24}}
                    if editor.workspace == "image" else None
                )
                yield {"type": "done", "message": f"完成：{prompt}", "proposals": [], "operations": [],
                       "composer_patch": patch_obj, "mask_editor": None, "run_updated": [], "refresh_run": False,
                       "refresh_library": False, "editor": None, "run_request": None, "base_revision": revision}

            fake_provider = SimpleNamespace(id="llm_1", kind="openai", base="https://example.invalid/v1", key="k")
            with patch.object(rt.studio.llm, "resolve", return_value=(fake_provider, "demo")), \
                 patch.object(workflow_api, "turn_events", side_effect=fake_turn):
                driver.get(url)
                driver.execute_script(
                    "localStorage.setItem('colabreel.composerScope', JSON.stringify(arguments[0]));"
                    "localStorage.setItem('colabreel.draft', JSON.stringify({workflow: 'ref2va', videoTask: 'images', videoUseImages: true, prompt: 'Video idea'}));",
                    scope,
                )
                driver.get(url)
                wait = WebDriverWait(driver, 12)
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".agent-launch"))).click()

                # 1. Queued OperationCard uses indeterminate progressbar without inline 0% width or determinate ARIA.
                bar = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".op-card .bar.indet")))
                self.assertIsNone(bar.get_attribute("aria-valuemin"))
                self.assertIsNone(bar.get_attribute("aria-valuemax"))
                self.assertIsNone(bar.get_attribute("aria-valuenow"))
                self.assertEqual(bar.get_attribute("aria-valuetext"), "排队中")
                self.assertEqual(bar.find_element(By.CSS_SELECTOR, "i").get_attribute("style") or "", "")

                # 2. Expired mask_id fetch error in applyAssistantComposerPatch does not fail a completed turn.
                box = driver.find_element(By.CSS_SELECTOR, ".agent-compose textarea")
                box.send_keys("应用过期选区")
                driver.find_element(By.CSS_SELECTOR, ".agent-send").click()
                wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".agent-log"), "完成：应用过期选区"))
                self.assertEqual(driver.find_elements(By.CSS_SELECTOR, ".agent-error"), [])

                # 3. Video ref2va with no uploaded reference image sends has_image=False.
                driver.find_element(By.CSS_SELECTOR, '.agent-head button[aria-label="收起"]').click()
                wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'视频')]"))).click()
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".agent-launch"))).click()
                box = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".agent-compose textarea")))
                box.send_keys("检查视频参考")
                driver.find_element(By.CSS_SELECTOR, ".agent-send").click()
                wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".agent-log"), "完成：检查视频参考"))
                self.assertEqual(seen_composers[-1]["mode"], "video")
                self.assertEqual(seen_composers[-1]["workflow"], "ref2va")
                self.assertFalse(seen_composers[-1]["has_image"])

    def test_committed_shot_edit_syncs_on_failed_turn_without_conflict(self):
        from draw_studio.workflows.shot_service import apply_shot_edits, read_shots

        with signed_in_browser() as (rt, driver, url):
            engine = rt.workflows
            run = engine.create_run({"topic": "sync", "workflow": {"name": "同步测试", "steps": [
                {"id": "script", "name": "分镜脚本", "type": "llm_script", "pause_after": True},
                {"id": "generate", "name": "生图", "type": "image_gen", "config": {"scenes_from": "script", "ref_sources": []}},
            ]}})
            rid = run["id"]
            with patch.object(engine, "_run_step", return_value={"scenes": [{"title": "S1", "keyframe_prompt": "old prompt"}]}):
                engine.start_run(rid)
                WebDriverWait(driver, 10).until(lambda _: engine.get_run(rid)["status"] == "paused")

            async def fail_after_commit(editor, provider, model, prompt, revision, key, turn_id, history, *, reload_plugins=False):
                shot = read_shots(rt, rid, "script")[0]
                res = apply_shot_edits(rt, run_id=rid, step_id="script", patches=[{
                    "shot_id": shot["shot_id"], "field": "keyframe_prompt",
                    "generation": shot["generation"], "expected_version": shot["field_versions"]["keyframe_prompt"],
                    "value": "agent committed",
                }], scope=rid)
                yield {"type": "started", "model": model}
                yield {"type": "tool", "name": "studio_apply_shot_edits", "call_id": "c1", "ok": True,
                       "run_updated": [res["run_updated"]], "refresh_run": True}
                yield {"type": "error", "code": "model_error", "message": "failed",
                       "run_updated": [res["run_updated"]], "refresh_run": True}

            fake_provider = SimpleNamespace(id="llm_1", kind="openai", base="https://example.invalid/v1", key="k")
            with patch.object(rt.studio.llm, "resolve", return_value=(fake_provider, "demo")), \
                 patch.object(workflow_api, "turn_events", side_effect=fail_after_commit):
                driver.get(f"{url}/?workflow={rid}")
                wait = WebDriverWait(driver, 12)
                row = wait.until(EC.presence_of_element_located((By.XPATH, "//li[.//b[normalize-space(.)='分镜脚本']]")))
                row.find_element(By.CSS_SELECTOR, ".step-h").click()
                field = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'textarea[aria-label="关键帧提示词"]')))
                self.assertEqual(field.get_property("value"), "old prompt")

                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".agent-launch"))).click()
                box = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".agent-compose textarea")))
                box.send_keys("改一下第一镜")
                driver.find_element(By.CSS_SELECTOR, ".agent-send").click()
                wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".agent-error")))
                wait.until(lambda _: driver.find_element(By.CSS_SELECTOR, 'textarea[aria-label="关键帧提示词"]').get_property("value") == "agent committed")

                # Subsequent manual edit must save cleanly with updated field_versions (zero conflict).
                field = driver.find_element(By.CSS_SELECTOR, 'textarea[aria-label="关键帧提示词"]')
                field.send_keys(SHORTCUT, "a", Keys.NULL, "human follow-up")
                driver.find_element(By.CSS_SELECTOR, ".run-head textarea").click()
                wait.until(lambda _: engine.get_run(rid)["step_states"]["script"]["output"]["scenes"][0]["keyframe_prompt"] == "human follow-up")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=2)
