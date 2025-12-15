import logging
import time
from io import BytesIO

import requests

from modules.jwt import authorized_request

logger = logging.getLogger(__name__)

MIN_SCALE = 50
MAX_RETRIES = 10
SCALE_STEP = 2

ISSUE_NUMBER_FMT ="{issue_id}{issue_date}00000000001001"

def _format_issue_number(issue_id: str, issue_date: str) -> str:
    """Generate issue number from ID and date"""
    return ISSUE_NUMBER_FMT.format(issue_id=issue_id, issue_date=issue_date)


def _download_image(issue_number: str, scale: str, page_number: int, key: str) -> bytes | None:
    """Download a single page image"""
    url = "https://i.prcdn.co/img"
    current_scale = int(scale)
    retries = 0
    
    while current_scale >= MIN_SCALE:
        params = {
            "file": issue_number,
            "page": page_number,
            "scale": str(current_scale),
            "ticket": key
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
        
        while retries < MAX_RETRIES:
            try:
                response = requests.get(url, headers=headers, params=params)
                
                if response.status_code == 500:
                    retries += 1
                    logger.warning(f"500 error for page {page_number}, retrying ({retries}/{MAX_RETRIES})...")
                    time.sleep(5)
                    continue
                    
                if response.status_code == 403:
                    current_scale -= SCALE_STEP
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
                
        if retries >= MAX_RETRIES:
            logger.error(f"Max retries reached for page {page_number} (500 error)")
            return None
    
    logger.error(f"403 error for page {page_number}, minimum scale reached")
    return None


def _get_page_keys(issue_id: str, issue_date: str) -> dict | None:
    """Get page keys for an issue"""
    url = "https://ingress.pressreader.com/services/IssueInfo/GetPageKeys"
    params = {
        "issue": _format_issue_number(issue_id, issue_date),
        "pageNumber": "0",
        "preview": "false"
    }
    
    try:
        response = authorized_request(url, params)
            
        if not response.ok:
            logger.error(f"Error in request: {response.status_code}")
            return None
            
        return response.json()
        
    except Exception as e:
        logger.error(f"Exception getting page keys: {e}")
        return None

def get_issue_info(issue_id: str) -> dict | None:
    """Get issue info for a publication"""
    url = f"https://ingress.pressreader.com/services/catalog/v2/publications/{issue_id}"
    params = {}

    try:
        response = authorized_request(url, params)

        if not response.ok:
            logger.error(f"Error in request: {response.status_code}")
            return None

        return response.json()
    except Exception as e:
        logger.error(f"Exception getting issue info: {e}")
        return None
    #

def download_issue(name: str, issue_id: str, issue_date: str, max_scale: int) -> list[BytesIO]:
    """Download all page images for a given issue.

    Args:
        name: Human-friendly publication name (used for logs only).
        issue_id: PressReader issue ID string.
        issue_date: Issue date in YYYYMMDD format.
        max_scale: Preferred scale (will step down on 403).

    Returns:
        List of BytesIO objects containing image bytes for each successfully downloaded page.
    """
    logger.info(f"Fetching page keys for {name} ({issue_id}) on {issue_date}...")
    response_data = _get_page_keys(issue_id, issue_date)

    if response_data is None:
        logger.error(f"Failed to get page keys; aborting.")
        return []

    issue_number = _format_issue_number(issue_id, issue_date)
    images: list[BytesIO] = []

    page_keys = response_data.get("PageKeys", [])
    if not page_keys:
        logger.warning("No pages reported by API.")
        return []

    l = len(page_keys)
    logging.debug(f"Issue has {l} pages.")

    if l < 2:
        logger.warning("Issue has less than 2 pages.")
        return []

    for page in page_keys:
        page_number = page.get("PageNumber")
        key = page.get("Key")
        if page_number is None or key is None:
            logger.warning("Skipping page with missing PageNumber/Key.")
            continue

        img_bytes = _download_image(issue_number, str(max_scale), int(page_number), str(key))
        if img_bytes:
            images.append(BytesIO(img_bytes))
        else:
            logger.warning(f"Failed to download page {page_number}.")

    logger.info(f"Downloaded {len(images)}/{len(page_keys)} pages for {name} ({issue_date}).")
    return images
