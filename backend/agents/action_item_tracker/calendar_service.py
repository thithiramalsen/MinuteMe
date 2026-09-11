import os
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import dateparser
from lib.database import get_google_credentials, save_google_credentials

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service(user_id: str):
    """
    Builds a user-specific Google Calendar service object.
    It fetches credentials from the database for the given user_id.
    """
    creds_info = get_google_credentials(user_id)
    if not creds_info or "credentials" not in creds_info:
        print(f"No Google credentials found for user {user_id}")
        return None

    creds = Credentials.from_authorized_user_info(creds_info["credentials"], SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print(f"Refreshing expired token for user {user_id}")
            creds.refresh(Request())
            
            # --- THE CORRECT FIX: Pass the flat credentials dictionary directly ---
            # The save_google_credentials function in database.py handles nesting it.
            save_google_credentials(user_id, {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            })
        else:
            # This case should ideally trigger a re-authentication flow
            print(f"Credentials for user {user_id} are invalid and cannot be refreshed.")
            return None
            
    return build('calendar', 'v3', credentials=creds)

def schedule_action_item(user_id: str, task_name: str, description: str, deadline_str: str, owner: str, duration_minutes: int = 60):
    print(f"Scheduling Google Calendar event for user {user_id}: {task_name}")
    service = get_calendar_service(user_id)
    
    if not service:
        print(f"Cannot schedule event for user {user_id}, calendar service not available.")
        return None

    # Parse deadline_str as full datetime (date + time)
    deadline = dateparser.parse(deadline_str, settings={'PREFER_DATES_FROM': 'future'})
    if not deadline:
        deadline = datetime.now() + timedelta(days=2)
    # Do NOT override hour/minute here!
    start_time = deadline
    end_time = start_time + timedelta(minutes=duration_minutes)

    event = {
        'summary': f"{task_name} ({owner})",
        'description': description,
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Asia/Colombo'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Asia/Colombo'},
    }

    created_event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"Event created: {created_event.get('htmlLink')}")
    return created_event
