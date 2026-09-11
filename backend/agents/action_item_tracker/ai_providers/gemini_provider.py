import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import re
import time
import random
from google.api_core.exceptions import ResourceExhausted

load_dotenv()
# Corrected to use GOOGLE_API_KEY from your .env file
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found. Make sure it's set in your .env file.")
genai.configure(api_key=api_key)

# Using a valid model from the list you provided.
model = genai.GenerativeModel("gemini-2.0-flash-exp") # Using the latest flash model

def clean_json_output(raw_output: str):
    try:
        # The response might be wrapped in ```json ... ```, remove it.
        if raw_output.strip().startswith("```json"):
            raw_output = raw_output.strip()[7:-3]
        return json.loads(raw_output)
    except json.JSONDecodeError:
        # Fallback for cases where the output is not perfect JSON
        match = re.search(r"\[.*]", raw_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                 return [{"error": "Failed to parse cleaned JSON", "raw": match.group()}]
        return [{"error": "Failed to parse JSON", "raw": raw_output}]

# --- NEW: Helper function to handle API calls with retries ---
def generate_with_retry(prompt: str, max_retries: int = 3):
    """
    Calls the Gemini API with a prompt and implements exponential backoff for rate limit errors.
    """
    base_delay = 5  # seconds
    for attempt in range(max_retries):
        try:
            print(f"🤖 Calling AI model (Attempt {attempt + 1}/{max_retries})...")
            response = model.generate_content(prompt)
            return response # Success
        except ResourceExhausted as e:
            print(f"Attempt {attempt + 1} failed with ResourceExhausted: {e}")
            if attempt < max_retries - 1:
                # Calculate wait time with jitter (randomness)
                wait_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"Rate limit exceeded. Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            else:
                print("Max retries reached. AI call failed.")
                # Re-raise the exception if all retries fail
                raise e
        except Exception as e:
            print(f"An unexpected error occurred during AI call: {e}")
            raise e

def extract_action_items(meeting_text:str):
    prompt = f"""
    Extract action items from this meeting. Respond ONLY with a JSON list of objects.
    Each object must have: "owner", "task", and "deadline" (if any, otherwise null).
    Meeting text: {meeting_text}
    """
    # --- MODIFIED: Use the retry helper ---
    response = generate_with_retry(prompt)
    return clean_json_output(response.text)

def generate_summary_gemini(text: str) -> str:
    prompt = f"Summarize the following text:\n{text}"
    # --- MODIFIED: Use the retry helper ---
    response = generate_with_retry(prompt)
    return response.text.strip()

def extract_key_decisions_gemini(text: str) -> list:
    prompt = f"Extract key decisions from the following text. Respond with a JSON list of strings. For example: [\"Decision one\", \"Decision two\"]\n\nText: {text}"
    # --- MODIFIED: Use the retry helper ---
    response = generate_with_retry(prompt)
    return clean_json_output(response.text)

def extract_future_topics_gemini(text: str) -> list:
    prompt = f"Extract future discussion topics from the following text. Respond with a JSON list of strings. For example: [\"Topic one\", \"Topic two\"]\n\nText: {text}"
    # --- MODIFIED: Use the retry helper ---
    response = generate_with_retry(prompt)
    return clean_json_output(response.text)

###########################################################
#Sample Output
#[
#  {"owner": "John", "task": "Prepare budget", "deadline": "Friday"},
#  {"owner": "Sarah", "task": "Update project plan", "deadline": null}
#]