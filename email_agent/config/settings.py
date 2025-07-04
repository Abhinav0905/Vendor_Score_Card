"""Settings configuration for the Email Agent"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings"""
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # Gmail Configuration
    GMAIL_CREDENTIALS_PATH: str = os.getenv("GMAIL_CREDENTIALS_PATH", "config/gmail_credentials.json")
    GMAIL_TOKEN_PATH: str = os.getenv("GMAIL_TOKEN_PATH", "config/gmail_token.pickle")
    GMAIL_SCOPES: List[str] = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.modify'
    ]
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///vendor_scorecard.db")
    
    # Agent Configuration
    AGENT_NAME: str = "EPCIS Error Correction Agent"
    MAX_EMAILS_PER_RUN: int = int(os.getenv("MAX_EMAILS_PER_RUN", "20"))
    ERROR_EMAIL_LABEL: str = os.getenv("ERROR_EMAIL_LABEL", "epcis_errors")
    PROCESSED_EMAIL_LABEL: str = os.getenv("PROCESSED_EMAIL_LABEL", "epcis_processed")

    # File Paths
    EPCIS_FILES_PATH: str = os.getenv("EPCIS_FILES_PATH", "../../backend/epcis_drop")

    # Validation Settings
    VALIDATION_TIMEOUT: int = int(os.getenv("VALIDATION_TIMEOUT", "300"))

    # Email Content
    EMAIL_SENDER_NAME: str = os.getenv("EMAIL_SENDER_NAME", "EPCIS Validation System")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@example.com")
    EMAIL_REPLY_TO: str = os.getenv("EMAIL_REPLY_TO", "support@example.com")
    EMAIL_SIGNATURE: str = os.getenv("EMAIL_SIGNATURE", "Best regards,\nEPCIS Validation Team")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/agent.log")
    
    # class Config:
    #     env_file = ".env",
    #     env_file_encoding="utf-8",
    #     case_sensitive = True

    # Vendor Validation Settings
    REQUIRED_VENDOR_FIELDS: str = os.getenv("REQUIRED_VENDOR_FIELDS", "vendor_name,vendor_email,po_number")
    DEFAULT_VENDOR_NAME: str = os.getenv("DEFAULT_VENDOR_NAME", "Unknown Vendor")
    DEFAULT_VENDOR_EMAIL: str = os.getenv("DEFAULT_VENDOR_EMAIL", "rushtoabhinavin@gmail.com")
    VALID_VENDOR_DOMAINS: str = os.getenv("VALID_VENDOR_DOMAINS", "gmail.com")
    MIN_PO_LENGTH: int = int(os.getenv("MIN_PO_LENGTH", "1"))

    # Helper properties for vendor validation
    @property
    def required_vendor_fields_list(self) -> List[str]:
        """Convert comma-separated string to list"""
        return [field.strip() for field in self.REQUIRED_VENDOR_FIELDS.split(',')]

    @property
    def valid_vendor_domains_list(self) -> List[str]:
        """Convert comma-separated string to list"""
        return [domain.strip() for domain in self.VALID_VENDOR_DOMAINS.split(',')]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

# Create settings instance
settings = Settings()
