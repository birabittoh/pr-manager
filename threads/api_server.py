import logging
from datetime import datetime
from pathlib import Path
import asyncio

from modules.database import db, Publication, FileWorkflow
from modules.utils import get_key
from modules.telegram import download_file_from_telegram
from modules import config

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import uvicorn
from pydantic import BaseModel

from threads.scheduler import find_new_issues

logger = logging.getLogger(__name__)

DELETION_DELAY = 300

app = FastAPI(title="PR Manager API")

# Mount static files
static_path = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

async def _delete_file_later(path: Path, delay: int = 300):
    """Delete a file after a delay, ensuring it's inside the DONE_FOLDER."""
    await asyncio.sleep(delay)
    try:
        # Safety: ensure we only delete files under config.DONE_FOLDER
        try:
            path.resolve().relative_to(config.DONE_FOLDER.resolve())
        except Exception:
            logger.warning(f"Refusing to delete {path}: not inside DONE_FOLDER")
            return
        if path.exists():
            path.unlink()
            logger.info(f"Deleted file {path} after {delay} seconds")
    except Exception as e:
        logger.error(f"Failed to delete {path}: {e}")

class PublicationUpdate(BaseModel):
    enabled: bool | None = None
    display_name: str | None = None
    issue_id: str | None = None
    max_scale: int | None = None
    language: str | None = None

class PublicationCreate(BaseModel):
    name: str
    display_name: str | None = None
    issue_id: str
    max_scale: int
    language: str

