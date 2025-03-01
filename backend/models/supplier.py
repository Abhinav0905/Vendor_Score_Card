from sqlalchemy import Column, Integer, String, Float, DateTime
from .base import Base
import datetime

class Supplier(Base):
    __tablename__ = "suppliers"
    
    id = Column(String, primary_key=True)
    name = Column(String)
    data_accuracy = Column(Float)
    error_rate = Column(Float)
    compliance_score = Column(Float)
    response_time = Column(Integer)
    last_submission = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)