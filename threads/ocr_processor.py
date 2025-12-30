import logging
from pathlib import Path
import time
import threading
from datetime import datetime
import ocrmypdf
from modules.database import db, Publication, FileWorkflow
from modules.utils import split_filename, temp_suffix, get_filename
from modules import config

import warnings

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

OCR_PROCESSOR_DELAY = 30

class OCRProcessorThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="OCRProcessorThread")
        self.download_folder = config.DOWNLOAD_FOLDER
        self.ocr_folder = config.OCR_FOLDER
        
    def process_file(self, temp_file: Path):
        """Process a single temp PDF file with OCR"""
        try:
            publication_name, date_str = split_filename(temp_file)
            output_filename = get_filename(publication_name, date_str)
            output_path = self.ocr_folder / output_filename
            ocr_language: str = "ita"
            
            # Check if already processed
            db.connect(reuse_if_open=True)
            workflow = FileWorkflow.get_or_none(
                FileWorkflow.publication_name == publication_name,
                FileWorkflow.key.contains(date_str)
            )

            if workflow:
                if workflow.ocr_processed and output_path.exists():
                    logger.debug(f"File {output_filename} already processed")
                    temp_file.unlink(missing_ok=True)
                    return

                if not workflow.downloaded:
                    logger.warning(f"File {temp_file.name} not marked as downloaded; skipping OCR processing.")
                    return

                publication = Publication.get_or_none(Publication.name == publication_name)
                if publication:
                    ocr_language = str(publication.language)
            
            db.close()
            
            logger.info(f"Processing {temp_file.name} with OCR")
            
            # Run OCR
            exit_code = ocrmypdf.ocr(
                temp_file,
                output_path,
                skip_text=True,
                optimize=0,
                quiet=True,
                progress_bar=False,
                language=ocr_language
            )
            if exit_code != 0:
                logger.error(f"OCR ({ocr_language}) processing failed for {temp_file.name} with exit code {exit_code}")
                return
            
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
                temp_files = list(self.download_folder.glob("*" + temp_suffix))
                
                for temp_file in temp_files:
                    self.process_file(temp_file)
                
            except Exception as e:
                logger.error(f"Error in OCR processor thread: {e}")

            time.sleep(OCR_PROCESSOR_DELAY)
