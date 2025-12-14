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
    
    def download_issue(self, publication, date_str):
        """Download a single issue"""
        filename = f"{publication.name}_{date_str}.temp.pdf"
        filepath = self.download_folder / filename
        
        # Check if already downloaded
        db.connect(reuse_if_open=True)
        workflow, created = FileWorkflow.get_or_create(
            publication_name=publication.name,
            date=date_str,
            defaults={'downloaded': False}
        )
        db.close()
        
        if workflow.downloaded and filepath.exists():
            logger.debug(f"Issue {filename} already downloaded")
            return
        
        try:
            logger.info(f"Downloading {filename}")
            images = download_issue(publication.name, publication.issue_id, date_str, publication.max_scale)
            
            # enqueue all images to be saved as PDF
            if len(images) <= 1:
                logger.warning(f"Not enough images downloaded for {filename} ({len(images)}); skipping PDF creation.")
                return

            save_images_as_pdf(images, filepath)
                
            db.connect(reuse_if_open=True)
            workflow.downloaded = True
            workflow.updated_at = datetime.now()
            workflow.save()
            db.close()
                
            logger.info(f"Successfully downloaded {filename}")
                
        except Exception as e:
            logger.error(f"Error downloading {filename}: {e}")
    
    def run(self):
        logger.info("Downloader thread running")

        while True:
            try:
                today = datetime.now().strftime("%Y%m%d")
                
                db.connect(reuse_if_open=True)
                publications: list[Publication] = list(
                    Publication.select().where(
                        (Publication.enabled == True) &
                        ((Publication.last_finished != today) | (Publication.last_finished.is_null()))
                    )
                )
                db.close()
                
                for pub in publications:
                    self.download_issue(pub, today)
                
                # Sleep for 6 hours
                sleep_hours = 6
                time.sleep(3600 * sleep_hours)
                
            except Exception as e:
                logger.error(f"Error in downloader thread: {e}")
                time.sleep(60)
