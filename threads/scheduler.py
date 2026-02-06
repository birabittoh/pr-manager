import logging
import time
import threading
from datetime import datetime

from modules.database import db, Publication, FileWorkflow
from modules.download import get_issue_info
from modules.utils import date_format, get_fw_date
from modules import config

import schedule

logger = logging.getLogger(__name__)

SCHEDULER_DELAY = 1

def find_new_issues(threshold_date: str) -> list[FileWorkflow]:
    """Find new issues for all enabled publications and create FileWorkflow entries for them."""
    created_workflows = []
    try:
        today = datetime.now().strftime(date_format)

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
            key: str = latest_issue.get("key", "")
            if not key:
                logger.debug(f"No latest issue found for publication {pub.name}")
                continue
            
            issue_date = get_fw_date(key)
            if issue_date < threshold_date:
                logger.debug(f"Publication {pub.name}'s latest issue date {issue_date} is before threshold {threshold_date}")
                continue

            logger.info(f"Found new issue for publication {pub.name} on {issue_date}")
            db.connect(reuse_if_open=True)
            # create an empty FileWorkflow if not exists
            fw, created = FileWorkflow.get_or_create(
                publication_name=pub.name,
                key=key,
                defaults={"downloaded": False}
            )
            db.close()

            if fw.downloaded:
                logger.debug(f"Issue for publication {pub.name} on {issue_date} already scheduled/downloaded")
                continue

            if created:
                created_workflows.append(fw)
            
            logger.info(f"Scheduling download for publication {pub.name} on {issue_date}")
  
    except Exception as e:
        logger.error(f"Error in scheduler thread: {e}")
        
    return created_workflows

class SchedulerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="SchedulerThread")
        self.status = "waiting"

        threshold_date = config.THRESHOLD_DATE
        scheduler_time = config.SCHEDULER_TIME

        def job_wrapper():
            self.status = "running"
            try:
                find_new_issues(threshold_date)
            finally:
                self.status = "waiting"

        schedule.every().day.at(scheduler_time).do(job_wrapper)
    
    def run(self):
        logger.info("Scheduler thread running")

        while True:
            schedule.run_pending()
            time.sleep(SCHEDULER_DELAY)
