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
        
    async def get_po_information(self, po_number: str) -> Dict[str, Any]:
        """
        Lookup PO information from database including vendor details
        
        Args:
            po_number: Purchase order number to lookup
            
        Returns:
            Dictionary containing PO and vendor information
        """
        try:
            # Ensure connection is established
            if not hasattr(self, 'connection') or not self.connection:
                if not self.test_connection():
                    logger.error("Database connection not available")
                    return None
            
            # Query to get PO and vendor information
            query = """
            SELECT 
                po.po_number,
                po.vendor_id,
                po.order_date,
                po.expected_delivery_date,
                po.status,
                po.total_amount,
                v.vendor_name,
                v.vendor_email,
                v.vendor_phone,
                v.vendor_address,
                v.primary_contact,
                v.contact_email,
                COUNT(pi.item_id) as item_count
            FROM purchase_orders po
            LEFT JOIN vendors v ON po.vendor_id = v.vendor_id
            LEFT JOIN po_items pi ON po.po_number = pi.po_number
            WHERE po.po_number = %s
            GROUP BY po.po_number, po.vendor_id, po.order_date, po.expected_delivery_date, 
                     po.status, po.total_amount, v.vendor_name, v.vendor_email, 
                     v.vendor_phone, v.vendor_address, v.primary_contact, v.contact_email
            """
            
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, (po_number,))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                logger.info(f"Found PO information for {po_number}: {result.get('vendor_name', 'Unknown vendor')}")
                return {
                    'po_number': result.get('po_number'),
                    'vendor_id': result.get('vendor_id'),
                    'vendor_name': result.get('vendor_name'),
                    'vendor_email': result.get('vendor_email') or result.get('contact_email'),
                    'vendor_phone': result.get('vendor_phone'),
                    'vendor_address': result.get('vendor_address'),
                    'primary_contact': result.get('primary_contact'),
                    'order_date': result.get('order_date'),
                    'expected_delivery_date': result.get('expected_delivery_date'),
                    'status': result.get('status'),
                    'total_amount': result.get('total_amount'),
                    'item_count': result.get('item_count', 0)
                }
            else:
                logger.warning(f"No PO information found for {po_number}")
                return None
                
        except Exception as e:
            logger.error(f"Error querying PO information for {po_number}: {str(e)}")
            return None

    async def get_lot_information(self, lot_number: str, po_number: str = None) -> Dict[str, Any]:
        """
        Lookup LOT information from database
        
        Args:
            lot_number: Lot number to lookup
            po_number: Optional PO number to filter results
            
        Returns:
            Dictionary containing lot information
        """
        try:
            # Ensure connection is established
            if not hasattr(self, 'connection') or not self.connection:
                if not self.test_connection():
                    logger.error("Database connection not available")
                    return None
            
            # Base query for lot information
            query = """
            SELECT 
                l.lot_number,
                l.po_number,
                l.product_id,
                l.quantity,
                l.manufacture_date,
                l.expiry_date,
                l.batch_id,
                l.status,
                p.product_name,
                p.product_code,
                p.manufacturer
            FROM lots l
            LEFT JOIN products p ON l.product_id = p.product_id
            WHERE l.lot_number = %s
            """
            
            params = [lot_number]
            
            # Add PO filter if provided
            if po_number:
                query += " AND l.po_number = %s"
                params.append(po_number)
            
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params)
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                logger.info(f"Found lot information for {lot_number}")
                return {
                    'lot_number': result.get('lot_number'),
                    'po_number': result.get('po_number'),
                    'product_id': result.get('product_id'),
                    'product_name': result.get('product_name'),
                    'product_code': result.get('product_code'),
                    'manufacturer': result.get('manufacturer'),
                    'quantity': result.get('quantity'),
                    'manufacture_date': result.get('manufacture_date'),
                    'expiry_date': result.get('expiry_date'),
                    'batch_id': result.get('batch_id'),
                    'status': result.get('status')
                }
            else:
                logger.warning(f"No lot information found for {lot_number}")
                return None
                
        except Exception as e:
            logger.error(f"Error querying lot information for {lot_number}: {str(e)}")
            return None
