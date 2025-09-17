import base64
import io
import os
import re
import sys
import traceback
import datetime  # Added for timestamping

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure # Import specific error

import docx
import fitz  # PyMuPDF
import google.generativeai as genai
import requests
from flask import Flask, jsonify, render_template, request
from PIL import Image
from youtube_transcript_api import YouTubeTranscriptApi

# Load environment variables from .env file for local development
load_dotenv()

app = Flask(__name__, template_folder='templates')

# --- Securely Load API Keys and MongoDB URI from Environment ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")

# --- Configure API Services ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")

# --- NEW: Configure MongoDB Connection (More Robust) ---
db = None
if not MONGO_URI:
    print("⚠️ WARNING: MONGO_URI environment variable not found. Database features will be disabled.")
else:
    try:
        print("Attempting to connect to MongoDB...")
        client = MongoClient(MONGO_URI)
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster')
        
        # --- IMPORTANT CHANGE HERE ---
        # Be explicit with your database name. Don't rely on the default.
        # Replace 'collegeproject_db' with the actual name of your database.
        db = client['collegeproject_db']
        
        print(f"✅ MongoDB connection successful. Connected to database: '{db.name}'")

        if 'chat_history' not in db.list_collection_names():
            db.create_collection('chat_history')
            print("Created 'chat_history' collection.")

    except ConnectionFailure as e:
        print(f"❌ CRITICAL ERROR: Could not connect to MongoDB. Check your MONGO_URI, IP Access List, and network settings.")
        print(f"   Detailed Error: {e}")
        db = None
    except Exception as e:
        print(f"❌ An unexpected error occurred during MongoDB setup: {e}")
        db = None
# --- END OF NEW MONGO CODE ---


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
    # ... (No changes to the chat logic until the very end) ...
    # ... (For brevity, the unchanged logic blocks are omitted) ...
    try:
        # ... (all your existing chat logic here) ...
        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType', '')
        # ... and so on ...
        
        # This is just a placeholder for your existing logic
        ai_response = "This is a response."
        
        # --- Save conversation to MongoDB ---
        if db:
            try:
                chat_history = db.chat_history
                chat_record = {
                    'user_message': user_message,
                    'ai_response': ai_response,
                    'timestamp': datetime.datetime.utcnow()
                }
                chat_history.insert_one(chat_record)
                print("📝 Chat history saved to MongoDB.")
            except Exception as e:
                print(f"⚠️ Could not save chat history to MongoDB. Error: {e}")
        
        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"A critical error occurred in /chat endpoint: {e}")
        traceback.print_exc()
        if "429" in str(e) and "quota" in str(e).lower():
            user_facing_error = "Sorry, the daily limit for the AI service has been reached. Please try again tomorrow."
        else:
            user_facing_error = "Sorry, something went wrong. Please try again."
        return jsonify({'response': user_facing_error})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
