from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment or use MySQL as fallback
# MySQL connection string format: mysql+pymysql://username:password@localhost/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost/vendor_scorecard")

# Try to connect to MySQL, fall back to SQLite if MySQL is not available
if DATABASE_URL.startswith("mysql+pymysql://"):
    try:
        engine = create_engine(DATABASE_URL)
        engine.connect()
        print("Successfully connected to MySQL database")
    except Exception as e:
        print(f"MySQL connection failed: {e}")
        print("Falling back to SQLite database")
        DATABASE_URL = "sqlite:///./vendor_scorecard.db"
        engine = create_engine(DATABASE_URL)
# Check for PostgreSQL as another option
elif DATABASE_URL.startswith("postgresql://"):
    try:
        engine = create_engine(DATABASE_URL)
        engine.connect()
        print("Successfully connected to PostgreSQL database")
    except Exception as e:
        print(f"PostgreSQL connection failed: {e}")
        print("Falling back to MySQL database")
        DATABASE_URL = "mysql+pymysql://root:password@localhost/vendor_scorecard"
        try:
            engine = create_engine(DATABASE_URL)
            engine.connect()
        except Exception as e:
            print(f"MySQL connection failed: {e}")
            print("Falling back to SQLite database")
            DATABASE_URL = "sqlite:///./vendor_scorecard.db"
            engine = create_engine(DATABASE_URL)
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)