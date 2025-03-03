import os
import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Any
import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from models.base import SessionLocal, engine, Base
from models.supplier import Supplier
from models.epcis_submission import EPCISSubmission
from epcis.file_watcher import EPCISFileWatcher
from epcis.submission_service import SubmissionService
from epcis.validator import EPCISValidator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Vendor Scorecard API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize services
submission_service = SubmissionService()

# Configure file watcher
WATCH_DIR = os.path.join(os.path.dirname(__file__), "epcis_drop")
supplier_mapping = {
    "supplier_a": "supplier_1",
    "supplier_b": "supplier_2",
    "supplier_c": "supplier_3"
}

file_watcher = EPCISFileWatcher(
    submission_service=submission_service,
    watch_dir=WATCH_DIR,
    supplier_mapping=supplier_mapping
)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    """Start the file watcher on application startup"""
    file_watcher.start()
    logger.info("EPCIS file watcher started")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop the file watcher on application shutdown"""
    file_watcher.stop()
    logger.info("EPCIS file watcher stopped")

@app.post("/epcis/upload")
async def upload_epcis_file(
    file: UploadFile = File(...),
    supplier_id: str = Form(...)
) -> Dict[str, Any]:
    """Upload and process an EPCIS file"""
    try:
        content = await file.read()
        result = await submission_service.process_submission(
            file_content=content,
            file_name=file.filename,
            supplier_id=supplier_id
        )
        return result
    except Exception as e:
        logger.error(f"Error processing EPCIS file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )

@app.get("/epcis/watch-dir")
async def get_watch_dir_info() -> Dict[str, Any]:
    """Get information about the watch directory and supplier mappings"""
    try:
        supplier_directories = []
        for supplier_dir in os.listdir(WATCH_DIR):
            dir_path = os.path.join(WATCH_DIR, supplier_dir)
            if os.path.isdir(dir_path) and supplier_dir in supplier_mapping:
                archive_path = os.path.join(dir_path, "archived")
                has_archived = os.path.exists(archive_path) and len(os.listdir(archive_path)) > 0
                
                supplier_directories.append({
                    "name": supplier_dir,
                    "path": dir_path,
                    "has_archived": has_archived
                })
        
        return {
            "watch_dir": WATCH_DIR,
            "supplier_directories": supplier_directories
        }
    except Exception as e:
        logger.error(f"Error getting watch directory info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error accessing watch directory: {str(e)}"
        )

@app.get("/epcis/submissions")
async def get_submissions(
    supplier_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get EPCIS submissions with optional filtering"""
    try:
        query = db.query(EPCISSubmission)
        
        if supplier_id:
            query = query.filter(EPCISSubmission.supplier_id == supplier_id)
        if status:
            query = query.filter(EPCISSubmission.status == status)
            
        submissions = query.order_by(EPCISSubmission.submission_date.desc()).all()
        return {"submissions": submissions}
    except Exception as e:
        logger.error(f"Error getting submissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/epcis/refresh-suppliers")
async def refresh_supplier_mapping(background_tasks: BackgroundTasks):
    """Refresh the supplier directory mapping"""
    try:
        # Implement supplier refresh logic here
        return {"message": "Supplier mapping refresh scheduled"}
    except Exception as e:
        logger.error(f"Error refreshing supplier mapping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)