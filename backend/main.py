import os
import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Any
import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile, Form, Depends, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.base import SessionLocal, engine, Base
from models.supplier import Supplier
from models.epcis_submission import EPCISSubmission, ValidationError, FileStatus, ValidEPCISSubmission, ErroredEPCISSubmission
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

# Dynamic supplier mapping from database
def get_supplier_mapping(db=None):
    """Get supplier mapping from database"""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        suppliers = db.query(Supplier).all()
        mapping = {}
        
        # For existing directories, try to match with suppliers in DB
        for item in os.listdir(WATCH_DIR):
            item_path = os.path.join(WATCH_DIR, item)
            if os.path.isdir(item_path):
                # Check if we have a supplier with this name
                supplier = db.query(Supplier).filter_by(name=item).first()
                if supplier:
                    mapping[item] = supplier.id
                else:
                    # Create a new supplier entry
                    new_supplier = Supplier(
                        id=f"supplier_{item.lower()}",
                        name=item,
                        is_active=True,
                        data_accuracy=100.0,
                        error_rate=0.0,
                        compliance_score=100.0,
                        response_time=0
                    )
                    db.add(new_supplier)
                    db.commit()
                    mapping[item] = new_supplier.id
        
        return mapping
    finally:
        if close_db:
            db.close()

# Get initial supplier mapping
db = SessionLocal()
try:
    supplier_mapping = get_supplier_mapping(db)
except Exception as e:
    logger.error(f"Error getting supplier mapping: {e}")
    supplier_mapping = {}
