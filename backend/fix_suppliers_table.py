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
    
    return databases

def fix_suppliers_table(db_path):
    """Add the code column to the suppliers table if needed"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for suppliers table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='suppliers'")
        if cursor.fetchone():
            logger.info(f"Database {db_path} has suppliers table.")
            
            # Check table structure
            cursor.execute("PRAGMA table_info(suppliers)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            logger.info(f"Columns in suppliers: {column_names}")
            
            # Add code column if it doesn't exist
            if 'code' not in column_names:
                logger.info(f"Adding code column to suppliers table in {db_path}")
                
                # Create new table with all columns including code
                cursor.execute("""
                CREATE TABLE suppliers_new (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    data_accuracy FLOAT DEFAULT 100.0,
                    error_rate FLOAT DEFAULT 0.0,
                    compliance_score FLOAT DEFAULT 100.0,
                    response_time INTEGER DEFAULT 0,
                    contact_name TEXT,
                    contact_email TEXT,
                    contact_phone TEXT,
                    address TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    last_submission_date TIMESTAMP,
                    status TEXT,
                    code TEXT UNIQUE
                )
                """)
                
                # Copy data from old table to new table
                existing_columns = ', '.join(column_names)
                cursor.execute(f"""
                INSERT INTO suppliers_new ({existing_columns}, code)
                SELECT {existing_columns}, NULL
                FROM suppliers
                """)
                
                # Drop old table and rename new one
                cursor.execute("DROP TABLE suppliers")
                cursor.execute("ALTER TABLE suppliers_new RENAME TO suppliers")
                
                conn.commit()
                logger.info(f"Successfully added code column to {db_path}")
                return True
            else:
                logger.info(f"suppliers.code column already exists in {db_path}")
        else:
            logger.info(f"Database {db_path} does not have suppliers table.")
        
        return False
    except Exception as e:
        logger.error(f"Error fixing suppliers table in {db_path}: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def fix_all_databases():
    """Find and fix all databases that need the suppliers.code column"""
    databases = find_sqlite_databases()
    
    if not databases:
        logger.error("No SQLite databases found in the project!")
        return False
    
    fixed_any = False
    
    for db_path in databases:
        logger.info(f"Checking database: {db_path}")
        fixed = fix_suppliers_table(db_path)
        if fixed:
            fixed_any = True
    
    return fixed_any

if __name__ == "__main__":
    print("Searching for databases that need the suppliers.code column...")
    if fix_all_databases():
        print("Success! At least one database was fixed. Restart your application.")
    else:
        print("No databases needed fixing or no databases were found.")