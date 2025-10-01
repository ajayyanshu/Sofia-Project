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
from flask import (Flask, jsonify, render_template, request, session, redirect,
                   url_for, flash)
from PIL import Image
from pymongo import MongoClient
from youtube_transcript_api import YouTubeTranscriptApi
# werkzeug is no longer needed for hashing as per new requirements
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)

# --- Google Drive API Imports (using WebFlow for server environment) ---
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow # Use Flow for web apps
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload


app = Flask(__name__, template_folder='templates')

# --- Securely Load Configuration from Render Environment Variables ---
# This is CRITICAL for security. Set this in Render's .env file.
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY")

# NOTE: The explicit check and print statement for the secret key has been removed as requested.
# However, the application will not function correctly without it set in the environment.

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
OPENROUTER_API_KEY_V3 = os.environ.get("OPENROUTER_API_KEY_V3")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GOOGLE_DRIVE_CREDS_JSON = os.environ.get("GOOGLE_DRIVE_CREDS_JSON")


# --- Configure API Services ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    print(f"✅ Loaded google-generativeai version: {genai.__version__}")
else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")

if GOOGLE_DRIVE_CREDS_JSON:
    print("✅ Google Drive credentials loaded from environment.")
else:
    print("CRITICAL WARNING: GOOGLE_DRIVE_CREDS_JSON not found. Google Drive features will be disabled.")

# --- MongoDB Configuration (for chat history only) ---
chat_history_collection = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client.get_database("ai_assistant_db")
        chat_history_collection = db.get_collection("chat_history")
        # users_collection is no longer used, users are managed in users.json on Drive
        print("✅ Successfully connected to MongoDB for chat history.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to MongoDB. Error: {e}")
else:
    print("CRITICAL WARNING: MONGO_URI not found. Chat history will not be saved.")

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
# This prevents redirecting for API calls, instead it will return a 401 Unauthorized error
login_manager.login_view = None 

class User(UserMixin):
    # User object is now created from data from users.json
    def __init__(self, user_data):
        self.id = user_data["email"] # Use email as the unique ID
        self.email = user_data["email"]
        self.name = user_data["name"]

    @staticmethod
    def get(user_id):
        # This function is called by load_user to get a user by their ID (email)
        all_users = get_all_users_from_drive()
        user_data = next((user for user in all_users if user['email'] == user_id), None)
        return User(user_data) if user_data else None

@login_manager.user_loader
def load_user(user_id):
    # user_id is the email stored in the session
    return User.get(user_id)

# --- GitHub & Google Drive Configuration ---
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

SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_USER_DATA_FILE_ID = '15iPQIg3gSq4N7eyWFto6pCEx8w1YlKCM' 
DRIVE_CREDENTIALS_LOG_FILENAME = "users.json"


# --- Google Drive Helper Functions for users.json ---

def get_drive_service():
    """Creates and returns an authenticated Google Drive service object."""
    creds = get_drive_credentials()
    if not creds:
        return None
    try:
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Error building Drive service: {e}")
        return None

def get_all_users_from_drive():
    """Fetches and parses the users.json file from Google Drive."""
    service = get_drive_service()
    if not service:
        print("DRIVE_READ_FAIL: Could not get Drive service.")
        return []

    try:
        response = service.files().list(q=f"name='{DRIVE_CREDENTIALS_LOG_FILENAME}' and trashed=false", spaces='drive', fields='files(id)').execute()
        files = response.get('files', [])
        
        if not files:
            return [] # Return empty list if file doesn't exist

        file_id = files[0].get('id')
        request_file = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request_file)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        file_content.seek(0)
        return json.load(file_content)
    except Exception as e:
        print(f"DRIVE_READ_ERROR: Failed to get or parse users.json: {e}")
        return []

def save_all_users_to_drive(users_data):
    """Saves the provided list of users to users.json on Google Drive."""
    service = get_drive_service()
    if not service:
        print("DRIVE_WRITE_FAIL: Could not get Drive service.")
        return False

    try:
        response = service.files().list(q=f"name='{DRIVE_CREDENTIALS_LOG_FILENAME}' and trashed=false", spaces='drive', fields='files(id)').execute()
        files = response.get('files', [])
        
        updated_content_bytes = json.dumps(users_data, indent=4).encode('utf-8')
        media = MediaIoBaseUpload(io.BytesIO(updated_content_bytes), mimetype='application/json', resumable=True)

        if files:
            file_id = files[0].get('id')
            service.files().update(fileId=file_id, media_body=media).execute()
        else:
            file_metadata = {'name': DRIVE_CREDENTIALS_LOG_FILENAME}
            service.files().create(body=file_metadata, media_body=media).execute()
        
        print("DRIVE_WRITE_SUCCESS: Successfully saved users.json.")
        return True
    except Exception as e:
        print(f"DRIVE_WRITE_ERROR: Failed to save users.json: {e}")
        return False

