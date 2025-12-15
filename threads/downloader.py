import logging
import time
import threading
from datetime import datetime
import requests
from modules.database import db, Publication, FileWorkflow
from modules.jwt import get_jwt, invalidate_jwt
from modules.download import download_issue
from modules import config
from modules.pdf import save_images_as_pdf

logger = logging.getLogger(__name__)

class DownloaderThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.download_folder = config.DOWNLOAD_FOLDER
    
    def download_issue(self, fw: FileWorkflow):
        """Download a single issue"""
        filename = f"{fw.publication_name}_{fw.date}.temp.pdf"
        filepath = self.download_folder / filename

        db.connect(reuse_if_open=True)
        publication: Publication = Publication.get(Publication.name == fw.publication_name)
        db.close()
        
        try:
            logger.info(f"Downloading {filename}")
            images = download_issue(str(publication.name), str(publication.issue_id), str(fw.date), int(publication.max_scale))
            
            # enqueue all images to be saved as PDF
            if len(images) <= 1:
                logger.warning(f"Not enough images downloaded for {filename} ({len(images)}); skipping PDF creation.")
                return

            save_images_as_pdf(images, filepath)
                
            logger.info(f"Successfully downloaded {filename}")
                
        except Exception as e:
            logger.error(f"Error downloading {filename}: {e}")
    
    def run(self):
        logger.info("Downloader thread running")

        while True:
            try:
                today = datetime.now().strftime("%Y%m%d")
                
                db.connect(reuse_if_open=True)
                # Get FileWorkflows that are not yet downloaded
                fws: list[FileWorkflow] = list(FileWorkflow.select().where((FileWorkflow.downloaded == False)))
                
                for fw in fws:
                    self.download_issue(fw)
                    
                    db.connect(reuse_if_open=True)
                    fw.downloaded = True
                    fw.updated_at = datetime.now()
                    fw.save()
                    db.close()
                
                # Sleep for 6 hours
                sleep_hours = 6
                time.sleep(3600 * sleep_hours)
                
            except Exception as e:
                logger.error(f"Error in downloader thread: {e}")
                time.sleep(60)
