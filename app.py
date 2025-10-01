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
from bson.objectid import ObjectId # Import ObjectId
from youtube_transcript_api import YouTubeTranscriptApi
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)

app = Flask(__name__, template_folder='templates')

# --- Securely Load Configuration from Environment Variables ---
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY")

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
OPENROUTER_API_KEY_V3 = os.environ.get("OPENROUTER_API_KEY_V3")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")


# --- Configure API Services ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    print(f"✅ Loaded google-generativeai version: {genai.__version__}")
else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")

if YOUTUBE_API_KEY:
    print("✅ YouTube API Key loaded.")
else:
    print("CRITICAL WARNING: YOUTUBE_API_KEY not found. YouTube features will be disabled.")

# --- MongoDB Configuration (for chat history and user management) ---
mongo_client = None
chat_history_collection = None
users_collection = None # Collection for storing user credentials
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client.get_database("ai_assistant_db")
        chat_history_collection = db.get_collection("chat_history")
        users_collection = db.get_collection("users") # Use MongoDB for users
        print("✅ Successfully connected to MongoDB for chat history and user management.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to MongoDB. Error: {e}")
else:
    print("CRITICAL WARNING: MONGO_URI not found. Chat history and user data will not be saved.")

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = None 

class User(UserMixin):
    # User object is now created from data from MongoDB
    def __init__(self, user_data):
        self.id = str(user_data["_id"]) # Use MongoDB's _id as the unique ID
        self.email = user_data["email"]
        self.name = user_data["name"]

    @staticmethod
    def get(user_id):
        # This function is called by load_user to get a user by their ID (_id)
        if not users_collection:
            return None
        try:
            # Find user by their MongoDB ObjectId
            user_data = users_collection.find_one({"_id": ObjectId(user_id)})
            return User(user_data) if user_data else None
        except: # Handles invalid ObjectId format
            return None

@login_manager.user_loader
def load_user(user_id):
    # user_id is the _id string stored in the session
    return User.get(user_id)

# --- GitHub Configuration ---
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


# --- API-based Authentication Routes using MongoDB ---

@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password') # Plaintext password from frontend

    if not all([name, email, password]):
        return jsonify({'success': False, 'error': 'Please fill out all fields: Name, Email, and Password.'}), 400

    if not users_collection:
        return jsonify({'success': False, 'error': 'Database not configured.'}), 500

    # Check if user already exists in MongoDB
    if users_collection.find_one({"email": email}):
        return jsonify({'success': False, 'error': 'An account with this email address already exists.'}), 409

    # IMPORTANT: Storing password in plain text as requested for testing.
    # In a production environment, you should ALWAYS hash and salt passwords.
    new_user = {
        "name": name,
        "email": email,
        "password": password, 
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        # MongoDB will automatically create a unique _id for the new user
        users_collection.insert_one(new_user)
        return jsonify({'success': True})
    except Exception as e:
        print(f"MONGO_WRITE_ERROR: Failed to save new user: {e}")
        return jsonify({'success': False, 'error': 'A server error occurred while creating your account. Please try again later.'}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({'success': False, 'error': 'Please enter both email and password.'}), 400

    if not users_collection:
        return jsonify({'success': False, 'error': 'Database not configured.'}), 500
        
    user_data = users_collection.find_one({"email": email})

    # Check for user and compare plain text password
    if user_data and user_data['password'] == password:
        user_obj = User(user_data)
        login_user(user_obj) # This stores user_obj.id (which is the _id) in the session
        return jsonify({'success': True, 'user': {'name': user_data['name'], 'email': user_data['email']}})
    else:
        return jsonify({'success': False, 'error': 'The email or password you entered is incorrect.'}), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'success': True})

@app.route('/api/users/delete', methods=['POST'])
@login_required
def api_delete_user():
    if not users_collection:
        return jsonify({'success': False, 'error': 'Database not configured.'}), 500

    user_id_to_delete = current_user.id # This is now the _id string
    
    try:
        # Delete user by their MongoDB ObjectId
        result = users_collection.delete_one({'_id': ObjectId(user_id_to_delete)})
        if result.deleted_count > 0:
            logout_user()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'User not found for deletion.'}), 404
    except Exception as e:
        print(f"MONGO_DELETE_ERROR: Failed to delete user: {e}")
        return jsonify({'success': False, 'error': 'An error occurred while deleting the user.'}), 500


