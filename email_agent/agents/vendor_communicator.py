import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from jinja2 import Template

from langchain.tools import Tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from email_agent.config import settings
from email_agent.models import ActionPlan, ValidationError
from email_agent.services import GmailService


logger = logging.getLogger(__name__)

class VendorCommunicatorAgent:
    """AI Agent for generating and sending vendor communications"""
    
    def __init__(self, settings):
        self.settings = settings
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.2,  # Slightly higher temperature for more natural language
            api_key=settings.OPENAI_API_KEY
        )
        self.gmail_service = GmailService(settings)
        self.agent = self._create_agent()
    
    def _create_agent(self):
        """Create the vendor communication agent"""
        
        tools = [
            Tool(
                name="generate_error_summary",
                description="Generate a clear summary of EPCIS errors for vendors",
                func=self._generate_error_summary
            ),
            Tool(
                name="create_action_items",
                description="Create specific action items for fixing EPCIS errors",
                func=self._create_action_items
            ),
            Tool(
                name="determine_priority",
                description="Determine priority level based on error types and count",
                func=self._determine_priority
            ),
            Tool(
                name="generate_email_content",
                description="Generate professional email content for vendor communication",
                func=self._generate_email_content
            )
        ]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional vendor communication specialist for EPCIS compliance.

Your role is to:
1. Create clear, actionable communications about EPCIS errors
2. Generate vendor-friendly explanations of technical issues
3. Provide step-by-step remediation instructions
4. Maintain professional tone while being helpful and specific

Guidelines:
- Use clear, non-technical language when possible
- Provide specific examples and steps to fix issues
- Include deadlines and priority levels
- Maintain professional but helpful tone
- Reference specific DSCSA requirements when relevant
- Include contact information for support

