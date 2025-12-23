import logging
import time
import threading
from datetime import datetime

from modules.database import db, Publication, FileWorkflow
from modules.download import get_page_keys, download_issue
from modules.utils import get_fw_date, get_fw_id, pdf_suffix, temp_suffix, get_fw_key, thumbnail_suffix
from modules import config

import img2pdf

logger = logging.getLogger(__name__)

GET_PAGE_KEYS_DELAY = 1
DOWNLOADER_DELAY = 30

class DownloaderThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="DownloaderThread")
        self.download_folder = config.DOWNLOAD_FOLDER
        self.ocr_folder = config.OCR_FOLDER
    
    def run(self):
        logger.info("Downloader thread running")

        while True:
            try:

                db.connect(reuse_if_open=True)
                # Get FileWorkflows that are not yet downloaded
                fws: list[FileWorkflow] = list(FileWorkflow.select().where((FileWorkflow.downloaded == False)))
                db.close()

                pubs_map: dict[str, Publication] = {}
                pubs_names = set(fw.publication_name for fw in fws)
                pubs_list: list[Publication] = list(Publication.select().where(Publication.name.in_(pubs_names)))
                for pub in pubs_list:
                    pubs_map[str(pub.name)] = pub

                # Get keys for each FileWorkflow first
                keys_map: dict[str, list[dict[str,str]]] = {}
                for fw in fws:
                    fw_key = get_fw_key(fw)
                    publication = pubs_map.get(str(fw.publication_name))
                    if publication is None:
                        logger.error(f"Publication {fw.publication_name} not found in database; skipping.")
                        continue

                    time.sleep(GET_PAGE_KEYS_DELAY)
                    logger.info(f"Fetching page keys for {fw_key}...")
                    page_keys, status_code = get_page_keys(str(fw.key))
                    if status_code == 404:
                        # delete the FileWorkflow as the issue does not exist
                        logger.error(f"Issue for {fw_key} not found (404). Deleting workflow.")
                        db.connect(reuse_if_open=True)
                        fw.delete_instance()
                        db.close()
                        continue
                    if len(page_keys) >= 0:
                        keys_map[fw_key] = page_keys
                
                # Download each issue
                for fw in fws:
                    fw_key = get_fw_key(fw)
                    if fw_key not in keys_map:
                        logger.error(f"Skipping download for {fw.publication_name} on {get_fw_date(str(fw.key))}: could not retrieve page keys")
                        continue
                    
                    filename = fw_key.replace(pdf_suffix, temp_suffix)
                    output_path = self.download_folder / filename

                    publication = pubs_map.get(str(fw.publication_name))
                    if publication is None:
                        logger.error(f"Publication {fw.publication_name} not found in database; skipping.")
                        continue

                    page_keys = keys_map[fw_key]

                    images: list[bytes] = []

                    logger.info(f"Attempting download for {fw_key} with issue number {get_fw_id(str(fw.key))}...")
                    images = download_issue(
                        str(fw.publication_name),
                        str(fw.key),
                        int(publication.max_scale),
                        page_keys,
                    )

                    # save all images as pdf
                    if len(images) <= 1:
                        logger.warning(f"Not enough images downloaded for {filename} ({len(images)}); skipping PDF creation.")
                        return

                    logger.info(f"Saving as PDF...")
                    pdf_bytes = img2pdf.convert(images)
                    if pdf_bytes is None:
                        logger.error(f"Failed to convert images to PDF for {filename}")
                        return
                    
                    with open(output_path, 'wb') as f:
                        _ = f.write(pdf_bytes)

                    # Also save thumbnail as jpg
                    ocr_output_path = self.ocr_folder / (filename.replace(temp_suffix, thumbnail_suffix))
                    with open(ocr_output_path, 'wb') as f:
                        _ = f.write(images[0])

                    logger.info(f"Successfully downloaded {filename}")

                    db.connect(reuse_if_open=True)
                    fw.downloaded = True
                    fw.updated_at = datetime.now()
                    fw.save()
                    db.close()
                
            except Exception as e:
                logger.error(f"Error in downloader thread: {e}")

            time.sleep(DOWNLOADER_DELAY)
