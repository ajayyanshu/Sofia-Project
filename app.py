import base64
import io
import os
import re
import sys
from datetime import datetime

import docx
import fitz  # PyMuPDF
import google.generativeai as genai
import requests
from flask import Flask, jsonify, render_template, request
from PIL import Image
from pymongo import MongoClient
from youtube_transcript_api import YouTubeTranscriptApi
# --- NEW: Imports for Authentication ---
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, JWTManager, get_jwt_identity

app = Flask(__name__, template_folder='templates')

# --- Securely Load API Keys from Render Environment ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
OPENROUTER_API_KEY_V3 = os.environ.get("OPENROUTER_API_KEY_V3")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
# --- NEW: Secret key for JWT ---
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "default-super-secret-key-for-dev")

# --- NEW: Initialize JWT Manager ---
jwt = JWTManager(app)

# --- Configure API Services ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not found.")

if not OPENROUTER_API_KEY_V3:
    print("WARNING: OPENROUTER_API_KEY_V3 not found. OpenRouter will be skipped.")
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not found. Groq API will be skipped.")


# --- MongoDB Configuration (with users collection) ---
chat_history_collection = None
users_collection = None # <-- ADDED
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client.get_database("ai_assistant_db")
        chat_history_collection = db.get_collection("chat_history")
        users_collection = db.get_collection("users") # <-- ADDED
        print("✅ Successfully connected to MongoDB.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to MongoDB. Error: {e}")
else:
    print("WARNING: MONGO_URI environment variable not found.")


# --- GitHub PDF Configuration ---
GITHUB_USER = "ajayyanshu"
# ... (rest of config is the same)
GITHUB_REPO = "collegeproject"
GITHUB_FOLDER_PATH = "upload pdf"
PDF_KEYWORDS = {
    "2016 hindi paper": "2016 - Hindi (7402-01).pdf",
    "2023 english paper": "2023 - English (7403-01).pdf",
    "2023 hindi paper": "2023 - Hindi (7402-01).pdf",
    "2025 english paper": "2025 - English (7403-01).pdf",
    "2025 hindi paper": "2025 - Hindi (7402-01).pdf"
}


@app.route('/')
def home():
    return render_template('coming_soon.html')


# --- NEW: Authentication Routes ---
@app.route('/signup', methods=['POST'])
def signup():
    if not users_collection:
        return jsonify({"msg": "Database not configured"}), 500
        
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"msg": "Username and password are required"}), 400

    if users_collection.find_one({"username": username}):
        return jsonify({"msg": "Username already exists"}), 409

    hashed_password = generate_password_hash(password)
    users_collection.insert_one({"username": username, "password": hashed_password})

    return jsonify({"msg": "User created successfully"}), 201

@app.route('/login', methods=['POST'])
def login():
    if not users_collection:
        return jsonify({"msg": "Database not configured"}), 500

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = users_collection.find_one({"username": username})

    if user and check_password_hash(user['password'], password):
        # Identity can be the string representation of the user's MongoDB ObjectId
        access_token = create_access_token(identity=str(user['_id']))
        return jsonify(access_token=access_token)

    return jsonify({"msg": "Bad username or password"}), 401


# --- Helper Functions for File Processing (No changes) ---
def extract_text_from_pdf(pdf_bytes):
# ... (function is the same)
    try:
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "".join(page.get_text() for page in pdf_document)
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""

def extract_text_from_docx(docx_bytes):
# ... (function is the same)
    try:
        document = docx.Document(io.BytesIO(docx_bytes))
        return "\n".join([para.text for para in document.paragraphs])
    except Exception as e:
        print(f"Error extracting DOCX text: {e}")
        return ""

def get_file_from_github(filename):
# ... (function is the same)
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{GITHUB_FOLDER_PATH.replace(' ', '%20')}/{filename.replace(' ', '%20')}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(f"Successfully downloaded {filename} from GitHub.")
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error downloading from GitHub: {e}")
        return None

def get_video_id(video_url):
# ... (function is the same)
    video_id_match = re.search(r"(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})",
                               video_url)
    return video_id_match.group(1) if video_id_match else None

def get_youtube_transcript(video_id):
# ... (function is the same)
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([d['text'] for d in transcript_list])
    except Exception as e:
        print(f"Error getting YouTube transcript: {e}")
        return None

# --- Helper Functions for APIs (No changes) ---
def call_openrouter_api(user_message):
# ... (function is the same)
    api_key = OPENROUTER_API_KEY_V3
    model_name = "deepseek/deepseek-chat"
    if not api_key:
        return None
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model_name, "messages": [{"role": "user", "content": user_message}]}
        )
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"Error calling OpenRouter API for model {model_name}: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Error parsing OpenRouter API response: {e}")
        return None

