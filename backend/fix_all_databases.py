#!/usr/bin/env python3

import os
import sys
import glob
import sqlite3
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_sqlite_databases():
    """Search for all SQLite databases in the project"""
    databases = []
    project_dir = '/Users/kumarabhinav/Documents/Scorecard/Vendor_Score_Card'
    
    # Search patterns for SQLite databases
    patterns = ['*.db', '*.sqlite', '*.sqlite3']
    
    # Search in the project directory and subdirectories
    for pattern in patterns:
        databases.extend(glob.glob(os.path.join(project_dir, pattern)))
        databases.extend(glob.glob(os.path.join(project_dir, '*', pattern)))
        databases.extend(glob.glob(os.path.join(project_dir, '*', '*', pattern)))
    
    # Include explicit locations
    explicit_locations = [
        os.path.join(project_dir, 'backend', 'database.sqlite'),
        os.path.join(project_dir, 'instance', 'database.sqlite'),
        os.path.join(project_dir, 'database.sqlite')
    ]
    
    for location in explicit_locations:
        if os.path.exists(location) and location not in databases:
            databases.append(location)
    
    return databases

def examine_database(db_path):
    """Examine the database to see if it has epcis_submissions table"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for epcis_submissions table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='epcis_submissions'")
        if cursor.fetchone():
            logger.info(f"Database {db_path} has epcis_submissions table.")
            
            # Check table structure
            cursor.execute("PRAGMA table_info(epcis_submissions)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            logger.info(f"Columns in epcis_submissions: {column_names}")
            
            # Check if the instance_identifier column exists
            if 'instance_identifier' in column_names:
                logger.info(f"Database {db_path} already has instance_identifier column.")
                return False
            else:
                logger.info(f"Database {db_path} NEEDS instance_identifier column.")
                return True
        else:
            logger.info(f"Database {db_path} does NOT have epcis_submissions table.")
            return False
            
    except Exception as e:
        logger.error(f"Error examining database {db_path}: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def fix_all_databases():
    """Find and fix all databases that need the instance_identifier column"""
    databases = find_sqlite_databases()
    
    if not databases:
        logger.error("No SQLite databases found in the project!")
        return False
    
    fixed = False
    
    for db_path in databases:
        logger.info(f"Examining database: {db_path}")
        
        needs_fix = examine_database(db_path)
        
        if needs_fix:
            try:
                logger.info(f"Adding instance_identifier column to {db_path}")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("ALTER TABLE epcis_submissions ADD COLUMN instance_identifier TEXT")
                conn.commit()
                conn.close()
                logger.info(f"Successfully added column to {db_path}")
                fixed = True
            except Exception as e:
                logger.error(f"Error fixing database {db_path}: {str(e)}")
    
    return fixed

if __name__ == "__main__":
    print("Searching for databases that need fixing...")
    if fix_all_databases():
        print("Done! At least one database was fixed. Please restart your application.")
    else:
        print("No databases needed fixing or no databases were found.")