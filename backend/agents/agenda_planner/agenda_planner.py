import os
import google.generativeai as genai
from .utils import (
    get_next_meeting_id,
    extract_keywords_rake,
    get_user_input_if_no_previous_file,
)
from lib.database import save_agenda
from datetime import datetime

# --- Gemini setup ---
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash-exp")


def assign_priority(topic):
    """
    Assign priority using Gemini.
    """
    prompt = f"""Classify the following meeting topic as one of: "urgent", "discussion", or "info".
Topic: "{topic}"
Respond with only the label."""
    try:
        response = model.generate_content(prompt)
        label = response.text.strip().lower()
        if "urgent" in label:
            return "urgent"
        elif "discussion" in label:
            return "discussion"
        else:
            return "info"
    except Exception as e:
        print(f"Gemini priority classification failed: {e}")
        return "info"

def allocate_time(priority):
    """Allocate time based on priority"""
    if priority == "urgent":
        return "20 mins"
    elif priority == "discussion":
        return "15 mins"
    return "10 mins"

def generate_meeting_name_ai(text):
    """
    Generates a concise meeting name using Gemini.
    """
    if not text or len(text.strip()) < 20:
        return "General Meeting"
    prompt = f"""Generate a short, descriptive meeting name (3-10 words) for the following topics:
{text}
Respond with only the meeting name."""
    try:
        response = model.generate_content(prompt)
        title = response.text.strip().replace('"', '')
        return title.title()
    except Exception as e:
        print(f"Gemini meeting name generation failed: {e}")
        return "General Meeting"

def generate_agenda(user_input=None, user_id="user_placeholder_123"):
    """
    Generate structured agenda JSON.
    """
    print("\n--- 🚀 Starting Agenda Planner ---")

    if user_input is None:
        print("🧠 No input provided. Checking DB for previous meeting minutes.")
        user_input = get_user_input_if_no_previous_file(user_id)
    else:
        print("🧠 Using provided input to generate new agenda.")

    # 1️⃣ Create meeting ID
    meeting_id = get_next_meeting_id(user_id)

    # 2️⃣ Combine all topics for agenda items
    all_topics = user_input.get("topics", []) + user_input.get("discussion_points", [])

    # 3️⃣ Generate agenda items
    agenda_items = []
    for topic in all_topics:
        short_topics = extract_keywords_rake(topic, top_n=1) or [topic]
        short_topic = short_topics[0].title()
        priority = assign_priority(topic)
        time_alloc = allocate_time(priority)

        agenda_items.append({
            "topic": short_topic,
            "priority": priority,
            "time_allocated": time_alloc
        })

    # 4️⃣ Generate meeting name using Gemini
    title_source_text = ". ".join(user_input.get("topics", []))
    if not title_source_text.strip():
        title_source_text = ". ".join(user_input.get("discussion_points", []))

    meeting_name = generate_meeting_name_ai(title_source_text)

    # 5️⃣ Build final agenda JSON
    agenda_json = {
        "meeting_id": meeting_id,
        "meeting_name": meeting_name,
        "meeting_date": user_input.get("date") or str(datetime.today().date()),
        "agenda": agenda_items
    }

    # 6️⃣ Save to MongoDB
    saved_agenda = save_agenda(agenda_json, user_id)
    print(f"✅ Agenda '{meeting_id}' saved to MongoDB for user '{user_id}'.")
    print("--- ✨ Finished Agenda Planner ---\n")

    return saved_agenda

if __name__ == "__main__":
    mock_input = {
        "topics": [
            "The production server is down and needs immediate attention.",
            "Reviewing the financial projections for the next quarter.",
            "Let's go over the designs for the new user dashboard."
        ],
        "discussion_points": ["Quick update on the team's holiday leave schedule."]
    }
    agenda = generate_agenda(user_input=mock_input)
    import json
    print("✅ Agenda created:")
    print(json.dumps(agenda, indent=4))