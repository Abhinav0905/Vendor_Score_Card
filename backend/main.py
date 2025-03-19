import os
import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Any
import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.base import SessionLocal, engine, Base
from models.supplier import Supplier
from models.epcis_submission import EPCISSubmission, ValidationError, FileStatus
from epcis.file_watcher import EPCISFileWatcher
from epcis.submission_service import SubmissionService
from epcis import EPCISValidator  # Updated import path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Vendor Scorecard API")

# Configure CORS to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default development server port
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
# Ensure watch directory exists
os.makedirs(WATCH_DIR, exist_ok=True)

supplier_mapping = {
    "supplier_a": "supplier_1",
    "supplier_b": "supplier_2",
    "supplier_c": "supplier_3"
}

# Ensure supplier directories exist
for supplier_dir in supplier_mapping.keys():
    supplier_path = os.path.join(WATCH_DIR, supplier_dir)
    archive_path = os.path.join(supplier_path, "archived")
    os.makedirs(supplier_path, exist_ok=True)
    os.makedirs(archive_path, exist_ok=True)

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

@app.get("/health")
async def health_check():
    """Health check endpoint to verify API is running"""
    return {"status": "OK"}

@app.post("/epcis/upload")
async def upload_epcis_file(
    file: UploadFile = File(...),
    supplier_id: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """Upload and process an EPCIS file"""
    try:
        # Validate file type
        allowed_extensions = ['.xml', '.json']
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Read file content
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=413,
                detail="File size exceeds the 10MB limit"
            )
        
        # Process submission
        result = await submission_service.process_submission(
            file_content=file_content,
            file_name=file.filename,
            supplier_id=supplier_id
        )
        
        # Return appropriate status code based on validation result
        status_code = result.get('status_code', 200)
        return result

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        logger.exception(f"Error processing EPCIS file: {str(e)}")
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
                
                # Count files in supplier directory (excluding archived folder)
                file_count = sum(1 for item in os.listdir(dir_path) 
                                if os.path.isfile(os.path.join(dir_path, item)))
                
                supplier_directories.append({
                    "name": supplier_dir,
                    "path": dir_path,
                    "has_archived": has_archived,
                    "file_count": file_count,
                    "mapped_id": supplier_mapping.get(supplier_dir)
                })
        
        return {
            "watch_dir": WATCH_DIR,
            "supplier_directories": supplier_directories,
            "supplier_mapping": supplier_mapping
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
        
        # Convert to list of dicts for JSON response
        result = []
        for sub in submissions:
            result.append({
                "id": sub.id,
                "supplier_id": sub.supplier_id,
                "file_name": sub.file_name,
                "file_path": sub.file_path,
                "file_size": sub.file_size,
                "status": sub.status,
                "is_valid": sub.is_valid,
                "error_count": sub.error_count,
                "warning_count": sub.warning_count,
                "submission_date": sub.submission_date.isoformat() if sub.submission_date else None,
                "processing_date": sub.processing_date.isoformat() if sub.processing_date else None,
                "completion_date": sub.completion_date.isoformat() if sub.completion_date else None
            })
        
        return {"submissions": result}
    except Exception as e:
        logger.error(f"Error getting submissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/suppliers")
async def get_suppliers() -> Dict[str, Any]:
    """Get a list of all suppliers"""
    try:
        return {
            "suppliers": [
                {"id": supplier_id, "name": f"Supplier {supplier_id}"} 
                for supplier_id in supplier_mapping.values()
            ]
        }
    except Exception as e:
        logger.error(f"Error getting suppliers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/epcis/refresh-suppliers")
async def refresh_supplier_mapping(background_tasks: BackgroundTasks):
    """Refresh the supplier directory mapping"""
    try:
        # Check for new directories in the watch directory
        current_suppliers = set(supplier_mapping.keys())
        
        for item in os.listdir(WATCH_DIR):
            item_path = os.path.join(WATCH_DIR, item)
            
            if os.path.isdir(item_path) and item not in current_suppliers:
                # Create archived directory if it doesn't exist
                archived_path = os.path.join(item_path, "archived")
                os.makedirs(archived_path, exist_ok=True)
                
                # Add to supplier mapping with a new ID
                new_id = f"supplier_{len(supplier_mapping) + 1}"
                supplier_mapping[item] = new_id
                logger.info(f"Added new supplier: {item} with ID: {new_id}")
        
        return {
            "message": "Supplier mapping refreshed",
            "suppliers": supplier_mapping
        }
    except Exception as e:
        logger.error(f"Error refreshing supplier mapping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get dashboard statistics including submission counts and supplier performance"""
    try:
        # Query total submissions
        total_submissions = db.query(EPCISSubmission).count()
        
        # Query successful submissions (validated status)
        successful_submissions = db.query(EPCISSubmission).filter(
            EPCISSubmission.status == 'validated'
        ).count()
        
        # Query failed submissions
        failed_submissions = db.query(EPCISSubmission).filter(
            EPCISSubmission.status == 'failed'
        ).count()
        
        # Get submission counts by status
        status_counts = {}
        for status in ['validated', 'held', 'failed', 'reprocessed']:
            count = db.query(EPCISSubmission).filter(
                EPCISSubmission.status == status
            ).count()
            status_counts[status] = count
        
        # Get top suppliers by submission count
        top_suppliers = []
        supplier_counts = (
            db.query(
                EPCISSubmission.supplier_id,
                func.count(EPCISSubmission.id).label('submission_count')
            )
            .group_by(EPCISSubmission.supplier_id)
            .order_by(func.count(EPCISSubmission.id).desc())
            .limit(5)
            .all()
        )
        
        for supplier in supplier_counts:
            top_suppliers.append({
                'id': supplier.supplier_id,
                'name': f'Supplier {supplier.supplier_id.split("_")[-1].upper()}',
                'submission_count': supplier.submission_count
            })
        
        # Get error type distribution by joining with validation errors table
        error_types = {
            'structure': db.query(EPCISSubmission).filter(
                EPCISSubmission.has_structure_errors == True
            ).count(),
            'field': db.query(ValidationError).filter(
                ValidationError.error_type == 'field'
            ).count(),
            'sequence': db.query(EPCISSubmission).filter(
                EPCISSubmission.has_sequence_errors == True
            ).count(),
            'aggregation': db.query(ValidationError).filter(
                ValidationError.error_type == 'aggregation'
            ).count()
        }
        
        return {
            'total_submissions': total_submissions,
            'successful_submissions': successful_submissions,
            'failed_submissions': failed_submissions,
            'submission_by_status': status_counts,
            'top_suppliers': top_suppliers,
            'error_type_distribution': error_types
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)