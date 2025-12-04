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
# --- MODIFICATION 1: Reverted import to its original state ---
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
SERPER_API_KEY = os.environ.get("SERPER_API_KEY") # <-- ADDED FOR WEB SEARCH
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

if SERPER_API_KEY: # <-- ADDED FOR WEB SEARCH
    print("✅ Serper API Key (for web search) loaded.")
else:
    print("CRITICAL WARNING: SERPER_API_KEY not found. AI web search will be disabled.")

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
        except Exception as e: # *** MODIFICATION 1: Catch specific exception ***
            print(f"USER_GET_ERROR: Failed to get user {user_id}. Error: {e}")
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

@app.route('/delete_account', methods=['DELETE'])
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
            # *** MODIFICATION 2: Added try/except around logout_user ***
            # This prevents a server crash if logout fails for any reason
            try:
                logout_user()
            except Exception as e:
                print(f"LOGOUT_ERROR_ON_DELETE: {e}")
                # This is not a critical error, the account is deleted.
                # We can proceed with the success response.
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

# --- Library CRUD API ---

# <-- ADDED: Helper functions for AI summarization -->
def get_ai_summary(text_content):
    """Calls Gemini API to get a summary of the provided text."""
    if not GOOGLE_API_KEY:
        print("AI_SUMMARY_SKIP: GOOGLE_API_KEY not set.")
        return "Summary generation skipped: AI not configured."
    
    if not text_content or text_content.isspace():
        return "No text content to summarize."

    try:
        # Using the same model from /chat for consistency
        model = genai.GenerativeModel("gemini-2.5-flash-lite") 
        
        # Truncate text to avoid overly long prompts (e.g., ~15k words)
        max_length = 80000 
        if len(text_content) > max_length:
            text_content = text_content[:max_length]

        prompt = (
            "You are an expert summarizer. Please provide a concise, one-paragraph summary "
            "of the following document. Focus on the main ideas and key takeaways.\n\n"
            f"--- DOCUMENT START ---\n{text_content}\n--- DOCUMENT END ---"
        )
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"AI_SUMMARY_ERROR: {e}")
        return f"Could not generate summary. Error: {e}"

def run_ai_summary_in_background(app, item_id, text_content):
    """Runs AI summarization in a background thread and updates MongoDB."""
    with app.app_context():
        print(f"Starting background summary for item: {item_id}")
        summary = get_ai_summary(text_content)
        
        if library_collection:
            try:
                library_collection.update_one(
                    {"_id": ObjectId(item_id)},
                    {"$set": {"ai_summary": summary, "ai_summary_status": "completed"}}
                )
                print(f"Successfully saved summary for item: {item_id}")
            except Exception as e:
                print(f"BACKGROUND_MONGO_ERROR: Failed to update summary for {item_id}. Error: {e}")
        else:
            print(f"BACKGROUND_MONGO_ERROR: library_collection is None. Cannot save summary.")
# <-- END: Helper functions for AI summarization -->


@app.route('/library/upload', methods=['POST'])
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
        extracted_text = extract_text_from_pdf(file_content) # <-- This helper is defined in /chat
    elif 'word' in file_type or file_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        extracted_text = extract_text_from_docx(file_content) # <-- This helper is defined in /chat
    elif 'text' in file_type:
        try:
            extracted_text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            extracted_text = file_content.decode('latin-1', errors='ignore')
    
    library_item = {
        "user_id": ObjectId(current_user.id),
        "filename": filename,
        "file_type": file_type,
        "file_size": file_size,
        "file_data": encoded_file_content, # Storing actual file data (base64)
        "extracted_text": extracted_text[:1000], # Store first 1000 chars of extracted text
        "ai_summary": "Processing...", # <-- ADDED for automation
        "ai_summary_status": "pending", # <-- ADDED for automation
        "timestamp": datetime.utcnow()
    }

    try:
        result = library_collection.insert_one(library_item)
        new_id = result.inserted_id # <-- ADDED: Get the new ID

        # <-- ADDED: Start background thread for AI summarization -->
        # Only summarize if text was actually extracted
        if extracted_text and extracted_text != "Image file.":
            Thread(target=run_ai_summary_in_background, args=(app, new_id, extracted_text)).start()
        else:
            # If no text (e.g., image), mark as not applicable
             library_collection.update_one(
                {"_id": new_id},
                {"$set": {"ai_summary": "Not applicable (image or empty file).", "ai_summary_status": "completed"}}
            )
        # <-- END: Background thread logic -->

        return jsonify({
            "success": True, 
            "id": str(new_id), # <-- MODIFIED: Use the new_id variable
            "filename": filename,
            "file_type": file_type,
            "timestamp": library_item["timestamp"].isoformat()
        })
    except Exception as e:
        print(f"Error uploading library item: {e}")
        return jsonify({"error": "Could not save file to library"}), 500

