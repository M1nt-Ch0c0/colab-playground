"""Chromium smoke test against the production Vite build and a real local ASGI server."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from http_fixture import gateway, png, serving


def chrome():
    options = webdriver.ChromeOptions()
    for option in ("--headless", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,1000"):
        options.add_argument(option)
    binary = shutil.which("chromium") or shutil.which("google-chrome")
    if binary:
        options.binary_location = binary
    return webdriver.Chrome(options=options, service=Service(shutil.which("chromedriver")))


class BrowserTest(unittest.TestCase):
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
                    wait.until(lambda _: row.find_elements(By.CSS_SELECTOR, ".step-cfg"))
                    return row

                def dropdown(row, label):
                    return Select(row.find_element(By.XPATH, f".//label[span[normalize-space(.)='{label}']]/select"))

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
                wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".run-head .tag"), "待审核"))
                # The persisted run uses the same controls and autosaves without re-stringifying them.
                image = open_step("测试生图")
                with patch.object(engine, "update_run_config", wraps=engine.update_run_config) as update:
                    dropdown(image, "首选 GPU").select_by_value("G4")
                    toggle(image, "每轮使用全部代理").click()
                    wait.until(lambda _: update.called and update.call_args.args[1]["workflow"]["steps"][1]["config"]["poll_all_proxies"] is True)
                    config = update.call_args.args[1]["workflow"]["steps"][1]["config"]
                self.assertEqual((config["gpu"], config["gpu_pool"]), ("G4", ["G4"]))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=2)
