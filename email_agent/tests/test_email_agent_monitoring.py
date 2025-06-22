#!/usr/bin/env python3
import asyncio
import signal
import sys
from datetime import datetime
from email_agent.agents.orchestrator import EmailProcessingOrchestrator

class EmailAgentMonitor:
    """Monitor and run the email agent continuously"""
    
    def __init__(self, check_interval=300):  # Check every 5 minutes
        self.orchestrator = EmailProcessingOrchestrator()
        self.check_interval = check_interval
        self.running = True
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signal"""
        print(f"\n📊 Received shutdown signal. Stopping email agent...")
        self.running = False
        
    async def monitor_emails(self):
        """Main monitoring loop"""
        print("🚀 Starting Email Agent Monitor")
        print(f"⏰ Check interval: {self.check_interval} seconds")
        print("Press Ctrl+C to stop")
        print("=" * 50)
        
        while self.running:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] 🔍 Checking for new EPCIS error emails...")
                
                # Process any new emails
                results = await self.orchestrator.process_new_emails()
                
                if results:
                    print(f"[{timestamp}] ✅ Processed {len(results)} emails")
                    for result in results:
                        print(f"   - PO: {result.get('po_number', 'N/A')} | "
                              f"Vendor: {result.get('vendor_name', 'N/A')} | "
                              f"Status: {result.get('status', 'N/A')}")
                else:
                    print(f"[{timestamp}] 📭 No new emails to process")
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                print(f"❌ Error in monitoring loop: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute on error
        
        print("📊 Email agent monitoring stopped")

async def main():
    """Run the email agent monitor"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Email Agent Monitor')
    parser.add_argument('--interval', type=int, default=300, 
                        help='Check interval in seconds (default: 300)')
    parser.add_argument('--test', action='store_true',
                        help='Run in test mode with sample data')
    
    args = parser.parse_args()
    
    monitor = EmailAgentMonitor(check_interval=args.interval)
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, monitor.signal_handler)
    signal.signal(signal.SIGTERM, monitor.signal_handler)
    
    if args.test:
        print("🧪 Running in test mode...")
        # Run test workflow instead
        from test_workflow_steps import WorkflowStepTester
        tester = WorkflowStepTester()
        await tester.run_complete_test()
    else:
        await monitor.monitor_emails()

if __name__ == "__main__":
    asyncio.run(main())