import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure # Import the exception class
from bson.objectid import ObjectId # Import the ObjectId class
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()  # Load environment variables from .env file

# --- Singleton Pattern for DB Connection ---
_db_client = None

def get_db():
    """
    Establishes a singleton connection to the MongoDB database.
    Reads MONGO_URI and MONGO_DB from the .env file.
    """
    global _db_client
    if _db_client is None:
        load_dotenv()
        mongo_uri = os.getenv("MONGO_URI")
        mongo_db_name = os.getenv("MONGO_DB")
        if not mongo_uri or not mongo_db_name:
            raise ValueError("MONGO_URI and MONGO_DB must be set in your .env file.")
        
        try:
            print("🔌 Establishing new MongoDB connection...")
            # Add these connection options to bypass some common connection issues
            client = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=10000,
                socketTimeoutMS=10000,
                retryWrites=True
            )
            # The ismaster command is cheap and does not require auth.
            client.admin.command('ping')  # Use ping instead of ismaster
            _db_client = client[mongo_db_name]
            print("✅ MongoDB connection successful.")
        except ConnectionFailure as e:
            print(f"❌ MongoDB connection failed: {e}")
            raise
    return _db_client

# --- CRUD Functions for Agents ---

def save_agenda(agenda_data: dict, user_id: str):
    """Saves an agenda document for a specific user."""
    db = get_db()
    agenda_data["user_id"] = user_id
    agenda_data["created_at"] = datetime.utcnow()
    result = db.agendas.insert_one(agenda_data)
    
    # After inserting, the agenda_data dict contains the non-serializable ObjectId.
    # We need to convert it to a string before returning.
    if "_id" in agenda_data:
        agenda_data["_id"] = str(agenda_data["_id"])
        
    return agenda_data

def save_minutes(minutes_data: dict, user_id: str):
    """Saves a meeting minutes document for a specific user."""
    db = get_db()
    minutes_data["user_id"] = user_id
    minutes_data["created_at"] = datetime.utcnow()
    result = db.minutes.insert_one(minutes_data)
    return str(result.inserted_id)

def update_minutes_with_action_items(minutes_id: str, action_items: list):
    """Finds a minutes document by its ID and adds the action items to it."""
    db = get_db()
    # Use ObjectId to correctly query the document by its primary key
    result = db.minutes.update_one(
        {"_id": ObjectId(minutes_id)},
        {"$set": {"action_items": action_items, "updated_at": datetime.utcnow()}}
    )
    print(f"📝 Updated minutes {minutes_id} with {len(action_items)} action items. Matched: {result.matched_count}")
    return result.modified_count

def get_latest_minutes(user_id: str):
    """Retrieves the most recent meeting minutes for a given user."""
    db = get_db()
    latest_minutes = db.minutes.find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)] # -1 for descending
    )
    if latest_minutes and "_id" in latest_minutes:
        latest_minutes["_id"] = str(latest_minutes["_id"])
    return latest_minutes

def get_minutes_by_id(minutes_id: str, user_id: str):
    """Retrieves a specific minutes document by its ID for a given user."""
    db = get_db()
    try:
        minutes_doc = db.minutes.find_one({"_id": ObjectId(minutes_id), "user_id": user_id})
        if minutes_doc and "_id" in minutes_doc:
            minutes_doc["_id"] = str(minutes_doc["_id"])
        return minutes_doc
    except Exception as e:
        print(f"Error fetching minutes by ID '{minutes_id}': {e}")
        return None

def get_agenda(meeting_id: str, user_id: str):
    """Retrieves a specific agenda for a given user."""
    db = get_db()
    agenda = db.agendas.find_one({"meeting_id": meeting_id, "user_id": user_id})
    if agenda and "_id" in agenda:
        agenda["_id"] = str(agenda["_id"])
    return agenda

def save_transcript(transcript_text: str, user_id: str, meeting_id: str, meeting_name: str, meeting_date: str, automated: bool = False):
    """Saves a raw transcript for a specific user."""
    db = get_db()
    transcript_data = {
        "user_id": user_id,
        "transcript": transcript_text,
        "created_at": datetime.utcnow(),
        "meeting_id": meeting_id,
        "meeting_name": meeting_name,
        "meeting_date": meeting_date,
        "automated": automated
    }
    result = db.transcripts.insert_one(transcript_data)
    return str(result.inserted_id)

def get_latest_transcript(user_id: str):
    """Retrieves the most recent transcript for a given user."""
    db = get_db()
    latest_transcript = db.transcripts.find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    )
    if latest_transcript and "_id" in latest_transcript:
        latest_transcript["_id"] = str(latest_transcript["_id"])
    return latest_transcript

