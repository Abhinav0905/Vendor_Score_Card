"""Setup script for the email agent package."""
from setuptools import setup, find_packages

setup(
    name="email_agent",
    version="0.1.0",
    description="AI Agent for Email Processing and EPCIS Validation",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "langchain>=0.1.20",
        "langchain-community>=0.0.38",
        "langchain-openai>=0.1.8",
        "langchain-google-genai>=1.0.6",
        "langgraph>=0.0.65",
        "langsmith>=0.1.77",
        "google-api-python-client==2.112.0",
        "google-auth-httplib2==0.2.0",
        "google-auth-oauthlib==1.2.2",
        "email-validator==2.1.0",
        "jinja2==3.1.2",
        "sqlalchemy>=2.0.23",
        "pymysql>=1.1.0",
        "pandas>=2.1.4",
        "pydantic>=2.5.2",
        "openai>=1.6.1",
        "tiktoken>=0.5.2",
        "python-dotenv>=1.0.0",
        "regex>=2023.12.25",
        "aiohttp==3.9.1",
        "uvloop==0.19.0",
        "rich==13.7.0",
        "pytest==7.4.3",
        "pytest-asyncio==0.21.1",
        "python-json-logger==2.0.7"
    ],
)
