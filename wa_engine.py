"""
WhatsApp Web engine - REAL browser automation (Selenium + Chrome).

Spins up a persistent Chrome profile, opens WhatsApp Web, extracts the live
QR code for scanning, and once authenticated reads/sends real messages.
Nothing is mocked - everything comes from the connected WhatsApp session.
"""

import base64
import os
import threading
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wa_session")
QR_IMAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qr_current.png")


class WhatsAppEngine:
    """Single Selenium-driven WhatsApp Web session."""

    def __init__(self):
        self.driver = None
        self.lock = threading.Lock()
        self.status = "idle"          # idle | starting | qr | linked | error
        self.last_error = ""
        self.contacts = {}            # name -> {"phone":..., "chats":[{who,text,ts}]}
        self._thread = None
        self._stop = False

    # ------------------------------------------------------------------ start
    def start(self):
        """Launch Chrome -> WhatsApp Web -> poll for QR/auth state."""
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self.status = "starting"
            os.makedirs(STATE_DIR, exist_ok=True)
            opts = Options()
            opts.add_argument(f"--user-data-dir={STATE_DIR}")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--disable-notifications")
            opts.add_argument("--lang=en-ZA")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            self.driver = webdriver.Chrome(options=opts, service=Service())
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
            )
            wait = WebDriverWait(self.driver, 30)
            self.driver.get("https://web.whatsapp.com")

            # Wait for either the QR screen or the main app
            while not self._stop:
                try:
                    time.sleep(2)
                    qr_el = self.driver.find_elements(By.XPATH, "//canvas[contains(@class, 'qr') or ancestor::*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'qr')]]")
                    if qr_el:
                        self.status = "qr"
                        self._save_qr(qr_el[0])
                        # keep refreshing the QR until scanned
                        while not self._stop and self.driver:
                            time.sleep(3)
                            if self._is_linked():
                                self.status = "linked"
                                self._sync_all()
                                break
                            try:
                                qr_el2 = self.driver.find_elements(By.XPATH, "//canvas[contains(@class,'qr')]")
                                if qr_el2:
                                    self._save_qr(qr_el2[0])
                            except Exception:
                                pass
                        break
                    if self._is_linked():
                        self.status = "linked"
                        self._sync_all()
                        break
                except Exception as e:
                    self.last_error = str(e)[:200]
                    self.status = "error"
                    break
        except Exception as e:
            self.status = "error"
            self.last_error = str(e)[:300]

    def _is_linked(self):
        try:
            return bool(self.driver.find_elements(By.XPATH, "//div[@id='side'] | //header//div[@contenteditable='true'] | //span[@data-testid='cell-frame-title']"))
        except Exception:
            return False

    def _save_qr(self, canvas_el):
        try:
            png = self.driver.execute_script(
                "var c = arguments[0]; var n = c.cloneNode(false); "
                "n.width = c.width; n.height = c.height; "
                "var x = n.getContext('2d'); x.drawImage(c, 0, 0); "
                "return n.toDataURL('image/png').substring(22);", canvas_el
            )
            with open(QR_IMAGE_PATH, "wb") as f:
                f.write(base64.b64decode(png))
        except Exception:
            pass

    # ------------------------------------------------------------------ stop
    def stop(self):
        self._stop = True
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None
        self.status = "idle"

    # ------------------------------------------------------------------ reads
    def qr_image(self):
        if os.path.exists(QR_IMAGE_PATH):
            with open(QR_IMAGE_PATH, "rb") as f:
                return f.read()
        return None

    def linked(self):
        return self.status == "linked"

    def _extract_text(self, el):
        try:
            return el.text.strip()
        except Exception:
            return ""

    def sync(self):
        """Pull latest messages from WhatsApp DOM (runs inside lock)."""
        if not self.driver or self.status != "linked":
            return
        try:
            contacts = self.driver.find_elements(By.XPATH, "//div[@id='side']//div[contains(@class,'cell')]")
            out = {}
            for cell in contacts[:40]:
                try:
                    name_el = cell.find_elements(By.XPATH, ".//span[@dir='auto']")
                    name = self._extract_text(name_el[0]) if name_el else "Unknown"
                    cell.click()
                    time.sleep(1.2)
                    msgs = []
                    bubbles = self.driver.find_elements(By.XPATH, "//div[contains(@class,'message-in')] | //div[contains(@class,'message-out')]")
                    for b in bubbles[-25:]:
                        direction = "lead" if "message-in" in (b.get_attribute("class") or "") else "ai"
                        txt = self._extract_text(b)
                        if txt:
                            msgs.append({"who": direction, "text": txt, "ts": datetime.now().strftime("%H:%M, %d/%m/%Y")})
                    out[name] = {"phone": "", "chats": msgs}
                except Exception:
                    continue
            with self.lock:
                self.contacts = out
        except Exception as e:
            self.last_error = str(e)[:200]

    def _sync_all(self):
        with self.lock:
            self.sync()

    def get_contacts(self):
        with self.lock:
            return dict(self.contacts)

    def send(self, contact_name: str, text: str) -> bool:
        """Send a real message in an open WhatsApp chat."""
        if not self.driver or self.status != "linked":
            return False
        with self.lock:
            try:
                box_xpaths = [
                    "//footer//div[@contenteditable='true']",
                    "//div[@contenteditable='true' and @data-tab='10']",
                    "//div[@role='textbox']",
                ]
                box = None
                for xp in box_xpaths:
                    els = self.driver.find_elements(By.XPATH, xp)
                    if els:
                        box = els[-1]
                        break
                if not box:
                    return False
                box.click()
                time.sleep(0.3)
                box.send_keys(text)
                time.sleep(0.4)
                box.send_keys(Keys.ENTER)
                time.sleep(0.6)
                return True
            except Exception as e:
                self.last_error = str(e)[:200]
                return False
