import base64
import io
import os
import re
import sys
import json
from datetime import datetime, date, timedelta
import uuid
import random
from threading import Thread

import docx
import fitz  # PyMuPDF
import google.generativeai as genai
import requests
from flask import (Flask, jsonify, render_template, request, session, redirect,
                   url_for, flash, make_response)
from flask_cors import CORS
from PIL import Image
from pymongo import MongoClient
from bson.objectid import ObjectId
from youtube_transcript_api import YouTubeTranscriptApi
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_mail import Mail, Message
# werkzeug.security is no longer needed for hashing
# from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='templates')
CORS(app)

# --- Configuration ---
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key") # Use default if not set
app.config['SECRET_KEY'] = SECRET_KEY
if SECRET_KEY == "dev-secret-key":
    print("CRITICAL WARNING: Using a default, insecure FLASK_SECRET_KEY for development.")

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ajay@123.com") # Admin email configuration

# --- Email Configuration ---
# NOTE: Using Gmail's SMTP is recommended for cloud hosting like Render.
# You will need to generate a Google App Password for this to work.
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD') # Use a Google App Password here
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

mail = Mail(app)

def send_async_email(app, msg):
    """Sends an email in a background thread to prevent request timeouts."""
    with app.app_context():
        try:
            mail.send(msg)
            print("✅ Email sent successfully in background.")
        except Exception as e:
            print(f"BACKGROUND_EMAIL_ERROR: {e}")

# --- API Services Configuration ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    print(f"✅ Loaded google-generativeai version: {genai.__version__}")
else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")

if YOUTUBE_API_KEY:
    print("✅ YouTube API Key loaded.")
else:
    print("CRITICAL WARNING: YOUTUBE_API_KEY not found. YouTube features will be disabled.")

# --- MongoDB Configuration ---
mongo_client = None
chat_history_collection = None
temporary_chat_collection = None
users_collection = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client.get_database("ai_assistant_db")
        # --- Add a connection test (ping) ---
        db.command('ping')
        print("✅ Successfully pinged MongoDB.")
        # --- End of added code ---
        chat_history_collection = db.get_collection("chat_history")
        temporary_chat_collection = db.get_collection("temporary_chats")
        users_collection = db.get_collection("users")
        print("✅ Successfully connected to MongoDB.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to MongoDB. Error: {e}")
else:
    print("CRITICAL WARNING: MONGO_URI not found. Data will not be saved.")

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["_id"])
        self.email = user_data.get("email")
        self.name = user_data.get("name")
        self.isAdmin = user_data.get("isAdmin", False)
        self.isPremium = user_data.get("isPremium", False)
        self.session_id = user_data.get("session_id")


    @staticmethod
    def get(user_id):
        if users_collection is None:
            return None
        try:
            user_data = users_collection.find_one({"_id": ObjectId(user_id)})
            return User(user_data) if user_data else None
        except:
            return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.before_request
def before_request_callback():
    if current_user.is_authenticated:
        if session.get('session_id') != current_user.session_id:
            logout_user()
            flash("You have been logged out from another device.", "info")
            return redirect(url_for('login_page'))


# --- GitHub Configuration ---
# NOTE: You need to configure these environment variables if you want to use the PDF keyword feature
GITHUB_USER = os.environ.get("GITHUB_USER")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
GITHUB_FOLDER_PATH = os.environ.get("GITHUB_FOLDER_PATH", "") # Default to root if not set

# This dictionary maps keywords to specific PDF filenames in your GitHub repo.
# When a user's message contains a keyword, the corresponding file will be fetched.
PDF_KEYWORDS = {
    # "keyword": "filename.pdf"
    # Example:
    # "privacy policy": "Privacy Policy.pdf",
    # "terms of service": "Terms of Service.pdf"
}


# --- Page Rendering Routes ---

@app.route('/')
@login_required
def home():
    """Renders the main chat application."""
    return render_template('index.html') 

@app.route('/login.html', methods=['GET'])
def login_page():
    """Renders the login page."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/signup.html', methods=['GET'])
def signup_page():
    """Renders the signup page."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('signup.html')

# Add Redirects for cleaner URLs
@app.route('/login')
def login_redirect():
    return redirect(url_for('login_page'))

@app.route('/signup')
def signup_redirect():
    return redirect(url_for('signup_page'))


# --- API Authentication Routes ---

