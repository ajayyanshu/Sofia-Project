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
conversations_collection = None
users_collection = None
library_collection = None # New collection for library items

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
        conversations_collection = db.get_collection("conversations")
        users_collection = db.get_collection("users")
        library_collection = db.get_collection("library_items") # Initialize the new collection
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
    user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
    usage_counts = user_data.get('usage_counts', {"messages": 0, "webSearches": 0})
    
    return jsonify({
        "name": current_user.name,
        "email": current_user.email,
        "isAdmin": current_user.isAdmin,
        "isPremium": current_user.isPremium,
        "usageCounts": usage_counts
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

# --- Chat History CRUD API ---

@app.route('/api/chats', methods=['GET'])
@login_required
def get_chats():
    if conversations_collection is None:
        return jsonify([])
    try:
        user_id = ObjectId(current_user.id)
        # Sort by timestamp descending to get most recent chats first
        chats_cursor = conversations_collection.find({"user_id": user_id}).sort("timestamp", -1)
        chats_list = []
        for chat in chats_cursor:
            chats_list.append({
                "id": str(chat["_id"]),
                "title": chat.get("title", "Untitled Chat"),
                "messages": chat.get("messages", [])
            })
        return jsonify(chats_list)
    except Exception as e:
        print(f"Error fetching chats: {e}")
        return jsonify({"error": "Could not fetch chat history"}), 500

@app.route('/api/chats', methods=['POST'])
@login_required
def save_chat():
    if conversations_collection is None:
        return jsonify({"error": "Database not configured"}), 500
    
    data = request.get_json()
    chat_id = data.get('id')
    messages = data.get('messages', [])
    title = data.get('title')

    if not messages:
        return jsonify({"status": "empty chat, not saved"})

    if not title:
        first_user_message = next((msg.get('text') for msg in messages if msg.get('sender') == 'user'), "Untitled Chat")
        title = first_user_message[:40] if first_user_message else "Untitled Chat"

    user_id = ObjectId(current_user.id)
    
    try:
        if chat_id:
            # Update existing chat
            conversations_collection.update_one(
                {"_id": ObjectId(chat_id), "user_id": user_id},
                {
                    "$set": {
                        "messages": messages,
                        "title": title,
                        "timestamp": datetime.utcnow()
                    }
                }
            )
            return jsonify({"id": chat_id})
        else:
            # Create new chat
            chat_document = {
                "user_id": user_id,
                "title": title,
                "messages": messages,
                "timestamp": datetime.utcnow()
            }
            result = conversations_collection.insert_one(chat_document)
            new_id = str(result.inserted_id)
            return jsonify({"id": new_id, "title": title})
    except Exception as e:
        print(f"Error saving chat: {e}")
        return jsonify({"error": "Could not save chat"}), 500

@app.route('/api/chats/<chat_id>', methods=['PUT'])
@login_required
def rename_chat(chat_id):
    if conversations_collection is None:
        return jsonify({"error": "Database not configured"}), 500
    
    data = request.get_json()
    new_title = data.get('title')
    if not new_title:
        return jsonify({"error": "New title not provided"}), 400

    try:
        result = conversations_collection.update_one(
            {"_id": ObjectId(chat_id), "user_id": ObjectId(current_user.id)},
            {"$set": {"title": new_title}}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Chat not found or permission denied"}), 404
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error renaming chat: {e}")
        return jsonify({"error": "Could not rename chat"}), 500

@app.route('/api/chats/<chat_id>', methods=['DELETE'])
@login_required
def delete_chat_by_id(chat_id):
    if conversations_collection is None:
        return jsonify({"error": "Database not configured"}), 500
    
    try:
        result = conversations_collection.delete_one(
            {"_id": ObjectId(chat_id), "user_id": ObjectId(current_user.id)}
        )
        if result.deleted_count == 0:
            return jsonify({"error": "Chat not found or permission denied"}), 404
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error deleting chat: {e}")
        return jsonify({"error": "Could not delete chat"}), 500

# --- Temporary Chat API ---
@app.route('/api/temp_chats', methods=['POST'])
@login_required
def save_or_update_temp_chat():
    if temporary_chat_collection is None:
        return jsonify({"error": "Database not configured"}), 500
    data = request.get_json()
    temp_chat_id = data.get('id')
    messages = data.get('messages', [])
    if not temp_chat_id:
        return jsonify({"error": "Temporary chat ID is required"}), 400

    user_id = ObjectId(current_user.id)
    try:
        temporary_chat_collection.update_one(
            {"_id": temp_chat_id, "user_id": user_id},
            {"$set": {
                "messages": messages,
                "timestamp": datetime.utcnow()
            }},
            upsert=True
        )
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error saving temporary chat: {e}")
        return jsonify({"error": "Could not save temporary chat"}), 500

@app.route('/api/temp_chats/save', methods=['POST'])
@login_required
def promote_temp_chat():
    if temporary_chat_collection is None or conversations_collection is None:
        return jsonify({"error": "Database not configured"}), 500

    data = request.get_json()
    temp_chat_id = data.get('id')
    if not temp_chat_id:
        return jsonify({"error": "Temporary chat ID is required"}), 400

    user_id = ObjectId(current_user.id)
    temp_chat = temporary_chat_collection.find_one({"_id": temp_chat_id, "user_id": user_id})

    if not temp_chat:
        return jsonify({"error": "Temporary chat not found or permission denied"}), 404

    messages = temp_chat.get('messages', [])
    if not messages:
        return jsonify({"error": "Cannot save an empty chat"}), 400

    # Generate title from the first user message
    first_user_message = next((msg.get('text') for msg in messages if msg.get('sender') == 'user'), "Untitled Chat")
    title = first_user_message[:40] if first_user_message else "Untitled Chat"

    try:
        # Create a new document in the permanent conversations collection
        new_chat_doc = {
            "user_id": user_id,
            "title": title,
            "messages": messages,
            "timestamp": datetime.utcnow()
        }
        result = conversations_collection.insert_one(new_chat_doc)
        
        # Delete the chat from the temporary collection
        temporary_chat_collection.delete_one({"_id": temp_chat_id, "user_id": user_id})

        return jsonify({
            "id": str(result.inserted_id),
            "title": title
        })
    except Exception as e:
        print(f"Error promoting temporary chat: {e}")
        return jsonify({"error": "Could not save chat permanently"}), 500


# --- Library CRUD API ---
@app.route('/api/library', methods=['POST'])
@login_required
def upload_library_item():
    if library_collection is None:
        return jsonify({"error": "Database not configured"}), 500
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = file.filename
    file_content = file.read()
    file_type = file.mimetype
    file_size = len(file_content)

    # Convert file content to base64 for storage in MongoDB
    encoded_file_content = base64.b64encode(file_content).decode('utf-8')

    # Basic content extraction for display/search
    extracted_text = ""
    if 'image' in file_type:
        try:
            img = Image.open(io.BytesIO(file_content))
            # Optional: Use AI to describe image, or just store a placeholder
            extracted_text = "Image file."
            # For actual content, you'd integrate a vision model here.
        except Exception as e:
            print(f"Error processing image: {e}")
    elif 'pdf' in file_type:
        extracted_text = extract_text_from_pdf(file_content)
    elif 'word' in file_type or file_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        extracted_text = extract_text_from_docx(file_content)
    elif 'text' in file_type:
        extracted_text = file_content.decode('utf-8')
    
    library_item = {
        "user_id": ObjectId(current_user.id),
        "filename": filename,
        "file_type": file_type,
        "file_size": file_size,
        "file_data": encoded_file_content, # Storing actual file data (base64)
        "extracted_text": extracted_text[:1000], # Store first 1000 chars of extracted text
        "timestamp": datetime.utcnow()
    }

    try:
        result = library_collection.insert_one(library_item)
        return jsonify({
            "success": True, 
            "id": str(result.inserted_id), 
            "filename": filename,
            "file_type": file_type,
            "timestamp": library_item["timestamp"].isoformat()
        })
    except Exception as e:
        print(f"Error uploading library item: {e}")
        return jsonify({"error": "Could not save file to library"}), 500

@app.route('/api/library', methods=['GET'])
@login_required
def get_library_items():
    if library_collection is None:
        return jsonify([])
    try:
        user_id = ObjectId(current_user.id)
        items_cursor = library_collection.find({"user_id": user_id}).sort("timestamp", -1)
        items_list = []
        for item in items_cursor:
            # Do not send full file_data in the list view for performance
            items_list.append({
                "id": str(item["_id"]),
                "filename": item["filename"],
                "file_type": item["file_type"],
                "file_size": item["file_size"],
                "timestamp": item["timestamp"].isoformat(),
                "thumbnail_data": None # Placeholder for future thumbnail generation
            })
        return jsonify(items_list)
    except Exception as e:
        print(f"Error fetching library items: {e}")
        return jsonify({"error": "Could not fetch library items"}), 500

@app.route('/api/library/<item_id>', methods=['GET'])
@login_required
def get_library_item(item_id):
    if library_collection is None:
        return jsonify({"error": "Database not configured"}), 500
    try:
        user_id = ObjectId(current_user.id)
        item = library_collection.find_one({"_id": ObjectId(item_id), "user_id": user_id})
        if not item:
            return jsonify({"error": "Item not found or permission denied"}), 404
        
        # Return full item data, including base64 encoded file
        return jsonify({
            "id": str(item["_id"]),
            "filename": item["filename"],
            "file_type": item["file_type"],
            "file_size": item["file_size"],
            "file_data": item["file_data"], # Base64 encoded content
            "extracted_text": item["extracted_text"],
            "timestamp": item["timestamp"].isoformat()
        })
    except Exception as e:
        print(f"Error fetching library item: {e}")
        return jsonify({"error": "Could not fetch library item"}), 500

@app.route('/api/library/<item_id>', methods=['DELETE'])
@login_required
def delete_library_item(item_id):
    if library_collection is None:
        return jsonify({"error": "Database not configured"}), 500
    try:
        result = library_collection.delete_one(
            {"_id": ObjectId(item_id), "user_id": ObjectId(current_user.id)}
        )
        if result.deleted_count == 0:
            return jsonify({"error": "Item not found or permission denied"}), 404
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error deleting library item: {e}")
        return jsonify({"error": "Could not delete library item"}), 500

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
                {'$set': {
                    'usage_counts': {'messages': 0, 'webSearches': 0},
                    'last_usage_reset': today.strftime('%Y-%m-%d')
                }}
            )
            user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
        
        usage = user_data.get('usage_counts', {})
        messages_used = usage.get('messages', 0)
        
        if messages_used >= 15:
            return jsonify({
                'error': 'You have reached your daily message limit. Please upgrade for unlimited access.',
                'upgrade_required': True
            }), 429
            
        # Increment the message count only for non-premium, non-admin users
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
            # NOTE: Chat saving is now handled by the frontend via the POST /api/chats endpoint.
            # The logic to save individual messages here is disabled to prevent data duplication
            # and conflicts with the new conversation-based storage model.
            pass

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
    """Fetches all of user's chat conversations and returns them as an HTML file."""
    if conversations_collection is None:
        return jsonify({'success': False, 'error': 'Database not configured.'}), 500

    try:
        user_id = ObjectId(current_user.id)
        user_name = current_user.name
        history_cursor = conversations_collection.find({"user_id": user_id}).sort("timestamp", 1)

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
        h3 {{
            background-color: #e4e6eb;
            padding: 10px;
            border-radius: 5px;
            margin-top: 30px;
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
            margin-top: 10px;
        }}
        .user-message .message {{
            background-color: #0084ff;
            color: white;
            border-bottom-right-radius: 4px;
        }}
        .ai-message-container {{
            display: flex;
            justify-content: flex-start;
            margin-top: 10px;
        }}
        .ai-message .message {{
            background-color: #e4e6eb;
            color: #050505;
            border-bottom-left-radius: 4px;
        }}
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

        # Loop through each conversation
        for conversation in history_cursor:
            conv_title = conversation.get('title', 'Untitled Chat').replace('<', '&lt;').replace('>', '&gt;')
            html_content += f"<h3>Conversation: {conv_title}</h3>"

            # Loop through messages in the conversation
            for message in conversation.get('messages', []):
                sender = message.get('sender')
                text = message.get('text', '').replace('<', '&lt;').replace('>', '&gt;')

                if sender == 'user':
                    html_content += f"""
        <div class="message-container user-message-container">
            <div class="user-message">
                <div class="label">You</div>
                <div class="message">{text}</div>
            </div>
        </div>"""
                elif sender == 'ai':
                    html_content += f"""
        <div class="message-container ai-message-container">
            <div class="ai-message">
                <div class="label">Sofia AI</div>
                <div class="message">{text}</div>
            </div>
        </div>"""

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