Communication should be:
- Respectful and professional
- Clear and actionable
- Specific about what needs to be fixed
- Helpful with examples and guidance"""),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        agent = create_openai_tools_agent(self.llm, tools, prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    def create_and_send_action_plan(self, 
                                  po_number: str,
                                  lot_number: str,
                                  vendor_info: Dict[str, Any],
                                  validation_errors: List[ValidationError],
                                  file_path: str) -> bool:
        """Create and send action plan to vendor"""
        try:
            # Generate action plan using AI
            action_plan = self._generate_action_plan(
                po_number, lot_number, vendor_info, validation_errors, file_path
            )
            
            # Generate email content
            email_content = self._generate_vendor_email(action_plan)
            
            # Send email
            success = self.gmail_service.send_email(
                to=vendor_info.get('email', ''),
                subject=email_content['subject'],
                body=email_content['plain_text'],
                html_body=email_content['html']
            )
            
            if success:
                logger.info(f"Action plan sent successfully to {vendor_info.get('name', 'vendor')}")
            else:
                logger.error(f"Failed to send action plan to {vendor_info.get('name', 'vendor')}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error creating/sending action plan: {str(e)}")
            return False
    
    # async def generate_action_plan(self, vendor_info: Dict[str, Any], po_number: str = None, lot_number: str = None) -> ActionPlan:
    #     """Public method to generate an action plan for orchestrator compatibility.
        
    #     Note: The orchestrator will handle validation_errors and file_path separately."""
    #     try:
    #         if not vendor_info or not isinstance(vendor_info, dict):
    #             logger.error("Invalid vendor_info provided, returning empty action plan.")
    #             return self._create_empty_action_plan()

    #         validation_errors = vendor_info.get('validation_errors', [])
    #         file_path = vendor_info.get('file_path', '')
    #         po_number = po_number or vendor_info.get('po_number', 'UNKNOWN')
    #         lot_number = lot_number or vendor_info.get('lot_number', 'UNKNOWN')
            
    #         if not validation_errors:
    #             logger.info("No validation errors found, no action plan needed.")
    #             return self._create_empty_action_plan()
            
    #         return self._generate_action_plan(po_number, lot_number, vendor_info, validation_errors, file_path)
    #     except Exception as e:
    #         logger.error(f"Error in generate_action_plan: {str(e)}")
    #         return self._create_empty_action_plan()

    async def generate_action_plan(self, vendor_info: Dict[str, Any], validation_errors: List[ValidationError], *args) -> ActionPlan:
        """Generate an action plan for vendor communication.
        
        Args:
            vendor_info: Dictionary containing vendor details and PO information
            validation_errors: List of validation errors found in EPCIS data
            *args: Additional arguments that might be passed by the orchestrator
        """
        try:
            if not vendor_info or not isinstance(vendor_info, dict):
                logger.error("Invalid vendor_info provided, returning empty action plan.")
                return self._create_empty_action_plan()

            po_number = vendor_info.get('po_number', 'UNKNOWN')
            lot_number = vendor_info.get('lot_number', 'UNKNOWN')
            file_path = vendor_info.get('file_path', '')
            
            if not validation_errors:
                logger.info("No validation errors found, creating empty action plan.")
                return self._create_empty_action_plan()
            
            return self._generate_action_plan(
                po_number=po_number,
                lot_number=lot_number,
                vendor_info=vendor_info,
                validation_errors=validation_errors,
                file_path=file_path
            )
        except Exception as e:
            logger.error(f"Error in generate_action_plan: {str(e)}")
            return self._create_empty_action_plan()

    async def send_correction_email(self, action_plan: ActionPlan, vendor_info: Dict[str, Any], *args) -> bool:
        """Public method to send correction email for orchestrator compatibility.
        
        Note: The orchestrator may pass additional arguments that we don't need."""
        try:
            # Do not send an email if the action plan is empty or invalid (has no errors)
            if not action_plan or not action_plan.recommendations:
                logger.warning("Skipping email for action plan with no errors.")
                return False
                
            if not vendor_info or not isinstance(vendor_info, dict) or not vendor_info.get('email'):
                logger.error("Invalid vendor_info or missing email, cannot send email.")
                return False

            email_content = self._generate_vendor_email(action_plan)
            result = await self.gmail_service.send_email(
                to=vendor_info.get('email', ''),
                subject=email_content['subject'],
                body=email_content['plain_text'],
                html_body=email_content['html']
            )
            return bool(result)
        except Exception as e:
            logger.error(f"Error in send_correction_email: {str(e)}")
            return False
    
    def _create_empty_action_plan(self) -> ActionPlan:
        """Creates a default, empty action plan to avoid returning None."""
        return ActionPlan(
            po_number="UNKNOWN",
            lot_number="UNKNOWN",
            vendor_email="",
            vendor_name="Unknown Vendor",
            errors=[],
            recommendations=["Could not generate action plan due to missing information."],
            priority="normal",
            due_date=datetime.now() + timedelta(days=1)
        )

    def _generate_action_plan(self, 
                            po_number: str,
                            lot_number: str,
                            vendor_info: Dict[str, Any],
                            validation_errors: List[ValidationError],
                            file_path: str) -> ActionPlan:
        """Generate action plan using AI agent"""
        try:
            # Use the agent to generate comprehensive action plan
            errors_summary = [e.dict() for e in validation_errors]
            
            result = self.agent.invoke({
                "input": f"""
                Create a comprehensive action plan for vendor {vendor_info.get('name', 'Unknown')} 
                for PO #{po_number} and LOT #{lot_number}.
                
                EPCIS File: {file_path}
                Validation Errors: {errors_summary}
                
                Generate:
                1. Error summary for vendor
                2. Specific action items to fix each error
                3. Priority level and deadline
                4. Professional email content
                """
            })
            
            # Create action plan object
            action_plan = ActionPlan(
                po_number=po_number,
                lot_number=lot_number,
                vendor_email=vendor_info.get('email', ''),
                vendor_name=vendor_info.get('name', 'Unknown Vendor'),
                errors=validation_errors,
                recommendations=self._create_action_items(str(errors_summary)),
                priority=self._determine_priority(str(len(validation_errors))),
                due_date=self._calculate_due_date(validation_errors)
            )
            
            return action_plan
            
        except Exception as e:
            logger.error(f"Error generating action plan: {str(e)}")
            # Return basic action plan as fallback
            return ActionPlan(
                po_number=po_number,
                lot_number=lot_number,
                vendor_email=vendor_info.get('email', ''),
                vendor_name=vendor_info.get('name', 'Unknown Vendor'),
                errors=validation_errors,
                recommendations=[f"Fix {len(validation_errors)} validation errors in EPCIS file"],
                priority="normal"
            )
    
    def _generate_vendor_email(self, action_plan: ActionPlan) -> Dict[str, str]:
        """Generate email content for vendor"""
        try:
            # Generate subject
            subject = f"Action Required: EPCIS File Correction - PO #{action_plan.po_number}"
            if action_plan.priority in ['high', 'urgent']:
                subject = f"URGENT - {subject}"
            
            # Generate email body using AI
            email_input = f"""
            Generate professional email content for:
            Vendor: {action_plan.vendor_name}
            PO: {action_plan.po_number}
            LOT: {action_plan.lot_number}
            Errors: {len(action_plan.errors)}
            Priority: {action_plan.priority}
            Due Date: {action_plan.due_date}
            
            Include:
            - Professional greeting
            - Clear explanation of issues
            - Specific action items
            - Timeline and next steps
            - Contact information
            """
            
            email_content = self.agent.invoke({
                "input": f"Generate professional email content: {email_input}"
            })
            
            # Generate both plain text and HTML versions
            plain_text = self._generate_plain_text_email(action_plan)
            html_content = self._generate_html_email(action_plan)
            
            return {
                'subject': subject,
                'plain_text': plain_text,
                'html': html_content
            }
            
        except Exception as e:
            logger.error(f"Error generating email content: {str(e)}")
            return {
                'subject': f"EPCIS File Correction Required - PO #{action_plan.po_number}",
                'plain_text': f"Please review and correct errors in your EPCIS file for PO #{action_plan.po_number}",
                'html': f"<p>Please review and correct errors in your EPCIS file for PO #{action_plan.po_number}</p>"
            }
    
    def _generate_plain_text_email(self, action_plan: ActionPlan) -> str:
        """Generate plain text email"""
        template = Template("""
Dear {{ vendor_name }},

We have identified {{ error_count }} validation error(s) in your EPCIS file for Purchase Order #{{ po_number }}{% if lot_number %} and LOT #{{ lot_number }}{% endif %}.

ERROR SUMMARY:
{% for error in errors %}
• {{ error.type|title }}: {{ error.message }}
{% if error.recommendation %}  Recommendation: {{ error.recommendation }}{% endif %}
{% endfor %}

ACTION REQUIRED:
{% for recommendation in recommendations %}
{{ loop.index }}. {{ recommendation }}
{% endfor %}

DETAILS:
- Priority: {{ priority|title }}
- Due Date: {{ due_date.strftime('%Y-%m-%d') if due_date else 'ASAP' }}
- PO Number: {{ po_number }}
{% if lot_number %}- LOT Number: {{ lot_number }}{% endif %}

Please review the errors above and resubmit your corrected EPCIS file by the due date. If you need assistance or have questions, please contact our support team.

Best regards,
{{ signature }}
        """.strip())
        
        return template.render(
            vendor_name=action_plan.vendor_name,
            error_count=len(action_plan.errors),
            po_number=action_plan.po_number,
            lot_number=action_plan.lot_number,
            errors=action_plan.errors,
            recommendations=action_plan.recommendations,
            priority=action_plan.priority,
            due_date=action_plan.due_date,
            signature=settings.EMAIL_SIGNATURE
        )
    
    def _generate_html_email(self, action_plan: ActionPlan) -> str:
        """Generate HTML email"""
        template = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }
        .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .priority-{{ priority }} { border-left: 4px solid {% if priority == 'urgent' %}#dc3545{% elif priority == 'high' %}#fd7e14{% else %}#28a745{% endif %}; }
        .error-list { background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0; }
        .error-item { margin: 10px 0; padding: 10px; border-left: 3px solid #dc3545; background-color: #f8f9fa; }
        .recommendation { color: #28a745; font-style: italic; margin-top: 5px; }
        .action-list { background-color: #d1ecf1; padding: 15px; border-radius: 5px; margin: 15px 0; }
        .due-date { color: {% if priority in ['high', 'urgent'] %}#dc3545{% else %}#28a745{% endif %}; font-weight: bold; }
        .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; }
    </style>
</head>
<body>
    <div class="header priority-{{ priority }}">
        <h2>EPCIS File Correction Required</h2>
        <p><strong>Vendor:</strong> {{ vendor_name }}</p>
        <p><strong>PO Number:</strong> {{ po_number }}</p>
        {% if lot_number %}<p><strong>LOT Number:</strong> {{ lot_number }}</p>{% endif %}
        <p><strong>Priority:</strong> <span class="priority">{{ priority|title }}</span></p>
        <p><strong>Due Date:</strong> <span class="due-date">{{ due_date.strftime('%Y-%m-%d') if due_date else 'ASAP' }}</span></p>
    </div>

    <h3>Error Summary ({{ error_count }} errors found)</h3>
    <div class="error-list">
        {% for error in errors %}
        <div class="error-item">
            <strong>{{ error.type|title }}:</strong> {{ error.message }}
            {% if error.line_number %}<br><small>Line: {{ error.line_number }}</small>{% endif %}
            {% if error.epc %}<br><small>EPC: {{ error.epc }}</small>{% endif %}
            {% if error.recommendation %}
            <div class="recommendation">💡 {{ error.recommendation }}</div>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <h3>Required Actions</h3>
    <div class="action-list">
        <ol>
        {% for recommendation in recommendations %}
            <li>{{ recommendation }}</li>
        {% endfor %}
        </ol>
    </div>

    <h3>Next Steps</h3>
    <p>Please review the errors listed above and correct your EPCIS file accordingly. Once corrected, please resubmit the file through your usual submission process.</p>
    
    <p>If you need technical assistance or have questions about these errors, please contact our support team.</p>

    <div class="footer">
        <p>Best regards,<br>{{ signature }}</p>
        <p><small>This is an automated message from the EPCIS validation system.</small></p>
    </div>
</body>
</html>
        """.strip())
        
        return template.render(
            vendor_name=action_plan.vendor_name,
            error_count=len(action_plan.errors),
            po_number=action_plan.po_number,
            lot_number=action_plan.lot_number,
            errors=action_plan.errors,
            recommendations=action_plan.recommendations,
            priority=action_plan.priority,
            due_date=action_plan.due_date,
            signature=settings.EMAIL_SIGNATURE
        )
    
    def _generate_error_summary(self, errors_json: str) -> str:
        """Generate error summary for vendors"""
        try:
            errors = eval(errors_json) if isinstance(errors_json, str) else errors_json
            summary = f"Found {len(errors)} validation errors:\n"
            
            error_types = {}
            for error in errors:
                error_type = error.get('type', 'unknown')
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            for error_type, count in error_types.items():
                summary += f"- {error_type}: {count} errors\n"
            
            return summary
        except:
            return "Multiple validation errors found in EPCIS file"
    
    def _create_action_items(self, errors_json: str) -> List[str]:
        """Create action items for fixing errors"""
        try:
            errors = eval(errors_json) if isinstance(errors_json, str) else errors_json
            actions = []
            
            for error in errors:
                error_type = error.get('type', '')
                message = error.get('message', '')
                
                if 'sequence' in error_type:
                    actions.append("Review and correct event sequence according to DSCSA requirements")
                elif 'field' in error_type:
                    actions.append(f"Add missing required fields to EPCIS events")
                elif 'format' in error_type:
                    actions.append("Correct data format errors (EPCs, dates, URNs)")
                elif 'hierarchy' in error_type:
                    actions.append("Fix packaging hierarchy and aggregation relationships")
                else:
                    actions.append("Review and correct validation errors in EPCIS file")
            
            # Remove duplicates while preserving order
            return list(dict.fromkeys(actions))
        except:
            return ["Review and correct all validation errors in EPCIS file"]
    
    def _determine_priority(self, error_count_str: str) -> str:
        """Determine priority based on error count and types"""
        try:
            error_count = int(error_count_str)
            
            if error_count >= 10:
                return "urgent"
            elif error_count >= 5:
                return "high"
            elif error_count >= 1:
                return "normal"
            else:
                return "low"
        except:
            return "normal"
    
    def _calculate_due_date(self, validation_errors: List[ValidationError]) -> datetime:
        """Calculate due date based on error severity"""
        has_critical = any(e.severity == 'error' for e in validation_errors)
        error_count = len(validation_errors)
        
        if has_critical and error_count >= 10:
            # Urgent: 2 business days
            return datetime.now() + timedelta(days=2)
        elif has_critical and error_count >= 5:
            # High: 3 business days
            return datetime.now() + timedelta(days=3)
        else:
            # Normal: 5 business days
            return datetime.now() + timedelta(days=5)
    
    def _generate_email_content(self, content_request: str) -> str:
        """Generate email content using AI"""
        try:
            response = self.llm.invoke(f"Generate professional email content: {content_request}")
            return response.content if hasattr(response, 'content') else str(response)
        except:
            return "Professional email content could not be generated"