@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not all([name, email, password]):
        return jsonify({'success': False, 'error': 'Please fill out all fields.'}), 400

    if users_collection is None:
        return jsonify({'success': False, 'error': 'Database not configured.'}), 500

    if users_collection.find_one({"email": email}):
        return jsonify({'success': False, 'error': 'An account with this email already exists.'}), 409

    # Storing the password in plain text. This is NOT recommended.
    # hashed_password = generate_password_hash(password)

    new_user = {
        "name": name, "email": email, "password": password,
        "isAdmin": email == ADMIN_EMAIL, "isPremium": False, "is_verified": True, # User is verified by default now
        "session_id": str(uuid.uuid4()),
        "usage_counts": { "messages": 0, "webSearches": 0 },
        "last_usage_reset": datetime.utcnow().strftime('%Y-%m-%d'),
        "timestamp": datetime.utcnow().isoformat()
    }
    users_collection.insert_one(new_user)

    return jsonify({'success': True, 'message': 'Account created successfully!'})


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({'success': False, 'error': 'Please enter both email and password.'}), 400

    if users_collection is None:
        return jsonify({'success': False, 'error': 'Database not configured.'}), 500
        
    user_data = users_collection.find_one({"email": email})

    # Plain text password comparison.
    if user_data and user_data.get('password') == password:
        # Removed the 'is_verified' check
        new_session_id = str(uuid.uuid4())
        users_collection.update_one({'_id': user_data['_id']}, {'$set': {'session_id': new_session_id}})
        user_data['session_id'] = new_session_id

        user_obj = User(user_data)
        login_user(user_obj)
        session['session_id'] = new_session_id
        return jsonify({'success': True, 'user': {'name': user_data['name'], 'email': user_data['email']}})
    else:
        return jsonify({'success': False, 'error': 'Incorrect email or password.'}), 401

@app.route('/api/request_password_reset', methods=['POST'])
def request_password_reset():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'success': False, 'error': 'Email is required.'}), 400

    user = users_collection.find_one({"email": email})
    if not user:
        # Don't reveal if a user exists or not for security reasons
        return jsonify({'success': True, 'message': 'If an account with that email exists, a password reset link has been sent.'})

    reset_token = uuid.uuid4().hex
    token_expiry = datetime.utcnow() + timedelta(hours=1)
    
    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {'password_reset_token': reset_token, 'reset_token_expires_at': token_expiry}}
    )
    
    # Construct the reset URL
    reset_url = url_for('home', _external=True) + f'reset-password?token={reset_token}'
    
    try:
        msg = Message("Password Reset Request", recipients=[email])
        msg.body = f"Click the following link to reset your password: {reset_url}\nThis link will expire in 1 hour."
        Thread(target=send_async_email, args=(app, msg)).start()
    except Exception as e:
        print(f"PASSWORD_RESET_EMAIL_ERROR: {e}")
        return jsonify({'success': False, 'error': 'Failed to send reset email.'}), 500
        
    return jsonify({'success': True, 'message': 'If an account with that email exists, a password reset link has been sent.'})

@app.route('/api/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    token = data.get('token')
    new_password = data.get('new_password')

    if not all([token, new_password]):
        return jsonify({'success': False, 'error': 'Token and new password are required.'}), 400

    user = users_collection.find_one({
        "password_reset_token": token,
        "reset_token_expires_at": {"$gt": datetime.utcnow()}
    })

    if not user:
        return jsonify({'success': False, 'error': 'Invalid or expired token.'}), 400
        
    # Storing the new password in plain text.
    # hashed_password = generate_password_hash(new_password)
    users_collection.update_one(
        {'_id': user['_id']},
        {
            '$set': {'password': new_password},
            '$unset': {'password_reset_token': "", 'reset_token_expires_at': ""}
        }
    )
    
    return jsonify({'success': True, 'message': 'Password has been reset successfully.'})

@app.route('/get_user_info')
@login_required
def get_user_info():
    """Provides user information to the front-end after login."""
    return jsonify({
        "name": current_user.name,
        "email": current_user.email,
        "isAdmin": current_user.isAdmin,
        "isPremium": current_user.isPremium
    })

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True})

@app.route('/logout-all', methods=['POST'])
@login_required
def logout_all_devices():
    """Invalidates all other sessions for the current user."""
    if users_collection is None:
        return jsonify({'success': False, 'error': 'Database not configured.'}), 500

    try:
        new_session_id = str(uuid.uuid4())
        users_collection.update_one({'_id': ObjectId(current_user.id)}, {'$set': {'session_id': new_session_id}})
        logout_user()
        return jsonify({'success': True, 'message': 'Successfully logged out of all devices.'})
    except Exception as e:
        print(f"LOGOUT_ALL_ERROR: {e}")
        return jsonify({'success': False, 'error': 'Server error during logout.'}), 500

@app.route('/2fa/setup', methods=['POST'])
@login_required
def setup_2fa():
    return jsonify({'success': False, 'message': '2FA setup is not yet implemented.'}), 501

