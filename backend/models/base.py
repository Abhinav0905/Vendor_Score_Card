from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment or use SQLite as fallback
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vendor_scorecard.db")

# Use SQLite for testing if PostgreSQL is not available
if DATABASE_URL.startswith("postgresql://"):
    try:
        engine = create_engine(DATABASE_URL)
        engine.connect()
    except Exception as e:
        print(f"PostgreSQL connection failed: {e}")
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