import datetime
import sys
import weakref
import logging
import json
from threading import Lock

from playwright.sync_api import Page, Response, TimeoutError, sync_playwright
import requests

from modules import config
from modules.notify import notify_admin

logger = logging.getLogger(__name__)

HEADLESS = config.HEADLESS

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
        logger.debug("Quitting Chromium...")
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
            logger.debug(f"Found status {response.status} for {response.url}")
            return False, response.status
        return True, response.status

    @staticmethod
    def __check_only_one_instance_alive():
        if len(Chromium._instance) != 1:
            logger.error("Weird behaviour, too many alive references...exiting...")
            notify_admin(
                "Browser session in an inconsistent state (too many Chromium instances). "
                "The JWT/login flow cannot continue and needs manual intervention.",
                dedupe_key="chromium-instances",
            )
            sys.exit("Weird behaviour, too many alive references...exiting...")


def _config_page(page: Page):
    window_size = {"width": 1920, "height": 1080}
    page.wait_for_load_state()
    page.set_viewport_size(viewport_size=window_size)
    page.set_default_timeout(config.CHROMIUM_TIMEOUT)

def _perform_mlol_login(page: Page, username: str, password: str, chromium: Chromium):
    logger.debug("Logging into MLOL...")
    page.click("#mainmenu > div.nav-item.d-none.d-lg-flex.justify-content-end.align-items-center.col-4.gap-3 > button", timeout=config.CHROMIUM_TIMEOUT)
    page.fill("input[name='Username']", username, timeout=config.CHROMIUM_TIMEOUT)
    page.fill("input[name='Password']", password, timeout=config.CHROMIUM_TIMEOUT)
    page.click("#loginFormBlock > button", timeout=config.CHROMIUM_TIMEOUT)

    # Failed login detection
    try:
        warning_failed_login = (page.text_content(".page-title") or "").lower()
        if "avviso" in warning_failed_login:
            chromium.clean()
            notify_admin(
                "MLOL login failed — please check your MLOL credentials. "
                "Downloads cannot proceed until this is fixed.",
                dedupe_key="mlol-login-failed",
            )
            sys.exit("Login failed, please check your MLOL credentials!")
    except TimeoutError:
        pass


def _get_auth_info(page: Page, chromium: Chromium) -> dict:
    logger.debug("Clicking Esplora button...")
    page.click("#btnExplore", timeout=config.CHROMIUM_TIMEOUT)

    logger.debug("Clicking Edicola section...")
    newspapers_section = page.locator("#typology a[href='/search?idtype=600']")
    newspapers_section.click(timeout=config.CHROMIUM_TIMEOUT)

    logger.debug("Clicking Corriere della Sera...")
    corriere_sera = page.locator("a[href='/media/details/550276273']").first
    corriere_sera.click(timeout=config.CHROMIUM_TIMEOUT)

    logger.debug("Looking for Sfoglia online link...")
    pressreader_link = page.locator("a[href='/Media/View/550276273']")
    href = pressreader_link.get_attribute("href")
    if not href:
        logger.error("Sfoglia online link not found")
        return {}

    base_url = page.url.split("/media/")[0]
    href = f"{base_url}{href}"
    logger.debug("Navigating to PressReader: %s", href)

    try:
        with page.expect_response(lambda r: "authentication/v1/initialize" in r.url, timeout=30000) as resp_info:
            page.goto(href)
        return resp_info.value.json()
    except TimeoutError:
        logger.error("Timed out waiting for authentication/v1/initialize")
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
        notify_admin(
            "MLOL credentials are not set (MLOL_USERNAME / MLOL_PASSWORD). "
            "The service cannot authenticate and needs manual intervention.",
            dedupe_key="mlol-credentials-missing",
        )
        sys.exit("MLOL credentials are not set in environment variables!")

    chromium = Chromium.get_chromium()
    chromium.context.on("page", _config_page)
    chromium.context.new_page()

    try:
        logger.debug("Visiting MLOL...")
        page = chromium.context.pages[0]
        chromium.visit_site(page, config.MLOL_WEBSITE)  # entrypoint
        _perform_mlol_login(page, config.MLOL_USERNAME, config.MLOL_PASSWORD, chromium)
        _dismiss_mlol_modal(page)
        auth_info = _get_auth_info(page, chromium)

        jwt_token = auth_info.get("bearerToken", None)

        if not jwt_token:
            notify_admin(
                "JWT token could not be captured from PressReader. The login flow may have "
                "changed or MLOL is unavailable; downloads are blocked until this is resolved.",
                dedupe_key="jwt-capture-failed",
            )
            sys.exit("JWT token not found!")

        # Decode exp claim from JWT payload (middle segment, base64url)
        try:
            payload_b64 = jwt_token.split(".")[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)  # pad
            payload = json.loads(__import__("base64").urlsafe_b64decode(payload_b64))
            expected_expiry = datetime.datetime.fromtimestamp(payload["exp"])
        except Exception:
            expected_expiry = datetime.datetime.now() + datetime.timedelta(hours=1)
        logger.info("JWT token captured successfully. Expires at %s. Token: %s", expected_expiry.isoformat(), jwt_token)
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
            logger.debug("Returning cached JWT")
            return _jwt_cache
        
        if _jwt_file.exists():
            with open(_jwt_file, "r") as f:
                _jwt_cache = f.read().strip()
                if _jwt_cache:
                    logger.debug("Loaded JWT from cache file")
                    return _jwt_cache
        
        logger.info("Retrieving new JWT...")
        _jwt_cache, _ = _get_jwt_logic()

        # save to file
        with open(_jwt_file, "w") as f:
            f.write(_jwt_cache)

        logger.info("JWT retrieved and cached successfully")
        return _jwt_cache

def invalidate_jwt():
    """Invalidate cached JWT"""
    global _jwt_cache
    with _jwt_lock:
        _jwt_cache = None

        # remove cached file
        if _jwt_file.exists():
            _jwt_file.unlink()

        logger.info("JWT cache invalidated")


def authorized_request(url: str, params: dict[str,str]) -> requests.Response:
    """Make an authorized GET request with JWT, invalidate on 401"""
    jwt = get_jwt()
    headers = {
        "Authorization": f"Bearer {jwt}",
    }
    timeout = (config.REQUEST_TIMEOUT, config.REQUEST_TIMEOUT)
    response = requests.get(url, headers=headers, params=params, timeout=timeout)
    if response.status_code == 401:
        logger.info("JWT expired, obtaining a new one...")
        invalidate_jwt()
        jwt = get_jwt()
        headers["Authorization"] = f"Bearer {jwt}"
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
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
