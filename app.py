import base64
import io
import os
import re
import sys
import json
from datetime import datetime, date, timedelta
import uuid
import random

import docx
import fitz  # PyMuPDF
import google.generativeai as genai
import requests
from flask import (Flask, jsonify, render_template, request, session, redirect,
                   url_for, flash)
from flask_cors import CORS
from PIL import Image
from pymongo import MongoClient
from bson.objectid import ObjectId
from youtube_transcript_api import YouTubeTranscriptApi
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_mail import Mail, Message

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
OPENROUTER_API_KEY_V3 = os.environ.get("OPENROUTER_API_KEY_V3")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ajay@123.com") # Admin email configuration

# --- Email Configuration ---
# =====================================================================================
# IMPORTANT: Platform-Specific Email Configuration (e.g., for Render, Heroku, etc.)
#
# Direct SMTP connections (especially to services like Proton Mail) often fail on cloud
# platforms because they have special requirements (like the Proton Mail Bridge) that
# CANNOT be run on a serverless platform like Render.
#
# --- SOLUTION FOR COLLEGE PROJECTS (Free, No Credit Card) ---
# Use a standard Gmail account with an "App Password". This is the recommended approach.
#   1. Enable 2-Factor Authentication (2FA) on your Google Account.
#   2. Go to "App Passwords" in your Google Account security settings.
#   3. Generate a new password for "Mail" on "Other" device.
#   4. Use the 16-character generated App Password as your MAIL_PASSWORD.
#
# Example Environment Variables for Gmail + App Password:
#   MAIL_SERVER=smtp.gmail.com
#   MAIL_PORT=587
#   MAIL_USE_TLS=True
#   MAIL_USE_SSL=False
#   MAIL_USERNAME=your.email@gmail.com
#   MAIL_PASSWORD=<Your 16-character App Password from Google>
#   MAIL_DEFAULT_SENDER=your.email@gmail.com
#
# --- RECOMMENDED PRODUCTION SOLUTION (May require a credit card) ---
# Use a Transactional Email Service Provider like SendGrid, Brevo, or Mailgun.
# =====================================================================================
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

mail = Mail(app)

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
users_collection = None
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
    # Check if mail is configured before proceeding
    if not app.config.get('MAIL_SERVER') or not app.config.get('MAIL_USERNAME'):
        print("CRITICAL_ERROR: Mail server is not configured. Cannot send signup email.")
        return jsonify({'success': False, 'error': 'The mail service is not configured on the server.'}), 503

    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not all([name, email, password]):
        return jsonify({'success': False, 'error': 'Please fill out all fields.'}), 400

    if users_collection is None:
        return jsonify({'success': False, 'error': 'Database not configured.'}), 500

    existing_user = users_collection.find_one({"email": email})
    if existing_user:
        if not existing_user.get('is_verified'):
            # Allow resending OTP if user exists but is not verified
            pass
        else:
            return jsonify({'success': False, 'error': 'An account with this email already exists.'}), 409

    otp = str(random.randint(100000, 999999))
    otp_expiry = datetime.utcnow() + timedelta(minutes=10)

    # Send OTP email first, before database operations
    try:
        msg = Message("Your Verification Code", recipients=[email])
        msg.body = f"Your OTP for Sofia AI is: {otp}\nThis code will expire in 10 minutes."
        mail.send(msg)
    except Exception as e:
        print(f"SIGNUP_EMAIL_ERROR: {e}")
        # Provide a more generic error to the user for security.
        return jsonify({'success': False, 'error': 'Could not send verification email. Please check the email address and server configuration.'}), 500

    if existing_user:
         # Update OTP for existing, unverified user
        users_collection.update_one(
            {'_id': existing_user['_id']},
            {'$set': {
                "verification_otp": otp,
                "otp_expires_at": otp_expiry,
            }}
        )
    else:
        # Create new user
        new_user = {
            "name": name,
            "email": email,
            "password": password, # In a real app, hash this password!
            "isAdmin": email == ADMIN_EMAIL,
            "isPremium": False,
            "is_verified": False,
            "verification_otp": otp,
            "otp_expires_at": otp_expiry,
            "session_id": str(uuid.uuid4()),
            "usage_counts": { "messages": 0, "webSearches": 0 },
            "last_usage_reset": datetime.utcnow().strftime('%Y-%m-%d'),
            "timestamp": datetime.utcnow().isoformat()
        }
        users_collection.insert_one(new_user)

    return jsonify({'success': True, 'message': 'An OTP has been sent to your email.'})


