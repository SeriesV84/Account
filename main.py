# main.py
import os
import time
import random
import traceback
from dotenv import load_dotenv
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from fake_useragent import UserAgent

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TOKEN")
TARGET_USERNAME = os.getenv("TARGET_USERNAME", "SeriesV84")

def get_chat_id_from_username(bot_token, username):
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if not data.get('ok'):
            return None
        for update in data.get('result', []):
            msg = update.get('message')
            if msg:
                user = msg.get('from')
                if user and user.get('username') == username.lstrip('@'):
                    return msg.get('chat', {}).get('id')
        return None
    except Exception:
        return None

def send_telegram_error(error_text, screenshot_path=None):
    if not TELEGRAM_TOKEN:
        return
    chat_id = get_chat_id_from_username(TELEGRAM_TOKEN, TARGET_USERNAME)
    if not chat_id:
        return
    base_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    caption = f"ERROR in Gmail creator:\n{error_text[:900]}"
    if screenshot_path and os.path.exists(screenshot_path):
        with open(screenshot_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': chat_id, 'caption': caption}
            requests.post(f"{base_url}/sendPhoto", files=files, data=data)
    else:
        requests.post(f"{base_url}/sendMessage", json={'chat_id': chat_id, 'text': caption})

class GmailAccountFiller:
    def __init__(self, proxy_list=None):
        self.proxy_list = proxy_list or []
        self.current_proxy = None
        self.ua = UserAgent()

    def _init_driver(self):
        opts = uc.ChromeOptions()
        opts.add_argument(f"--user-agent={self.ua.random}")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        if self.current_proxy:
            opts.add_argument(f"--proxy-server={self.current_proxy}")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option('useAutomationExtension', False)
        driver = uc.Chrome(options=opts, version_main=114)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def _take_screenshot(self, driver, prefix="error"):
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}.png"
        driver.save_screenshot(filename)
        return filename

    def fill_account_form(self, email, password, firstname, lastname="User"):
        driver = None
        try:
            driver = self._init_driver()
            driver.get("https://accounts.google.com/signup/v2/webcreateaccount?flowName=GlifWebSignIn&flowEntry=SignUp")
            wait = WebDriverWait(driver, 20)

            wait.until(EC.presence_of_element_located((By.ID, "firstName"))).send_keys(firstname)
            driver.find_element(By.ID, "lastName").send_keys(lastname)
            username = email.split('@')[0] if '@' in email else email
            driver.find_element(By.ID, "username").send_keys(username)
            driver.find_element(By.NAME, "Passwd").send_keys(password)
            driver.find_element(By.NAME, "ConfirmPasswd").send_keys(password)
            driver.find_element(By.ID, "accountDetailsNext").click()
            time.sleep(3)

            for _ in range(2):
                try:
                    skip = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Skip')]"))
                    )
                    skip.click()
                    time.sleep(1)
                except:
                    pass

            time.sleep(3)
            try:
                i_agree = driver.find_element(By.XPATH, "//span[contains(text(), 'I agree')]")
                i_agree.click()
            except:
                pass

            time.sleep(5)
            if "myaccount" in driver.current_url or "inbox" in driver.current_url:
                return True
            else:
                raise Exception("Verification required")
        except Exception as e:
            error_trace = traceback.format_exc()
            screenshot_file = None
            if driver:
                try:
                    screenshot_file = self._take_screenshot(driver, f"error_{email.replace('@','_')}")
                except:
                    pass
            send_telegram_error(f"Email: {email}\n{error_trace[:800]}", screenshot_file)
            if screenshot_file and os.path.exists(screenshot_file):
                os.remove(screenshot_file)
            return False
        finally:
            if driver:
                driver.quit()

    def run_from_file(self, filepath="input.txt"):
        try:
            with open(filepath, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            send_telegram_error(f"File not found: {filepath}")
            return

        for line in lines:
            parts = line.split(':')
            if len(parts) < 3:
                continue
            email = parts[0].strip()
            password = parts[1].strip()
            firstname = parts[2].strip()
            lastname = parts[3].strip() if len(parts) >= 4 else "User"

            success = self.fill_account_form(email, password, firstname, lastname)
            with open("success_log.txt", "a") as s_log, open("failed_log.txt", "a") as f_log:
                (s_log if success else f_log).write(f"{email}:{password}\n")
            time.sleep(random.uniform(90, 180))

if __name__ == "__main__":
    creator = GmailAccountFiller()
    creator.run_from_file("input.txt")
