#!/usr/bin/env python3
import os
import sys
import sqlite3
import logging
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import importlib.util

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_init")

def find_config_file():
    """Find database configuration in the project"""
    possible_configs = []
    
    # Common config file paths
    for root, dirs, files in os.walk(os.path.join(os.path.dirname(__file__), '..')):
        for file in files:
            if file.endswith('.py') and ('config' in file.lower() or 'settings' in file.lower()):
                possible_configs.append(os.path.join(root, file))
    
    for config_path in possible_configs:
        logger.info(f"Checking config file: {config_path}")
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location("config_module", config_path)
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)
            
            # Look for database URL or path
            for attr_name in dir(config_module):
                if attr_name.upper().endswith('_URI') or attr_name.upper().endswith('_URL') or 'DATABASE' in attr_name.upper():
                    db_uri = getattr(config_module, attr_name, None)
                    if isinstance(db_uri, str) and ('sqlite' in db_uri.lower()):
                        logger.info(f"Found database URI in {config_path}: {db_uri}")
                        if db_uri.startswith('sqlite:///'):
                            # Convert URI to file path
                            db_path = db_uri[10:]
                            return os.path.abspath(db_path)
        except Exception as e:
            logger.debug(f"Error parsing config file {config_path}: {str(e)}")
    
    return None

def find_main_file():
    """Find the main.py file and extract database info"""
    # Look for main.py file
    main_files = []
    for root, dirs, files in os.walk(os.path.join(os.path.dirname(__file__), '..')):
        if 'main.py' in files:
            main_files.append(os.path.join(root, 'main.py'))
    
    for main_path in main_files:
        logger.info(f"Found main file: {main_path}")
        try:
            with open(main_path, 'r') as f:
                content = f.read()
                if 'create_engine' in content and 'sqlite' in content.lower():
                    logger.info("Database configuration found in main.py")
                    # This is just info, we're not executing the file
        except Exception as e:
            logger.debug(f"Error reading main file {main_path}: {str(e)}")
    
    return None

def initialize_database():
    """Create and initialize the database"""
    
    # First, look for the database in config
    db_path = find_config_file()
    
    if not db_path:
        # Check if there's information in main.py
        find_main_file()
        
        # Use default location as fallback
        db_path = os.path.join(os.path.dirname(__file__), '..', 'database.sqlite')
        logger.info(f"No database config found, using default path: {db_path}")
    
    # Check if the path exists
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        logger.info(f"Created directory: {db_dir}")
    
    # Initialize database and create tables
    try:
        logger.info(f"Initializing database at: {db_path}")
        conn = sqlite3.connect(db_path)
        
        # Create epcis_submissions table if it doesn't exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='epcis_submissions'")
        if not cursor.fetchone():
            logger.info("Creating epcis_submissions table...")
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
            
            # Check if suppliers table exists, if not create it
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='suppliers'")
            if not cursor.fetchone():
                logger.info("Creating suppliers table...")
                cursor.execute('''
                CREATE TABLE suppliers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    code TEXT UNIQUE,
                    contact_email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
            # Create validation_errors table if needed
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='validation_errors'")
            if not cursor.fetchone():
                logger.info("Creating validation_errors table...")
                cursor.execute('''
                CREATE TABLE validation_errors (
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
                ''')
            
            conn.commit()
            logger.info("Database initialized successfully")
        else:
            logger.info("Database already initialized")
        
        # List existing tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        logger.info(f"Existing tables: {[t[0] for t in tables]}")
        
        conn.close()
        return db_path
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return None

if __name__ == "__main__":
    db_path = initialize_database()
    if db_path:
        print(f"Database initialized at: {db_path}")
        print("Now run the migration script to add any missing columns:")
        print("python migrations/add_instance_identifier_column.py")
        sys.exit(0)
    else:
        print("Failed to initialize database!")
        sys.exit(1)