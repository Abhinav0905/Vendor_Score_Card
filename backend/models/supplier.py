from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import Base

class Supplier(Base):
    """Supplier model with scorecard metrics"""
    __tablename__ = "suppliers"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    
    # Scorecard metrics
    data_accuracy = Column(Float, default=100.0)  # Percentage
    error_rate = Column(Float, default=0.0)  # Percentage
    compliance_score = Column(Float, default=100.0)  # Percentage
    response_time = Column(Integer, default=0)  # In hours
    
    # Additional details
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_submission_date = Column(DateTime, nullable=True)
    
    # Relationships
    submissions = relationship("EPCISSubmission", 
                             primaryjoin="Supplier.id == foreign(EPCISSubmission.supplier_id)",
                             backref="supplier")
    
    def __repr__(self):
        return f"<Supplier(id='{self.id}', name='{self.name}')>"

class PerformanceTrend(Base):
    """Supplier performance trend model for tracking metrics over time"""
    __tablename__ = "performance_trends"
    
    id = Column(String, primary_key=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)
    
    # Time period
    month = Column(String, nullable=False)  # YYYY-MM format
    year = Column(Integer, nullable=False)
    month_number = Column(Integer, nullable=False)  # 1-12
    
    # Metrics
    data_accuracy = Column(Float, default=100.0)  # Percentage
    error_rate = Column(Float, default=0.0)  # Percentage
    compliance_score = Column(Float, default=100.0)  # Percentage
    response_time = Column(Integer, default=0)  # In hours
    submission_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    supplier = relationship("Supplier", backref="performance_trends")
    
    def __repr__(self):
        return f"<PerformanceTrend(supplier='{self.supplier_id}', month='{self.month}')>"