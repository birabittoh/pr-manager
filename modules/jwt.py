import datetime
import sys
import weakref
import logging
import json
from threading import Lock

from playwright.sync_api import Page, Response, TimeoutError, sync_playwright
import requests

from modules import config

# Constants
HEADLESS = True

_jwt_file = config.JWT_TOKEN
_jwt_cache = None
_jwt_lock = Lock()


class Chromium(object):
    _instance = []
    headless: bool = True

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 0,
    ):
        self.headless = headless
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context(locale="en-GB")
        self.context.clear_cookies()

        self.timeout = timeout
        self.context.set_default_timeout(self.timeout)

    def __new__(
        cls,
        headless: bool = True,
        timeout: int = 0,
    ):
        if Chromium._instance:
            Chromium.__check_only_one_instance_alive()
            return weakref.proxy(Chromium._instance[0])
        else:
            instance_local = super().__new__(cls)
            Chromium._instance.append(instance_local)
            return instance_local

    def clean(self):
        logging.debug("Quitting Chromium...")
        if len(Chromium._instance) != 0:
            self.context.close()
            self.browser.close()
            self.playwright.stop()
            self._instance.remove(self)

    @staticmethod
    def get_chromium():
        if len(Chromium._instance) == 0:
            return Chromium(headless=HEADLESS, timeout=config.CHROMIUM_TIMEOUT)
        return Chromium._instance[0]

    def visit_site(self, page: Page, url: str) -> Response | None:
        response = page.goto(url)
        ok, status = self.__check_response_status(response)
        if not ok:
            self.clean()
        return response

    @staticmethod
    def __check_response_status(response: Response) -> tuple[bool, int]:
        if response.status != 200:
            logging.debug(f"Found status {response.status} for {response.url}")
            return False, response.status
        return True, response.status

    @staticmethod
    def __check_only_one_instance_alive():
        if len(Chromium._instance) != 1:
            logging.error("Weird behaviour, too many alive references...exiting...")
            sys.exit("Weird behaviour, too many alive references...exiting...")


def _config_page(page: Page):
    window_size = {"width": 1920, "height": 1080}
    page.wait_for_load_state()
    page.set_viewport_size(viewport_size=window_size)
    page.set_default_timeout(config.CHROMIUM_TIMEOUT)

def _perform_mlol_login(page: Page, username: str, password: str, chromium: Chromium):
    logging.debug("Logging into MLOL...")
    page.fill("input[name='lusername']", username, timeout=0)
    page.fill("input[name='lpassword']", password, timeout=0)
    page.click("input[type='submit']", timeout=0)

    # Failed login detection
    try:
        warning_failed_login = (page.text_content(".page-title") or "").lower()
        if "avviso" in warning_failed_login:
            chromium.clean()
            sys.exit("Login failed, please check your MLOL credentials!")
    except TimeoutError:
        pass


def _get_auth_info(page: Page, chromium: Chromium) -> dict:
    # Clicking on catalogue
    typologies_menu_entry = page.query_selector("#caricatip")
    typologies_menu_entry.click()

    newspapers_section = page.locator(":nth-match(:text('EDICOLA'), 1)")
    newspapers_section.click()

    # Focusing on Corriere della Sera
    corriere_sera = page.locator("text=Corriere della Sera")
    corriere_sera.nth(0).click()

    # Find the "SFOGLIA" <a> element and navigate directly to its href in the current tab
    pressreader_link = page.locator(":nth-match(:text('SFOGLIA'), 1)")
    href = pressreader_link.get_attribute("href")
    if not href:
        return {}

    base_url = page.url.rsplit("/", 1)[0]
    href = f"{base_url}/{href}"

    try:
        with page.expect_response(lambda r: "preload" in r.url) as resp_info:
            page.goto(href)
        resp = resp_info.value
        text = resp.text()

        # handle JSONP response
        if text.strip().startswith("loadCallback"):
            start = text.find("(")
            end = text.rfind(")")
            payload = text[start + 1 : end]
            response_json = json.loads(payload)
        else:
            response_json = resp.json()

        return response_json.get("auth", {})

    except TimeoutError:
        return {}


def _dismiss_mlol_modal(page: Page):
    try:
        page.wait_for_selector("#FavModal")
        modal_dismissal_button = page.locator(
            "//div[@class='modal-footer']/button[@data-dismiss='modal']"
        )
        modal_dismissal_button.click()
    except TimeoutError:
        pass


def _get_jwt_logic() -> tuple[str, datetime.datetime]:
    """Return JWT token captured from PressReader GetPageKeys request."""
    if not config.MLOL_USERNAME or not config.MLOL_PASSWORD:
        sys.exit("MLOL credentials are not set in environment variables!")

    chromium = Chromium.get_chromium()
    chromium.context.on("page", _config_page)
    chromium.context.new_page()

    try:
        logging.debug("Visiting MLOL...")
        page = chromium.context.pages[0]
        chromium.visit_site(page, config.MLOL_WEBSITE)  # entrypoint
        _perform_mlol_login(page, config.MLOL_USERNAME, config.MLOL_PASSWORD, chromium)
        _dismiss_mlol_modal(page)
        auth_info = _get_auth_info(page, chromium)

        #token = auth_info.get("Token", None)
        #user_key = auth_info.get("UserKey", None)
        #use_geolocation = auth_info.get("UseGeoLocation", False)
        jwt_token = auth_info.get("BearerToken", None)
        expires_in = auth_info.get("ExpiresIn", 0)

        if not jwt_token:
            sys.exit("JWT token not found!")

        expected_expiry = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
        logging.info("JWT token captured successfully. Expires at %s", expected_expiry.isoformat())
        return jwt_token, expected_expiry

    finally:
        chromium.clean()

def get_jwt() -> str:
    """
    Thread-safe JWT retrieval function.
    Caches the JWT to avoid multiple retrievals.
    """
    global _jwt_cache
    
    with _jwt_lock:
        if _jwt_cache is not None:
            logging.debug("Returning cached JWT")
            return _jwt_cache
        
        if _jwt_file.exists():
            with open(_jwt_file, "r") as f:
                _jwt_cache = f.read().strip()
                if _jwt_cache:
                    logging.debug("Loaded JWT from cache file")
                    return _jwt_cache
        
        logging.info("Retrieving new JWT...")
        _jwt_cache, _ = _get_jwt_logic()

        # save to file
        with open(_jwt_file, "w") as f:
            f.write(_jwt_cache)

        logging.info("JWT retrieved and cached successfully")
        return _jwt_cache

def invalidate_jwt():
    """Invalidate cached JWT"""
    global _jwt_cache
    with _jwt_lock:
        _jwt_cache = None

        # remove cached file
        if _jwt_file.exists():
            _jwt_file.unlink()

        logging.info("JWT cache invalidated")


def authorized_request(url: str, params: dict[str,str]) -> requests.Response:
    """Make an authorized GET request with JWT, invalidate on 401"""
    jwt = get_jwt()
    headers = {
        "Authorization": f"Bearer {jwt}",
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 401:
        logging.info("JWT expired, obtaining a new one...")
        invalidate_jwt()
        jwt = get_jwt()
        headers["Authorization"] = f"Bearer {jwt}"
        response = requests.get(url, headers=headers, params=params)
    return response


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    token, expiration = _get_jwt_logic()
    logging.info(f"JWT Token: {token}")
    logging.info(f"Expires at: {expiration}")