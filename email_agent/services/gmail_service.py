import os
import base64
import pickle
import logging
import asyncio
from typing import List, Dict, Any, Optional
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from email_agent.config import settings

logger = logging.getLogger(__name__)

class GmailService:
    """Gmail API service for reading and sending emails"""
    
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 
              'https://www.googleapis.com/auth/gmail.modify']
    PORT = 8080  # Fixed port for OAuth redirect
    
    def __init__(self, settings):
        self.settings = settings
        self.service = None
        self._authenticate()
    
    # Keep the synchronous version of authentication
    def _authenticate(self):
        try:
            current_dir = Path(__file__).resolve().parent
            credentials_path = current_dir.parent / 'config' / 'gmail_credentials.json'
            token_path = current_dir.parent / 'config' / 'token.pickle'

            logger.info("Starting Gmail authentication process...")
            logger.info("To use this application in development:")
            logger.info("1. Go to Google Cloud Console > APIs & Services > OAuth consent screen")
            logger.info("2. Add your email as a test user")
            logger.info("3. Wait a few minutes for changes to propagate")
            
            if not credentials_path.exists():
                raise FileNotFoundError(f"Credentials file not found at {credentials_path}")

            creds = None
            if token_path.exists():
                logger.info("Found existing token, attempting to load...")
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Token expired, refreshing...")
                    creds.refresh(Request())
                else:
                    logger.info("Starting new OAuth flow...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(credentials_path), 
                        self.SCOPES,
                    )
                    creds = flow.run_local_server(
                        port=self.PORT,
                        success_message="Authentication successful! You may close this window.",
                    )
                    logger.info("OAuth flow completed successfully")
                
                logger.info(f"Saving token to: {token_path}")
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)

            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Gmail authentication completed successfully")

        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            if "access_denied" in str(e):
                logger.error("Access denied. Make sure you've added your email as a test user in Google Cloud Console")
            raise
    
    async def get_emails_by_label(self, label: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Get emails by label asynchronously"""
        try:
            # Run Gmail API calls in a thread pool since they're blocking
            def _get_emails():
                # Get label ID
                labels_response = self.service.users().labels().list(userId='me').execute()
                labels = labels_response.get('labels', [])
                
                # Log all found labels for debugging
                found_labels = [lbl['name'] for lbl in labels]
                logger.info(f"Found the following labels in the account: {found_labels}")

                label_id = None
                for lbl in labels:
                    if lbl['name'].lower() == label.lower():
                        label_id = lbl['id']
                        break
                
                if not label_id:
                    logger.warning(f"The specific label '{label}' was not found in the account.")
                    return []
                
                # Get messages
                result = self.service.users().messages().list(
                    userId='me',
                    labelIds=[label_id],
                    maxResults=max_results
                ).execute()
                
                messages = []
                for msg in result.get('messages', []):
                    message_detail = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()
                    messages.append(message_detail)
                
                logger.info(f"Retrieved {len(messages)} emails with label '{label}'")
                return messages
            
            # Run the blocking function in a thread pool
            messages = await asyncio.to_thread(_get_emails)
            return messages
            
        except Exception as e:
            logger.error(f"Error retrieving emails: {str(e)}")
            return []
    
    async def extract_email_content(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Extract content from Gmail message asynchronously"""
        try:
            if not message or 'payload' not in message or not message['payload']:
                logger.error("Invalid message format: missing payload")
                return {'message_id': message.get('id', 'unknown') if message else 'unknown', 'error': 'Invalid message format'}
            
            payload = message['payload']
            headers = payload['headers']
            
            # Extract headers (case-insensitive)
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
            
            # Extract body
            body = await self._extract_body(payload)
            
            # Extract attachment names
            attachments = []
            if 'parts' in payload:
                for part in payload['parts']:
                    if part.get('filename'):
                        attachments.append(part['filename'])
            
            return {
                'message_id': message['id'],
                'subject': subject,
                'sender': sender,
                'body': body,
                'received_date': date,
                'attachments': attachments
            }
            
        except Exception as e:
            logger.error(f"Error extracting email content for message {message.get('id', 'unknown')}: {str(e)}")
            return {'message_id': message.get('id', 'unknown') if message else 'unknown', 'error': str(e)}
    
    async def _extract_body(self, payload: Dict[str, Any]) -> str:
        """Extract email body from payload asynchronously"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                    body_data = part['body']['data']
                    body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    break
                elif part['mimeType'] == 'text/html' and 'data' in part['body'] and not body:
                    body_data = part['body']['data']
                    body = base64.urlsafe_b64decode(body_data).decode('utf-8')
        elif 'body' in payload and 'data' in payload['body']:
            body_data = payload['body']['data']
            body = base64.urlsafe_b64decode(body_data).decode('utf-8')
        
        return body
    
    async def send_email(self, to: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
        """Send email asynchronously"""
        try:
            def _send():
                message = MIMEMultipart('alternative')
                message['to'] = to
                message['subject'] = subject
                message['from'] = self.settings.EMAIL_FROM
                
                # Add text body
                message.attach(MIMEText(body, 'plain'))
                
                # Add HTML body if provided
                if html_body:
                    message.attach(MIMEText(html_body, 'html'))
                
                raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
                
                self.service.users().messages().send(
                    userId='me',
                    body={'raw': raw_message}
                ).execute()
                
                return True
            
            result = await asyncio.to_thread(_send)
            logger.info(f"Email sent successfully to {to}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    # async def mark_email_processed(self, message_id: str) -> bool:
    #     """Mark email as processed asynchronously"""
    #     try:
    #         def _mark():
    #             # Add processed label and remove error label
    #             self.service.users().messages().modify(
    #                 userId='me',
    #                 id=message_id,
    #                 body={
    #                     'addLabelIds': [self.settings.PROCESSED_EMAIL_LABEL],
    #                     'removeLabelIds': [self.settings.ERROR_EMAIL_LABEL]
    #                 }
    #             ).execute()
    #             return True
            
    #         result = await asyncio.to_thread(_mark)
    #         logger.info(f"Email {message_id} marked as processed")
    #         return result
            
    #     except Exception as e:
    #         logger.error(f"Error marking email as processed: {str(e)}")
    #         return False

    async def mark_email_processed(self, message_id: str) -> bool:
        """Mark email as processed asynchronously"""
        try:
            def _mark():
                # Get all labels first
                labels_response = self.service.users().labels().list(userId='me').execute()
                labels = labels_response.get('labels', [])
                
                # Find label IDs case-insensitively
                processed_label_id = next((lbl['id'] for lbl in labels 
                    if lbl['name'].lower() == self.settings.PROCESSED_EMAIL_LABEL.lower()), None)
                error_label_id = next((lbl['id'] for lbl in labels 
                    if lbl['name'].lower() == self.settings.ERROR_EMAIL_LABEL.lower()), None)
                
                if not processed_label_id or not error_label_id:
                    logger.error("Could not find required labels")
                    return False

                # Add processed label and remove error label
                self.service.users().messages().modify(
                    userId='me',
                    id=message_id,
                    body={
                        'addLabelIds': [processed_label_id],
                        'removeLabelIds': [error_label_id]
                    }
                ).execute()
                return True
            
            result = await asyncio.to_thread(_mark)
            logger.info(f"Email {message_id} marked as processed")
            return result
            
        except Exception as e:
            logger.error(f"Error marking email as processed: {str(e)}")
            return False
    
    async def is_authenticated(self):
        """Check if the service is authenticated and ready to use asynchronously."""
        try:
            def _check():
                # Test the connection by making a simple API call
                self.service.users().getProfile(userId='me').execute()
                return True
                
            result = await asyncio.to_thread(_check)
            return result
        except Exception as e:
            logger.error(f"Gmail authentication check failed: {str(e)}")
            return False

    async def get_error_emails(self, max_results: int) -> List[Dict[str, Any]]:
        """Fetches emails with the error label asynchronously."""
        error_label = self.settings.ERROR_EMAIL_LABEL
        logger.info(f"Fetching up to {max_results} emails with label '{error_label}'")
        return await self.get_emails_by_label(error_label, max_results=max_results)

    def get_error_message(self):
        """Return any error message if authentication failed."""
        if not hasattr(self, 'service'):
            return "Gmail service not initialized"
        return None