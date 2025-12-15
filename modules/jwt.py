import datetime
import sys
import time
import weakref
import logging
from pathlib import Path
from threading import Lock

from playwright.sync_api import Page, Response, TimeoutError, sync_playwright
import requests

from modules import config

# Constants
TIMEOUT = 30000  # ms

_jwt_file = config.JWT_TOKEN
_jwt_cache = None
_jwt_lock = Lock()


class Chromium(object):
    _instance = []

    def __init__(
        self,
        headless: bool = True,
        trace: bool = False,
        timeout: int = 0,
    ):
        self.trace = trace
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context(locale="en-GB")
        self.context.clear_cookies()

        self.timeout = timeout
        self.context.set_default_timeout(self.timeout)
        if self.trace:
            self.context.tracing.start(screenshots=True, snapshots=True)

    def __new__(
        cls,
        headless: bool = True,
        trace: bool = False,
        timeout: int = 0,
    ):
        if Chromium._instance:
            Chromium.__check_only_one_instance_alive()
            return weakref.proxy(Chromium._instance[0])
        else:
            instance_local = super().__new__(cls)
            Chromium._instance.append(instance_local)
            return instance_local

    def clean(self, debug_trace: bool = False):
        logging.debug("Quitting Chromium...")
        if len(Chromium._instance) != 0:
            try:
                if debug_trace and self.trace:
                    self.context.tracing.stop(path=str(Path("trace.zip")))
            except Exception:
                pass
            self.context.close()
            self.browser.close()
            self.playwright.stop()
            self._instance.remove(self)

    @staticmethod
    def get_chromium():
        if len(Chromium._instance) == 0:
            return Chromium(headless=True, trace=False, timeout=TIMEOUT)
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
    page.set_default_timeout(TIMEOUT)

def _perform_mlol_login(page: Page, username: str, password: str, chromium: Chromium):
    logging.debug("Logging into MLOL...")
    page.fill("input[name='lusername']", username, timeout=0)
    page.fill("input[name='lpassword']", password, timeout=0)
    page.click("input[type='submit']", timeout=0)

    # Failed login detection
    try:
        warning_failed_login = (page.text_content(".page-title") or "").lower()
        if "avviso" in warning_failed_login:
            chromium.clean(debug_trace=True)
            sys.exit("Login failed, please check your MLOL credentials!")
    except TimeoutError:
        pass


def _mlol_to_pressreader(page: Page, chromium: Chromium) -> Page:
    # Clicking on catalogue
    typologies_menu_entry = page.query_selector("#caricatip")
    typologies_menu_entry.click()

    newspapers_section = page.locator(":nth-match(:text('EDICOLA'), 1)")
    newspapers_section.click()

    # Focusing on Corriere della Sera
    corriere_sera = page.locator("text=Corriere della Sera")
    corriere_sera.nth(0).click()

    pressreader_submit_button = page.locator(":nth-match(:text('SFOGLIA'), 1)")

    with chromium.context.expect_page() as pressreader_blank_target:
        pressreader_submit_button.click()
    page_pressreader = pressreader_blank_target.value
    page_pressreader.wait_for_load_state("domcontentloaded")

    assert "pressreader" in page_pressreader.title().lower(), Exception(
        "Failed tab switch"
    )
    return page_pressreader


def _dismiss_mlol_modal(page: Page):
    try:
        page.wait_for_selector("#FavModal")
        modal_dismissal_button = page.locator(
            "//div[@class='modal-footer']/button[@data-dismiss='modal']"
        )
        modal_dismissal_button.click()
    except TimeoutError:
        pass


def _handle_publication_button(p: Page):
    try:
        publication_button = p.wait_for_selector(
            "xpath=//label[@data-bind='click: selectTitle']"
        )
        publication_button.click()
    except TimeoutError:
        pass


def _login_pressreader(p: Page, username: str, password: str, chromium: Chromium):
    logging.debug("Logging into Pressreader...")
    p.fill("input[type='email']", username, timeout=0)
    p.fill("input[type='password']", password, timeout=0)

    try:
        stay_signed_in_checkbox = p.wait_for_selector(".checkbox")
        if stay_signed_in_checkbox.is_checked():
            stay_signed_in_checkbox.click()
    except TimeoutError:
        pass

    submit_button = p.wait_for_selector(
        "xpath=//div[@class='pop-group']/a[@role='link']"
    )
    submit_button.click()

    # Subscribe to login response for forbidden
    def _on_response(r: Response):
        if "Authentication/SignIn" in r.url:
            if r.status == 403:
                chromium.clean(debug_trace=True)
                sys.exit("Access denied to PressReader!")

    p.on("response", _on_response)

    # Failed login detection
    try:
        wrong_credentials_warning = p.query_selector(".infomsg >> text=Invalid")
        if wrong_credentials_warning and wrong_credentials_warning.is_visible():
            chromium.clean(debug_trace=True)
            sys.exit("Login failed, please check your Pressreader credentials!")
    except TimeoutError:
        pass


def _logout_safe(p: Page):
    try:
        profile_dialog_menu = p.wait_for_selector(".userphoto-title")
        profile_dialog_menu.click()
        logout_item = p.wait_for_selector(".pri-logout")
        logout_item.click()
    except TimeoutError:
        pass


def _get_jwt_logic() -> str:
    """Return JWT token captured from PressReader GetPageKeys request."""
    if not config.MLOL_USERNAME or not config.MLOL_PASSWORD:
        sys.exit("MLOL credentials are not set in environment variables!")

    chromium = Chromium(headless=True, trace=False, timeout=TIMEOUT)
    chromium.context.on("page", _config_page)
    chromium.context.new_page()

    try:
        # MLOL entry and login
        logging.debug("Visiting MLOL...")
        page = chromium.context.pages[0]
        chromium.visit_site(page, config.MLOL_WEBSITE)  # entrypoint
        _perform_mlol_login(page, config.MLOL_USERNAME, config.MLOL_PASSWORD, chromium)
        _dismiss_mlol_modal(page)
        press_page = _mlol_to_pressreader(page, chromium)

        time.sleep(5)

        today = datetime.datetime.now().strftime("%Y%m%d")

        # Navigate to a specific publication page and capture JWT
        press_page.goto(f"https://www.pressreader.com/italy/corriere-della-sera/{today}/page/1")
        logging.info("Waiting for GetPageKeys request...")

        try:
            request = press_page.wait_for_event(
                "request",
                timeout=10000,
                predicate=lambda req: "GetPageKeys" in req.url
                and req.headers.get("authorization", "").startswith("Bearer "),
            )
            auth_header = request.headers.get("authorization")
            jwt_token = auth_header[len("Bearer "):] if auth_header else None
        except TimeoutError:
            jwt_token = None

        if not jwt_token:
            chromium.clean(debug_trace=True)
            sys.exit("JWT token not found in request headers!")

        logging.info("JWT token captured successfully.")
        return jwt_token

    finally:
        #try:
        #    _logout_safe(press_page)
        #except Exception:
        #    pass
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
        _jwt_cache = _get_jwt_logic()

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

    token = _get_jwt_logic()
    logging.info(f"JWT Token: {token}")
