import base64
import io
import os
import re
import sys
import traceback
import datetime

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

import docx
import fitz  # PyMuPDF
import google.generativeai as genai
import requests
from flask import Flask, jsonify, render_template, request
from PIL import Image
from youtube_transcript_api import YouTubeTranscriptApi

# Load environment variables for local development
load_dotenv()

# --- MERGED FROM MONGODB.PY: Database Connection Logic ---

def init_db():
    """
    Initializes and returns a connection to the MongoDB database.
    If it fails, it will stop the application.
    """
    mongo_uri = os.environ.get("MONGO_URI")

    if not mongo_uri:
        print("\n" + "="*60)
        print("❌ FATAL ERROR: MONGO_URI environment variable not found.")
        print("   The application cannot start without the database connection string.")
        print("   Please check this variable in your Render Environment settings.")
        print("="*60 + "\n")
        sys.exit(1) # Stop the application
    
    try:
        print("--- Attempting to connect to MongoDB ---")
        client = MongoClient(mongo_uri)
        client.admin.command('ismaster') # A cheap command to verify connection
        db = client['collegeproject']
        print(f"✅ MongoDB connection successful. Connected to database: '{db.name}'")

        if 'chat_history' not in db.list_collection_names():
            db.create_collection('chat_history')
            print("--- Created 'chat_history' collection. ---")
        return db

    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ FATAL ERROR: Could not connect to MongoDB.")
        print(f"   Please check your MONGO_URI, IP Access List, and user permissions.")
        print(f"   DETAILS: {e}")
        print("="*60 + "\n")
        sys.exit(1) # Stop the application

def save_chat_history(db, user_msg, ai_msg):
    """Saves a chat record to MongoDB."""
    if not db:
        print("⚠️ Database connection is not available. Cannot save chat history.")
        return
    try:
        print("--- Attempting to save chat history... ---")
        chat_history_collection = db.chat_history
        chat_record = {'user_message': user_msg, 'ai_response': ai_msg, 'timestamp': datetime.datetime.utcnow()}
        result = chat_history_collection.insert_one(chat_record)
        print(f"📝 Chat history saved successfully with ID: {result.inserted_id}")
    except Exception as e:
        print(f"⚠️ DATABASE SAVE FAILED: {e}")


# --- Main Application Setup ---

app = Flask(__name__, template_folder='templates')

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")

# --- INITIALIZE DATABASE ON STARTUP ---
db = init_db()

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

# --- Flask Routes and Helper Functions ---

@app.route('/')
def home():
    return render_template('coming_soon.html')

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
    video_id_match = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})", video_url)
    return video_id_match.group(1) if video_id_match else None

def get_youtube_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([d['text'] for d in transcript_list])
    except Exception as e:
        print(f"Error getting YouTube transcript: {e}")
        return None

@app.route('/chat', methods=['POST'])
def chat():
    # --- DIAGNOSTIC CODE ---
    try:
        print("[DIAGNOSTIC] --- New Request Received ---")
        if request.is_json:
            raw_data = request.get_json()
            print(f"[DIAGNOSTIC] Raw JSON received: {raw_data}")
            if 'text' in raw_data:
                print(f"[DIAGNOSTIC] 'text' key found. Type: {type(raw_data.get('text'))}")
            if 'fileData' in raw_data and raw_data.get('fileData'):
                print(f"[DIAGNOSTIC] 'fileData' key found and is NOT empty.")
            else:
                print("[DIAGNOSTIC] 'fileData' key is MISSING or EMPTY.")
            if 'fileType' in raw_data:
                 print(f"[DIAGNOSTIC] 'fileType' key found. Value: {raw_data.get('fileType')}")
        else:
            print("[DIAGNOSTIC] Request is NOT JSON.")
        print("[DIAGNOSTIC] --- End of Diagnostic Info ---")
    except Exception as diag_e:
        print(f"[DIAGNOSTIC] Error during diagnostic logging: {diag_e}")
    # --- END OF DIAGNOSTIC CODE ---

    try:
        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType', '')

        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt_parts = []
        if user_message:
            prompt_parts.append(user_message)

        # Priority 1: Handle a YouTube Link
        if "youtube.com" in user_message or "youtu.be" in user_message:
            video_id = get_video_id(user_message)
            if video_id:
                transcript = get_youtube_transcript(video_id)
                if transcript:
                    youtube_prompt = f"Please provide a detailed summary of the following YouTube transcript:\n\n{transcript}"
                    response = model.generate_content(youtube_prompt)
                    ai_response_text = response.text
                    save_chat_history(db, user_message, ai_response_text)
                    return jsonify({'response': ai_response_text})

        # Priority 2: Check for keywords to get a file from GitHub
        matched_filename = next((fn for kw, fn in PDF_KEYWORDS.items() if kw in user_message.lower()), None)
        if matched_filename:
            file_bytes = get_file_from_github(matched_filename)
            if file_bytes:
                pdf_text = extract_text_from_pdf(file_bytes)
                if pdf_text.strip():
                    prompt_parts.append(f"\n--- Document: {matched_filename} ---\n{pdf_text}")

        # Priority 3: Handle a direct file upload
        if file_data:
            try:
                file_bytes = base64.b64decode(file_data)
                if 'pdf' in file_type:
                    pdf_text = extract_text_from_pdf(file_bytes)
                    prompt_parts.append(f"\n--- Uploaded PDF ---\n{pdf_text}")
                elif 'word' in file_type or 'vnd.openxmlformats-officedocument.wordprocessingml.document' in file_type:
                    docx_text = extract_text_from_docx(file_bytes)
                    prompt_parts.append(f"\n--- Uploaded Document ---\n{docx_text}")
                elif 'image' in file_type:
                    image = Image.open(io.BytesIO(file_bytes))
                    prompt_parts.append(image)
            except Exception as e:
                print(f"Error decoding or processing file data: {e}")
                return jsonify({'response': "Sorry, there was an error processing the uploaded file."})

        # Generate AI Response
        if not prompt_parts:
            return jsonify({'response': "Please ask a question or upload a file."})

        response = model.generate_content(prompt_parts)
        ai_response = response.text

        # --- SAVE TO MONGODB ---
        save_chat_history(db, user_message, ai_response)

        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"A critical error occurred: {e}")
        traceback.print_exc()
        # Check for specific API errors to provide better user feedback
        if "429" in str(e) and "quota" in str(e).lower():
            user_facing_error = "Sorry, the daily limit for the AI service has been reached. Please try again tomorrow."
        else:
            user_facing_error = "The AI service is currently unavailable. Please try again later."
        return jsonify({'response': user_facing_error})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

