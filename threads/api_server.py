import logging
from datetime import datetime
from pathlib import Path
import os

from modules.database import db, Publication, FileWorkflow
from modules.utils import get_key

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import uvicorn
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="PR Manager API")

# Mount static files
static_path = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

class PublicationUpdate(BaseModel):
    enabled: bool | None = None
    issue_id: str | None = None
    max_scale: int | None = None
    language: str | None = None

class PublicationCreate(BaseModel):
    name: str
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
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

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
            issue_id=pub.issue_id,
            max_scale=pub.max_scale,
            language=pub.language
        )
        result = {
            "id": publication.id,
            "name": publication.name,
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
async def get_workflow():
    """Get workflow status for all files"""
    db.connect(reuse_if_open=True)
    workflows = list(FileWorkflow.select().order_by(FileWorkflow.created_at.desc()).limit(100).dicts())
    db.close()
    return workflows

"""
@app.get("/api/workflow/{publication_name}/{date_str}")
async def get_downloaded_file(publication_name: str, date_str: str):
    # Use the telethon client to download the file
    db.connect(reuse_if_open=True)
    workflow = FileWorkflow.get_or_none(
        FileWorkflow.publication_name == publication_name,
        FileWorkflow.date == date_str,
        FileWorkflow.uploaded == True
    )
    db.close()

    if not workflow:
        raise HTTPException(status_code=404, detail="File not found or not uploaded yet")
    
    filename = get_key(publication_name, date_str)
    
    client = manager.get_client()
    async def get_file():
        async with client:
            file_path = await client.download_media(
                message=client.iter_messages(workflow.channel_id, ids=workflow.message_id).__anext__(),
                file=Path(os.tmpdir()) / filename
            )
            return file_path
    
    file_path = await get_file()
    return FileResponse(path=str(file_path), filename=filename, media_type='application/pdf')
"""

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
    from modules import config
    host = config.API_HOST
    port = config.API_PORT

    uvicorn.run(app, host=host, port=port, log_level="info")
