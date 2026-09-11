import os
from .ai_providers import gemini_provider
from .calendar_service import schedule_action_item
from .agenda_service import read_agenda
from .action_item_service import save_action_items
from ..agenda_planner.agenda_planner import generate_agenda
import nltk
from datetime import datetime, timedelta
import dateparser
# NEW: Import the function to get a specific minutes document
from lib.database import get_minutes_by_id, save_action_item, get_google_credentials
from .ai_providers.gemini_provider import extract_action_items

# The NLTK download logic has been moved to a central setup file (lib/nltk_setup.py)
# and is run at server startup, so this loop is no longer needed here.
# Temporary fix: Add download logic here to ensure resources are available.
for resource in ['punkt', 'averaged_perceptron_tagger', 'maxent_ne_chunker', 'words']:
    try:
        # A simple find call is sufficient, the path logic is complex.
        nltk.data.find(f'tokenizers/{resource}' if resource == 'punkt' else f'taggers/{resource}' if resource == 'averaged_perceptron_tagger' else f'chunkers/{resource}' if resource == 'maxent_ne_chunker' else f'corpora/{resource}')
    except LookupError:
        print(f"Downloading NLTK resource: {resource}")
        nltk.download(resource)


def run_action_item_tracker(meeting_text: str):
    # This function is kept as a fallback or for comparison
    return {
        "provider": "Gemini",
        "action_items": gemini_provider.extract_action_items(meeting_text)
    }

def extract_action_items_nlp(meeting_text: str):
    """
    Extracts action items using the Gemini API.
    """
    return {
        "provider": "Gemini",
        "action_items": extract_action_items(meeting_text),
    }

def extract_and_schedule_tasks(user_id: str, minutes_id: str, schedule=True):
    """
    Reads a specific minutes document, extracts action items, and schedules them.
    """
    print("\n--- 🚀 Starting Action Item Tracker ---")
    
    # Step 1: Fetch the minutes document
    print(f"[DEBUG] Fetching minutes document with ID: {minutes_id} for user: {user_id}")
    minutes_doc = get_minutes_by_id(minutes_id, user_id)
    if not minutes_doc:
        print(f"[ERROR] Minutes document not found. ID: {minutes_id}, User: {user_id}")
        return None

    # Step 2: Combine summary and decisions for context
    summary_text = minutes_doc.get("summary", "")
    decisions_text = " ".join(minutes_doc.get("decisions", []))
    meeting_text = f"{summary_text} {decisions_text}"
    print(f"[DEBUG] Combined meeting text for action item extraction. Length: {len(meeting_text)} characters.")

    # Step 3: Extract action items
    print("[DEBUG] Extracting action items...")
    result = extract_action_items_nlp(meeting_text)
    action_items = result.get("action_items", [])
    print(f"[DEBUG] Extracted {len(action_items)} action items.")

    # Step 4: Assign deadlines and durations to action items
    meeting_date = minutes_doc.get("date")
    next_meeting_date = minutes_doc.get("next_meeting_date")
    print(f"[DEBUG] Meeting date: {meeting_date}, Next meeting date: {next_meeting_date}")

    for idx, item in enumerate(action_items):
        # --- MODIFIED: Add robust fallback for deadline ---
        if not item.get("deadline"):
            # Use next meeting date, then meeting date, then default to 7 days from now
            fallback_date = next_meeting_date or meeting_date
            if fallback_date:
                item["deadline"] = fallback_date
            else:
                item["deadline"] = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            print(f"[DEBUG] No deadline from AI. Assigned fallback deadline: {item['deadline']}")
        
        item["duration"] = 60  # Default duration
        print(f"[DEBUG] Action item {idx + 1}: {item}")

    # Step 5: Schedule action items (if enabled)
    if schedule:
        # --- THE FIX: Check for credentials BEFORE trying to schedule ---
        print("[DEBUG] Checking for Google Calendar integration...")
        if not get_google_credentials(user_id):
            print("[WARN] Google Calendar not connected for this user. Skipping scheduling.")
        else:
            print("[DEBUG] Google Calendar connected. Proceeding with scheduling action items...")
            for idx, item in enumerate(action_items):
                task = item.get("task")
                owner = item.get("owner")
                deadline = item.get("deadline")
                duration = item.get("duration")
                print(f"[DEBUG] Scheduling task {idx + 1}: {task}, Owner: {owner}, Deadline: {deadline}, Duration: {duration} minutes")
                schedule_action_item(
                    user_id=user_id,
                    task_name=task,
                    description=f"Action item assigned to {owner}",
                    deadline_str=deadline,
                    owner=owner,
                    duration_minutes=duration
                )

    # Step 6: Save action items to the database
    print("[DEBUG] Saving action items to the database...")
    saved_items = []
    for item in action_items:
        saved_item = save_action_item(item, user_id, minutes_doc["_id"])
        saved_items.append(saved_item)
        print(f"[DEBUG] Saved action item: {saved_item.get('task')} with ID: {saved_item.get('_id')}")

    # Step 7: Generate the next agenda
    if minutes_doc.get("next_meeting_date"):
        print("[DEBUG] Generating next agenda...")
        next_meeting_input = {
            "topics": minutes_doc.get("future_discussion_points", ["Review previous action items"]),
            "discussion_points": [],
            "date": minutes_doc.get("next_meeting_date")
        }
        new_agenda = generate_agenda(next_meeting_input, user_id=user_id)
        print(f"[DEBUG] Next agenda generated with ID: {new_agenda.get('meeting_id')}")

    print("--- ✅ Action Item Tracker Completed ---")
    return result
