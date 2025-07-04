#!/usr/bin/env python3

import os
import sqlite3
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_instance_identifier_column():
    """Add instance_identifier column directly to the SQLite database"""
    
    # Find the database file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'database.sqlite')
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found at {db_path}")
        return False
    
    logger.info(f"Using database at: {db_path}")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='epcis_submissions'")
        if not cursor.fetchone():
            logger.error("Table epcis_submissions does not exist!")
            return False
        
        # Get column info to check if the column already exists
        cursor.execute("PRAGMA table_info(epcis_submissions)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'instance_identifier' not in columns:
            logger.info("Adding instance_identifier column to epcis_submissions table")
            cursor.execute("ALTER TABLE epcis_submissions ADD COLUMN instance_identifier TEXT")
            conn.commit()
            logger.info("Column added successfully")
        else:
            logger.info("Column instance_identifier already exists")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(epcis_submissions)")
        columns = [col[1] for col in cursor.fetchall()]
        logger.info(f"Current columns in epcis_submissions: {columns}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error updating database: {str(e)}")
        return False

if __name__ == "__main__":
    success = add_instance_identifier_column()
    if success:
        print("Database updated successfully! Restart your application.")
    else:
        print("Failed to update database. Check the logs for details.")