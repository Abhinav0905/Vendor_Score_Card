import os
import sys
import json
import logging
from typing import List, Dict, Any

from backend.epcis.event_validation import EPCISEventValidator
from backend.epcis.parser import EPCISParser
from backend.epcis.sequence_validation import EPCISSequenceValidator
# backend_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend')
# sys.path.insert(0, backend_path)
# Add the parent directory to path to access backend modules
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

 

from langchain.tools import Tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from email_agent.models import ValidationError
from email_agent.config import settings

logger = logging.getLogger(__name__)

class EPCISAnalyzerAgent:
    """AI Agent for analyzing EPCIS files and identifying errors"""
    
    def __init__(self, settings):
        self.settings = settings
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.1,
            api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize EPCIS validators
        self.sequence_validator = EPCISSequenceValidator()
        self.event_validator = EPCISEventValidator() if 'EPCISEventValidator' in dir() else None
        self.parser = EPCISParser() if 'EPCISParser' in dir() else None
        
        self.agent = self._create_agent()
    
    def _create_agent(self):
        """Create the EPCIS analyzer agent"""
        
        tools = [
            Tool(
                name="validate_epcis_sequence",
                description="Validate EPCIS event sequences according to DSCSA rules",
                func=self._validate_sequence
            ),
            Tool(
                name="validate_epcis_events",
                description="Validate individual EPCIS events for format and content",
                func=self._validate_events
            ),
            Tool(
                name="parse_epcis_file",
                description="Parse EPCIS file and extract events",
                func=self._parse_file
            ),
            Tool(
                name="analyze_error_patterns",
                description="Analyze validation errors and categorize them",
                func=self._analyze_error_patterns
            )
        ]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert EPCIS (Electronic Product Code Information Services) file analyzer specialized in DSCSA compliance.

Your responsibilities:
1. Parse EPCIS files (XML/JSON format)
2. Validate event sequences according to DSCSA rules
3. Identify format errors, missing fields, and compliance issues
4. Categorize errors by severity and type
5. Generate specific recommendations for fixing errors

DSCSA Event Sequence Rules:
- commissioning → packing → shipping → receiving → storing → dispensing/decommissioning
- Each event must have proper predecessors
- Items must be commissioned before use in other events
- Aggregation hierarchy must be consistent

Common Error Types:
- Missing required fields (bizStep, eventTime, epcList)
- Invalid event sequences
- Packaging hierarchy violations
- Format errors (invalid EPCs, dates)
- Business logic violations

