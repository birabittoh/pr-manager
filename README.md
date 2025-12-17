# PR Manager

A multithreaded Python application for downloading, OCR processing, and uploading publications.

## Setup (Debian)

1. Install dependencies:
   ```bash
   sudo apt install python3.13-venv tesseract-ocr-ita ghostscript
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python -m playwright install --with-deps chromium
   ```

2. Set your credentials in `.env`:
   ```bash
   cp .env.example .env
   ```

3. Create a Telegram session file:
   ```bash
   python telegram_login.py
   ```

4. Run the application:
   ```bash
   python main.py
   ```

5. Access the web interface at http://localhost:8000

## Architecture

- **Scheduler Thread**: Starts each workflow
- **Downloader Thread**: Downloads publications
- **OCR Processor Thread**: Processes PDFs with OCR
- **Telegram Uploader Thread**: Uploads processed files to Telegram
- **API Server**: FastAPI server with web interface

## Features

- SQLite database with Peewee ORM
- JWT authentication with caching
- Web interface for managing publications
- Manual download trigger
- Workflow tracking

## License
PR Manager is provided under the MIT license.