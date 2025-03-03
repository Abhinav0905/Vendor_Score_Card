import os
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Any, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class EPCISFileHandler:
    """Handler for EPCIS file operations"""
    
    def __init__(self, storage_path: str = "storage"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
    
    def store_file(self, file_content: bytes, file_name: str, supplier_id: str) -> str:
        """Store an EPCIS file in the storage directory
        
        Args:
            file_content: Raw content of the file
            file_name: Original filename
            supplier_id: ID of the supplier
            
        Returns:
            Path where the file was stored
        """
        # Create supplier directory if it doesn't exist
        supplier_dir = os.path.join(self.storage_path, supplier_id)
        os.makedirs(supplier_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(supplier_dir, file_name)
        with open(file_path, 'wb') as f:
            f.write(file_content)
            
        return file_path
    
    def parse_file(self, file_path: str) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
        """Parse an EPCIS file and extract events
        
        Args:
            file_path: Path to the EPCIS file
            
        Returns:
            Tuple of (parsed data, list of parse warnings)
        """
        warnings = []
        
        try:
            if file_path.lower().endswith('.xml'):
                return self._parse_xml(file_path, warnings)
            elif file_path.lower().endswith('.json'):
                return self._parse_json(file_path, warnings)
            else:
                raise ValueError("Unsupported file format")
                
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            warnings.append({
                "level": "error",
                "message": f"Failed to parse file: {str(e)}"
            })
            return {}, warnings
    
    def _parse_xml(self, file_path: str, warnings: List[Dict[str, str]]) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
        """Parse an XML EPCIS file
        
        Args:
            file_path: Path to the XML file
            warnings: List to append warnings to
            
        Returns:
            Tuple of (parsed data, warnings)
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Remove XML namespace for easier parsing
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}', 1)[1]
            
            # Extract events
            events = []
            for event_elem in root.findall('.//ObjectEvent') + root.findall('.//AggregationEvent'):
                try:
                    event = self._parse_xml_event(event_elem)
                    events.append(event)
                except Exception as e:
                    warnings.append({
                        "level": "warning",
                        "message": f"Failed to parse event: {str(e)}"
                    })
            
            return {
                "format": "xml",
                "events": events,
                "schema_version": root.get("schemaVersion", "1.2")
            }, warnings
            
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML format: {str(e)}")
    
    def _parse_xml_event(self, event_elem: ET.Element) -> Dict[str, Any]:
        """Parse an XML event element
        
        Args:
            event_elem: XML element containing event data
            
        Returns:
            Dict with parsed event data
        """
        event = {
            "type": event_elem.tag,
            "time": event_elem.findtext("eventTime"),
            "timezone_offset": event_elem.findtext("eventTimeZoneOffset"),
            "action": event_elem.findtext("action"),
            "biz_step": event_elem.findtext("bizStep"),
            "disposition": event_elem.findtext("disposition")
        }
        
        # Extract EPCs
        epc_list = event_elem.find("epcList")
        if epc_list is not None:
            event["epcs"] = [epc.text for epc in epc_list.findall("epc")]
        
        # Extract business location
        biz_location = event_elem.find("bizLocation")
        if biz_location is not None:
            event["biz_location"] = biz_location.findtext("id")
        
        # Extract read point
        read_point = event_elem.find("readPoint")
        if read_point is not None:
            event["read_point"] = read_point.findtext("id")
        
        return event
    
    def _parse_json(self, file_path: str, warnings: List[Dict[str, str]]) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
        """Parse a JSON EPCIS file
        
        Args:
            file_path: Path to the JSON file
            warnings: List to append warnings to
            
        Returns:
            Tuple of (parsed data, warnings)
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                raise ValueError("Invalid JSON format: root must be an object")
            
            events = []
            for event_data in data.get("eventList", []):
                try:
                    event = self._parse_json_event(event_data)
                    events.append(event)
                except Exception as e:
                    warnings.append({
                        "level": "warning",
                        "message": f"Failed to parse event: {str(e)}"
                    })
            
            return {
                "format": "json",
                "events": events,
                "schema_version": data.get("schemaVersion", "1.2")
            }, warnings
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
    
    def _parse_json_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a JSON event object
        
        Args:
            event_data: Dict containing event data
            
        Returns:
            Dict with parsed event data
        """
        return {
            "type": event_data.get("type", "ObjectEvent"),
            "time": event_data.get("eventTime"),
            "timezone_offset": event_data.get("eventTimeZoneOffset"),
            "action": event_data.get("action"),
            "biz_step": event_data.get("bizStep"),
            "disposition": event_data.get("disposition"),
            "epcs": event_data.get("epcList", []),
            "biz_location": event_data.get("bizLocation", {}).get("id"),
            "read_point": event_data.get("readPoint", {}).get("id")
        }
    
    def move_to_archive(self, file_path: str) -> Optional[str]:
        """Move a processed file to the archive directory
        
        Args:
            file_path: Path to the file to archive
            
        Returns:
            Path to the archived file, or None if archiving failed
        """
        try:
            # Create archive directory if it doesn't exist
            file_dir = os.path.dirname(file_path)
            archive_dir = os.path.join(file_dir, "archived")
            os.makedirs(archive_dir, exist_ok=True)
            
            # Move file to archive
            file_name = os.path.basename(file_path)
            archive_path = os.path.join(archive_dir, file_name)
            os.rename(file_path, archive_path)
            
            return archive_path
            
        except Exception as e:
            logger.error(f"Error archiving file {file_path}: {e}")
            return None