Provide detailed, actionable recommendations for each error found."""),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        agent = create_openai_tools_agent(self.llm, tools, prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    def analyze_epcis_file(self, file_path: str) -> List[ValidationError]:
        """Analyze EPCIS file and return validation errors"""
        try:
            if not os.path.exists(file_path):
                return [ValidationError(
                    type="file_error",
                    severity="error", 
                    message=f"EPCIS file not found: {file_path}"
                )]
            
            logger.info(f"Analyzing EPCIS file: {file_path}")
            
            # Use the agent to analyze the file
            result = self.agent.invoke({
                "input": f"Please analyze the EPCIS file at {file_path} and identify all validation errors, sequence issues, and compliance problems."
            })
            
            # Parse the file and validate
            events = self._parse_file(file_path)
            if not events:
                return [ValidationError(
                    type="parse_error",
                    severity="error",
                    message="Could not parse EPCIS file or no events found"
                )]
            
            # Perform validations
            validation_errors = []
            
            # Sequence validation
            sequence_errors = self._validate_sequence(json.dumps(events))
            validation_errors.extend(self._convert_to_validation_errors(sequence_errors, "sequence"))
            
            # Event validation
            if self.event_validator:
                event_errors = self._validate_events(json.dumps(events))
                validation_errors.extend(self._convert_to_validation_errors(event_errors, "event"))
            
            # Hierarchy validation
            hierarchy_errors = self.sequence_validator.validate_packaging_hierarchy(events)
            validation_errors.extend(self._convert_to_validation_errors(hierarchy_errors, "hierarchy"))
            
            # Analyze error patterns with AI
            if validation_errors:
                analyzed_errors = self._analyze_error_patterns(json.dumps([e.dict() for e in validation_errors]))
                # Enhance errors with AI insights
                for i, error in enumerate(validation_errors):
                    if i < len(analyzed_errors):
                        error.recommendation = analyzed_errors[i].get('recommendation')
            
            logger.info(f"Found {len(validation_errors)} validation errors")
            return validation_errors
            
        except Exception as e:
            logger.error(f"Error analyzing EPCIS file: {str(e)}")
            return [ValidationError(
                type="analysis_error",
                severity="error",
                message=f"Error analyzing file: {str(e)}"
            )]
    
    def _parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse EPCIS file and extract events"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            events = []
            
            if file_path.endswith('.json'):
                # Parse JSON format
                data = json.loads(content)
                if 'epcisBody' in data and 'eventList' in data['epcisBody']:
                    events = data['epcisBody']['eventList']
                elif 'events' in data:
                    events = data['events']
                elif isinstance(data, list):
                    events = data
                    
            elif file_path.endswith('.xml'):
                # For XML, we'd need to implement XML parsing
                # For now, return empty list
                logger.warning("XML parsing not implemented in basic version")
                events = []
            
            logger.info(f"Parsed {len(events)} events from {file_path}")
            return events
            
        except Exception as e:
            logger.error(f"Error parsing file: {str(e)}")
            return []
    
    def _validate_sequence(self, events_json: str) -> List[Dict[str, Any]]:
        """Validate event sequences"""
        try:
            events = json.loads(events_json)
            errors = self.sequence_validator.validate_sequence(events)
            logger.info(f"Sequence validation found {len(errors)} errors")
            return errors
        except Exception as e:
            logger.error(f"Sequence validation error: {str(e)}")
            return []
    
    def _validate_events(self, events_json: str) -> List[Dict[str, Any]]:
        """Validate individual events"""
        try:
            if not self.event_validator:
                return []
                
            events = json.loads(events_json)
            all_errors = []
            
            for event in events:
                errors = self.event_validator.validate_event(event)
                all_errors.extend(errors)
            
            logger.info(f"Event validation found {len(all_errors)} errors")
            return all_errors
        except Exception as e:
            logger.error(f"Event validation error: {str(e)}")
            return []
    
    def _analyze_error_patterns(self, errors_json: str) -> List[Dict[str, Any]]:
        """Analyze error patterns and provide recommendations"""
        try:
            errors = json.loads(errors_json)
            
            # Use AI to analyze error patterns
            analysis_prompt = f"""
            Analyze these EPCIS validation errors and provide specific recommendations:
            
            {json.dumps(errors, indent=2)}
            
            For each error, provide:
            1. Root cause analysis
            2. Specific fix recommendation
            3. Prevention strategy
            4. Priority level
            
            Return as JSON array with enhanced error objects.
            """
            
            response = self.llm.invoke(analysis_prompt)
            
            # Parse AI response (simplified for now)
            analyzed_errors = []
            for error in errors:
                recommendation = self._generate_recommendation(error)
                analyzed_errors.append({
                    **error,
                    'recommendation': recommendation
                })
            
            return analyzed_errors
            
        except Exception as e:
            logger.error(f"Error pattern analysis failed: {str(e)}")
            return []
    
    def _generate_recommendation(self, error: Dict[str, Any]) -> str:
        """Generate recommendation for a specific error"""
        error_type = error.get('type', '')
        message = error.get('message', '')
        
        if 'sequence' in error_type.lower():
            if 'not commissioned' in message:
                return "Add a commissioning event for this item before using it in other events. Ensure the commissioning event has action=ADD and proper bizStep=commissioning."
            elif 'predecessor' in message:
                return "Ensure events follow the correct DSCSA sequence: commissioning → packing → shipping → receiving → storing → dispensing/decommissioning."
            else:
                return "Review event sequence to ensure compliance with DSCSA requirements."
                
        elif 'hierarchy' in error_type.lower():
            if 'already aggregated' in message:
                return "Disaggregate the item from its current parent before aggregating to a new parent."
            else:
                return "Review packaging hierarchy to ensure proper parent-child relationships."
                
        elif 'field' in error_type.lower():
            if 'missing' in message.lower():
                field_match = message.split('field:')[-1].strip() if 'field:' in message else 'required field'
                return f"Add the missing {field_match} to the event data."
            else:
                return "Ensure all required fields are present and properly formatted."
                
        else:
            return "Review the error message and consult EPCIS documentation for proper format."
    
    def _convert_to_validation_errors(self, errors: List[Dict[str, Any]], error_category: str) -> List[ValidationError]:
        """Convert validation errors to ValidationError objects"""
        validation_errors = []
        
        for error in errors:
            validation_error = ValidationError(
                type=error.get('type', error_category),
                severity=error.get('severity', 'error'),
                message=error.get('message', error.get('description', 'Unknown error')),
                line_number=error.get('line_number'),
                epc=error.get('epc'),
                recommendation=error.get('recommendation')
            )
            validation_errors.append(validation_error)
        
        return validation_errors
