import sys
import os
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.models.supplier import Supplier

# Add backend path to sys.path to import existing models
backend_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend')
sys.path.insert(0, backend_path)

# from models.supplier import Supplier
# from models.epcis_submission import EPCISSubmission

from backend.models.epcis_submission import EPCISSubmission
from email_agent.config import settings

logger = logging.getLogger(__name__)

class DatabaseService:
    """Database service for searching PO and LOT data"""
    
    def __init__(self, settings):
        self.settings = settings
        self.engine = create_engine(settings.DATABASE_URL)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def search_po_and_lot(self, po_numbers: List[str], lot_numbers: List[str]) -> Dict[str, Any]:
        """Search for PO and LOT numbers in database"""
        try:
            session = self.SessionLocal()
            results = {
                'found': False,
                'po_data': None,
                'lot_data': None,
                'epcis_files': [],
                'vendor_info': None
            }
            
            # Search for PO numbers in business transactions
            if po_numbers:
                for po_number in po_numbers:
                    po_data = self._search_po_in_submissions(session, po_number)
                    if po_data:
                        results['found'] = True
                        results['po_data'] = po_data
                        break
            
            # Search for LOT numbers in EPCIS data
            if lot_numbers:
                for lot_number in lot_numbers:
                    lot_data = self._search_lot_in_submissions(session, lot_number)
                    if lot_data:
                        results['found'] = True
                        results['lot_data'] = lot_data
                        if not results['po_data']:
                            results['po_data'] = lot_data
                        break
            
            # Get vendor information if we found data
            if results['found'] and results['po_data']:
                vendor_info = self._get_vendor_info(session, results['po_data'].get('supplier_id'))
                results['vendor_info'] = vendor_info
                
                # Get EPCIS file paths
                epcis_files = self._get_epcis_files(session, results['po_data'].get('id'))
                results['epcis_files'] = epcis_files
            
            session.close()
            logger.info(f"Database search completed. Found: {results['found']}")
            return results
            
        except Exception as e:
            logger.error(f"Database search error: {str(e)}")
            return {'found': False, 'error': str(e)}
    
    def _search_po_in_submissions(self, session, po_number: str) -> Optional[Dict[str, Any]]:
        """Search for PO number in EPCIS submissions"""
        try:
            # Search in raw EPCIS data for business transactions
            query = text("""
                SELECT es.*, s.name as supplier_name, s.email as supplier_email
                FROM epcis_submissions es
                JOIN suppliers s ON es.supplier_id = s.id
                WHERE es.raw_data LIKE :po_pattern
                ORDER BY es.created_at DESC
                LIMIT 1
            """)
            
            result = session.execute(query, {'po_pattern': f'%{po_number}%'}).fetchone()
            
            if result:
                return {
                    'id': result.id,
                    'supplier_id': result.supplier_id,
                    'file_path': result.file_path,
                    'supplier_name': result.supplier_name,
                    'supplier_email': result.supplier_email,
                    'po_number': po_number,
                    'created_at': result.created_at
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching PO: {str(e)}")
            return None
    
    def _search_lot_in_submissions(self, session, lot_number: str) -> Optional[Dict[str, Any]]:
        """Search for LOT number in EPCIS submissions"""
        try:
            # Search in raw EPCIS data for lot numbers
            query = text("""
                SELECT es.*, s.name as supplier_name, s.email as supplier_email
                FROM epcis_submissions es
                JOIN suppliers s ON es.supplier_id = s.id
                WHERE es.raw_data LIKE :lot_pattern
                ORDER BY es.created_at DESC
                LIMIT 1
            """)
            
            result = session.execute(query, {'lot_pattern': f'%{lot_number}%'}).fetchone()
            
            if result:
                return {
                    'id': result.id,
                    'supplier_id': result.supplier_id,
                    'file_path': result.file_path,
                    'supplier_name': result.supplier_name,
                    'supplier_email': result.supplier_email,
                    'lot_number': lot_number,
                    'created_at': result.created_at
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching LOT: {str(e)}")
            return None
    
    def _get_vendor_info(self, session, supplier_id: int) -> Optional[Dict[str, Any]]:
        """Get vendor information"""
        try:
            supplier = session.query(Supplier).filter(Supplier.id == supplier_id).first()
            
            if supplier:
                return {
                    'id': supplier.id,
                    'name': supplier.name,
                    'email': supplier.email,
                    'contact_person': getattr(supplier, 'contact_person', None),
                    'phone': getattr(supplier, 'phone', None)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting vendor info: {str(e)}")
            return None
    
    def _get_epcis_files(self, session, submission_id: int) -> List[str]:
        """Get EPCIS file paths for a submission"""
        try:
            submission = session.query(EPCISSubmission).filter(EPCISSubmission.id == submission_id).first()
            
            if submission and submission.file_path:
                return [submission.file_path]
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting EPCIS files: {str(e)}")
            return []
    
    def get_submission_by_id(self, submission_id: int) -> Optional[Dict[str, Any]]:
        """Get submission details by ID"""
        try:
            session = self.SessionLocal()
            
            submission = session.query(EPCISSubmission).filter(EPCISSubmission.id == submission_id).first()
            
            if submission:
                supplier = session.query(Supplier).filter(Supplier.id == submission.supplier_id).first()
                
                result = {
                    'id': submission.id,
                    'file_path': submission.file_path,
                    'supplier_id': submission.supplier_id,
                    'supplier_name': supplier.name if supplier else None,
                    'supplier_email': supplier.email if supplier else None,
                    'created_at': submission.created_at,
                    'status': submission.status
                }
                
                session.close()
                return result
            
            session.close()
            return None
            
        except Exception as e:
            logger.error(f"Error getting submission: {str(e)}")
            return None
    
    def test_connection(self):
        """Test if the database connection is working."""
        try:
            # Attempt a simple database operation
            with self.SessionLocal() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {str(e)}")
            return False