@app.route('/api/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if not all([email, otp]):
        return jsonify({'success': False, 'error': 'Email and OTP are required.'}), 400

    user = users_collection.find_one({"email": email})
    if not user:
        return jsonify({'success': False, 'error': 'User not found.'}), 404

    if user.get('is_verified'):
        return jsonify({'success': True, 'message': 'Account already verified.'}), 200

    if user.get('otp_expires_at') < datetime.utcnow():
        return jsonify({'success': False, 'error': 'OTP has expired.'}), 400

    if user.get('verification_otp') != otp:
        return jsonify({'success': False, 'error': 'Invalid OTP.'}), 400

    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {'is_verified': True}, '$unset': {'verification_otp': "", 'otp_expires_at': ""}}
    )
    return jsonify({'success': True, 'message': 'Email verified successfully! You can now log in.'})


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

    if user_data and user_data['password'] == password:
        if not user_data.get('is_verified'):
            return jsonify({'success': False, 'error': 'Please verify your email before logging in.', 'not_verified': True}), 403

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
        # Still return success to prevent email enumeration attacks
        return jsonify({'success': True, 'message': 'If an account with that email exists, a password reset link has been sent.'})

    reset_token = uuid.uuid4().hex
    token_expiry = datetime.utcnow() + timedelta(hours=1)
    
    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {'password_reset_token': reset_token, 'reset_token_expires_at': token_expiry}}
    )
    
    reset_url = url_for('home', _external=True) + f'reset-password?token={reset_token}'
    
    try:
        msg = Message("Password Reset Request", recipients=[email])
        msg.body = f"Click the following link to reset your password: {reset_url}\nThis link will expire in 1 hour."
        mail.send(msg)
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
        
    # In a real app, hash this password!
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

@app.route('/logout', methods=['POST']) # FIX: Changed from /api/logout to /logout
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
        
        # Anonymize the user by removing personal details, but keeping the document and chat history.
        # This preserves chat history while removing personally identifiable information.
        update_result = users_collection.update_one(
            {'_id': user_id},
            {
                '$set': {
                    'email': f'deleted_{user_id}@anonymous.com',
                    'password': 'deleted',
                    'name': 'Anonymous User'
                },
                '$unset': {
                    'session_id': "" # Remove session_id to invalidate sessions
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
            # Reset the count for the new day
            users_collection.update_one(
                {'_id': ObjectId(current_user.id)},
                {'$set': {'usage_counts.messages': 0, 'last_usage_reset': today.strftime('%Y-%m-%d')}}
            )
            user_data = users_collection.find_one({'_id': ObjectId(current_user.id)}) # Re-fetch user data
        
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
        match = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0--9_-]{11})", video_url)
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
        ai_response, api_used, model_logged = None, "", ""

        gemini_history = []
        openai_history = []
        if chat_history_collection is not None:
            try:
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
            if OPENROUTER_API_KEY_V3:
                print("Routing to OpenRouter...")
                ai_response = call_api("https://openrouter.ai/api/v1/chat/completions",
                                       {"Authorization": f"Bearer {OPENROUTER_API_KEY_V3}"},
                                       {"model": "deepseek/deepseek-chat", "messages": openai_history},
                                       "OpenRouter")
                if ai_response:
                    api_used, model_logged = "OpenRouter", "deepseek/deepseek-chat"

            if not ai_response and GROQ_API_KEY:
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
            
            # --- REFACTORED GEMINI CALL ---
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


        if chat_history_collection is not None and ai_response:
            try:
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

# --- Live AI Camera Feature (Backend) ---
@app.route('/live_object_detection', methods=['POST'])
@login_required
def live_object_detection():
    """
    This endpoint receives a frame from a live camera feed, sends it to the AI,
    and returns a description of the objects in the frame.
    NOTE: The frontend needs to be built to capture frames from the user's camera
    and send them to this endpoint as a base64 encoded string.
    """
    data = request.get_json()
    if not data or 'image_data' not in data:
        return jsonify({'error': 'No image data provided.'}), 400

    image_data = data['image_data']
    try:
        # Decode the base64 string
        image_bytes = base64.b64decode(image_data.split(',')[1])
        img = Image.open(io.BytesIO(image_bytes))

        # Call Gemini AI
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(["Describe the objects you see in this image.", img])
        
        return jsonify({'description': response.text})

    except Exception as e:
        print(f"Error in live object detection: {e}")
        return jsonify({'error': 'Failed to process image.'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

