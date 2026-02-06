import logging
import sys
import warnings
from dotenv import load_dotenv

# Suppress all warnings
warnings.filterwarnings("ignore")

# Load environment variables
load_dotenv()
from modules import config

# Configure logging
log_level = config.LOG_LEVEL
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Initialize database
from modules.database import init_db
init_db()

# Import threads
from threads.scheduler import SchedulerThread
from threads.downloader import DownloaderThread
from threads.ocr_processor import OCRProcessorThread
from threads.telegram_uploader import TelegramUploaderThread
from threads.api_server import start_api_server

def main():
    logger.info("Starting PR Manager")
    
    # Start threads
    threads = []

    # Scheduler thread
    scheduler = SchedulerThread()
    scheduler.daemon = True 
    scheduler.start()
    threads.append(scheduler)
    logger.info("Scheduler thread started")
    
    # Downloader thread
    downloader = DownloaderThread()
    downloader.daemon = True
    downloader.start()
    threads.append(downloader)
    logger.info("Downloader thread started")
    
    # OCR processor thread
    ocr_processor = OCRProcessorThread()
    ocr_processor.daemon = True
    ocr_processor.start()
    threads.append(ocr_processor)
    logger.info("OCR processor thread started")
    
    # Telegram uploader thread
    telegram_uploader = TelegramUploaderThread()
    telegram_uploader.daemon = True
    telegram_uploader.start()
    threads.append(telegram_uploader)
    logger.info("Telegram uploader thread started")
    
    # API server (runs in main thread)
    logger.info("Starting API server")
    start_api_server(threads=threads)

if __name__ == "__main__":
    exit(main())
