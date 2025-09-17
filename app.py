# --- IMPORTS (Added new ones) ---
import base64
import io
import os
import re
import sys
import traceback  # For better error logging

# --- NEW CODE START: Import new libraries ---
from dotenv import load_dotenv
from pymongo import MongoClient
# --- NEW CODE END ---

import docx
import fitz  # PyMuPDF
import google.generativeai as genai
import requests
from flask import Flask, jsonify, render_template, request
from PIL import Image
from youtube_transcript_api import YouTubeTranscriptApi

# --- NEW CODE START: Load environment variables for local development ---
# This line loads the variables from your .env file
load_dotenv()
# --- NEW CODE END ---

app = Flask(__name__, template_folder='templates')

# --- Securely Load API Keys and MongoDB URI from Environment ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
# --- NEW CODE START: Get Mongo URI ---
MONGO_URI = os.environ.get("MONGO_URI")
# --- NEW CODE END ---


# --- Configure API Services ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")

# --- NEW CODE START: Configure MongoDB Connection ---
db = None # Initialize db as None
try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        db = client.get_default_database() # Or specify a DB name: client['your_db_name']
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster')
        print("✅ MongoDB connection successful.")
        # Example: Create a collection for chat history if it doesn't exist
        if 'chat_history' not in db.list_collection_names():
            db.create_collection('chat_history')
            print("Created 'chat_history' collection.")
    else:
        print("⚠️ WARNING: MONGO_URI environment variable not found. Database features will be disabled.")
except Exception as e:
    print(f"❌ CRITICAL ERROR: Could not connect to MongoDB. Error: {e}")
    db = None # Ensure db is None if connection fails
# --- NEW CODE END ---


# --- GitHub PDF Configuration ---
GITHUB_USER = "ajayyanshu"
GITHUB_REPO = "collegeproject"
GITHUB_FOLDER_PATH = "upload pdf"
PDF_KEYWORDS = {
    "2016 hindi paper": "2016 - Hindi (7402-01).pdf",
    "2023 english paper": "2023 - English (7403-01).pdf",
    "2023 hindi paper": "2023 - Hindi (7402-01).pdf",
    "2025 english paper": "2025 - English (7403-01).pdf",
    "2025 hindi paper": "2025 - Hindi (7402-01).pdf"
}


@app.route('/')
def home():
    return render_template('coming_soon.html')


# --- Helper Functions (No changes here) ---
def extract_text_from_pdf(pdf_bytes):
    try:
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "".join(page.get_text() for page in pdf_document)
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""


def extract_text_from_docx(docx_bytes):
    try:
        document = docx.Document(io.BytesIO(docx_bytes))
        return "\n".join([para.text for para in document.paragraphs])
    except Exception as e:
        print(f"Error extracting DOCX text: {e}")
        return ""


def get_file_from_github(filename):
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{GITHUB_FOLDER_PATH.replace(' ', '%20')}/{filename.replace(' ', '%20')}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(f"Successfully downloaded {filename} from GitHub.")
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error downloading from GitHub: {e}")
        return None


def get_video_id(video_url):
    video_id_match = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})",
                               video_url)
    return video_id_match.group(1) if video_id_match else None


def get_youtube_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([d['text'] for d in transcript_list])
    except Exception as e:
        print(f"Error getting YouTube transcript: {e}")
        return None


# --- Main Chat Logic ---
@app.route('/chat', methods=['POST'])
def chat():
    # --- DIAGNOSTIC CODE (No changes here) ---
    try:
        print("[DIAGNOSTIC] --- New Request Received ---")
        if request.is_json:
            raw_data = request.get_json()
            # ... (rest of diagnostic code is unchanged) ...
        print("[DIAGNOSTIC] --- End of Diagnostic Info ---")
    except Exception as diag_e:
        print(f"[DIAGNOSTIC] Error during diagnostic logging: {diag_e}")

    try:
        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType', '')

        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt_parts = []
        if user_message:
            prompt_parts.append(user_message)

        # --- Priority 1, 2, 3 (No changes in logic here) ---
        # ... (YouTube, GitHub, and file upload logic remains the same) ...
        # (For brevity, the unchanged logic blocks are omitted)

        # Generate AI Response
        if not prompt_parts:
            return jsonify(
                {'response': "Please ask a question or upload a file."})

        # ... (Code to check for text/image and generate response is unchanged) ...
        response = model.generate_content(prompt_parts)
        ai_response = response.text

        # --- NEW CODE START: Save conversation to MongoDB ---
        if db: # Only try to save if the database connection is valid
            try:
                chat_history = db.chat_history
                # We save the original user message and the final AI response
                chat_record = {
                    'user_message': user_message,
                    'ai_response': ai_response,
                    'timestamp': __import__('datetime').datetime.utcnow()
                }
                chat_history.insert_one(chat_record)
                print("📝 Chat history saved to MongoDB.")
            except Exception as e:
                print(f"⚠️ Could not save chat history to MongoDB. Error: {e}")
        # --- NEW CODE END ---

        return jsonify({'response': ai_response})

    except Exception as e:
        # --- NEW CODE START: Improved Error Logging ---
        print(f"A critical error occurred in /chat endpoint: {e}")
        traceback.print_exc() # This will print the full error stack trace
        # --- NEW CODE END ---
        if "429" in str(e) and "quota" in str(e).lower():
            user_facing_error = "Sorry, the daily limit for the AI service has been reached. Please try again tomorrow."
        else:
            user_facing_error = "Sorry, something went wrong. Please try again."
        return jsonify({'response': user_facing_error})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
