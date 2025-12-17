import logging
import time
import threading
from datetime import datetime

from modules.database import db, Publication, FileWorkflow
from modules.download import get_page_keys, download_issue
from modules.utils import temp_suffix, get_fw_key
from modules import config

import img2pdf

logger = logging.getLogger(__name__)

class DownloaderThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="DownloaderThread")
        self.download_folder = config.DOWNLOAD_FOLDER
    
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

                    logger.info(f"Fetching page keys for {fw_key}...")
                    page_keys = get_page_keys(str(publication.issue_id), str(fw.date))
                    if page_keys is not None:
                        keys_map[fw_key] = page_keys
                    time.sleep(1)
                
                # Download each issue
                for fw in fws:
                    fw_key = get_fw_key(fw)
                    if fw_key not in keys_map:
                        logger.error(f"Skipping download for {fw.publication_name} on {fw.date}: could not retrieve page keys")
                        continue
                    
                    filename = fw_key + temp_suffix
                    output_path = self.download_folder / filename

                    publication = pubs_map.get(str(fw.publication_name))
                    if publication is None:
                        logger.error(f"Publication {fw.publication_name} not found in database; skipping.")
                        continue

                    page_keys = keys_map[fw_key]

                    try:
                        logger.info(f"Downloading {filename}")
                        images = download_issue(
                            str(publication.name),
                            str(publication.issue_id),
                            str(fw.date),
                            int(publication.max_scale),
                            page_keys,
                        )

                        # save all images as pdf
                        if len(images) <= 1:
                            logger.warning(f"Not enough images downloaded for {filename} ({len(images)}); skipping PDF creation.")
                            return

                        logger.info(f"Saving as PDF...")
                        pdf_bytes = img2pdf.convert(images)
                        with open(output_path, 'wb') as f:
                            f.write(pdf_bytes)

                        logger.info(f"Successfully downloaded {filename}")

                    except Exception as e:
                        logger.error(f"Error downloading {filename}: {e}")
                        continue

                    db.connect(reuse_if_open=True)
                    fw.downloaded = True
                    fw.updated_at = datetime.now()
                    fw.save()
                    db.close()
                
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in downloader thread: {e}")
                time.sleep(60)
