#!/usr/bin/env python
"""
One-time migration script to add missing columns to the tables.
This fixes the 'no such column: epcis_submissions.valid_submission_id', 'no such column: suppliers.status' 
and 'no such column: validation_errors.line_number' errors.
"""
import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the database in backend directory
BACKEND_DB_PATH = os.path.join(os.path.dirname(__file__), "vendor_scorecard.db")
# Path to the database in root directory
ROOT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vendor_scorecard.db")

def add_missing_columns(db_path):
    """Add missing columns to the epcis_submissions, suppliers, and validation_errors tables"""
    try:
        logger.info(f"Updating database at: {db_path}")
        
        # Connect to the SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the columns already exist in epcis_submissions table
        cursor.execute("PRAGMA table_info(epcis_submissions)")
        columns = {column[1] for column in cursor.fetchall()}
        
        # Add the valid_submission_id column if it doesn't exist
        if "valid_submission_id" not in columns:
            logger.info(f"Adding valid_submission_id column to epcis_submissions table in {db_path}")
            cursor.execute("ALTER TABLE epcis_submissions ADD COLUMN valid_submission_id TEXT")
        else:
            logger.info(f"Column valid_submission_id already exists in {db_path}")
        
        # Add the errored_submission_id column if it doesn't exist
        if "errored_submission_id" not in columns:
            logger.info(f"Adding errored_submission_id column to epcis_submissions table in {db_path}")
            cursor.execute("ALTER TABLE epcis_submissions ADD COLUMN errored_submission_id TEXT")
        else:
            logger.info(f"Column errored_submission_id already exists in {db_path}")
        
        # Check if the columns already exist in suppliers table
        cursor.execute("PRAGMA table_info(suppliers)")
        supplier_columns = {column[1] for column in cursor.fetchall()}
        
        # Add the status column to suppliers table if it doesn't exist
        if "status" not in supplier_columns:
            logger.info(f"Adding status column to suppliers table in {db_path}")
            cursor.execute("ALTER TABLE suppliers ADD COLUMN status TEXT DEFAULT 'active'")
        else:
            logger.info(f"Column status already exists in suppliers table in {db_path}")
            
        # Check if the columns already exist in validation_errors table
        cursor.execute("PRAGMA table_info(validation_errors)")
        validation_columns = {column[1] for column in cursor.fetchall()}
        
        # Add the line_number column to validation_errors table if it doesn't exist
        if "line_number" not in validation_columns:
            logger.info(f"Adding line_number column to validation_errors table in {db_path}")
            cursor.execute("ALTER TABLE validation_errors ADD COLUMN line_number INTEGER")
        else:
            logger.info(f"Column line_number already exists in validation_errors table in {db_path}")
        
        # Commit changes and close connection
        conn.commit()
        logger.info(f"Schema update completed successfully for {db_path}")
        
        return True
    except Exception as e:
        logger.error(f"Error updating schema for {db_path}: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Update both database files
    backend_success = False
    root_success = False
    
    logger.info("Starting schema updates for both database files")
    
    # Update backend database
    if os.path.exists(BACKEND_DB_PATH):
        backend_success = add_missing_columns(BACKEND_DB_PATH)
        if backend_success:
            logger.info(f"✅ Schema update completed successfully for backend database: {BACKEND_DB_PATH}")
        else:
            logger.error(f"❌ Schema update failed for backend database: {BACKEND_DB_PATH}")
    else:
        logger.warning(f"⚠️ Backend database file not found at: {BACKEND_DB_PATH}")
    
    # Update root database
    if os.path.exists(ROOT_DB_PATH):
        root_success = add_missing_columns(ROOT_DB_PATH)
        if root_success:
            logger.info(f"✅ Schema update completed successfully for root database: {ROOT_DB_PATH}")
        else:
            logger.error(f"❌ Schema update failed for root database: {ROOT_DB_PATH}")
    else:
        logger.warning(f"⚠️ Root database file not found at: {ROOT_DB_PATH}")
    
    # Final status report
    if backend_success or root_success:
        logger.info("✅ Schema update process completed. At least one database was updated successfully.")
    else:
        logger.error("❌ Schema update process failed. No databases were updated successfully.")
        logger.info("The database will be created with all columns when you start the application.")