@app.route('/delete-account', methods=['DELETE'])
@login_required
def delete_account():
    if users_collection is None:
        return jsonify({'success': False, 'error': 'Database not configured.'}), 500

    try:
        user_id = ObjectId(current_user.id)
        
        # Anonymize user details by replacing personal info and removing session/name
        update_result = users_collection.update_one(
            {'_id': user_id},
            {
                '$set': {
                    'email': f'deleted_{user_id}@anonymous.com',
                    'password': 'deleted_password_placeholder' 
                },
                '$unset': {
                    'name': "",
                    'session_id': ""
                }
            }
        )

        if update_result.matched_count > 0:
            logout_user()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'User not found.'}), 404
    except Exception as e:
        print(f"MONGO_DELETE_ERROR: {e}")
        return jsonify({'success': False, 'error': 'Error deleting user details.'}), 500


# --- Status Route ---
@app.route('/status', methods=['GET'])
def status():
    """Provides a simple status check for the server."""
    return jsonify({'status': 'ok'}), 200

# --- Chat Logic ---
@app.route('/chat', methods=['POST'])
@login_required
def chat():
    # --- Daily Usage Limit Check and Reset ---
    if not current_user.isPremium and not current_user.isAdmin:
        user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
        
        last_reset_str = user_data.get('last_usage_reset', '1970-01-01')
        last_reset_date = datetime.strptime(last_reset_str, '%Y-%m-%d').date()
        today = datetime.utcnow().date()

        if last_reset_date < today:
            users_collection.update_one(
                {'_id': ObjectId(current_user.id)},
                {'$set': {'usage_counts.messages': 0, 'last_usage_reset': today.strftime('%Y-%m-%d')}}
            )
            user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
        
        usage = user_data.get('usage_counts', {})
        messages_used = usage.get('messages', 0)
        
        if messages_used >= 15:
            return jsonify({
                'error': 'You have reached your daily message limit. Please upgrade for unlimited access.',
                'upgrade_required': True
            }), 429
            
        users_collection.update_one({'_id': ObjectId(current_user.id)}, {'$inc': {'usage_counts.messages': 1}})

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
        if not all([GITHUB_USER, GITHUB_REPO]):
            print("CRITICAL WARNING: GITHUB_USER or GITHUB_REPO is not configured.")
            return None
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
            print(f"Attempting to call {api_name} API at {url}...")
            response = requests.post(url, headers=headers, json=json_payload)
            response.raise_for_status()
            result = response.json()
            print(f"Successfully received response from {api_name}.")
            return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"Error calling {api_name} API: {e}")
            return None

    try:
        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType', '')
        is_temporary = data.get('isTemporary', False)
        ai_response, api_used, model_logged = None, "", ""

        gemini_history = []
        openai_history = []
        if chat_history_collection is not None and not is_temporary:
            try:
                # Fetch history only for normal chats
                recent_chats = chat_history_collection.find(
                    {"user_id": ObjectId(current_user.id)}
                ).sort("timestamp", -1).limit(10)
                
                ordered_chats = list(recent_chats)[::-1]

                for chat in ordered_chats:
                    gemini_history.append({'role': 'user', 'parts': [chat.get('user_message', '')]})
                    if 'ai_response' in chat:
                        gemini_history.append({'role': 'model', 'parts': [chat.get('ai_response', '')]})
                    
                    openai_history.append({"role": "user", "content": chat.get('user_message', '')})
                    if 'ai_response' in chat:
                        openai_history.append({"role": "assistant", "content": chat.get('ai_response', '')})
            except Exception as e:
                print(f"Error fetching chat history from MongoDB: {e}")

        openai_history.append({"role": "user", "content": user_message})

        is_multimodal = bool(file_data) or "youtube.com" in user_message or "youtu.be" in user_message or any(k in user_message.lower() for k in PDF_KEYWORDS)

        if not is_multimodal and user_message.strip():
            ai_response = None
            if not ai_response and GROQ_API_KEY:
                print("Routing to Groq...")
                ai_response = call_api("https://api.groq.com/openai/v1/chat/completions",
                                       {"Authorization": f"Bearer {GROQ_API_KEY}"},
                                       {"model": "llama-3.1-8b-instant", "messages": openai_history},
                                       "Groq")
                if ai_response:
                    api_used, model_logged = "Groq", "llama-3.1-8b-instant"

        if not ai_response:
            print("Routing to Gemini (Sofia AI)...")
            api_used, model_logged = "Gemini", "gemini-2.5-pro"
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
            
            try:
                full_prompt = gemini_history + [{'role': 'user', 'parts': prompt_parts}]
                response = model.generate_content(full_prompt)
                ai_response = response.text
            except Exception as e:
                print(f"Error calling Gemini API with history: {e}")
                try:
                    print("Retrying Gemini call without history...")
                    response = model.generate_content(prompt_parts)
                    ai_response = response.text
                except Exception as e2:
                    print(f"Error calling Gemini API on retry: {e2}")
                    ai_response = "Sorry, I encountered an error trying to respond."

        if ai_response:
            try:
                # If it's a temporary chat, save to the temporary collection
                if is_temporary and temporary_chat_collection is not None:
                    temp_chat_document = {
                        "user_id": ObjectId(current_user.id),
                        "user_message": user_message,
                        "ai_response": ai_response,
                        "api_used": api_used,
                        "model_used": model_logged,
                        "timestamp": datetime.utcnow()
                    }
                    temporary_chat_collection.insert_one(temp_chat_document)
                # Otherwise (it's a normal chat), save to the main history collection
                elif not is_temporary and chat_history_collection is not None:
                    chat_document = {
                        "user_id": ObjectId(current_user.id),
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
        import traceback
        traceback.print_exc()
        return jsonify({'response': "Sorry, an internal error occurred."})

# --- Save Chat History Route ---
@app.route('/save_chat_history', methods=['POST'])
@login_required
def save_chat_history():
    """Fetches user's chat history and returns it as an HTML file."""
    if chat_history_collection is None:
        return jsonify({'success': False, 'error': 'Database not configured.'}), 500

    try:
        user_id = ObjectId(current_user.id)
        user_name = current_user.name
        history_cursor = chat_history_collection.find({"user_id": user_id}).sort("timestamp", 1)

        # Start building the HTML content
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat History for {user_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f2f5;
            color: #1c1e21;
        }}
        .container {{
            max-width: 800px;
            margin: auto;
            background: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            color: #333;
            border-bottom: 2px solid #ccc;
            padding-bottom: 10px;
        }}
        .message-container {{
            margin-bottom: 20px;
        }}
        .message {{
            padding: 10px 15px;
            border-radius: 18px;
            max-width: 75%;
            word-wrap: break-word;
        }}
        .user-message-container {{
            display: flex;
            justify-content: flex-end;
        }}
        .user-message .message {{
            background-color: #0084ff;
            color: white;
            border-bottom-right-radius: 4px;
        }}
        .ai-message-container {{
            display: flex;
            justify-content: flex-start;
        }}
        .ai-message .message {{
            background-color: #e4e6eb;
            color: #050505;
            border-bottom-left-radius: 4px;
        }}
        .timestamp {{
            font-size: 0.75rem;
            color: #65676b;
            margin: 5px 0;
        }}
        .user-message .timestamp {{ text-align: right; }}
        .ai-message .timestamp {{ text-align: left; }}
        .label {{
            font-weight: bold;
            font-size: 0.8rem;
            color: #65676b;
            margin-bottom: 4px;
        }}
        .user-message .label {{ text-align: right; margin-right: 5px;}}
        .ai-message .label {{ text-align: left; margin-left: 5px;}}
    </style>
