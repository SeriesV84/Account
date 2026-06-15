import os
import time
import random
import traceback
from datetime import datetime
from dotenv import load_dotenv
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TOKEN")
TARGET_USER_ID = 7450323200

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

def send_telegram_error(error_text, screenshot_path=None):
    log("Sending error report to Telegram...")
    if not TELEGRAM_TOKEN:
        log("No TELEGRAM_TOKEN – skipping")
        return
    base_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    caption = f"ERROR in Gmail creator:\n{error_text[:900]}"
    if screenshot_path and os.path.exists(screenshot_path):
        with open(screenshot_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': TARGET_USER_ID, 'caption': caption}
            resp = requests.post(f"{base_url}/sendPhoto", files=files, data=data)
            log("Telegram photo sent" if resp.status_code == 200 else f"Telegram send failed: {resp.text}")
    else:
        resp = requests.post(f"{base_url}/sendMessage", json={'chat_id': TARGET_USER_ID, 'text': caption})
        log("Telegram message sent" if resp.status_code == 200 else f"Telegram send failed: {resp.text}")


class GmailAccountFiller:
    def __init__(self, proxy_list=None):
        self.proxy_list = proxy_list or []
        self.current_proxy = None
        self._chrome_bin = "/opt/chrome-linux64/chrome"
        self._driver_path = "/opt/chromedriver-linux64/chromedriver"

    def _init_driver(self):
        log("Initializing ChromeDriver...")
        opts = Options()
        opts.binary_location = self._chrome_bin
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-setuid-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--disable-software-rasterizer")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--remote-debugging-port=0")
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        if self.current_proxy:
            opts.add_argument(f"--proxy-server={self.current_proxy}")
            log(f"Using proxy: {self.current_proxy}")

        service = Service(executable_path=self._driver_path)
        driver = webdriver.Chrome(service=service, options=opts)

        stealth(
            driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
        log("ChromeDriver ready with stealth")
        return driver

    def _take_screenshot(self, driver, prefix="error"):
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}.png"
        driver.save_screenshot(filename)
        log(f"Screenshot saved: {filename}")
        return filename

    def fill_account_form(self, email, password, firstname, lastname="User"):
        driver = None
        log(f"=== Starting account creation for {email} ===")
        try:
            driver = self._init_driver()
            log("Navigating to Google signup page...")
            driver.get(
                "https://accounts.google.com/signup/v2/webcreateaccount"
                "?flowName=GlifWebSignIn&flowEntry=SignUp"
            )
            wait = WebDriverWait(driver, 20)

            log("Waiting for first name field...")
            first_name_field = wait.until(
                EC.presence_of_element_located((By.ID, "firstName"))
            )
            first_name_field.send_keys(firstname)

            driver.find_element(By.ID, "lastName").send_keys(lastname)

            username = email.split("@")[0] if "@" in email else email
            log(f"Entering username: {username}")
            driver.find_element(By.ID, "username").send_keys(username)

            driver.find_element(By.NAME, "Passwd").send_keys(password)
            driver.find_element(By.NAME, "ConfirmPasswd").send_keys(password)

            driver.find_element(By.ID, "accountDetailsNext").click()
            time.sleep(3)

            for i in range(2):
                try:
                    skip = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//span[contains(text(), 'Skip')]")
                        )
                    )
                    skip.click()
                    log(f"Skip {i+1} clicked")
                    time.sleep(1)
                except Exception:
                    log(f"No skip button on attempt {i+1}")

            time.sleep(3)
            try:
                i_agree = driver.find_element(
                    By.XPATH, "//span[contains(text(), 'I agree')]"
                )
                i_agree.click()
                log("I agree clicked")
            except Exception:
                log("No I agree button found")

            time.sleep(5)
            current_url = driver.current_url
            log(f"Final URL: {current_url}")
            if "myaccount" in current_url or "inbox" in current_url:
                log(f"[SUCCESS] {email} created")
                return True
            else:
                raise Exception("Verification or phone step detected — account not created")

        except Exception as e:
            error_trace = traceback.format_exc()
            log(f"[ERROR] for {email}: {e}")
            screenshot_file = None
            if driver:
                try:
                    screenshot_file = self._take_screenshot(
                        driver, f"error_{email.replace('@', '_')}"
                    )
                except Exception as ss_err:
                    log(f"Screenshot failed: {ss_err}")
            send_telegram_error(f"Email: {email}\n{error_trace[:800]}", screenshot_file)
            if screenshot_file and os.path.exists(screenshot_file):
                os.remove(screenshot_file)
            return False

        finally:
            if driver:
                driver.quit()
                log("Browser closed")

    def run_from_file(self, filepath="input.txt"):
        log(f"Reading accounts from {filepath}")
        try:
            with open(filepath, "r") as f:
                lines = [line.strip() for line in f if line.strip()]
            log(f"Loaded {len(lines)} lines")
        except FileNotFoundError:
            log(f"File not found: {filepath}")
            send_telegram_error(f"File not found: {filepath}")
            return

        for idx, line in enumerate(lines, 1):
            log(f"\n--- Processing line {idx}/{len(lines)} ---")
            parts = line.split(":")
            if len(parts) < 3:
                log(f"Skipping malformed line: {line}")
                continue

            email     = parts[0].strip()
            password  = parts[1].strip()
            firstname = parts[2].strip()
            lastname  = parts[3].strip() if len(parts) >= 4 else "User"

            success = self.fill_account_form(email, password, firstname, lastname)
            log(f"Result: {'SUCCESS' if success else 'FAIL'}")

            with open("success_log.txt", "a") as s_log, open("failed_log.txt", "a") as f_log:
                (s_log if success else f_log).write(f"{email}:{password}\n")

            cooldown = random.uniform(90, 180)
            log(f"Cooling down for {cooldown:.1f} seconds...")
            time.sleep(cooldown)

        log("All accounts processed.")


if __name__ == "__main__":
    log("Gmail Account Filler started")
    creator = GmailAccountFiller()
    creator.run_from_file("input.txt")
    log("Script finished.")
