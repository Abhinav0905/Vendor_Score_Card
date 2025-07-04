#!/usr/bin/env python3

import os
import sqlite3
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_database():
    """Initialize the database with all required tables"""
    
    # Find the database file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'database.sqlite')
    
    logger.info(f"Using database at: {db_path}")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create suppliers table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            code TEXT UNIQUE,
            contact_email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create epcis_submissions table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS epcis_submissions (
            id TEXT PRIMARY KEY,
            supplier_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_hash TEXT NOT NULL,
            instance_identifier TEXT,
            status TEXT NOT NULL DEFAULT 'received',
            is_valid BOOLEAN,
            error_count INTEGER DEFAULT 0,
            warning_count INTEGER DEFAULT 0,
            has_structure_errors BOOLEAN DEFAULT 0,
            has_sequence_errors BOOLEAN DEFAULT 0,
            submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processing_date TIMESTAMP,
            completion_date TIMESTAMP,
            submitter_id TEXT,
            valid_submission_id TEXT,
            errored_submission_id TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
        )
        """)
        
        # Create validation_errors table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS validation_errors (
            id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            error_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            line_number INTEGER,
            is_resolved BOOLEAN DEFAULT 0,
            resolution_note TEXT,
            resolved_at TIMESTAMP,
            resolved_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (submission_id) REFERENCES epcis_submissions (id)
        )
        """)
        
        # Create valid_epcis_submissions table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS valid_epcis_submissions (
            id TEXT PRIMARY KEY,
            master_submission_id TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            warning_count INTEGER DEFAULT 0,
            processed_event_count INTEGER DEFAULT 0,
            insertion_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed_date TIMESTAMP,
            FOREIGN KEY (master_submission_id) REFERENCES epcis_submissions (id)
        )
        """)
        
        # Create errored_epcis_submissions table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS errored_epcis_submissions (
            id TEXT PRIMARY KEY,
            master_submission_id TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            error_count INTEGER DEFAULT 0,
            warning_count INTEGER DEFAULT 0,
            has_structure_errors BOOLEAN DEFAULT 0,
            has_sequence_errors BOOLEAN DEFAULT 0,
            insertion_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_error_date TIMESTAMP,
            is_resolved BOOLEAN DEFAULT 0,
            resolution_date TIMESTAMP,
            resolved_by TEXT,
            FOREIGN KEY (master_submission_id) REFERENCES epcis_submissions (id)
        )
        """)
        
        # Create performance_trends table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS performance_trends (
            id TEXT PRIMARY KEY,
            supplier_id TEXT NOT NULL,
            month TEXT NOT NULL,
            year INTEGER NOT NULL,
            month_number INTEGER NOT NULL,
            data_accuracy FLOAT DEFAULT 100.0,
            error_rate FLOAT DEFAULT 0.0,
            compliance_score FLOAT DEFAULT 100.0,
            response_time INTEGER DEFAULT 0,
            submission_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
        )
        """)
        
        conn.commit()
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        logger.info(f"Tables in database: {[t[0] for t in tables]}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False

if __name__ == "__main__":
    success = initialize_database()
    if success:
        print("Database initialized successfully! Restart your application.")
    else:
        print("Failed to initialize database. Check the logs for details.")