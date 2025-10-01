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
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest


app = Flask(__name__, template_folder='templates')

# --- Securely Load API Keys from Render Environment ---
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-for-prod")
GOOGLE_DRIVE_CREDS_JSON = os.environ.get("GOOGLE_DRIVE_CREDS_JSON")
# The REDIRECT_URI is now generated automatically and does not need to be set as an environment variable.

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
OPENROUTER_API_KEY_V3 = os.environ.get("OPENROUTER_API_KEY_V3")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

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

# --- Improved check for Google Drive configuration ---
if not GOOGLE_DRIVE_CREDS_JSON:
    print("ERROR: GOOGLE_DRIVE_CREDS_JSON environment variable is not set. Drive integration is disabled.")


# --- MongoDB Configuration ---
chat_history_collection = None
if MONGO_URI: # Corrected typo from MONRO_URI to MONGO_URI
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
def get_google_flow(redirect_uri):
    if not GOOGLE_DRIVE_CREDS_JSON:
        raise ValueError("Google OAuth environment variable is not configured.")
    try:
        client_config = json.loads(GOOGLE_DRIVE_CREDS_JSON)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in GOOGLE_DRIVE_CREDS_JSON.")
    
    if redirect_uri not in client_config.get("web", {}).get("redirect_uris", []):
         print(f"WARNING: The dynamically generated REDIRECT_URI '{redirect_uri}' is not in the list of authorized URIs in your credentials JSON. You must add it in the Google Cloud Console.")

    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)

# --- Routes ---
@app.route('/')
def home():
    files = []
    is_connected = False
    specific_file_content = None
    error_message = None

    if 'google_credentials' in session:
        try:
            creds = Credentials.from_authorized_user_info(session['google_credentials'], SCOPES)
            
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                session['google_credentials'] = {
                    'token': creds.token, 'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri, 'client_id': creds.client_id,
                    'client_secret': creds.client_secret, 'scopes': creds.scopes
                }

            service = build('drive', 'v3', credentials=creds)
            
            # 1. List recent files
            results = service.files().list(
                pageSize=15, fields="files(id, name, webViewLink, iconLink)").execute()
            files = results.get('files', [])
            is_connected = True

            # 2. Get specific file content by ID
            file_id = '1G86soMom_Ifbfg7liqtBWWzdr9ChtZoU'
            try:
                # Get file metadata to check the MIME type
                file_metadata = service.files().get(fileId=file_id, fields='mimeType, name').execute()
                file_name = file_metadata.get('name', 'Unknown File')
                mime_type = file_metadata.get('mimeType')

                # Download the file content
                request_download = service.files().get_media(fileId=file_id)
                file_bytes_io = io.BytesIO()
                downloader = MediaIoBaseDownload(file_bytes_io, request_download)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                
                file_bytes = file_bytes_io.getvalue()

                # Extract text based on file type
                if 'pdf' in mime_type:
                    specific_file_content = f"Content of '{file_name}':\n\n{extract_text_from_pdf(file_bytes)}"
                elif 'vnd.openxmlformats-officedocument.wordprocessingml.document' in mime_type:
                    specific_file_content = f"Content of '{file_name}':\n\n{extract_text_from_docx(file_bytes)}"
                else:
                    specific_file_content = f"Cannot display content for this file type ({mime_type})."

            except HttpError as error:
                print(f"An error occurred while fetching the specific file: {error}")
                error_message = f"Could not access file. Please ensure the file ID is correct and you have permission to view it. Error: {error.reason}"
            
        except Exception as e:
            print(f"Error accessing Google Drive: {e}")
            session.pop('google_credentials', None) # Log out on error
            error_message = "An error occurred while connecting to Google Drive. Please try connecting again."
            
    return render_template('index.html', files=files, is_connected=is_connected, specific_file_content=specific_file_content, error_message=error_message)


@app.route('/authorize_google_drive')
def authorize_google_drive():
    if not GOOGLE_DRIVE_CREDS_JSON:
         return "Application is not configured for Google Drive. Administrator needs to set GOOGLE_DRIVE_CREDS_JSON environment variable.", 500
    try:
        # Dynamically generate the full callback URL
        redirect_uri = url_for('oauth2callback', _external=True)
        flow = get_google_flow(redirect_uri)
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
        # Dynamically generate the same callback URL for token fetching
        redirect_uri = url_for('oauth2callback', _external=True)
        flow = get_google_flow(redirect_uri)
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        
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
        return f"[Error extracting PDF: {e}]"


def extract_text_from_docx(docx_bytes):
    try:
        document = docx.Document(io.BytesIO(docx_bytes))
        return "\n".join([para.text for para in document.paragraphs])
    except Exception as e:
        print(f"Error extracting DOCX text: {e}")
        return f"[Error extracting DOCX: {e}]"


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
    video_id_match = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})", video_url)
    return video_id_match.group(1) if video_id_match else None


def get_youtube_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([d['text'] for d in transcript_list])
    except Exception as e:
        print(f"Error getting YouTube transcript: {e}")
        return None

# --- Main Chat Logic (Remains the same) ---
@app.route('/chat', methods=['POST'])
def chat():
    # ... existing chat code ...
    try:
        data = request.json
        user_message = data.get('text', '')
        # ... rest of the chat logic ...
        return jsonify({'response': "Chat response placeholder"})
    except Exception as e:
        print(f"A critical error occurred in chat: {e}")
        return jsonify({'response': "Sorry, something went wrong in the chat."})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)

