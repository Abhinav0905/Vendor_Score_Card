"""
Main entry point for the EPCIS Error Correction Agent
"""
import asyncio
import argparse
import logging

from email_agent.utils.logging_config import setup_logging
from email_agent.agents.orchestrator import OrchestratorAgent
from email_agent.config.settings import Settings
from email_agent.services.gmail_service import GmailService

# Add project root to Python path to resolve module not found error
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# from utils.logging_config import setup_logging
# from agents.orchestrator import OrchestratorAgent
# from config.settings import Settings
# from services.gmail_service import GmailService

logger = logging.getLogger(__name__)

async def run_agent():
    """Run the main agent workflow"""
    logger.info("=" * 60)
    logger.info("EPCIS Error Correction Agent Starting")
    logger.info("=" * 60)
    
    try:
        settings = Settings()
        agent = OrchestratorAgent(settings)
        
        # Check agent status
        status = await agent.get_status()
        logger.info(f"Agent Status: {status}")
        
        if not status["gmail_connected"]:
            logger.error("Gmail service not authenticated. Please run setup first.")
            return
        
        if not status["database_connected"]:
            logger.error("Database connection failed. Please check configuration.")
            return
        
        # Run the workflow
        result = await agent.run()
        
        logger.info("=" * 60)
        logger.info("EPCIS Error Correction Agent Completed")
        logger.info(f"Status: {result['status']}")
        logger.info(f"Processed: {result['processed_count']} emails")
        logger.info(f"Failed: {result['failed_count']} emails")
        if 'duration' in result:
            logger.info(f"Duration: {result['duration']:.2f} seconds")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Agent failed: {str(e)}")
        raise

async def process_single_email(message_id: str):
    """Process a single email by message ID"""
    logger.info(f"Processing single email: {message_id}")
    
    try:
        settings = Settings()
        agent = OrchestratorAgent(settings)
        
        result = await agent.process_single_email_by_id(message_id)
        
        logger.info(f"Single email processing result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to process single email: {str(e)}")
        raise

def check_status():
    """Check agent status and configuration"""
    try:
        settings = Settings()
        agent = OrchestratorAgent(settings)
        
        status = agent.get_status()
        
        print("\n" + "=" * 60)
        print("EPCIS Error Correction Agent Status")
        print("=" * 60)
        print(f"Agent Name: {status['agent_name']}")
        print(f"Status: {status['status']}")
        print(f"Gmail Connected: {status['gmail_connected']}")
        print(f"Database Connected: {status['database_connected']}")
        print("\nSettings:")
        for key, value in status['settings'].items():
            print(f"  {key}: {value}")
        print("=" * 60)
        
    except Exception as e:
        print(f"Status check failed: {str(e)}")

def setup_gmail():
    """Setup Gmail authentication"""
    try:
        print("Setting up Gmail authentication...")
        settings = Settings()
        gmail_service = GmailService(settings)
        
        # This will trigger the OAuth flow
        gmail_service.authenticate()
        
        print("Gmail authentication completed successfully!")
        
    except Exception as e:
        print(f"Gmail setup failed: {str(e)}")

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="EPCIS Error Correction Agent")
    parser.add_argument(
        "command",
        choices=["run", "status", "setup-gmail", "process-email"],
        help="Command to execute"
    )
    parser.add_argument(
        "--message-id",
        help="Gmail message ID for single email processing"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    parser.add_argument(
        "--log-file",
        help="Log file path (default: logs/agent.log)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(level=args.log_level, log_file=args.log_file)
    
    if args.command == "run":
        asyncio.run(run_agent())
    
    elif args.command == "status":
        check_status()
    
    elif args.command == "setup-gmail":
        setup_gmail()
    
    elif args.command == "process-email":
        if not args.message_id:
            print("Error: --message-id is required for process-email command")
            return
        asyncio.run(process_single_email(args.message_id))
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
