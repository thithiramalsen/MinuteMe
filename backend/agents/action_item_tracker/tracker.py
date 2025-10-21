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
from lib.database import get_minutes_by_id, save_action_item

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
    Extracts action items using NLTK with POS tagging and NER for better accuracy.
    This is a more robust replacement for the spaCy implementation.
    """
    action_items = []
    sentences = nltk.sent_tokenize(meeting_text)

    for sent in sentences:
        words = nltk.word_tokenize(sent)
        tagged_words = nltk.pos_tag(words)
        
        # Use NLTK's Named Entity Recognition to find people
        tree = nltk.ne_chunk(tagged_words)
        owners = []
        for subtree in tree.subtrees(filter=lambda t: t.label() == 'PERSON'):
            owners.append(" ".join([word for word, tag in subtree.leaves()]))

        # Keywords indicating a task is being assigned
        action_keywords = ["will", "needs to", "to-do", "action item", "task for", "responsible for"]
        
        # Check if the sentence likely contains an action item
        if any(keyword in sent.lower() for keyword in action_keywords) or owners:
            # A simple rule: if a person is mentioned, the whole sentence is the task.
            # A more complex parser could be built here to find the specific verb phrase.
            task_description = sent.strip()
            
            # If we found a person, assign them as the owner.
            task_owner = owners[0] if owners else "Unassigned"

            # Avoid adding duplicate or very short/generic sentences
            if len(task_description.split()) > 4:
                action_items.append({
                    "owner": task_owner,
                    "task": task_description,
                    "deadline": None # Deadline extraction can be a separate, complex task
                })

    return {"provider": "NLP (NLTK)", "action_items": action_items}

def extract_and_schedule_tasks(user_id: str, minutes_id: str, schedule=True):
    """
    Reads a specific minutes document, extracts action items, and schedules them.
    """
    print("\n--- 🚀 Starting Action Item Tracker ---")
    
    # MODIFIED: Read a specific minutes document instead of the latest one
    minutes_doc = get_minutes_by_id(minutes_id, user_id)
    if not minutes_doc:
        print(f"❌ Could not find minutes with ID '{minutes_id}' for user '{user_id}'. Aborting.")
        return None

    # Use the summary from the specific minutes document as the text to process
    meeting_text = minutes_doc.get("summary", "")
    # --- MODIFIED: Use Gemini provider for action item extraction ---
    result = run_action_item_tracker(meeting_text)
    print(f"🔍 Found {len(result.get('action_items', []))} potential action items using {result.get('provider')}.")

    meeting_date = minutes_doc.get("date")
    next_meeting_date = minutes_doc.get("next_meeting_date")

    agenda_items = []
    if minutes_id:
        # Pass the user_id to correctly fetch the agenda for the authenticated user
        agenda = read_agenda(minutes_id, user_id)
        if agenda:
            agenda_items = agenda.get("agenda", [])

    # Assign durations to action items (for reference, not for scheduling)
    for idx, item in enumerate(result['action_items']):
        if idx < len(agenda_items):
            time_alloc = agenda_items[idx].get("time_allocated", "60 mins")
            try:
                duration = int(time_alloc.split()[0])
            except Exception:
                duration = 60
        else:
            duration = 60
        item["duration"] = duration
        if not item.get("deadline"):
            if next_meeting_date:
                item["deadline"] = next_meeting_date
            elif meeting_date:
                item["deadline"] = meeting_date

    if schedule:
        # 1️⃣ Schedule agenda topics sequentially on next_meeting_date
        if next_meeting_date:
            base_dt = dateparser.parse(next_meeting_date)
            if not base_dt:
                base_dt = datetime.now()
            current_start = base_dt.replace(hour=9, minute=0, second=0, microsecond=0)
            for idx, agenda_item in enumerate(agenda_items):
                topic = agenda_item.get("topic", f"Agenda Item {idx+1}")
                time_alloc = agenda_item.get("time_allocated", "60 mins")
                try:
                    duration = int(time_alloc.split()[0])
                except Exception:
                    duration = 60
                schedule_action_item(
                    user_id=user_id, # Pass user_id
                    task_name=topic,
                    description=f"Agenda topic: {topic}",
                    deadline_str=current_start.strftime("%Y-%m-%d %H:%M"),
                    owner="All",
                    duration_minutes=duration
                )
                current_start += timedelta(minutes=duration)
        # 2️⃣ Schedule each action item as a separate event on its deadline, staggered if same day
        from collections import defaultdict
        deadline_groups = defaultdict(list)
        for item in result['action_items']:
            deadline_groups[item['deadline']].append(item)
        for deadline, items in deadline_groups.items():
            base_dt = dateparser.parse(deadline)
            if not base_dt:
                base_dt = datetime.now()
            current_start = base_dt.replace(hour=9, minute=0, second=0, microsecond=0)
            for item in items:
                task = item.get('task')
                owner = item.get('owner')
                description = f"Action item assigned to {owner}"
                item_duration = item.get("duration", 60)
                
                # --- MODIFIED: Capture the created event ---
                created_event = schedule_action_item(
                    user_id=user_id, # Pass user_id
                    task_name=task,
                    description=description,
                    deadline_str=current_start.strftime("%Y-%m-%d %H:%M"),
                    owner=owner,
                    duration_minutes=item_duration
                )
                
                # --- MODIFIED: Store the Google Event ID if it exists ---
                if created_event and 'id' in created_event:
                    item['google_event_id'] = created_event['id']

                current_start += timedelta(minutes=item_duration)
    
    # Save action items as separate documents and collect them
    saved_items = []
    if minutes_doc and minutes_doc.get("_id"):
        for item in result['action_items']:
            saved_item = save_action_item(item, user_id, minutes_doc["_id"])
            saved_items.append(saved_item)
    
    # Replace the original list with the saved items (which include IDs)
    result['action_items'] = saved_items

    # --- NEW: Close the loop by generating the next agenda ---
    if minutes_doc and minutes_doc.get("next_meeting_date"):
        print("\n--- 🔄 Closing the Loop: Generating Next Agenda ---")
        next_meeting_input = {
            "topics": minutes_doc.get("future_discussion_points", ["Review previous action items"]),
            "discussion_points": [],  # <-- Only future topics, no action items
            "date": minutes_doc.get("next_meeting_date")
        }
        print(f"🗓️  Input for next agenda on date: {next_meeting_input['date']}")
        # Call the agenda planner to create the next agenda file
        new_agenda = generate_agenda(next_meeting_input, user_id=user_id)
        print(f"Successfully generated next agenda: {new_agenda.get('meeting_id')}")

    return result
