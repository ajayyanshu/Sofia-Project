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
import requests # Still needed for get_file_from_github and OpenRouter
from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from PIL import Image
from pymongo import MongoClient
from youtube_transcript_api import YouTubeTranscriptApi

# --- Google Drive API Imports ---
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest


app = Flask(__name__, template_folder='templates')

# --- Securely Load API Keys from Render Environment ---
# IMPORTANT: Add these to your Render environment variables
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-for-prod")
# This JSON content comes from the credentials.json file from Google Cloud Console
GOOGLE_DRIVE_CREDS_JSON = os.environ.get("GOOGLE_DRIVE_CREDS_JSON")
# This must match one of the "Authorized redirect URIs" in your Google Cloud Console
# For Render, it will be your full app URL + /oauth2callback
REDIRECT_URI = os.environ.get("REDIRECT_URI") 

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
OPENROUTER_API_KEY_V3 = os.environ.get("OPENROUTER_API_KEY_V3")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# --- Google Drive Scopes (permissions your app will ask for) ---
# Using read-only for safety. Change if you need to write files.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

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
if not all([GOOGLE_DRIVE_CREDS_JSON, REDIRECT_URI]):
    print("WARNING: GOOGLE_DRIVE_CREDS_JSON or REDIRECT_URI environment variables not set. Drive integration will be disabled.")


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

# --- Google Drive Helper ---
def get_google_flow():
    """Builds a Google OAuth Flow object from environment variables."""
    if not all([GOOGLE_DRIVE_CREDS_JSON, REDIRECT_URI]):
        raise ValueError("Google OAuth environment variables are not fully configured.")
    
    try:
        # Parse the JSON string from the environment variable
        client_config = json.loads(GOOGLE_DRIVE_CREDS_JSON)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in GOOGLE_DRIVE_CREDS_JSON.")
    
    # Check if the redirect URI from your environment is listed in your credentials
    if REDIRECT_URI not in client_config.get("web", {}).get("redirect_uris", []):
         print(f"WARNING: The REDIRECT_URI '{REDIRECT_URI}' is not in the list of authorized URIs in your credentials JSON. This may cause an error.")

    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI)

# --- Routes ---
@app.route('/')
def home():
    files = []
    is_connected = False
    if 'google_credentials' in session:
        try:
            creds = Credentials.from_authorized_user_info(session['google_credentials'], SCOPES)
            
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                session['google_credentials'] = {
                    'token': creds.token, 'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri, 'client_id': creds.client_id,
                    'client_secret': creds.client_secret, 'scopes': creds.scopes
                }

            service = build('drive', 'v3', credentials=creds)
            results = service.files().list(
                pageSize=15, fields="files(id, name, webViewLink, iconLink)").execute()
            files = results.get('files', [])
            is_connected = True
        except Exception as e:
            print(f"Error accessing Google Drive: {e}")
            session.pop('google_credentials', None)
            
    return render_template('index.html', files=files, is_connected=is_connected)

@app.route('/authorize_google_drive')
def authorize_google_drive():
    try:
        flow = get_google_flow()
        authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
        session['state'] = state
        return redirect(authorization_url)
    except ValueError as e:
        return str(e), 500
    except Exception as e:
        print(f"Error in authorize_google_drive: {e}")
        return "Authorization failed.", 500

@app.route('/oauth2callback')
def oauth2callback():
    state = session.get('state')
    if not state or state != request.args.get('state'):
        return 'State mismatch error.', 400

    try:
        flow = get_google_flow()
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        
        # Storing credentials in session is okay for simple apps.
        # For production, you MUST save these to a secure, encrypted user database.
        # NEVER expose the refresh_token on the client-side.
        session['google_credentials'] = {
            'token': creds.token, 'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri, 'client_id': creds.client_id,
            'client_secret': creds.client_secret, 'scopes': creds.scopes
        }
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Error in oauth2callback: {e}")
        return "Failed to fetch authorization token.", 500

@app.route('/disconnect_google_drive')
def disconnect_google_drive():
    session.pop('google_credentials', None)
    return redirect(url_for('home'))


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
            model_logged = "gemini-1.5-flash-latest" 
            model = genai.GenerativeModel(model_logged)
            prompt_parts = []
            if user_message:
                prompt_parts.append(user_message)

            if is_youtube_link:
                video_id = get_video_id(user_message)
                transcript = get_youtube_transcript(video_id) if video_id else None
                if transcript:
                    prompt_parts = [f"Summarize this YouTube video transcript:\n\n{transcript}"]
                else:
                    return jsonify({'response': "Sorry, couldn't get the transcript for that video."})
            elif matched_github_keyword:
                filename = next((fname for kw, fname in PDF_KEYWORDS.items() if kw in user_message.lower()), None)
                file_bytes = get_file_from_github(filename) if filename else None
                if file_bytes:
                    prompt_parts.append(f"\n--- Document: {filename} ---\n{extract_text_from_pdf(file_bytes)}")
                else:
                     return jsonify({'response': f"Sorry, I could not download the requested document."})
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
        return jsonify({'response': "Sorry, something went wrong. Please try again."})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Use threaded=False if you see issues with some libraries, but True is generally better for performance
    app.run(host='0.0.0.0', port=port, threaded=True)