finally:
    db.close()

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
    response: Response,
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
        
        # Set the appropriate status code from the result
        if 'status_code' in result:
            if result['status_code'] == 409:  # Duplicate submission
                response.status_code = status.HTTP_409_CONFLICT
            else:
                response.status_code = result['status_code']
        
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
        
        # Query failed submissions - Include both 'failed' and 'held' statuses,
        # as well as any submission with errored_submission_id not null
        failed_submissions = db.query(EPCISSubmission).filter(
            (EPCISSubmission.status.in_(['failed', 'held'])) | 
            (EPCISSubmission.errored_submission_id.isnot(None))
        ).count()
        
        # Get submission counts by status
        status_counts = {}
        for status in ['validated', 'held', 'failed', 'reprocessed']:
            count = db.query(EPCISSubmission).filter(
                EPCISSubmission.status == status
            ).count()
            status_counts[status] = count
        
        # Get top suppliers by submission count with detailed success/failure metrics
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
            # Get supplier name
            supplier_name = supplier.supplier_id
            try:
                supplier_record = db.query(Supplier).filter_by(id=supplier.supplier_id).first()
                if supplier_record and supplier_record.name:
                    supplier_name = supplier_record.name
                else:
                    # Fallback to formatted ID if no name is found
                    supplier_name = f'Supplier {supplier.supplier_id.split("_")[-1].upper()}'
            except:
                pass
            
            # Get success count for this supplier (validated status)
            success_count = db.query(EPCISSubmission).filter(
                EPCISSubmission.supplier_id == supplier.supplier_id,
                EPCISSubmission.status == 'validated'
            ).count()
            
            # Get failure count for this supplier
            failure_count = db.query(EPCISSubmission).filter(
                EPCISSubmission.supplier_id == supplier.supplier_id,
                ((EPCISSubmission.status.in_(['failed', 'held'])) | 
                 (EPCISSubmission.errored_submission_id.isnot(None)))
            ).count()
            
            # Calculate error rate
            error_rate = 0
            if supplier.submission_count > 0:
                error_rate = round((failure_count / supplier.submission_count) * 100)
                
            top_suppliers.append({
                'id': supplier.supplier_id,
                'name': supplier_name,
                'submission_count': supplier.submission_count,
                'success_count': success_count,
                'failure_count': failure_count,
                'error_rate': error_rate
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

@app.get("/epcis/valid-submissions")
async def get_valid_submissions(
    supplier_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get valid EPCIS submissions with optional filtering"""
    try:
        query = db.query(ValidEPCISSubmission)
        
        if supplier_id:
            query = query.filter(ValidEPCISSubmission.supplier_id == supplier_id)
            
        total = query.count()
        submissions = query.order_by(ValidEPCISSubmission.insertion_date.desc()).offset(offset).limit(limit).all()
        
        # Convert to list of dicts for JSON response
        result = []
        for sub in submissions:
            result.append({
                "id": sub.id,
                "master_submission_id": sub.master_submission_id,
                "supplier_id": sub.supplier_id,
                "file_name": sub.file_name,
                "file_size": sub.file_size,
                "warning_count": sub.warning_count,
                "processed_event_count": sub.processed_event_count,
                "insertion_date": sub.insertion_date.isoformat(),
                "last_accessed_date": sub.last_accessed_date.isoformat() if sub.last_accessed_date else None
            })
        
        return {
            "total": total,
            "submissions": result,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error getting valid submissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/epcis/errored-submissions")
async def get_errored_submissions(
    supplier_id: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get errored EPCIS submissions with optional filtering"""
    try:
        query = db.query(ErroredEPCISSubmission)
        
        if supplier_id:
            query = query.filter(ErroredEPCISSubmission.supplier_id == supplier_id)
        
        if is_resolved is not None:
            query = query.filter(ErroredEPCISSubmission.is_resolved == is_resolved)
            
        total = query.count()
        submissions = query.order_by(ErroredEPCISSubmission.insertion_date.desc()).offset(offset).limit(limit).all()
        
        # Convert to list of dicts for JSON response
        result = []
        for sub in submissions:
            result.append({
                "id": sub.id,
                "master_submission_id": sub.master_submission_id,
                "supplier_id": sub.supplier_id,
                "file_name": sub.file_name,
                "file_size": sub.file_size,
                "error_count": sub.error_count,
                "warning_count": sub.warning_count,
                "has_structure_errors": sub.has_structure_errors,
                "has_sequence_errors": sub.has_sequence_errors,
                "insertion_date": sub.insertion_date.isoformat(),
                "last_error_date": sub.last_error_date.isoformat() if sub.last_error_date else None,
                "is_resolved": sub.is_resolved,
                "resolution_date": sub.resolution_date.isoformat() if sub.resolution_date else None,
                "resolved_by": sub.resolved_by
            })
        
        return {
            "total": total,
            "submissions": result,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error getting errored submissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/epcis/valid-submissions/{submission_id}")
async def get_valid_submission_details(
    submission_id: str,
) -> Dict[str, Any]:
    """Get details of a valid submission"""
    result = submission_service.get_valid_submission(submission_id)
    if not result.get('success'):
        raise HTTPException(status_code=404, detail=result.get('message', 'Submission not found'))
    return result

@app.get("/epcis/errored-submissions/{submission_id}")
async def get_errored_submission_details(
    submission_id: str,
) -> Dict[str, Any]:
    """Get details of an errored submission"""
    result = submission_service.get_errored_submission(submission_id)
    if not result.get('success'):
        raise HTTPException(status_code=404, detail=result.get('message', 'Submission not found'))
    return result

@app.get("/epcis/submissions/{submission_id}/validation")
async def get_submission_validation(
    submission_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get validation results for a submission"""
    try:
        submission = db.query(EPCISSubmission).filter_by(id=submission_id).first()
        if not submission:
            raise HTTPException(
                status_code=404,
                detail=f"Submission {submission_id} not found"
            )

        # Get validation errors
        validation_errors = db.query(ValidationError).filter_by(submission_id=submission_id).all()
        
        return {
            "status": submission.status,
            "error_count": submission.error_count,
            "warning_count": submission.warning_count,
            "errors": [
                {
                    "id": error.id,
                    "type": error.error_type,
                    "severity": error.severity,
                    "message": error.message,
                    "line_number": error.line_number,
                    "is_resolved": error.is_resolved,
                    "resolution_note": error.resolution_note,
                    "resolved_at": error.resolved_at.isoformat() if error.resolved_at else None,
                    "resolved_by": error.resolved_by
                }
                for error in validation_errors
            ]
        }
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        logger.exception(f"Error getting validation results: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving validation results: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)