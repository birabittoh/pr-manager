# PR Manager

A multithreaded Python application for downloading, OCR processing, and uploading publications.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables in `.env`:
   - Set your Telegram API credentials
   - Adjust paths and settings as needed

   Note: The Telegram uploader is non-interactive. Create a Telegram session before starting the service:
   ```bash
   python telegram_login.py
   ```
   The helper will prompt for your phone and code and save the session to the path configured by TELEGRAM_SESSION in modules/config.py.

3. Run the application:
```bash
python main.py
```

4. Access the web interface at http://localhost:8000

## Architecture

- **Downloader Thread**: Downloads publications from mock server
- **OCR Processor Thread**: Processes PDFs with OCR
- **Telegram Uploader Thread**: Uploads processed files to Telegram
- **API Server**: FastAPI server with web interface

## Features

- SQLite database with Peewee ORM
- JWT authentication with caching
- Web interface for managing publications
- Manual download trigger
- Workflow tracking
