import os
import json
import time
import gdown
from google.generativeai import GenerativeModel
import google.generativeai as genai
from dotenv import load_dotenv
# --- NEW: Import the specific error class ---
from pymongo.errors import ConnectionFailure
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
    Transcribes a video file using the Gemini model, downloading it if a URL is provided.

    Args:
        video_path (str, optional): The local path to the video file.
        video_url (str, optional): A public URL (e.g., Google Drive) to the video file.
        user_id (str): The ID of the user to associate the transcript with.

    Returns:
        str: The generated transcript text, or None if an error occurred.
    """
    if not video_path and not video_url:
        raise ValueError("Either video_path or video_url must be provided.")

    local_video_path = video_path
    is_temp_file = False
    temp_video_path = None
    temp_audio_path = None

    try:
        # 1. Configure the Gemini API
        configure_gemini()

        # 2. Download the video if a URL is provided
        if video_url:
            print(f"Downloading video from URL: {video_url}")
            # Define a temporary path for the downloaded file
            temp_dir = "data/meeting_video/temp"
            os.makedirs(temp_dir, exist_ok=True)
            # Download video from URL
            temp_video_path = os.path.join(temp_dir, "downloaded_video.mp4")
            gdown.download(video_url, temp_video_path, quiet=False, fuzzy=True)
            print(f"Video downloaded to temporary path: {temp_video_path}")

            # Convert video to audio
            print(f"Converting video to audio...")
            temp_audio_path = os.path.join(temp_dir, "extracted_audio.mp3")
            try:
                video_clip = mp.VideoFileClip(temp_video_path)
                video_clip.audio.write_audiofile(temp_audio_path, codec='mp3')
                video_clip.close()
                print(f"Audio extracted to: {temp_audio_path}")
                upload_path = temp_audio_path
            except Exception as e:
                print(f"Audio extraction failed: {e}. Falling back to video upload.")
                upload_path = temp_video_path
        else:
            upload_path = local_video_path

        # 3. Process the audio file with Gemini
        print(f"Processing file: {upload_path}...")
        
        # Create a model instance
        model = GenerativeModel("gemini-2.0-flash-exp")
        
        # Read the audio file
        with open(upload_path, "rb") as f:
            audio_data = f.read()
        
        # Create the prompt for transcription
        prompt = "Transcribe the audio from this file. Include speaker labels (diarization) for each part of the conversation. For example: 'Speaker 1: Hello there. Speaker 2: Hi, how are you?'"
        
        # Generate the transcription
        response = model.generate_content([
            prompt,
            {"mime_type": "audio/mp3", "data": audio_data}
        ])
        
        # Extract the transcript
        transcript = response.text
        print("\n--- Transcription ---")
        print(transcript)
        print("---------------------\n")

        print("Cleaning up temporary files...")
        # Clean up temporary files
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        print("--- ✅ Finished Transcription Agent ---")

        return transcript

    # --- MODIFIED: More specific error handling ---
    except ConnectionFailure as e:
        print("\n" + "="*50)
        print("❌ DATABASE CONNECTION FAILED")
        print(f"   Error: {e}")
        print("   This is a network-level error. The application could not find the MongoDB server.")
        print("   Please check:")
        print("   1. Your computer's internet connection.")
        print("   2. If a firewall or VPN is blocking the connection to MongoDB Atlas.")
        print("   3. The MONGO_URI in your backend/.env file is 100% correct.")
        print("="*50 + "\n")
        # Re-raise the exception so the API endpoint returns a proper 500 error
        raise
    except Exception as e:
        print(f"An unexpected error occurred in transcription agent: {e}")
        # Re-raise for the API endpoint
        raise

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