# --- New API-based Authentication Routes ---

@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password') # Plaintext password from frontend

    if not all([name, email, password]):
        return jsonify({'success': False, 'error': 'Missing required fields.'}), 400

    all_users = get_all_users_from_drive()
    if any(user['email'] == email for user in all_users):
        return jsonify({'success': False, 'error': 'User with this email already exists.'}), 409

    new_user = {
        "name": name,
        "email": email,
        "password": password, # Storing plaintext as per the frontend logic
        "timestamp": datetime.utcnow().isoformat()
    }
    all_users.append(new_user)
    
    if save_all_users_to_drive(all_users):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Could not save new user to Drive.'}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({'success': False, 'error': 'Missing required fields.'}), 400

    all_users = get_all_users_from_drive()
    user_data = next((user for user in all_users if user['email'] == email), None)

    if user_data and user_data['password'] == password:
        user_obj = User(user_data)
        login_user(user_obj) # This creates the server-side session
        return jsonify({'success': True, 'user': {'name': user_data['name'], 'email': user_data['email']}})
    else:
        return jsonify({'success': False, 'error': 'Invalid email or password.'}), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'success': True})

@app.route('/api/users/delete', methods=['POST'])
@login_required
def api_delete_user():
    user_email_to_delete = current_user.id
    all_users = get_all_users_from_drive()
    
    # Filter out the user to be deleted
    updated_users = [user for user in all_users if user.get('email') != user_email_to_delete]
    
    if len(updated_users) < len(all_users):
        if save_all_users_to_drive(updated_users):
            logout_user()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Could not update user list in Drive.'}), 500
    else:
        return jsonify({'success': False, 'error': 'User not found for deletion.'}), 404


# --- Main Application Route ---
@app.route('/')
def home():
    # This route now simply serves the single-page application.
    # It is no longer protected by @login_required.
    return render_template('index.html')


