from fastapi import FastAPI, Body, Depends, HTTPException, BackgroundTasks # Import BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from agents.agenda_planner.agenda_planner import generate_agenda
from agents.minutes_generator.minutes_generator import generate_minutes
from agents.action_item_tracker.tracker import extract_and_schedule_tasks
from agents.transcription_agent.transcription_agent import transcribe_video, get_video_length
from agents.action_item_tracker.calendar_service import schedule_action_item, SCOPES
import dateparser
from bson import ObjectId
from datetime import datetime
import os
from lib.auth import get_current_user
from lib.database import (
    get_db,
    get_all_agendas_for_user,
    get_all_action_items_for_user,
    get_agenda,
    get_all_minutes_for_user,
    get_minutes_by_id,
    update_agenda,
    save_meeting,
    get_all_meetings_for_user,
    update_meeting,
    delete_meeting,
    save_transcript,
    delete_transcript, # <-- Import delete_transcript
    save_google_credentials,
    get_google_credentials,
    delete_google_credentials
)
from lib.notifications import (
    get_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    create_notification,
    update_notification_email_status,
    send_email_notification,
    AutomationNotifier # Import the new notifier class
)
from lib.quota import (
    get_monthly_meeting_count,
    get_monthly_automation_cycles,
    increment_automation_cycle,
    check_free_tier_limits,
    get_monthly_transcription_count,
)
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from clerk_backend_api import Clerk 
# --- ADD THIS IMPORT FOR DETAILED ERROR LOGGING ---
import traceback

app = FastAPI()

# Allow frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your frontend's domain
    allow_credentials=True,
    # --- FIX: Explicitly list the allowed methods ---
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# +++ AUTOMATION FLOW +++
def run_full_automation_flow(user_id: str, meeting_id: str, video_url: str = None, transcript_text: str = None):
    """
    This function runs in the background. It orchestrates the entire agent chain.
    """
    notifier = AutomationNotifier(user_id, meeting_id)
    try:
        print(f"🤖 [Auto-Flow] Starting for user {user_id}, meeting {meeting_id}")
        notifier.start()

        # --- Step 1: Transcription (if needed) ---
        if video_url:
            notifier.step_transcribe()
            print(f"🤖 [Auto-Flow] Step 1: Transcribing video...")
            transcript_text = transcribe_video(video_url=video_url, user_id=user_id)
            if not transcript_text:
                raise ValueError("Transcription failed to produce text.")
            save_transcript(transcript_text, user_id, meeting_id, f"Meeting {meeting_id}", str(datetime.utcnow().date()), automated=True)
            print(f"🤖 [Auto-Flow] Step 1 Complete: Transcription saved.")

        # --- Step 2: Generate Minutes ---
        notifier.step_minutes()
        print(f"🤖 [Auto-Flow] Step 2: Generating minutes...")
        minutes_data = generate_minutes(user_id=user_id, transcript_text=transcript_text)
        if not minutes_data or not minutes_data.get("_id"):
            raise ValueError("Minutes generation failed.")
        minutes_id = minutes_data["_id"]
        print(f"🤖 [Auto-Flow] Step 2 Complete: Minutes generated with ID {minutes_id}.")

        # --- Step 3: Generate Action Items ---
        notifier.step_actions()
        print(f"🤖 [Auto-Flow] Step 3: Extracting action items...")
        extract_and_schedule_tasks(user_id=user_id, minutes_id=minutes_id)
        print(f"🤖 [Auto-Flow] Step 3 Complete: Action items extracted and scheduled.")

        # --- Final Step: Increment Quota & Notify ---
        increment_automation_cycle(meeting_id, user_id)
        
        # --- NEW: Prompt for Google Calendar Integration ---
        db = get_db()
        user_info = db.users.find_one({"user_id": user_id})
        if user_info and user_info.get("tier") == "premium":
            if not get_google_credentials(user_id):
                create_notification(
                    user_id=user_id,
                    title="Enhance Your Workflow",
                    message="Connect your Google Calendar to automatically schedule action items.",
                    type="prompt_google_calendar_integration"
                )
                print(f"🤖 [Auto-Flow] Sent Google Calendar integration prompt to premium user {user_id}.")

        notifier.success()
        print(f"🤖 [Auto-Flow] Success for user {user_id}, meeting {meeting_id}")

    except Exception as e:
        error_reason = str(e)
        print(f"🤖❌ [Auto-Flow] FAILED for user {user_id}, meeting {meeting_id}. Reason: {error_reason}")
        notifier.error(error_reason)

