import logging
import time
import threading
from pathlib import Path
from datetime import datetime
import asyncio

from modules import config
from modules.database import Publication, db, FileWorkflow
from modules.utils import get_caption, split_filename
from modules.telegram import get_telegram_credentials, create_telegram_client

from telethon import TelegramClient

logger = logging.getLogger(__name__)

class TelegramUploaderThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.ocr_folder = config.OCR_FOLDER
        self.done_folder = config.DONE_FOLDER
        self.delete_after_done = config.DELETE_AFTER_DONE
        
        self.api_id, self.api_hash, self.channel = get_telegram_credentials()
        self.client: TelegramClient | None = None
        self.loop = asyncio.new_event_loop()
        
    def setup_client(self):
        """Setup Telegram client without interactive prompts.
        The session must be created beforehand using the telegram_login.py helper.
        """
        async def async_setup():
            try:
                client = await create_telegram_client()
                logger.info("Telegram uploader client connected")
                return client
            except Exception as e:
                logger.error(f"Failed to setup Telegram client: {e}")
                raise

        try:
            self.client = self.loop.run_until_complete(async_setup())
            if self.client is None:
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to setup Telegram client: {e}")
            return False

    async def async_upload(self, pdf_file, display_name: str):
        if self.client is None:
            raise RuntimeError("Telegram client is not initialized")

        caption = get_caption(pdf_file, display_name)

        return await self.client.send_file(
            self.channel,
            pdf_file.__str__(),
            caption=caption
        )
    
    def upload_file(self, pdf_file: Path):
        """Upload a single PDF file to Telegram"""
        try:
            publication_name, date_str = split_filename(pdf_file)
            
            # Check if already uploaded
            db.connect(reuse_if_open=True)
            workflow = FileWorkflow.get_or_none(
                FileWorkflow.publication_name == publication_name,
                FileWorkflow.date == date_str
            )
            publication = Publication.get_or_none(Publication.name == publication_name)
            db.close()
            
            if workflow and workflow.uploaded:
                logger.debug(f"File {pdf_file.name} already uploaded")
                pdf_file.unlink(missing_ok=True)
                return
            
            if workflow and not workflow.ocr_processed:
                logger.warning(f"File {pdf_file.name} not OCR processed yet; skipping upload.")
                return

            display_name = publication.display_name if publication and publication.display_name else ""
            
            logger.info(f"Uploading {pdf_file.name} to Telegram")
            result = self.loop.run_until_complete(self.async_upload(pdf_file, display_name))
            
            # Update database
            if workflow and result.id:
                db.connect(reuse_if_open=True)
                workflow.uploaded = True
                workflow.channel_id = self.channel
                workflow.message_id = result.id
                workflow.updated_at = datetime.now()
                workflow.save()

                if publication:
                    publication.last_finished = date_str
                    publication.save()
                db.close()
            
            logger.info(f"Successfully uploaded {pdf_file.name}")
            
            if self.delete_after_done:
                pdf_file.unlink(missing_ok=True)
            else:
                done_path = self.done_folder / pdf_file.name
                pdf_file.rename(done_path)
            
        except Exception as e:
            logger.error(f"Error uploading {pdf_file.name}: {e}")
    
    def run(self):
        logger.info("Telegram uploader thread running")
        
        # Setup client
        if not self.setup_client():
            logger.error("Failed to setup Telegram client, thread exiting")
            return
        
        while True:
            try:
                # Find all PDF files (not .temp.pdf)
                pdf_files = [f for f in self.ocr_folder.glob("*.pdf") if not f.name.endswith(".temp.pdf")]
                
                for pdf_file in pdf_files:
                    self.upload_file(pdf_file)
                
                # Sleep for 30 seconds
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in Telegram uploader thread: {e}")
                time.sleep(30)