def call_groq_api(user_message):
# ... (function is the same)
    if not GROQ_API_KEY:
        return None
    try:
        response = requests.post(
            url="https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": user_message}]
            }
        )
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"Error calling Groq API: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Error parsing Groq API response: {e}")
        return None

# --- Main Chat Logic (Now protected and personalized) ---
@app.route('/chat', methods=['POST'])
@jwt_required() # <-- THIS PROTECTS THE ROUTE
def chat():
    try:
        # --- NEW: Get the ID of the logged-in user ---
        current_user_id = get_jwt_identity()

        data = request.json
        user_message = data.get('text', '')
        file_data = data.get('fileData')
        file_type = data.get('fileType', '')
        
        ai_response = ""
        api_used = ""
        model_logged = ""
        
        is_youtube_link = "youtube.com" in user_message or "youtu.be" in user_message
        matched_github_keyword = any(keyword in user_message.lower() for keyword in PDF_KEYWORDS)
        is_multimodal_request = bool(file_data) or is_youtube_link or matched_github_keyword

        # Route 1: Text-only chat
        if not is_multimodal_request and user_message.strip():
            print("Routing to OpenRouter with DeepSeek model.")
            ai_response = call_openrouter_api(user_message)
            if ai_response:
                api_used = "OpenRouter"
                model_logged = "deepseek/deepseek-chat"
            
            if not ai_response:
                print("OpenRouter failed, trying Groq as a second option.")
                ai_response = call_groq_api(user_message)
                if ai_response:
                    api_used = "Groq"
                    model_logged = "llama3-8b-8192"

        # Route 2: Fallback or Multimodal to Gemini
        if not ai_response:
            print("Routing to Gemini for multimodal request or as a final fallback.")
            api_used = "Gemini"
            model_logged = "gemini-1.5-flash"
            # ... (rest of Gemini logic is the same)
            model = genai.GenerativeModel(model_logged)
            prompt_parts = []
            if user_message:
                prompt_parts.append(user_message)
            if is_youtube_link:
                video_id = get_video_id(user_message)
                if video_id:
                    transcript = get_youtube_transcript(video_id)
                    prompt_parts = [f"Summarize this YouTube video transcript:\n\n{transcript}"] if transcript else []
                if not prompt_parts: return jsonify({'response': "Sorry, couldn't get the transcript for that video."})
            elif matched_github_keyword:
                filename = next((fname for kw, fname in PDF_KEYWORDS.items() if kw in user_message.lower()), None)
                file_bytes = get_file_from_github(filename)
                if file_bytes: prompt_parts.append(f"\n--- Document: {filename} ---\n{extract_text_from_pdf(file_bytes)}")
                else: return jsonify({'response': f"Sorry, I could not download '{filename}'."})
            elif file_data:
                file_bytes = base64.b64decode(file_data)
                if 'pdf' in file_type: prompt_parts.append(f"\n--- Uploaded PDF ---\n{extract_text_from_pdf(file_bytes)}")
                elif 'word' in file_type: prompt_parts.append(f"\n--- Uploaded Document ---\n{extract_text_from_docx(file_bytes)}")
                elif 'image' in file_type: prompt_parts.append(Image.open(io.BytesIO(file_bytes)))
                else: return jsonify({'response': f"Sorry, unsupported file type '{file_type}'."})
            if not prompt_parts: return jsonify({'response': "Please ask a question or upload a file."})
            if any(isinstance(p, Image.Image) for p in prompt_parts) and not any(isinstance(p, str) and p.strip() for p in prompt_parts):
                prompt_parts.insert(0, "Describe this image in detail.")
            response = model.generate_content(prompt_parts)
            ai_response = response.text

        # --- Save to MongoDB with user ID ---
        if chat_history_collection is not None and ai_response:
            try:
                chat_history_collection.insert_one({
                    "user_id": current_user_id, # <-- ADDED
                    "user_message": user_message, "ai_response": ai_response,
                    "api_used": api_used, "model_used": model_logged,
                    "has_file": bool(file_data), "file_type": file_type if file_data else None,
                    "timestamp": datetime.utcnow()
                })
            except Exception as e:
                print(f"Error saving chat to MongoDB: {e}")

        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"A critical error occurred: {e}")
        user_facing_error = "Sorry, something went wrong. Please try again."
        return jsonify({'response': user_facing_error})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

