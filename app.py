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
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)

# --- Google Drive API Imports (using WebFlow for server environment) ---
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow # Use Flow for web apps
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload


app = Flask(__name__, template_folder='templates')

# --- Securely Load Configuration from Render Environment Variables ---
# This is CRITICAL for security. Set this in Render's .env file.
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY")
if not app.config['SECRET_KEY']:
    print("CRITICAL ERROR: FLASK_SECRET_KEY is not set. The app will not run.")
    # In a real app, you might want to sys.exit(1) here
    app.config['SECRET_KEY'] = 'dev-secret-key-for-local-testing-only' # Fallback for local dev


GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
OPENROUTER_API_KEY_V3 = os.environ.get("OPENROUTER_API_KEY_V3")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
# Load Google Drive credentials from an environment variable
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

# --- MongoDB Configuration ---
chat_history_collection = None
users_collection = None # Collection for users
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client.get_database("ai_assistant_db")
        chat_history_collection = db.get_collection("chat_history")
        users_collection = db.get_collection("users")
        print("✅ Successfully connected to MongoDB.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to MongoDB. Error: {e}")
else:
    print("CRITICAL WARNING: MONGO_URI not found. App will not function correctly.")

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect to /login if user is not authenticated

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["_id"])
        self.username = user_data["username"]
        self.password_hash = user_data["password"]

    @staticmethod
    def get(user_id):
        from bson.objectid import ObjectId
        if not users_collection: return None
        user_data = users_collection.find_one({'_id': ObjectId(user_id)})
        return User(user_data) if user_data else None

@login_manager.user_loader
def load_user(user_id):
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

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DRIVE_FILE_ID = '15iPQIg3gSq4N7eyWFto6pCEx8w1YlKCM'


# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not users_collection:
            flash('Database not connected. Please contact support.', 'error')
            return render_template('login.html')
        user_data = users_collection.find_one({'username': username})
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data)
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not users_collection:
            flash('Database not connected. Please contact support.', 'error')
            return render_template('signup.html')
        if users_collection.find_one({'username': username}):
            flash('Username already exists.', 'error')
            return redirect(url_for('signup'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        users_collection.insert_one({'username': username, 'password': hashed_password})
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('google_credentials', None) # Clear Google creds on logout
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# --- Main Application Routes ---
@app.route('/')
@login_required
def home():
    # Check if user is authorized with Google
    google_authorized = 'google_credentials' in session
    return render_template('index.html', google_authorized=google_authorized)

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
                session.pop('google_credentials', None) # Clear invalid credentials
                return None
        else:
            return None # Not authorized or no refresh token
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
    if 'google_oauth_state' not in session or session['google_oauth_state'] != request.args.get('state'):
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
        client_config, SCOPES, state=session['google_oauth_state'],
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    flow.fetch_token(authorization_response=request.url)
    session['google_credentials'] = flow.credentials.to_json()
    flash('Successfully authorized with Google Drive!', 'success')
    return redirect(url_for('home'))

@app.route('/load_drive_data')
@login_required
def load_drive_data():
    creds = get_drive_credentials()
    if not creds:
        return jsonify({'status': 'error', 'message': 'Authorization required.', 'action': 'authorize'})

    try:
        service = build('drive', 'v3', credentials=creds)
        file_request = service.files().get_media(fileId=DRIVE_FILE_ID)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, file_request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        file_content.seek(0)
        data = json.load(file_content)

        # Here you can process the loaded 'data'
        print(f"User {current_user.username} loaded data from Drive.")
        return jsonify({'status': 'success', 'message': 'Data loaded from Google Drive.'})

    except HttpError as error:
        print(f"Google Drive API Error: {error}")
        return jsonify({'status': 'error', 'message': 'Could not access Google Drive file. Please re-authorize.'})
    except Exception as e:
        print(f"Error processing Drive file: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to process file from Drive.'})

# --- Chat Logic (largely unchanged, but now user-specific) ---
@app.route('/chat', methods=['POST'])
@login_required
def chat():
    # ... (your existing chat logic, helpers like extract_text_from_pdf etc. go here) ...
    # The only change needed is in the final save-to-DB step.
    # I am including the full chat logic for completeness.

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

    # --- Main Chat Logic ---
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

            # Handle multimodal inputs
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

        # --- MODIFIED: Save to MongoDB with user ID and file data ---
        if chat_history_collection is not None and ai_response:
            try:
                # Prepare the document to be inserted
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
                
                # If a file was uploaded, add its base64 data to the document
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

