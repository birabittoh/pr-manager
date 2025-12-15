import logging
import time
import threading
from datetime import datetime
from modules.database import db, Publication, FileWorkflow
from modules.download import download_issue, get_issue_info
from modules import config
from modules.pdf import save_images_as_pdf

logger = logging.getLogger(__name__)

SLEEP_HOURS = 1

class SchedulerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.threshold_date = config.THRESHOLD_DATE
        if self.threshold_date is None:
            self.threshold_date = "19700101"
    
    def run(self):
        logger.info("Scheduler thread running")

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
                    info = get_issue_info(str(pub.issue_id))
                    if info is None:
                        logger.error(f"Failed to get issue info for publication {pub.name}")
                        continue

                    latest_issue = info.get("latestIssue", {})
                    issue_timestamp = latest_issue.get("issueDate", "")
                    if issue_timestamp == "":
                        logger.error(f"No issue date found for publication {pub.name}")
                        continue

                    # issue_timestamp is in 2025-12-13T00:00:00Z format, convert to YYYYMMDD
                    issue_date = issue_timestamp.split("T")[0].replace("-", "")
                    if issue_date < self.threshold_date:
                        logger.debug(f"Publication {pub.name}'s latest issue date {issue_date} is before threshold {self.threshold_date}")
                        continue

                    db.connect(reuse_if_open=True)
                    # create an empty FileWorkflow if not exists
                    fw, created = FileWorkflow.get_or_create(
                        publication=pub,
                        issue_date=issue_date,
                        issue_id=pub.issue_id,
                        defaults={"downloaded": False}
                    )
                    db.close()

                    if fw.downloaded:
                        logger.debug(f"Issue for publication {pub.name} on {issue_date} already scheduled/downloaded")
                        continue

                    logger.info(f"Scheduling download for publication {pub.name} on {issue_date}")
                    time.sleep(5)
                
                time.sleep(3600 * SLEEP_HOURS)
  
            except Exception as e:
                logger.error(f"Error in downloader thread: {e}")
                time.sleep(60)
