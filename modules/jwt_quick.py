import logging
from threading import Lock

import requests

from modules import config

logger = logging.getLogger(__name__)

PRESSREADER_LANGUAGE = "it"
PRESSREADER_URL = "https://www.pressreader.com"
PRESSREADER_INIT_ENDPOINT = "/authentication/v1/initialize"
PRESSREADER_CATALOG_ENDPOINT = "/catalog"

_jwt_file = config.LITE_JWT_TOKEN
_jwt_cache = None
_jwt_lock = Lock()

def _get_jwt_logic() -> str:
    url = PRESSREADER_URL + PRESSREADER_INIT_ENDPOINT
    data = {
        "tickets": [],
        "language": PRESSREADER_LANGUAGE,
        "urlReferrer": "",
        "url": f"{PRESSREADER_URL}/{PRESSREADER_LANGUAGE}{PRESSREADER_CATALOG_ENDPOINT}",
    }
    response = requests.post(url, json=data)
    response.raise_for_status()
    json_data = response.json()
    bearer_token = json_data.get("bearerToken", "")
    if not bearer_token:
        raise ValueError("No bearerToken found in response")
    return bearer_token

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
        _jwt_cache = _get_jwt_logic()

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


def unauthorized_request(url: str, params: dict[str,str]) -> requests.Response:
    """Make an authorized GET request with JWT, invalidate on 401"""
    jwt = get_jwt()
    headers = {
        "Authorization": f"Bearer {jwt}",
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 401:
        logger.info("JWT expired, obtaining a new one...")
        invalidate_jwt()
        jwt = get_jwt()
        headers["Authorization"] = f"Bearer {jwt}"
        response = requests.get(url, headers=headers, params=params)
    return response
