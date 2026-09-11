import os
import time
import gdown
import random
import uuid
from google.api_core.exceptions import ResourceExhausted
import google.generativeai as genai
from dotenv import load_dotenv
from pymongo.errors import ConnectionFailure
# --- RE-INTRODUCED: moviepy is essential for audio extraction ---
import moviepy.editor as mp

def configure_gemini():
    """
    Configures the Gemini API with the key from environment variables.
    """
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables. Please set it in your .env file.")
    genai.configure(api_key=api_key)

def transcribe_video(video_path: str = None, video_url: str = None, user_id: str = "user_placeholder_123"):
    """
    Transcribes a video by first extracting its audio, then uploading the audio file.
    """
    if not video_path and not video_url:
        raise ValueError("Either video_path or video_url must be provided.")

    local_video_path = video_path
    is_temp_file = False
    temp_video_path = None
    temp_audio_path = None
    uploaded_file_handle = None

    try:
        configure_gemini()
        temp_dir = "data/meeting_video/temp"
        os.makedirs(temp_dir, exist_ok=True)

        if video_url:
            print(f"Downloading video from URL: {video_url}")
            temp_video_path = os.path.join(temp_dir, f"{uuid.uuid4()}.mp4")
            gdown.download(video_url, temp_video_path, quiet=False, fuzzy=True)
            local_video_path = temp_video_path
            is_temp_file = True
            print(f"Video downloaded to temporary path: {local_video_path}")

        if not os.path.exists(local_video_path):
            raise FileNotFoundError(f"Video file not found at {local_video_path}")

        # --- HEART OF THE SYSTEM: Extract audio from the video file ---
        print(f"Extracting audio from '{local_video_path}'...")
        temp_audio_path = os.path.join(temp_dir, f"{uuid.uuid4()}.mp3")
        with mp.VideoFileClip(local_video_path) as video_clip:
            video_clip.audio.write_audiofile(temp_audio_path, codec='mp3')
        print(f"Audio extracted successfully to '{temp_audio_path}'.")

        # --- UPLOAD THE SMALLER AUDIO FILE, NOT THE VIDEO ---
        print(f"Uploading audio file to Gemini: {temp_audio_path}")
        uploaded_file_handle = genai.upload_file(path=temp_audio_path, display_name="meeting_audio")
        print(f"File uploaded successfully. URI: {uploaded_file_handle.uri}")

        print(f"Waiting for file '{uploaded_file_handle.name}' to be processed...")
        while uploaded_file_handle.state.name == "PROCESSING":
            time.sleep(5) # Check every 5 seconds
            uploaded_file_handle = genai.get_file(uploaded_file_handle.name)
        
        if uploaded_file_handle.state.name == "FAILED":
            raise ValueError(f"Audio file processing failed: {uploaded_file_handle.state.name}")
        
        print("File is now ACTIVE and ready for use.")

        prompt = "Transcribe the following audio. Provide a clean, verbatim transcript. Include speaker labels (diarization) if possible, like 'Speaker 1:' and 'Speaker 2:'."
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        max_retries = 3
        base_delay = 5

        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1}/{max_retries}: Generating transcription...")
                response = model.generate_content([prompt, uploaded_file_handle])
                transcript = response.text.strip()
                print("\n--- Transcription Successful ---")
                return transcript
            except ResourceExhausted as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    wait_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Rate limit exceeded. Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    print("Max retries reached. Transcription failed.")
                    raise e
            except Exception as e:
                print(f"An unexpected error occurred during content generation: {e}")
                raise e

    finally:
        # --- ROBUST CLEANUP ---
        if uploaded_file_handle:
            print(f"Cleaning up uploaded file from Gemini: {uploaded_file_handle.name}")
            genai.delete_file(uploaded_file_handle.name)
        
        if is_temp_file and temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)
            print(f"Deleted temporary video file: {temp_video_path}")
            
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
            print(f"Deleted temporary audio file: {temp_audio_path}")

async def get_video_length(video_url: str) -> float:
    """
    Gets the length of a video in minutes from a URL.
    
    This function checks if the URL contains length information or uses
    a default value for testing. In production, this should be replaced
    with actual video length detection.
    
    Args:
        video_url: URL to the video file
    
    Returns:
        Float representing video length in minutes
    """
    try:
        # Option 1: Check if the URL contains length information (as a query parameter)
        import re
        
        length_match = re.search(r"length=(\d+)", video_url)
        if length_match:
            # Length parameter is present in the URL
            return float(length_match.group(1))
        
        # Option 2: For development/testing, you can add special prefixes to test different lengths
        if video_url.startswith("test:short:"):
            return 10.0  # 10 minute video (within free tier)
        elif video_url.startswith("test:long:"):
            return 20.0  # 20 minute video (exceeds free tier)
            
        # Option 3: In a production implementation, you would:
        # - For Google Drive: Use Drive API to get metadata
        # - For direct uploads: Use ffmpeg or moviepy to check duration
        
        print(f"[INFO] Estimating video length for {video_url}")
        return 10.0  # Default to 10 minutes for testing
        
    except Exception as e:
        print(f"Error determining video length: {e}")
        # Default to a safe value for development
        return 10.0

if __name__ == '__main__':
    # --- How to use this script ---
    # 1. Make sure you have a .env file in the `backend` directory with your GOOGLE_API_KEY.
    # 2. Provide either a local video file path OR a public Google Drive URL.

    # --- Example with a local file ---
    # video_file_path = "data/meeting_video/meeting.mp4"
    # video_drive_url = None

    # --- Example with a Google Drive URL ---
    # Make sure the link is public / shareable
    video_file_path = None
    video_drive_url = "https://drive.google.com/file/d/1-sample-id-for-a-video/view?usp=sharing" # Replace with a real public video link

    # Call the transcription function
    transcribe_video(video_path=video_file_path, video_url=video_drive_url)