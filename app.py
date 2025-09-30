import base64
import io
import os
import re
import sys
import json
from datetime import datetime

import docx
import fitz  # PyMuPDF
import google.generativeai as genai
import requests 
from flask import Flask, jsonify, render_template, request
from PIL import Image
from pymongo import MongoClient
from youtube_transcript_api import YouTubeTranscriptApi

# --- Google Drive API Imports ---
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload


app = Flask(__name__, template_folder='templates')

# --- Securely Load API Keys and Config from Render Environment ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
OPENROUTER_API_KEY_V3 = os.environ.get("OPENROUTER_API_KEY_V3")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# --- New: Google Drive Credentials and File ID ---
GOOGLE_DRIVE_CREDS_JSON = os.environ.get("GOOGLE_DRIVE_CREDS_JSON")
DRIVE_FILE_ID = "1G86soMom_Ifbfg7liqtBWWzdr9ChtZoU"


# --- Configure API Services ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    print(f"✅ Loaded google-generativeai version: {genai.__version__}")
else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")

if not OPENROUTER_API_KEY_V3:
    print("WARNING: OPENROUTER_API_KEY_V3 not found. OpenRouter will be skipped.")
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not found. Groq API will be skipped.")


# --- MongoDB Configuration ---
chat_history_collection = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client.get_database("ai_assistant_db")
        chat_history_collection = db.get_collection("chat_history")
        print("✅ Successfully connected to MongoDB.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to MongoDB. Chat history will not be saved. Error: {e}")
else:
    print("WARNING: MONGO_URI environment variable not found. Chat history will not be saved.")
    
# --- New: Google Drive Helper Functions ---

def get_drive_service():
    """Authenticates and returns a Google Drive service object."""
    if not GOOGLE_DRIVE_CREDS_JSON:
        print("CRITICAL ERROR: GOOGLE_DRIVE_CREDS_JSON environment variable not found.")
        return None
    try:
        creds_info = json.loads(GOOGLE_DRIVE_CREDS_JSON)
        creds = Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=creds)
        print("✅ Successfully authenticated with Google Drive API.")
        return service
    except Exception as e:
        print(f"CRITICAL ERROR: Could not authenticate with Google Drive. Error: {e}")
        return None

def get_users_from_drive_file(service, file_id):
    """Downloads and reads the user JSON file from Google Drive."""
    if not service:
        return []
    try:
        request = service.files().get_media(fileId=file_id)
        file_io = io.BytesIO()
        downloader = MediaIoBaseDownload(file_io, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        file_io.seek(0)
        users = json.load(file_io)
        print(f"✅ Successfully loaded {len(users)} users from Google Drive.")
        return users
    except Exception as e:
        print(f"ERROR: Could not read users file from Google Drive. Error: {e}")
        return [] # Return empty list on failure

def save_users_to_drive_file(service, file_id, users_data):
    """Uploads updated user data to the JSON file in Google Drive."""
    if not service:
        return False
    try:
        file_content = json.dumps(users_data, indent=4).encode('utf-8')
        file_io = io.BytesIO(file_content)
        media = MediaIoBaseUpload(file_io, mimetype='application/json', resumable=True)
        service.files().update(fileId=file_id, media_body=media).execute()
        print(f"✅ Successfully saved {len(users_data)} users to Google Drive.")
        return True
    except Exception as e:
        print(f"ERROR: Could not save users file to Google Drive. Error: {e}")
        return False
        
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
    return render_template('index.html')

# --- New: User Authentication Routes ---
@app.route('/users', methods=['GET'])
def get_users():
    drive_service = get_drive_service()
    users = get_users_from_drive_file(drive_service, DRIVE_FILE_ID)
    return jsonify(users)

@app.route('/users', methods=['POST'])
def add_user():
    new_user_data = request.json
    drive_service = get_drive_service()
    
    # Read existing users
    existing_users = get_users_from_drive_file(drive_service, DRIVE_FILE_ID)
    
    # Check for duplicates
    for user in existing_users:
        if user.get('email') == new_user_data.get('email'):
            return jsonify({'success': False, 'error': 'User already exists'}), 409
            
    # Add new user and save
    existing_users.append(new_user_data)
    success = save_users_to_drive_file(drive_service, DRIVE_FILE_ID, existing_users)
    
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Failed to save user data to Google Drive'}), 500


# --- Helper Functions for File Processing ---
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
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO.replace(' ', '%20')}/main/{GITHUB_FOLDER_PATH.replace(' ', '%20')}/{filename.replace(' ', '%20')}"
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

