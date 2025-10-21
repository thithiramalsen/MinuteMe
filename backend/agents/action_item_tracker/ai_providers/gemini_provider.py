import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import re

load_dotenv()
# Corrected to use GOOGLE_API_KEY from your .env file
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found. Make sure it's set in your .env file.")
genai.configure(api_key=api_key)

# Using a valid model from the list you provided.
model = genai.GenerativeModel("gemini-2.0-flash-exp")

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

def extract_action_items(meeting_text:str):
    prompt = f"""
    Extract action items from this meeting. Respond ONLY with a JSON list of objects.
    Each object must have: "owner", "task", and "deadline" (if any, otherwise null).
    Meeting text: {meeting_text}
    """
    response = model.generate_content(prompt)
    return clean_json_output(response.text)


###########################################################
#Sample Output
#[
#  {"owner": "John", "task": "Prepare budget", "deadline": "Friday"},
#  {"owner": "Sarah", "task": "Update project plan", "deadline": null}
#]