class ManualDownload(BaseModel):
    publication_name: str
    dates: list[str]

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page"""
    html_file = Path(__file__).parent.parent / "static" / "index.html"
    with open(html_file, 'r') as f:
        return f.read()

@app.get("/api/health")
async def health():
    """Health check endpoint"""
    now = datetime.now()
    hour, minute = map(int, config.SCHEDULER_TIME.split(":"))
    next_check_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_check_time <= now:
        next_check_time = next_check_time.replace(day=now.day + 1)
    next_check_in_seconds = (next_check_time - now).total_seconds()
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "next_check_in_seconds": next_check_in_seconds}

@app.post("/api/check")
async def force_check():
    """Force an immediate check for new publications"""
    response = find_new_issues(config.THRESHOLD_DATE)
    return response

@app.get("/api/publications")
async def get_publications():
    """Get all publications"""
    db.connect(reuse_if_open=True)
    publications = list(Publication.select().dicts())
    db.close()
    return publications

@app.post("/api/publications")
async def create_publication(pub: PublicationCreate):
    """Create a new publication"""
    db.connect(reuse_if_open=True)
    try:
        publication = Publication.create(
            name=pub.name,
            display_name=pub.display_name,
            issue_id=pub.issue_id,
            max_scale=pub.max_scale,
            language=pub.language
        )
        result = {
            "id": publication.id,
            "name": publication.name,
            "display_name": publication.display_name,
            "issue_id": publication.issue_id,
            "max_scale": publication.max_scale,
            "language": publication.language,
            "enabled": publication.enabled
        }
        db.close()
        return result
    except Exception as e:
        db.close()
        raise HTTPException(status_code=400, detail=str(e))

@app.patch("/api/publications/{name}")
async def update_publication(name: str, update: PublicationUpdate):
    """Update a publication"""
    db.connect(reuse_if_open=True)
    pub = Publication.get_or_none(Publication.name == name)
    if not pub:
        db.close()
        raise HTTPException(status_code=404, detail="Publication not found")
    
    if update.enabled is not None:
        pub.enabled = update.enabled
    if update.display_name is not None:
        pub.display_name = update.display_name
    if update.issue_id is not None:
        pub.issue_id = update.issue_id
    if update.max_scale is not None:
        pub.max_scale = update.max_scale
    if update.language is not None:
        pub.language = update.language
    
    pub.save()
    db.close()
    return {"status": "updated"}

@app.delete("/api/publications/{name}")
async def delete_publication(name: str):
    """Delete a publication"""
    db.connect(reuse_if_open=True)
    pub = Publication.get_or_none(Publication.name == name)
    if not pub:
        db.close()
        raise HTTPException(status_code=404, detail="Publication not found")
    
    pub.delete_instance()
    db.close()
    return {"status": "deleted"}

@app.get("/api/workflow")
async def get_workflow(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("", description="Search by publication name or date")
):
    """Get workflow status for files with pagination and search"""
    db.connect(reuse_if_open=True)
    
    # Build query
    query = FileWorkflow.select()
    
    # Apply search filter
    if search:
        search_lower = search.lower()
        query = query.where(
            (FileWorkflow.publication_name.contains(search_lower)) |
            (FileWorkflow.date.contains(search))
        )
    
    # Get total count
    total_count = query.count()
    total_pages = (total_count + limit - 1) // limit  # Ceiling division
    
    # Apply pagination
    offset = (page - 1) * limit
    workflows = list(
        query.order_by(FileWorkflow.created_at.desc())
        .limit(limit)
        .offset(offset)
        .dicts()
    )
    
    db.close()
    
    return {
        "workflows": workflows,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

@app.get("/api/workflow/{publication_name}/{date_str}")
async def get_downloaded_file(publication_name: str, date_str: str):
    """Download a PDF file from Telegram"""
    # Check if file exists and is uploaded
    db.connect(reuse_if_open=True)
    workflow = FileWorkflow.get_or_none(
        FileWorkflow.publication_name == publication_name,
        FileWorkflow.date == date_str,
        FileWorkflow.uploaded == True
    )
    db.close()

    if not workflow:
        raise HTTPException(
            status_code=404, 
            detail="File not found or not uploaded yet"
        )

    # Generate filename
    filename = get_key(publication_name, date_str)
    
    # Save file into DONE_FOLDER
    done_file = config.DONE_FOLDER / filename
    if done_file.exists():
        logger.info(f"Serving existing file {done_file}")
        return FileResponse(
            path=str(done_file),
            filename=filename,
            media_type='application/pdf',
        )
    
    try:
        if workflow.channel_id is None or workflow.message_id is None:
            raise HTTPException(
                status_code=500,
                detail="Workflow metadata incomplete (missing channel_id or message_id)"
            )
        # Download file from Telegram into DONE_FOLDER
        logger.info(f"Downloading {filename} from Telegram (channel: {workflow.channel_id}, message: {workflow.message_id})")
        
        downloaded_path = await download_file_from_telegram(
            channel_id=workflow.channel_id,
            message_id=workflow.message_id,
            output_path=done_file
        )

        if config.DELETE_AFTER_DONE:
            try:
                asyncio.create_task(_delete_file_later(downloaded_path, DELETION_DELAY))
                logger.info(f"Scheduled deletion for {downloaded_path} in {DELETION_DELAY} seconds")
            except Exception as e:
                logger.error(f"Failed to schedule deletion for {downloaded_path}: {e}")
        
        # Return file as download
        return FileResponse(
            path=str(downloaded_path),
            filename=filename,
            media_type='application/pdf',
        )
        
    except ValueError as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error downloading file: {e}")
        raise HTTPException(status_code=500, detail="Failed to download file from Telegram")

@app.post("/api/download")
async def manual_download(request: ManualDownload):
    """Trigger manual download for specific dates"""
    # This would need to communicate with the downloader thread
    # For now, just create workflow entries
    db.connect(reuse_if_open=True)
    
    pub = Publication.get_or_none(Publication.name == request.publication_name)
    if not pub:
        db.close()
        raise HTTPException(status_code=404, detail="Publication not found")
    
    for date_str in request.dates:
        FileWorkflow.get_or_create(
            publication_name=request.publication_name,
            date=date_str,
            defaults={'downloaded': False}
        )
    
    db.close()
    return {"status": "queued", "count": len(request.dates)}

def start_api_server():
    """Start the FastAPI server"""
    host = config.API_HOST
    port = config.API_PORT

    uvicorn.run(app, host=host, port=port, log_level="info")