@app.route('/library/files', methods=['GET'])
@login_required
def get_library_items():
    if library_collection is None:
        return jsonify([])
    try:
        user_id = ObjectId(current_user.id)
        items_cursor = library_collection.find({"user_id": user_id}).sort("timestamp", -1)
        items_list = []
        for item in items_cursor:
            # MODIFIED: Return all data in camelCase format, as expected by original JS
            items_list.append({
                "_id": str(item["_id"]),             # JS expects _id
                "fileName": item["filename"],        # JS expects camelCase
                "fileType": item["file_type"],       # JS expects camelCase
                "fileSize": item["file_size"],       # JS expects camelCase (for consistency)
                "fileData": item["file_data"],       # JS expects full file data in the list
                "aiSummary": item.get("ai_summary", "Not processed."), # <-- ADDED
                "aiSummaryStatus": item.get("ai_summary_status", "unknown"), # <-- ADDED
                "timestamp": item["timestamp"].isoformat()
            })
        return jsonify(items_list)
    except Exception as e:
        print(f"Error fetching library items: {e}")
        return jsonify({"error": "Could not fetch library items"}), 500

@app.route('/library/files/<item_id>', methods=['DELETE'])
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

# <-- ADDED: Moved text extraction functions here to be globally available -->
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
# <-- END: Moved text extraction functions -->


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
        
        if messages_used >= 15: # Daily message limit from HTML
            return jsonify({
                'error': 'You have reached your daily message limit. Please upgrade for unlimited access.',
                'upgrade_required': True
            }), 429
            
        # Increment the message count only for non-premium, non-admin users
        users_collection.update_one({'_id': ObjectId(current_user.id)}, {'$inc': {'usage_counts.messages': 1}})

    # <-- REMOVED: Text extraction functions were moved to be global -->

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

    # --- MODIFICATION 2: Reverted this function to its original state ---
    def get_youtube_transcript(video_id):
        try:
            # Call the class method
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
            # Check for valid response structure
            if 'choices' in result and len(result['choices']) > 0 and 'message' in result['choices'][0] and 'content' in result['choices'][0]['message']:
                 return result['choices'][0]['message']['content']
            else:
                print(f"Unexpected response structure from {api_name}: {result}")
                return None
        except Exception as e:
            print(f"Error calling {api_name} API: {e}")
            return None

    def search_web(query):
        """Calls Serper.dev API to get web search results."""
        if not SERPER_API_KEY:
            print("Web search skipped: SERPER_API_KEY not set.")
            return "Web search is disabled because the API key is not configured."

        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query})
        headers = {
            'X-API-KEY': SERPER_API_KEY,
            'Content-Type': 'application/json'
        }
        try:
            print(f"Attempting web search for: {query}")
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            results = response.json()
            print("Web search successful.")
            
            snippets = []
            if "organic" in results:
                for item in results.get("organic", [])[:5]: # Get top 5 results
                    title = item.get("title", "No Title")
                    snippet = item.get("snippet", "No Snippet")
                    link = item.get("link", "No Link")
                    snippets.append(f"Title: {title}\nSnippet: {snippet}\nSource: {link}")
            
            if snippets:
                return "\n\n---\n\n".join(snippets)
            elif "answerBox" in results:
                # Handle answer boxes (e.g., "What is the weather?")
                answer = results["answerBox"].get("snippet") or results["answerBox"].get("answer")
                if answer:
                    return f"Direct Answer: {answer}"
            
            return "No relevant web results found."
            
        except Exception as e:
            print(f"Error calling Serper API: {e}")
            return f"An error occurred during the web search: {e}"

    # <-- ADDED: Library Search Helper -->
    def search_library(user_id, query):
        """Searches the user's library for relevant text snippets."""
        if not library_collection:
            return None # Return None, not a string
        
        try:
            # Split query into keywords to broaden search
            keywords = re.split(r'\s+', query)
            # Create a regex that looks for all keywords (case-insensitive)
            # This searches for documents containing all keywords, in any order.
            regex_pattern = '.*'.join(f'(?=.*{re.escape(k)})' for k in keywords)

            items_cursor = library_collection.find({
                "user_id": user_id,
                "extracted_text": {"$regex": regex_pattern, "$options": "i"}
            }).limit(3) # Get top 3 matching docs
            
            snippets = []
            for item in items_cursor:
                filename = item.get("filename", "Untitled")
                snippet = item.get("extracted_text", "")
                
                # Get the start of the text as a snippet
                context_snippet = snippet[:300] # Get first 300 chars
                    
                snippets.append(f"Source: {filename} (from your Library)\nSnippet: {context_snippet}...")
            
            if snippets:
                print(f"Library search found {len(snippets)} items for query: {query}")
                return "\n\n---\n\n".join(snippets)
            else:
                print(f"Library search found no items for query: {query}")
                return None
                
        except Exception as e:
            print(f"Error calling Library search: {e}")
            return None
    
    # <-- MODIFIED: Automation Heuristic -->
    def should_auto_search(user_message):
        """
        Decides if a query is informational and should trigger auto-search.
        Returns the mode: 'code_security_scan', 'security_search', 'web_search', or None.
        """
        msg_lower = user_message.lower().strip()
        
        # Keywords that imply a security-focused search
        security_keywords = [
            'vulnerability', 'malware', 'cybersecurity', 'sql injection',
            'xss', 'cross-site scripting', 'cve-', 'zero-day', 'phishing',
            'ransomware', 'data breach', 'mitigation', 'pentest', 'exploit'
        ]

        # <-- ADDED: Keywords that imply code is being pasted -->
        code_keywords = [
            'def ', 'function ', 'public class', 'SELECT *', 'import ', 'require(', 
            'const ', 'let ', 'var ', '<?php', 'public static void', 'console.log'
        ]

        # Keywords that imply a general search
        general_search_keywords = [
            'what is', 'who is', 'where is', 'when did', 'how to',
            'latest', 'news', 'in 2025', 'in 2024',
            'explain', 'summary of', 'overview of', 'compare'
        ]
        
        # Simple questions that don't need search
        chat_keywords = ['hi', 'hello', 'how are you', 'thanks', 'thank you']

        if any(msg_lower.startswith(k) for k in chat_keywords):
            return None # Just a chat
            
        if any(k in msg_lower for k in security_keywords):
            return 'security_search' # Security-focused search
            
        # <-- ADDED: Code scan check -->
        if any(k in user_message for k in code_keywords):
            return 'code_security_scan' # This is a code scan request

        if any(k in msg_lower for k in general_search_keywords):
            return 'web_search' # General web search
            
        # If it's a longer, more complex question (e.g., > 6 words), default to general search
        if len(user_message.split()) > 6:
            return 'web_search'
            
        return None # Not a search query

    # --- START OF /CHAT LOGIC ---
    try:
        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType', '')
        is_temporary = data.get('isTemporary', False)
        
        request_mode = data.get('mode') 
        
        ai_response, api_used, model_logged = None, "", ""
        web_search_context = None 
        library_search_context = None # <-- ADDED

        is_multimodal = bool(file_data) or "youtube.com" in user_message or "youtu.be" in user_message or any(k in user_message.lower() for k in PDF_KEYWORDS)

        # <-- MODIFIED AUTOMATION LOGIC -->
        # Only trigger if it's a plain chat, not multimodal
        if request_mode == 'chat' and not is_multimodal:
            auto_mode = should_auto_search(user_message)
            if auto_mode:
                print(f"AUTOMATION: Auto-triggering {auto_mode} for: {user_message}")
                request_mode = auto_mode # Upgrade the request mode
                
                # ALSO trigger library search, *UNLESS* it's a code scan
                if auto_mode in ['web_search', 'security_search']:
                    library_search_context = search_library(ObjectId(current_user.id), user_message)
        # <-- END MODIFIED AUTOMATION LOGIC -->


        # --- Web Search Logic (now handles manual, web_search, or security_search) ---
        # <-- MODIFIED: Don't run web search if it's a code scan -->
        if (request_mode == 'web_search' or request_mode == 'security_search') and not is_multimodal and user_message.strip():
            if not SERPER_API_KEY:
                print("Web search requested but SERPER_API_KEY not set.")
                web_search_context = "Web search is disabled by the server administrator."
            elif not current_user.isPremium and not current_user.isAdmin:
                # Check web search usage limit
                user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
                searches_used = user_data.get('usage_counts', {}).get('webSearches', 0)
                
                if searches_used >= 1: # Daily limit from HTML
                    print(f"User {current_user.id} exceeded web search limit.")
                    web_search_context = "You have already used your daily web search. Please upgrade for unlimited searches."
                else:
                    print(f"Performing web search for: {user_message}")
                    web_search_context = search_web(user_message)
                    # Increment web search count
                    users_collection.update_one({'_id': ObjectId(current_user.id)}, {'$inc': {'usage_counts.webSearches': 1}})
            else:
                # Premium or Admin user
                print(f"Performing web search for: {user_message}")
                web_search_context = search_web(user_message)
        
        gemini_history = []
        openai_history = []
        
        # --- FIX: Load History from conversations_collection ---
        if conversations_collection is not None and not is_temporary:
            try:
                # 1. Fetch the single most recent active conversation for this user
                # We assume the user is continuing the latest chat since script.js doesn't send chatId
                recent_conversation = conversations_collection.find_one(
                    {"user_id": ObjectId(current_user.id)},
                    sort=[("timestamp", -1)] 
                )

                if recent_conversation and 'messages' in recent_conversation:
                    # 2. Get the last 10 messages from that conversation to use as context
                    past_messages = recent_conversation['messages'][-10:]

                    for msg in past_messages:
                        role = msg.get('sender')
                        content = msg.get('text', '')
                        
                        # Format for Gemini
                        gemini_role = 'user' if role == 'user' else 'model'
                        gemini_history.append({'role': gemini_role, 'parts': [content]})
                        
                        # Format for OpenAI/Groq
                        openai_role = 'user' if role == 'user' else 'assistant'
                        openai_history.append({"role": openai_role, "content": content})
                        
            except Exception as e:
                print(f"Error fetching chat history from MongoDB: {e}")

        openai_history.append({"role": "user", "content": user_message})


        if not is_multimodal and user_message.strip():
            ai_response = None
            
            # <-- MODIFIED: Handle Code Security Scan Mode -->
            if request_mode == 'code_security_scan':
                print(f"Using Groq (Code Security Scan) for: {user_message[:50]}...")
                
                # <-- MODIFIED: Upgraded Professional Prompt -->
                CODE_SECURITY_PROMPT = (
                    "You are 'Sofia-Sec-L-70B', a specialized AI Code Security Analyst modeled after Google's internal security review tools. "
                    "A user (potential Google intern) has submitted a code snippet for review. Your task is to perform a rigorous security and vulnerability analysis. "
                    "The output MUST be a professional-grade security report formatted in Markdown, suitable for a technical audience (e.g., a Google engineering team).\n\n"
                    "**SECURITY ANALYSIS REPORT**\n\n"
                    "**1. Executive Summary:**\n"
                    "   - A high-level overview of the code's purpose and its primary security posture.\n\n"
                    "**2. Vulnerability Findings:**\n"
                    "   - (List each finding. If none, state 'No significant vulnerabilities detected.')\n"
                    "   - **[Severity: Critical/High/Medium/Low] - [Vulnerability Type (e.g., SQL Injection)]**\n"
                    "     - **Location:** (Quote the problematic line(s) of code.)\n"
                    "     - **Analysis:** (Detailed explanation of the vulnerability, its attack vector, and potential business impact.)\n"
                    "     - **CVE-ID (if applicable):** (e.g., CVE-2023-XXXXX, or 'N/A'.)\n"
                    "     - **Recommended Mitigation:** (Provide the corrected, secure code snippet. Explain *why* the new code is secure, referencing best practices like input sanitization, parameterized queries, etc.)\n\n"
                    "**3. Secure Coding Recommendations:**\n"
                    "   - General advice on how to improve the overall security of this code, referencing Google's secure coding standards or OWASP Top 10.\n\n"
                    "**4. Overall Security Rating:** (Assign one: Excellent, Good, Fair, Poor, Critical)\n\n"
                    "--- USER SUBMITTED CODE ---\n"
                )
                
                code_scan_history = [
                    {"role": "system", "content": CODE_SECURITY_PROMPT},
                    {"role": "user", "content": user_message}
                ]
                
                ai_response = call_api(
                    "https://api.groq.com/openai/v1/chat/completions",
                    {"Authorization": f"Bearer {GROQ_API_KEY}"},
                    # Use a powerful model for this complex task
                    {"model": "llama-3.1-70b-versatile", "messages": code_scan_history}, 
                    "Groq (Code Security Scan)"
                )
                if ai_response:
                    api_used, model_logged = "Groq (Code Security Scan)", "llama-3.1-70b-versatile"
            
            # <-- MODIFIED: Check for ai_response before continuing -->
            elif (web_search_context or library_search_context) and not ai_response:
                print(f"Using Groq (with search context) in mode: {request_mode}...")
                
                # <-- MODIFIED: Upgraded Professional Prompts -->
                GENERAL_SYSTEM_PROMPT = (
                    "You are a helpful assistant. You MUST answer the user's question "
                    "based *only* on the provided context. "
                    "Cite your sources using the [Source: link] or [Source: Filename] format."
                )
                SECURITY_SYSTEM_PROMPT = (
                    "You are 'Sofia-Sec-L', a specialized AI Security Analyst modeled after Google's internal threat intelligence platforms. "
                    "Your task is to answer the user's cybersecurity question. You MUST synthesize information *only* from the provided real-time internet search results and library context. "
                    "Provide a professional, technical answer suitable for a security engineer. "
                    "Your response should:\n"
                    "1.  Directly answer the user's question.\n"
                    "2.  Analyze threats, vulnerabilities, and mitigation strategies based *only* on the provided context.\n"
                    "3.  Reference CVEs, threat actors, or TTPs if mentioned in the search results.\n"
                    "4.  Conclude with a 'Key Takeaways' section.\n"
                    "5.  Cite all sources meticulously using [Source: URL/Filename] for every claim made."
                )
                
                if request_mode == 'security_search':
                    system_prompt = SECURITY_SYSTEM_PROMPT
                else:
                    system_prompt = GENERAL_SYSTEM_PROMPT
                # <-- END: Dynamic System Prompt -->

                context_parts = []
                if web_search_context:
                    context_parts.append(f"--- WEB SEARCH RESULTS ---\n{web_search_context}")
                if library_search_context:
                    context_parts.append(f"--- YOUR LIBRARY RESULTS ---\n{library_search_context}")
                
                context_prompt = "\n\n".join(context_parts)
                
                search_augmented_history = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": (
                        f"{context_prompt}\n\n"
                        f"--- USER QUESTION ---\n{user_message}"
                    )}
                ]
                
                ai_response = call_api(
                    "https://api.groq.com/openai/v1/chat/completions",
                    {"Authorization": f"Bearer {GROQ_API_KEY}"},
                    {"model": "llama-3.1-8b-instant", "messages": search_augmented_history},
                    "Groq (Contextual Search)"
                )
                if ai_response:
                    api_used, model_logged = "Groq (Contextual Search)", "llama-3.1-8b-instant"
                    
            elif not ai_response and GROQ_API_KEY:
                # Original logic: No search context, just a normal text chat
                print("Routing to Groq (no search)...")
                ai_response = call_api("https://api.groq.com/openai/v1/chat/completions",
                                       {"Authorization": f"Bearer {GROQ_API_KEY}"},
                                       {"model": "llama-3.1-8b-instant", "messages": openai_history},
                                       "Groq")
                if ai_response:
                    api_used, model_logged = "Groq", "llama-3.1-8b-instant"

        if not ai_response:
            print("Routing to Gemini (Sofia AI)...")
            model_name = "gemini-2.5-flash-lite" 
            api_used, model_logged = "Gemini", model_name
            model = genai.GenerativeModel(model_name)

            prompt_parts = [user_message] if user_message else []

            # --- MODIFIED: Handle Code Scan, then Web/Library Scan, then Multimodal ---
            if request_mode == 'code_security_scan':
                # <-- MODIFIED: Upgraded Professional Prompt for Gemini -->
                CODE_SECURITY_PROMPT = (
                    "You are 'Sofia-Sec-L', a specialized AI Code Security Analyst modeled after Google's internal security review tools. "
                    "A user (potential Google intern) has submitted a code snippet for review. Your task is to perform a rigorous security and vulnerability analysis. "
                    "The output MUST be a professional-grade security report formatted in Markdown, suitable for a technical audience (e.g., a Google engineering team).\n\n"
                    "**SECURITY ANALYSIS REPORT**\n\n"
                    "**1. Executive Summary:**\n"
                    "   - A high-level overview of the code's purpose and its primary security posture.\n\n"
                    "**2. Vulnerability Findings:**\n"
                    "   - (List each finding. If none, state 'No significant vulnerabilities detected.')\n"
                    "   - **[Severity: Critical/High/Medium/Low] - [Vulnerability Type (e.g., SQL Injection)]**\n"
                    "     - **Location:** (Quote the problematic line(s) of code.)\n"
                    "     - **Analysis:** (Detailed explanation of the vulnerability, its attack vector, and potential business impact.)\n"
                    "     - **CVE-ID (if applicable):** (e.g., CVE-2023-XXXXX, or 'N/A'.)\n"
                    "     - **Recommended Mitigation:** (Provide the corrected, secure code snippet. **You MUST wrap all code snippets in triple backticks (```) with the language identifier**, like this: ```python\n# Your code here\n```)\n\n"
                    "**3. Secure Coding Recommendations:**\n"
                    "   - General advice on how to improve the overall security of this code, referencing Google's secure coding standards or OWASP Top 10.\n\n"
                    "**4. Overall Security Rating:** (Assign one: Excellent, Good, Fair, Poor, Critical)\n\n"
                    "--- USER SUBMITTED CODE ---\n" + user_message
                )
                prompt_parts = [CODE_SECURITY_PROMPT]
                api_used = "Gemini (Code Security Scan)"

            elif web_search_context or library_search_context:
                # <-- MODIFIED: Upgraded Professional Prompts for Gemini -->
                GENERAL_SYSTEM_PROMPT = (
                    "You are a helpful assistant. You MUST answer the user's question "
                    "based *only* on the provided context. "
                    "Cite your sources using the [Source: link] or [Source: Filename] format."
                )
                SECURITY_SYSTEM_PROMPT = (
                    "You are 'Sofia-Sec-L', a specialized AI Security Analyst modeled after Google's internal threat intelligence platforms. "
                    "Your task is to answer the user's cybersecurity question. You MUST synthesize information *only* from the provided real-time internet search results and library context. "
                    "Provide a professional, technical answer suitable for a security engineer. "
                    "Your response should:\n"
                    "1.  Directly answer the user's question.\n"
                    "2.  Analyze threats, vulnerabilities, and mitigation strategies based *only* on the provided context.\n"
                    "3.  Reference CVEs, threat actors, or TTPs if mentioned in the search results.\n"
                    "4.  Conclude with a 'Key Takeaways' section.\n"
                    "5.  Cite all sources meticulously using [Source: URL/Filename] for every claim made."
                )
                
                if request_mode == 'security_search':
                    system_prompt = SECURITY_SYSTEM_PROMPT
                    api_used = "Gemini (Security Search)"
                else:
                    system_prompt = GENERAL_SYSTEM_PROMPT
                    api_used = "Gemini (Contextual Search)"
                # <-- END: Dynamic System Prompt for Gemini -->
                
                context_parts = []
                if web_search_context:
                    context_parts.append(f"--- WEB SEARCH RESULTS ---\n{web_search_context}")
                if library_search_context:
                    context_parts.append(f"--- YOUR LIBRARY RESULTS ---\n{library_search_context}")
                
                context_prompt = "\n\n".join(context_parts)
                
                # This will be the only prompt part. We ignore history to focus on the search task.
                prompt_parts = [
                    f"{system_prompt}\n\n{context_prompt}\n\n--- USER QUESTION ---\n{user_message}"
                ]
                
            elif "youtube.com" in user_message or "youtu.be" in user_message:
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
                # --- MODIFIED: Don't use history if we have search or code scan context ---
                if web_search_context or library_search_context or request_mode == 'code_security_scan':
                    full_prompt = prompt_parts
                else:
                    full_prompt = gemini_history + [{'role': 'user', 'parts': prompt_parts}]
                
                response = model.generate_content(full_prompt)
                ai_response = response.text
            except Exception as e:
                print(f"Error calling Gemini API: {e}")
                try:
                    print("Retrying Gemini call without history...")
                    response = model.generate_content(prompt_parts) # This is the fallback
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
    # --- END OF MODIFIED /CHAT LOGIC ---

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
</head><body>
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
# [Code for this feature has been removed as requested]

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
