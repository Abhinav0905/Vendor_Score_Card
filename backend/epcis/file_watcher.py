import os
import time
import logging
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Dict, Any, Optional

from .submission_service import SubmissionService
from .file_handler import EPCISFileHandler

logger = logging.getLogger(__name__)

class EPCISFileEventHandler(FileSystemEventHandler):
    """Watchdog event handler for EPCIS files dropped in watch directories"""
    
    def __init__(self, submission_service: SubmissionService, supplier_mapping: Dict[str, str]):
        self.submission_service = submission_service
        self.supplier_mapping = supplier_mapping
        self.file_handler = EPCISFileHandler()
        self.processing_files = set()
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
            
        file_path = event.src_path
        
        # Check if this is an XML or JSON file
        if not (file_path.lower().endswith('.xml') or file_path.lower().endswith('.json')):
            return
            
        # Check if the file is in a supplier directory
        file_dir = os.path.dirname(file_path)
        supplier_dir = os.path.basename(file_dir)
        
        # Skip archived files
        if 'archived' in file_dir.lower():
            return
        
        # Check if this supplier is in our mapping
        if supplier_dir in self.supplier_mapping:
            supplier_id = self.supplier_mapping[supplier_dir]
            
            # Don't process files that are already being processed
            if file_path in self.processing_files:
                return
                
            self.processing_files.add(file_path)
            logger.info(f"New EPCIS file detected: {file_path} for supplier: {supplier_dir}")
            
            try:
                # Wait a moment to ensure the file is fully written
                time.sleep(1)
                
                # Process the file
                asyncio.run(self._process_file(file_path, supplier_id))
                
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
            finally:
                # Remove from processing set
                self.processing_files.discard(file_path)
    
    async def _process_file(self, file_path: str, supplier_id: str):
        """Process an EPCIS file"""
        try:
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            file_name = os.path.basename(file_path)
            
            # Submit file for processing
            result = await self.submission_service.process_submission(
                file_content=file_content,
                file_name=file_name,
                supplier_id=supplier_id
            )
            
            if result.get('success'):
                logger.info(f"File {file_path} processed successfully")
                
                # Move file to archived directory
                archived_path = self.file_handler.move_to_archive(file_path)
                if archived_path:
                    logger.info(f"File archived to {archived_path}")
            else:
                logger.warning(f"File {file_path} processing failed: {result.get('message')}")
                
        except Exception as e:
            logger.exception(f"Error processing file {file_path}: {e}")

class EPCISFileWatcher:
    """File watcher service for EPCIS files"""
    
    def __init__(
        self,
        submission_service: SubmissionService,
        watch_dir: str,
        supplier_mapping: Dict[str, str],
        poll_interval: float = 1.0
    ):
        self.submission_service = submission_service
        self.watch_dir = watch_dir
        self.supplier_mapping = supplier_mapping
        self.poll_interval = poll_interval
        
        # Create watch directory if it doesn't exist
        os.makedirs(watch_dir, exist_ok=True)
        
        # Initialize watchdog observer and event handler
        self.observer = None
        self.event_handler = EPCISFileEventHandler(submission_service, supplier_mapping)
    
    def start(self):
        """Start watching for file events"""
        try:
            logger.info(f"Starting EPCIS file watcher on directory: {self.watch_dir}")
            
            self.observer = Observer()
            self.observer.schedule(self.event_handler, self.watch_dir, recursive=True)
            self.observer.start()
            
            logger.info("File watcher started successfully")
            
        except Exception as e:
            logger.exception(f"Error starting file watcher: {e}")
    
    def stop(self):
        """Stop watching for file events"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("File watcher stopped")