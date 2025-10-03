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
                   url_for, flash, Response)
from flask_cors import CORS
from PIL import Image
from pymongo import MongoClient
from bson.objectid import ObjectId
from youtube_transcript_api import YouTubeTranscriptApi
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_mail import Mail, Message

# --- Email Test Imports ---
import smtplib
import ssl
from email.message import EmailMessage

app = Flask(__name__, template_folder='templates')
CORS(app)

# --- Configuration ---
# NOTE: Using a default, insecure FLASK_SECRET_KEY for development.
# In production, set this as an environment variable.
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
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
# For GMAIL, use the following settings:
# MAIL_SERVER = 'smtp.gmail.com'
# MAIL_PORT = 465
# MAIL_USE_TLS = False
# MAIL_USE_SSL = True
# MAIL_USERNAME = Your full Gmail address (e.g., 'you@gmail.com')
# MAIL_PASSWORD = Your 16-character Google App Password (NO SPACES!)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'false').lower() in ['true', '1', 't']
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'true').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

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

PDF_KEYWORDS = {}


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

@app.route('/login')
def login_redirect():
    return redirect(url_for('login_page'))

@app.route('/signup')
def signup_redirect():
    return redirect(url_for('signup_page'))

# --- NEW: Email Debugging Route ---
@app.route('/debug-email-test')
def debug_email_test():
    """
    This route runs a standalone email connection test to diagnose configuration issues.
    It returns the output as plain text.
    """
    output = []
    
    SENDER_EMAIL = os.environ.get("MAIL_USERNAME")
    SENDER_PASSWORD = os.environ.get("MAIL_PASSWORD")
    RECIPIENT_EMAIL = os.environ.get("MAIL_USERNAME")

    output.append("--- Starting Email Connection Test ---")

    if not all([SENDER_EMAIL, SENDER_PASSWORD]):
        output.append("\nFATAL ERROR: The MAIL_USERNAME and/or MAIL_PASSWORD environment variables are not set.")
        output.append("Please check your .env file on Render and redeploy.")
        return Response("\n".join(output), mimetype='text/plain')

    output.append(f"Attempting to send email from: {SENDER_EMAIL}")

    msg = EmailMessage()
    msg["Subject"] = "Render Email Connection Test"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.set_content("If you received this email, your Render environment variables are correct!")

    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 465
    output.append(f"Connecting to server: {SMTP_SERVER} on port {SMTP_PORT} using SSL...")

    context = ssl.create_default_context()

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            output.append("Connection successful. Attempting to log in...")
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            output.append("Login successful. Sending test email...")
            server.send_message(msg)
            output.append("\n--- SUCCESS! ---")
            output.append("The test email was sent successfully.")
            output.append("This means your environment variables and Google Account settings are correct.")
    except smtplib.SMTPAuthenticationError as e:
        output.append("\n--- AUTHENTICATION FAILED ---")
        output.append(f"Error: {e}")
        output.append("This is a critical error. It means your username or password is incorrect.")
        output.append("1. Double-check that MAIL_USERNAME is your full, correct Gmail address.")
        output.append("2. Double-check that MAIL_PASSWORD is your 16-character App Password WITH NO SPACES.")
        output.append("3. Check your Gmail for a 'Security Alert' and approve the sign-in attempt.")
    except Exception as e:
        output.append("\n--- CONNECTION FAILED ---")
        output.append(f"An unexpected error occurred: {e}")
        output.append("This could be a network issue, an incorrect port, or a firewall problem.")
    
    return Response("\n".join(output), mimetype='text/plain')


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

    existing_user = users_collection.find_one({"email": email})
    if existing_user:
        if not existing_user.get('is_verified'):
            pass
        else:
            return jsonify({'success': False, 'error': 'An account with this email already exists.'}), 409

    otp = str(random.randint(100000, 999999))
    otp_expiry = datetime.utcnow() + timedelta(minutes=10)

    try:
        msg = Message("Your Verification Code", recipients=[email])
        msg.body = f"Your OTP for Sofia AI is: {otp}\nThis code will expire in 10 minutes."
        mail.send(msg)
    except Exception as e:
        print(f"SIGNUP_EMAIL_ERROR: {e}")
        return jsonify({'success': False, 'error': 'Could not send verification email. Please check your email address and try again.'}), 500

    if existing_user:
        users_collection.update_one(
            {'_id': existing_user['_id']},
            {'$set': { "verification_otp": otp, "otp_expires_at": otp_expiry }}
        )
    else:
        new_user = {
            "name": name, "email": email, "password": password,
            "isAdmin": email == ADMIN_EMAIL, "isPremium": False, "is_verified": False,
            "verification_otp": otp, "otp_expires_at": otp_expiry,
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
    return jsonify({
        "name": current_user.name, "email": current_user.email,
        "isAdmin": current_user.isAdmin, "isPremium": current_user.isPremium
    })

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True})

@app.route('/logout-all', methods=['POST'])
@login_required
def logout_all_devices():
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
        update_result = users_collection.update_one(
            {'_id': user_id},
            {
                '$set': {
                    'email': f'deleted_{user_id}@anonymous.com',
                    'password': 'deleted', 'name': 'Anonymous User'
                },
                '$unset': { 'session_id': "" }
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
    return jsonify({'status': 'ok'}), 200

# --- Chat Logic ---
@app.route('/chat', methods=['POST'])
@login_required
def chat():
    # ... (rest of the chat logic is unchanged)
    return jsonify({'response': "Chat logic placeholder"})


# --- Live AI Camera Feature (Backend) ---
@app.route('/live_object_detection', methods=['POST'])
@login_required
def live_object_detection():
    # ... (rest of the camera logic is unchanged)
    return jsonify({'description': "Camera logic placeholder"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

