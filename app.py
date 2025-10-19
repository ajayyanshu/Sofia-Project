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

app = Flask(__name__, template_folder='templates')
CORS(app)

# --- Configuration ---
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
app.config['SECRET_KEY'] = SECRET_KEY
if SECRET_KEY == "dev-secret-key":
    print("CRITICAL WARNING: Using a default, insecure FLASK_SECRET_KEY for development.")

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ajay@123.com")

# --- Email Configuration ---
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

mail = Mail(app)

def send_async_email(app, msg):
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

# --- MongoDB Configuration ---
mongo_client = None
conversations_collection = None
users_collection = None
library_collection = None

if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client.get_database("ai_assistant_db")
        db.command('ping')
        print("✅ Successfully pinged MongoDB.")
        conversations_collection = db.get_collection("conversations")
        users_collection = db.get_collection("users")
        library_collection = db.get_collection("library_items")
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
        if users_collection is None: return None
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
    if current_user.is_authenticated and session.get('session_id') != current_user.session_id:
        logout_user()
        flash("You have been logged out from another device.", "info")
        return redirect(url_for('login_page'))

# --- Page Rendering Routes ---
@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/login.html')
def login_page():
    return render_template('login.html') if not current_user.is_authenticated else redirect(url_for('home'))

@app.route('/signup.html')
def signup_page():
    return render_template('signup.html') if not current_user.is_authenticated else redirect(url_for('home'))

# --- API Authentication Routes ---
@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.get_json()
    name, email, password = data.get('name'), data.get('email'), data.get('password')

    if not all([name, email, password]):
        return jsonify({'success': False, 'error': 'Please fill out all fields.'}), 400
    if users_collection.find_one({"email": email}):
        return jsonify({'success': False, 'error': 'An account with this email already exists.'}), 409

    new_user = {
        "name": name, "email": email, "password": password, # In a real app, hash the password
        "isAdmin": email == ADMIN_EMAIL, "isPremium": False,
        "session_id": str(uuid.uuid4()),
        "usage_counts": {"messages": 0, "webSearches": 0},
        "last_usage_reset": datetime.utcnow().strftime('%Y-%m-%d'),
        "timestamp": datetime.utcnow().isoformat()
    }
    users_collection.insert_one(new_user)
    return jsonify({'success': True, 'message': 'Account created successfully!'})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email, password = data.get('email'), data.get('password')

    if not all([email, password]):
        return jsonify({'success': False, 'error': 'Please enter both email and password.'}), 400
    
    user_data = users_collection.find_one({"email": email})

    if user_data and user_data.get('password') == password:
        new_session_id = str(uuid.uuid4())
        users_collection.update_one({'_id': user_data['_id']}, {'$set': {'session_id': new_session_id}})
        user_data['session_id'] = new_session_id
        user_obj = User(user_data)
        login_user(user_obj)
        session['session_id'] = new_session_id
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Incorrect email or password.'}), 401

@app.route('/get_user_info')
@login_required
def get_user_info():
    user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
    return jsonify({
        "name": current_user.name,
        "email": current_user.email,
        "isAdmin": current_user.isAdmin,
        "isPremium": current_user.isPremium,
        "usageCounts": user_data.get('usage_counts', {"messages": 0})
    })

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True})

# --- Chat History & Library API (Simplified for brevity) ---
@app.route('/api/chats', methods=['GET'])
@login_required
def get_chats():
    chats = list(conversations_collection.find({"user_id": ObjectId(current_user.id)}).sort("timestamp", -1))
    for chat in chats:
        chat['id'] = str(chat['_id'])
        del chat['_id']
        del chat['user_id']
    return jsonify(chats)

@app.route('/api/chats', methods=['POST'])
@login_required
def save_chat():
    data = request.get_json()
    chat_id = data.get('id')
    messages = data.get('messages', [])
    if not messages: return jsonify({"status": "empty chat, not saved"})
    
    title = next((m.get('text', '') for m in messages if m.get('sender') == 'user'), "New Chat")[:40]
    user_id = ObjectId(current_user.id)

    if chat_id:
        conversations_collection.update_one(
            {"_id": ObjectId(chat_id), "user_id": user_id},
            {"$set": {"messages": messages, "title": title, "timestamp": datetime.utcnow()}}
        )
        return jsonify({"id": chat_id})
    else:
        result = conversations_collection.insert_one({
            "user_id": user_id, "title": title, "messages": messages, "timestamp": datetime.utcnow()
        })
        return jsonify({"id": str(result.inserted_id), "title": title})

# --- Main Chat Logic ---
@app.route('/chat', methods=['POST'])
@login_required
def chat():
    # --- Daily Usage Limit Check and Reset ---
    updated_usage_counts = {"messages": 0} # Default for admin/premium
    if not current_user.isPremium and not current_user.isAdmin:
        user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
        last_reset_date = datetime.strptime(user_data.get('last_usage_reset', '1970-01-01'), '%Y-%m-%d').date()
        today = datetime.utcnow().date()

        if last_reset_date < today:
            users_collection.update_one(
                {'_id': ObjectId(current_user.id)},
                {'$set': {'usage_counts': {'messages': 0, 'webSearches': 0}, 'last_usage_reset': today.strftime('%Y-%m-%d')}}
            )
            user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
        
        messages_used = user_data.get('usage_counts', {}).get('messages', 0)
        
        if messages_used >= 15:
            return jsonify({'error': 'You have reached your daily message limit.', 'upgrade_required': True}), 429
            
        users_collection.update_one({'_id': ObjectId(current_user.id)}, {'$inc': {'usage_counts.messages': 1}})
        
        # Fetch the latest count to send back to the UI
        updated_user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
        updated_usage_counts = updated_user_data.get('usage_counts')

    # --- AI Response Logic (Simplified) ---
    data = request.json
    user_message = data.get('text', '')
    
    # Placeholder for your generative AI call
    ai_response = f"This is a placeholder response to your message: '{user_message}'"
    
    return jsonify({
        'response': ai_response,
        'userInfo': {
            'usageCounts': updated_usage_counts,
            'isPremium': current_user.isPremium,
            'isAdmin': current_user.isAdmin
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

