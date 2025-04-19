from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import Base

class Supplier(Base):
    """Model representing a supplier/vendor"""
    __tablename__ = 'suppliers'
    
    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True)
    contact_email = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Fix the relationship - remove the backref as it's already defined in EPCISSubmission
    submissions = relationship("EPCISSubmission", back_populates="supplier")
    
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