import warnings
from dotenv import load_dotenv

# Suppress all warnings
warnings.filterwarnings("ignore")

# Load environment variables
load_dotenv()
from modules import config

# Configure logging (must happen before any thread imports)
from modules.logging_setup import setup_logging
setup_logging()

import logging
logger = logging.getLogger(__name__)

# Initialize database
from modules.database import init_db
init_db()

# Import threads
from threads.scheduler import SchedulerThread
from threads.downloader import DownloaderThread
from threads.ocr_processor import OCRProcessorThread
from threads.telegram_uploader import TelegramUploaderThread
from threads.manager import ThreadManager
from threads.api_server import start_api_server

def main():
    logger.info("Starting PR Manager")

    manager = ThreadManager()
    manager.register(SchedulerThread)
    manager.register(DownloaderThread)
    manager.register(OCRProcessorThread)
    manager.register(TelegramUploaderThread)
    manager.start_all()
    manager.start_supervisor()

    # API server (runs in main thread)
    logger.info("Starting API server")
    start_api_server(manager=manager)

if __name__ == "__main__":
    exit(main())