def get_all_agendas_for_user(user_id: str):
    """Retrieves all agendas for a given user, sorted by most recent."""
    db = get_db()
    agendas = list(db.agendas.find({"user_id": user_id}, sort=[("created_at", -1)]))
    for agenda in agendas:
        if "_id" in agenda:
            agenda["_id"] = str(agenda["_id"])
    return agendas

def save_action_item(action_item: dict, user_id: str, minutes_id: str):
    db = get_db()
    action_item["user_id"] = user_id
    action_item["minutes_id"] = minutes_id
    action_item["created_at"] = datetime.utcnow()
    result = db.action_items.insert_one(action_item)
    action_item["_id"] = str(result.inserted_id)
    return action_item

def get_all_action_items_for_user(user_id: str):
    db = get_db()
    action_items = list(db.action_items.find({"user_id": user_id}))
    for item in action_items:
        if "_id" in item:
            item["_id"] = str(item["_id"])
    return action_items

def get_all_minutes_for_user(user_id: str):
    """Retrieves all minutes documents for a given user."""
    db = get_db()
    minutes_docs = list(db.minutes.find({"user_id": user_id}))
    for doc in minutes_docs:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
    return minutes_docs

def get_document_count(collection_name: str, user_id: str):
    """Counts documents in a collection for a specific user."""
    db = get_db()
    return db[collection_name].count_documents({"user_id": user_id})

def update_agenda(agenda_id: str, update_data: dict, user_id: str):
    db = get_db()
    print(f"🔎 update_agenda called with agenda_id={agenda_id}, user_id={user_id}")
    result = db.agendas.update_one(
        {"meeting_id": agenda_id, "user_id": user_id},
        {"$set": update_data}
    )
    print(f"Matched count: {result.matched_count}, Modified count: {result.modified_count}")
    if result.modified_count == 0:
        print("❌ No agenda updated. Check meeting_id and user_id.")
        return None
    agenda = db.agendas.find_one({"meeting_id": agenda_id, "user_id": user_id})
    if agenda and "_id" in agenda:
        agenda["_id"] = str(agenda["_id"])
    return agenda

def save_meeting(meeting_data: dict, user_id: str):
    db = get_db()
    meeting_data["user_id"] = user_id
    meeting_data["created_at"] = datetime.utcnow()
    result = db.meetings.insert_one(meeting_data)
    meeting_data["_id"] = str(result.inserted_id)
    return meeting_data

def get_all_meetings_for_user(user_id: str):
    db = get_db()
    meetings = list(db.meetings.find({"user_id": user_id}))
    for meeting in meetings:
        if "_id" in meeting:
            meeting["_id"] = str(meeting["_id"])
    return meetings

def update_meeting(meeting_id: str, update_data: dict, user_id: str):
    db = get_db()
    result = db.meetings.update_one(
        {"_id": ObjectId(meeting_id), "user_id": user_id},
        {"$set": update_data}
    )
    if result.modified_count == 0:
        return None
    meeting = db.meetings.find_one({"_id": ObjectId(meeting_id), "user_id": user_id})
    if meeting and "_id" in meeting:
        meeting["_id"] = str(meeting["_id"])
    return meeting

def delete_meeting(meeting_id: str, user_id: str):
    db = get_db()
    result = db.meetings.delete_one({"_id": ObjectId(meeting_id), "user_id": user_id})
    return result.deleted_count

def delete_transcript(transcript_id: str, user_id: str):
    """Deletes a transcript document for a specific user."""
    db = get_db()
    result = db.transcripts.delete_one({"_id": ObjectId(transcript_id), "user_id": user_id})
    return result.deleted_count

# --- Google OAuth Credential Storage ---

def save_google_credentials(user_id: str, credentials_info: dict):
    """Saves or updates a user's Google credentials."""
    db = get_db()
    db.google_credentials.update_one(
        {"user_id": user_id},
        {"$set": {"credentials": credentials_info, "updated_at": datetime.utcnow()}},
        upsert=True
    )
    print(f"Saved Google credentials for user {user_id}")

def get_google_credentials(user_id: str):
    """Retrieves a user's Google credentials."""
    db = get_db()
    return db.google_credentials.find_one({"user_id": user_id})

def delete_google_credentials(user_id: str):
    """Deletes a user's Google credentials."""
    db = get_db()
    result = db.google_credentials.delete_one({"user_id": user_id})
    print(f"Deleted Google credentials for user {user_id}")
    return result.deleted_count