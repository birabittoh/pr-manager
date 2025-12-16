import logging
import time
import threading
from datetime import datetime
import ocrmypdf
from modules.database import db, FileWorkflow
from modules import config

import warnings
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

class OCRProcessorThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.download_folder = config.DOWNLOAD_FOLDER
        self.ocr_folder = config.OCR_FOLDER
        
    def process_file(self, temp_file):
        """Process a single temp PDF file with OCR"""
        try:
            # Parse filename: name_YYYYmmdd.temp.pdf
            filename = temp_file.stem.replace(".temp", "")
            publication_name = "_".join(filename.split("_")[:-1])
            date_str = filename.split("_")[-1]
            
            output_filename = f"{filename}.pdf"
            output_path = self.ocr_folder / output_filename
            
            # Check if already processed
            db.connect(reuse_if_open=True)
            workflow = FileWorkflow.get_or_none(
                FileWorkflow.publication_name == publication_name,
                FileWorkflow.date == date_str
            )
            db.close()
            
            if workflow and workflow.ocr_processed and output_path.exists():
                logger.debug(f"File {output_filename} already processed")
                temp_file.unlink(missing_ok=True)
                return

            if workflow and not workflow.downloaded:
                logger.warning(f"File {temp_file.name} not marked as downloaded; skipping OCR processing.")
                return
            
            logger.info(f"Processing {temp_file.name} with OCR")
            
            # Run OCR
            ocrmypdf.ocr(
                temp_file,
                output_path,
                skip_text=True,
                optimize=0,
                quiet=True,
                progress_bar=False
            )
            
            # Update database
            if workflow:
                db.connect(reuse_if_open=True)
                workflow.ocr_processed = True
                workflow.updated_at = datetime.now()
                workflow.save()
                db.close()
                
            # Remove temp file
            temp_file.unlink(missing_ok=True)
            logger.info(f"Successfully processed {output_filename}")
            
        except Exception as e:
            logger.error(f"Error processing {temp_file.name}: {e}")
    
    def run(self):
        logger.info("OCR processor thread running")
        
        while True:
            try:
                # Find all .temp.pdf files
                temp_files = list(self.download_folder.glob("*.temp.pdf"))
                
                for temp_file in temp_files:
                    self.process_file(temp_file)
                
                # Sleep for 30 seconds
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in OCR processor thread: {e}")
                time.sleep(30)
