import logging
import time

import requests

from modules import config
from modules.jwt import authorized_request
from modules.jwt_quick import unauthorized_request
from modules.utils import get_fw_date

logger = logging.getLogger(__name__)

VALID_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0"

PRESSREADER_BASE_URL = "https://ingress.pressreader.com/services/"
PRESSREADER_CDN_URL = "https://i.prcdn.co/img"

GET_PAGE_KEYS_ENDPOINT = "IssueInfo/GetPageKeys"
GET_ISSUE_INFO_ENDPOINT = "catalog/v2/publications/"

RETRY_DELAY = 5

def _download_image(issue_number: str, scale: int, page_number: int, key: str) -> bytes | None:
    """Download a single page image"""
    url = PRESSREADER_CDN_URL
    current_scale = scale
    retries = 0
    
    while current_scale >= config.MIN_SCALE:
        params = {
            "file": issue_number,
            "page": page_number,
            "scale": str(current_scale),
            "ticket": key,
        }
        
        headers = { "User-Agent": VALID_USER_AGENT }
        
        while retries < config.MAX_RETRIES:
            try:
                logger.debug(f"GET {url}?{'&'.join(f'{k}={v}' for k,v in params.items())}")
                response = requests.get(url, params=params, headers=headers)
                
                if response.status_code == 500:
                    retries += 1
                    logger.warning(f"500 error for page {page_number}, retrying ({retries}/{config.MAX_RETRIES})...")
                    time.sleep(RETRY_DELAY)
                    continue
                    
                if response.status_code == 403:
                    
                    current_scale -= config.SCALE_STEP
                    logger.warning(f"403 error for page {page_number}, retrying with lower scale: {current_scale}")
                    retries = 0
                    break
                    
                if not response.ok:
                    logger.error(f"Failed to download image for page {page_number}. Status code: {response.status_code}")
                    return None
                    
                logger.debug(f"Downloaded page {page_number}")
                return response.content
                
            except Exception as e:
                logger.error(f"Exception downloading page {page_number}: {e}")
                retries += 1
                
        if retries >= config.MAX_RETRIES:
            logger.error(f"Max retries reached for page {page_number} (500 error)")
            return None
    
    logger.error(f"403 error for page {page_number}, minimum scale reached")
    return None


def get_page_keys(issue_key: str) -> tuple[list[dict[str,str]], int]:
    """Get page keys for an issue"""
    url = PRESSREADER_BASE_URL + GET_PAGE_KEYS_ENDPOINT
    params = {
        "issue": issue_key,
        "pageNumber": "0",
        "preview": "false"
    }
    
    try:
        response = authorized_request(url, params)
            
        if not response.ok:
            logger.error(f"Error in request: {response.status_code}")
            return [], response.status_code
            
        response_data = response.json()
        page_keys = response_data.get("PageKeys", [])
        if not page_keys:
            logger.warning("No pages reported by API.")
            return [], 500
        return page_keys, 200
        
    except Exception as e:
        logger.error(f"Exception getting page keys: {e}")
        return [], 500

def get_issue_info(issue_id: str) -> dict | None:
    """Get issue info for a publication"""
    url = PRESSREADER_BASE_URL + GET_ISSUE_INFO_ENDPOINT + issue_id
    params = {}

    try:
        logger.debug(f"Getting issue info for issue ID {issue_id}")
        response = unauthorized_request(url, params)

        if not response.ok:
            logger.error(f"Error in request: {response.status_code}")
            return None

        return response.json()
    except Exception as e:
        logger.error(f"Exception getting issue info: {e}")
        return None
    #

def download_issue(name: str, key: str, max_scale: int, page_keys: list[dict[str,str]]) -> list[bytes]:
    """Download all page images for a given issue.

    Args:
        name: Human-friendly publication name (used for logs only).
        key: Issue key from FileWorkflow.
        max_scale: Preferred scale (will step down on 403).
        page_keys: List of page key dictionaries as returned by get_page_keys().

    Returns:
        List of bytes objects containing image bytes for each successfully downloaded page.
    """

    images: list[bytes] = []

    l = len(page_keys)
    logging.debug(f"Issue has {l} pages.")

    if l <= 1:
        logger.warning("Issue has less than 2 pages.")
        return []

    page_keys = sorted(page_keys, key=lambda x: x.get("PageNumber", 0))

    for index, page in enumerate(page_keys):
        page_number = int(page.get("PageNumber") or index + 1)
        page_key = page.get("Key")
        if page_key is None:
            logger.warning(f"Skipping page {page_number} with missing Key.")
            continue

        img_bytes = _download_image(key, max_scale, page_number, page_key)
        if img_bytes:
            images.append(img_bytes)
        else:
            logger.warning(f"Failed to download page {page_number}.")
            return []

    logger.info(f"Downloaded {len(images)}/{len(page_keys)} pages for {name} ({get_fw_date(key)}).")
    return images
