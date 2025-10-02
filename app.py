import base64
import io
import os
import re
import sys
import json
from datetime import datetime
import uuid

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
# ... (This section remains unchanged)

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

    new_user = {
        "name": name,
        "email": email,
        "password": password,
        "isAdmin": email == ADMIN_EMAIL,
        "isPremium": False,
        "session_id": str(uuid.uuid4()),
        "usage_counts": { "messages": 0, "webSearches": 0 },
        "last_usage_reset": datetime.utcnow().strftime('%Y-%m-%d'),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        users_collection.insert_one(new_user)
        return jsonify({'success': True})
    except Exception as e:
        print(f"MONGO_WRITE_ERROR: {e}")
        return jsonify({'success': False, 'error': 'Server error creating account.'}), 500

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
        new_session_id = str(uuid.uuid4())
        users_collection.update_one({'_id': user_data['_id']}, {'$set': {'session_id': new_session_id}})
        user_data['session_id'] = new_session_id

        user_obj = User(user_data)
        login_user(user_obj)
        session['session_id'] = new_session_id
        return jsonify({'success': True, 'user': {'name': user_data['name'], 'email': user_data['email']}})
    else:
        return jsonify({'success': False, 'error': 'Incorrect email or password.'}), 401
        
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
        result = users_collection.delete_one({'_id': ObjectId(current_user.id)})
        if result.deleted_count > 0:
            logout_user()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'User not found.'}), 404
    except Exception as e:
        print(f"MONGO_DELETE_ERROR: {e}")
        return jsonify({'success': False, 'error': 'Error deleting user.'}), 500


# --- Status Route ---
# ... (This section remains unchanged)

# --- Chat Logic ---
@app.route('/chat', methods=['POST'])
@login_required
def chat():
# ... (This section remains unchanged)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

