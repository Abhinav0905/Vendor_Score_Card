# EPCIS Error Correction Agent

An AI-powered agent that automatically processes Gmail emails containing EPCIS validation errors, extracts PO/LOT numbers, validates data against the existing backend system, and sends detailed correction instructions to vendors.

## 🚀 Features

- **📧 Email Processing**: Automatically reads and processes Gmail emails containing EPCIS errors
- **🔍 Data Extraction**: Uses AI to extract PO numbers, LOT numbers, and vendor information from email content
- **🗄️ Database Integration**: Searches existing vendor scorecard database for matching records
- **✅ EPCIS Validation**: Integrates with existing backend EPCIS validation code to identify specific errors
- **🤖 Intelligent Communication**: Generates professional, detailed error correction emails with specific recommendations
- **⚡ Automated Workflow**: Orchestrates the entire process from email receipt to vendor communication

## 🏗️ Architecture

The agent is built using LangChain and follows a modular architecture:

```
email_agent/
├── agents/                 # AI Agent implementations
│   ├── orchestrator.py    # Main coordinator agent
│   ├── email_processor.py # Email data extraction
│   ├── epcis_analyzer.py  # EPCIS validation analysis
│   └── vendor_communicator.py # Email generation & sending
├── services/              # External service integrations
│   ├── gmail_service.py   # Gmail API integration
│   └── database_service.py # Database operations
├── models/                # Data models
│   └── email_models.py    # Pydantic models
├── config/                # Configuration
│   └── settings.py        # Application settings
├── utils/                 # Utilities
│   └── logging_config.py  # Logging setup
└── main.py               # CLI entry point
```

### Agent Workflow

1. **OrchestratorAgent**: Coordinates the entire workflow using LangGraph
2. **EmailProcessorAgent**: Extracts PO/LOT numbers and vendor info using GPT-4
3. **EPCISAnalyzerAgent**: Validates EPCIS data using existing backend code
4. **VendorCommunicatorAgent**: Generates professional correction emails
5. **Gmail/Database Services**: Handle external integrations

## 📦 Installation

### Prerequisites

- Python 3.8+
- Gmail API credentials
- OpenAI API key
- Access to existing vendor scorecard database

### Setup Steps

1. **Clone and Navigate**
   ```bash
   cd /path/to/Vendor_Score_Card/email_agent
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

4. **Gmail Setup** (see detailed section below)

5. **Database Setup** (uses existing vendor scorecard database)

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4-turbo-preview

# Gmail Configuration  
GMAIL_CREDENTIALS_PATH=config/gmail_credentials.json
GMAIL_TOKEN_PATH=config/gmail_token.pickle

# Database Configuration
DATABASE_URL=sqlite:///../../backend/vendor_scorecard.db

# Agent Configuration
MAX_EMAILS_PER_RUN=20
ERROR_EMAIL_LABEL=EPCIS_ERRORS
PROCESSED_EMAIL_LABEL=EPCIS_PROCESSED
```

### Gmail Setup

1. **Enable Gmail API**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create/select a project
   - Enable Gmail API
   - Create credentials (OAuth 2.0 Client ID)
   - Download credentials as `config/gmail_credentials.json`

2. **Setup Authentication**
   ```bash
   python main.py setup-gmail
   ```
   This will open a browser for OAuth authentication.

3. **Gmail Labels**
   Create these labels in Gmail:
   - `EPCIS_ERRORS` (for incoming error emails)
   - `EPCIS_PROCESSED` (for processed emails)

## 🎯 Usage

### Command Line Interface

```bash
# Run the complete workflow
python main.py run

# Check agent status and configuration
python main.py status

# Setup Gmail authentication
python main.py setup-gmail

# Process a single email by ID (for testing)
python main.py process-email --message-id MESSAGE_ID

# Set logging level
python main.py run --log-level DEBUG

# Custom log file
python main.py run --log-file custom.log
```

### Programmatic Usage

```python
from email_agent.agents.orchestrator import OrchestratorAgent
from email_agent.config.settings import Settings

# Initialize agent
settings = Settings()
agent = OrchestratorAgent(settings)

# Run workflow
result = await agent.run()

# Process single email
result = await agent.process_single_email_by_id("message_id")

# Check status
status = agent.get_status()
```

