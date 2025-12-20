import logging
import time

import requests

from modules import config
from modules.jwt import authorized_request

logger = logging.getLogger(__name__)

ISSUE_NUMBER_FMT ="{issue_id}{issue_date}00000000001001"

PRESSREADER_BASE_URL = "https://ingress.pressreader.com/services/"
PRESSREADER_CDN_URL = "https://i.prcdn.co/img"

GET_PAGE_KEYS_ENDPOINT = "IssueInfo/GetPageKeys"
GET_ISSUE_INFO_ENDPOINT = "catalog/v2/publications/"

RETRY_DELAY = 5

def _format_issue_number(issue_id: str, issue_date: str) -> str:
    """Generate issue number from ID and date"""
    return ISSUE_NUMBER_FMT.format(issue_id=issue_id, issue_date=issue_date)


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
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-GPC": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Priority": "u=0, i",
            "TE": "trailers"
        }
        
        while retries < config.MAX_RETRIES:
            try:
                response = requests.get(url, headers=headers, params=params)
                
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


def get_page_keys(issue_id: str, issue_date: str) -> tuple[list[dict[str,str]], int]:
    """Get page keys for an issue"""
    url = PRESSREADER_BASE_URL + GET_PAGE_KEYS_ENDPOINT
    params = {
        "issue": _format_issue_number(issue_id, issue_date),
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
        response = authorized_request(url, params)

        if not response.ok:
            logger.error(f"Error in request: {response.status_code}")
            return None

        return response.json()
    except Exception as e:
        logger.error(f"Exception getting issue info: {e}")
        return None
    #

def download_issue(name: str, issue_id: str, issue_date: str, max_scale: int, page_keys: list[dict[str,str]]) -> list[bytes]:
    """Download all page images for a given issue.

    Args:
        name: Human-friendly publication name (used for logs only).
        issue_id: PressReader issue ID string.
        issue_date: Issue date in YYYYMMDD format.
        max_scale: Preferred scale (will step down on 403).

    Returns:
        List of bytes objects containing image bytes for each successfully downloaded page.
    """

    issue_number = _format_issue_number(issue_id, issue_date)
    images: list[bytes] = []

    l = len(page_keys)
    logging.debug(f"Issue has {l} pages.")

    if l <= 1:
        logger.warning("Issue has less than 2 pages.")
        return []

    page_keys = sorted(page_keys, key=lambda x: x.get("PageNumber", 0))

    for index, page in enumerate(page_keys):
        page_number = int(page.get("PageNumber") or index)
        key = page.get("Key")
        if key is None:
            logger.warning(f"Skipping page {page_number} with missing Key.")
            continue

        img_bytes = _download_image(issue_number, max_scale, page_number, key)
        if img_bytes:
            images.append(img_bytes)
        else:
            logger.warning(f"Failed to download page {page_number}.")

    logger.info(f"Downloaded {len(images)}/{len(page_keys)} pages for {name} ({issue_date}).")
    return images
