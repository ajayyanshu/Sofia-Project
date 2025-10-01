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
from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from PIL import Image
from pymongo import MongoClient
from youtube_transcript_api import YouTubeTranscriptApi

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest

app = Flask(__name__, template_folder='templates')

# --- Configuration ---
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a-very-secret-key-for-development")
GOOGLE_DRIVE_CREDS_JSON = os.environ.get("GOOGLE_DRIVE_CREDS_JSON")
MONGO_URI = os.environ.get("MONGO_URI")
# This is the specific file ID for your user database
USER_DATA_FILE_ID = '1G86soMom_Ifbfg7liqtBWWzdr9ChtZoU'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/drive.file']

# --- API Keys (for other features) ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
OPENROUTER_API_KEY_V3 = os.environ.get("OPENROUTER_API_KEY_V3")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# --- Configure API Services ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    print("✅ google-generativeai configured.")
else:
    print("WARNING: GOOGLE_API_KEY not found.")

if not GOOGLE_DRIVE_CREDS_JSON:
    print("CRITICAL ERROR: GOOGLE_DRIVE_CREDS_JSON environment variable not set. User login will fail.")

# --- MongoDB Configuration ---
chat_history_collection = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client.get_database("ai_assistant_db")
        chat_history_collection = db.get_collection("chat_history")
        print("✅ Successfully connected to MongoDB.")
    except Exception as e:
        print(f"ERROR: Could not connect to MongoDB. Error: {e}")
else:
    print("WARNING: MONGO_URI not found. Chat history will not be saved.")

# --- Google Drive Helper Functions ---
def get_google_flow(redirect_uri):
    if not GOOGLE_DRIVE_CREDS_JSON:
        raise ValueError("Google OAuth environment variable is not configured.")
    client_config = json.loads(GOOGLE_DRIVE_CREDS_JSON)
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)

def get_drive_service(creds_info=None):
    creds = None
    if creds_info:
        creds = Credentials.from_authorized_user_info(creds_info, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        else:
            # This case is for server-to-server interaction if needed,
            # but for user data we rely on user's authorized session.
            return None 
    return build('drive', 'v3', credentials=creds)

# --- Routes ---
@app.route('/')
def index():
    # The main page is now the login/chat interface
    return render_template('index.html')

# --- User Management API (The New Part) ---
@app.route('/users', methods=['GET', 'POST'])
def handle_users():
    # For this operation, the app needs its own credentials, not the user's.
    # We will use the main Google Drive connection for this.
    # A user must be logged in to Google via OAuth to provide the service.
    if 'google_credentials' not in session:
        return jsonify({"error": "Application not authorized. Please connect to Google Drive first."}), 403

    try:
        service = get_drive_service(session['google_credentials'])
        if not service:
            return jsonify({"error": "Could not create Google Drive service."}), 500

        if request.method == 'GET':
            # Download the user data file from Google Drive
            request_download = service.files().get_media(fileId=USER_DATA_FILE_ID)
            file_bytes_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_bytes_io, request_download)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            users_json = file_bytes_io.getvalue().decode('utf-8')
            return jsonify(json.loads(users_json))

        if request.method == 'POST':
            # Get the new user list from the frontend
            updated_users = request.get_json()
            
            # Prepare the new file content
            new_content = json.dumps(updated_users, indent=2).encode('utf-8')
            media_body = MediaFileUpload(io.BytesIO(new_content), mimetype='application/json')
            
            # Update the existing file in Google Drive
            service.files().update(
                fileId=USER_DATA_FILE_ID,
                media_body=media_body
            ).execute()
            
            return jsonify({"success": True, "message": "Users updated successfully."})

    except HttpError as error:
        print(f"An HTTP error occurred: {error}")
        return jsonify({"error": f"Google Drive API error: {error.reason}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


# --- Google Drive OAuth Routes (for file listing feature) ---
@app.route('/authorize_google_drive')
def authorize_google_drive():
    redirect_uri = url_for('oauth2callback', _external=True, _scheme='https')
    flow = get_google_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session.get('state')
    if not state or state != request.args.get('state'):
        return 'State mismatch error.', 400
    
    redirect_uri = url_for('oauth2callback', _external=True, _scheme='https')
    flow = get_google_flow(redirect_uri)
    flow.fetch_token(authorization_response=request.url.replace('http://', 'https://')) # Fix for Render proxy
    creds = flow.credentials
    
    session['google_credentials'] = {
        'token': creds.token, 'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri, 'client_id': creds.client_id,
        'client_secret': creds.client_secret, 'scopes': creds.scopes
    }
    return redirect(url_for('index')) # Redirect back to the main app

@app.route('/disconnect_google_drive')
def disconnect_google_drive():
    session.pop('google_credentials', None)
    return redirect(url_for('index'))

@app.route('/list_drive_files')
def list_drive_files():
    if 'google_credentials' not in session:
        return jsonify({"error": "User not authenticated with Google Drive."}), 401
    
    try:
        service = get_drive_service(session['google_credentials'])
        results = service.files().list(
            pageSize=15, fields="files(id, name, webViewLink, iconLink)").execute()
        files = results.get('files', [])
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Use threaded=True for development to handle multiple requests
    app.run(host='0.0.0.0', port=port, threaded=True)