# --- Helper Function for OpenRouter API (Simplified) ---
def call_openrouter_api(user_message):
    api_key = OPENROUTER_API_KEY_V3
    model_name = "deepseek/deepseek-chat"
    if not api_key:
        return None
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model_name, "messages": [{"role": "user", "content": user_message}]}
        )
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"Error calling OpenRouter API for model {model_name}: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Error parsing OpenRouter API response: {e}")
        return None

# --- Helper Function for Groq API ---
def call_groq_api(user_message):
    if not GROQ_API_KEY:
        return None
    try:
        response = requests.post(
            url="https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": user_message}]
            }
        )
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"Error calling Groq API: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Error parsing Groq API response: {e}")
        return None

# --- Main Chat Logic (with intelligent routing) ---
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType', '')
        
        ai_response = ""
        api_used = ""
        model_logged = ""
        
        is_youtube_link = "youtube.com" in user_message or "youtu.be" in user_message
        matched_github_keyword = any(keyword in user_message.lower() for keyword in PDF_KEYWORDS)
        is_multimodal_request = bool(file_data) or is_youtube_link or matched_github_keyword

        # --- Route 1: Text-only chat with automatic fallbacks ---
        if not is_multimodal_request and user_message.strip():
            print("Routing to OpenRouter with DeepSeek model.")
            ai_response = call_openrouter_api(user_message)
            if ai_response:
                api_used = "OpenRouter"
                model_logged = "deepseek/deepseek-chat"
            
            if not ai_response:
                print("OpenRouter failed, trying Groq as a second option.")
                ai_response = call_groq_api(user_message)
                if ai_response:
                    api_used = "Groq"
                    model_logged = "llama3-8b-8192"

        # --- Route 2: Fallback or Multimodal to Gemini ---
        if not ai_response:
            print("Routing to Gemini for multimodal request or as a final fallback.")
            api_used = "Gemini"
            
            model_logged = "gemini-2.0-flash-exp" 
            
            model = genai.GenerativeModel(model_logged)
            prompt_parts = []
            if user_message:
                prompt_parts.append(user_message)

            # Handle multimodal inputs
            if is_youtube_link:
                video_id = get_video_id(user_message)
                if video_id:
                    transcript = get_youtube_transcript(video_id)
                    prompt_parts = [f"Summarize this YouTube video transcript:\n\n{transcript}"] if transcript else []
                if not prompt_parts: return jsonify({'response': "Sorry, couldn't get the transcript for that video."})
            elif matched_github_keyword:
                filename = next((fname for kw, fname in PDF_KEYWORDS.items() if kw in user_message.lower()), None)
                file_bytes = get_file_from_github(filename)
                if file_bytes: prompt_parts.append(f"\n--- Document: {filename} ---\n{extract_text_from_pdf(file_bytes)}")
                else: return jsonify({'response': f"Sorry, I could not download '{filename}'."})
            elif file_data:
                file_bytes = base64.b64decode(file_data)
                if 'pdf' in file_type: prompt_parts.append(f"\n--- Uploaded PDF ---\n{extract_text_from_pdf(file_bytes)}")
                elif 'word' in file_type: prompt_parts.append(f"\n--- Uploaded Document ---\n{extract_text_from_docx(file_bytes)}")
                elif 'image' in file_type: prompt_parts.append(Image.open(io.BytesIO(file_bytes)))
                else: return jsonify({'response': f"Sorry, unsupported file type '{file_type}'."})
            
            if not prompt_parts: return jsonify({'response': "Please ask a question or upload a file."})

            if any(isinstance(p, Image.Image) for p in prompt_parts) and not any(isinstance(p, str) and p.strip() for p in prompt_parts):
                prompt_parts.insert(0, "Describe this image in detail.")

            response = model.generate_content(prompt_parts)
            ai_response = response.text

        # --- Save to MongoDB (runs for all routes) ---
        if chat_history_collection is not None and ai_response:
            try:
                chat_history_collection.insert_one({
                    "user_message": user_message, "ai_response": ai_response,
                    "api_used": api_used, "model_used": model_logged,
                    "has_file": bool(file_data), "file_type": file_type if file_data else None,
                    "timestamp": datetime.utcnow()
                })
            except Exception as e:
                print(f"Error saving chat to MongoDB: {e}")

        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"A critical error occurred: {e}")
        user_facing_error = "Sorry, something went wrong. Please try again."
        return jsonify({'response': user_facing_error})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