# --- Status Route ---
@app.route('/api/status')
def api_status():
    db_connected = False
    if mongo_client:
        try:
            # The ismaster command is cheap and does not require auth.
            mongo_client.admin.command('ismaster')
            db_connected = True
        except Exception as e:
            print(f"DB connection check failed: {e}")
            db_connected = False
    
    return jsonify({
        'database_connected': db_connected,
        'youtube_api_ready': bool(YOUTUBE_API_KEY)
    })

# --- Main Application Route ---
@app.route('/')
def home():
    # This route serves the single-page application.
    return render_template('index12.html')


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

        # --- Fetch and Prepare Chat History for All Models ---
        gemini_history = []
        openai_history = []
        if chat_history_collection is not None:
            try:
                # Fetch last 10 items (5 conversation turns)
                recent_chats = chat_history_collection.find(
                    {"user_id": ObjectId(current_user.id)}
                ).sort("timestamp", -1).limit(10)
                
                ordered_chats = list(recent_chats)[::-1]

                for chat in ordered_chats:
                    # Format for Gemini
                    gemini_history.append({'role': 'user', 'parts': [chat.get('user_message', '')]})
                    if 'ai_response' in chat:
                        gemini_history.append({'role': 'model', 'parts': [chat.get('ai_response', '')]})
                    
                    # Format for OpenAI-compatible APIs
                    openai_history.append({"role": "user", "content": chat.get('user_message', '')})
                    if 'ai_response' in chat:
                        openai_history.append({"role": "assistant", "content": chat.get('ai_response', '')})
            except Exception as e:
                print(f"Error fetching chat history from MongoDB: {e}")

        # Add the current message to the OpenAI-compatible history for this request
        openai_history.append({"role": "user", "content": user_message})

        is_multimodal = bool(file_data) or "youtube.com" in user_message or "youtu.be" in user_message or any(k in user_message.lower() for k in PDF_KEYWORDS)

        if not is_multimodal and user_message.strip():
            print("Routing to OpenRouter...")
            ai_response = call_api("https://openrouter.ai/api/v1/chat/completions",
                                   {"Authorization": f"Bearer {OPENROUTER_API_KEY_V3}"},
                                   {"model": "deepseek/deepseek-chat", "messages": openai_history},
                                   "OpenRouter")
            if ai_response:
                api_used, model_logged = "OpenRouter", "deepseek/deepseek-chat"

            if not ai_response:
                print("Routing to Groq...")
                ai_response = call_api("https://api.groq.com/openai/v1/chat/completions",
                                       {"Authorization": f"Bearer {GROQ_API_KEY}"},
                                       {"model": "llama3-8b-8192", "messages": openai_history},
                                       "Groq")
                if ai_response:
                    api_used, model_logged = "Groq", "llama3-8b-8192"

        if not ai_response:
            print("Routing to Gemini (Sofia AI)...")
            api_used, model_logged = "Gemini", "gemini-1.5-flash-latest"
            model = genai.GenerativeModel(model_logged)

            # --- Prepare the current prompt (with files if any) ---
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

            # --- Call Gemini API with the full conversation history ---
            try:
                chat_session = model.start_chat(history=gemini_history)
                response = chat_session.send_message(prompt_parts)
                ai_response = response.text
            except Exception as e:
                print(f"Error calling Gemini API: {e}")
                ai_response = "Sorry, I encountered an error trying to respond."

        if chat_history_collection is not None and ai_response:
            try:
                chat_document = {
                    "user_id": ObjectId(current_user.id), # Use the unique ObjectId of the user
                    "user_message": user_message, 
                    "ai_response": ai_response,
                    "api_used": api_used, 
                    "model_used": model_logged,
                    "has_file": bool(file_data), 
                    "file_type": file_type if file_data else None,
                    "timestamp": datetime.utcnow()
                }
                
                if file_data:
                    # Save the base64 encoded file data with the chat message
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

