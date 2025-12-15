import logging
import time
import threading
from datetime import datetime
from modules.database import db, Publication, FileWorkflow
from modules.download import get_issue_info
from modules import config

logger = logging.getLogger(__name__)

class SchedulerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.threshold_date = config.THRESHOLD_DATE or "19700101"
        self.sleep_hours = config.SLEEP_HOURS or 8
    
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
                    time.sleep(5)
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

                    logger.info(f"Found new issue for publication {pub.name} on {issue_date}")
                    db.connect(reuse_if_open=True)
                    # create an empty FileWorkflow if not exists
                    fw, created = FileWorkflow.get_or_create(
                        publication_name=pub.name,
                        date=issue_date,
                        defaults={"downloaded": False}
                    )
                    db.close()

                    if fw.downloaded:
                        logger.debug(f"Issue for publication {pub.name} on {issue_date} already scheduled/downloaded")
                        continue

                    logger.info(f"Scheduling download for publication {pub.name} on {issue_date}")
                
                time.sleep(3600 * self.sleep_hours)
  
            except Exception as e:
                logger.error(f"Error in scheduler thread: {e}")
                time.sleep(60)