</head>
<body>
    <div class="container">
        <h1>Chat History</h1>
        <h2>User: {user_name}</h2>
"""

        # Loop through chat history and append to HTML
        for chat in history_cursor:
            user_msg = chat.get('user_message', '').replace('<', '&lt;').replace('>', '&gt;')
            ai_msg = chat.get('ai_response', '').replace('<', '&lt;').replace('>', '&gt;')
            timestamp = chat.get('timestamp').strftime("%Y-%m-%d %H:%M:%S UTC")

            html_content += f"""
        <div class="message-container user-message-container">
            <div class="user-message">
                <div class="label">You</div>
                <div class="message">{user_msg}</div>
                <div class="timestamp">{timestamp}</div>
            </div>
        </div>
        <div class="message-container ai-message-container">
            <div class="ai-message">
                <div class="label">Sofia AI</div>
                <div class="message">{ai_msg}</div>
                <div class="timestamp">{timestamp}</div>
            </div>
        </div>
"""

        # Close HTML tags
        html_content += """
    </div>
</body>
</html>
"""

        # Create response and set headers for download
        response = make_response(html_content)
        response.headers["Content-Disposition"] = "attachment; filename=chat_history.html"
        response.headers["Content-Type"] = "text/html"
        return response

    except Exception as e:
        print(f"Error generating chat history HTML: {e}")
        return jsonify({'success': False, 'error': 'Failed to generate chat history.'}), 500

# --- Live AI Camera Feature (Backend) ---
@app.route('/live_object_detection', methods=['POST'])
@login_required
def live_object_detection():
    data = request.get_json()
    if not data or 'image_data' not in data:
        return jsonify({'error': 'No image data provided.'}), 400

    image_data = data['image_data']
    try:
        image_bytes = base64.b64decode(image_data.split(',')[1])
        img = Image.open(io.BytesIO(image_bytes))

        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(["Describe the objects you see in this image.", img])
        
        return jsonify({'description': response.text})

    except Exception as e:
        print(f"Error in live object detection: {e}")
        return jsonify({'error': 'Failed to process image.'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