@app.post("/process-automated")
async def process_automated_endpoint(
    background_tasks: BackgroundTasks,
    request_body: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Triggers the full, end-to-end automated processing for a meeting.
    Accepts either a video_url or transcript_text.
    """
    user_id = current_user.get("sub")
    tier = current_user.get("metadata", {}).get("tier", "free")
    
    # --- Quota Check for Free Users ---
    if tier == "free":
        exceeded, quota_info = check_free_tier_limits(user_id, "automation")
        if exceeded:
            raise HTTPException(
                status_code=403,
                detail=f"You have used all {quota_info['limit']} of your automation cycles for this month. Upgrade to Premium for unlimited automations."
            )

    video_url = request_body.get("video_url")
    transcript_text = request_body.get("transcript_text")
    meeting_id = request_body.get("meeting_id")

    if not meeting_id or (not video_url and not transcript_text):
        raise HTTPException(status_code=400, detail="meeting_id and either video_url or transcript_text are required.")

    # Add the long-running task to the background
    background_tasks.add_task(run_full_automation_flow, user_id, meeting_id, video_url, transcript_text)

    # Immediately return a response to the user
    return {"message": "Automation process started. You will receive a notification upon completion."}


# --- ROUTES ---

@app.get("/")
def read_root():
    return {"message": "Welcome to the MinuteMe Backend"}

@app.post("/agenda")
async def create_agenda_endpoint(
    user_input: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Creates a new agenda for the authenticated user.
    """
    try:
        user_id = current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in token.")
        
        print(f"Authenticated request. Generating agenda for user: {user_id}")
        agenda = generate_agenda(user_input, user_id=user_id)
        return agenda
    except Exception as e:
        print(f"Error creating agenda: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agendas")
async def get_agendas_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Retrieves all agendas for the authenticated user.
    """
    try:
        user_id = current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in token.")
        
        agendas = get_all_agendas_for_user(user_id)
        return agendas
    except Exception as e:
        print(f"Error getting agendas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/action-items")
async def get_action_items_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Retrieves all action items for the authenticated user.
    """
    try:
        user_id = current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in token.")
        
        action_items = get_all_action_items_for_user(user_id)
        return action_items
    except Exception as e:
        print(f"Error getting action items: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/minutes")
async def get_all_minutes_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Retrieves minutes documents for the authenticated user.
    For free users, only returns the last 3 minutes.
    """
    user_id = current_user.get("sub")
    tier = current_user.get("metadata", {}).get("tier", "free")
    
    minutes = get_all_minutes_for_user(user_id)
    
    # TIER CHECK: Limit history for free users
    if tier == "free" and len(minutes) > 3:
        # Sort by date and return only the most recent 3
        minutes = sorted(minutes, key=lambda x: x.get("created_at", ""), reverse=True)[:3]
        
    return minutes

@app.get("/minutes/{minutes_id}")
async def get_minute_detail_endpoint(minutes_id: str, current_user: dict = Depends(get_current_user)):
    """
    Retrieves a single minutes document by its ID.
    """
    user_id = current_user.get("sub")
    minute = get_minutes_by_id(minutes_id, user_id)
    if not minute:
        raise HTTPException(status_code=404, detail="Minutes not found.")
    return minute

@app.get("/events")
async def get_events_endpoint(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub")
    meetings = get_all_meetings_for_user(user_id)
    action_items = get_all_action_items_for_user(user_id)  # <-- Add this

    events = []

    # Meetings as events
    for meeting in meetings:
        event_date = dateparser.parse(meeting.get("meeting_date"))
        if event_date:
            events.append({
                "title": meeting.get("meeting_name", "Untitled Meeting"),
                "start": event_date,
                "end": event_date,
                "allDay": True,
                "resource": {
                    "type": "meeting",
                    "agenda_id": meeting.get("agenda_id")
                }
            })

    # Action items as events
    for item in action_items:
        deadline = item.get("deadline")
        if deadline:
            deadline_date = dateparser.parse(deadline)
            if deadline_date:
                events.append({
                    "title": item.get("task", "Untitled Action Item"),
                    "start": deadline_date,
                    "end": deadline_date,
                    "allDay": True,
                    "resource": {
                        "type": "action-item",
                        "owner": item.get("owner"),
                        "status": item.get("status", "pending")
                    }
                })

    return events

@app.post("/schedule-agenda")
async def schedule_agenda_endpoint(
    request_body: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("sub")
    agenda_id = request_body.get("agenda_id")
    if not agenda_id:
        raise HTTPException(status_code=400, detail="agenda_id is required.")

    agenda = get_agenda(agenda_id, user_id)
    if not agenda:
        raise HTTPException(status_code=404, detail="Agenda not found.")

    try:
        description = "\n".join([item['topic'] for item in agenda.get("agenda", [])])
        # Schedule in Google Calendar
        schedule_action_item(
            user_id,
            task_name=agenda.get("meeting_name"),
            description=description,
            deadline_str=agenda.get("meeting_date"),
            owner="All",
            duration_minutes=60
        )
        # Create meeting document in DB
        meeting_data = {
            "meeting_name": agenda.get("meeting_name"),
            "meeting_date": agenda.get("meeting_date"),
            "agenda_id": agenda.get("meeting_id"),
            "status": "scheduled"
        }
        from lib.database import save_meeting
        save_meeting(meeting_data, user_id)
        return {"message": "Meeting scheduled successfully in Google Calendar and saved in DB."}
    except Exception as e:
        print(f"Error scheduling agenda: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule meeting: {e}")


@app.post("/transcribe")
async def transcribe_endpoint(
    request_body: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user.get("sub")
        tier = current_user.get("metadata", {}).get("tier", "free")
        video_url = request_body.get("video_url")
        meeting_id = request_body.get("meeting_id")
        meeting_name = request_body.get("meeting_name")
        meeting_date = request_body.get("meeting_date")

        if not all([video_url, meeting_id, meeting_name, meeting_date]):
            raise HTTPException(status_code=400, detail="Missing required fields for transcription.")

        # TIER CHECK: Video length and transcription quota
        if tier == "free":
            video_length_minutes = await get_video_length(video_url)
            if video_length_minutes > 15:
                raise HTTPException(status_code=403, detail="Free tier users can only transcribe meetings up to 15 minutes.")
            
            exceeded, quota_info = check_free_tier_limits(user_id, "transcription")
            if exceeded:
                raise HTTPException(status_code=403, detail=f"You've reached your monthly limit of {quota_info['limit']} video transcriptions.")

        transcript_text = transcribe_video(video_url=video_url, user_id=user_id)
        
        if not transcript_text:
            raise HTTPException(status_code=500, detail="Transcription failed to produce text.")

        # Save the transcript and mark it as automated
        from lib.database import save_transcript
        transcript_id = save_transcript(
            transcript_text=transcript_text,
            user_id=user_id,
            meeting_id=meeting_id,
            meeting_name=meeting_name,
            meeting_date=meeting_date,
            automated=True # This will be used for quota counting
        )
        
        return {"message": "Transcription successful", "transcript_id": transcript_id}
    except Exception as e:
        print(f"Error in /transcribe: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/save-manual-transcript")
async def save_manual_transcript_endpoint(
    request_body: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Saves a manually provided transcript."""
    try:
        user_id = current_user.get("sub")
        transcript_id = save_transcript(
            transcript_text=request_body.get("transcript"),
            user_id=user_id,
            meeting_id=request_body.get("meeting_id"),
            meeting_name=request_body.get("meeting_name"),
            meeting_date=request_body.get("meeting_date"),
            automated=False # This is a manual submission
        )
        return {"message": "Transcript saved", "transcript_id": transcript_id}
    except Exception as e:
        print(f"Error saving manual transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transcripts")
async def get_transcripts_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Retrieves all transcripts for the authenticated user.
    """
    user_id = current_user.get("sub")
    db = get_db()
    transcripts = list(db.transcripts.find({"user_id": user_id}, sort=[("created_at", -1)]))
    for t in transcripts:
        if "_id" in t:
            t["_id"] = str(t["_id"])
    return transcripts

@app.delete("/transcripts/{transcript_id}")
async def delete_transcript_endpoint(
    transcript_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Deletes a transcript for the authenticated user."""
    user_id = current_user.get("sub")
    deleted_count = delete_transcript(transcript_id, user_id)
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transcript not found or you do not have permission to delete it.")
    return {"message": "Transcript deleted successfully."}

@app.post("/generate-minutes")
async def generate_minutes_endpoint(request_body: dict = Body(None), current_user: dict = Depends(get_current_user)):
    """
    Generates minutes from a transcript for the authenticated user.
    If no transcript_id is provided, it uses the latest one.
    """
    try:
        user_id = current_user.get("sub")
        transcript_id = None
        if request_body:
            transcript_id = request_body.get("transcript_id")
        
        # This function returns the full minutes document, including the new _id
        minutes_data = generate_minutes(user_id=user_id, transcript_id=transcript_id)
        
        if not minutes_data:
            raise HTTPException(status_code=500, detail="Failed to generate minutes from transcript.")
            
        return minutes_data
    except Exception as e:
        print(f"Error generating minutes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-action-items")
async def generate_action_items_endpoint(
    request_body: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Generates action items for a specific minutes document.
    Expects: {"minutes_id": "..."}
    """
    try:
        user_id = current_user.get("sub")
        minutes_id = request_body.get("minutes_id")
        if not minutes_id:
            raise HTTPException(status_code=400, detail="minutes_id is required.")
        
        # --- MODIFIED: Capture the return value which contains the corrected items ---
        action_items_result = extract_and_schedule_tasks(user_id=user_id, minutes_id=minutes_id)
        
        if action_items_result is None:
            raise HTTPException(status_code=404, detail="Failed to process action items. Minutes document may not exist.")
            
        return action_items_result
    except Exception as e:
        print(f"Error generating action items: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.patch("/agenda/{agenda_id}")
async def update_agenda_endpoint(
    agenda_id: str,
    update_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Updates an existing agenda for the authenticated user.
    """
    user_id = current_user.get("sub")
    # Implement update logic in lib/database.py
    updated_agenda = update_agenda(agenda_id, update_data, user_id)
    if not updated_agenda:
        raise HTTPException(status_code=404, detail="Agenda not found or update failed.")
    return updated_agenda

@app.patch("/action-items/{item_id}")
async def update_action_item_status(
    item_id: str,
    update_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Updates the status or details of an action item.
    """
    user_id = current_user.get("sub")
    db = get_db()
    result = db.action_items.update_one(
        {"_id": ObjectId(item_id), "user_id": user_id},
        {"$set": update_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Action item not found or update failed.")
    item = db.action_items.find_one({"_id": ObjectId(item_id), "user_id": user_id})
    if item and "_id" in item:
        item["_id"] = str(item["_id"])
    return item

@app.post("/meetings")
async def create_meeting_endpoint(
    meeting_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Creates a new meeting for the authenticated user.
    """
    user_id = current_user.get("sub")
    tier = current_user.get("tier", "free")
    # Enforce meeting count for free users
    if tier == "free":
        from lib.database import get_document_count
        count = get_document_count("meetings", user_id)
        if count >= 5:
            raise HTTPException(status_code=403, detail="Free tier: max 5 meetings per month.")
        # Enforce meeting length
        if meeting_data.get("duration", 0) > 15:
            raise HTTPException(status_code=403, detail="Free tier: max 15 min meetings.")
    # Proceed as normal for premium
    meeting = save_meeting(meeting_data, user_id)
    return meeting

@app.get("/meetings")
async def get_meetings_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Retrieves all meetings for the authenticated user.
    """
    user_id = current_user.get("sub")
    meetings = get_all_meetings_for_user(user_id)
    return meetings

@app.patch("/meetings/{meeting_id}")
async def update_meeting_endpoint(
    meeting_id: str,
    update_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Updates an existing meeting for the authenticated user.
    """
    user_id = current_user.get("sub")
    updated_meeting = update_meeting(meeting_id, update_data, user_id)
    if not updated_meeting:
        raise HTTPException(status_code=404, detail="Meeting not found or update failed.")
    return updated_meeting

@app.delete("/meetings/{meeting_id}")
async def delete_meeting_endpoint(
    meeting_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Deletes a meeting for the authenticated user.
    """
    user_id = current_user.get("sub")
    deleted = delete_meeting(meeting_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Meeting not found or delete failed.")
    return {"message": "Meeting deleted."}

@app.delete("/agenda/{agenda_id}")
async def delete_agenda_endpoint(
    agenda_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Deletes an agenda for the authenticated user.
    """
    user_id = current_user.get("sub")
    db = get_db()
    result = db.agendas.delete_one({"meeting_id": agenda_id, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Agenda not found or already deleted.")
    return {"message": "Agenda deleted successfully."}

@app.get("/admin/users")
async def list_users(current_user: dict = Depends(get_current_user)):
    print("[/admin/users] current_user:", current_user)
    if current_user.get("metadata", {}).get("role") != "admin":
        print("[/admin/users] Forbidden: Not admin")
        raise HTTPException(status_code=403, detail="Forbidden: Admins only.")
    # Example: Fetch users from Clerk (replace with your actual logic)
    from clerk_backend_api import Clerk
    clerk = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))
    users = clerk.users.list()
    # Format users for frontend
    user_list = []
    for u in users:
        user_data = {
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email_addresses[0].email_address if u.email_addresses else "No email",
            "role": u.public_metadata.get("role", "user"),
            "tier": u.public_metadata.get("tier", "free"),
        }
        user_list.append(user_data)
    return user_list

@app.patch("/admin/user/{user_id}/tier")
async def update_user_tier(user_id: str, tier: str, current_user: dict = Depends(get_current_user)):
    print(f"--- ⚙️ ADMIN: ATTEMPTING TIER UPDATE ---")
    print(f"Target User ID: {user_id}, New Tier: {tier}")
    print(f"Admin User: {current_user.get('sub')}")

    if current_user.get("metadata", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        clerk = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))
        print("1. Clerk client initialized.")
        
        user_to_update = clerk.users.get(user_id=user_id)
        print(f"2. Fetched user to update. Current metadata: {user_to_update.public_metadata}")
        
        current_metadata = user_to_update.public_metadata or {}
        current_metadata['tier'] = tier
        print(f"3. Prepared new metadata for update: {current_metadata}")
        
        # Fix: Change update_user to update
        updated_user = clerk.users.update(user_id=user_id, public_metadata=current_metadata)
        print(f"4. ✅ Successfully updated user in Clerk. New metadata: {updated_user.public_metadata}")
        
        return {"success": True, "user_id": updated_user.id, "new_tier": updated_user.public_metadata.get("tier")}
    except Exception as e:
        print(f"❌ FAILED TO UPDATE TIER. Exception: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update user tier in Clerk: {str(e)}")

@app.patch("/admin/user/{user_id}/role")
async def update_user_role(user_id: str, role: str, current_user: dict = Depends(get_current_user)):
    print(f"--- ⚙️ ADMIN: ATTEMPTING ROLE UPDATE ---")
    print(f"Target User ID: {user_id}, New Role: {role}")
    print(f"Admin User: {current_user.get('sub')}")

    if current_user.get("metadata", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        clerk = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))
        print("1. Clerk client initialized.")

        user_to_update = clerk.users.get(user_id=user_id)
        print(f"2. Fetched user to update. Current metadata: {user_to_update.public_metadata}")

        current_metadata = user_to_update.public_metadata or {}
        current_metadata['role'] = role
        print(f"3. Prepared new metadata for update: {current_metadata}")

        updated_user = clerk.users.update(user_id=user_id, public_metadata=current_metadata)
        print(f"4. ✅ Successfully updated user in Clerk. New metadata: {updated_user.public_metadata}")
        
        return {"success": True, "user_id": updated_user.id, "new_role": updated_user.public_metadata.get("role")}
    except Exception as e:
        # --- MODIFIED: Print the full traceback for detailed debugging ---
        print(f"❌ FAILED TO UPDATE ROLE. Exception: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update user role in Clerk: {str(e)}")


@app.delete("/admin/user/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Deletes a user from Clerk. This is a permanent action."""
    if current_user.get("metadata", {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        clerk = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))
        deleted_user_response = clerk.users.delete(user_id=user_id)
        
        # Optionally, you might want to clean up user-related data from your own database here.
        # For example: db.meetings.delete_many({"user_id": user_id})
        
        return {"success": True, "deleted_user_id": deleted_user_response.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user from Clerk: {str(e)}")


# Replace these notification endpoints

@app.get("/notifications")
async def get_notifications_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Retrieves notifications for the authenticated user.
    """
    user_id = current_user.get("sub")
    tier = current_user.get("metadata", {}).get("tier", "free")
    
    notifications = get_user_notifications(user_id)
    return notifications

@app.post("/notifications/read-all")
async def read_all_notifications_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Marks all notifications as read for the authenticated user.
    """
    user_id = current_user.get("sub")
    result = mark_all_notifications_read(user_id)
    return {"success": True, "updated": result}

@app.patch("/notifications/{notification_id}/read")
async def read_notification_endpoint(
    notification_id: str, 
    current_user: dict = Depends(get_current_user)
):
    """
    Marks a specific notification as read.
    """
    user_id = current_user.get("sub")
    result = mark_notification_read(notification_id, user_id)
    return {"success": result}

@app.get("/user/automation-quota")
async def get_automation_quota_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Returns the user's remaining automation cycles for the month.
    """
    user_id = current_user.get("sub")
    tier = current_user.get("metadata", {}).get("tier", "free")
    
    # Premium users have unlimited automation cycles
    if tier == "premium":
        return {"limit": -1, "used": 0, "remaining": -1}
    
    _, quota_info = check_free_tier_limits(user_id, "automation")
    return quota_info

@app.get("/user/transcription-quota")
async def get_transcription_quota_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Returns the user's remaining video transcription quota for the month.
    """
    user_id = current_user.get("sub")
    tier = current_user.get("metadata", {}).get("tier", "free")
    
    # Premium users have unlimited transcriptions
    if tier == "premium":
        return {"limit": -1, "used": 0, "remaining": -1}
    
    _, quota_info = check_free_tier_limits(user_id, "transcription")
    return quota_info

# --- Google Calendar Auth Routes ---

@app.get("/auth/google/url")
async def get_google_auth_url(current_user: dict = Depends(get_current_user)):
    """Generates the Google OAuth2 authorization URL."""
    # --- ADDED: Tier check for this premium feature ---
    tier = current_user.get("metadata", {}).get("tier", "free")
    if tier == "free":
        raise HTTPException(
            status_code=403,
            detail="Google Calendar integration is a Premium feature. Please upgrade to connect your calendar."
        )
        
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri="http://localhost:5173/settings" # Redirect to frontend settings page
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent', # Force prompt for refresh_token
        include_granted_scopes='true'
    )
    return {"authorization_url": authorization_url}

@app.post("/auth/google/exchange")
async def exchange_google_auth_code(
    request_body: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Exchanges an authorization code for credentials."""
    user_id = current_user.get("sub")
    code = request_body.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code is required.")

    try:
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=SCOPES,
            redirect_uri="http://localhost:5173/settings"
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # --- FIX: Ensure refresh_token is saved on initial exchange ---
        creds_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token, # This was missing
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        save_google_credentials(user_id, creds_dict)
        return {"message": "Google Calendar connected successfully."}
    except Exception as e:
        print(f"Error exchanging Google auth code: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to exchange code: {str(e)}")

@app.get("/auth/google/status")
async def get_google_auth_status(current_user: dict = Depends(get_current_user)):
    """Checks if the user has connected their Google Calendar."""
    user_id = current_user.get("sub")
    credentials = get_google_credentials(user_id)
    return {"is_connected": credentials is not None}

@app.post("/auth/google/disconnect")
async def disconnect_google_calendar(current_user: dict = Depends(get_current_user)):
    """Disconnects the user's Google Calendar."""
    user_id = current_user.get("sub")
    delete_google_credentials(user_id)
    return {"message": "Google Calendar disconnected successfully."}