# --- Google Drive Integration Routes ---
def get_drive_credentials():
    creds = None
    if 'google_credentials' in session:
        creds_info = json.loads(session['google_credentials'])
        creds = Credentials.from_authorized_user_info(creds_info, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                session['google_credentials'] = creds.to_json()
            except Exception as e:
                print(f"Error refreshing Google token: {e}")
                session.pop('google_credentials', None) 
                return None
        else:
            return None 
    return creds


@app.route('/authorize_google')
@login_required
def authorize_google():
    if not GOOGLE_DRIVE_CREDS_JSON:
        flash('Google credentials configuration is missing on the server.', 'error')
        return redirect(url_for('home'))
    try:
        client_config = json.loads(GOOGLE_DRIVE_CREDS_JSON)
    except json.JSONDecodeError:
        flash('Invalid Google credentials format in environment variable.', 'error')
        return redirect(url_for('home'))

    flow = Flow.from_client_config(
        client_config, SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['google_oauth_state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session.get('google_oauth_state')
    if not state or state != request.args.get('state'):
        flash('OAuth state mismatch. Please try authorizing again.', 'error')
        return redirect(url_for('home'))

    if not GOOGLE_DRIVE_CREDS_JSON:
        flash('Google credentials configuration is missing on the server.', 'error')
        return redirect(url_for('home'))
    try:
        client_config = json.loads(GOOGLE_DRIVE_CREDS_JSON)
    except json.JSONDecodeError:
        flash('Invalid Google credentials format in environment variable.', 'error')
        return redirect(url_for('home'))

    flow = Flow.from_client_config(
        client_config, SCOPES, state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    try:
        flow.fetch_token(authorization_response=request.url)
        session['google_credentials'] = flow.credentials.to_json()
        flash('Successfully authorized with Google Drive!', 'success')
    except Exception as e:
        flash(f'Failed to fetch Google token: {e}', 'error')
    return redirect(url_for('home'))

@app.route('/load_drive_data')
@login_required
def load_drive_data():
    creds = get_drive_credentials()
    if not creds:
        return jsonify({'status': 'error', 'message': 'Authorization required.', 'action': 'authorize'})

    try:
        service = build('drive', 'v3', credentials=creds)
        file_request = service.files().get_media(fileId=DRIVE_USER_DATA_FILE_ID)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, file_request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        file_content.seek(0)
        data = json.load(file_content)

        print(f"User {current_user.name} loaded data from Drive.")
        return jsonify({'status': 'success', 'message': 'Data loaded from Google Drive.'})

    except HttpError as error:
        print(f"Google Drive API Error: {error}")
        return jsonify({'status': 'error', 'message': 'Could not access Google Drive file. Please re-authorize.'})
    except Exception as e:
        print(f"Error processing Drive file: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to process file from Drive.'})

# --- Chat Logic ---
@app.route('/chat', methods=['POST'])
@login_required
def chat():
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
            return response.content
        except requests.exceptions.RequestException as e:
            print(f"Error downloading from GitHub: {e}")
            return None

    def get_video_id(video_url):
        match = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})", video_url)
        return match.group(1) if match else None

    def get_youtube_transcript(video_id):
        try:
            return " ".join([d['text'] for d in YouTubeTranscriptApi.get_transcript(video_id)])
        except Exception as e:
            print(f"Error getting YouTube transcript: {e}")
            return None

    def call_api(url, headers, json_payload, api_name):
        try:
            response = requests.post(url, headers=headers, json=json_payload)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"Error calling {api_name} API: {e}")
            return None

    try:
        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType', '')
        ai_response, api_used, model_logged = None, "", ""

        is_multimodal = bool(file_data) or "youtube.com" in user_message or "youtu.be" in user_message or any(k in user_message.lower() for k in PDF_KEYWORDS)

        if not is_multimodal and user_message.strip():
            print("Routing to OpenRouter...")
            ai_response = call_api("https://openrouter.ai/api/v1/chat/completions",
                                   {"Authorization": f"Bearer {OPENROUTER_API_KEY_V3}"},
                                   {"model": "deepseek/deepseek-chat", "messages": [{"role": "user", "content": user_message}]},
                                   "OpenRouter")
            if ai_response:
                api_used, model_logged = "OpenRouter", "deepseek/deepseek-chat"

            if not ai_response:
                print("Routing to Groq...")
                ai_response = call_api("https://api.groq.com/openai/v1/chat/completions",
                                       {"Authorization": f"Bearer {GROQ_API_KEY}"},
                                       {"model": "llama3-8b-8192", "messages": [{"role": "user", "content": user_message}]},
                                       "Groq")
                if ai_response:
                    api_used, model_logged = "Groq", "llama3-8b-8192"

        if not ai_response:
            print("Routing to Gemini...")
            api_used, model_logged = "Gemini", "gemini-1.5-flash-latest"
            model = genai.GenerativeModel(model_logged)
            prompt_parts = [user_message] if user_message else []

            if "youtube.com" in user_message or "youtu.be" in user_message:
                video_id = get_video_id(user_message)
                transcript = get_youtube_transcript(video_id) if video_id else None
                if transcript: prompt_parts = [f"Summarize this YouTube video transcript:\n\n{transcript}"]
                else: return jsonify({'response': "Sorry, couldn't get the transcript."})
            elif any(k in user_message.lower() for k in PDF_KEYWORDS):
                fname = next((fname for kw, fname in PDF_KEYWORDS.items() if kw in user_message.lower()), None)
                fbytes = get_file_from_github(fname)
                if fbytes: prompt_parts.append(f"\n--- Document ---\n{extract_text_from_pdf(fbytes)}")
                else: return jsonify({'response': f"Sorry, could not download '{fname}'."})
            elif file_data:
                fbytes = base64.b64decode(file_data)
                if 'pdf' in file_type: prompt_parts.append(extract_text_from_pdf(fbytes))
                elif 'word' in file_type: prompt_parts.append(extract_text_from_docx(fbytes))
                elif 'image' in file_type: prompt_parts.append(Image.open(io.BytesIO(fbytes)))

            if not prompt_parts: return jsonify({'response': "Please ask a question or upload a file."})
            if isinstance(prompt_parts[-1], Image.Image) and not any(isinstance(p, str) and p.strip() for p in prompt_parts):
                prompt_parts.insert(0, "Describe this image.")

            response = model.generate_content(prompt_parts)
            ai_response = response.text

        if chat_history_collection is not None and ai_response:
            try:
                chat_document = {
                    "user_id": current_user.id,
                    "user_message": user_message, 
                    "ai_response": ai_response,
                    "api_used": api_used, 
                    "model_used": model_logged,
                    "has_file": bool(file_data), 
                    "file_type": file_type if file_data else None,
                    "timestamp": datetime.utcnow()
                }
                
                if file_data:
                    chat_document['file_data'] = file_data

                chat_history_collection.insert_one(chat_document)

            except Exception as e:
                print(f"Error saving chat to MongoDB: {e}")

        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"A critical error occurred in /chat: {e}")
        return jsonify({'response': "Sorry, an internal error occurred."})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

