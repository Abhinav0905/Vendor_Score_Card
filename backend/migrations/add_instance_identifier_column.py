import os
import sys
import sqlite3
import logging
import glob

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_database_file():
    """Find the SQLite database file in the project"""
    # Common locations to check for the database
    base_dir = os.path.join(os.path.dirname(__file__), '..')
    project_dir = os.path.join(os.path.dirname(__file__), '../..')
    
    possible_locations = [
        os.path.join(base_dir, 'database.sqlite'),
        os.path.join(base_dir, 'app.db'),
        os.path.join(base_dir, 'instance', 'database.sqlite'),
        os.path.join(project_dir, 'database.sqlite'),
        os.path.join(project_dir, 'app.db')
    ]
    
    # Search for any .db or .sqlite files
    for root_dir in [base_dir, project_dir]:
        for ext in ['*.db', '*.sqlite', '*.sqlite3']:
            possible_locations.extend(glob.glob(os.path.join(root_dir, ext)))
            possible_locations.extend(glob.glob(os.path.join(root_dir, '*', ext)))
    
    # Check each location
    for loc in possible_locations:
        if os.path.exists(loc) and os.path.getsize(loc) > 0:
            logger.info(f"Found database at: {loc}")
            return loc
    
    return None

def create_tables_if_needed(conn):
    """Create the epcis_submissions table if it doesn't exist"""
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='epcis_submissions'")
    if not cursor.fetchone():
        logger.info("epcis_submissions table doesn't exist, creating it...")
        
        # Create the table with basic structure including the instance_identifier
        cursor.execute('''
        CREATE TABLE epcis_submissions (
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
            errored_submission_id TEXT
        )
        ''')
        conn.commit()
        logger.info("Created epcis_submissions table with instance_identifier column")
        return True
    return False

def run_migration():
    """Add instance_identifier column to epcis_submissions table"""
    try:
        # Get database path
        db_path = find_database_file()
        
        if not db_path:
            logger.error("No SQLite database found! Please specify the database path manually.")
            logger.info("Searching for the application database config...")
            
            # Try to find configuration that might contain DB path
            for root, dirs, files in os.walk(os.path.join(os.path.dirname(__file__), '../')):
                for file in files:
                    if file.endswith('.py') and ('config' in file.lower() or 'settings' in file.lower()):
                        logger.info(f"Possible config file: {os.path.join(root, file)}")
            
            return False
        
        logger.info(f"Connecting to database at: {db_path}")
        conn = sqlite3.connect(db_path)
        
        # Create tables if they don't exist
        created = create_tables_if_needed(conn)
        if created:
            logger.info("Migration completed - table was created with the required column")
            conn.close()
            return True
        
        # Continue with normal migration
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(epcis_submissions)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'instance_identifier' not in column_names:
            logger.info("Adding instance_identifier column to epcis_submissions table")
            cursor.execute("ALTER TABLE epcis_submissions ADD COLUMN instance_identifier TEXT")
            conn.commit()
            logger.info("Migration completed successfully")
        else:
            logger.info("Column instance_identifier already exists, skipping migration")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        logger.info("Database diagnosis information:")
        
        try:
            # List all SQLite files in the project
            for root, dirs, files in os.walk(os.path.join(os.path.dirname(__file__), '../../')):
                for file in files:
                    if file.endswith(('.db', '.sqlite', '.sqlite3')):
                        db_file = os.path.join(root, file)
                        logger.info(f"Found possible database: {db_file}")
                        
                        # Try to connect and list tables
                        try:
                            test_conn = sqlite3.connect(db_file)
                            test_cursor = test_conn.cursor()
                            test_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                            tables = test_cursor.fetchall()
                            logger.info(f"Tables in {db_file}: {[t[0] for t in tables]}")
                            test_conn.close()
                        except Exception as db_err:
                            logger.info(f"Error examining {db_file}: {str(db_err)}")
        except Exception as diag_err:
            logger.error(f"Error during diagnosis: {str(diag_err)}")
                
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)