## 🔄 Workflow Details

### 1. Email Fetching
- Connects to Gmail using OAuth
- Searches for emails with `EPCIS_ERRORS` label
- Fetches up to `MAX_EMAILS_PER_RUN` emails

### 2. Data Extraction
- Uses GPT-4 to extract:
  - PO Numbers
  - LOT Numbers  
  - Vendor Information
  - Error Descriptions
  - File Attachments Info

### 3. Database Lookup
- Searches vendor scorecard database
- Matches PO/LOT numbers to existing records
- Retrieves vendor contact information

### 4. EPCIS Validation
- Integrates with existing backend validation:
  - `sequence_validation.py`
  - `event_validation.py`
  - `identifier_validation.py`
- Identifies specific EPCIS errors and violations

### 5. Action Plan Generation
- Analyzes validation errors
- Generates specific recommendations
- Creates professional email templates
- Includes both plain text and HTML formats

### 6. Email Communication
- Sends correction emails to vendors
- Includes detailed error explanations
- Provides specific fix recommendations
- Tracks email delivery status

### 7. Status Updates
- Marks emails as processed
- Applies Gmail labels
- Updates database records
- Logs all activities

## 📊 Monitoring & Logging

### Log Levels
- `DEBUG`: Detailed debugging information
- `INFO`: General operational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages

### Log Files
- Default: `logs/agent_YYYYMMDD.log`
- Rotating logs (10MB max, 5 backups)
- Separate console and file logging

### Status Monitoring
```bash
python main.py status
```

Provides:
- Agent connectivity status
- Gmail authentication status  
- Database connection status
- Configuration summary
- Processing statistics

## 🧪 Testing

### Unit Tests
```bash
pytest tests/
```

### Integration Tests
```bash
pytest tests/integration/
```

### Manual Testing
```bash
# Test single email processing
python main.py process-email --message-id test_message_id

# Test with debug logging
python main.py run --log-level DEBUG
```

## 🚨 Error Handling

The agent includes comprehensive error handling:

- **Email Processing Errors**: Skips invalid emails, continues processing
- **API Rate Limits**: Implements exponential backoff
- **Database Errors**: Graceful degradation with logging
- **Network Issues**: Retry logic with configurable timeouts
- **Validation Failures**: Detailed error reporting

## 🔒 Security

- **OAuth 2.0**: Secure Gmail authentication
- **Token Management**: Automatic token refresh
- **API Key Protection**: Environment variable storage
- **Database Security**: Parameterized queries
- **Email Privacy**: Secure email handling

## 🤝 Integration

### With Existing Backend
- Uses existing EPCIS validation code
- Connects to existing vendor scorecard database
- Integrates with current file drop system

### With External Services
- Gmail API for email operations
- OpenAI API for AI processing
- Database connections (SQLite/MySQL)

## 📈 Performance

- **Batch Processing**: Handles multiple emails efficiently
- **Async Operations**: Non-blocking I/O operations
- **Resource Management**: Proper connection pooling
- **Memory Efficiency**: Streaming for large emails

## 🛠️ Troubleshooting

### Common Issues

1. **Gmail Authentication Failed**
   ```bash
   python main.py setup-gmail
   ```

2. **Database Connection Error**
   - Check `DATABASE_URL` in `.env`
   - Verify database file exists
   - Check file permissions

3. **OpenAI API Errors**
   - Verify `OPENAI_API_KEY` in `.env`
   - Check API quota and billing
   - Monitor rate limits

4. **Email Processing Failures**
   - Check Gmail labels exist
   - Verify email permissions
   - Review log files for details

### Debug Mode
```bash
python main.py run --log-level DEBUG
```

### Log Analysis
```bash
tail -f logs/agent_$(date +%Y%m%d).log
```

## 📝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## 📄 License

This project is part of the Vendor Score Card system and follows the same licensing terms.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review log files
3. Check existing issues
4. Create a new issue with details

---

**EPCIS Error Correction Agent** - Automating vendor communication for EPCIS compliance