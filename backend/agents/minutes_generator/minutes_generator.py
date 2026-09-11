import os
import json
import nltk
from transformers import pipeline
from lib.database import save_minutes, get_latest_transcript
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from agents.action_item_tracker.ai_providers.gemini_provider import (
    generate_summary_gemini,
    extract_key_decisions_gemini,
    extract_future_topics_gemini,
)

# Ensure NLTK sentence tokenizer is downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

def load_transcript_from_db(user_id: str, transcript_id: str = None) -> str:
    """Loads a transcript text for a user from MongoDB. If transcript_id is provided, loads that specific transcript."""
    print(f"📖 Loading transcript from DB for user: {user_id}")
    from lib.database import get_latest_transcript, get_db
    db = get_db()
    if transcript_id:
        transcript_doc = db.transcripts.find_one({"_id": ObjectId(transcript_id), "user_id": user_id})
    else:
        transcript_doc = get_latest_transcript(user_id)
    if transcript_doc:
        return transcript_doc.get("transcript", "")
    print("⚠️ No transcript found in DB.")
    return ""

def generate_summary(text: str) -> str:
    """Generates a summary using the Gemini API."""
    return generate_summary_gemini(text)

def extract_key_decisions(text: str) -> list:
    """Extracts key decisions using the Gemini API."""
    return extract_key_decisions_gemini(text)

def extract_future_topics(text: str) -> list:
    """Extracts future topics using the Gemini API."""
    return extract_future_topics_gemini(text)

def generate_minutes(user_id: str = "user_placeholder_123", transcript_id: str = None, transcript_text: str = None):
    """Main function to generate and save meeting minutes to MongoDB."""
    print("\n--- 🚀 Starting Minutes Generator ---")
    
    # Step 1: Load transcript
    print(f"[DEBUG] Loading transcript for user: {user_id}")
    transcript = transcript_text or load_transcript_from_db(user_id, transcript_id)
    if not transcript:
        print("[ERROR] No transcript content found. Aborting minutes generation.")
        return

    print(f"[DEBUG] Transcript loaded. Length: {len(transcript)} characters.")

    # Step 2: Generate summary
    print("[DEBUG] Generating summary...")
    summary = generate_summary(transcript)
    print(f"[DEBUG] Summary generated. Length: {len(summary)} characters.")

    # Step 3: Extract key decisions
    print("[DEBUG] Extracting key decisions...")
    decisions = extract_key_decisions(transcript)
    print(f"[DEBUG] Extracted {len(decisions)} decisions. Data: {decisions}")

    # Step 4: Extract future topics
    print("[DEBUG] Extracting future discussion topics...")
    future_topics = extract_future_topics(transcript)
    print(f"[DEBUG] Extracted {len(future_topics)} future topics. Data: {future_topics}")

    # Step 5: Structure and save minutes
    print("[DEBUG] Structuring minutes data...")
    output_data = {
        "meeting_id": f"minutes_{user_id}_{datetime.now().strftime('%Y%m%d')}",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "next_meeting_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        "summary": summary,
        "decisions": decisions,
        "future_discussion_points": future_topics,
        "action_items": []
    }
    print("[DEBUG] Saving minutes to the database...")
    inserted_id = save_minutes(output_data, user_id)
    output_data['_id'] = inserted_id
    print(f"[DEBUG] Minutes saved with ID: {inserted_id}")

    print(f"[DEBUG] Final minutes data being returned: {output_data}")
    print("--- ✅ Minutes Generator Completed ---")
    return output_data

if __name__ == '__main__':
    # This allows you to run the script directly to generate minutes
    # from the latest transcript in the DB.
    generate_minutes()